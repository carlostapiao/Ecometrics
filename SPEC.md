# EcoMetrics — MVP

Base: acuerdos explícitos de Carlos del 2026-10-28 en esta conversación. Este documento diferencia requisitos confirmados y decisiones de implementación propuestas; no acredita software construido.

## Objetivo

Demostrar que un operario puede registrar un pesaje y que un gerente puede consultar información compartida y persistente de varias sedes, con trazabilidad y reportes. Uso inicial académico con datos ficticios; interfaz en español para celular y escritorio.

## Acuerdos confirmados

1. Django y PostgreSQL, con Docker Compose para desarrollo local en Windows.
2. Pesos en kilogramos con dos decimales, por ejemplo `12.50 kg`.
3. El operario solo consulta y lista registros propios. Los permisos deben aplicarse en servidor, también al acceder directamente a un registro.
4. Categorías: no reciclables; reciclables desglosados en plástico, cartón, vidrio y metal; orgánicos. Los peligrosos quedan fuera del MVP.
5. Reportes del MVP: CSV y HTML optimizado para imprimir o guardar como PDF desde el navegador. El generador nativo de PDF queda pospuesto.
6. Conciliación excluida del primer sprint. Prioridad: pesaje manual, trazabilidad, dashboard multisede y persistencia. No se asume comprometida una fase posterior de conciliación.

## Propuesta técnica inicial

- Un monolito Django con plantillas HTML, CSS y JavaScript acotado, y una base PostgreSQL. Sin frontend separado ni microservicios.
- Servicios Compose de aplicación y base de datos, con volumen persistente. Publicar la web inicialmente solo en localhost; no publicar la base al anfitrión por defecto.
- Autenticación de Django y roles operario/gerente; la cuenta gerencial funcional se distingue del superusuario técnico.
- Cada operario tiene una sede asignada. El servidor fija autor, sede y fecha de creación; no confía en valores manipulados del formulario.
- Datos mínimos de pesaje: categoría, peso positivo, fecha de generación y observación opcional. Zona de negocio `America/Lima`.
- Usar decimales exactos con dos posiciones. Rechazar exceso de decimales sin redondearlo silenciosamente; aceptar coma o punto decimal sin separadores de miles.
- Representar las categorías como seis opciones de captura, agrupando plástico/cartón/vidrio/metal como reciclables. No inferir tratamiento real a partir de esa clasificación.
- Trazabilidad de altas, correcciones y anulaciones: actor, fecha y cambios; correcciones y anulaciones gerenciales con motivo. Conservar historia y excluir anulados de las métricas; no borrar físicamente desde la interfaz.
- Evitar pesajes duplicados por doble clic o reintento. Mantener coherencia entre cambio de negocio e historial.
- Dashboard gerencial: kg registrados, cantidad de registros, distribución por sede/categoría y evolución temporal. Filtros de sede y fechas inclusivas; mismos datos y reglas para los reportes.
- No presentar el peso clasificado como reciclable como reciclaje efectivamente realizado. La gestión de destinos parciales y las metas no se heredan automáticamente de versiones anteriores.
- Datos ficticios de varias sedes y cuentas de ambos roles, cargados sin duplicar ni borrar datos existentes. La cantidad exacta se define al implementar la demostración.
- Contraseñas y configuración secreta fuera de código y Git; configuración de ejemplo sin credenciales reales. Versiones compatibles y específicas se fijarán al implementar, no se heredan sin comprobar soporte.

Estas propuestas resuelven detalles de implementación dentro del objetivo. Si aparece una decisión que cambie el alcance, los permisos o el significado de los indicadores, se plantea a Carlos antes de aplicarla.

## Primer sprint: flujo local de extremo a extremo

1. Preparar Compose, conexión PostgreSQL, migraciones y carga de datos ficticios.
2. Implementar acceso por rol, captura de pesajes e historial propio del operario.
3. Incorporar consulta gerencial, correcciones/anulaciones trazadas y dashboard multisede básico.
4. Verificar permisos, cálculos, duplicados y persistencia con datos conocidos y pruebas contra PostgreSQL.

