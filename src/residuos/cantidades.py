import re
from decimal import Decimal
from django.core.exceptions import ValidationError


def validar_kg(valor, permitir_cero=False):
    texto = str(valor).strip()
    if not re.fullmatch(r"[0-9]+(?:[.,][0-9]{1,2})?", texto):
        raise ValidationError("Ingresa kilogramos con hasta dos decimales, sin separadores de miles.")
    peso = Decimal(texto.replace(",", "."))
    minimo = Decimal("0.00") if permitir_cero else Decimal("0.01")
    if peso < minimo or peso > Decimal("9999999.99"):
        raise ValidationError(f"El peso debe estar entre {minimo} y 9999999.99 kg.")
    return peso.quantize(Decimal("0.01"))
