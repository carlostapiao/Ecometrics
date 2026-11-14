import csv
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_safe

from cuentas.models import Sede
from .forms import AnulacionForm, ConsultaPesajesForm, CorreccionForm, FiltrosForm, PesajeForm, ReporteForm
from .models import Pesaje
from .consultas_movimientos import filtrar_generacion
from .services import modificar_pesaje, registrar_pesaje


def rol_requerido(rol):
    def decorador(vista):
        @login_required
        @wraps(vista)
        def protegida(request, *args, **kwargs):
            if request.user.rol != rol:
                raise PermissionDenied
            if rol == "operario" and (not request.user.sede_id or not request.user.sede.activa):
                raise PermissionDenied("Tu cuenta necesita una sede activa.")
            return vista(request, *args, **kwargs)
        return protegida
    return decorador


def consulta_filtrada(request, queryset):
    form = FiltrosForm(request.GET)
    if form.is_valid():
        datos = form.cleaned_data
        if datos.get("desde"):
            queryset = queryset.filter(fecha_generacion__gte=datos["desde"])
        if datos.get("hasta"):
            queryset = queryset.filter(fecha_generacion__lte=datos["hasta"])
        if datos.get("categoria"):
            queryset = queryset.filter(categoria=datos["categoria"])
    else:
        queryset = queryset.none()
    return form, queryset


