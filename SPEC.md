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

En el alcance inicial quedaron fuera conciliación, PDF nativo, peligrosos, IoT/balanzas conectadas, migración del prototipo, despliegue Azure, publicación y gastos. Azure/Terraform eran antecedentes futuros, sin convertirlos en condición para entregar el piloto local. Las ampliaciones posteriores se registran a continuación. No se prometen certificación ambiental, reciclaje verificado ni cumplimiento normativo.

## Destino Azure y previsión de capacidades por fase — 2026-10-30 (actualizado 2026-11-14)

Carlos confirma el despliegue demostrativo en **Microsoft Azure** (suscripción *Azure for Students* `94846a8b-9491-4312-82bb-3082c340b45f`, región primaria `mexicocentral`) bajo un **único presupuesto y arquitectura de Nivel Intermedio** (monolito Django con Gunicorn/WhiteNoise en Azure Container Apps, Azure Container Registry Basic, Azure Database for PostgreSQL Flexible Server `B_Standard_B1ms`, Azure Blob Storage privado para evidencias/respaldos, Log Analytics + Application Insights, Terraform con bootstrap de estado remoto y GitHub Actions con OIDC desde `carlostapiao/Ecometrics` rama `main`). Sin dominio propio, sin envío de correos (activación manual) y con carga inicial exclusiva de datos demo. El diseño detallado y el Plan Financiero Inicial (modelo SaaS B2B con TC = S/ 3.50) se documentan en [specs/PLAN-AZURE.md](specs/PLAN-AZURE.md). Preparar el plan no autoriza crear recursos, publicar, desplegar ni generar gastos; esas acciones conservan la autorización explícita aplicable.

La tabla describe cobertura prevista, no ejecución ni disponibilidad operativa acreditada. Las comprobaciones y carencias actuales se consultan en [STATE.md](STATE.md). Las fases pueden solaparse cuando sus dependencias lo permitan: los pendientes locales no bloquean automáticamente el análisis de Azure.

| Fase | Capacidades necesarias | Skills o recursos previstos | Decisiones pendientes |
| --- | --- | --- | --- |
| Desarrollo local | Django, datos PostgreSQL, permisos, pruebas y contenedores | [django-expert](../../.agents/skills/django-expert/SKILL.md), [docker-project-foundations](../../.agents/skills/docker-project-foundations/SKILL.md), [docker-compose-patterns](../../.agents/skills/docker-compose-patterns/SKILL.md); procedimientos del proyecto y documentación oficial de PostgreSQL | Revisar cobertura al cambiar requisitos; no adoptar herramientas adicionales por el solo hecho de figurar en una skill. |
| Interfaz y validación | Diseño adaptable, recorridos por rol y comprobación visual e impresión | [frontend-design](../../.agents/skills/frontend-design/SKILL.md) para diseño; navegador y procedimientos de comprobación como recursos separados | Confirmar acceso efectivo al navegador y comprobaciones necesarias antes del recorrido. La skill de diseño no acredita validación visual. |
| Preparación para Azure | Arquitectura Nivel Intermedio, identidad OIDC, secretos, PostgreSQL Flexible, Blob Storage, costos SaaS (USD/PEN) y recuperación | Documentación oficial de Microsoft Azure y [specs/PLAN-AZURE.md](specs/PLAN-AZURE.md); sin necesidad de instalar skills adicionales | Alcance, región (`mexicocentral`), presupuesto intermedio (TC S/ 3.50) y componentes definidos en [specs/PLAN-AZURE.md](specs/PLAN-AZURE.md). Pendiente aprobación de Carlos para pasar a implementación. |
| Aprovisionamiento y despliegue | Empaquetado Gunicorn/WhiteNoise, módulos Terraform con bootstrap, pipeline GitHub Actions OIDC, migraciones, datos demo y verificación HTTPS | Terraform CLI (`v1.14.7`), Azure CLI (`2.91.0`), GitHub CLI (`2.94.0`), [django-expert](../../.agents/skills/django-expert/SKILL.md), [docker-project-foundations](../../.agents/skills/docker-project-foundations/SKILL.md) y [specs/PLAN-AZURE.md](specs/PLAN-AZURE.md) | Mecanismo seleccionado: **Terraform con bootstrap** + **GitHub Actions (`main`)**. Requiere alinear sesión de GitHub hacia `carlostapiao/Ecometrics` y autorización explícita antes de `terraform apply` y `git push`. |
| Operación | Supervisión, mantenimiento, respaldos en PostgreSQL/Blob Storage, restauración y control de consumo del crédito estudiantil | Documentación oficial, Application Insights y procedimientos operativos en [specs/PLAN-AZURE.md](specs/PLAN-AZURE.md) | Definir apagado/escalado a cero fuera de demostraciones para conservar el crédito de *Azure for Students*. |

