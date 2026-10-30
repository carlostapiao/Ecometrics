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

    def csv(self, nombre_tipo, **filtros):
        response = self.client.get(reverse("movimientos_csv", kwargs={"tipo": nombre_tipo}), filtros)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))

    def test_dashboard_fecha_de_cada_indicador_y_anulados_excluidos(self):
        for fecha, generado, salido, recibido in ((self.generacion, "100.00", None, None),
                (self.salida, None, "55.00", None), (self.hoy, None, None, "18.50")):
            with self.subTest(fecha=fecha):
                response = self.client.get(reverse("resumen"), self.filtros(desde=fecha, hasta=fecha))
                self.assertEqual(response.status_code, 200)
                for clave, esperado in (("totales", generado), ("salidas", salido), ("recepciones", recibido)):
                    self.assertEqual(response.context[clave]["peso"], Decimal(esperado) if esperado else None)
        response = self.client.get(reverse("resumen"), self.filtros(desde=self.salida, hasta=self.salida))
        self.assertEqual(response.context["por_revisar"], 3)
        self.assertEqual(response.context["observados"], 2)
        self.assertEqual(response.context["sin_recepcion"], 1)
        self.assertContains(response, "Por fecha de recepción")

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

    def test_centro_csv_html_coinciden_para_salidas_y_recepciones(self):
        for tipo, fecha, peso, cantidad in (("retiros", self.salida, "55.00", 3), ("recepciones", self.hoy, "18.50", 2)):
            with self.subTest(tipo=tipo):
                datos = self.filtros(tipo=tipo, desde=fecha, hasta=fecha)
                centro = self.client.get(reverse("reportes"), datos)
                html = self.client.get(reverse("movimientos_imprimible", kwargs={"tipo": tipo}), datos)
                rows = self.csv(tipo, **datos)[1:]
                self.assertEqual(centro.context["totales"]["peso"], Decimal(peso))
                self.assertEqual(len(rows), cantidad)
                self.assertEqual(html.status_code, 200)
                self.assertEqual(html.context["totales"], centro.context["movimientos"])
                indice = 6 if tipo == "retiros" else 7
                self.assertEqual(sum((Decimal(row[indice]) for row in rows), Decimal(0)), Decimal(peso))
                self.assertEqual(html["Cache-Control"], "private, no-store")

    def test_csv_pendiente_vacio_cero_explicito_y_documentos_no_duplican(self):
        rows = {int(row[0]): row for row in self.csv("retiros", **self.filtros())[1:]}
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[self.pendiente.pk][7:9], ["", ""])
        self.assertEqual(rows[self.cero.pk][7:9], ["0.00", "-5.00"])
        self.assertEqual(rows[self.recibido.pk][7:9], ["18.50", "-1.50"])
        self.assertEqual(rows[self.recibido.pk][11], "2")
        html = self.client.get(reverse("movimientos_imprimible", kwargs={"tipo": "retiros"}), self.filtros())
        self.assertContains(html, "Pendiente")
        self.assertContains(html, "0,00")
        self.assertNotContains(html, "retiros/informe-")

    def test_filtros_estado_sede_categoria_y_limites_inclusivos(self):
        rows = self.csv("retiros", **self.filtros(estado="observado", desde=self.salida, hasta=self.salida))
        self.assertEqual({int(row[0]) for row in rows[1:]}, {self.recibido.pk, self.cero.pk})
        rows = self.csv("recepciones", sede=self.otra.pk, categoria=self.vidrio.pk, estado="conciliado")
        self.assertEqual([int(row[0]) for row in rows[1:]], [self.otro.pk])

    def test_sin_resultados_no_convierte_pendientes_en_diferencia(self):
        rows = self.csv("recepciones", **self.filtros(desde=self.salida, hasta=self.salida))
        self.assertEqual(len(rows), 1)
        html = self.client.get(reverse("movimientos_imprimible", kwargs={"tipo": "retiros"}), self.filtros(estado="pendiente"))
        self.assertContains(html, "Sin recepciones")
        self.assertEqual(html.context["totales"]["confirmadas"], 0)

    def test_filtros_invalidos_no_permiten_exportar(self):
        for cambios in ({"tipo": "desconocido"}, {"sede": "no"}, {"sede": "999999"},
                {"categoria": "999999"}, {"estado": "anulado"}, {"desde": "ayer"},
                {"desde": self.hoy, "hasta": self.salida}):
            with self.subTest(cambios=cambios):
                datos = self.filtros(tipo="retiros")
                datos.update(cambios)
                centro = self.client.get(reverse("reportes"), datos)
                self.assertFalse(centro.context["puede_exportar"])
                self.assertNotContains(centro, ">Descargar CSV</a>")
                self.assertEqual(self.client.get(reverse("movimientos_csv", kwargs={"tipo": "retiros"}), datos).status_code, 400)
        self.assertEqual(self.client.get(reverse("reporte_csv"), {"estado": "observado"}).status_code, 400)

    def test_no_acepta_tipo_contradictorio_y_rutas_desconocidas(self):
        self.assertEqual(self.client.get(reverse("movimientos_imprimible", kwargs={"tipo": "retiros"}), {"tipo": "recepciones"}).status_code, 400)
        self.assertEqual(self.client.get(reverse("movimientos_csv", kwargs={"tipo": "otro"})).status_code, 404)

    def test_csv_neutraliza_formulas_y_html_escapa_contenido(self):
        self.recibido.receptor = '=HYPERLINK("url")'
        self.recibido.documento_ref = "+SUM(1,1)"
        self.recibido.observacion_recepcion = "<script>alert(1)</script>"
        self.recibido.save()
        rows = {int(row[0]): row for row in self.csv("retiros", **self.filtros())[1:]}
        self.assertTrue(rows[self.recibido.pk][5].startswith("'="))
        self.assertTrue(rows[self.recibido.pk][10].startswith("'+"))
        html = self.client.get(reverse("movimientos_imprimible", kwargs={"tipo": "retiros"}), self.filtros())
        self.assertNotContains(html, "<script>alert(1)</script>")
        self.assertContains(html, "&lt;script&gt;")

    def test_exportaciones_solo_gerencia_y_solo_lectura(self):
        for nombre in ("movimientos_csv", "movimientos_imprimible"):
            url = reverse(nombre, kwargs={"tipo": "retiros"})
            self.assertEqual(self.client.post(url).status_code, 405)
            self.client.force_login(self.operario)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(self.gerente)
