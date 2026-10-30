# EcoMetrics — Estado actual

Actualizado: 2026-10-29. Alcance y decisiones: [SPEC.md](SPEC.md).

## Construido y verificado

- Monolito Django + PostgreSQL con Docker Compose; acceso local en `http://localhost:8010/`.
- Autenticación por rol, gestión de sedes y operarios, activación por enlace temporal y contraseña personal. Corrección CSRF aplicada con política `same-origin`.
- Pesajes con dos decimales, historial propio, correcciones/anulaciones gerenciales y trazabilidad. Protección contra duplicados, formularios obsoletos y exceso de cantidades.
- Operario: salidas parciales de pesajes propios de su sede actual activa, recepción y respaldos privados. Gerencia: consulta multisede, registro alternativo y cierre/reapertura/anulación exclusivos. Se conserva la conciliación actual.
- Dashboard diferencia generación, salida y recepción por sus respectivas fechas. Reportes con filtros, CSV y HTML imprimible. Carlos confirmó la impresión y revisó la adaptación móvil del Dashboard.
- Última suite completa: **102 pruebas aprobadas contra PostgreSQL aislado**, con verificaciones de Compose, Django, migraciones y dependencias; alta HTTP como operario y reintento sin duplicación comprobados adicionalmente. No se reejecutaron para esta actualización documental.
- Persistencia y recuperación aislada de un respaldo comprobadas: tablas, secuencias y archivos coincidentes.

## Siguiente acción exacta

Confirmar en Chrome la activación de un operario mediante un enlace nuevo: definir contraseña, obtener «Cuenta activada» e iniciar sesión con esa cuenta. La corrección pasó pruebas automáticas; falta confirmación manual explícita del resultado.

## Límites técnicos vigentes

- Entorno local con DEBUG y servidor de desarrollo; sin despliegue ni acceso remoto preparado. La vista móvil emulada no acredita conectividad desde un teléfono real.
- Pruebas automáticas y capturas parciales no acreditan todos los recorridos visuales; queda por completar la revisión manual de Salidas, recepción, respaldo y cierre gerencial.
- Respaldos privados en la misma computadora; código y `.env` se conservan por separado. No hay copia externa configurada.
- Activación con enlace compartido manualmente; sin envío de correo. PDF mediante impresión del navegador. Sin certificación ASG ni acreditación automática de reciclaje o tratamiento.
