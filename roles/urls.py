# -------------------------------------------------------------------------------
# Rutas (URLs) de la app "roles":
# - Define los paneles de usuario según el rol (ADMIN, EDITOR, CONSULTOR).
# - Incluye vistas para crear y editar libros desde el panel del editor.
# -------------------------------------------------------------------------------


from django.urls import path
from .views import (
    PanelView,                 # panel unificado
    LibroCreateWizardView,     # wizard de creación de fichas en tres pasos
    LibroEditView,             # editar (para los templates de edición)
    ficha_upload # solo para probar carga archivo (validar posteriormente)
)

app_name = "roles"

urlpatterns = [
    path("panel/", PanelView.as_view(), name="panel"),

    # Wizard de creación (EDITOR)
    path("editor/fichas/nueva/",      LibroCreateWizardView.as_view(), name="ficha_new"),
    path("editor/fichas/<str:isbn>/", LibroEditView.as_view(),         name="ficha_edit"),
    path("editor/fichas/cargar/", ficha_upload, name="ficha_upload"),
]