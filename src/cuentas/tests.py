import hashlib
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from residuos.models import Categoria, Pesaje
from .models import EventoGestion, Invitacion, Sede
from .services import activar_cuenta, guardar_personal, guardar_sede, renovar_invitacion, revocar_invitacion


class GestionCuentasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sede = Sede.objects.create(nombre="Planta Uno")
        cls.otra = Sede.objects.create(nombre="Planta Dos")
        cls.gerente = get_user_model().objects.create_user(username="responsable", rol="gerente", password="Acceso-aislado-2026!")
        cls.operario = get_user_model().objects.create_user(username="operador", first_name="Elena", sede=cls.sede, password="Acceso-aislado-2026!")
        cls.tecnico = get_user_model().objects.create_user(username="tecnico", rol="operario", is_staff=True, sede=cls.sede)

    def setUp(self):
        self.client.force_login(self.gerente)

    def datos(self, **cambios):
        datos = {"first_name": "Ana", "last_name": "Rojas", "username": "ana.rojas", "email": "", "sede": self.sede.pk, "version": 0}
        datos.update(cambios)
        return datos

    def crear_pendiente(self, **cambios):
        respuesta = self.client.post(reverse("personal_nuevo"), self.datos(**cambios))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "cuentas/invitacion.html")
        token = respuesta.context["enlace"].split("#", 1)[1]
        return respuesta.context["persona"], token

    def credenciales(self, token, **cambios):
        datos = {"token": token, "new_password1": "Bosque!Agua-2026-Seguro", "new_password2": "Bosque!Agua-2026-Seguro"}
        datos.update(cambios)
        return datos

    def test_alta_solo_operario_inactivo_sin_clave_y_token_hasheado(self):
        persona, token = self.crear_pendiente(rol="gerente", is_staff="on", is_superuser="on", is_active="on", password="impuesta")
        persona.refresh_from_db()
        self.assertEqual(persona.rol, "operario")
        self.assertFalse(persona.is_active or persona.is_staff or persona.is_superuser or persona.has_usable_password())
        invitacion = Invitacion.objects.get(usuario=persona)
        self.assertNotEqual(invitacion.huella, token)
        self.assertEqual(invitacion.huella, hashlib.sha256(token.encode()).hexdigest())
        self.assertNotIn(token, str(list(EventoGestion.objects.values("datos"))))
        self.assertLess(invitacion.vence_en, timezone.now() + timedelta(hours=24, seconds=1))
        self.assertEqual(self.client.post(reverse("personal_nuevo"), self.datos()).status_code, 400)
        self.assertEqual(get_user_model().objects.filter(username="ana.rojas").count(), 1)

    def test_enlace_en_fragmento_y_respuesta_no_cache(self):
        respuesta = self.client.post(reverse("personal_nuevo"), self.datos())
        self.assertIn("/activar/#", respuesta.context["enlace"])
        self.assertNotIn("?token", respuesta.context["enlace"])
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.assertEqual(respuesta["Referrer-Policy"], "no-referrer")
        self.assertNotContains(self.client.get(reverse("personal")), respuesta.context["enlace"])

    def test_activacion_unica_permite_login_real(self):
        persona, token = self.crear_pendiente()
        self.client.logout()
        respuesta = self.client.post(reverse("activar_cuenta"), self.credenciales(token))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Cuenta activada")
        persona.refresh_from_db()
        self.assertTrue(persona.is_active and persona.check_password("Bosque!Agua-2026-Seguro"))
        self.assertEqual(self.client.post(reverse("activar_cuenta"), self.credenciales(token)).status_code, 400)
        self.assertEqual(EventoGestion.objects.filter(usuario=persona, accion="cuenta_activada").count(), 1)
        self.assertTrue(self.client.login(username=persona.username, password="Bosque!Agua-2026-Seguro"))
        self.assertEqual(self.client.get(reverse("registrar")).status_code, 200)

    def test_activacion_csrf_origen_propio_y_rechazo_ajeno(self):
        persona, token = self.crear_pendiente()
        navegador = Client(enforce_csrf_checks=True)
        pagina = navegador.get(reverse("activar_cuenta"))
        self.assertEqual(pagina["Referrer-Policy"], "same-origin")
        self.assertContains(pagina, 'name="referrer" content="same-origin"')
        csrf = navegador.cookies["csrftoken"].value
        datos = dict(self.credenciales(token), csrfmiddlewaretoken=csrf)
        for origen in ("null", "http://otro.example"):
            self.assertEqual(navegador.post(reverse("activar_cuenta"), datos, HTTP_ORIGIN=origen).status_code, 403)
        self.assertEqual(navegador.post(reverse("activar_cuenta"), self.credenciales(token), HTTP_ORIGIN="http://testserver").status_code, 403)
        respuesta = navegador.post(reverse("activar_cuenta"), datos, HTTP_ORIGIN="http://testserver")
        self.assertContains(respuesta, "Cuenta activada")
        persona.refresh_from_db()
        self.assertTrue(persona.is_active)

    def test_clave_debil_o_distinta_no_consume_enlace(self):
        persona, token = self.crear_pendiente()
        for cambios in ({"new_password1": "123", "new_password2": "123"}, {"new_password2": "Diferente!2026"}, {"new_password1": "Corta!123", "new_password2": "Corta!123"}):
            self.assertEqual(self.client.post(reverse("activar_cuenta"), self.credenciales(token, **cambios)).status_code, 400)
        persona.refresh_from_db()
        self.assertFalse(persona.is_active)
        self.assertIsNone(Invitacion.objects.get(usuario=persona).utilizada_en)

    def test_enlace_vencido_aleatorio_o_sin_token_no_activa(self):
        persona, token = self.crear_pendiente()
        Invitacion.objects.filter(usuario=persona).update(vence_en=timezone.now() - timedelta(seconds=1))
        for valor in (token, "inventado", "", "a" * 101):
            self.assertEqual(self.client.post(reverse("activar_cuenta"), self.credenciales(valor)).status_code, 400)
        persona.refresh_from_db()
        self.assertFalse(persona.is_active)

    def test_reemision_invalida_anterior_y_revocacion_bloquea(self):
        persona, primero = self.crear_pendiente()
        respuesta = self.client.post(reverse("invitacion_gestionar", args=[persona.pk]), {"version": 1, "accion": "emitir"})
        segundo = respuesta.context["enlace"].split("#", 1)[1]
        self.assertEqual(self.client.post(reverse("activar_cuenta"), self.credenciales(primero)).status_code, 400)
        persona.refresh_from_db()
        self.assertEqual(self.client.post(reverse("invitacion_gestionar", args=[persona.pk]), {"version": persona.version_gestion, "accion": "revocar"}).status_code, 302)
        self.assertEqual(self.client.post(reverse("activar_cuenta"), self.credenciales(segundo)).status_code, 400)
        self.assertEqual(self.client.get(reverse("invitacion_gestionar", args=[persona.pk])).status_code, 405)

    def test_activacion_no_es_reset_de_cuentas_activas(self):
        persona, token = self.crear_pendiente()
        activar_cuenta(token, "Bosque!Agua-2026-Seguro")
        persona.refresh_from_db()
        with self.assertRaises(ValidationError):
            renovar_invitacion(self.gerente, persona.pk, persona.version_gestion)
        self.assertEqual(self.client.post(reverse("invitacion_gestionar", args=[self.operario.pk]), {"version": 1, "accion": "emitir"}).status_code, 400)

    def test_sede_inactiva_bloquea_alta_y_activacion(self):
        persona, token = self.crear_pendiente()
        self.sede.activa = False
        self.sede.save()
        self.assertEqual(self.client.post(reverse("activar_cuenta"), self.credenciales(token)).status_code, 400)
        self.assertEqual(self.client.post(reverse("personal_nuevo"), self.datos(username="otra.persona")).status_code, 400)
        self.assertIsNone(Invitacion.objects.get(usuario=persona).utilizada_en)

    def test_no_se_pueden_gestionar_gerentes_ni_tecnicos(self):
        for persona in (self.gerente, self.tecnico):
            for nombre in ("personal_editar", "invitacion_gestionar"):
                self.assertEqual(self.client.get(reverse(nombre, args=[persona.pk])).status_code, 404 if nombre == "personal_editar" else 405)
                self.assertEqual(self.client.post(reverse(nombre, args=[persona.pk]), self.datos()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("personal")), "tecnico")

    def test_desactivacion_corta_sesion_y_conserva_pesajes(self):
        import uuid
        registro = Pesaje.objects.create(autor=self.operario, sede=self.sede, categoria=Categoria.objects.first(), peso_kg=Decimal("2.50"), fecha_generacion=timezone.localdate(), operacion=uuid.uuid4())
        otro = Client()
        otro.force_login(self.operario)
        respuesta = self.client.post(reverse("personal_editar", args=[self.operario.pk]), self.datos(username="no-se-cambia", first_name="Elena", version=1))
        self.assertEqual(respuesta.status_code, 302)
        self.operario.refresh_from_db()
        self.assertFalse(self.operario.is_active)
        self.assertEqual(self.operario.username, "operador")
        self.assertEqual(otro.get(reverse("historial")).status_code, 302)
        self.assertTrue(Pesaje.objects.filter(pk=registro.pk).exists())
        self.assertEqual(EventoGestion.objects.get(usuario=self.operario).datos["antes"]["activo"], True)

    def test_cambio_sede_no_reescribe_historia(self):
        import uuid
        registro = Pesaje.objects.create(autor=self.operario, sede=self.sede, categoria=Categoria.objects.first(), peso_kg=Decimal("2.50"), fecha_generacion=timezone.localdate(), operacion=uuid.uuid4())
        self.client.post(reverse("personal_editar", args=[self.operario.pk]), self.datos(first_name="Elena", sede=self.otra.pk, version=1, is_active="on"))
        self.operario.refresh_from_db()
        registro.refresh_from_db()
        self.assertEqual(self.operario.sede_id, self.otra.pk)
        self.assertEqual(registro.sede_id, self.sede.pk)
        self.assertEqual(self.client.post(reverse("personal_editar", args=[self.operario.pk]), self.datos(version=1)).status_code, 400)

    def test_sedes_alta_edicion_desactivacion_y_auditoria(self):
        self.assertEqual(self.client.post(reverse("sede_nueva"), {"nombre": "Planta Tres", "direccion": "Avenida Principal", "activa": "on", "version": 0}).status_code, 302)
        sede = Sede.objects.get(nombre="Planta Tres")
        self.assertEqual(self.client.post(reverse("sede_editar", args=[sede.pk]), {"nombre": "Planta Tres", "direccion": "", "version": 1}).status_code, 302)
        sede.refresh_from_db()
        self.assertFalse(sede.activa)
        self.assertEqual(EventoGestion.objects.filter(sede=sede).count(), 2)
        self.assertEqual(self.client.post(reverse("sede_editar", args=[sede.pk]), {"nombre": "Antigua", "direccion": "", "version": 1}).status_code, 400)
        self.assertEqual(self.client.post(reverse("sede_nueva"), {"nombre": "planta tres", "version": 0}).status_code, 400)

    def test_restricciones_case_insensitive_en_base(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Sede.objects.create(nombre="planta uno")
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create(username="OPERADOR")

    def test_modulos_solo_gerenciales_y_csrf(self):
        rutas = [reverse("sedes"), reverse("sede_nueva"), reverse("personal"), reverse("personal_nuevo"), reverse("personal_editar", args=[self.operario.pk])]
        for ruta in rutas:
            self.client.force_login(self.operario)
            self.assertEqual(self.client.get(ruta).status_code, 403)
            self.client.force_login(self.gerente)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.gerente)
        for ruta in rutas[1:]:
            self.assertEqual(cliente.post(ruta, self.datos()).status_code, 403)
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse("activar_cuenta"), self.credenciales("x")).status_code, 403)

    def test_fallo_de_evento_revierte_alta_y_activacion(self):
        datos = self.datos(sede=self.sede)
        with patch("cuentas.services.EventoGestion.objects.create", side_effect=RuntimeError("fallo")):
            with self.assertRaises(RuntimeError):
                guardar_personal(self.gerente, datos)
        self.assertFalse(get_user_model().objects.filter(username="ana.rojas").exists())
        persona, token = self.crear_pendiente()
        with patch("cuentas.services.EventoGestion.objects.create", side_effect=RuntimeError("fallo")):
            with self.assertRaises(RuntimeError):
                activar_cuenta(token, "Bosque!Agua-2026-Seguro")
        persona.refresh_from_db()
        self.assertFalse(persona.is_active)
        self.assertIsNone(Invitacion.objects.get(usuario=persona).utilizada_en)

    def test_html_nombres_escapados_y_pantallas_gerenciales(self):
        self.operario.first_name = "<script>alert(1)</script>"
        self.operario.save()
        self.assertContains(self.client.get(reverse("personal")), "&lt;script&gt;")
        for ruta in (reverse("sedes"), reverse("sede_nueva"), reverse("personal_nuevo"), reverse("personal_editar", args=[self.operario.pk])):
            self.assertEqual(self.client.get(ruta).status_code, 200)
        self.assertContains(self.client.get(reverse("activar_cuenta")), "activacion.js")
