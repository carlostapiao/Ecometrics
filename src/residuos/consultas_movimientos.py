from decimal import Decimal
from django.db.models import Count, Q, Sum
from .models import Pesaje, Retiro


def filtrar_retiros(datos, fecha="fecha_salida", incluir_anulados=False):
    if fecha not in ("fecha_salida", "fecha_confirmacion"):
        raise ValueError("Fecha de movimiento no admitida")
    registros = Retiro.objects.select_related("sede", "categoria", "actor")
    if not incluir_anulados:
        registros = registros.exclude(estado=Retiro.Estado.ANULADO)
    if fecha == "fecha_confirmacion":
        registros = registros.filter(peso_confirmado__isnull=False, fecha_confirmacion__isnull=False)
    for campo in ("sede", "categoria", "estado"):
        if datos.get(campo):
            registros = registros.filter(**{campo: datos[campo]})
    if datos.get("desde"):
        registros = registros.filter(**{fecha + "__gte": datos["desde"]})
    if datos.get("hasta"):
        registros = registros.filter(**{fecha + "__lte": datos["hasta"]})
    return registros


def filtrar_generacion(datos, incluir_anulados=False):
    registros = Pesaje.objects.select_related("sede", "categoria", "autor")
    if not incluir_anulados:
        registros = registros.filter(anulado=False)
    for campo in ("sede", "categoria"):
        if datos.get(campo):
            registros = registros.filter(**{campo: datos[campo]})
    if datos.get("desde"):
        registros = registros.filter(fecha_generacion__gte=datos["desde"])
    if datos.get("hasta"):
        registros = registros.filter(fecha_generacion__lte=datos["hasta"])
    return registros


def totales_movimientos(filas):
    if hasattr(filas, "aggregate"):
        datos = filas.aggregate(salida=Sum("peso_salida"), cantidad=Count("id"), confirmado=Sum("peso_confirmado"),
                                confirmadas=Count("peso_confirmado"), salida_confirmada=Sum("peso_salida", filter=Q(peso_confirmado__isnull=False)))
        for campo in ("salida", "confirmado", "salida_confirmada"):
            datos[campo] = datos[campo] or Decimal("0.00")
        datos["sin_recepcion"] = datos["cantidad"] - datos["confirmadas"]
        datos["diferencia"] = datos["confirmado"] - datos["salida_confirmada"]
        return datos
    filas = list(filas)
    confirmadas = [fila for fila in filas if fila.peso_confirmado is not None]
    return {"salida": sum((fila.peso_salida for fila in filas), Decimal("0.00")), "cantidad": len(filas),
            "confirmado": sum((fila.peso_confirmado for fila in confirmadas), Decimal("0.00")),
            "confirmadas": len(confirmadas), "sin_recepcion": len(filas) - len(confirmadas),
            "salida_confirmada": sum((fila.peso_salida for fila in confirmadas), Decimal("0.00")),
            "diferencia": sum((fila.diferencia for fila in confirmadas), Decimal("0.00"))}
