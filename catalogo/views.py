# catalogo/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from .models import LibroFicha

def libro_detalle(request, isbn):
    
    # 1) Rol del usuario logueado 
    role = getattr(getattr(request.user, "profile", None), "role", None)

    # 2) SOLO CONSULTOR (por ahora)
    if role != "CONSULTOR":
        return redirect("home-root")

    # --- Normaliza el ISBN que viene por URL (quita guiones y espacios) ---
    isbn_norm = isbn.replace("-", "").replace(" ", "").strip()

    # 3) Trae el libro:
    #    intenta primero con lo que viene tal cual, y si no, con el normalizado
    obj = get_object_or_404(
        LibroFicha.objects.select_related("editorial").filter(
            Q(isbn=isbn) | Q(isbn=isbn_norm) | Q(isbn__iexact=isbn)
        )
    )

    # 4) Render
    return render(request, "catalogo/libro_detalle.html", {"obj": obj})






