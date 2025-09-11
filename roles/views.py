# -----------------------------------------------------------------------------
# Tres paneles por rol. Usamos un decorador sencillo para exigir el rol esperado.
# Si no coincide, redirige (ajusta 'home-root' por la vista que prefieras).
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# Paneles de usuario y utilidades de filtrado para la app "roles":
# - Define tres paneles según el rol (ADMIN, EDITOR, CONSULTOR) con acceso protegido.
# - Incluye decoradores y mixins para validar roles y redirigir usuarios no autorizados.
# - Construye querysets de libros filtrados por editorial, fechas y permisos de rol.
# - Permite exportar listas a CSV y proporciona vistas stub para crear/editar fichas de libros.
# -----------------------------------------------------------------------------


from __future__ import annotations
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpRequest
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.views import View


from .models import Profile, UsuarioEditorial
from catalogo.models import LibroFicha


import csv
from datetime import datetime


def _role(user):
    """Devuelve el rol del usuario o None si no tiene profile."""
    # Aquí lo que hacemos es usar getattr de forma encadenada para evitar errores
    # en caso de que el usuario no tenga profile asociado.
    # Si existe user.profile.role lo devolvemos, si no, retornamos None.
    return getattr(getattr(user, "profile", None), "role", None)


def role_required(expected_role):
    """
    Decorador que exige:
      - estar autenticado
      - tener el rol 'expected_role'
    """
    # Definimos un decorador que envolverá la vista original.
    def decorator(viewfunc):
        @login_required
        def _wrapped(request, *args, **kwargs):
            if _role(request.user) != expected_role:
                return redirect("home-root")  # cámbialo por 403 si prefieres
            return viewfunc(request, *args, **kwargs)
        return _wrapped
    return decorator


@role_required(Profile.ROLE_ADMIN)
def panel_admin(request):
    # En este panel construimos el contexto con el usuario y su rol
    ctx = {"user_obj": request.user, "role": request.user.profile.role}
    # Renderizamos la plantilla específica para el panel de administrador
    return render(request, "roles/panel_admin.html", ctx)


@role_required(Profile.ROLE_EDITOR)
def panel_editor(request):
    # Aquí hacemos lo mismo, pero para el rol de editor
    ctx = {"user_obj": request.user, "role": request.user.profile.role}
    return render(request, "roles/panel_editor.html", ctx)


@role_required(Profile.ROLE_CONSULTOR)
def panel_consultor(request):
    # Y en este caso repetimos la lógica, pero para el rol de consultor
    ctx = {"user_obj": request.user, "role": request.user.profile.role}
    return render(request, "roles/panel_consultor.html", ctx)




# ----------------------------
# Utils de filtrado/ordenación
# ----------------------------
ALLOWED_SORTS = {
    "isbn": "isbn",
    "titulo": "titulo",
    "autor": "autor",
    "editorial": "editorial__nombre",
    "fecha": "fecha_edicion",
}

def _parse_date(s: str | None):
    if not s:
        return None
    # <input type="date"> entrega 'YYYY-MM-DD'
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None

def build_queryset_for_user(user, params):
    """
    Construye un queryset de LibroFicha respetando:
    - Búsqueda por nombre de editorial (q)
    - Rango de fechas (date_from, date_to)
    - Límite por rol (editor ve solo sus editoriales)
    - Ordenamiento (?sort=)
    """
    qs = LibroFicha.objects.select_related("editorial")
    q = (params.get("q") or "").strip()
    date_from = _parse_date(params.get("date_from"))
    date_to   = _parse_date(params.get("date_to"))
    sort_key  = params.get("sort") or ""

    if q:
        qs = qs.filter(editorial__nombre__icontains=q)

    if date_from:
        qs = qs.filter(fecha_edicion__gte=date_from)
    if date_to:
        qs = qs.filter(fecha_edicion__lte=date_to)

    # Restricción por rol (EDITOR: solo sus editoriales)
    role = getattr(getattr(user, "profile", None), "role", None)
    if role == Profile.ROLE_EDITOR:
        # Todas las editoriales asociadas al usuario
        ed_ids = UsuarioEditorial.objects.filter(user=user).values_list("editorial_id", flat=True)
        qs = qs.filter(editorial_id__in=list(ed_ids))

    # Orden
    if sort_key in ALLOWED_SORTS:
        qs = qs.order_by(ALLOWED_SORTS[sort_key])

    return qs


# ----------------------------
# Vistas de lista
# ----------------------------
class BasePanelView(LoginRequiredMixin, View):
    template_name = ""       # lo define cada subclase
    role_required = None     # opcional (Profile.ROLE_...)

    def get(self, request: HttpRequest):
        # Si se pide exportación CSV
        if request.GET.get("export") == "csv":
            return self.export_csv(request)

        qs = build_queryset_for_user(request.user, request.GET)
        ctx = {
            "rows": qs[:1000],  # limitada a 1000 registros (podemos cambiarla por otras opciones de paginación)
            "q": request.GET.get("q", ""),
            "date_from": request.GET.get("date_from", ""),
            "date_to": request.GET.get("date_to", ""),
            "sort": request.GET.get("sort", ""),
            "ALLOWED_SORTS": ALLOWED_SORTS,
        }

        # valida rol si corresponde
        role = getattr(getattr(request.user, "profile", None), "role", None)
        if self.role_required and role != self.role_required:
            return redirect("home-root")  # o 403

        return render(request, self.template_name, ctx)

    def export_csv(self, request: HttpRequest) -> HttpResponse:
        qs = build_queryset_for_user(request.user, request.GET)

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="libros.csv"'
        writer = csv.writer(response)
        writer.writerow(["ISBN", "TÍTULO", "AUTOR", "EDITORIAL", "FECHA_EDICIÓN"])

        for r in qs:
            writer.writerow([
                r.isbn,
                r.titulo,
                r.autor,
                r.editorial.nombre,
                r.fecha_edicion.isoformat() if r.fecha_edicion else "",
            ])
        return response


class PanelAdminView(BasePanelView):
    template_name = "roles/panel_admin.html"
    role_required = Profile.ROLE_ADMIN


class PanelConsultorView(BasePanelView):
    template_name = "roles/panel_consultor.html"
    role_required = Profile.ROLE_CONSULTOR


class PanelEditorView(BasePanelView):
    template_name = "roles/panel_editor.html"
    role_required = Profile.ROLE_EDITOR



# ----------------------------
# SOLO PARA NO MOSTRAR ERROR ... TEMPLATES POR CREAR
# Vistas provisionales para crear/editar fichas de libros.
# Solo existen para evitar errores mientras se crean los templates definitivos.
# Estas clases deben eliminarse una vez estén disponibles los templates finales.
# ----------------------------
class LibroCreateView(LoginRequiredMixin, View):
    def get(self, request):
        # TODO: template de creación
        return HttpResponse("Nueva ficha (formulario)") 

class LibroEditView(LoginRequiredMixin, View):
    def get(self, request, isbn):
        # TODO: template de edición
        return HttpResponse(f"Editar ficha {isbn}")
