from django.contrib import admin
from .models import LibroFicha

@admin.register(LibroFicha)
class LibroFichaAdmin(admin.ModelAdmin):
    list_display = ("isbn", "titulo", "autor", "editorial", "fecha_edicion")
    search_fields = ("isbn", "titulo", "autor", "editorial__nombre")
    list_filter = ("editorial",)



