
from django.db import models, connection
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date
from roles.models import Editorial  # FK existente en app Roles

# ============================
# Catálogos 
# ============================

class TipoTapa(models.Model):
    """
    Catálogo de tipos de encuadernación/tapa.
    Ej: 'Rústica', 'Tapa dura', 'Rústica con solapas', etc.
    """
    nombre = models.CharField(max_length=35, unique=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre


class Pais(models.Model):  # Modelo de país con código ISO
    """
    País normalizado con siglas ISO 3166-1 alpha-2 (CL, AR, ES, ...)
    """
    code = models.CharField(
        max_length=2,
        unique=True,  # No se repite entre países
        validators=[RegexValidator(r"^[A-Za-z]{2}$", "Use código ISO 3166-1 alpha-2, p. ej. 'CL'.")], # Solo letras
        help_text="Código ISO 3166-1 alpha-2 (2 letras).",
    )
    nombre = models.CharField(max_length=100)

    class Meta:
        ordering = ["nombre"]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.code.upper()})" 


class Moneda(models.Model): # Modelo de moneda con código ISO 4217
    """
    Moneda normalizada con código ISO 4217 (CLP, USD, EUR, ...)
    """
    code = models.CharField(
        max_length=3,
        unique=True,
        validators=[RegexValidator(r"^[A-Za-z]{3}$", "Use código ISO 4217, p. ej. 'CLP'.")],  # Solo letras
        help_text="Código ISO 4217 (3 letras).",
    )
    nombre = models.CharField(max_length=30) #nombre de la moneda
    simbolo = models.CharField(max_length=5, blank=True, null=True) # Ej: $, €

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code.upper()} – {self.nombre}" 


class Idioma(models.Model): # Modelo de idioma con código ISO 639-1
    """
    Idioma normalizado con código ISO 639-1 (es, en, fr, ...)
    """
    code = models.CharField(
        max_length=2,  # Código de 2 letras (ej: es, en, fr)
        unique=True,
        validators=[RegexValidator(r"^[A-Za-z]{2,5}$", "Use código ISO 639-1, p. ej. 'es'.")], # solo letras
        help_text="Código ISO 639-1 (2 letras).",
    )
    nombre = models.CharField(max_length=20) #nombre del idioma

    class Meta:
        ordering = ["nombre"]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.code.lower()})"


# ============================
# FICHA DEL LIBRO
# ============================

class LibroFicha(models.Model):
    # Identificadores
    isbn  = models.CharField(max_length=16, unique=True, db_index=True)   # usado en panel/búsquedas (Largo 16, por si tienes guiones)
    ean   = models.CharField(max_length=16, blank=True, null=True)

    editorial = models.ForeignKey(
        Editorial,
        on_delete=models.CASCADE,
        related_name="libros",
    )

    # Título / autores
    titulo        = models.CharField(max_length=100, db_index=True)  # usado en panel/búsquedas
    subtitulo     = models.CharField(max_length=100, blank=True, null=True)
    autor         = models.CharField(max_length=100, db_index=True)  # 120 por autores múltiples
    autor_prologo = models.CharField(max_length=40, blank=True, null=True)
    traductor     = models.CharField(max_length=40, blank=True, null=True)
    ilustrador    = models.CharField(max_length=60, blank=True, null=True)

    # Ficha técnica (normalizados donde aporta)

    
    tipo_tapa = models.ForeignKey(TipoTapa, on_delete=models.PROTECT)  # sin null/blank
    numero_paginas  = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    alto_cm         = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    ancho_cm        = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    grosor_cm       = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    peso_gr         = models.PositiveIntegerField(blank=True, null=True)

    idioma_original = models.ForeignKey(Idioma, on_delete=models.PROTECT)

    numero_edicion   = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    fecha_edicion    = models.DateField(db_index=True)  # usado en panel/búsquedas

    
    pais_edicion = models.ForeignKey(Pais, on_delete=models.PROTECT)

    numero_impresion = models.PositiveIntegerField(blank=True, null=True)

    tematica = models.CharField(max_length=60, blank=True, null=True) #texto libre

    # COMERCIAL
    precio  = models.DecimalField(max_digits=10, decimal_places=2)
    
  
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT) #lo he dejado nuleable
    
    # Porcentaje 0.0–99.9 (ej: 12.5 = 12.5%)
    descuento_distribuidor = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(99.9)],
        help_text="Porcentaje de 0.0 a 99.9",
    )
    
    # Contenido / media
    resumen_libro = models.TextField()

    #IMPORTANTE : PERMITO NULOS TEMPORALMENTE PARA CARGAR EL BASE DE DATOS
    codigo_imagen = models.CharField(max_length=120, blank=True, null=True) #lo he dejado nuleable 
    rango_etario  = models.CharField(max_length=30, blank=True, null=True)

    class Meta:
        ordering = ["titulo"]
        indexes = [
            # Filtros/orden usados en PANEL y VISTAS
            models.Index(fields=["isbn"]),
            models.Index(fields=["titulo"]),
            models.Index(fields=["autor"]),
            models.Index(fields=["fecha_edicion"]),
            models.Index(fields=["editorial"]),
        ]

    def __str__(self) -> str:
        return f"{self.isbn} · {self.titulo}"
    
    # llamar a la función fn_calcula_pvp() pasando el ID del libro
    @property
    def pvp_calculado(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT fn_calcula_pvp(%s)", [self.id])
            result = cursor.fetchone()
            return result[0] if result else None
  


# ============================
# VARIABLES EXTERNAS
# ============================
class VariableExterna(models.Model):
    TIPO_IVA = "IVA"
    TIPO_TC  = "TC"
    TIPO_CHOICES = [
        (TIPO_IVA, "IVA"),
        (TIPO_TC,  "Tipo de cambio"),
    ]

    tipo   = models.CharField(max_length=10, choices=TIPO_CHOICES)   # IVA o TC
    moneda = models.ForeignKey("catalogo.Moneda", null=True, blank=True, on_delete=models.CASCADE)

    # Nueva columna para redundancia simple (ej: "USD", "EUR", "IVA")
    nombre_tipo = models.CharField(max_length=10, blank=True, null=True, help_text="Ej: USD, EUR, IVA")

    # Renombrado: antes 'fecha'
    fecha_actualizacion = models.DateField(null=True, blank=True)

    valor  = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(0)])

    class Meta:
        unique_together = ("tipo", "moneda")
        indexes = [
            models.Index(fields=["tipo", "moneda"]),
            models.Index(fields=["nombre_tipo"]),
        ]
        ordering = ["tipo", "moneda"]

    def __str__(self):
        return f"{self.tipo} {self.nombre_tipo or ''} = {self.valor}"
