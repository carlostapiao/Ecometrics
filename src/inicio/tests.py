from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from cuentas.models import Sede


class PaginaInicialTests(SimpleTestCase):
    def test_inicio_envia_al_acceso(self):
        respuesta = self.client.get(reverse("inicio"))
        self.assertRedirects(respuesta, reverse("login"))

    def test_salud_no_necesita_base(self):
        self.assertEqual(self.client.get(reverse("salud")).json(), {"estado": "ok"})

    def test_no_acepta_host_ajeno(self):
        self.assertEqual(self.client.get("/", HTTP_HOST="ajeno.invalid").status_code, 400)


class BasePostgresTests(TestCase):
    def test_disponibilidad_fallida_no_expone_detalles(self):
        with patch("inicio.views.connection.cursor", side_effect=OperationalError("dato privado")):
            respuesta = self.client.get(reverse("disponibilidad"))
        self.assertEqual(respuesta.status_code, 503)
        self.assertNotIn("dato privado", respuesta.content.decode())

    def test_disponibilidad_consulta_base(self):
        self.assertEqual(self.client.get(reverse("disponibilidad")).status_code, 200)

    def test_operario_no_recibe_privilegios_tecnicos(self):
        sede = Sede.objects.create(nombre="Planta de prueba")
        usuario = get_user_model().objects.create_user(username="operario_prueba", sede=sede)
        self.assertEqual(usuario.rol, "operario")
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(usuario.has_usable_password())
