$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location $taskRoot
try {
    $taskPrivate = Join-Path $taskRoot '.private'
    $null = New-Item -ItemType Directory -Path $taskPrivate -Force
    $taskCredPath = Join-Path $taskPrivate 'accesos-demo.json'
    if (-not (Test-Path -LiteralPath $taskCredPath)) {
        $taskCreds = [ordered]@{}
        $taskRng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            foreach($taskUser in @('operario_norte','operario_norte_2','operario_sur','gerente_demo')) {
                $taskBytes = New-Object byte[] 24
                $taskRng.GetBytes($taskBytes)
                $taskCreds[$taskUser] = [Convert]::ToBase64String($taskBytes)
            }
        } finally { $taskRng.Dispose() }
        [IO.File]::WriteAllText($taskCredPath, ($taskCreds | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    }
    Get-Content -LiteralPath $taskCredPath -Raw | docker compose exec -T web python manage.py preparar_demo
    if ($LASTEXITCODE -ne 0) { throw 'No se prepararon las cuentas. Se conservaron las existentes.' }
    Write-Output 'Accesos guardados en .private/accesos-demo.json; no compartir ni versionar.'
} finally { Pop-Location }