CSV y HTML imprimible son parte del MVP y se implementarán después del flujo prioritario. No se necesita otro documento de planificación para iniciar este sprint.

## Criterios de aceptación del primer sprint

- Un operario autenticado registra `12.50 kg` en su sede; su registro persiste tras recargar y recrear contenedores conservando el volumen.
- Peso cero, negativo, inválido o con más de dos decimales se rechaza. Un reintento de la misma operación no genera dos pesajes.
- Otro operario, incluso de la misma sede, no puede listar ni consultar ese registro. Tampoco obtiene acceso modificando IDs o parámetros.
- El gerente consulta registros de distintas sedes y los filtros producen sumas exactas de un conjunto conocido; el operario no accede al dashboard gerencial.
- Una corrección o anulación conserva actor, motivo y valores necesarios para reconstruir el cambio; los totales reflejan solo registros vigentes.
- La carga de ejemplos repetida no duplica información ni reinicia el escenario. No se ejecutan borrados de volúmenes como parte del arranque o de una prueba rutinaria.

Para completar el MVP, CSV y vista imprimible deberán coincidir con filtros y totales del dashboard, respetar permisos y mostrar claramente el caso sin datos. Guardar como PDF depende de la impresión del navegador.

## Fuera de este inicio

Conciliación, PDF nativo, peligrosos, IoT/balanzas conectadas, migración del prototipo, despliegue Azure, publicación y gastos. Azure/Terraform permanecen como antecedente futuro, sin convertirlos en condición para entregar el piloto local. No se prometen certificación ambiental, reciclaje verificado ni cumplimiento normativo.

## Ampliación gerencial acordada — 2026-10-29

Carlos solicita separar la operación gerencial por módulos y conservar el flujo móvil del operario. Esta ampliación incorpora conciliación al trabajo posterior al MVP inicial; no cambia retrospectivamente su exclusión del primer sprint.

