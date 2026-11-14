import csv
import io
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cuentas.models import Sede
from .consultas_movimientos import filtrar_retiros, totales_movimientos
from .models import Categoria, EvidenciaRetiro, Pesaje, Retiro


class IntegracionMovimientosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sede = Sede.objects.create(nombre="Sede Álamo")
        cls.otra = Sede.objects.create(nombre="Otra sede")
        cls.gerente = get_user_model().objects.create_user(username="gerencia_reportes", rol="gerente")
        cls.operario = get_user_model().objects.create_user(username="registro_reportes", sede=cls.sede)
        cls.categoria = Categoria.objects.get(clave="plastico")
        cls.vidrio = Categoria.objects.get(clave="vidrio")
        cls.hoy = timezone.localdate()
        cls.salida = cls.hoy - timedelta(days=2)
        cls.generacion = cls.hoy - timedelta(days=10)
        cls.pesaje = Pesaje.objects.create(autor=cls.operario, sede=cls.sede, categoria=cls.categoria,
            peso_kg=Decimal("100.00"), fecha_generacion=cls.generacion, operacion=uuid.uuid4())
        def retiro(peso, confirmado=None, **cambios):
            datos = dict(sede=cls.sede, categoria=cls.categoria, receptor="Gestor Álamo", actor=cls.gerente,
                operacion=uuid.uuid4(), fecha_salida=cls.salida, peso_salida=Decimal(peso),
                peso_confirmado=Decimal(confirmado) if confirmado is not None else None,
                fecha_confirmacion=cls.hoy if confirmado is not None else None)
            datos.update(cambios)
            return Retiro.objects.create(**datos)
        cls.recibido = retiro("20.00", "18.50", estado="observado", documento_ref="GUIA-01")
        cls.pendiente = retiro("30.00")
        cls.cero = retiro("5.00", "0.00", estado="observado")
        cls.anulado = retiro("9.00", "8.00", estado="anulado")
        cls.otro = retiro("10.00", "10.00", sede=cls.otra, categoria=cls.vidrio, estado="conciliado")
        # Solo metadatos aislados: la exportación cuenta respaldos sin abrir archivos.
        for n in range(2):
            EvidenciaRetiro.objects.create(retiro=cls.recibido, archivo=f"retiros/informe-{n}.pdf",
                nombre=f"informe-{n}.pdf", sha256="0" * 64, tipo="application/pdf", tamanio=20, actor=cls.gerente)

    def setUp(self):
        self.client.force_login(self.gerente)

    def filtros(self, **cambios):
        datos = {"sede": self.sede.pk, "categoria": self.categoria.pk}
        datos.update(cambios)
        return datos



    def test_diferencia_solo_confirmados_y_totales_consistentes(self):
        filas = filtrar_retiros({"sede": self.sede, "categoria": self.categoria})
        sql = totales_movimientos(filas)
        self.assertEqual(sql, totales_movimientos(list(filas)))
        self.assertEqual(sql["salida"], Decimal("55.00"))
        self.assertEqual(sql["confirmado"], Decimal("18.50"))
        self.assertEqual(sql["diferencia"], Decimal("-6.50"))
        self.assertEqual((sql["cantidad"], sql["confirmadas"], sql["sin_recepcion"]), (3, 2, 1))

    def test_generacion_por_defecto_conserva_exportacion_anterior(self):
        response = self.client.get(reverse("reportes"), self.filtros())
        self.assertEqual(response.context["tipo"], "generacion")
        self.assertEqual(response.context["totales"]["peso"], Decimal("100.00"))
        self.assertContains(response, reverse("reporte_csv"))
        self.assertEqual(self.client.get(reverse("reporte_csv"), self.filtros()).status_code, 200)

    def test_rutas_retiradas_no_permiten_consulta_ni_escritura(self):
        rutas = ['/gerencia/conciliacion/', '/gerencia/conciliacion/nuevo/',
            f'/gerencia/conciliacion/{self.recibido.pk}/', f'/gerencia/conciliacion/{self.recibido.pk}/recepcion/',
            f'/gerencia/conciliacion/{self.recibido.pk}/accion/', f'/gerencia/conciliacion/{self.recibido.pk}/evidencia/',
            f'/gerencia/conciliacion/evidencias/{EvidenciaRetiro.objects.first().pk}/',
            '/gerencia/reportes/retiros/csv/', '/gerencia/reportes/recepciones/imprimir/']
        for usuario in (self.gerente, self.operario, None):
            self.client.logout()
            if usuario:
                self.client.force_login(usuario)
            for ruta in rutas:
                with self.subTest(usuario=usuario, ruta=ruta):
                    self.assertEqual(self.client.get(ruta).status_code, 404)
                    self.assertEqual(self.client.post(ruta, {'accion':'anular'}).status_code, 404)
        self.assertEqual(Retiro.objects.count(), 5)
        self.assertEqual(EvidenciaRetiro.objects.count(), 2)
        self.recibido.refresh_from_db()
        self.assertEqual(self.recibido.estado, 'observado')

    def test_navegacion_y_dashboard_sin_modulo(self):
        for nombre in ('resumen', 'pesajes_gerencia', 'reportes', 'sedes', 'personal'):
            pagina = self.client.get(reverse(nombre))
            self.assertEqual(pagina.status_code, 200)
            for texto in ('Conciliación', 'Mis salidas', '/gerencia/conciliacion/', 'Salidas registradas', 'Confirmado por el receptor'):
                self.assertNotContains(pagina, texto)
        pagina = self.client.get(reverse('resumen'), self.filtros())
        self.assertEqual(pagina.context['totales']['peso'], Decimal('100.00'))
        self.assertNotIn('salidas', pagina.context)
        self.client.force_login(self.operario)
        for nombre in ('registrar', 'historial'):
            pagina = self.client.get(reverse(nombre))
            self.assertNotContains(pagina, '>Salidas</a>')
            self.assertNotContains(pagina, '/gerencia/conciliacion/')

    def test_reportes_solo_generacion_y_sin_selector(self):
        for tipo in ('retiros', 'recepciones', 'desconocido'):
            parametros = self.filtros(tipo=tipo)
            pagina = self.client.get(reverse('reportes'), parametros)
            self.assertFalse(pagina.context['puede_exportar'])
            self.assertEqual(self.client.get(reverse('reporte_csv'), parametros).status_code, 400)
            self.assertEqual(self.client.get(reverse('reporte_imprimible'), parametros).status_code, 400)
        pagina = self.client.get(reverse('reportes'))
        self.assertNotContains(pagina, 'Tipo de reporte')
        self.assertNotContains(pagina, 'Estado del retiro')
        parametros = self.filtros(tipo='generacion')
        csv_respuesta = self.client.get(reverse('reporte_csv'), parametros)
        filas = list(csv.reader(io.StringIO(csv_respuesta.content.decode('utf-8-sig'))))
        self.assertEqual(filas[1][5], '100.00')
        html = self.client.get(reverse('reporte_imprimible'), parametros)
        self.assertEqual(html.context['total'], Decimal('100.00'))
