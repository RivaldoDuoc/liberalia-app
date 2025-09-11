from django.urls import path
from .views import panel_admin, panel_consultor, panel_editor
from .views import PanelConsultorView  

app_name = "roles"

urlpatterns = [
    path("admin/",     panel_admin,     name="panel_admin"),
    path("editor/",    panel_editor,    name="panel_editor"),
    path("consultor/", PanelConsultorView.as_view(), name="panel_consultor"),
    #path("consultor/", panel_consultor, name="panel_consultor"),
]
