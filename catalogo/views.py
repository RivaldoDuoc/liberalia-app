# catalogo/views.py
from django.shortcuts import render, get_object_or_404
from .models import LibroFicha

def libro_detalle(request, isbn):
    """
    Muestra la ficha del libro por ISBN.
    (Por ahora sin chequeo de rol; lo agregamos luego.)
    """
    obj = get_object_or_404(LibroFicha.objects.select_related("editorial"), isbn=isbn)
    return render(request, "catalogo/libro_detalle.html", {"obj": obj})



