import json
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cuentas.models import Sede


class Command(BaseCommand):
    help = "Crea cuentas ficticias desde JSON por stdin sin imprimir contraseñas ni reiniciar datos."

    @transaction.atomic
    def handle(self, *args, **options):
        datos = json.load(sys.stdin)
        definiciones = [
            ("operario_norte", "Alex", "operario", "Planta Norte"),
            ("operario_norte_2", "María", "operario", "Planta Norte"),
            ("operario_sur", "Luis", "operario", "Planta Sur"),
            ("gerente_demo", "Carlos", "gerente", None),
        ]
        for nombre, persona, rol, sede_nombre in definiciones:
            clave = datos.get(nombre)
            if not clave or len(clave) < 16:
                raise CommandError("Cada cuenta requiere una contraseña local de al menos 16 caracteres.")
            sede = Sede.objects.get_or_create(nombre=sede_nombre)[0] if sede_nombre else None
            usuario, creado = get_user_model().objects.get_or_create(username=nombre, defaults={
                "first_name": persona, "rol": rol, "sede": sede,
            })
            if creado:
                usuario.set_password(clave)
                usuario.save(update_fields=["password"])
            elif not usuario.check_password(clave) or usuario.rol != rol or usuario.sede_id != (sede.pk if sede else None):
                raise CommandError("Una cuenta demo existente no coincide. No se cambió su contraseña ni su asignación.")
        self.stdout.write("DEMO_PREPARADA=OK; 2 sedes y 4 cuentas, sin generar pesajes ni restablecer datos.")
