from django.db import models
from roles.models import Editorial

class LibroFicha(models.Model):
    # Identificadores
    isbn  = models.CharField(max_length=32, unique=True)        # *
    ean   = models.CharField(max_length=32, blank=True, null=True)

    editorial = models.ForeignKey(                              # id_editorial *
        Editorial,
        on_delete=models.CASCADE,
        related_name="libros",
    )

    # Título / autores
    titulo        = models.CharField(max_length=255)            # *
    autor         = models.CharField(max_length=255)            # *
    autor_prologo = models.CharField(max_length=255, blank=True, null=True)
    traductor     = models.CharField(max_length=255, blank=True, null=True)
    ilustrador    = models.CharField(max_length=255, blank=True, null=True)

    # Ficha técnica
    tipo_tapa       = models.CharField(max_length=100)
    numero_paginas  = models.PositiveIntegerField()             # *
    alto_cm         = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    ancho_cm        = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    grosor_cm       = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    peso_gr         = models.PositiveIntegerField(blank=True, null=True)
    idioma_original = models.CharField(max_length=100, blank=True, null=True)

    numero_edicion   = models.PositiveIntegerField()            # *
    fecha_edicion    = models.DateField()                       # *
    pais_edicion     = models.CharField(max_length=100, blank=True, null=True)
    numero_impresion = models.PositiveIntegerField(blank=True, null=True)

    tematica = models.CharField(max_length=255, blank=True, null=True)

    # Comercial
    precio  = models.DecimalField(max_digits=10, decimal_places=2)        # *
    moneda  = models.CharField(max_length=10)                              # *
    descuento_distribuidor = models.DecimalField(                          # * (1 decimal)
        max_digits=5, decimal_places=1
    )

    # Contenido / media
    resumen_libro = models.TextField()                                     # *
    codigo_imagen = models.CharField(max_length=255)                       # * (string por ahora)
    rango_etario  = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ["titulo"]

    def __str__(self):
        return f"{self.isbn} · {self.titulo}"

