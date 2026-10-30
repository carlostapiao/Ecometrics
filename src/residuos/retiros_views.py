import csv
from decimal import Decimal
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from .models import EvidenciaRetiro, Pesaje, Retiro
from .retiros_forms import AccionRetiroForm, AsignacionesFormSet, ConfirmacionForm, EvidenciaForm, FiltrosRetiroForm, RetiroForm, SeleccionRetiroForm
from .retiros_services import adjuntar_evidencia, confirmar_recepcion, crear_retiro, pesajes_disponibles, resolver_retiro
from .views import rol_requerido, texto_csv_seguro
from .forms import ReporteForm
from .consultas_movimientos import filtrar_retiros, totales_movimientos


def registro_requerido(vista):
    @login_required
    @wraps(vista)
    def protegida(request, *args, **kwargs):
        u = request.user
        if u.rol not in ('operario', 'gerente') or (u.rol == 'operario' and (not u.sede_id or not u.sede.activa)):
            raise PermissionDenied
        return vista(request, *args, **kwargs)
    return protegida


def retiros_visibles(usuario):
    filas = Retiro.objects.all()
    if usuario.rol == 'operario':
        filas = filas.filter(actor=usuario, sede_id=usuario.sede_id)
    return filas


def limitar_sede(form, usuario):
    if usuario.rol == 'operario':
        form.fields['sede'].queryset = form.fields['sede'].queryset.filter(pk=usuario.sede_id)
    return form


@registro_requerido
@require_safe
def listado(request):
    form = limitar_sede(FiltrosRetiroForm(request.GET), request.user)
    registros = filtrar_retiros(form.cleaned_data, incluir_anulados=True) if form.is_valid() else Retiro.objects.none()
    if request.user.rol == "operario":
        registros = registros.filter(actor=request.user, sede_id=request.user.sede_id)
    parametros = request.GET.copy()
    parametros.pop("page", None)
    return render(request, "residuos/conciliacion.html", {"filtros": form, "pagina": Paginator(registros, 15).get_page(request.GET.get("page")),
                  "parametros": parametros.urlencode(), "seccion": "conciliacion"})


@registro_requerido
@require_http_methods(["GET", "POST"])
def nuevo(request):
    seleccion = limitar_sede(SeleccionRetiroForm(request.POST if request.method == "POST" else request.GET or None), request.user)
    form = None
    formset = None
    sede = categoria = None
    if seleccion.is_bound and seleccion.is_valid():
        sede, categoria = seleccion.cleaned_data["sede"], seleccion.cleaned_data["categoria"]
        disponibles = pesajes_disponibles(sede, categoria)
        if request.user.rol == "operario":
            disponibles = disponibles.filter(autor=request.user)
        form = RetiroForm(request.POST if request.method == "POST" else None, usuario=request.user, initial={"sede": sede.pk, "categoria": categoria.pk})
        formset = AsignacionesFormSet(request.POST if request.method == "POST" else None, prefix="origenes", form_kwargs={"disponibles": disponibles})
        if request.method == "POST":
            valido = form.is_valid()
            origenes_validos = formset.is_valid()
            if valido and origenes_validos:
                filas = [fila for fila in formset.cleaned_data if fila and not fila.get("DELETE")]
                try:
                    retiro, creado = crear_retiro(request.user, form.cleaned_data, filas)
                except ValidationError as error:
                    form.add_error(None, error)
                else:
                    messages.success(request, "Retiro registrado." if creado else "Este retiro ya estaba registrado. No se duplicó.")
                    return redirect("retiro_detalle", pk=retiro.pk)
    return render(request, "residuos/retiro_nuevo.html", {"seleccion": seleccion, "form": form, "formset": formset,
                  "sede": sede, "categoria": categoria, "seccion": "conciliacion"}, status=400 if request.method == "POST" else 200)


def mostrar_detalle(request, retiro, *, confirmacion=None, evidencia=None, accion=None, status=200):
    return render(request, "residuos/retiro_detalle.html", {"retiro": retiro,
        "origenes": retiro.asignaciones.select_related("pesaje"), "evidencias": retiro.evidencias.select_related("actor"),
        "eventos": retiro.eventos.select_related("actor"), "confirmacion": confirmacion or ConfirmacionForm(initial={
            "peso_confirmado": format(retiro.peso_confirmado, ".2f") if retiro.peso_confirmado is not None else "",
            "fecha_confirmacion": retiro.fecha_confirmacion or timezone.localdate(), "documento_ref": retiro.documento_ref,
            "observacion_recepcion": retiro.observacion_recepcion, "version": retiro.version}),
        "evidencia_form": evidencia or EvidenciaForm(initial={"version": retiro.version}),
        "accion_form": accion or AccionRetiroForm(initial={"version": retiro.version}), "seccion": "conciliacion"}, status=status)


@registro_requerido
@require_safe
def detalle(request, pk):
    retiro = get_object_or_404(retiros_visibles(request.user).select_related("sede", "categoria", "actor"), pk=pk)
    return mostrar_detalle(request, retiro)


