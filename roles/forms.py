from django import forms
from django.core.exceptions import ValidationError
import re

from catalogo.models import LibroFicha, TipoTapa, Moneda, Idioma, Pais
from roles.models import UsuarioEditorial, Editorial

# ===========================
# validaciones
# ===========================
_ISBN10_RE = re.compile(r"^\d{9}[\dX]$")   # 9 dígitos + dígito o X
_DIGITS_RE = re.compile(r"^\d+$")

def _normalize_code(raw: str) -> str:
    """Quita guiones/espacios y pasa a mayúsculas."""
    return re.sub(r"[\s-]+", "", (raw or "")).upper()

def _is_valid_isbn10(code: str) -> bool:
    """
    ISBN-10 con dígito verificador (módulo 11). 'X' equivale a 10.
    Regla: sum(d_i * w_i) % 11 == 0 con w_i = 10..1
    """
    if not _ISBN10_RE.match(code):
        return False
    total = 0
    for i, ch in enumerate(code):           # i = 0..9 -> peso = 10..1
        weight = 10 - i
        val = 10 if ch == "X" else int(ch)
        total += val * weight
    return total % 11 == 0

def _is_valid_ean13(code: str) -> bool:
    """
    EAN-13 / ISBN-13 (módulo 10). Último dígito es verificador.
    """
    if len(code) != 13 or not _DIGITS_RE.match(code):
        return False
    digits = [int(c) for c in code]
    checksum = sum(d if (i % 2 == 0) else d * 3 for i, d in enumerate(digits[:-1]))
    check = (10 - (checksum % 10)) % 10
    return check == digits[-1]


# ===========================
# Base para los forms del wizard
# ===========================
class BaseEditorForm(forms.ModelForm):
    """
    - Inyecta request_user para limitar editoriales cuando sea EDITOR.
    - Homologa mensaje de campo obligatorio.
    """
    def __init__(self, *args, **kwargs):
        self._request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)

        for f in self.fields.values():
            if f.required:
                f.error_messages.setdefault("required", "Este campo es obligatorio.")

        if self._request_user is not None:
            self.limit_editoriales(self._request_user)

    def limit_editoriales(self, user):
        if hasattr(user, "profile") and getattr(user.profile, "role", None) == "EDITOR":
            ed_ids = UsuarioEditorial.objects.filter(user=user).values_list("editorial_id", flat=True)
            if "editorial" in self.fields:
                self.fields["editorial"].queryset = Editorial.objects.filter(id__in=list(ed_ids))


# ===========================
# PASO 1: Identificación
# ===========================
class LibroIdentForm(BaseEditorForm):
    class Meta:
        model = LibroFicha
        fields = [
            "isbn", "ean", "editorial",
            "titulo", "subtitulo",
            "autor", "autor_prologo", "traductor", "ilustrador",
        ]
        widgets = {
            "isbn": forms.TextInput(attrs={
                "maxlength": 16, "class": "form-control", "required": True,
                "placeholder": "ISBN-10 o ISBN-13"
            }),
            "ean": forms.TextInput(attrs={
                "maxlength": 16, "class": "form-control",
                
            }),
            "editorial": forms.Select(attrs={"class": "form-select", "required": True}),
            "titulo": forms.TextInput(attrs={"maxlength": 100, "class": "form-control", "required": True}),
            "subtitulo": forms.TextInput(attrs={"maxlength": 100, "class": "form-control"}),
            "autor": forms.TextInput(attrs={"maxlength": 100, "class": "form-control", "required": True}),
            "autor_prologo": forms.TextInput(attrs={"maxlength": 40, "class": "form-control"}),
            "traductor": forms.TextInput(attrs={"maxlength": 40, "class": "form-control"}),
            "ilustrador": forms.TextInput(attrs={"maxlength": 60, "class": "form-control"}),
        }
        error_messages = {
                    'isbn': {
                        'unique': "ISBN ya existe",
                        'required': "Campo obligatorio.",
                    }                      
                }
    def clean_isbn(self):
        raw = self.cleaned_data.get("isbn", "")
        code = _normalize_code(raw)
        if len(code) == 10:
            if not _is_valid_isbn10(code):
                raise ValidationError("ISBN-10 inválido")
        elif len(code) == 13:
            if not _is_valid_ean13(code):
                raise ValidationError("ISBN-13 inválido")
        else:
            raise ValidationError("El ISBN debe tener 10 o 13 caracteres")
        return code  # se guarda normalizado

    def clean_ean(self):
        raw = self.cleaned_data.get("ean", "")
        if not raw:
            return raw
        code = _normalize_code(raw)
        if not _is_valid_ean13(code):
            raise ValidationError("EAN-13 inválido")
        return code  # se guarda normalizado


# ===========================
# PASO 2: Ficha técnica
# ===========================
class LibroTecnicaForm(BaseEditorForm):
    class Meta:
        model = LibroFicha
        fields = [
            "tipo_tapa", "numero_paginas",
            "alto_cm", "ancho_cm", "grosor_cm", "peso_gr",
            "idioma_original", "numero_edicion", "fecha_edicion",
            "pais_edicion", "numero_impresion", "tematica",
        ]
        widgets = {
            "tipo_tapa": forms.Select(attrs={"class": "form-select", "required": True}),
            "numero_paginas": forms.NumberInput(attrs={"class": "form-control", "min": 1, "required": True}),
            "alto_cm": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "ancho_cm": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "grosor_cm": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "peso_gr": forms.NumberInput(attrs={"class": "form-control"}),
            "idioma_original": forms.Select(attrs={"class": "form-select", "required": True}),
            "numero_edicion": forms.NumberInput(attrs={"class": "form-control", "min": 1, "required": True}),
            "fecha_edicion": forms.DateInput(attrs={"type": "date", "class": "form-control", "required": True}),
            "pais_edicion": forms.Select(attrs={"class": "form-select", "required": True}),
            "numero_impresion": forms.NumberInput(attrs={"class": "form-control"}),
            "tematica": forms.TextInput(attrs={"maxlength": 60, "class": "form-control"}),
        }


# ===========================
# PASO 3: Comercial
# ===========================
class LibroComercialForm(BaseEditorForm):
    class Meta:
        model = LibroFicha
        fields = ["precio", "moneda", "descuento_distribuidor", "resumen_libro", "codigo_imagen", "rango_etario"]
        widgets = {
            "precio": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "required": True}),
            "moneda": forms.Select(attrs={"class": "form-select", "required": True}),
            "descuento_distribuidor": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "required": True}),
            "resumen_libro": forms.Textarea(attrs={"class": "form-control", "rows": 6, "required": True}),
            "codigo_imagen": forms.TextInput(attrs={"maxlength": 120, "class": "form-control"}),
            "rango_etario": forms.TextInput(attrs={"maxlength": 30, "class": "form-control"}),
        }

    def clean_descuento_distribuidor(self):
        val = self.cleaned_data.get("descuento_distribuidor")
        if val is None or not (0 <= float(val) <= 99.9):
            raise ValidationError("El descuento debe estar entre 0.0 y 99.9%.")
        return val
