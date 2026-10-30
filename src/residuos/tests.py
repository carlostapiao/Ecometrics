import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from cuentas.models import Sede
from .forms import nueva_operacion
from .models import Categoria, EventoPesaje, Pesaje
from .services import registrar_pesaje


class FlujoPesajeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.norte = Sede.objects.create(nombre="Norte")
        cls.sur = Sede.objects.create(nombre="Sur")
        cls.uno = get_user_model().objects.create_user("uno", password="Prueba-aislada-2026!", sede=cls.norte)
        cls.dos = get_user_model().objects.create_user("dos", password="Prueba-aislada-2026!", sede=cls.norte)
        cls.tres = get_user_model().objects.create_user("tres", password="Prueba-aislada-2026!", sede=cls.sur)
        cls.gerente = get_user_model().objects.create_user("gerente", password="Prueba-aislada-2026!", rol="gerente")
        cls.categoria = Categoria.objects.get(clave="plastico")

    def setUp(self):
        self.client.force_login(self.uno)

    def datos(self, **cambios):
        datos = {"categoria": str(self.categoria.pk), "peso_kg": "12.50", "fecha_generacion": timezone.localdate().isoformat(), "observacion": "Referencia de prueba", "operacion": nueva_operacion(self.uno)}
        datos.update(cambios)
        return datos

    def crear(self, **cambios):
        respuesta = self.client.post(reverse("registrar"), self.datos(**cambios))
        self.assertEqual(respuesta.status_code, 302)
        return Pesaje.objects.latest("pk")

    def test_catalogo_solo_categorias_acordadas(self):
        self.assertSetEqual(set(Categoria.objects.values_list("clave", flat=True)), {"no-reciclable", "plastico", "carton", "vidrio", "metal", "organico"})

    def test_captura_decimal_y_evento_con_autor_y_sede_servidor(self):
        datos = self.datos(autor=self.dos.pk, sede=self.sur.pk)
        respuesta = self.client.post(reverse("registrar"), datos)
        self.assertEqual(respuesta.status_code, 302)
        pesaje = Pesaje.objects.get()
        self.assertEqual((pesaje.peso_kg, pesaje.autor_id, pesaje.sede_id), (Decimal("12.50"), self.uno.pk, self.norte.pk))
        evento = pesaje.eventos.get()
        self.assertEqual(evento.actor_id, self.uno.pk)
        self.assertEqual(evento.datos["peso_kg"], "12.50")

    def test_acepta_coma_decimal(self):
        self.assertEqual(self.crear(peso_kg="12,50").peso_kg, Decimal("12.50"))

    def test_rechaza_pesos_invalidos_sin_mutar(self):
        for peso in ("0", "-1", "12.501", "NaN", "1,000", "1.2.3", "10000000", "1e2", ""):
            with self.subTest(peso=peso):
                self.assertEqual(self.client.post(reverse("registrar"), self.datos(peso_kg=peso)).status_code, 400)
        self.assertFalse(Pesaje.objects.exists())

    def test_rechaza_fecha_futura_y_categoria_ajena(self):
        for cambios in ({"fecha_generacion": (timezone.localdate() + timedelta(days=1)).isoformat()}, {"categoria": "999999"}):
            self.assertEqual(self.client.post(reverse("registrar"), self.datos(**cambios)).status_code, 400)
        self.assertFalse(Pesaje.objects.exists())

    def test_reintento_no_duplica_pesaje_ni_evento(self):
        datos = self.datos()
        primera = self.client.post(reverse("registrar"), datos)
        segunda = self.client.post(reverse("registrar"), datos)
        self.assertEqual(primera.url, segunda.url)
        self.assertEqual((Pesaje.objects.count(), EventoPesaje.objects.count()), (1, 1))

    def test_reutilizacion_operacion_con_otro_contenido_se_rechaza(self):
        datos = self.datos()
        self.client.post(reverse("registrar"), datos)
        datos["peso_kg"] = "99"
        self.assertEqual(self.client.post(reverse("registrar"), datos).status_code, 400)
        self.assertEqual(Pesaje.objects.get().peso_kg, Decimal("12.50"))

    def test_firma_alterada_y_firma_de_otro_usuario(self):
        for clave in ("inventada", nueva_operacion(self.dos)):
            self.assertEqual(self.client.post(reverse("registrar"), self.datos(operacion=clave)).status_code, 400)
        self.assertFalse(Pesaje.objects.exists())

    def test_historial_y_detalle_privados_en_misma_y_otra_sede(self):
        registro = self.crear()
        for otro in (self.dos, self.tres):
            self.client.force_login(otro)
            self.assertNotContains(self.client.get(reverse("historial")), "Referencia de prueba")
            self.assertEqual(self.client.get(reverse("detalle_pesaje", args=[registro.pk])).status_code, 404)
            self.assertEqual(self.client.get(reverse("historial"), {"autor": self.uno.pk}).context["totales"]["cantidad"], 0)

    def test_historial_conserva_sede_historica(self):
        registro = self.crear()
        self.uno.sede = self.sur
        self.uno.save(update_fields=["sede"])
        self.assertContains(self.client.get(reverse("historial")), "Norte")
        self.assertEqual(self.client.get(reverse("detalle_pesaje", args=[registro.pk])).status_code, 200)

    def test_filtros_fechas_inclusivas_y_categoria(self):
        self.crear()
        hoy = timezone.localdate().isoformat()
        self.assertEqual(self.client.get(reverse("historial"), {"desde": hoy, "hasta": hoy}).context["totales"]["peso"], Decimal("12.50"))
        otra = Categoria.objects.exclude(pk=self.categoria.pk).first()
        self.assertEqual(self.client.get(reverse("historial"), {"categoria": otra.pk}).context["totales"]["cantidad"], 0)
        self.assertEqual(self.client.get(reverse("historial"), {"desde": "invalida"}).context["totales"]["cantidad"], 0)

    def test_roles_se_verifican_en_servidor(self):
        self.assertEqual(self.client.get(reverse("resumen")).status_code, 403)
        self.client.force_login(self.gerente)
        self.assertEqual(self.client.get(reverse("registrar")).status_code, 403)
        self.assertEqual(self.client.get(reverse("historial")).status_code, 403)

    def test_resumen_gerencial_suma_real_multisede(self):
        self.crear()
        self.client.force_login(self.tres)
        self.client.post(reverse("registrar"), self.datos(peso_kg="7.25", operacion=nueva_operacion(self.tres)))
        self.client.force_login(self.gerente)
        respuesta = self.client.get(reverse("resumen"))
        self.assertEqual(respuesta.context["totales"]["peso"], Decimal("19.75"))
        self.assertEqual(len(respuesta.context["por_sede"]), 2)
        self.assertEqual(self.client.get(reverse("resumen"), {"sede": self.sur.pk}).context["totales"]["peso"], Decimal("7.25"))

    def test_sede_inactiva_bloquea_escritura_y_lectura(self):
        self.norte.activa = False
        self.norte.save()
        self.assertEqual(self.client.post(reverse("registrar"), self.datos()).status_code, 403)
        self.assertEqual(self.client.get(reverse("historial")).status_code, 403)

    def test_csrf_requerido_para_guardar_y_salir(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.uno)
        self.assertEqual(cliente.post(reverse("registrar"), self.datos()).status_code, 403)
        self.assertEqual(cliente.post(reverse("logout")).status_code, 403)
        self.assertEqual(cliente.get(reverse("logout")).status_code, 405)

    def test_observacion_se_escapa(self):
        registro = self.crear(observacion="<script>alert(1)</script>")
        respuesta = self.client.get(reverse("detalle_pesaje", args=[registro.pk]))
        self.assertContains(respuesta, "&lt;script&gt;")
        self.assertNotContains(respuesta, "<script>")

    def test_fallo_de_auditoria_revierte_pesaje(self):
        datos = {"categoria": self.categoria, "peso_kg": Decimal("12.50"), "fecha_generacion": timezone.localdate(), "observacion": "", "operacion": uuid.uuid4()}
        with patch("residuos.services.EventoPesaje.objects.create", side_effect=RuntimeError("fallo")):
            with self.assertRaises(RuntimeError):
                registrar_pesaje(self.uno, datos)
        self.assertFalse(Pesaje.objects.exists())

    def test_restriccion_peso_en_base(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Pesaje.objects.create(autor=self.uno, sede=self.norte, categoria=self.categoria, peso_kg=0, fecha_generacion=timezone.localdate(), operacion=uuid.uuid4())

    def test_login_real_redirige_por_rol_y_rechaza_clave_incorrecta(self):
        self.client.logout()
        respuesta = self.client.post(reverse("login"), {"username": "uno", "password": "incorrecta"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        respuesta = self.client.post(reverse("login"), {"username": "uno", "password": "Prueba-aislada-2026!", "rol": "gerente", "next": "https://ajeno.invalid"})
        self.assertRedirects(respuesta, reverse("registrar"))
        self.client.post(reverse("logout"))
        respuesta = self.client.post(reverse("login"), {"username": "gerente", "password": "Prueba-aislada-2026!"})
        self.assertRedirects(respuesta, reverse("resumen"))

    def test_login_cuenta_inactiva_o_sin_sede_se_rechaza(self):
        self.client.logout()
        self.uno.is_active = False
        self.uno.save()
        self.client.post(reverse("login"), {"username": "uno", "password": "Prueba-aislada-2026!"})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.dos.sede = None
        self.dos.save()
        self.client.post(reverse("login"), {"username": "dos", "password": "Prueba-aislada-2026!"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_acceso_anonimo_no_expone_registros(self):
        registro = self.crear()
        self.client.logout()
        for ruta in (reverse("registrar"), reverse("historial"), reverse("resumen"), reverse("detalle_pesaje", args=[registro.pk])):
            self.assertEqual(self.client.get(ruta).status_code, 302)


class CambiosGerencialesTests(TestCase):
    setUpTestData = classmethod(FlujoPesajeTests.setUpTestData.__func__)
    datos = FlujoPesajeTests.datos
    crear = FlujoPesajeTests.crear

    def setUp(self):
        self.client.force_login(self.uno)
        self.pesaje = self.crear()
        self.client.force_login(self.gerente)

    def correccion(self, **cambios):
        datos = {"categoria": self.categoria.pk, "peso_kg": "10.25", "fecha_generacion": timezone.localdate().isoformat(),
                 "observacion": "Peso corregido", "motivo": "Error de digitación", "version": self.pesaje.version}
        datos.update(cambios)
        return datos

    def test_correccion_conserva_origen_y_reconstruye_cambio(self):
        respuesta = self.client.post(reverse("corregir_pesaje", args=[self.pesaje.pk]), self.correccion(autor=self.dos.pk, sede=self.sur.pk))
        self.assertEqual(respuesta.status_code, 302)
        self.pesaje.refresh_from_db()
        self.assertEqual((self.pesaje.peso_kg, self.pesaje.autor_id, self.pesaje.sede_id, self.pesaje.version), (Decimal("10.25"), self.uno.pk, self.norte.pk, 2))
        evento = self.pesaje.eventos.get(accion="correccion")
        self.assertEqual(evento.actor_id, self.gerente.pk)
        self.assertEqual(evento.motivo, "Error de digitación")
        self.assertEqual(evento.datos["antes"]["peso_kg"], "12.50")
        self.assertEqual(evento.datos["despues"]["peso_kg"], "10.25")
        self.assertContains(self.client.get(reverse("detalle_pesaje", args=[self.pesaje.pk])), "Error de digitación")

    def test_motivo_obligatorio_y_precision_en_correccion(self):
        for cambios in ({"motivo": "  "}, {"peso_kg": "1.235"}, {"fecha_generacion": (timezone.localdate() + timedelta(days=1)).isoformat()}):
            self.assertEqual(self.client.post(reverse("corregir_pesaje", args=[self.pesaje.pk]), self.correccion(**cambios)).status_code, 400)
        self.pesaje.refresh_from_db()
        self.assertEqual(self.pesaje.version, 1)
        self.assertEqual(self.pesaje.eventos.count(), 1)

    def test_operario_no_corrige_ni_anula_incluso_propio(self):
        self.client.force_login(self.uno)
        for nombre in ("corregir_pesaje", "anular_pesaje"):
            self.assertEqual(self.client.get(reverse(nombre, args=[self.pesaje.pk])).status_code, 403)
            self.assertEqual(self.client.post(reverse(nombre, args=[self.pesaje.pk]), self.correccion(confirmar="on")).status_code, 403)

    def test_anulacion_conserva_historia_y_excluye_metricas(self):
        ruta = reverse("anular_pesaje", args=[self.pesaje.pk])
        self.assertEqual(self.client.get(ruta).status_code, 200)
        self.pesaje.refresh_from_db()
        self.assertFalse(self.pesaje.anulado)
        self.assertEqual(self.client.post(ruta, {"version": 1, "motivo": "Registro duplicado"}).status_code, 400)
        self.assertEqual(self.client.post(ruta, {"version": 1, "motivo": "Registro duplicado", "confirmar": "on"}).status_code, 302)
        self.pesaje.refresh_from_db()
        self.assertTrue(self.pesaje.anulado)
        evento = self.pesaje.eventos.get(accion="anulacion")
        self.assertFalse(evento.datos["antes"]["anulado"])
        self.assertTrue(evento.datos["despues"]["anulado"])
        respuesta = self.client.get(reverse("resumen"))
        self.assertEqual(respuesta.context["totales"]["cantidad"], 0)
        self.assertEqual(respuesta.context["anulados"], 1)
        self.assertEqual(list(respuesta.context["por_categoria"]), [])
        self.assertEqual(respuesta.context["por_dia"], [])
        self.client.force_login(self.uno)
        respuesta = self.client.get(reverse("historial"))
        self.assertContains(respuesta, "Anulado")
        self.assertEqual(respuesta.context["totales"]["cantidad"], 0)
        self.assertEqual(self.client.get(reverse("detalle_pesaje", args=[self.pesaje.pk])).status_code, 200)

    def test_version_obsoleta_no_sobrescribe_ni_duplica_eventos(self):
        ruta = reverse("corregir_pesaje", args=[self.pesaje.pk])
        self.client.post(ruta, self.correccion())
        self.assertEqual(self.client.post(ruta, self.correccion(peso_kg="99")).status_code, 400)
        self.assertEqual(self.client.post(reverse("anular_pesaje", args=[self.pesaje.pk]), {"version": 1, "motivo": "Antiguo", "confirmar": "on"}).status_code, 400)
        self.pesaje.refresh_from_db()
        self.assertEqual(self.pesaje.peso_kg, Decimal("10.25"))
        self.assertFalse(self.pesaje.anulado)
        self.assertEqual(self.pesaje.eventos.count(), 2)

    def test_anulado_no_admite_edicion_ni_repetir_anulacion(self):
        ruta = reverse("anular_pesaje", args=[self.pesaje.pk])
        self.client.post(ruta, {"version": 1, "motivo": "Prueba", "confirmar": "on"})
        self.assertEqual(self.client.post(ruta, {"version": 2, "motivo": "Otra vez", "confirmar": "on"}).status_code, 400)
        self.assertEqual(self.client.post(reverse("corregir_pesaje", args=[self.pesaje.pk]), self.correccion(version=2)).status_code, 400)
        self.assertEqual(self.pesaje.eventos.count(), 2)

    def test_fallo_evento_revierte_correccion(self):
        with patch("residuos.services.EventoPesaje.objects.create", side_effect=RuntimeError("fallo")):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("corregir_pesaje", args=[self.pesaje.pk]), self.correccion())
        self.pesaje.refresh_from_db()
        self.assertEqual((self.pesaje.peso_kg, self.pesaje.version), (Decimal("12.50"), 1))

    def test_dashboard_categoria_dias_filtros_y_correccion(self):
        self.client.post(reverse("corregir_pesaje", args=[self.pesaje.pk]), self.correccion())
        self.client.force_login(self.tres)
        ayer = timezone.localdate() - timedelta(days=1)
        organico = Categoria.objects.get(clave="organico")
        self.client.post(reverse("registrar"), self.datos(categoria=organico.pk, peso_kg="7.25", fecha_generacion=ayer.isoformat(), operacion=nueva_operacion(self.tres)))
        self.client.force_login(self.gerente)
        respuesta = self.client.get(reverse("resumen"))
        self.assertEqual(respuesta.context["totales"]["peso"], Decimal("17.50"))
        self.assertEqual([x["peso"] for x in respuesta.context["por_dia"]], [Decimal("7.25"), Decimal("10.25")])
        self.assertEqual(sum(x["peso"] for x in respuesta.context["por_categoria"]), Decimal("17.50"))
        respuesta = self.client.get(reverse("resumen"), {"sede": self.sur.pk, "categoria": organico.pk, "desde": ayer.isoformat(), "hasta": ayer.isoformat()})
        self.assertEqual(respuesta.context["totales"]["peso"], Decimal("7.25"))
        self.assertEqual(len(respuesta.context["por_dia"]), 1)

    def test_cambios_requieren_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.gerente)
        for nombre in ("corregir_pesaje", "anular_pesaje"):
            self.assertEqual(cliente.post(reverse(nombre, args=[self.pesaje.pk]), self.correccion(confirmar="on")).status_code, 403)


class ReportesTests(TestCase):
    setUpTestData = classmethod(FlujoPesajeTests.setUpTestData.__func__)
    datos = FlujoPesajeTests.datos
    crear = FlujoPesajeTests.crear

    def setUp(self):
        self.client.force_login(self.uno)
        self.registro = self.crear()
        self.client.force_login(self.gerente)

    def filas_csv(self, respuesta):
        import csv
        import io
        return list(csv.reader(io.StringIO(respuesta.content.decode("utf-8-sig"))))

    def test_reportes_solo_gerenciales(self):
        for nombre in ("reporte_csv", "reporte_imprimible"):
            ruta = reverse(nombre)
            self.client.force_login(self.uno)
            self.assertEqual(self.client.get(ruta).status_code, 403)
            self.client.logout()
            self.assertEqual(self.client.get(ruta).status_code, 302)
            self.client.force_login(self.gerente)
            self.assertEqual(self.client.post(ruta).status_code, 405)

    def test_csv_utf8_dos_decimales_y_formato_descarga(self):
        respuesta = self.client.get(reverse("reporte_csv"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.content.startswith(b"\xef\xbb\xbf"))
        self.assertIn("attachment", respuesta["Content-Disposition"])
        self.assertEqual(respuesta["Cache-Control"], "private, no-store")
        filas = self.filas_csv(respuesta)
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[1][5], "12.50")
        self.assertEqual(filas[1][2:5], ["Norte", "Plástico", "uno"])

    def test_csv_neutraliza_formulas_y_conserva_comillas_saltos(self):
        from .views import texto_csv_seguro
        for texto in ("=1+1", " +CMD()", "-1+2", "@SUM(A1)", "\tvalor", "\n=1"):
            self.assertTrue(texto_csv_seguro(texto).startswith("'"))
        self.registro.observacion = '=HYPERLINK("url", "texto")\nsegunda línea'
        self.registro.save(update_fields=["observacion"])
        filas = self.filas_csv(self.client.get(reverse("reporte_csv")))
        self.assertEqual(filas[1][6], "'" + self.registro.observacion)

    def test_reportes_respetan_correccion_y_anulacion(self):
        self.client.post(reverse("corregir_pesaje", args=[self.registro.pk]), {"categoria": self.categoria.pk, "peso_kg": "8.75", "fecha_generacion": timezone.localdate().isoformat(), "observacion": "", "motivo": "Corregido", "version": 1})
        self.assertEqual(self.filas_csv(self.client.get(reverse("reporte_csv")))[1][5], "8.75")
        self.client.post(reverse("anular_pesaje", args=[self.registro.pk]), {"motivo": "Anulado", "version": 2, "confirmar": "on"})
        self.assertEqual(len(self.filas_csv(self.client.get(reverse("reporte_csv")))), 1)
        respuesta = self.client.get(reverse("reporte_imprimible"))
        self.assertEqual(respuesta.context["total"], Decimal("0.00"))
        self.assertEqual(respuesta.context["cantidad"], 0)
        self.assertContains(respuesta, "No hay pesajes vigentes")

    def test_filtros_coinciden_entre_dashboard_csv_e_impresion(self):
        self.client.force_login(self.tres)
        ayer = timezone.localdate() - timedelta(days=1)
        self.client.post(reverse("registrar"), self.datos(peso_kg="7.25", fecha_generacion=ayer.isoformat(), operacion=nueva_operacion(self.tres)))
        self.client.force_login(self.gerente)
        filtros = {"sede": self.sur.pk, "categoria": self.categoria.pk, "desde": ayer.isoformat(), "hasta": ayer.isoformat()}
        resumen = self.client.get(reverse("resumen"), filtros)
        reporte = self.client.get(reverse("reporte_imprimible"), filtros)
        filas = self.filas_csv(self.client.get(reverse("reporte_csv"), filtros))
        self.assertEqual(reporte.context["total"], resumen.context["totales"]["peso"])
        self.assertEqual(reporte.context["total"], Decimal("7.25"))
        self.assertEqual(reporte.context["cantidad"], len(filas)-1)
        self.assertEqual(filas[1][2], "Sur")
        self.assertContains(reporte, "reporte.css")
        self.assertContains(reporte, "window.print()")

    def test_filtros_invalidos_no_exportan_datos(self):
        for parametros in ({"desde": "no-fecha"}, {"categoria": 999999}, {"sede": "invalida"}, {"desde": "2026-10-28", "hasta": "2026-10-01"}):
            for nombre in ("reporte_csv", "reporte_imprimible"):
                self.assertEqual(self.client.get(reverse(nombre), parametros).status_code, 400)

    def test_html_escapa_observaciones_y_exporta_mas_de_diez(self):
        self.registro.observacion = "<script>alert(1)</script>"
        self.registro.save(update_fields=["observacion"])
        for _ in range(11):
            Pesaje.objects.create(autor=self.uno, sede=self.norte, categoria=self.categoria, peso_kg=Decimal("1.00"), fecha_generacion=timezone.localdate(), operacion=uuid.uuid4())
        respuesta = self.client.get(reverse("reporte_imprimible"))
        self.assertEqual(respuesta.context["cantidad"], 12)
        self.assertEqual(respuesta.context["total"], Decimal("23.50"))
        self.assertContains(respuesta, "&lt;script&gt;")
        self.assertNotContains(respuesta, "<script>")
        self.assertEqual(len(self.filas_csv(self.client.get(reverse("reporte_csv")))), 13)


class ModulosGerencialesTests(TestCase):
    setUpTestData = classmethod(FlujoPesajeTests.setUpTestData.__func__)
    datos = FlujoPesajeTests.datos
    crear = FlujoPesajeTests.crear

    def setUp(self):
        self.client.force_login(self.uno)
        self.registro = self.crear(observacion="Carga del turno mañana")
        self.client.force_login(self.gerente)

    def test_dashboard_pesajes_y_reportes_separan_sus_tareas(self):
        dashboard = self.client.get(reverse("resumen"))
        self.assertContains(dashboard, "Dashboard")
        self.assertNotContains(dashboard, "Descargar CSV")
        self.assertNotContains(dashboard, "Últimos registros")
        listado = self.client.get(reverse("pesajes_gerencia"))
        self.assertContains(listado, "Registro #" + str(self.registro.pk))
        self.assertNotContains(listado, "Evolución diaria")
        reportes = self.client.get(reverse("reportes"))
        self.assertContains(reportes, "Descargar CSV")
        self.assertEqual(reportes.context["totales"]["peso"], Decimal("12.50"))
        for respuesta, seccion in ((dashboard, "dashboard"), (listado, "pesajes"), (reportes, "reportes")):
            self.assertEqual(respuesta.context["seccion"], seccion)
            self.assertContains(respuesta, 'aria-current="page"')

    def test_modulos_exclusivos_del_gerente(self):
        for ruta in (reverse("pesajes_gerencia"), reverse("reportes")):
            self.client.force_login(self.uno)
            self.assertEqual(self.client.get(ruta).status_code, 403)
            self.client.logout()
            self.assertEqual(self.client.get(ruta).status_code, 302)
            self.client.force_login(self.gerente)
            self.assertEqual(self.client.post(ruta).status_code, 405)

    def test_busqueda_por_numero_nombre_y_observacion(self):
        for texto in (str(self.registro.pk), "uno", "turno mañana"):
            respuesta = self.client.get(reverse("pesajes_gerencia"), {"buscar": texto})
            self.assertEqual(list(respuesta.context["pagina"]), [self.registro])
        self.assertEqual(self.client.get(reverse("pesajes_gerencia"), {"buscar": "inexistente"}).context["cantidad"], 0)
        self.assertEqual(self.client.get(reverse("pesajes_gerencia"), {"buscar": "x" * 101}).context["cantidad"], 0)

    def test_paginacion_conserva_busqueda_y_estado(self):
        for _ in range(16):
            Pesaje.objects.create(autor=self.uno, sede=self.norte, categoria=self.categoria, peso_kg=Decimal("1.00"), fecha_generacion=timezone.localdate(), observacion="Turno mañana", operacion=uuid.uuid4())
        respuesta = self.client.get(reverse("pesajes_gerencia"), {"buscar": "mañana", "estado": "vigente", "page": 2})
        self.assertEqual(respuesta.context["cantidad"], 17)
        self.assertEqual(len(respuesta.context["pagina"]), 2)
        self.assertIn("buscar=ma%C3%B1ana", respuesta.context["parametros"])
        self.assertIn("estado=vigente", respuesta.context["parametros"])
        self.assertNotIn("page=", respuesta.context["parametros"])

    def test_filtrar_anulados_conserva_historia_y_no_suma(self):
        self.client.post(reverse("anular_pesaje", args=[self.registro.pk]), {"version": 1, "motivo": "Duplicado", "confirmar": "on"})
        respuesta = self.client.get(reverse("pesajes_gerencia"), {"estado": "anulado"})
        self.assertEqual(respuesta.context["cantidad"], 1)
        self.assertEqual(respuesta.context["totales"]["cantidad"], 0)
        self.assertContains(respuesta, "Anulado · No suma")
        self.assertEqual(self.client.get(reverse("pesajes_gerencia"), {"estado": "vigente"}).context["cantidad"], 0)

    def test_filtros_compartidos_y_errores_no_muestran_datos(self):
        filtros = {"sede": self.norte.pk, "categoria": self.categoria.pk, "desde": timezone.localdate().isoformat(), "hasta": timezone.localdate().isoformat()}
        for nombre in ("resumen", "pesajes_gerencia", "reportes"):
            respuesta = self.client.get(reverse(nombre), filtros)
            self.assertEqual(respuesta.context["totales"]["peso"], Decimal("12.50"))
        for parametros in ({"sede": "invalida"}, {"categoria": "99999"}, {"desde": "no-fecha"}):
            for nombre in ("pesajes_gerencia", "reportes"):
                respuesta = self.client.get(reverse(nombre), parametros)
                self.assertEqual(respuesta.context["totales"]["cantidad"], 0)
                if nombre == "reportes":
                    self.assertFalse(respuesta.context["puede_exportar"])
                    self.assertNotContains(respuesta, "Descargar CSV")

    def test_textos_del_sistema_sin_etiquetas_academicas(self):
        rutas = [reverse("login"), reverse("resumen"), reverse("pesajes_gerencia"), reverse("reportes"), reverse("reporte_imprimible")]
        for ruta in rutas:
            respuesta = self.client.get(ruta, follow=True)
            for etiqueta in ("Datos ficticios", "Demostración", "Proyecto académico"):
                self.assertNotContains(respuesta, etiqueta)
        self.client.logout()
        respuesta = self.client.get(reverse("login"))
        self.assertNotContains(respuesta, "Datos ficticios")

    def test_operario_conserva_captura_e_historial(self):
        self.client.force_login(self.uno)
        self.assertContains(self.client.get(reverse("registrar")), "Guardar pesaje")
        self.assertContains(self.client.get(reverse("historial")), "Mi historial")
        self.assertNotContains(self.client.get(reverse("historial")), "Menú ·")
        self.assertEqual(self.client.get(reverse("detalle_pesaje", args=[self.registro.pk])).status_code, 200)
