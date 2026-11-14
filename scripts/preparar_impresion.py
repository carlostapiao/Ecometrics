"""Se ejecuta con manage.py shell. No escribe registros en la base de datos."""
from datetime import date
from decimal import Decimal
from pathlib import Path
import re
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import RequestFactory
from django.utils import timezone
from cuentas.models import Usuario

destino = Path('/tmp/ecometrics-revision-impresion')
destino.mkdir(exist_ok=True)
request = RequestFactory().get('/gerencia/reportes/')
request.user = Usuario(username='revision_impresion', first_name='Revisión de impresión', rol='gerente')


def guardar(nombre, plantilla, contexto):
    contenido = render_to_string(plantilla, contexto, request=request)
    def estilo(match):
        return '<style>' + (Path('/app/static') / match.group(1)).read_text(encoding='utf-8') + '</style>'
    contenido = re.sub(r'<link rel="stylesheet" href="/static/([^"/]+)">', estilo, contenido)
    (destino / nombre).write_text(contenido, encoding='utf-8')


pesajes = [SimpleNamespace(pk=n, fecha_generacion=date(2026, 10, 29), sede=SimpleNamespace(nombre='Sede de revisión Norte'),
    categoria=SimpleNamespace(nombre='Plástico'), autor=request.user, peso_kg=Decimal('12.50'),
    observacion=f'FILA-{n:04d}: Observación extensa para comprobar el ajuste de texto dentro de la última columna del reporte, sin recortar el contenido.') for n in range(1, 121)]
comun = dict(emitido_en=timezone.localtime(), filtros={}, parametros='', seccion='reportes')
guardar('generacion-120-filas.html', 'residuos/reporte.html', dict(comun, registros=pesajes, total=Decimal('1500.00'), cantidad=120))

print('HTML_IMPRESION_PREPARADO=OK; solo generación; sin escrituras de negocio')
