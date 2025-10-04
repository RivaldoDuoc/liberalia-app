# -------------------------------------------------------------------------------
# Rutas (URLs) de la app "roles":
# - Define los paneles de usuario según el rol (ADMIN, EDITOR, CONSULTOR).
# - Incluye vistas para crear y editar libros desde el panel del editor.
# -------------------------------------------------------------------------------

from . import views
from django.urls import path
from .views import (
    PanelView,                 # panel unificado
    LibroCreateWizardView,     # wizard de creación de fichas en tres pasos
    LibroEditView,             # editar (para los templates de edición)
    UsuariosListarView,     # lista de usuarios (Mantenedor de Usuarios)
    EditarUsuarioView, #para editar usuarios
    InvitarUsuarioView, #invitar usuarios
    ToggleUsuarioActivoView, #para activar o desactivar botones (Habilitar / Deshabilitar)
    LibroDeleteView,
    EditorialesListarView,
    EditarEditorialView,
    ToggleEditorialEstadoView,    
    ficha_upload,
    upload_fichas_json,
    descargar_plantilla_excel
)

app_name = "roles"

urlpatterns = [
    path("", PanelView.as_view(), name="panel"),

    # Wizard de creación (EDITOR)
    path("editor/fichas/nueva/",      LibroCreateWizardView.as_view(), name="ficha_new"),
    path("editor/fichas/cargar/", ficha_upload, name="ficha_upload"),
    path("editor/fichas/upload-json/", upload_fichas_json, name="ficha_upload_json"),
    path('descargar/descargar_plantilla_excel/', descargar_plantilla_excel, name='descargar_plantilla_excel'),
    path("editor/fichas/<str:isbn>/", LibroEditView.as_view(),         name="ficha_edit"),
    path("editor/fichas/<str:isbn>/eliminar/", LibroDeleteView.as_view(), name="ficha_eliminar"),

    # Mantenedor de usuarios
    path("admin/usuarios/", UsuariosListarView.as_view(), name="usuarios_mantenedor"),
    path("admin/usuarios/<int:user_id>/editar/", EditarUsuarioView.as_view(), name="usuarios_editar"),
    path("admin/usuarios/<int:user_id>/toggle-activo/", ToggleUsuarioActivoView.as_view(), name="usuarios_toggle_activo"),
    path("admin/usuarios/invitar/", InvitarUsuarioView.as_view(), name="usuarios_invitar"),

    # Mantenedor de Editoriales
    path("admin/editoriales/", EditorialesListarView.as_view(), name="editoriales_mantenedor"),
    path("admin/editoriales/<int:editorial_id>/editar/", EditarEditorialView.as_view(), name="editoriales_editar"),
    path("admin/editoriales/<int:editorial_id>/toggle/", ToggleEditorialEstadoView.as_view(), name="editoriales_toggle"),
    path("admin/editoriales/crear/", views.editoriales_crear, name="editoriales_crear"),

    # Nueva ruta para upload_portada
    path('upload-portada/', views.upload_portada, name='upload_portada'),
]

