import hashlib
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from cuentas.models import Sede, Usuario
from cuentas.services import exigir_gerente
from .cantidades import validar_kg
from .models import AsignacionRetiro, Categoria, EventoRetiro, EvidenciaRetiro, Pesaje, Retiro


def exigir_registrador(actor):
    actor = Usuario.objects.select_for_update().get(pk=actor.pk)
    if not actor.is_active or actor.rol not in ('gerente', 'operario'):
        raise PermissionDenied
    if actor.rol == 'operario' and (not actor.sede_id or not actor.sede.activa):
        raise PermissionDenied
    return actor


def autorizar_retiro(actor, retiro):
    if actor.rol == 'operario' and (retiro.actor_id != actor.pk or retiro.sede_id != actor.sede_id):
        raise PermissionDenied


def pesajes_disponibles(sede, categoria):
    decimal = DecimalField(max_digits=12, decimal_places=2)
    return Pesaje.objects.filter(sede=sede, categoria=categoria, anulado=False).annotate(
        retirado=Coalesce(Sum("asignaciones_retiro__peso_kg", filter=~Q(asignaciones_retiro__retiro__estado=Retiro.Estado.ANULADO)), Value(Decimal("0.00")), output_field=decimal)
    ).annotate(disponible=F("peso_kg") - F("retirado")).order_by("fecha_generacion", "pk")


def snapshot(retiro):
    return {"peso_salida": str(retiro.peso_salida), "peso_confirmado": str(retiro.peso_confirmado) if retiro.peso_confirmado is not None else None,
            "fecha_confirmacion": retiro.fecha_confirmacion.isoformat() if retiro.fecha_confirmacion else None,
            "documento_ref": retiro.documento_ref, "estado": retiro.estado, "version": retiro.version,
            "observacion_recepcion": retiro.observacion_recepcion}


def bloquear_retiro(actor, pk, version):
    actor = exigir_registrador(actor)
    retiro = Retiro.objects.select_for_update().get(pk=pk)
    autorizar_retiro(actor, retiro)
    if retiro.version != version:
        raise ValidationError("El retiro cambió en otra operación. Vuelve a abrir su detalle.")
    return actor, retiro


@transaction.atomic
def crear_retiro(actor, datos, filas):
    actor = exigir_registrador(actor)
    pares = [(fila["pesaje"].pk, validar_kg(fila["peso_kg"])) for fila in filas]
    if not pares or len(pares) > 20 or len({pk for pk, _ in pares}) != len(pares):
        raise ValidationError("Selecciona entre uno y veinte pesajes distintos para el retiro.")
    sede = Sede.objects.get(pk=datos["sede"].pk)
    categoria = Categoria.objects.get(pk=datos["categoria"].pk)
    if actor.rol == "operario" and sede.pk != actor.sede_id:
        raise PermissionDenied
    existente = Retiro.objects.filter(actor=actor, operacion=datos["operacion"]).first()
    if existente:
        iguales = (existente.sede_id == sede.pk and existente.categoria_id == categoria.pk and existente.receptor == datos["receptor"]
                   and existente.fecha_salida == datos["fecha_salida"] and existente.observacion == datos.get("observacion", "")
                   and sorted(existente.asignaciones.values_list("pesaje_id", "peso_kg")) == sorted(pares))
        if not iguales:
            raise ValidationError("La operación ya fue registrada con otros datos. Abre un formulario nuevo.")
        return existente, False
    if not sede.activa or datos["fecha_salida"] > timezone.localdate():
        raise ValidationError("Elige una sede activa y una fecha de salida no futura.")
    origenes = list(Pesaje.objects.select_for_update().filter(pk__in=[pk for pk, _ in pares]).order_by("pk"))
    if len(origenes) != len(pares):
        raise ValidationError("Uno de los pesajes ya no está disponible.")
    cantidades = dict(pares)
    for pesaje in origenes:
        if actor.rol == "operario" and pesaje.autor_id != actor.pk:
            raise PermissionDenied
        if pesaje.anulado or pesaje.sede_id != sede.pk or pesaje.categoria_id != categoria.pk or pesaje.fecha_generacion > datos["fecha_salida"]:
            raise ValidationError("Cada pesaje debe ser vigente, de la misma sede/categoría y anterior o igual a la salida.")
        asignado = pesaje.asignaciones_retiro.exclude(retiro__estado=Retiro.Estado.ANULADO).aggregate(peso=Sum("peso_kg"))["peso"] or Decimal("0.00")
        if cantidades[pesaje.pk] > pesaje.peso_kg - asignado:
            raise ValidationError(f"El pesaje #{pesaje.pk} no tiene saldo suficiente para esta salida.")
    retiro = Retiro(sede=sede, categoria=categoria, receptor=datos["receptor"], fecha_salida=datos["fecha_salida"],
                    peso_salida=validar_kg(sum(cantidades.values())), observacion=datos.get("observacion", ""), actor=actor, operacion=datos["operacion"])
    retiro.full_clean()
    retiro.save()
    for pesaje in origenes:
        AsignacionRetiro.objects.create(retiro=retiro, pesaje=pesaje, peso_kg=cantidades[pesaje.pk])
    EventoRetiro.objects.create(retiro=retiro, actor=actor, accion="creacion", datos={"despues": snapshot(retiro), "origenes": [{"pesaje": pk, "kg": str(peso)} for pk, peso in pares]})
    return retiro, True


