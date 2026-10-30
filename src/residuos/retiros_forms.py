import uuid
from django import forms
from django.core import signing
from django.forms import formset_factory
from django.utils import timezone
from cuentas.models import Sede
from .models import Categoria, Pesaje, Retiro
from .cantidades import validar_kg

SALT = "ecometrics.retiro"


class SeleccionRetiroForm(forms.Form):
    sede = forms.ModelChoiceField(queryset=Sede.objects.filter(activa=True), label="Sede")
    categoria = forms.ModelChoiceField(queryset=Categoria.objects.all(), label="Categoría")


class RetiroForm(SeleccionRetiroForm):
    fecha_salida = forms.DateField(label="Fecha de salida", input_formats=["%Y-%m-%d"], widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    receptor = forms.CharField(max_length=160, label="Recolector o receptor")
    observacion = forms.CharField(max_length=500, required=False, label="Observación (opcional)", widget=forms.Textarea(attrs={"rows": 3}))
    operacion = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.fields["sede"].widget = forms.HiddenInput()
        self.fields["categoria"].widget = forms.HiddenInput()
        self.fields["fecha_salida"].initial = timezone.localdate()
        self.fields["fecha_salida"].widget.attrs["max"] = timezone.localdate().isoformat()
        if not self.is_bound:
            self.fields["operacion"].initial = signing.dumps({"usuario": usuario.pk, "operacion": str(uuid.uuid4())}, salt=SALT)

    def clean_fecha_salida(self):
        fecha = self.cleaned_data["fecha_salida"]
        if fecha > timezone.localdate():
            raise forms.ValidationError("La salida no puede tener una fecha futura.")
        return fecha

    def clean_operacion(self):
        try:
            datos = signing.loads(self.cleaned_data["operacion"], salt=SALT, max_age=86400)
            if datos["usuario"] != self.usuario.pk:
                raise ValueError
            return uuid.UUID(datos["operacion"])
        except (signing.BadSignature, KeyError, ValueError, TypeError):
            raise forms.ValidationError("El formulario venció. Abre un retiro nuevo.")


class PesajeDisponibleField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"#{obj.pk} · {obj.fecha_generacion:%d/%m/%Y} · Disponible: {obj.disponible:.2f} kg"


class AsignacionForm(forms.Form):
    pesaje = PesajeDisponibleField(queryset=Pesaje.objects.none(), label="Pesaje de origen")
    peso_kg = forms.CharField(label="Cantidad a retirar (kg)", max_length=12, widget=forms.TextInput(attrs={"inputmode": "decimal", "placeholder": "0.00"}))

    def __init__(self, *args, disponibles, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pesaje"].queryset = disponibles

    def clean_peso_kg(self):
        return validar_kg(self.cleaned_data["peso_kg"])


AsignacionesFormSet = formset_factory(AsignacionForm, extra=0, min_num=1, validate_min=True, max_num=20, absolute_max=20, validate_max=True, can_delete=True)


class ConfirmacionForm(forms.Form):
    peso_confirmado = forms.CharField(label="Peso confirmado por el receptor (kg)", max_length=12, widget=forms.TextInput(attrs={"inputmode": "decimal"}))
    fecha_confirmacion = forms.DateField(label="Fecha de recepción", input_formats=["%Y-%m-%d"], widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    documento_ref = forms.CharField(max_length=120, required=False, label="N.º de constancia, guía o documento")
    observacion_recepcion = forms.CharField(max_length=500, required=False, label="Observación del receptor (opcional)", widget=forms.Textarea(attrs={"rows": 3}))
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def clean_peso_confirmado(self):
        return validar_kg(self.cleaned_data["peso_confirmado"], permitir_cero=True)

    def clean_fecha_confirmacion(self):
        fecha = self.cleaned_data["fecha_confirmacion"]
        if fecha > timezone.localdate():
            raise forms.ValidationError("La recepción no puede tener una fecha futura.")
        return fecha


class AccionRetiroForm(forms.Form):
    accion = forms.ChoiceField(choices=[("conciliar", "Conciliar"), ("anular", "Anular"), ("reabrir", "Reabrir")], widget=forms.HiddenInput)
    motivo = forms.CharField(max_length=1000, required=False, label="Motivo o explicación de la diferencia", widget=forms.Textarea(attrs={"rows": 3}))
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class EvidenciaForm(forms.Form):
    archivo = forms.FileField(label="Documento de respaldo (PDF, JPG o PNG; máximo 10 MB)", widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png"}))
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def clean_archivo(self):
        from .retiros_services import validar_archivo
        archivo = self.cleaned_data["archivo"]
        validar_archivo(archivo)
        return archivo


class FiltrosRetiroForm(forms.Form):
    sede = forms.ModelChoiceField(queryset=Sede.objects.all(), required=False, empty_label="Todas las sedes")
    categoria = forms.ModelChoiceField(queryset=Categoria.objects.all(), required=False, empty_label="Todas las categorías")
    estado = forms.ChoiceField(required=False, choices=[("", "Todos los estados")] + list(Retiro.Estado.choices))
    desde = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        datos = super().clean()
        if datos.get("desde") and datos.get("hasta") and datos["desde"] > datos["hasta"]:
            raise forms.ValidationError("La fecha inicial debe ser anterior o igual a la final.")
        return datos
