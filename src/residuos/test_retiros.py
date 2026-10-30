import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cuentas.models import Sede
from .models import AsignacionRetiro, Categoria, EventoRetiro, EvidenciaRetiro, Pesaje, Retiro
from .retiros_forms import RetiroForm
from .retiros_services import adjuntar_evidencia, confirmar_recepcion, crear_retiro, pesajes_disponibles, resolver_retiro, validar_archivo
from .services import modificar_pesaje


class RetirosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sede = Sede.objects.create(nombre="Origen")
        cls.otra_sede = Sede.objects.create(nombre="Otro origen")
        cls.gerente = get_user_model().objects.create_user(username="gestion", rol="gerente")
        cls.operario = get_user_model().objects.create_user(username="registro", sede=cls.sede)
        cls.categoria = Categoria.objects.get(clave="plastico")
        cls.otro_material = Categoria.objects.get(clave="vidrio")
        cls.pesaje = Pesaje.objects.create(autor=cls.operario, sede=cls.sede, categoria=cls.categoria, peso_kg=Decimal("100.00"), fecha_generacion=timezone.localdate()-timedelta(days=1), operacion=uuid.uuid4())

    def setUp(self):
        self.client.force_login(self.gerente)
        self.temporal = tempfile.TemporaryDirectory()
        self.ajustes = override_settings(MEDIA_ROOT=self.temporal.name)
        self.ajustes.enable()
        self.addCleanup(self.temporal.cleanup)
        self.addCleanup(self.ajustes.disable)

    def datos(self, **cambios):
        datos = {"sede": self.sede, "categoria": self.categoria, "receptor": "Gestor receptor", "fecha_salida": timezone.localdate(), "observacion": "Salida del turno", "operacion": uuid.uuid4()}
        datos.update(cambios)
        return datos

    def crear(self, peso="80.00", **cambios):
        return crear_retiro(self.gerente, self.datos(**cambios), [{"pesaje": self.pesaje, "peso_kg": Decimal(peso)}])[0]

    def recepcion(self, retiro, peso="78.00", **cambios):
        datos = {"peso_confirmado": Decimal(peso), "fecha_confirmacion": timezone.localdate(), "documento_ref": "GUIA-001", "observacion_recepcion": "Recibido", "version": retiro.version}
        datos.update(cambios)
        return confirmar_recepcion(self.gerente, retiro.pk, datos)

    def archivo(self, nombre="recepcion.pdf", contenido=b"%PDF-1.4\ncontenido\n%%EOF"):
        return SimpleUploadedFile(nombre, contenido, content_type="application/pdf")

    def test_retiro_parcial_saldo_y_doble_asignacion(self):
        retiro = self.crear()
        self.assertEqual(retiro.peso_salida, Decimal("80.00"))
        self.assertEqual(pesajes_disponibles(self.sede, self.categoria).get().disponible, Decimal("20.00"))
        with self.assertRaises(ValidationError):
            self.crear(peso="20.01")
        self.crear(peso="20.00")
        self.assertEqual(pesajes_disponibles(self.sede, self.categoria).get().disponible, 0)
        self.assertEqual(AsignacionRetiro.objects.count(), 2)

    def test_origenes_repetidos_sede_material_fecha_y_anulados(self):
        for cambios in ({"sede": self.otra_sede}, {"categoria": self.otro_material}, {"fecha_salida": timezone.localdate()-timedelta(days=2)}, {"fecha_salida": timezone.localdate()+timedelta(days=1)}):
            with self.assertRaises(ValidationError):
                self.crear(**cambios)
        with self.assertRaises(ValidationError):
            crear_retiro(self.gerente, self.datos(), [{"pesaje": self.pesaje, "peso_kg": Decimal("1.00")}] * 2)
        self.pesaje.anulado = True
        self.pesaje.save()
        with self.assertRaises(ValidationError):
            self.crear()
        self.assertEqual(Retiro.objects.count(), 0)

    def test_reintento_identico_y_operacion_con_contenido_distinto(self):
        datos = self.datos()
        filas = [{"pesaje": self.pesaje, "peso_kg": Decimal("80.00")}]
        primero, creado = crear_retiro(self.gerente, datos, filas)
        segundo, creado = crear_retiro(self.gerente, datos, filas)
        self.assertFalse(creado)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(EventoRetiro.objects.count(), 1)
        datos["receptor"] = "Distinto"
        with self.assertRaises(ValidationError):
            crear_retiro(self.gerente, datos, filas)

    def test_recepcion_diferencia_negativa_y_cero_confirmado(self):
        retiro = self.recepcion(self.crear())
        self.assertEqual(retiro.diferencia, Decimal("-2.00"))
        self.assertEqual(retiro.estado, Retiro.Estado.OBSERVADO)
        retiro = self.recepcion(retiro, peso="0.00")
        self.assertEqual(retiro.peso_confirmado, Decimal("0.00"))
        self.assertEqual(retiro.diferencia, Decimal("-80.00"))

    def test_sin_recepcion_no_puede_cerrar_y_coincidencia_no_cierra_sola(self):
        retiro = self.crear()
        with self.assertRaises(ValidationError):
            resolver_retiro(self.gerente, retiro.pk, {"accion": "conciliar", "version": 1})
        retiro = self.recepcion(retiro, peso="80.00")
        self.assertEqual(retiro.estado, Retiro.Estado.PENDIENTE)
        with self.assertRaises(ValidationError):
            resolver_retiro(self.gerente, retiro.pk, {"accion": "conciliar", "version": retiro.version})

    def test_respaldo_explicacion_cierre_y_reapertura_trazados(self):
        retiro = self.recepcion(self.crear())
        documento = adjuntar_evidencia(self.gerente, retiro.pk, self.archivo(), retiro.version)
        retiro.refresh_from_db()
        with self.assertRaises(ValidationError):
            resolver_retiro(self.gerente, retiro.pk, {"accion": "conciliar", "version": retiro.version, "motivo": ""})
        retiro = resolver_retiro(self.gerente, retiro.pk, {"accion": "conciliar", "version": retiro.version, "motivo": "Diferencia explicada por ajuste de tara"})
        self.assertEqual(retiro.estado, Retiro.Estado.CONCILIADO)
        with self.assertRaises(ValidationError):
            self.recepcion(retiro)
        with self.assertRaises(ValidationError):
            resolver_retiro(self.gerente, retiro.pk, {"accion": "anular", "version": retiro.version, "motivo": "Error"})
        retiro = resolver_retiro(self.gerente, retiro.pk, {"accion": "reabrir", "version": retiro.version, "motivo": "Revisar el documento"})
        self.assertEqual(retiro.estado, Retiro.Estado.OBSERVADO)
        self.assertEqual(retiro.eventos.get(accion="conciliar").motivo, "Diferencia explicada por ajuste de tara")
        self.assertTrue(documento.archivo.storage.exists(documento.archivo.name))

    def test_anulacion_libera_saldo_y_conserva_origen_y_evento(self):
        retiro = self.crear()
        retiro = resolver_retiro(self.gerente, retiro.pk, {"accion": "anular", "version": 1, "motivo": "Registro de salida incorrecto"})
        self.assertEqual(pesajes_disponibles(self.sede, self.categoria).get().disponible, Decimal("100.00"))
        self.assertEqual(retiro.asignaciones.count(), 1)
        with self.assertRaises(ValidationError):
            self.recepcion(retiro)
        self.assertTrue(retiro.eventos.filter(accion="anular").exists())

    def test_version_obsoleta_no_sobrescribe(self):
        retiro = self.crear()
        self.recepcion(retiro)
        with self.assertRaises(ValidationError):
            self.recepcion(retiro, peso="99.00")
        with self.assertRaises(ValidationError):
            resolver_retiro(self.gerente, retiro.pk, {"accion": "anular", "version": 1, "motivo": "Antiguo"})

    def test_correccion_de_pesaje_respeta_los_retiros(self):
        self.crear()
        datos = {"categoria": self.categoria, "peso_kg": Decimal("79.99"), "fecha_generacion": self.pesaje.fecha_generacion, "observacion": "", "version": 1, "motivo": "Corrección"}
        with self.assertRaises(ValidationError):
            modificar_pesaje(self.gerente, self.pesaje.pk, datos)
        with self.assertRaises(ValidationError):
            modificar_pesaje(self.gerente, self.pesaje.pk, datos, anular=True)
        datos["peso_kg"] = Decimal("90.00")
        modificar_pesaje(self.gerente, self.pesaje.pk, datos)
        self.assertEqual(pesajes_disponibles(self.sede, self.categoria).get().disponible, Decimal("10.00"))

    def test_recepcion_fechas_incoherentes_y_precision(self):
        retiro = self.crear()
        for cambios in ({"fecha_confirmacion": retiro.fecha_salida-timedelta(days=1)}, {"fecha_confirmacion": timezone.localdate()+timedelta(days=1)}, {"peso_confirmado": Decimal("1.001")}, {"peso_confirmado": Decimal("-1")}):
            with self.assertRaises(ValidationError):
                self.recepcion(retiro, **cambios)

    def test_privacidad_documentos_tipo_tamano_y_hash(self):
        retiro = self.crear()
        documento = adjuntar_evidencia(self.gerente, retiro.pk, self.archivo(nombre="respaldo.pdf"), 1)
        respuesta = self.client.get(reverse("evidencia_descargar", args=[documento.pk]))
        self.assertIn("attachment", respuesta["Content-Disposition"])
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.assertEqual(b"".join(respuesta.streaming_content), b"%PDF-1.4\ncontenido\n%%EOF")
        self.client.force_login(self.operario)
        self.assertEqual(self.client.get(reverse("evidencia_descargar", args=[documento.pk])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("evidencia_descargar", args=[documento.pk])).status_code, 302)
        for archivo in (self.archivo("documento.html"), self.archivo("documento.pdf", b"<script>contenido</script>"), self.archivo("grande.pdf", b"%PDF-"+b"x"*(10*1024*1024))):
            with self.assertRaises(ValidationError):
                validar_archivo(archivo)
        self.assertEqual(len(documento.sha256), 64)
        self.assertNotIn("respaldo", documento.archivo.name)

    def test_duplicado_de_documento_no_se_guarda_y_fallo_revierte_archivo(self):
        retiro = self.crear()
        adjuntar_evidencia(self.gerente, retiro.pk, self.archivo(), 1)
        retiro.refresh_from_db()
        with self.assertRaises(ValidationError):
            adjuntar_evidencia(self.gerente, retiro.pk, self.archivo(), retiro.version)
        iniciales = list(Path(self.temporal.name).rglob("*.pdf"))
        with patch("residuos.retiros_services.EventoRetiro.objects.create", side_effect=RuntimeError("fallo")):
            with self.assertRaises(RuntimeError):
                adjuntar_evidencia(self.gerente, retiro.pk, self.archivo("otro.pdf", b"%PDF-1.4\notro\n%%EOF"), retiro.version)
        self.assertEqual(list(Path(self.temporal.name).rglob("*.pdf")), iniciales)
        self.assertEqual(EvidenciaRetiro.objects.count(), 1)

    def test_fallo_evento_no_deja_retiro_ni_asignaciones(self):
        with patch("residuos.retiros_services.EventoRetiro.objects.create", side_effect=RuntimeError("fallo")):
            with self.assertRaises(RuntimeError):
                self.crear()
        self.assertEqual(Retiro.objects.count(), 0)
        self.assertEqual(AsignacionRetiro.objects.count(), 0)

    def test_pantallas_y_alta_post_real(self):
        self.assertEqual(self.client.get(reverse("conciliacion")).status_code, 200)
        self.assertEqual(self.client.get(reverse("retiro_nuevo")).status_code, 200)
        respuesta = self.client.get(reverse("retiro_nuevo"), {"sede": self.sede.pk, "categoria": self.categoria.pk})
        self.assertEqual(respuesta.status_code, 200)
        token = respuesta.context["form"]["operacion"].value()
        datos = {"sede": self.sede.pk, "categoria": self.categoria.pk, "receptor": "Gestor", "fecha_salida": timezone.localdate().isoformat(), "observacion": "", "operacion": token,
                 "origenes-TOTAL_FORMS": "1", "origenes-INITIAL_FORMS": "0", "origenes-MIN_NUM_FORMS": "1", "origenes-MAX_NUM_FORMS": "20", "origenes-0-pesaje": self.pesaje.pk, "origenes-0-peso_kg": "80,00"}
        respuesta = self.client.post(reverse("retiro_nuevo"), datos)
        self.assertEqual(respuesta.status_code, 302)
        retiro = Retiro.objects.get()
        self.assertEqual(self.client.get(reverse("retiro_detalle", args=[retiro.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse("retiro_nuevo"), datos).status_code, 302)
        self.assertEqual(Retiro.objects.count(), 1)
        datos["operacion"] = "firma-alterada"
        self.assertEqual(self.client.post(reverse("retiro_nuevo"), datos).status_code, 400)
        self.assertEqual(Retiro.objects.count(), 1)

    def test_recorrido_http_recepcion_respaldo_y_cierre(self):
        retiro = self.crear()
        respuesta = self.client.post(reverse("retiro_confirmar", args=[retiro.pk]), {
            "peso_confirmado": "78,00", "fecha_confirmacion": timezone.localdate().isoformat(),
            "documento_ref": "REC-2026-001", "observacion_recepcion": "Diferencia de tara", "version": 1})
        self.assertEqual(respuesta.status_code, 302)
        retiro.refresh_from_db()
        self.assertEqual(self.client.post(reverse("retiro_evidencia", args=[retiro.pk]), {"version": retiro.version, "archivo": self.archivo()}).status_code, 302)
        retiro.refresh_from_db()
        self.assertEqual(self.client.post(reverse("retiro_accion", args=[retiro.pk]), {
            "version": retiro.version, "accion": "conciliar", "motivo": "Tara verificada con el receptor"}).status_code, 302)
        retiro.refresh_from_db()
        self.assertEqual(retiro.estado, Retiro.Estado.CONCILIADO)
        respuesta = self.client.get(reverse("retiro_detalle", args=[retiro.pk]))
        self.assertContains(respuesta, "Reabrir conciliación")
        self.assertContains(respuesta, "Tara verificada con el receptor")

    def test_operarios_y_anonimos_no_gestionan_retiros_y_csrf(self):
        retiro = self.crear()
        rutas = [reverse("conciliacion"), reverse("retiro_nuevo"), reverse("retiro_detalle", args=[retiro.pk])]
        self.client.force_login(self.operario)
        for ruta in rutas[:2]:
            self.assertEqual(self.client.get(ruta).status_code, 200)
        self.assertEqual(self.client.get(rutas[2]).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(rutas[0]).status_code, 302)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.gerente)
        for nombre in ("retiro_confirmar", "retiro_accion", "retiro_evidencia"):
            self.assertEqual(cliente.post(reverse(nombre, args=[retiro.pk]), {}).status_code, 403)
            self.assertEqual(cliente.get(reverse(nombre, args=[retiro.pk])).status_code, 405)
        with self.assertRaises(PermissionDenied):
            resolver_retiro(self.operario, retiro.pk, {"version": retiro.version, "accion": "anular", "motivo": "No autorizado"})

    def test_operario_registra_recibe_adjunta_y_gerente_cierra(self):
        retiro = crear_retiro(self.operario, self.datos(), [{"pesaje": self.pesaje, "peso_kg": Decimal("10.00")}])[0]
        self.client.force_login(self.operario)
        pagina = self.client.get(reverse("retiro_detalle", args=[retiro.pk]))
        self.assertEqual(pagina.status_code, 200)
        self.assertNotContains(pagina, 'name="accion" value="conciliar"')
        datos = {"peso_confirmado": "9.80", "fecha_confirmacion": timezone.localdate(), "documento_ref": "GUIA-OPERARIO", "observacion_recepcion": "Recibido", "version": retiro.version}
        self.assertEqual(self.client.post(reverse("retiro_confirmar", args=[retiro.pk]), datos).status_code, 302)
        retiro.refresh_from_db()
        self.assertEqual(retiro.diferencia, Decimal("-0.20"))
        documento = adjuntar_evidencia(self.operario, retiro.pk, self.archivo(), retiro.version)
        self.assertEqual(self.client.get(reverse("evidencia_descargar", args=[documento.pk])).status_code, 200)
        retiro.refresh_from_db()
        self.assertEqual(self.client.post(reverse("retiro_accion", args=[retiro.pk]), {"accion": "conciliar", "version": retiro.version}).status_code, 403)
        resolver_retiro(self.gerente, retiro.pk, {"accion": "conciliar", "version": retiro.version, "motivo": "Diferencia revisada"})
        retiro.refresh_from_db()
        self.assertEqual(retiro.estado, Retiro.Estado.CONCILIADO)
        with self.assertRaises(ValidationError):
            confirmar_recepcion(self.operario, retiro.pk, dict(datos, version=retiro.version))

    def test_alta_http_operario_con_firma_y_reintento(self):
        self.client.force_login(self.operario)
        self.test_pantallas_y_alta_post_real()
        self.assertEqual(Retiro.objects.get().actor_id, self.operario.pk)
        self.assertContains(self.client.get(reverse("conciliacion")), "Mis salidas")

    def test_operario_no_usa_pesajes_ajenos_ni_sede_ajena(self):
        otro = get_user_model().objects.create_user(username="colega", sede=self.sede)
        for actor, cambios in ((otro, {}), (self.operario, {"sede": self.otra_sede})):
            with self.assertRaises(PermissionDenied):
                crear_retiro(actor, self.datos(**cambios), [{"pesaje": self.pesaje, "peso_kg": Decimal("1.00")}])
        retiro = self.crear()
        with self.assertRaises(PermissionDenied):
            confirmar_recepcion(self.operario, retiro.pk, {"version": retiro.version})
        with self.assertRaises(PermissionDenied):
            adjuntar_evidencia(self.operario, retiro.pk, self.archivo(), retiro.version)
        self.client.force_login(self.operario)
        self.assertEqual(self.client.get(reverse("conciliacion")).context["pagina"].paginator.count, 0)
        self.operario.sede = self.otra_sede
        self.operario.save()
        with self.assertRaises(PermissionDenied):
            crear_retiro(self.operario, self.datos(), [{"pesaje": self.pesaje, "peso_kg": Decimal("1.00")}])

    def test_filtros_y_nombres_escapados(self):
        retiro = self.crear(receptor="<script>alert(1)</script>")
        self.assertContains(self.client.get(reverse("retiro_detalle", args=[retiro.pk])), "&lt;script&gt;")
        respuesta = self.client.get(reverse("conciliacion"), {"sede": self.otra_sede.pk})
        self.assertEqual(respuesta.context["pagina"].paginator.count, 0)
        self.assertEqual(self.client.get(reverse("conciliacion"), {"desde": "invalido"}).context["pagina"].paginator.count, 0)


class AsignacionesConcurrentesTests(TransactionTestCase):
    def test_dos_gerentes_no_pueden_sobregirar_el_mismo_pesaje(self):
        sede = Sede.objects.create(nombre="Concurrencia")
        categoria = Categoria.objects.create(clave="concurrencia", nombre="Material", grupo="reciclable")
        uno = get_user_model().objects.create(username="gerente_a", rol="gerente")
        dos = get_user_model().objects.create(username="gerente_b", rol="gerente")
        pesaje = Pesaje.objects.create(autor=uno, sede=sede, categoria=categoria, peso_kg=Decimal("100.00"), fecha_generacion=timezone.localdate(), operacion=uuid.uuid4())
        barrera = Barrier(2)
        def retirar(actor):
            try:
                barrera.wait(timeout=10)
                crear_retiro(actor, {"sede": sede, "categoria": categoria, "receptor": "Receptor", "fecha_salida": timezone.localdate(), "observacion": "", "operacion": uuid.uuid4()}, [{"pesaje": pesaje, "peso_kg": Decimal("80.00")}])
                return "creado"
            except ValidationError:
                return "rechazado"
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(retirar, (uno, dos)))
        self.assertCountEqual(resultados, ["creado", "rechazado"])
        self.assertEqual(Retiro.objects.count(), 1)
