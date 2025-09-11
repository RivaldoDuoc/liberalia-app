from django.db import models
from roles.models import Editorial  # usamos la Editorial que ya existe

class LibroFicha(models.Model):
    isbn = models.CharField(max_length=32, unique=True)
    titulo = models.CharField(max_length=255)
    autor = models.CharField(max_length=255, blank=True)
    editorial = models.ForeignKey(
        Editorial,
        on_delete=models.CASCADE,   # si borras Editorial, se borran sus libros
        related_name="libros"
    )
    fecha_edicion = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["titulo"]

    def __str__(self):
        return f"{self.isbn} · {self.titulo}"