Las referencias técnicas específicas se seleccionarán y verificarán al preparar cada fase. Las skills previstas se consultarán según la tarea; no se instalan ni se crean de forma anticipada para completar esta previsión.

## Ampliación gerencial acordada — 2026-10-29

Carlos solicita separar la operación gerencial por módulos y conservar el flujo móvil del operario. El alcance vigente se limita a generación de residuos y su trazabilidad; Conciliación y Salidas se retiran de ambos perfiles por decisión de Carlos del 2026-11-02.

- Navegación prevista: Dashboard, Sedes y plantas, Pesajes, Reportes, Personal y Configuración. Cada entrada se incorpora cuando tenga una función disponible, sin pantallas vacías.
- Primer incremento: Dashboard con indicadores y tendencias; Pesajes con búsqueda, filtros, paginación y acceso al historial/correcciones; Reportes con selección de filtros y exportación CSV/HTML. Mantener permisos gerenciales y el mismo criterio de exclusión de anulados.
- Diseño gerencial adaptable a escritorio y celular, con menú compacto y filtros plegables. Conservar Django, PostgreSQL y el monolito; no se introduce una aplicación móvil separada.
- Lenguaje visible de operación real: sin rótulos de demo, prueba, datos ficticios o proyecto académico. Esto no autoriza alterar registros históricos ni acredita preparación para despliegue empresarial.
- Administración de sedes y personal con activación segura. La categoría reciclable no acredita reciclaje realizado.
- Personal: la propuesta es que gerencia cree operarios con sede y activación mediante enlace temporal; no comparte contraseñas permanentes. La creación de gerentes necesita un permiso específico. El correo real y el acceso fuera de la oficina requieren configuración posterior.
- Incremento Sedes/Personal: sedes con nombre, dirección opcional y estado; altas exclusivas de operarios inicialmente inactivos y sin contraseña utilizable; activación manual mediante enlace privado de 24 horas y un solo uso. Token aleatorio de 256 bits, huella en base y fragmento de URL retirado por el navegador antes de enviar el formulario. Reemisión invalida el anterior y revocación bloquea su uso. Contraseña personal validada por Django con mínimo de 12 caracteres. No se configura correo ni se permite restablecer cuentas ya activadas mediante este enlace.
- Gestión gerencial de operarios: nombre, correo opcional, sede y estado de acceso; identificador de usuario inmutable desde edición y sin permisos técnicos editables. Cambios trazados y protegidos por versión. Sedes/cuentas se desactivan sin borrar sus pesajes; trasladar un operario no modifica sedes históricas. Nombres de sede y usuarios únicos sin distinguir mayúsculas/minúsculas.
- Retiro de interfaz: se eliminan Conciliación/Salidas, registro y detalle de retiros, recepción, documentos y acciones asociadas de ambos perfiles; Dashboard y Reportes presentan únicamente generación. Direcciones HTTP antiguas devuelven 404 y los tipos de reporte retirados no exportan datos.
- Conservación: modelos, migraciones, servicios internos y documentos históricos permanecen; no se borran datos ni se debilitan restricciones de pesajes vinculados a retiros previos. Esos retiros no son gestionables en la interfaz actual. Sus datos privados siguen cubiertos por respaldo/restauración.
- Cobertura de este ajuste: django-expert para rutas, consultas y pruebas; frontend-design para navegación y distribución existente; scripts/verificar.ps1 para comprobaciones. No requiere migraciones, nueva infraestructura ni nuevas skills. Revisión separada de plan y resultado.

El avance y las verificaciones se consultan únicamente en STATE.md.

### Fuentes de la base técnica

- [Campos de Django, incluido DecimalField](https://docs.djangoproject.com/en/stable/ref/models/fields/#decimalfield).
- [Autenticación y autorización de Django](https://docs.djangoproject.com/en/stable/topics/auth/default/).
- [Docker Compose: servicios, salud y persistencia](https://docs.docker.com/compose/gettingstarted/).
