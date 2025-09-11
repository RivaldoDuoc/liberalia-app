# catalogo/urls.py
from django.urls import path
from .views import libro_detalle  # vista simple por ahora

app_name = "catalogo"

urlpatterns = [
    path("libro/<str:isbn>/", libro_detalle, name="libro_detalle"),
]