@transaction.atomic
def confirmar_recepcion(actor, pk, datos):
    actor, retiro = bloquear_retiro(actor, pk, datos["version"])
    if retiro.estado in (Retiro.Estado.ANULADO, Retiro.Estado.CONCILIADO):
        raise ValidationError("El retiro está cerrado. Reabre la conciliación antes de modificarla.")
    if datos["fecha_confirmacion"] < retiro.fecha_salida or datos["fecha_confirmacion"] > timezone.localdate():
        raise ValidationError("La recepción debe estar entre la fecha de salida y hoy.")
    antes = snapshot(retiro)
    retiro.peso_confirmado = validar_kg(datos["peso_confirmado"], permitir_cero=True)
    for campo in ("fecha_confirmacion", "documento_ref", "observacion_recepcion"):
        setattr(retiro, campo, datos[campo])
    retiro.estado = Retiro.Estado.OBSERVADO if retiro.diferencia != 0 else Retiro.Estado.PENDIENTE
    retiro.version += 1
    retiro.full_clean()
    retiro.save()
    EventoRetiro.objects.create(retiro=retiro, actor=actor, accion="recepcion", datos={"antes": antes, "despues": snapshot(retiro)})
    return retiro


@transaction.atomic
def resolver_retiro(actor, pk, datos):
    actor = exigir_gerente(actor)
    actor, retiro = bloquear_retiro(actor, pk, datos["version"])
    accion = datos["accion"]
    motivo = datos.get("motivo", "").strip()
    if len(motivo) > 1000:
        raise ValidationError("El motivo no puede superar los 1000 caracteres.")
    antes = snapshot(retiro)
    if accion == "conciliar":
        if retiro.estado not in (Retiro.Estado.PENDIENTE, Retiro.Estado.OBSERVADO):
            raise ValidationError("Este retiro no está pendiente de conciliación.")
        if retiro.peso_confirmado is None or not retiro.documento_ref or not retiro.evidencias.exists():
            raise ValidationError("Registra el peso confirmado, la referencia del documento y al menos un respaldo antes de conciliar.")
        if retiro.diferencia != 0 and not motivo:
            raise ValidationError("Explica la diferencia de peso antes de cerrar la conciliación.")
        retiro.estado = Retiro.Estado.CONCILIADO
    elif accion == "reabrir":
        if retiro.estado != Retiro.Estado.CONCILIADO or not motivo:
            raise ValidationError("Solo se puede reabrir un retiro conciliado e indicando el motivo.")
        retiro.estado = Retiro.Estado.OBSERVADO
    elif accion == "anular":
        if retiro.estado not in (Retiro.Estado.PENDIENTE, Retiro.Estado.OBSERVADO) or not motivo:
            raise ValidationError("Indica el motivo. Si está conciliado, reábrelo antes de anular.")
        retiro.estado = Retiro.Estado.ANULADO
    else:
        raise ValidationError("La acción no es válida.")
    retiro.version += 1
    retiro.save(update_fields=["estado", "version"])
    EventoRetiro.objects.create(retiro=retiro, actor=actor, accion=accion, motivo=motivo, datos={"antes": antes, "despues": snapshot(retiro)})
    return retiro


def validar_archivo(archivo):
    nombre = str(archivo.name).replace("\\", "/").split("/")[-1][:180]
    extension = Path(nombre).suffix.lower()
    tipos = {".pdf": (b"%PDF-", "application/pdf"), ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
             ".jpeg": (b"\xff\xd8\xff", "image/jpeg"), ".png": (b"\x89PNG\r\n\x1a\n", "image/png")}
    if extension not in tipos or not nombre or any(ord(letra) < 32 for letra in nombre):
        raise ValidationError("Adjunta un archivo PDF, JPG o PNG válido.")
    digest = hashlib.sha256()
    total = 0
    inicio = b""
    try:
        for parte in archivo.chunks():
            total += len(parte)
            if total > 10 * 1024 * 1024:
                raise ValidationError("El archivo no puede superar los 10 MB.")
            if not inicio:
                inicio = parte[:12]
            digest.update(parte)
    finally:
        archivo.seek(0)
    if total == 0 or not inicio.startswith(tipos[extension][0]):
        raise ValidationError("El contenido del archivo no coincide con su tipo.")
    return {"nombre": nombre, "sha256": digest.hexdigest(), "tipo": tipos[extension][1], "tamanio": total}


def adjuntar_evidencia(actor, pk, archivo, version):
    evidencia = None
    guardado = False
    try:
        with transaction.atomic():
            actor, retiro = bloquear_retiro(actor, pk, version)
            if retiro.estado in (Retiro.Estado.CONCILIADO, Retiro.Estado.ANULADO):
                raise ValidationError("Reabre el retiro antes de añadir un respaldo.")
            metadatos = validar_archivo(archivo)
            if retiro.evidencias.filter(sha256=metadatos["sha256"]).exists():
                raise ValidationError("Ese archivo ya está adjunto a este retiro.")
            evidencia = EvidenciaRetiro(retiro=retiro, actor=actor, **metadatos)
            evidencia.archivo.save(metadatos["nombre"], archivo, save=False)
            guardado = True
            evidencia.save()
            retiro.version += 1
            retiro.save(update_fields=["version"])
            EventoRetiro.objects.create(retiro=retiro, actor=actor, accion="evidencia", datos={"nombre": evidencia.nombre, "sha256": evidencia.sha256, "evidencia_id": evidencia.pk})
        return evidencia
    except Exception:
        if guardado:
            evidencia.archivo.storage.delete(evidencia.archivo.name)
        raise
