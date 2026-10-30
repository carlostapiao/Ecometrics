import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from .models import EventoGestion, Invitacion, Sede


def exigir_gerente(actor):
    actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    if not actor.is_active or actor.rol != "gerente":
        raise PermissionDenied
    return actor


def operario_gestionable(pk):
    usuario = get_user_model().objects.select_for_update().filter(pk=pk, rol="operario", is_staff=False, is_superuser=False).first()
    if not usuario:
        raise PermissionDenied
    return usuario


def datos_usuario(usuario):
    return {"nombres": usuario.first_name, "apellidos": usuario.last_name, "usuario": usuario.username,
            "correo": usuario.email, "sede_id": usuario.sede_id, "sede_nombre": usuario.sede.nombre if usuario.sede_id else "Sin sede", "activo": usuario.is_active,
            "version": usuario.version_gestion}


@transaction.atomic
def guardar_sede(actor, datos, pk=None):
    actor = exigir_gerente(actor)
    sede = Sede.objects.select_for_update().get(pk=pk) if pk else Sede()
    if pk and datos["version"] != sede.version:
        raise ValidationError("La sede cambió en otra operación. Vuelve al listado y ábrela de nuevo.")
    antes = {"nombre": sede.nombre, "direccion": sede.direccion, "activa": sede.activa} if pk else None
    if Sede.objects.filter(nombre__iexact=datos["nombre"]).exclude(pk=pk).exists():
        raise ValidationError("Ya existe una sede con ese nombre.")
    for campo in ("nombre", "direccion", "activa"):
        setattr(sede, campo, datos[campo])
    if pk:
        sede.version += 1
    sede.full_clean()
    sede.save()
    despues = {"nombre": sede.nombre, "direccion": sede.direccion, "activa": sede.activa}
    EventoGestion.objects.create(actor=actor, sede=sede, accion="sede_actualizada" if pk else "sede_creada",
                                 datos={"antes": antes, "despues": despues})
    return sede


@sensitive_variables()
def emitir_invitacion(usuario, actor):
    # Se llama dentro de la transacción y con la cuenta bloqueada.
    token = secrets.token_urlsafe(32)
    invitacion, _ = Invitacion.objects.update_or_create(usuario=usuario, defaults={
        "huella": hashlib.sha256(token.encode()).hexdigest(), "vence_en": timezone.now() + timedelta(hours=24),
        "utilizada_en": None, "revocada_en": None,
    })
    EventoGestion.objects.create(actor=actor, usuario=usuario, accion="activacion_emitida", datos={"vence_en": invitacion.vence_en.isoformat()})
    return token


@transaction.atomic
@sensitive_variables()
def guardar_personal(actor, datos, pk=None):
    actor = exigir_gerente(actor)
    usuario = operario_gestionable(pk) if pk else get_user_model()()
    if pk and datos["version"] != usuario.version_gestion:
        raise ValidationError("La cuenta cambió en otra operación. Abre su ficha nuevamente.")
    sede = Sede.objects.get(pk=datos["sede"].pk)
    activa = datos.get("is_active", False) if pk and usuario.has_usable_password() else False
    if not sede.activa and (not pk or sede.pk != usuario.sede_id or activa):
        raise ValidationError("Selecciona una sede activa para habilitar el acceso.")
    antes = datos_usuario(usuario) if pk else None
    for campo in ("first_name", "last_name", "email"):
        setattr(usuario, campo, datos[campo])
    usuario.sede = sede
    usuario.is_active = activa
    if not pk:
        usuario.username = datos["username"]
        usuario.rol = "operario"
        usuario.is_staff = usuario.is_superuser = False
        usuario.set_unusable_password()
    else:
        usuario.version_gestion += 1
    if get_user_model().objects.filter(username__iexact=usuario.username).exclude(pk=pk).exists():
        raise ValidationError("Ese usuario ya existe.")
    usuario.full_clean()
    usuario.save()
    if pk:
        Invitacion.objects.filter(usuario=usuario, utilizada_en__isnull=True).update(revocada_en=timezone.now())
    EventoGestion.objects.create(actor=actor, usuario=usuario, accion="personal_actualizado" if pk else "personal_creado",
                                 datos={"antes": antes, "despues": datos_usuario(usuario)})
    token = emitir_invitacion(usuario, actor) if not pk else None
    return usuario, token


@transaction.atomic
@sensitive_variables()
def renovar_invitacion(actor, pk, version):
    actor = exigir_gerente(actor)
    usuario = operario_gestionable(pk)
    if usuario.version_gestion != version:
        raise ValidationError("La cuenta cambió. Abre su ficha nuevamente.")
    if usuario.has_usable_password():
        raise ValidationError("La cuenta ya fue activada. No se puede emitir otro enlace de activación.")
    if not usuario.sede_id or not usuario.sede.activa:
        raise ValidationError("Asigna una sede activa antes de emitir el enlace.")
    usuario.version_gestion += 1
    usuario.save(update_fields=["version_gestion"])
    return usuario, emitir_invitacion(usuario, actor)


@transaction.atomic
def revocar_invitacion(actor, pk, version):
    actor = exigir_gerente(actor)
    usuario = operario_gestionable(pk)
    if usuario.version_gestion != version or usuario.has_usable_password():
        raise ValidationError("La cuenta cambió o ya está activada. Abre su ficha nuevamente.")
    Invitacion.objects.filter(usuario=usuario, utilizada_en__isnull=True).update(revocada_en=timezone.now())
    usuario.version_gestion += 1
    usuario.save(update_fields=["version_gestion"])
    EventoGestion.objects.create(actor=actor, usuario=usuario, accion="activacion_revocada")


@sensitive_variables()
def buscar_invitacion(token):
    if not token or len(token) > 100:
        return None
    return Invitacion.objects.filter(huella=hashlib.sha256(token.encode()).hexdigest(),
                                     utilizada_en__isnull=True, revocada_en__isnull=True,
                                     vence_en__gt=timezone.now()).select_related("usuario").first()


@transaction.atomic
@sensitive_variables()
def activar_cuenta(token, clave):
    invitacion = buscar_invitacion(token)
    if not invitacion:
        raise ValidationError("El enlace venció, fue reemplazado o ya se utilizó. Solicita uno nuevo al gerente.")
    usuario = operario_gestionable(invitacion.usuario_id)
    invitacion = Invitacion.objects.select_for_update().get(pk=invitacion.pk)
    if (invitacion.huella != hashlib.sha256(token.encode()).hexdigest() or invitacion.utilizada_en or invitacion.revocada_en
            or invitacion.vence_en <= timezone.now() or usuario.has_usable_password()):
        raise ValidationError("El enlace ya no está disponible. Solicita uno nuevo al gerente.")
    if not usuario.sede_id or not usuario.sede.activa:
        raise ValidationError("La cuenta necesita una sede activa. Comunícate con el gerente.")
    validate_password(clave, usuario)
    usuario.set_password(clave)
    usuario.is_active = True
    usuario.version_gestion += 1
    usuario.save(update_fields=["password", "is_active", "version_gestion"])
    invitacion.utilizada_en = timezone.now()
    invitacion.save(update_fields=["utilizada_en"])
    EventoGestion.objects.create(actor=usuario, usuario=usuario, accion="cuenta_activada", datos={"sede_id": usuario.sede_id})
    return usuario
