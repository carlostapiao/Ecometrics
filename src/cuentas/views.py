from django.contrib.auth.views import LoginView
from django.urls import reverse

from .forms import AccesoForm


class AccesoView(LoginView):
    template_name = "cuentas/login.html"
    authentication_form = AccesoForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse("resumen" if self.request.user.rol == "gerente" else "registrar")
