from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum

from .models import EventoPesaje, Pesaje, Retiro


def instantanea(pesaje):
    return {"categoria": pesaje.categoria.clave, "categoria_nombre": pesaje.categoria.nombre,
            "peso_kg": str(pesaje.peso_kg), "fecha_generacion": pesaje.fecha_generacion.isoformat(),
            "observacion": pesaje.observacion, "autor_id": pesaje.autor_id,
            "sede_id": pesaje.sede_id, "anulado": pesaje.anulado, "version": pesaje.version}


@transaction.atomic
def modificar_pesaje(usuario, pesaje_id, datos, *, anular=False):
    actor = get_user_model().objects.select_for_update().get(pk=usuario.pk)
    if not actor.is_active or actor.rol != "gerente":
        raise PermissionDenied
    pesaje = Pesaje.objects.select_for_update(of=("self",)).select_related("categoria").get(pk=pesaje_id)
    if pesaje.version != datos["version"]:
        raise ValidationError("Este pesaje cambió en otra operación. Vuelve al detalle y abre un formulario nuevo.")
    if pesaje.anulado:
        raise ValidationError("El pesaje está anulado y no admite más cambios.")
    asignaciones = pesaje.asignaciones_retiro.exclude(retiro__estado=Retiro.Estado.ANULADO)
    total_retirado = asignaciones.aggregate(peso=Sum("peso_kg"))["peso"] or 0
    if total_retirado:
        if anular:
            raise ValidationError("Este pesaje tiene retiros vinculados. Revisa y anula esos retiros antes de anular el pesaje.")
        primera_salida = asignaciones.order_by("retiro__fecha_salida").first().retiro.fecha_salida
        if datos["categoria"].pk != pesaje.categoria_id or datos["peso_kg"] < total_retirado or datos["fecha_generacion"] > primera_salida:
            raise ValidationError("La corrección no puede cambiar la categoría, reducir el peso por debajo de lo retirado ni dejar la generación después de una salida vinculada.")
    motivo = datos.get("motivo", "").strip()
    if not motivo or len(motivo) > 500:
        raise ValidationError("Indica un motivo de hasta 500 caracteres.")
    anterior = instantanea(pesaje)
    if anular:
        pesaje.anulado = True
    else:
        categoria = datos["categoria"]
        if not categoria.activa and categoria.pk != pesaje.categoria_id:
            raise ValidationError("La categoría seleccionada ya no está activa.")
        for campo in ("categoria", "peso_kg", "fecha_generacion", "observacion"):
            setattr(pesaje, campo, datos[campo])
        if instantanea(pesaje) == anterior:
            raise ValidationError("No hay cambios para guardar.")
    pesaje.version += 1
    pesaje.full_clean()
    pesaje.save(update_fields=["categoria", "peso_kg", "fecha_generacion", "observacion", "anulado", "version"])
    EventoPesaje.objects.create(pesaje=pesaje, actor=actor, accion="anulacion" if anular else "correccion",
                               motivo=motivo, datos={"antes": anterior, "despues": instantanea(pesaje)})
    return pesaje


@transaction.atomic
def registrar_pesaje(usuario, datos):
    usuario = get_user_model().objects.select_for_update(of=("self",)).select_related("sede").get(pk=usuario.pk)
    if not usuario.is_active or usuario.rol != "operario" or not usuario.sede_id or not usuario.sede.activa:
        raise PermissionDenied
    valores = {k: datos[k] for k in ("categoria", "peso_kg", "fecha_generacion", "observacion")}
    existente = Pesaje.objects.filter(autor=usuario, operacion=datos["operacion"]).first()
    if existente:
        if any(getattr(existente, k) != v for k, v in valores.items()):
            raise ValidationError("Esta operación ya fue registrada con otros datos. Abre un formulario nuevo.")
        return existente, False
    if not valores["categoria"].activa:
        raise ValidationError("La categoría ya no está activa.")
    pesaje = Pesaje(autor=usuario, sede=usuario.sede, operacion=datos["operacion"], **valores)
    pesaje.full_clean()
    pesaje.save()
    EventoPesaje.objects.create(pesaje=pesaje, actor=usuario, accion="creacion", datos={
        "peso_kg": str(pesaje.peso_kg), "categoria": pesaje.categoria.clave,
        "sede_id": pesaje.sede_id, "fecha_generacion": pesaje.fecha_generacion.isoformat(),
        "observacion": pesaje.observacion,
    })
    return pesaje, True
