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


class Adjuntos(list):
    def all(self):
        return self


retiros = []
for n in range(1, 81):
    peso = None if n % 3 == 0 else Decimal('0.00') if n % 7 == 0 else Decimal('12.25')
    retiros.append(SimpleNamespace(pk=n, sede=SimpleNamespace(nombre='Sede de revisión Norte'), categoria=SimpleNamespace(nombre='Cartón'),
        fecha_salida=date(2026, 10, 28), fecha_confirmacion=date(2026, 10, 29) if peso is not None else None,
        peso_salida=Decimal('12.50'), peso_confirmado=peso, diferencia=peso-Decimal('12.50') if peso is not None else None,
        receptor='Gestor receptor con denominación extensa para revisar el ancho disponible',
        observacion_recepcion=f'RETIRO-{n:04d}: Referencia de revisión y observación extensa para comprobar que las nueve columnas se mantienen legibles.',
        documento_ref=f'GUIA-REVISION-{n:04d}', evidencias=Adjuntos([1, 2]), get_estado_display='Pendiente' if peso is None else 'Observado'))
from residuos.consultas_movimientos import totales_movimientos
for tipo in ('retiros', 'recepciones'):
    filas = retiros if tipo == 'retiros' else [fila for fila in retiros if fila.peso_confirmado is not None]
    guardar(tipo + '-varias-paginas.html', 'residuos/reporte_movimientos.html', dict(comun, tipo=tipo, registros=filas, totales=totales_movimientos(filas)))
print('HTML_IMPRESION_PREPARADO=OK; sin escrituras de negocio')
