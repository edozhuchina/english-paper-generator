# 一键启动小学英语出卷系统
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# 固定配置模块：否则会继承当前 shell 里的 DJANGO_SETTINGS_MODULE（例如自检脚本留下的
# config.settings_sqlite），数据就会悄悄写进自检用的 _selftest.sqlite3 而不是 MySQL。
$env:DJANGO_SETTINGS_MODULE = "config.settings"

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "未找到虚拟环境 .venv，请先执行：" -ForegroundColor Red
    Write-Host "  D:\Python312\python.exe -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt" -ForegroundColor Yellow
    Read-Host "按回车退出"
    exit 1
}

Write-Host "正在启动小学英语出卷系统..." -ForegroundColor Green
Write-Host "启动后请访问 http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "后台管理 http://127.0.0.1:8000/admin/" -ForegroundColor Cyan
Write-Host "（关闭本窗口即可停止服务）" -ForegroundColor Gray
Write-Host ""

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; & '$python' manage.py runserver 127.0.0.1:8000 --noreload"
Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:8000"