- Navegación prevista: Dashboard, Sedes y plantas, Pesajes, Conciliación, Reportes, Personal y Configuración. Cada entrada se incorpora cuando tenga una función disponible, sin pantallas vacías.
- Primer incremento: Dashboard con indicadores y tendencias; Pesajes con búsqueda, filtros, paginación y acceso al historial/correcciones; Reportes con selección de filtros y exportación CSV/HTML. Mantener permisos gerenciales y el mismo criterio de exclusión de anulados.
- Diseño gerencial adaptable a escritorio y celular, con menú compacto y filtros plegables. Conservar Django, PostgreSQL y el monolito; no se introduce una aplicación móvil separada.
- Lenguaje visible de operación real: sin rótulos de demo, prueba, datos ficticios o proyecto académico. Esto no autoriza alterar registros históricos ni acredita preparación para despliegue empresarial.
- Siguientes incrementos: administración de sedes y personal con activación segura; después retiros y conciliación de cantidades entregadas/recibidas con respaldo. No confundir generación con entrega ni categoría reciclable con reciclaje realizado.
- Personal: la propuesta es que gerencia cree operarios con sede y activación mediante enlace temporal; no comparte contraseñas permanentes. La creación de gerentes necesita un permiso específico. El correo real y el acceso fuera de la oficina requieren configuración posterior.
- Incremento Sedes/Personal: sedes con nombre, dirección opcional y estado; altas exclusivas de operarios inicialmente inactivos y sin contraseña utilizable; activación manual mediante enlace privado de 24 horas y un solo uso. Token aleatorio de 256 bits, huella en base y fragmento de URL retirado por el navegador antes de enviar el formulario. Reemisión invalida el anterior y revocación bloquea su uso. Contraseña personal validada por Django con mínimo de 12 caracteres. No se configura correo ni se permite restablecer cuentas ya activadas mediante este enlace.
- Gestión gerencial de operarios: nombre, correo opcional, sede y estado de acceso; identificador de usuario inmutable desde edición y sin permisos técnicos editables. Cambios trazados y protegidos por versión. Sedes/cuentas se desactivan sin borrar sus pesajes; trasladar un operario no modifica sedes históricas. Nombres de sede y usuarios únicos sin distinguir mayúsculas/minúsculas.
- Conciliación: partir de un mismo retiro/material, admitir cantidades parciales, impedir doble asignación y conservar motivo/actor al resolver diferencias.
- Retiro: una sede, categoría, receptor y fecha de salida; entre uno y veinte pesajes de origen con cantidades parciales positivas de dos decimales. La salida se calcula como suma de esas cantidades. No se permite exceder saldos, usar pesajes anulados, mezclar sedes/categorías ni retirar antes de la generación. Operación firmada e idempotente; bloqueo de pesajes ordenado por ID protege las asignaciones concurrentes.
- Recepción: peso confirmado con dos decimales (cero admisible), fecha entre salida y hoy, referencia documental y observación. Diferencia = confirmado menos salida, sin equiparar generación, entrega y tratamiento. Un peso coincidente no cierra automáticamente la revisión.
- Cierre: estados Pendiente, Observado, Conciliado y Anulado. Conciliar requiere peso confirmado, referencia y respaldo; si hay diferencia, explicación obligatoria. Reabrir exige motivo y conserva valores/eventos. Anular exige motivo, libera asignaciones y conserva historia; un conciliado debe reabrirse primero. Formulario obsoleto no sobrescribe una versión nueva.
- Protección de origen: un pesaje con retiros vigentes no se anula ni cambia de categoría; su peso no puede bajar de lo ya retirado y su generación no puede quedar después de una salida vinculada.
- Respaldo privado: PDF/JPG/PNG hasta 10 MB, extensión y cabecera concordantes, nombre de almacenamiento aleatorio y huella SHA-256. Descarga autenticada solo para gerencia, como adjunto y sin rutas públicas de media. Los documentos no se borran ni reemplazan desde la interfaz; reabrir permite añadir una nueva evidencia conservando la anterior. Volumen persistente separado de la base de datos.
- Integración gerencial: Dashboard distingue generación (fecha de generación), salidas (fecha de salida) y recepción confirmada (fecha de recepción). Cada indicador aplica el mismo periodo a su propio evento; no se resta generación menos recepción como saldo ni se presenta como tasa de reciclaje. Seguimiento de retiros por revisar, observados y sin recepción según fecha de salida.
- Reportes: selección de generación, salidas o recepciones, con sede, categoría, periodo y estado vigente del retiro cuando corresponde. CSV y HTML usan los mismos registros y criterio de fecha. Salidas muestra recepción actual aunque sea de otro periodo; recepciones incluye únicamente pesos/fechas confirmados y conserva la salida vinculada. Diferencia solo sobre retiros recibidos; pendiente queda vacío en CSV y cero confirmado permanece 0.00. Anulados excluidos. Adjuntos no multiplican cantidades; la exportación informa referencias y número de respaldos sin publicar sus rutas.
- Reportes de gestión de residuos y constancias externas se distinguen de una certificación ASG. EcoMetrics no emite una certificación por sumar pesajes.

El avance y las verificaciones de cada incremento se registran únicamente en STATE.md.

### Fuentes de la base técnica

- [Campos de Django, incluido DecimalField](https://docs.djangoproject.com/en/stable/ref/models/fields/#decimalfield).
- [Autenticación y autorización de Django](https://docs.djangoproject.com/en/stable/topics/auth/default/).
- [Docker Compose: servicios, salud y persistencia](https://docs.docker.com/compose/gettingstarted/).

## Ajuste operativo de salidas aprobado

El operario registra entregas parciales exclusivamente de pesajes propios de su sede actual y activa. Puede consultar sus retiros de esa sede, registrar o corregir recepción mientras estén abiertos y adjuntar/descargar sus respaldos. El servidor verifica alcance tanto en consultas/formularios como dentro de las transacciones. Gerencia conserva acceso multisede y registro alternativo, y es la única que cierra, reabre o anula. Transferir un operario no modifica el origen histórico ni le da acceso a retiros de su sede anterior. El registro se hace cuando ocurre una entrega; el pesaje de generación no implica una salida automática. La interfaz móvil incorpora Salidas; conserva captura e historial propios.
