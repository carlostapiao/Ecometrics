import re
import uuid
from decimal import Decimal

from django import forms
from django.core import signing
from django.db.models import Q
from django.utils import timezone

from cuentas.models import Sede
from .models import Categoria, Retiro

SALT = "ecometrics.pesaje"


def nueva_operacion(usuario):
    return signing.dumps({"usuario": usuario.pk, "operacion": str(uuid.uuid4())}, salt=SALT)


class PesajeForm(forms.Form):
    categoria = forms.ModelChoiceField(queryset=Categoria.objects.none(), widget=forms.RadioSelect, label="Categoría del residuo", empty_label=None)
    peso_kg = forms.CharField(label="Peso neto (kg)", max_length=12, widget=forms.TextInput(attrs={"inputmode": "decimal", "placeholder": "0.00", "class": "peso", "autocomplete": "off"}))
    fecha_generacion = forms.DateField(label="Fecha de generación", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), input_formats=["%Y-%m-%d"])
    observacion = forms.CharField(label="Observación (opcional)", max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 3}))
    operacion = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.fields["categoria"].queryset = Categoria.objects.filter(activa=True)
        self.fields["fecha_generacion"].initial = timezone.localdate()
        self.fields["fecha_generacion"].widget.attrs["max"] = timezone.localdate().isoformat()
        if not self.is_bound and "operacion" in self.fields:
            self.fields["operacion"].initial = nueva_operacion(usuario)

    def clean_peso_kg(self):
        valor = self.cleaned_data["peso_kg"].strip()
        if not re.fullmatch(r"[0-9]+(?:[.,][0-9]{1,2})?", valor):
            raise forms.ValidationError("Ingresa un peso positivo con hasta dos decimales, sin separadores de miles.")
        peso = Decimal(valor.replace(",", "."))
        if peso <= 0 or peso > Decimal("9999999.99"):
            raise forms.ValidationError("El peso debe estar entre 0.01 y 9999999.99 kg.")
        return peso.quantize(Decimal("0.01"))

    def clean_fecha_generacion(self):
        fecha = self.cleaned_data["fecha_generacion"]
        if fecha > timezone.localdate():
            raise forms.ValidationError("La fecha no puede estar en el futuro.")
        return fecha

    def clean_operacion(self):
        try:
            datos = signing.loads(self.cleaned_data["operacion"], salt=SALT, max_age=86400)
            if datos["usuario"] != self.usuario.pk:
                raise ValueError
            return uuid.UUID(datos["operacion"])
        except (signing.BadSignature, KeyError, ValueError, TypeError):
            raise forms.ValidationError("El formulario venció o no es válido. Abre un registro nuevo.")


class CorreccionForm(PesajeForm):
    operacion = None
    motivo = forms.CharField(max_length=500, label="Motivo de la corrección", widget=forms.Textarea(attrs={"rows": 3}))
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, usuario, pesaje, **kwargs):
        super().__init__(*args, usuario=usuario, **kwargs)
        # Una categoría histórica inactiva puede conservarse al corregir otros campos.
        self.fields["categoria"].queryset = Categoria.objects.filter(Q(activa=True) | Q(pk=pesaje.categoria_id))
        self.initial.update({"categoria": pesaje.categoria_id, "peso_kg": str(pesaje.peso_kg),
                             "fecha_generacion": pesaje.fecha_generacion, "observacion": pesaje.observacion,
                             "version": pesaje.version})


class AnulacionForm(forms.Form):
    motivo = forms.CharField(max_length=500, label="Motivo de la anulación", widget=forms.Textarea(attrs={"rows": 3}))
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    confirmar = forms.BooleanField(label="Confirmo la anulación de este pesaje")


class FiltrosForm(forms.Form):
    desde = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    categoria = forms.ModelChoiceField(queryset=Categoria.objects.all(), required=False, empty_label="Todas las categorías")

    def clean(self):
        datos = super().clean()
        if datos.get("desde") and datos.get("hasta") and datos["desde"] > datos["hasta"]:
            raise forms.ValidationError("La fecha inicial debe ser anterior o igual a la final.")
        return datos


class ConsultaPesajesForm(FiltrosForm):
    estado = forms.ChoiceField(required=False, choices=[("", "Todos los estados"), ("vigente", "Vigentes"), ("anulado", "Anulados")])
    buscar = forms.CharField(required=False, max_length=100, label="Buscar", widget=forms.TextInput(attrs={"placeholder": "N.º de registro, operario u observación", "type": "search"}))


class ReporteForm(FiltrosForm):
    tipo = forms.ChoiceField(required=False, initial="generacion", label="Tipo de reporte", choices=[
        ("generacion", "Residuos generados"), ("retiros", "Salidas de residuos"), ("recepciones", "Recepciones confirmadas")])
    sede = forms.ModelChoiceField(queryset=Sede.objects.all(), required=False, empty_label="Todas las sedes")
    estado = forms.ChoiceField(required=False, label="Estado del retiro", choices=[("", "Todos los estados vigentes")] + [
        (valor, nombre) for valor, nombre in Retiro.Estado.choices if valor != Retiro.Estado.ANULADO])

    def clean(self):
        datos = super().clean()
        datos["tipo"] = datos.get("tipo") or "generacion"
        if datos["tipo"] == "generacion" and datos.get("estado"):
            self.add_error("estado", "El estado del retiro solo se utiliza en salidas y recepciones.")
        return datos
