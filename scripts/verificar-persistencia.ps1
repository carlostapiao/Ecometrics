# Recrea exclusivamente los contenedores de este proyecto y conserva el volumen.
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $taskMarker = [Guid]::NewGuid().ToString('N')
    docker compose exec -T web python manage.py comprobar_persistencia escribir $taskMarker
    if ($LASTEXITCODE -ne 0) { throw 'No se guardó la marca técnica' }
    docker compose up -d --no-build --force-recreate --wait --wait-timeout 90
    if ($LASTEXITCODE -ne 0) { throw 'La recreación no se completó' }
    docker compose exec -T web python manage.py comprobar_persistencia comprobar $taskMarker
    if ($LASTEXITCODE -ne 0) { throw 'No se comprobó la persistencia' }
} finally { Pop-Location }
