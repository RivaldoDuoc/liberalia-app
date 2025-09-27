# catalogo/urls.py
from django.urls import path
from .views import libro_detalle, actualizar_tc  # vista simple por ahora


app_name = "catalogo"

urlpatterns = [
    path("libro/<str:isbn>/", libro_detalle, name="libro_detalle"),
    path("api/actualizar-tc/", actualizar_tc, name="actualizar_tc"),
]