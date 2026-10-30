import hashlib
import json
import tarfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from psycopg import sql


def inventario():
    tablas = {}
    with connection.cursor() as cursor:
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
        nombres = [fila[0] for fila in cursor.fetchall()]
        for nombre in nombres:
            cursor.execute(sql.SQL("SELECT row_to_json(t)::text FROM {} t").format(sql.Identifier("public", nombre)))
            filas = sorted(fila[0] for fila in cursor.fetchall())
            huella = hashlib.sha256()
            for fila in filas:
                huella.update(fila.encode("utf-8") + b"\n")
            tablas[nombre] = {"filas": len(filas), "sha256": huella.hexdigest()}
        cursor.execute("SELECT sequencename, last_value FROM pg_sequences WHERE schemaname = 'public' ORDER BY sequencename")
        secuencias = dict(cursor.fetchall())
    archivos = {}
    raiz = Path(settings.MEDIA_ROOT)
    for archivo in sorted(raiz.rglob("*")):
        if archivo.is_symlink():
            raise CommandError("El almacén contiene un enlace simbólico; revisa su origen.")
        if archivo.is_file():
            with archivo.open("rb") as entrada:
                huella = hashlib.file_digest(entrada, "sha256").hexdigest()
            archivos[archivo.relative_to(raiz).as_posix()] = {"bytes": archivo.stat().st_size, "sha256": huella}
    from residuos.models import EvidenciaRetiro
    for documento in EvidenciaRetiro.objects.all():
        datos = archivos.get(documento.archivo.name)
        if not datos or datos["sha256"] != documento.sha256 or datos["bytes"] != documento.tamanio:
            raise CommandError("Un respaldo documental no coincide con su referencia en la base.")
    return {"tablas": tablas, "secuencias": secuencias, "archivos": archivos}


class Command(BaseCommand):
    help = "Inventaría y comprueba respaldos sin revelar filas ni credenciales."

    def add_arguments(self, parser):
        parser.add_argument("accion", choices=["crear", "verificar"])
        parser.add_argument("carpeta")

    def handle(self, *args, **opciones):
        carpeta = Path(opciones["carpeta"])
        manifiesto = carpeta / "inventario.json"
        datos = inventario()
        if opciones["accion"] == "crear":
            if manifiesto.exists() or (carpeta / "documentos.tar.gz").exists():
                raise CommandError("El destino ya contiene un respaldo; utiliza una carpeta nueva.")
            with tarfile.open(carpeta / "documentos.tar.gz", "w:gz") as salida:
                for nombre in datos["archivos"]:
                    salida.add(Path(settings.MEDIA_ROOT) / nombre, arcname=nombre, recursive=False)
            manifiesto.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write("INVENTARIO_RESPALDO=OK")
        else:
            if datos != json.loads(manifiesto.read_text(encoding="utf-8")):
                raise CommandError("La copia restaurada no coincide con el inventario original.")
            self.stdout.write("BASE_Y_DOCUMENTOS_RESTAURADOS=OK")
            self.stdout.write(f"TABLAS_COMPROBADAS={len(datos['tablas'])}; ARCHIVOS_COMPROBADOS={len(datos['archivos'])}")
