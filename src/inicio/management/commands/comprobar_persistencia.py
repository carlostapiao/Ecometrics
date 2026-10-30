from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import re
import uuid


class Command(BaseCommand):
    help = "Escribe o comprueba una marca técnica sin datos de negocio ni autenticación."

    def add_arguments(self, parser):
        parser.add_argument("modo", choices=["escribir", "comprobar"])
        parser.add_argument("marca")

    def handle(self, *args, **options):
        clave = "ecometrics-verificacion-base"
        if options["modo"] == "escribir":
            anterior = Session.objects.filter(session_key=clave).first()
            archivo_anterior = anterior.get_decoded().get("archivo_tecnico", "") if anterior else ""
            archivo = default_storage.save("verificaciones/" + uuid.uuid4().hex + ".txt", ContentFile(options["marca"].encode()))
            try:
                Session.objects.update_or_create(
                    session_key=clave,
                    defaults={
                        "session_data": SessionStore().encode({"marca_tecnica": options["marca"], "archivo_tecnico": archivo}),
                        "expire_date": timezone.now() + timezone.timedelta(days=1),
                    },
                )
            except Exception:
                default_storage.delete(archivo)
                raise
            if re.fullmatch(r"verificaciones/[0-9a-f]{32}\.txt", archivo_anterior):
                default_storage.delete(archivo_anterior)
            self.stdout.write("MARCA_TECNICA_GUARDADA=OK")
        else:
            sesion = Session.objects.filter(session_key=clave).first()
            if not sesion or sesion.get_decoded().get("marca_tecnica") != options["marca"]:
                raise CommandError("La marca no se conservó en PostgreSQL.")
            archivo = sesion.get_decoded().get("archivo_tecnico", "")
            if not re.fullmatch(r"verificaciones/[0-9a-f]{32}\.txt", archivo) or not default_storage.exists(archivo):
                raise CommandError("El archivo de comprobación no se conservó en el volumen de evidencias.")
            with default_storage.open(archivo, "rb") as contenido:
                if contenido.read() != options["marca"].encode():
                    raise CommandError("El contenido del archivo de comprobación cambió.")
            self.stdout.write("PERSISTENCIA_TRAS_RECREACION=OK")
            self.stdout.write("PERSISTENCIA_ARCHIVOS=OK")
