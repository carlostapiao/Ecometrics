from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from .models import Sede


class AccesoForm(AuthenticationForm):
    username = forms.CharField(label="Usuario", widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}))
    password = forms.CharField(label="Contraseña", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.rol == "operario" and (not user.sede_id or not user.sede.activa):
            raise forms.ValidationError("Tu cuenta necesita una sede activa. Consulta al responsable.", code="sede_inactiva")


class SedeForm(forms.ModelForm):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput, initial=0)

    class Meta:
        model = Sede
        fields = ["nombre", "direccion", "activa"]
        labels = {"nombre": "Nombre de la sede o planta", "direccion": "Dirección (opcional)", "activa": "Sede activa"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["version"] = self.instance.version if self.instance.pk else 0

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        if Sede.objects.filter(nombre__iexact=nombre).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe una sede con ese nombre.")
        return nombre


class PersonalForm(forms.ModelForm):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput, initial=0)

    class Meta:
        model = get_user_model()
        fields = ["first_name", "last_name", "username", "email", "sede", "is_active"]
        labels = {"first_name": "Nombres", "last_name": "Apellidos", "username": "Usuario de acceso", "email": "Correo (opcional)", "sede": "Sede asignada", "is_active": "Acceso activo"}
        help_texts = {"username": "Hasta 150 caracteres. Letras, números y @/./+/-/_ solamente."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        self.fields["first_name"].required = True
        self.fields["sede"].required = True
        self.fields["sede"].queryset = Sede.objects.filter(Q(activa=True) | Q(pk=self.instance.sede_id))
        self.initial["version"] = self.instance.version_gestion if self.instance.pk else 0
        if self.instance.pk:
            self.fields["username"].disabled = True
        if not self.instance.pk or not self.instance.has_usable_password():
            self.fields.pop("is_active")

    def clean_username(self):
        nombre = self.cleaned_data["username"].strip()
        if get_user_model().objects.filter(username__iexact=nombre).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ese usuario ya existe. Elige otro identificador.")
        return nombre
