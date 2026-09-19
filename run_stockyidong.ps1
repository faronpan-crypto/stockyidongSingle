# 启动股票异动分析系统
Set-Location "$PSScriptRoot\src"

# 检查Python环境是否存在
if (Test-Path "..\.venv\Scripts\python.exe") {
    Write-Host "使用虚拟环境运行..."
    & "..\.venv\Scripts\python.exe" "stockyidong mac.py"
} else {
    Write-Host "虚拟环境不存在，使用系统Python运行..."
    & python "stockyidong mac.py"
}

# 等待用户按任意键退出
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
