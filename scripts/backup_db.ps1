# 数据库备份：把题库导出成带时间戳的 .sql，并只保留最近 N 份
#
# 用法：
#   .\scripts\backup_db.ps1              # 备份一次，保留最近 14 份
#   .\scripts\backup_db.ps1 -Keep 30     # 保留最近 30 份
#
# 说明：
#   * 备份文件放在 backups\，文件名形如 english_exam_20261030-114500.sql
#   * 密码通过临时 defaults 文件传给 mysqldump，不出现在命令行里，导出后立即删除
#   * media\ 里的图片/音频不在此脚本范围内，如需要请单独复制该目录

param(
    [int]$Keep = 14
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# ---------------------------------------------------------------- 读取 .env
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "未找到 .env，请先按 .env.example 配置数据库连接" -ForegroundColor Red
    exit 1
}

$config = @{}
foreach ($line in Get-Content $envFile -Encoding UTF8) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
    $split = $trimmed.IndexOf("=")
    $config[$trimmed.Substring(0, $split).Trim()] = $trimmed.Substring($split + 1).Trim()
}

$dbName = if ($config["MYSQL_DATABASE"]) { $config["MYSQL_DATABASE"] } else { "english_exam" }
$dbHost = if ($config["MYSQL_HOST"]) { $config["MYSQL_HOST"] } else { "127.0.0.1" }
$dbPort = if ($config["MYSQL_PORT"]) { $config["MYSQL_PORT"] } else { "3306" }
$dbUser = if ($config["MYSQL_USER"]) { $config["MYSQL_USER"] } else { "root" }
$dbPass = $config["MYSQL_PASSWORD"]

# ---------------------------------------------------------------- 定位 mysqldump
$dump = $null
foreach ($candidate in Get-Command mysqldump -ErrorAction SilentlyContinue) { $dump = $candidate.Source }
if (-not $dump) {
    $found = Get-ChildItem "C:\Program Files\MySQL\*\bin\mysqldump.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
    if ($found) { $dump = $found.FullName }
}
if (-not $dump) {
    Write-Host "未找到 mysqldump.exe，请把 MySQL 的 bin 目录加入 PATH 后重试" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------- 准备输出
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $root "backups"
if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir | Out-Null }
$target = Join-Path $backupDir "${dbName}_$stamp.sql"

$defaultsFile = Join-Path $env:TEMP "examgen_mysqldump_$stamp.cnf"
@"
[client]
user=$dbUser
password=$dbPass
host=$dbHost
port=$dbPort
default-character-set=utf8mb4
"@ | Set-Content -Path $defaultsFile -Encoding ASCII

Write-Host "正在备份 $dbName -> $target" -ForegroundColor Cyan
try {
    & $dump "--defaults-extra-file=$defaultsFile" `
        --single-transaction --quick --routines --events --set-gtid-purged=OFF `
        --databases $dbName > $target
    if ($LASTEXITCODE -ne 0) { throw "mysqldump 退出码 $LASTEXITCODE" }
}
finally {
    if (Test-Path $defaultsFile) { Remove-Item $defaultsFile -Force }
}

$size = [math]::Round((Get-Item $target).Length / 1KB, 1)
Write-Host "备份完成：$size KB" -ForegroundColor Green

# ---------------------------------------------------------------- 清理旧备份
$old = Get-ChildItem $backupDir -Filter "${dbName}_*.sql" |
    Sort-Object LastWriteTime -Descending | Select-Object -Skip $Keep
if ($old) {
    $old | ForEach-Object { Remove-Item $_.FullName -Force }
    Write-Host "已清理 $($old.Count) 份超过保留期（$Keep 份）的旧备份" -ForegroundColor Gray
}
