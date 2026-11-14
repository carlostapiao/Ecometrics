# EcoMetrics — Estado actual

Actualizado: 2026-11-14. Fases 1 y 2 de preparación cloud (Django/Docker + Terraform + GitHub Actions) implementadas, verificadas y aprobadas en revisión independiente. Plan vigente: [specs/PLAN-AZURE.md](specs/PLAN-AZURE.md). Alcance y decisiones: [SPEC.md](SPEC.md).

## Construido y verificado

- Monolito Django + PostgreSQL con Docker Compose; acceso local en `http://localhost:8010/` servido con **Gunicorn + WhiteNoise** (`132` archivos estáticos compilados en `/var/lib/ecometrics/staticfiles`).
- Autenticación por rol, gestión de sedes y operarios, activación por enlace temporal y contraseña personal. Corrección CSRF aplicada con política `same-origin`.
- Pesajes con dos decimales, historial propio, correcciones/anulaciones gerenciales y trazabilidad. Protección contra duplicados, formularios obsoletos y exceso de cantidades.
- Operario: captura e historial propios. Gerencia: Dashboard, Sedes y plantas, Pesajes, Reportes y Personal. Retiradas las pantallas, rutas, descargas y navegación de Conciliación/Salidas de ambos perfiles.
- Preparación cloud (Fase 1): `requirements.txt` actualizado con `gunicorn`, `whitenoise`, `django-storages[azure]` y `azure-storage-blob`; `settings.py` parametrizado para `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECURE_SSL`, `POSTGRES_SSLMODE`, `STATIC_ROOT` fuera de `/app` y `AzureStorage` condicional (`expiration_secs = 3600`); `.gitignore` y `.dockerignore` endurecidos.
- Infraestructura y CI/CD (Fase 2): `infra/terraform/bootstrap/` y `infra/terraform/environments/dev/` organizados en 4 módulos cohesivos (`observabilidad`, `datos`, `aplicacion`, `github_oidc`) en `mexicocentral`, más `.github/workflows/deploy.yml` para pruebas y despliegue OIDC desde `main`.
- Verificación del código actual tras la última edición: **92 pruebas aprobadas contra PostgreSQL aislado (`66.925s`)**, `check`, `makemigrations --check --dry-run` y `pip check` sin errores (`VERIFICACION_BASE=OK`); instanciación verificada de `AzureStorage` (`evidencias`, `3600`); `/healthz`, `/readyz`, `/static/app.css` y `/login/` responden `200` en local.
- Validación Terraform: `terraform fmt -recursive -check` y `terraform validate` aprobados en `bootstrap` y `environments/dev`.
- Revisión separada de Fases 1 y 2 aprobada tras revalidación dirigida, sin bloqueos pendientes.

## Siguiente acción exacta

Con autorización explícita de Carlos para acciones externas (`terraform apply` en Azure y `git push` a `carlostapiao/Ecometrics`), ejecutar la **Fase 3** (aprovisionamiento `bootstrap` + `dev` en `mexicocentral`), configurar los secrets/variables en GitHub y completar las **Fases 4 y 5** (`git push` en `main`, migraciones, `preparar_demo` y verificación HTTPS).

## Preparación de próximas fases

- Suscripción *Azure for Students* (`94846a8b-9491-4312-82bb-3082c340b45f`) comprobada con `mexicocentral` habilitada y proveedores en estado `Registered`.
- Detectado previamente en `gh auth status` que el token activo pertenece a `carlostapiaorellana`, mientras que el repositorio objetivo es `carlostapiao/Ecometrics`; confirmar o actualizar autenticación antes del `git push` y de configurar secrets en GitHub.
- No se han creado recursos en Azure ni se ha ejecutado `git push` todavía.

## Límites técnicos vigentes

- Entorno local con DEBUG y servidor de desarrollo; sin despliegue ni acceso remoto preparado. La vista móvil emulada no acredita conectividad desde un teléfono real.
- Modelos y documentos de retiros previos se conservan para integridad y recuperación. Sus restricciones sobre pesajes vinculados siguen vigentes, aunque esos retiros ya no se gestionan desde la interfaz. No se borraron datos ni volúmenes.
- Respaldos privados en la misma computadora; código y `.env` se conservan por separado. No hay copia externa configurada.
- Activación con enlace compartido manualmente; sin envío de correo. PDF mediante impresión del navegador. Sin certificación ASG ni acreditación automática de reciclaje o tratamiento.
