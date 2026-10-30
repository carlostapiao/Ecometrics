param(
    [ValidateSet('crear', 'verificar')][string]$Accion = 'crear',
    [string]$Carpeta
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
python (Join-Path $PSScriptRoot 'respaldo_local.py') $Accion --raiz $taskRoot --carpeta "$Carpeta"
if ($LASTEXITCODE -ne 0) { throw 'El respaldo o su restauración no se completaron. Consulta el mensaje anterior.' }
