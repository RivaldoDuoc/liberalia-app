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
    UsuariosListarView,     # lista de usuarios (Mantenedor de Usuarios)
    EditarUsuarioView, #para editar usuarios
    ToggleUsuarioActivoView, #para activar o desactivar botones (Habilitar / Deshabilitar)
    ficha_upload, # solo para probar carga archivo (validar posteriormente)
    LibroDeleteView,    
)

app_name = "roles"

urlpatterns = [
    path("", PanelView.as_view(), name="panel"),

    # Wizard de creación (EDITOR)
    path("editor/fichas/nueva/",      LibroCreateWizardView.as_view(), name="ficha_new"),
    path("editor/fichas/<str:isbn>/", LibroEditView.as_view(),         name="ficha_edit"),
    path("editor/fichas/cargar/", ficha_upload, name="ficha_upload"),
    path("editor/fichas/<str:isbn>/eliminar/", LibroDeleteView.as_view(), name="ficha_eliminar"),

    # Mantenedor de usuarios
    path("admin/usuarios/", UsuariosListarView.as_view(), name="usuarios_mantenedor"),
    path("admin/usuarios/<int:user_id>/editar/", EditarUsuarioView.as_view(), name="usuarios_editar"),
    path("admin/usuarios/<int:user_id>/toggle-activo/", ToggleUsuarioActivoView.as_view(), name="usuarios_toggle_activo"),
]

