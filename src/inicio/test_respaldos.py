import hashlib
import json
from pathlib import Path
import tarfile
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from cuentas.models import Sede, Usuario
from residuos.models import Categoria, EvidenciaRetiro, Retiro


_LOCAL_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


class RespaldoTests(TestCase):
    def test_archivo_binario_y_tablas_en_inventario_sin_exponer_filas(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            media = raiz / 'media'
            media.mkdir()
            (media / 'archivo.bin').write_bytes(b'\x00\xffcontenido\x00')
            with override_settings(MEDIA_ROOT=media, STORAGES=_LOCAL_STORAGES):
                call_command('comprobar_respaldo', 'crear', str(raiz))
                inventario = json.loads((raiz / 'inventario.json').read_text(encoding='utf-8'))
                self.assertIn('cuentas_usuario', inventario['tablas'])
                self.assertEqual(inventario['archivos']['archivo.bin']['sha256'], hashlib.sha256(b'\x00\xffcontenido\x00').hexdigest())
                with tarfile.open(raiz / 'documentos.tar.gz') as archivo:
                    self.assertEqual(archivo.extractfile('archivo.bin').read(), b'\x00\xffcontenido\x00')
                call_command('comprobar_respaldo', 'verificar', str(raiz))
                (media / 'archivo.bin').write_bytes(b'alterado')
                with self.assertRaises(CommandError):
                    call_command('comprobar_respaldo', 'verificar', str(raiz))

    def test_documento_referenciado_ausente_no_produce_respaldo_valido(self):
        import uuid
        from datetime import date
        sede = Sede.objects.create(nombre='Respaldo')
        usuario = Usuario.objects.create(username='responsable_respaldo', rol='gerente')
        retiro = Retiro.objects.create(sede=sede, categoria=Categoria.objects.get(clave='plastico'), receptor='Receptor',
            fecha_salida=date(2026, 10, 29), peso_salida='1.00', actor=usuario, operacion=uuid.uuid4())
        EvidenciaRetiro.objects.create(retiro=retiro, archivo='ausente.pdf', nombre='ausente.pdf', sha256='0'*64, tamanio=10, tipo='application/pdf', actor=usuario)
        with tempfile.TemporaryDirectory() as temporal, override_settings(MEDIA_ROOT=temporal, STORAGES=_LOCAL_STORAGES):
            with self.assertRaises(CommandError):
                call_command('comprobar_respaldo', 'crear', temporal)
            self.assertFalse((Path(temporal) / 'inventario.json').exists())

    def test_destino_existente_no_se_sobrescribe(self):
        with tempfile.TemporaryDirectory() as temporal, override_settings(MEDIA_ROOT=Path(temporal) / 'media', STORAGES=_LOCAL_STORAGES):
            ruta = Path(temporal) / 'inventario.json'
            ruta.write_text('conservar', encoding='utf-8')
            with self.assertRaises(CommandError):
                call_command('comprobar_respaldo', 'crear', temporal)
            self.assertEqual(ruta.read_text(encoding='utf-8'), 'conservar')
