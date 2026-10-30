"""Crea una copia privada y verifica su recuperación sin tocar la base original."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tarfile
import time
import uuid
from datetime import datetime, timezone


def ejecutar(*args, entrada=None, env=None):
    proceso = subprocess.run([str(arg) for arg in args], input=entrada, text=True,
                             encoding="utf-8", capture_output=True, env=env)
    if proceso.returncode:
        # No se imprimen salidas de comandos ni argumentos con datos de la base.
        raise RuntimeError(f"Falló {args[0]} (código {proceso.returncode}).")
    return proceso.stdout.strip()


def compose(*args):
    return ejecutar("docker", "compose", *args)


def huella(ruta):
    with ruta.open("rb") as entrada:
        return hashlib.file_digest(entrada, "sha256").hexdigest()


def crear(raiz):
    carpeta = raiz / ".private" / "respaldos" / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    carpeta.mkdir(parents=True, exist_ok=False)
    db = compose("ps", "-q", "db")
    web = compose("ps", "-q", "web")
    if not db or not web:
        raise RuntimeError("Inicia primero la base y la aplicación.")
    imagen_db = ejecutar("docker", "inspect", "--format", "{{.Image}}", db)
    imagen_web = ejecutar("docker", "inspect", "--format", "{{.Image}}", web)
    remoto = "/tmp/ecometrics-" + uuid.uuid4().hex + ".dump"
    print("Pausando la aplicación para obtener una copia coherente...", flush=True)
    compose("stop", "web")
    try:
        ejecutar("docker", "exec", db, "sh", "-c", 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl -f "$1"', "sh", remoto)
        ejecutar("docker", "cp", f"{db}:{remoto}", carpeta / "base.dump")
        compose("run", "--rm", "--no-deps", "-T", "-v", f"{carpeta}:/backup", "web",
                "python", "manage.py", "comprobar_respaldo", "crear", "/backup")
    finally:
        # Se recupera el servicio incluso si el volcado o la copia fallan.
        compose("start", "web")
        ejecutar("docker", "exec", db, "rm", "-f", remoto)
    archivos = {nombre: huella(carpeta / nombre) for nombre in ("base.dump", "documentos.tar.gz", "inventario.json")}
    (carpeta / "respaldo.json").write_text(json.dumps({"version": 1, "creado_utc": datetime.now(timezone.utc).isoformat(),
        "imagen_db": imagen_db, "imagen_web": imagen_web, "sha256": archivos}, indent=2), encoding="utf-8")
    print("RESPALDO_CREADO=OK", flush=True)
    print(f"Carpeta privada: {carpeta}", flush=True)
    return carpeta


def verificar(carpeta, raiz):
    meta = json.loads((carpeta / "respaldo.json").read_text(encoding="utf-8"))
    nombres = {"base.dump", "documentos.tar.gz", "inventario.json"}
    if meta.get("version") != 1 or set(meta["sha256"]) != nombres:
        raise RuntimeError("Formato de respaldo no admitido.")
    for nombre in nombres:
        if huella(carpeta / nombre) != meta["sha256"][nombre]:
            raise RuntimeError("El respaldo está incompleto o fue modificado.")
    identificador = "ecometrics-recuperacion-" + uuid.uuid4().hex[:12]
    red = identificador + "-red"
    directorio = carpeta / ("recuperacion-" + uuid.uuid4().hex[:8])
    documentos = directorio / "documentos"
    documentos.mkdir(parents=True, exist_ok=False)
    with tarfile.open(carpeta / "documentos.tar.gz", "r:gz") as entrada:
        for miembro in entrada.getmembers():
            destino = (documentos / miembro.name).resolve()
            if not miembro.isfile() or not destino.is_relative_to(documentos.resolve()):
                raise RuntimeError("Entrada no admitida en el archivo de documentos.")
        entrada.extractall(documentos, filter="data")
    entorno = dict(os.environ, POSTGRES_PASSWORD=secrets.token_urlsafe(36), DJANGO_SECRET_KEY=secrets.token_urlsafe(48))
    red_creada = db_creada = False
    try:
        ejecutar("docker", "network", "create", "--internal", red)
        red_creada = True
        ejecutar("docker", "run", "-d", "--name", identificador, "--label", f"ecometrics.recuperacion={identificador}",
            "--network", red, "--tmpfs", "/var/lib/postgresql/data:rw", "-e", "POSTGRES_PASSWORD",
            "-e", "POSTGRES_USER=recuperacion", "-e", "POSTGRES_DB=recuperacion", meta["imagen_db"], env=entorno)
        db_creada = True
        for intento in range(60):
            estado = subprocess.run(["docker", "exec", identificador, "pg_isready", "-h", "127.0.0.1", "-U", "recuperacion", "-d", "recuperacion"], capture_output=True)
            if estado.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("La base aislada no inició a tiempo.")
        ejecutar("docker", "cp", carpeta / "base.dump", f"{identificador}:/tmp/base.dump")
        ejecutar("docker", "exec", identificador, "pg_restore", "--exit-on-error", "--no-owner", "--no-acl", "-U", "recuperacion", "-d", "recuperacion", "/tmp/base.dump")
        argumentos = ["docker", "run", "--rm", "--network", red, "-e", "POSTGRES_PASSWORD", "-e", "DJANGO_SECRET_KEY",
            "-e", "POSTGRES_USER=recuperacion", "-e", "POSTGRES_DB=recuperacion", "-e", f"POSTGRES_HOST={identificador}",
            "-e", "ECOMETRICS_MEDIA_ROOT=/data/evidencias", "--mount", f"type=bind,source={raiz / 'src'},target=/app,readonly",
            "--mount", f"type=bind,source={documentos},target=/data/evidencias,readonly",
            "--mount", f"type=bind,source={carpeta},target=/backup,readonly", meta["imagen_web"], "python", "manage.py"]
        ejecutar(*argumentos, "check", "--database", "default", env=entorno)
        resultado = ejecutar(*argumentos, "comprobar_respaldo", "verificar", "/backup", env=entorno)
        (directorio / "resultado.json").write_text(json.dumps({"verificado_utc": datetime.now(timezone.utc).isoformat(),
            "resultado": "OK", "comprobacion": resultado, "base_aislada": True, "puertos_publicados": False}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(resultado, flush=True)
        print("RESTAURACION_AISLADA=OK", flush=True)
    finally:
        if db_creada:
            etiqueta = ejecutar("docker", "inspect", "--format", '{{index .Config.Labels "ecometrics.recuperacion"}}', identificador)
            if etiqueta != identificador:
                raise RuntimeError("Identidad del contenedor inesperada; limpieza detenida.")
            ejecutar("docker", "stop", identificador)
            ejecutar("docker", "rm", identificador)
        if red_creada:
            ejecutar("docker", "network", "rm", red)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accion", choices=["crear", "verificar"])
    parser.add_argument("--raiz", required=True)
    parser.add_argument("--carpeta", default="")
    args = parser.parse_args()
    raiz = Path(args.raiz).resolve()
    os.chdir(raiz)
    try:
        compose("config", "--quiet")
        if args.accion == "crear":
            if args.carpeta:
                raise RuntimeError("Crear utiliza siempre una carpeta nueva dentro de .private/respaldos.")
            verificar(crear(raiz), raiz)
        else:
            if not args.carpeta:
                raise RuntimeError("Indica la carpeta del respaldo que quieres comprobar.")
            verificar(Path(args.carpeta).resolve(), raiz)
    except Exception as error:
        print(f"COMPROBACION_NO_COMPLETADA: {error}", flush=True)
        raise SystemExit(1)
