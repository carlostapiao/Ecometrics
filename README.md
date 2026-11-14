# EcoMetrics

Proyecto piloto de Cerebro: aplicación web para registrar residuos manualmente, conservar trazabilidad y consultar indicadores por sede.

## Entrada

- [SPEC.md](SPEC.md): acuerdos del MVP, propuesta técnica y criterios de aceptación.
- [STATE.md](STATE.md): única fuente del avance actual y siguiente acción.
- `src/`: código Django, plantillas, estilos, migraciones y pruebas.
- `Dockerfile`, `compose.yaml`, `requirements.txt`: entorno local reproducible.
- `scripts/`: arranque y verificación desde PowerShell.

La raíz de trabajo es `C:/Carpeta de Carlos/Cerebro/projects/ecometrics/`. Las versiones anteriores de EcoMetrics son referencias históricas; su código, sus datos y sus procedimientos no se copian automáticamente. Los acuerdos actuales prevalecen sobre las especificaciones anteriores.

## Forma de trabajar

La metodología, incluida la revisión separada según el impacto del trabajo, se define en [AGENTS.md](../../AGENTS.md). El alcance está en SPEC y el avance y los pendientes en STATE; solo se crea un subplan adicional cuando ayude a resolver una complejidad concreta.

## Skills y herramientas

La skill compartida [planeador](../../.agents/skills/planeador/SKILL.md) puede concretar las decisiones iniciales y criterios de aceptación de SPEC. Su uso no exige otro agente, otro turno ni un sello para continuar dentro del trabajo autorizado.

La base técnica es inspección de archivos, edición, PowerShell y verificaciones de Django/PostgreSQL/Docker cuando se implemente la aplicación. La documentación oficial aporta referencia técnica, no una nueva aprobación.

Skills técnicas incorporadas: [django-expert](../../.agents/skills/django-expert/SKILL.md), [docker-project-foundations](../../.agents/skills/docker-project-foundations/SKILL.md), [docker-compose-patterns](../../.agents/skills/docker-compose-patterns/SKILL.md) y [frontend-design](../../.agents/skills/frontend-design/SKILL.md). Sus [fuentes y revisiones](../../.agents/skills/SOURCES.md) se conservan junto a ellas. Se cargan según la tarea, manteniendo plantillas y formularios de Django; no se incorporan DRF, Celery o Redis.

Para las pantallas se combinarán pruebas funcionales y revisión en navegador cuando esté disponible. Del sistema anterior solo se adaptó el planeador; no se importan automáticamente otros perfiles ni procedimientos.

Si el arranque o la validación se repiten, se reunirán en scripts del proyecto. Solo se extraerá una skill compartida si el procedimiento demuestra utilidad en varios proyectos.

## Arranque y verificación

Requisito: Docker Desktop con motor Linux y Docker Compose. Ejecutar desde esta carpeta en PowerShell:

```powershell
.\scripts\iniciar.ps1
.\scripts\verificar.ps1
```

Para comprobar persistencia recreando exclusivamente los contenedores de este proyecto y conservando sus volúmenes, ejecutar ` .\scripts\verificar-persistencia.ps1`. La comprobación guarda una marca técnica en sesiones y un pequeño archivo en el almacenamiento privado, sin usuarios autenticados ni datos de negocio. Comprueba ambas marcas tras la recreación; no sustituye una copia de seguridad ni la comprobación de registros concretos.

Si Windows bloquea el archivo por política de ejecución, usar `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\iniciar.ps1`; solo afecta ese proceso. No es necesario cambiar políticas permanentes.

El arranque genera `.env` con secretos aleatorios si no existe, construye la imagen, aplica migraciones mediante un servicio separado e inicia la web. Conservar `.env` entre arranques; si la base ya existe, cambiar su contraseña en este archivo no cambia la contraseña almacenada en PostgreSQL.

