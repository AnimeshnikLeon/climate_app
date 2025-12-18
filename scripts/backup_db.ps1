$ErrorActionPreference = "Stop"

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = Join-Path $PSScriptRoot "..\backups"
$outFile = Join-Path $outDir ("climate_service_{0}.dump" -f $ts)

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# Берем значения из окружения (docker compose передает .env в контейнеры, но не в PowerShell),
# поэтому по умолчанию используем те же имена, что в .env.example.
$db = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "climate_service" }
$user = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "climate_user" }

$container = "climate_db"

docker exec -i $container pg_dump -U $user -F c -d $db | Set-Content -Encoding Byte -Path $outFile

Write-Host ("Backup created: {0}" -f $outFile)