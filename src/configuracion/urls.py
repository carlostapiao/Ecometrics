from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path

from inicio.views import inicio, salud, disponibilidad
from cuentas.views import AccesoView
from cuentas import gestion_views as gestion
from residuos import views as residuos
from residuos import retiros_views as retiros

urlpatterns = [
    path("", inicio, name="inicio"),
    path("healthz", salud, name="salud"),
    path("readyz", disponibilidad, name="disponibilidad"),
    path("admin/", admin.site.urls),
    path("login/", AccesoView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("activar/", gestion.activacion, name="activar_cuenta"),
    path("operario/registrar/", residuos.registrar, name="registrar"),
    path("operario/historial/", residuos.historial, name="historial"),
    path("pesajes/<int:pk>/", residuos.detalle, name="detalle_pesaje"),
    path("pesajes/<int:pk>/corregir/", residuos.modificar, name="corregir_pesaje"),
    path("pesajes/<int:pk>/anular/", residuos.modificar, {"anular": True}, name="anular_pesaje"),
    path("gerencia/", residuos.resumen, name="resumen"),
    path("gerencia/conciliacion/", retiros.listado, name="conciliacion"),
    path("gerencia/conciliacion/nuevo/", retiros.nuevo, name="retiro_nuevo"),
    path("gerencia/conciliacion/<int:pk>/", retiros.detalle, name="retiro_detalle"),
    path("gerencia/conciliacion/<int:pk>/recepcion/", retiros.confirmar, name="retiro_confirmar"),
    path("gerencia/conciliacion/<int:pk>/accion/", retiros.accion, name="retiro_accion"),
    path("gerencia/conciliacion/<int:pk>/evidencia/", retiros.evidencia, name="retiro_evidencia"),
    path("gerencia/conciliacion/evidencias/<int:pk>/", retiros.descargar_evidencia, name="evidencia_descargar"),
    path("gerencia/sedes/", gestion.sedes, name="sedes"),
    path("gerencia/sedes/nueva/", gestion.sede_editar, name="sede_nueva"),
    path("gerencia/sedes/<int:pk>/", gestion.sede_editar, name="sede_editar"),
    path("gerencia/personal/", gestion.personal, name="personal"),
    path("gerencia/personal/nuevo/", gestion.personal_editar, name="personal_nuevo"),
    path("gerencia/personal/<int:pk>/", gestion.personal_editar, name="personal_editar"),
    path("gerencia/personal/<int:pk>/activacion/", gestion.invitacion_gestionar, name="invitacion_gestionar"),
    path("gerencia/pesajes/", residuos.listado_pesajes, name="pesajes_gerencia"),
    path("gerencia/reportes/", residuos.centro_reportes, name="reportes"),
    path("gerencia/reportes/<str:tipo>/csv/", retiros.reporte_movimientos, {"formato": "csv"}, name="movimientos_csv"),
    path("gerencia/reportes/<str:tipo>/imprimir/", retiros.reporte_movimientos, name="movimientos_imprimible"),
    path("gerencia/reportes/imprimir/", residuos.reporte, name="reporte_imprimible"),
    path("gerencia/reportes/csv/", residuos.reporte, {"formato": "csv"}, name="reporte_csv"),
]