Abrir [EcoMetrics local](http://127.0.0.1:8010/). `WEB_PORT` en `.env` permite otro puerto. La web está limitada a localhost y PostgreSQL solo es accesible dentro de Compose. La instancia se llama `cerebro-ecometrics` y tiene su propio volumen; no comparte recursos con el EcoMetrics anterior.

```powershell
docker compose ps
docker compose logs --tail 50 web
docker compose down
```

`down` sin `-v` conserva el volumen. No usar `down -v`, borrar volúmenes ni reinicializar datos para solucionar un arranque.

`/healthz` comprueba el proceso y `/readyz` la conexión a PostgreSQL. El servidor de desarrollo de Django es exclusivamente local; un despliegue requiere configuración posterior. El panel técnico `/admin/` no sustituye los roles ni las pantallas del MVP. Consultar STATE para conocer la verificación efectuada.

## Probar el flujo por rol

Después del arranque, ejecutar `.\scripts\preparar-demo.ps1`. Crea dos sedes y cuatro cuentas ficticias, con contraseñas aleatorias distintas guardadas exclusivamente en `.private/accesos-demo.json`. Repetirlo no restablece contraseñas ni duplica cuentas. No compartir ese archivo; está excluido de Git y de la construcción Docker.

| Usuario | Rol | Sede |
| --- | --- | --- |
| operario_norte | Operario | Planta Norte |
| operario_norte_2 | Operario | Planta Norte |
| operario_sur | Operario | Planta Sur |
| gerente_demo | Gerente | Consulta multisede |

Abrir `/login/`. La identidad determina rol y sede; no hay selectores que permitan suplantarlos.

1. Con `operario_norte`, registrar plástico con `12.50` kg, fecha de hoy y una observación ficticia. Revisar el detalle y Mi historial. También se admite `12,50`; la presentación usa coma decimal en español.
2. Intentar `0`, un negativo o `12.501`: el formulario debe rechazarlos. Reenviar la misma operación no debe duplicarla.
3. Con `operario_norte_2`, comprobar que el historial no muestra registros del primer operario. Su URL de detalle responde 404. El acceso operario a `/gerencia/` responde 403.
4. Con `gerente_demo`, consultar el resumen por sede, fechas y categoría. La categoría reciclable expresa clasificación, no reciclaje efectivamente realizado.
5. Ejecutar `.\scripts\verificar.ps1` para comprobar permisos, validación, sumas, reintentos y escritura atómica del pesaje y su evento de creación contra PostgreSQL de prueba.

La interfaz toma la paleta verde, navegación móvil y distribución gerencial del prototipo anterior como referencia visual. La autenticación y persistencia se implementan en Django/PostgreSQL, sin importar su simulación en el navegador.

Para el primer avance de la rúbrica proporcionada, esta secuencia permite demostrar acceso y privilegios, interacción, validaciones y funcionamiento. El dominio técnico requiere explicar los modelos, las restricciones y las pruebas; el software no garantiza una calificación. Consultar STATE para el avance y los pendientes.

## Correcciones, anulaciones e indicadores

La navegación gerencial separa **Dashboard**, **Pesajes** y **Reportes**. En celular, se accede mediante **Menú**. Dashboard muestra indicadores; Pesajes permite buscar por número, operario u observación, filtrar vigentes/anulados y abrir su detalle. Reportes concentra selección y exportación de datos. Los nuevos módulos previstos y su avance están en SPEC y STATE.

Con `gerente_demo`, abrir un registro desde **Pesajes** y elegir **Corregir pesaje**. Se pueden ajustar categoría, peso, fecha de generación y observación; el motivo es obligatorio. Autor y sede originales se conservan. El detalle muestra quién cambió los datos, cuándo, por qué y los valores anteriores y nuevos.

**Anular pesaje** requiere motivo y marcar la confirmación. El registro sigue visible para su autor y gerencia, pero deja de sumar en todos los indicadores. Un anulado no admite nuevas correcciones ni otra anulación; no hay borrado físico ni restauración desde esta interfaz.

Si otro cambio se guarda mientras un formulario permanece abierto, el envío antiguo se rechaza. Volver al detalle y abrir un formulario nuevo permite revisar la versión actual antes de continuar.

El dashboard muestra pesajes vigentes por sede y categoría, y evolución por fecha de generación. Los filtros afectan a todas esas secciones. Los días sin registros se omiten, como indica la tabla; no se interpolan resultados. Los últimos registros incluyen anulados, claramente identificados, para acceder a su historia.

## Reportes gerenciales

Abrir **Reportes**, aplicar filtros de sede, categoría y fecha de generación y elegir **Descargar CSV** o **Ver reporte imprimible**. Ambos formatos incluyen todos los pesajes vigentes del filtro, independientemente de la paginación en Pesajes. Filtros inválidos impiden exportar. El acceso a los reportes es exclusivo del gerente.

El CSV usa UTF-8 con BOM, coma como delimitador y punto decimal con dos posiciones. El reporte de generación incluye identidad, sede, fecha, categoría, peso, observación, fecha de registro y versión. Los textos que podrían interpretarse como fórmulas se prefijan con apóstrofo al exportar; el dato almacenado no cambia. Si Excel no detecta el delimitador automáticamente, importar como CSV UTF-8 delimitado por comas.

La vista imprimible muestra filtros, usuario, fecha de emisión, registros y total. En Chrome o Edge, **Imprimir o guardar PDF** abre la impresión del navegador: elegir guardar como PDF, A4 horizontal y revisar la vista previa. Se oculta la navegación y se repiten cabeceras de tabla. No hay generador PDF en el servidor. Las verificaciones realizadas y los pendientes se consultan en [STATE.md](STATE.md).

## Sedes y Personal

**Sedes y plantas** permite añadir una unidad, editar su nombre/dirección y desactivarla. La desactivación bloquea el acceso operativo de sus operarios asignados y conserva los registros. Cada sede muestra peso y cantidad de pesajes vigentes, además del personal activo. La ficha conserva el historial de cambios.

En **Personal → Añadir personal**, completar nombres, usuario de acceso y sede activa; apellidos y correo son opcionales. Se crea exclusivamente un operario inactivo, sin contraseña utilizable. No se pueden crear gerentes ni cuentas técnicas desde este módulo.

La respuesta muestra un enlace privado de activación, válido 24 horas y para un solo uso. Se comparte manualmente con la persona: no se envían correos. El token se incluye después de `#`, de modo que no viaja en la URL de las peticiones HTTP. El navegador lo traslada al formulario y lo retira de la dirección visible; en la base solo se guarda su huella. La persona necesita JavaScript para procesar el enlace y debe definir una contraseña de al menos 12 caracteres que supere los validadores de Django.

El enlace se muestra únicamente al crearlo o reemitirlo. **Emitir nuevo enlace** invalida el anterior; **Revocar enlace** impide su uso. Guardar cambios en una cuenta pendiente revoca su enlace anterior. Las cuentas ya activadas no aceptan enlaces de activación como mecanismo de restablecimiento de contraseña.

Para cambiar sede o suspender/reactivar un operario, abrir **Gestionar personal**. Un cambio de sede solo afecta a los registros futuros; los anteriores conservan su sede original. Desmarcar **Acceso activo** bloquea también las sesiones que intenten seguir consultando. Una sede inactiva no permite habilitar el acceso.

Los enlaces actuales usan el mismo origen de la aplicación local. Para abrir uno en este equipo con otra identidad, usar una ventana privada. El acceso desde otros dispositivos o fuera de la oficina requiere configurar un origen accesible y HTTPS; no se ha publicado la aplicación ni cambiado su exposición de red.

## Alcance de la interfaz

Operario: registrar pesajes y consultar el historial propio. Gerencia: Dashboard de generación, Sedes y plantas, Pesajes, Reportes CSV/HTML y Personal. Conciliación, Salidas y sus reportes y descargas ya no están disponibles, tampoco mediante las direcciones anteriores.

Los retiros, eventos y documentos existentes se conservan en la base y el almacén privado para proteger su integridad y recuperación. Sus restricciones sobre pesajes vinculados siguen vigentes; esos retiros no se pueden gestionar desde la interfaz retirada. No se recalculan como generación ni se eliminan sus asignaciones. Cualquier tratamiento posterior de esos datos requiere una decisión específica.

## Respaldo local y comprobación de recuperación

Desde PowerShell, en la raíz del proyecto:

```powershell
.\scripts\respaldo-local.ps1
```

Crea una carpeta nueva en `.private/respaldos/`, pausa brevemente web, guarda PostgreSQL en formato custom y los archivos privados en `documentos.tar.gz`, y vuelve a iniciar web incluso si la copia falla. No detiene la base. `inventario.json` conserva conteos y huellas de tablas, secuencias y archivos; `respaldo.json` registra imágenes y hashes de los tres componentes.

A continuación restaura la copia en PostgreSQL temporal, en una red interna sin puertos publicados. Extrae los documentos en una carpeta privada nueva, ejecuta la comprobación de Django y compara todas las tablas/secuencias/archivos y las referencias documentales. El contenedor temporal y su red se retiran al terminar; el resultado y los documentos recuperados quedan junto a la copia. No sobrescribe la base ni el volumen originales.

Para volver a comprobar una copia existente, sin pausar la aplicación ni crear otra:

```powershell
.\scripts\respaldo-local.ps1 -Accion verificar -Carpeta 'RUTA_ABSOLUTA_DE_LA_COPIA'
```

Conserva también el código correspondiente y `.env` de forma privada: no están incluidos en el respaldo de datos. La comprobación utiliza el código local y las imágenes identificadas en el respaldo, que deben estar disponibles. La copia contiene datos y hashes de contraseñas; permanece excluida de Git y de la construcción Docker. Actualmente se guarda en la misma computadora; una copia externa se decidirá por separado.

La restauración sobre una instalación de uso real requiere seleccionar explícitamente ese destino. El script ofrece únicamente recuperación aislada para evitar reemplazos accidentales.

## Revisión de impresión con varias páginas

`scripts/preparar_impresion.py` se ejecuta mediante `manage.py shell` en el contenedor web y renderiza las plantillas con objetos temporales en memoria: 120 filas de generación con textos largos. No crea cuentas ni registros de negocio. Genera HTML autónomos en `/tmp/ecometrics-revision-impresion/` dentro del contenedor; cada uno incluye los estilos de la aplicación. Para revisarlos, copiarlos a una carpeta privada del equipo, abrirlos en Chrome e imprimir con A4 horizontal.

La comprobación debe verificar cabeceras repetidas, filas y total finales, columnas completas y legibilidad. Tener el HTML o un PDF antiguo no acredita esa revisión; el resultado actual se registra en STATE.
