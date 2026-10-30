from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from decimal import Decimal
import uuid
from pathlib import Path


class Categoria(models.Model):
    class Grupo(models.TextChoices):
        NO_RECICLABLE = "no_reciclable", "No reciclables"
        RECICLABLE = "reciclable", "Reciclables"
        ORGANICO = "organico", "Orgánicos"

    clave = models.SlugField(unique=True)
    nombre = models.CharField(max_length=80)
    grupo = models.CharField(max_length=20, choices=Grupo.choices)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.nombre


class Pesaje(models.Model):
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pesajes")
    sede = models.ForeignKey("cuentas.Sede", on_delete=models.PROTECT)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    peso_kg = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    fecha_generacion = models.DateField()
    observacion = models.CharField(max_length=500, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    operacion = models.UUIDField()
    anulado = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-creado_en", "-pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(peso_kg__gt=0), name="pesaje_peso_positivo"),
            models.UniqueConstraint(fields=["autor", "operacion"], name="pesaje_operacion_unica"),
        ]
        indexes = [models.Index(fields=["autor", "fecha_generacion"]), models.Index(fields=["sede", "fecha_generacion"])]


class EventoPesaje(models.Model):
    pesaje = models.ForeignKey(Pesaje, on_delete=models.PROTECT, related_name="eventos")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    accion = models.CharField(max_length=30)
    ocurrido_en = models.DateTimeField(auto_now_add=True)
    datos = models.JSONField()
    motivo = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["ocurrido_en", "pk"]


class Retiro(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        OBSERVADO = "observado", "Observado"
        CONCILIADO = "conciliado", "Conciliado"
        ANULADO = "anulado", "Anulado"

    sede = models.ForeignKey("cuentas.Sede", on_delete=models.PROTECT)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    receptor = models.CharField(max_length=160)
    fecha_salida = models.DateField()
    peso_salida = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    peso_confirmado = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    fecha_confirmacion = models.DateField(null=True, blank=True)
    documento_ref = models.CharField(max_length=120, blank=True)
    observacion = models.CharField(max_length=500, blank=True)
    observacion_recepcion = models.CharField(max_length=500, blank=True)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operacion = models.UUIDField()
    version = models.PositiveIntegerField(default=1)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_salida", "-pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(peso_salida__gt=0), name="retiro_salida_positiva"),
            models.CheckConstraint(condition=models.Q(peso_confirmado__isnull=True) | models.Q(peso_confirmado__gte=0), name="retiro_confirmado_no_negativo"),
            models.UniqueConstraint(fields=["actor", "operacion"], name="retiro_operacion_unica"),
        ]

    @property
    def diferencia(self):
        return None if self.peso_confirmado is None else self.peso_confirmado - self.peso_salida


class AsignacionRetiro(models.Model):
    retiro = models.ForeignKey(Retiro, on_delete=models.PROTECT, related_name="asignaciones")
    pesaje = models.ForeignKey(Pesaje, on_delete=models.PROTECT, related_name="asignaciones_retiro")
    peso_kg = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["retiro", "pesaje"], name="asignacion_pesaje_unica"),
                       models.CheckConstraint(condition=models.Q(peso_kg__gt=0), name="asignacion_peso_positivo")]


def ruta_evidencia(instance, nombre):
    return "retiros/" + uuid.uuid4().hex + Path(nombre).suffix.lower()


class EvidenciaRetiro(models.Model):
    retiro = models.ForeignKey(Retiro, on_delete=models.PROTECT, related_name="evidencias")
    archivo = models.FileField(upload_to=ruta_evidencia, max_length=200)
    nombre = models.CharField(max_length=180)
    sha256 = models.CharField(max_length=64)
    tipo = models.CharField(max_length=30)
    tamanio = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)


class EventoRetiro(models.Model):
    retiro = models.ForeignKey(Retiro, on_delete=models.PROTECT, related_name="eventos")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    accion = models.CharField(max_length=30)
    motivo = models.CharField(max_length=1000, blank=True)
    datos = models.JSONField(default=dict)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["creado_en", "pk"]
