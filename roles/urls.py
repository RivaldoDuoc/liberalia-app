# -------------------------------------------------------------------------------
# Rutas (URLs) de la app "roles":
# - Define los paneles de usuario según el rol (ADMIN, EDITOR, CONSULTOR).
# - Incluye vistas para crear y editar libros desde el panel del editor.
# -------------------------------------------------------------------------------


from django.urls import path
from .views import (
    PanelView, LibroCreateView, LibroEditView
    
)

app_name = "roles"

urlpatterns = [
    # Ruta única del panel (sirve para ADMIN / EDITOR / CONSULTOR)
    path("panel/", PanelView.as_view(), name="panel"),

    # Editor: crear/editar (stubs)
    path("editor/fichas/nueva/",        LibroCreateView.as_view(), name="ficha_new"),
    path("editor/fichas/<str:isbn>/",   LibroEditView.as_view(),   name="ficha_edit"),
]
