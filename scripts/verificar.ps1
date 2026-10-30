$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Compose inválido' }
    docker compose exec -T web python manage.py check
    if ($LASTEXITCODE -ne 0) { throw 'Falló check' }
    docker compose exec -T web python manage.py makemigrations --check --dry-run
    if ($LASTEXITCODE -ne 0) { throw 'Hay cambios de modelo sin migración' }
    docker compose exec -T web python -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependencias incompatibles' }
    docker compose exec -T web python manage.py test --noinput
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas' }
    Write-Output 'VERIFICACION_BASE=OK'
} finally { Pop-Location }
