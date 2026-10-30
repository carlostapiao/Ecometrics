from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from residuos.models import Pesaje
from residuos.views import rol_requerido
from .forms import PersonalForm, SedeForm
from .models import Sede
from .services import activar_cuenta, buscar_invitacion, guardar_personal, guardar_sede, renovar_invitacion, revocar_invitacion


def operarios():
    return get_user_model().objects.filter(rol="operario", is_staff=False, is_superuser=False)


@rol_requerido("gerente")
@require_safe
def sedes(request):
    consulta = Sede.objects.annotate(personal_activo=Count("usuario", filter=Q(usuario__rol="operario", usuario__is_active=True))).order_by("nombre")
    resumen = {r["sede_id"]: r for r in Pesaje.objects.filter(anulado=False).order_by().values("sede_id").annotate(peso=Sum("peso_kg"), cantidad=Count("id"))}
    filas = [{"sede": sede, "pesajes": resumen.get(sede.pk, {})} for sede in consulta]
    return render(request, "cuentas/sedes.html", {"filas": filas, "seccion": "sedes"})


@rol_requerido("gerente")
@require_http_methods(["GET", "POST"])
def sede_editar(request, pk=None):
    sede = get_object_or_404(Sede, pk=pk) if pk else Sede()
    form = SedeForm(request.POST if request.method == "POST" else None, instance=sede)
    if request.method == "POST" and form.is_valid():
        try:
            guardar_sede(request.user, form.cleaned_data, pk)
        except ValidationError as error:
            form.add_error(None, error)
        except IntegrityError:
            form.add_error(None, "No se guardó la sede porque sus datos coinciden con otro registro. Revisa el nombre.")
        else:
            messages.success(request, "Sede actualizada." if pk else "Sede creada.")
            return redirect("sedes")
    return render(request, "cuentas/sede_form.html", {"form": form, "sede": sede,
                  "eventos": sede.eventos_gestion.select_related("actor")[:10] if pk else [], "seccion": "sedes"},
                  status=400 if request.method == "POST" else 200)


@rol_requerido("gerente")
@require_safe
def personal(request):
    consulta = operarios().select_related("sede", "invitacion").order_by("first_name", "username")
    buscar = request.GET.get("buscar", "").strip()[:100]
    if buscar:
        consulta = consulta.filter(Q(first_name__icontains=buscar) | Q(last_name__icontains=buscar) | Q(username__icontains=buscar))
    return render(request, "cuentas/personal.html", {"pagina": Paginator(consulta, 15).get_page(request.GET.get("page")),
                  "buscar": buscar, "seccion": "personal"})


def respuesta_invitacion(request, persona, token):
    respuesta = render(request, "cuentas/invitacion.html", {
        "persona": persona, "enlace": request.build_absolute_uri(reverse("activar_cuenta")) + "#" + token,
        "seccion": "personal",
    })
    respuesta["Cache-Control"] = "private, no-store"
    respuesta["Referrer-Policy"] = "no-referrer"
    return respuesta


@rol_requerido("gerente")
@never_cache
@require_http_methods(["GET", "POST"])
def personal_editar(request, pk=None):
    persona = get_object_or_404(operarios(), pk=pk) if pk else get_user_model()()
    form = PersonalForm(request.POST if request.method == "POST" else None, instance=persona)
    if request.method == "POST" and form.is_valid():
        try:
            persona, token = guardar_personal(request.user, form.cleaned_data, pk)
        except ValidationError as error:
            form.add_error(None, error)
        except IntegrityError:
            form.add_error(None, "No se guardó la cuenta. El usuario puede haber sido registrado en otra operación.")
        else:
            if token:
                return respuesta_invitacion(request, persona, token)
            messages.success(request, "Personal actualizado. El historial de pesajes se conserva.")
            return redirect("personal")
    return render(request, "cuentas/personal_form.html", {"form": form, "persona": persona,
                  "eventos": persona.eventos_gestion.select_related("actor")[:10] if pk else [], "seccion": "personal"},
                  status=400 if request.method == "POST" else 200)


@rol_requerido("gerente")
@never_cache
@require_POST
def invitacion_gestionar(request, pk):
    persona = get_object_or_404(operarios(), pk=pk)
    try:
        version = int(request.POST.get("version", ""))
    except (ValueError, TypeError):
        return HttpResponse("La solicitud no es válida. Abre la ficha del personal nuevamente.", status=400)
    try:
        if request.POST.get("accion") == "revocar":
            revocar_invitacion(request.user, pk, version)
            messages.success(request, "Enlace revocado. La cuenta sigue sin acceso.")
            return redirect("personal_editar", pk=pk)
        if request.POST.get("accion") != "emitir":
            return HttpResponse("Selecciona una acción válida.", status=400)
        persona, token = renovar_invitacion(request.user, pk, version)
    except ValidationError as error:
        return render(request, "cuentas/aviso.html", {"errores": error.messages, "persona": persona, "seccion": "personal"}, status=400)
    return respuesta_invitacion(request, persona, token)


@never_cache
@sensitive_post_parameters("token", "new_password1", "new_password2")
@require_http_methods(["GET", "POST"])
def activacion(request):
    token = request.POST.get("token", "") if request.method == "POST" else ""
    invitacion = buscar_invitacion(token) if request.method == "POST" else None
    form = SetPasswordForm(invitacion.usuario if invitacion else None, request.POST if request.method == "POST" else None)
    completada = False
    if request.method == "POST":
        if not invitacion:
            form.add_error(None, "El enlace venció, fue reemplazado o ya se utilizó. Solicita uno nuevo al gerente.")
        elif form.is_valid():
            try:
                activar_cuenta(token, form.cleaned_data["new_password1"])
            except ValidationError as error:
                form.add_error(None, error)
            else:
                completada = True
                token = ""
    respuesta = render(request, "cuentas/activar.html", {"form": form, "token": token, "completada": completada},
                       status=400 if request.method == "POST" and not completada else 200)
    respuesta["Referrer-Policy"] = "same-origin"
    return respuesta
