# 打包 TuneKuo for Windows -> dist\TuneKuo\
param(
  [switch]$NoVlc,
  [switch]$NoInstall
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Find-Python {
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    $exe = (& py -3 -c "import sys;print(sys.executable)" 2>$null)
    if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
  }
  $p = Get-Command python -ErrorAction SilentlyContinue
  if ($p) {
    $exe = (& python -c "import sys;print(sys.executable)" 2>$null)
    if ($LASTEXITCODE -eq 0 -and $exe -and $exe -notlike '*WindowsApps*') { return $exe.Trim() }
  }
  throw "没有找到可用的 Python 3.10+。"
}

$python = Find-Python
Write-Host "Python : $python" -ForegroundColor Cyan

if (-not $NoInstall) {
  Write-Host "安装/更新依赖 ..." -ForegroundColor Cyan
  & $python -m pip install --disable-pip-version-check -r requirements.txt
}

Write-Host "生成图标 ..." -ForegroundColor Cyan
if (-not (Test-Path 'app\assets\icon.ico')) {
  & $python 'scripts\make_icon.py'
}

Write-Host "PyInstaller 打包 ..." -ForegroundColor Cyan
& $python -m PyInstaller `
  --noconfirm --clean --windowed --onedir `
  --name TuneKuo `
  --icon (Join-Path $root 'app\assets\icon.ico') `
  --hidden-import vlc `
  --hidden-import vlcenv `
  --hidden-import mediakeys `
  --hidden-import instance `
  --hidden-import PIL.Image `
  --hidden-import PIL.ImageTk `
  --distpath (Join-Path $root 'dist') --workpath (Join-Path $root 'build') `
  (Join-Path $root 'app\main.py')
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失败" }

$vlcSrc = Join-Path $root 'vendor\vlc64'
$vlcDst = Join-Path $root 'dist\TuneKuo\vlc'
if ($NoVlc) {
  Write-Host "跳过 libvlc 复制（将使用系统安装的 64 位 VLC）" -ForegroundColor Yellow
} elseif (Test-Path (Join-Path $vlcSrc 'libvlc.dll')) {
  Write-Host "复制 libvlc ..." -ForegroundColor Cyan
  if (Test-Path $vlcDst) { Remove-Item $vlcDst -Recurse -Force }
  Copy-Item $vlcSrc $vlcDst -Recurse -Force
} else {
  Write-Host "没有 vendor\vlc64，正在下载 ..." -ForegroundColor Yellow
  & (Join-Path $root 'scripts\fetch_vlc.ps1')
  if (Test-Path (Join-Path $vlcSrc 'libvlc.dll')) { Copy-Item $vlcSrc $vlcDst -Recurse -Force }
}

foreach ($docName in @('README.md', 'README-Windows.md')) {
  $docPath = Join-Path $root $docName
  if (Test-Path $docPath) {
    Copy-Item $docPath (Join-Path $root 'dist\TuneKuo\使用说明.md') -Force
    break
  }
}

$exe = Join-Path $root 'dist\TuneKuo\TuneKuo.exe'
if (Test-Path $exe) {
  $mb = [math]::Round(((Get-ChildItem (Join-Path $root 'dist\TuneKuo') -Recurse -File |
        Measure-Object Length -Sum).Sum / 1MB), 1)
  Write-Host "`n打包完成: $exe" -ForegroundColor Green
  Write-Host "整个目录 $mb MB —— 分发时把 dist\TuneKuo 整个文件夹打包给别人即可。" -ForegroundColor Green
} else {
  throw "没有生成 TuneKuo.exe"
}
