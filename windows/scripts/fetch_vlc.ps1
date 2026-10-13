# 下载 64 位 VLC 运行库到 vendor\vlc64（打包时会一起复制到 dist\TuneKuo\vlc）
# 用法: pwsh -File scripts\fetch_vlc.ps1
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$dest = Join-Path $root 'vendor\vlc64'
$ver  = '3.0.24'
$urls = @(
  "https://mirrors.tuna.tsinghua.edu.cn/videolan-ftp/vlc/$ver/win64/vlc-$ver-win64.zip",
  "https://mirrors.ustc.edu.cn/videolan-ftp/vlc/$ver/win64/vlc-$ver-win64.zip",
  "https://download.videolan.org/vlc/$ver/win64/vlc-$ver-win64.zip"
)

if ((Test-Path (Join-Path $dest 'libvlc.dll'))) {
  Write-Host "已存在: $dest（如要重新下载请先删除该目录）" -ForegroundColor Green
  return
}

$zip = Join-Path $env:TEMP "vlc-$ver-win64.zip"
$stage = Join-Path $env:TEMP "vlc-$ver-stage"
$ok = $false
foreach ($u in $urls) {
  try {
    Write-Host "下载 $u"
    curl.exe -L --fail --silent --show-error --max-time 1800 -o $zip $u
    if ((Test-Path $zip) -and (Get-Item $zip).Length -gt 20000000) { $ok = $true; break }
  } catch { Write-Host "  失败: $($_.Exception.Message)" -ForegroundColor Yellow }
}
if (-not $ok) { throw "所有镜像都下载失败，请手动下载 vlc-$ver-win64.zip 并解压到 vendor\vlc64" }

if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
Expand-Archive -Path $zip -DestinationPath $stage -Force
$inner = Get-ChildItem $stage -Directory | Select-Object -First 1
if (-not $inner) { throw "压缩包结构异常" }
New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
Move-Item $inner.FullName $dest

# 只保留播放必需的部分，省下 60MB 左右
foreach ($d in 'locale', 'skins', 'hrtfs', 'msi', 'lua') {
  $p = Join-Path $dest $d
  if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}
foreach ($d in 'visualization', 'gui') {
  $p = Join-Path $dest "plugins\$d"
  if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}
foreach ($f in 'NEWS.txt', 'AUTHORS.txt', 'COPYING.txt', 'axvlc.dll', 'vlc.exe', 'vlc-cache-gen.exe') {
  $p = Join-Path $dest $f
  if (Test-Path $p) { Remove-Item $p -Force }
}
Remove-Item $zip -Force -ErrorAction SilentlyContinue
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue

$mb = [math]::Round(((Get-ChildItem $dest -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Host "完成: $dest ($mb MB)" -ForegroundColor Green