@registro_requerido
@require_POST
def confirmar(request, pk):
    retiro = get_object_or_404(retiros_visibles(request.user).select_related("sede", "categoria"), pk=pk)
    form = ConfirmacionForm(request.POST)
    if form.is_valid():
        try:
            confirmar_recepcion(request.user, pk, form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Recepción guardada. Gerencia revisará la diferencia y el respaldo." if request.user.rol == "operario" else "Recepción guardada. Revisa la diferencia y el respaldo antes de conciliar.")
            return redirect("retiro_detalle", pk=pk)
    return mostrar_detalle(request, retiro, confirmacion=form, status=400)


@rol_requerido("gerente")
@require_POST
def accion(request, pk):
    retiro = get_object_or_404(retiros_visibles(request.user).select_related("sede", "categoria"), pk=pk)
    form = AccionRetiroForm(request.POST)
    if form.is_valid():
        try:
            resolver_retiro(request.user, pk, form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, {"conciliar": "Conciliación cerrada.", "reabrir": "Conciliación reabierta.", "anular": "Retiro anulado. Sus cantidades vuelven a estar disponibles."}[form.cleaned_data["accion"]])
            return redirect("retiro_detalle", pk=pk)
    return mostrar_detalle(request, retiro, accion=form, status=400)


@registro_requerido
@require_POST
def evidencia(request, pk):
    retiro = get_object_or_404(retiros_visibles(request.user).select_related("sede", "categoria"), pk=pk)
    form = EvidenciaForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            adjuntar_evidencia(request.user, pk, form.cleaned_data["archivo"], form.cleaned_data["version"])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Documento de respaldo adjuntado.")
            return redirect("retiro_detalle", pk=pk)
    return mostrar_detalle(request, retiro, evidencia=form, status=400)


@registro_requerido
@require_safe
def descargar_evidencia(request, pk):
    documento = get_object_or_404(EvidenciaRetiro.objects.filter(retiro__in=retiros_visibles(request.user)), pk=pk)
    try:
        archivo = documento.archivo.open("rb")
    except FileNotFoundError:
        raise Http404("El archivo no está disponible.")
    respuesta = FileResponse(archivo, as_attachment=True, filename=documento.nombre, content_type=documento.tipo)
    respuesta["Cache-Control"] = "private, no-store"
    respuesta["X-Content-Type-Options"] = "nosniff"
    return respuesta


@rol_requerido("gerente")
@require_safe
def reporte_movimientos(request, tipo, formato="html"):
    if tipo not in ("retiros", "recepciones"):
        raise Http404
    consulta = request.GET.copy()
    if consulta.get("tipo") and consulta["tipo"] != tipo:
        return HttpResponse("El tipo del reporte no coincide con la dirección solicitada.", status=400)
    consulta["tipo"] = tipo
    form = ReporteForm(consulta)
    if not form.is_valid():
        return HttpResponse("Corrige los filtros en Reportes antes de generar el documento.", status=400, content_type="text/plain; charset=utf-8")
    fecha = "fecha_confirmacion" if tipo == "recepciones" else "fecha_salida"
    filas = list(filtrar_retiros(form.cleaned_data, fecha=fecha).prefetch_related("evidencias").order_by(fecha, "pk"))
    if formato == "csv":
        respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
        respuesta["Content-Disposition"] = f'attachment; filename="ecometrics-{tipo}.csv"'
        respuesta.write("\ufeff")
        escritor = csv.writer(respuesta)
        escritor.writerow(["Retiro", "Fecha de salida", "Fecha de recepción", "Sede", "Categoría", "Receptor", "Salida (kg)", "Confirmado (kg)", "Diferencia confirmada (kg)", "Estado", "Referencia documental", "Documentos adjuntos", "Responsable del retiro", "Observación de recepción"])
        for fila in filas:
            escritor.writerow([fila.pk, fila.fecha_salida.isoformat(), fila.fecha_confirmacion.isoformat() if fila.fecha_confirmacion else "",
                texto_csv_seguro(fila.sede.nombre), texto_csv_seguro(fila.categoria.nombre), texto_csv_seguro(fila.receptor),
                format(fila.peso_salida, ".2f"), format(fila.peso_confirmado, ".2f") if fila.peso_confirmado is not None else "",
                format(fila.diferencia, ".2f") if fila.diferencia is not None else "", fila.get_estado_display(),
                texto_csv_seguro(fila.documento_ref), len(fila.evidencias.all()), texto_csv_seguro(fila.actor.get_full_name() or fila.actor.username),
                texto_csv_seguro(fila.observacion_recepcion)])
    else:
        respuesta = render(request, "residuos/reporte_movimientos.html", {"registros": filas, "totales": totales_movimientos(filas),
            "tipo": tipo, "filtros": form.cleaned_data, "emitido_en": timezone.localtime(), "seccion": "reportes", "parametros": consulta.urlencode()})
    respuesta["Cache-Control"] = "private, no-store"
    return respuesta
