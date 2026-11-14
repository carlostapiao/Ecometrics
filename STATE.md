# EcoMetrics — Estado actual

Actualizado: 2026-11-14. Despliegue en Azure implementado, verificado de punta a punta por HTTPS y destruido temporalmente (**Opción B**) para preservar créditos de *Azure for Students* hasta la presentación. Plan vigente: [specs/PLAN-AZURE.md](specs/PLAN-AZURE.md). Alcance y decisiones: [SPEC.md](SPEC.md).

## Construido y verificado

- Monolito Django + PostgreSQL con Docker Compose; acceso local en `http://localhost:8010/` servido con **Gunicorn + WhiteNoise** (`132` archivos estáticos compilados en `/var/lib/ecometrics/staticfiles`).
- Autenticación por rol, gestión de sedes y operarios, activación por enlace temporal y contraseña personal. Corrección CSRF aplicada con política `same-origin`.
- Pesajes con dos decimales, historial propio, correcciones/anulaciones gerenciales y trazabilidad. Protección contra duplicados, formularios obsoletos y exceso de cantidades.
- Operario: captura e historial propios. Gerencia: Dashboard, Sedes y plantas, Pesajes, Reportes y Personal. Retiradas las pantallas, rutas, descargas y navegación de Conciliación/Salidas de ambos perfiles.
- Preparación cloud (Fase 1): `requirements.txt` actualizado con `gunicorn`, `whitenoise`, `django-storages[azure]` y `azure-storage-blob`; `settings.py` parametrizado para `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECURE_SSL`, `POSTGRES_SSLMODE`, `STATIC_ROOT` fuera de `/app` y `AzureStorage` condicional (`expiration_secs = 3600`); `.gitignore` y `.dockerignore` endurecidos.
- Infraestructura y CI/CD (Fases 2 y 3):
  - `infra/terraform/bootstrap/` aplicado en `mexicocentral` (`rg-ecom-tfstate-mxc`, `stecomtffgnin1`, contenedor `tfstate`).
  - `infra/terraform/environments/dev/` organizado en 4 módulos (`observabilidad`, `datos`, `aplicacion`, `github_oidc`) con estado remoto y rol `User Access Administrator` sobre `rg-ecom-dev-mxc` para el SP OIDC de GitHub.
  - Repositorio público `carlostapiao/Ecometrics` configurado en rama `main` con OIDC (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`), secrets y variables de despliegue.
  - Flujos `.github/workflows/deploy.yml` (verificación en PostgreSQL, build ACR, migraciones y despliegue en Container Apps) y `.github/workflows/destroy.yml` (destrucción selectiva con confirmación `DESTROY`).
- Verificación en vivo ejecutada en Azure (Fases 4 y 5):
  - GitHub Actions `deploy.yml` ([run 43652776016](https://github.com/carlostapiao/Ecometrics/actions/runs/43652776016)): `verify` (`35s`) y `deploy` (`3m33s`) en verde sobre commit `9384b63`.
  - Carga inicial (`preparar_demo` -> `DEMO_PREPARADA=OK`) y prueba de persistencia en Blob Storage (`comprobar_persistencia` -> `PERSISTENCIA_ARCHIVOS=OK` en contenedor privado `evidencias`).
  - Prueba HTTPS E2E (`AZURE_E2E_VERIFICATION=OK`): `/healthz`, `/readyz`, `/static/app.css` y `/login/` en `200`; login de `operario_norte` (`200`), registro de pesaje (`12.50 kg` -> redirect `200`), login de `gerente_demo` (`200`), exportación CSV (`200`, `lines= 2`, `contains_12.50= True`) y ruta retirada `/gerencia/conciliacion/` en `404`. Sin reglas temporales residuales en el firewall de PostgreSQL (`["AllowAzureServices"]`).
- Apagado temporal ejecutado (Opción B):
  - Flujo `.github/workflows/destroy.yml` ([run 43653896173](https://github.com/carlostapiao/Ecometrics/actions/runs/43653896173)) completado en verde (`1m3s`).
  - Verificación con `az resource list`: `rg-ecom-dev-mxc` quedó sin Container App, CAE, ACR, PostgreSQL, Storage ni Log Analytics/App Insights (solo el action group `Application Insights Smart Detection` sin costo); se conservan `rg-ecom-tfstate-mxc` (`stecomtffgnin1`), el `resource group` `rg-ecom-dev-mxc` y la identidad OIDC de GitHub para reaprovisionar sin reconfigurar secrets.

## Siguiente acción exacta

Cuando Carlos necesite levantar el entorno para pruebas finales o el día de la presentación:
1. Ejecutar `terraform apply` en `infra/terraform/environments/dev/`.
2. Lanzar el workflow manual `deploy.yml` en `carlostapiao/Ecometrics` (para compilar/publicar la imagen en el ACR recién creado, correr migraciones en PostgreSQL y actualizar el Container App).
3. Ejecutar `preparar_demo` contra el PostgreSQL aprovisionado para recrear las 2 sedes y 4 cuentas de demostración.
4. Al terminar la exposición, ejecutar `destroy.yml` con `confirm = DESTROY` para volver a costo ~\$0.00.

## Límites técnicos vigentes

- Entorno Azure actualmente **destruido temporalmente** (solo persiste el backend remoto Terraform `stecomtffgnin1` y la identidad OIDC de GitHub). Al recrear con `terraform apply`, la base de datos y las imágenes ACR parten limpias.
- Secretos y accesos locales privados (`azure-secrets.json`, `accesos-demo-azure.json`) y `backend.hcl`/`terraform.tfvars` quedan exclusivamente fuera de Git bajo `.private/` y `infra/terraform/environments/dev/`.
- Entorno local Docker Compose sigue disponible en `http://localhost:8010/`.
- Modelos y documentos de retiros previos se conservan para integridad. Activación con enlace compartido manualmente; sin envío de correo ni dominio personalizado (usa subdominio HTTPS de Container Apps).
