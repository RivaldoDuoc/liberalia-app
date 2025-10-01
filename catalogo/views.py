# catalogo/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, F, Func, DecimalField
from .models import LibroFicha

#Actualización tipo de cambio
from django.http import JsonResponse, HttpResponseForbidden
from django.conf import settings
from catalogo.models import VariableExterna, Moneda
from catalogo.services import obtener_tipo_cambio
from decimal import Decimal

@login_required
def libro_detalle(request, isbn):
    # Normaliza ISBN (acepta con o sin guiones/espacios)
    isbn_norm = isbn.replace("-", "").replace(" ", "").strip()

    # Usamos annotate para traer el PVP desde MySQL
    qs = (
        LibroFicha.objects
        .select_related("editorial", "moneda")
        .annotate(pvp=FnCalculaPVP(F('id')))   # <-- alias claro 'pvp'
        .filter(
            Q(isbn=isbn) |
            Q(isbn=isbn_norm) |
            Q(isbn__iexact=isbn)
        )
    )

    # get_object_or_404 sobre el mismo queryset anotado
    obj = get_object_or_404(qs)

    return render(
        request,
        "catalogo/libro_detalle.html",
        {
            "obj": obj,      # incluye obj.pvp gracias al annotate
            "pvp": obj.pvp,  # por si te resulta más cómodo en el template
        }
    )

def actualizar_tc(request):
    # Seguridad por token (si no quieres token, elimina este bloque)
    token = request.GET.get("token")
    if token != getattr(settings, "CRON_SECRET_TOKEN", None):
        return HttpResponseForbidden("Token inválido")

    resultados = []

    # indicador en la API -> código ISO en tu tabla Moneda
    for indicador, iso in {"dolar": "USD", "euro": "EUR"}.items():
        # 1) obtengo datos desde la API
        fecha, valor = obtener_tipo_cambio(indicador)

        # 2) obtengo la moneda (asegúrate de tener USD/EUR creados)
        moneda = Moneda.objects.get(code__iexact=iso)

        # 3) actualizo/creo SIEMPRE la misma fila por (tipo, moneda)
        obj, created = VariableExterna.objects.update_or_create(
            tipo="TC",
            moneda=moneda,                 # <-- lookup
            defaults={
                "nombre_tipo": iso,        # "USD" / "EUR" (opcional, pero lo pediste)
                "valor": Decimal(str(valor)),
                "fecha_actualizacion": fecha,  # <-- nombre nuevo del campo
            },
        )

        resultados.append({
            "moneda": iso,
            "fecha": fecha.isoformat(),
            "valor": str(obj.valor),
            "created": created,
        })

    return JsonResponse({"ok": True, "resultados": resultados})

 #El método tiene que hacer que el precio del libro sea modificado por la información que tiene la editorial
    
def precio_final_sugerido(self) -> Decimal:
        """
        Calcula el precio sugerido considerando los porcentajes
        definidos en la editorial.
        """
        total = (
            (self.editorial.cargo_origen or 0) +
            (self.editorial.recargo_fletes or 0) +
            (self.editorial.gastos_indirectos or 0) +
            (self.editorial.margen_comercializacion or 0)
        )
        return self.precio * (Decimal("1") + Decimal(total) / Decimal("100"))


# Para la función MySQL fn_calcula_pvp(id) ---
class FnCalculaPVP(Func):
    function = 'fn_calcula_pvp'
    output_field = DecimalField(max_digits=12, decimal_places=0)
