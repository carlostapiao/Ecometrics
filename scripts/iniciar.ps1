$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location $taskRoot
try {
    $taskEnv = Join-Path $taskRoot '.env'
    if (-not (Test-Path -LiteralPath $taskEnv)) {
        $taskRng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $taskBytes = New-Object byte[] 48
            $taskRng.GetBytes($taskBytes)
            $taskSecret = [Convert]::ToBase64String($taskBytes)
            $taskRng.GetBytes($taskBytes)
            $taskPassword = [Convert]::ToBase64String($taskBytes)
            $taskContent = "DJANGO_SECRET_KEY=$taskSecret`nPOSTGRES_PASSWORD=$taskPassword`nPOSTGRES_DB=ecometrics`nPOSTGRES_USER=ecometrics`nWEB_PORT=8010`nDJANGO_DEBUG=true`n"
            [IO.File]::WriteAllText($taskEnv, $taskContent, [Text.UTF8Encoding]::new($false))
        } finally { $taskRng.Dispose() }
        Write-Output 'Configuración local generada; secretos omitidos de la salida.'
    }
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Configuración Compose inválida' }
    docker compose up --build -d --wait --wait-timeout 90
    if ($LASTEXITCODE -ne 0) { throw 'El arranque no se completó; revisar docker compose logs' }
    Write-Output 'Base local iniciada. Puerto predeterminado 8010; consulta WEB_PORT si lo cambiaste.'
} finally { Pop-Location }
