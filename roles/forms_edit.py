# roles/forms_edit.py
from django import forms
from django.core.exceptions import ValidationError

from catalogo.models import LibroFicha
# Reutilizamos utilidades ya definidas en forms.py
from roles.forms import BaseEditorForm, _normalize_code, _is_valid_isbn10, _is_valid_ean13


class LibroEditForm(BaseEditorForm):
    class Meta:
        model = LibroFicha
        fields = [
            "isbn", "ean", "editorial", "titulo", "subtitulo",
            "autor", "autor_prologo", "traductor", "ilustrador",
            "tipo_tapa", "numero_paginas",
            "alto_cm", "ancho_cm", "grosor_cm", "peso_gr",
            "idioma_original", "numero_edicion", "fecha_edicion",
            "pais_edicion", "numero_impresion", "tematica",
            "precio", "moneda", "descuento_distribuidor",
            "resumen_libro", "codigo_imagen", "rango_etario",
        ]
        widgets = {
            "fecha_edicion": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "resumen_libro": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.allow_change_isbn = kwargs.pop("allow_change_isbn", False)
        super().__init__(*args, **kwargs)
        if not self.allow_change_isbn and "isbn" in self.fields:
            self.fields["isbn"].disabled = True

    def clean_isbn(self):
        raw = self.cleaned_data.get("isbn", "")
        if not self.allow_change_isbn:
            return self.instance.isbn
        code = _normalize_code(raw)
        if len(code) == 10:
            if not _is_valid_isbn10(code):
                raise ValidationError("ISBN-10 inválido")
        elif len(code) == 13:
            if not _is_valid_ean13(code):
                raise ValidationError("ISBN-13 inválido")
        else:
            raise ValidationError("El ISBN debe tener 10 o 13 caracteres")
        return code

    def clean_ean(self):
        raw = self.cleaned_data.get("ean", "")
        if not raw:
            return raw
        code = _normalize_code(raw)
        if not _is_valid_ean13(code):
            raise ValidationError("EAN-13 inválido")
        return code

    def clean_descuento_distribuidor(self):
        val = self.cleaned_data.get("descuento_distribuidor")
        if val is None or not (0 <= float(val) <= 99.9):
            raise ValidationError("El descuento debe estar entre 0.0 y 99.9%.")
        return val
