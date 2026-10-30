from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class Sede(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    activa = models.BooleanField(default=True)
    direccion = models.CharField(max_length=250, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(Lower("nombre"), name="sede_nombre_sin_mayusculas")]

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        OPERARIO = "operario", "Operario"
        GERENTE = "gerente", "Gerente"

    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.OPERARIO)
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, null=True, blank=True)
    version_gestion = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(Lower("username"), name="usuario_nombre_sin_mayusculas")]


class Invitacion(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.PROTECT, related_name="invitacion")
    huella = models.CharField(max_length=64, unique=True)
    vence_en = models.DateTimeField()
    utilizada_en = models.DateTimeField(null=True, blank=True)
    revocada_en = models.DateTimeField(null=True, blank=True)


class EventoGestion(models.Model):
    actor = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="acciones_gestion")
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, null=True, blank=True, related_name="eventos_gestion")
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, null=True, blank=True, related_name="eventos_gestion")
    accion = models.CharField(max_length=40)
    ocurrido_en = models.DateTimeField(auto_now_add=True)
    datos = models.JSONField(default=dict)

    class Meta:
        ordering = ["-ocurrido_en", "-pk"]

    @property
    def etiqueta(self):
        return {"sede_creada": "Sede creada", "sede_actualizada": "Sede actualizada",
                "personal_creado": "Personal añadido", "personal_actualizado": "Personal actualizado",
                "activacion_emitida": "Enlace de activación emitido", "activacion_revocada": "Enlace de activación revocado",
                "cuenta_activada": "Cuenta activada"}.get(self.accion, self.accion)

    @property
    def cambios(self):
        antes = self.datos.get("antes") or {}
        despues = self.datos.get("despues") or {}
        nombres = {"nombre": "Nombre", "direccion": "Dirección", "activa": "Sede activa", "nombres": "Nombres",
                   "apellidos": "Apellidos", "correo": "Correo", "sede_nombre": "Sede", "activo": "Acceso activo"}
        def texto(valor):
            return ("Sí" if valor else "No") if isinstance(valor, bool) else (valor or "Sin dato")
        return [{"campo": nombre, "antes": texto(antes.get(campo)), "despues": texto(despues.get(campo))}
                for campo, nombre in nombres.items() if campo in despues and antes.get(campo) != despues[campo]]
