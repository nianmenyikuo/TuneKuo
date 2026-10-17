# 开发模式启动（需要本机有 Python 3.10+ / tkinter / python-vlc / Pillow）
param([Parameter(ValueFromRemainingArguments = $true)]$Files)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

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
  throw "没有找到可用的 Python，请先安装 Python 3.10 以上版本（安装时勾选 tcl/tk）。"
}

$py = Find-Python
Write-Host "Python: $py"
& $py (Join-Path $root 'app\main.py') @Files
exit $LASTEXITCODE