@rol_requerido("operario")
@require_http_methods(["GET", "POST"])
def registrar(request):
    form = PesajeForm(request.POST if request.method == "POST" else None, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            pesaje, creado = registrar_pesaje(request.user, form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Pesaje guardado correctamente." if creado else "Este pesaje ya estaba guardado. No se duplicó.")
            return redirect("detalle_pesaje", pk=pesaje.pk)
    return render(request, "residuos/registrar.html", {"form": form, "seccion": "registrar"}, status=400 if request.method == "POST" else 200)


@rol_requerido("operario")
@require_safe
def historial(request):
    form, registros = consulta_filtrada(request, Pesaje.objects.filter(autor=request.user).select_related("categoria", "sede"))
    totales = registros.filter(anulado=False).aggregate(peso=Sum("peso_kg"), cantidad=Count("id"))
    pagina = Paginator(registros, 15).get_page(request.GET.get("page"))
    parametros = request.GET.copy()
    parametros.pop("page", None)
    return render(request, "residuos/historial.html", {"filtros": form, "pagina": pagina, "totales": totales, "parametros": parametros.urlencode(), "seccion": "historial"})


@login_required
@require_safe
def detalle(request, pk):
    consulta = Pesaje.objects.select_related("categoria", "sede", "autor").prefetch_related("eventos__actor")
    if request.user.rol == "operario":
        if not request.user.sede_id or not request.user.sede.activa:
            raise PermissionDenied
        consulta = consulta.filter(autor=request.user)
    elif request.user.rol != "gerente":
        raise PermissionDenied
    pesaje = get_object_or_404(consulta, pk=pk)
    return render(request, "residuos/detalle.html", {"pesaje": pesaje, "seccion": "pesajes" if request.user.rol == "gerente" else "historial"})


def consulta_gerencial(request):
    form, registros = consulta_filtrada(request, Pesaje.objects.select_related("categoria", "sede", "autor"))
    sede_id = request.GET.get("sede", "")
    if sede_id:
        if sede_id.isascii() and sede_id.isdigit():
            registros = registros.filter(sede_id=sede_id)
        else:
            registros = registros.none()
            form.add_error(None, "La sede seleccionada no es válida.")
    return form, registros, sede_id


def contexto_filtros(request, form, sede_id):
    parametros = request.GET.copy()
    parametros.pop("page", None)
    return {"filtros": form, "sedes": Sede.objects.all().order_by("nombre"), "sede_id": sede_id,
            "parametros": parametros.urlencode(), "hay_filtros": any(parametros.values())}


@rol_requerido("gerente")
@require_safe
def resumen(request):
    form, registros, sede_id = consulta_gerencial(request)
    vigentes = registros.filter(anulado=False)
    por_dia = list(vigentes.order_by().values("fecha_generacion").annotate(peso=Sum("peso_kg"), cantidad=Count("id")).order_by("fecha_generacion"))
    return render(request, "residuos/resumen.html", {
        **contexto_filtros(request, form, sede_id),
        "totales": vigentes.aggregate(peso=Sum("peso_kg"), cantidad=Count("id")),
        "anulados": registros.filter(anulado=True).count(),
        "por_sede": vigentes.order_by().values("sede__nombre").annotate(peso=Sum("peso_kg"), cantidad=Count("id")).order_by("sede__nombre"),
        "por_categoria": vigentes.order_by().values("categoria__nombre", "categoria__grupo").annotate(peso=Sum("peso_kg"), cantidad=Count("id")).order_by("categoria__nombre"),
        "por_dia": por_dia, "maximo_diario": max((fila["peso"] for fila in por_dia[-14:]), default=1),
        "seccion": "dashboard",
    })


@rol_requerido("gerente")
@require_safe
def listado_pesajes(request):
    _, registros, sede_id = consulta_gerencial(request)
    form = ConsultaPesajesForm(request.GET)
    if form.is_valid():
        if form.cleaned_data.get("estado"):
            registros = registros.filter(anulado=form.cleaned_data["estado"] == "anulado")
        texto = form.cleaned_data.get("buscar", "")
        if texto:
            condicion = Q(autor__username__icontains=texto) | Q(autor__first_name__icontains=texto) | Q(autor__last_name__icontains=texto) | Q(observacion__icontains=texto)
            if texto.isascii() and texto.isdigit() and len(texto) <= 18:
                condicion |= Q(pk=int(texto))
            registros = registros.filter(condicion)
    else:
        registros = registros.none()
    # La consulta común valida sede además de los campos del formulario.
    if sede_id and not (sede_id.isascii() and sede_id.isdigit()):
        form.add_error(None, "La sede seleccionada no es válida.")
    contexto = contexto_filtros(request, form, sede_id)
    contexto.update({"pagina": Paginator(registros, 15).get_page(request.GET.get("page")),
                     "seccion": "pesajes", "totales": registros.filter(anulado=False).aggregate(peso=Sum("peso_kg"), cantidad=Count("id")),
                     "cantidad": registros.count()})
    return render(request, "residuos/pesajes.html", contexto)


@rol_requerido("gerente")
@require_safe
def centro_reportes(request):
    form = ReporteForm(request.GET)
    valido = form.is_valid()
    datos = form.cleaned_data if valido else {}
    tipo = datos.get("tipo", "generacion")
    sede = datos.get("sede")
    sede_id = str(sede.pk) if sede else ""
    contexto = contexto_filtros(request, form, sede_id)
    registros = filtrar_generacion(datos, incluir_anulados=True) if valido else Pesaje.objects.none()
    contexto.update({"totales": registros.filter(anulado=False).aggregate(peso=Sum("peso_kg"), cantidad=Count("id")),
                     "anulados": registros.filter(anulado=True).count(),
                     "url_csv": reverse("reporte_csv"), "url_imprimir": reverse("reporte_imprimible")})
    contexto.update({"seccion": "reportes", "puede_exportar": valido, "tipo": tipo})
    return render(request, "residuos/reportes.html", contexto)


@rol_requerido("gerente")
@require_http_methods(["GET", "POST"])
def modificar(request, pk, anular=False):
    pesaje = get_object_or_404(Pesaje.objects.select_related("categoria", "sede", "autor"), pk=pk)
    if anular:
        form = AnulacionForm(request.POST if request.method == "POST" else None, initial={"version": pesaje.version})
    else:
        form = CorreccionForm(request.POST if request.method == "POST" else None, usuario=request.user, pesaje=pesaje)
    if request.method == "POST" and form.is_valid():
        try:
            modificar_pesaje(request.user, pk, form.cleaned_data, anular=anular)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Pesaje anulado. Su historial se conserva." if anular else "Corrección guardada con su motivo.")
            return redirect("detalle_pesaje", pk=pk)
    return render(request, "residuos/modificar.html", {"form": form, "pesaje": pesaje, "anular": anular, "seccion": "pesajes"},
                  status=400 if request.method == "POST" else 200)


def texto_csv_seguro(valor):
    texto = str(valor)
    # Evita interpretar datos de usuario como fórmulas al abrir el CSV en una hoja de cálculo.
    if texto.lstrip().startswith(("=", "+", "-", "@")) or texto.startswith(("\t", "\r", "\n")):
        return "'" + texto
    return texto


@rol_requerido("gerente")
@require_safe
def reporte(request, formato="html"):
    form = ReporteForm(request.GET)
    if not form.is_valid() or form.cleaned_data["tipo"] != "generacion":
        return HttpResponse("Corrige los filtros en Reportes antes de generar el documento.", status=400, content_type="text/plain; charset=utf-8")
    # Una sola lectura materializa el contenido y mantiene el total de esta exportación coherente.
    filas = list(filtrar_generacion(form.cleaned_data).order_by("fecha_generacion", "pk"))
    if formato == "csv":
        respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
        respuesta["Content-Disposition"] = 'attachment; filename="ecometrics-pesajes.csv"'
        respuesta.write("\ufeff")
        escritor = csv.writer(respuesta)
        escritor.writerow(["Registro", "Fecha de generación", "Sede", "Categoría", "Operario", "Peso (kg)", "Observación", "Registrado el (Lima)", "Versión"])
        for fila in filas:
            escritor.writerow([fila.pk, fila.fecha_generacion.isoformat(), texto_csv_seguro(fila.sede.nombre),
                               texto_csv_seguro(fila.categoria.nombre), texto_csv_seguro(fila.autor.username),
                               format(fila.peso_kg, ".2f"), texto_csv_seguro(fila.observacion),
                               timezone.localtime(fila.creado_en).strftime("%Y-%m-%d %H:%M:%S"), fila.version])
    else:
        respuesta = render(request, "residuos/reporte.html", {
            "registros": filas, "total": sum((fila.peso_kg for fila in filas), Decimal("0.00")),
            "cantidad": len(filas), "emitido_en": timezone.localtime(), "filtros": form.cleaned_data,
            "sede": form.cleaned_data.get("sede"),
            "sede_seleccionada": bool(form.cleaned_data.get("sede")), "parametros": request.GET.urlencode(),
            "seccion": "reportes",
        })
    respuesta["Cache-Control"] = "private, no-store"
    return respuesta
