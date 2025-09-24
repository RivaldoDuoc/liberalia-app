from __future__ import annotations
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse, HttpRequest, JsonResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages

from .models import Profile, UsuarioEditorial, Editorial
from catalogo.models import LibroFicha

import csv
from datetime import datetime, date, datetime as dt
from django.urls import reverse
from .forms import LibroIdentForm, LibroTecnicaForm, LibroComercialForm
from decimal import Decimal  
from django import forms

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from urllib.parse import urlencode
from .forms import EditarUsuarioForm

#PARA EDITAR
from .forms_edit import LibroEditForm
#PARA MANTENEDOR DE USUARIOS
from django.contrib.auth import get_user_model
from django.views.generic import ListView
from django.db.models import Q, Prefetch


# ----------------------------
# Helpers de rol
# ----------------------------
def _role(user):
    """Devuelve el rol del usuario o None si no tiene profile."""
    return getattr(getattr(user, "profile", None), "role", None)


def role_required(expected_role):
    """Decorador que exige login y rol esperado."""
    def decorator(viewfunc):
        @login_required
        def _wrapped(request, *args, **kwargs):
            if _role(request.user) != expected_role:
                return redirect("home-root")  # cámbialo por un 403 si prefieres
            return viewfunc(request, *args, **kwargs)
        return _wrapped
    return decorator


def _panel_flags(user):
    """
    Banderas de UI / capacidades por rol para el template unificado.
    """
    role = _role(user)
    is_admin = role == Profile.ROLE_ADMIN
    is_editor = role == Profile.ROLE_EDITOR
    is_consultor = role == Profile.ROLE_CONSULTOR

    if is_admin:
        role_label = "ADMIN"
        role_badge_class = "bg-danger"
    elif is_editor:
        role_label = "EDITOR"
        role_badge_class = "bg-secondary"
    else:
        role_label = "CONSULTOR"
        role_badge_class = "bg-secondary"

    return {
        "is_admin": is_admin,
        "is_editor": is_editor,
        "is_consultor": is_consultor,
        "role_label": role_label,
        "role_badge_class": role_badge_class,

        # Capacidades por rol (alineadas a tus 3 plantillas originales)
        "can_download": is_admin or is_consultor,   # Admin/Consultor tenían "Descargar"
        "can_create": is_editor,                    # Editor tenía "Crear"
        "can_edit": is_editor,                      # Editor tenía "Editar"
        "show_detail": is_admin or is_consultor,    # Admin/Consultor mostraban "Detalle"
        "detail_disabled": "disabled",

        # Nombres de URL (ajusta si tus names cambian)
        "create_url_name": "roles:ficha_new" if is_editor else None,
        "edit_url_name": "roles:ficha_edit" if is_editor else None,
    }


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
    - Para ADMIN/CONSULTOR: búsqueda SOLO por EDITORIAL (q)
    - Para EDITOR: búsqueda por campo TITULO (q_titulo) e ISBN (q_isbn)
    - Rango de fechas (date_from, date_to)
    - Límite por rol (editor ve solo sus editoriales)
    - Ordenamiento (?sort=)
    """
    qs = LibroFicha.objects.select_related("editorial")

    role = getattr(getattr(user, "profile", None), "role", None)

    # --- filtros por texto según rol ---
    if role == Profile.ROLE_EDITOR:
        q_titulo = (params.get("q_titulo") or "").strip()
        q_isbn   = (params.get("q_isbn") or "").strip()
        if q_titulo:
            qs = qs.filter(titulo__icontains=q_titulo) # busca títulos que contengan el texto (sin distinguir mayúsc/minúsc)
        if q_isbn:
            qs = qs.filter(isbn__icontains=q_isbn)   # busca ISBN que contengan la cadena de caracteres
    else:
        q = (params.get("q") or "").strip()
        if q:
            qs = qs.filter(editorial__nombre__icontains=q)

    # --- fechas ---
    date_from = _parse_date(params.get("date_from"))  # obtiene y convierte la fecha inicial desde los parámetros
    date_to   = _parse_date(params.get("date_to")) # obtiene y convierte la fecha final desde los parámetros
    if date_from:
        qs = qs.filter(fecha_edicion__gte=date_from)  # filtra registros con fecha_edicion mayor o igual a date_from
    if date_to:
        qs = qs.filter(fecha_edicion__lte=date_to) # filtra registros con fecha_edicion menor o igual a date_to

    # --- restricción por rol (EDITOR: solo sus editoriales) ---
    if role == Profile.ROLE_EDITOR:
        ed_ids = UsuarioEditorial.objects.filter(user=user).values_list("editorial_id", flat=True)
        qs = qs.filter(editorial_id__in=list(ed_ids))

    # --- orden ---
    sort_key = params.get("sort") or ""
    if sort_key in ALLOWED_SORTS:
        qs = qs.order_by(ALLOWED_SORTS[sort_key])

    return qs


# -----------------------------------------------
# Vistas de lista (template unificado)
# -----------------------------------------------

class BasePanelView(LoginRequiredMixin, View):
    template_name = "roles/panel.html"
    role_required = None
    paginate_by = 8  # registros por página

    def get(self, request: HttpRequest):
        # Exportación CSV
        if request.GET.get("export") == "csv":
            role = getattr(getattr(request.user, "profile", None), "role", None)
            if self.role_required and role != self.role_required:
                return redirect("home-root")
            flags = _panel_flags(request.user)
            if not flags.get("can_download"):
                return HttpResponse("No autorizado", status=403)
            return self.export_csv(request)

        qs = build_queryset_for_user(request.user, request.GET)

        # Paginación
        page = request.GET.get("page", 1)
        paginator = Paginator(qs, self.paginate_by)
        try:
            rows = paginator.page(page)
        except PageNotAnInteger:
            rows = paginator.page(1)
        except EmptyPage:
            rows = paginator.page(paginator.num_pages)

        # >>> NUEVO: querystring base sin 'page'
        params = request.GET.copy()
        params.pop('page', None)
        base_qs = params.urlencode()
        # <<<

        ctx = {
            "rows": rows,
            "paginator": paginator,
            "page_obj": rows,
            "is_paginated": rows.has_other_pages(),
            "q": request.GET.get("q", ""),
            "q_titulo": request.GET.get("q_titulo", ""),
            "q_isbn": request.GET.get("q_isbn", ""),
            "date_from": request.GET.get("date_from", ""),
            "date_to": request.GET.get("date_to", ""),
            "sort": request.GET.get("sort", ""),
            "ALLOWED_SORTS": ALLOWED_SORTS,
            "base_qs": base_qs,   # >>> añade esto
        }

        role = getattr(getattr(request.user, "profile", None), "role", None)
        if self.role_required and role != self.role_required:
            return redirect("home-root")

        ctx.update(_panel_flags(request.user))
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


class PanelView(BasePanelView):
    """Panel unificado; el template condiciona por rol."""
    role_required = None

    def get(self, request, *args, **kwargs):
        # Asegura que el usuario tenga un rol válido antes de renderizar
        role = _role(request.user)
        if role not in (Profile.ROLE_ADMIN, Profile.ROLE_EDITOR, Profile.ROLE_CONSULTOR):
            return redirect("home-root")  # o HttpResponse(status=403)
        return super().get(request, *args, **kwargs)


# -----------------------------------------------------------
# CREACION DE FICHAS (USUARIO EDITOR) 
# -----------------------------------------------------------

class LibroCreateWizardView(LoginRequiredMixin, View):
    """Wizard en 3 pasos para crear LibroFicha (solo EDITOR).
    Guardo el avance en request.session['libro_wizard'] usando SOLO tipos JSON puros
    (strings, números, bool, listas, dicts). Nada de objetos de Django.
    """
    template_name = "roles/libro_wizard.html"
    steps = ("ident", "tecnica", "comercial")

    # Campos ForeignKey del modelo (coinciden con tus forms)
    FK_FIELDS = ("editorial", "tipo_tapa", "idioma_original", "pais_edicion", "moneda")

    # ---- Helpers de sesión / rol ----
    def _ensure_editor(self, request):
        # Me aseguro que solo un usuario con rol EDITOR pueda entrar a este flujo
        role = getattr(getattr(request.user, "profile", None), "role", None)
        if role != Profile.ROLE_EDITOR:
            return redirect("roles:panel")  # también podría devolver un 403

    def _get_storage(self, request):
        # Leo (o creo) el diccionario donde voy guardando el progreso del wizard
        return request.session.setdefault("libro_wizard", {})

    def _save_storage(self, request, data):
        # Persisto el diccionario en la sesión y marco como modificada
        request.session["libro_wizard"] = data
        request.session.modified = True

    def _clear_storage(self, request):
        # Limpio los datos del wizard al terminar (o si quiero reiniciar)
        if "libro_wizard" in request.session:
            del request.session["libro_wizard"]
            request.session.modified = True

    def _step_form(self, step, user, data=None, initial=None):
        """
        Devuelvo la instancia de form que toca según el paso:
        - data: POST para bindear y validar
        - initial: valores precargados desde sesión para pintar en el GET
        """
        kwargs = {"data": data, "initial": initial, "request_user": user}
        if step == "ident":
            return LibroIdentForm(**kwargs)
        if step == "tecnica":
            return LibroTecnicaForm(**kwargs)
        if step == "comercial":
            return LibroComercialForm(**kwargs)
        # Si llega algo raro, corto de inmediato
        raise ValueError("Paso inválido")

    # ---------- Serialización segura para session ----------
    def _serialize_for_session(self, form: forms.ModelForm) -> dict:
        """
        Convierto cleaned_data a PRIMITIVOS JSON (clave para no romper la sesión):
        - ModelChoiceField     -> guardo <campo>_id (el PK)
        - ModelMultipleChoice  -> guardo <campo>_ids (lista de PKs)
        - date/datetime        -> guardo como string ISO
        - Decimal              -> guardo como string
        - Primitivos           -> los dejo tal cual
        - Files                -> no los guardo en sesión
        """
        out = {}
        for name, field in form.fields.items():
            val = form.cleaned_data.get(name)

            # Si es un archivo (tiene .read y .name), lo salto: no va a la sesión
            if hasattr(val, "read") and hasattr(val, "name"):
                continue

            # ForeignKey (uno): guardo el _id
            if isinstance(field, forms.ModelChoiceField):
                out[f"{name}_id"] = getattr(val, "pk", None) if val else None
                continue

            # ManyToMany: guardo lista de ids
            if isinstance(field, forms.ModelMultipleChoiceField):
                out[f"{name}_ids"] = [obj.pk for obj in val] if val is not None else []
                continue

            # Fechas/horas: a ISO string
            if isinstance(val, (date, datetime)):
                out[name] = val.isoformat() if val else None
                continue

            # Decimales: a string (evito problemas de serialización)
            if isinstance(val, Decimal):
                out[name] = str(val) if val is not None else None
                continue
                
            # El resto (str, int, float, bool, None, listas/dicts simples)
            out[name] = val
        return out

    def _initial_from_storage(self, step_storage: dict, form_cls: type[forms.ModelForm]) -> dict:
        """
        Convierto lo que tengo en sesión a 'initial' del form.
        Para FK/M2M, los forms aceptan directamente PKs o listas de PKs.
        """
        dummy = form_cls(request_user=None)  # creo una instancia sin bind para inspeccionar fields
        initial = {}
        for name, field in dummy.fields.items():
            if isinstance(field, forms.ModelChoiceField):
                # Para FK uso el valor *_id que dejé en la sesión
                initial[name] = step_storage.get(f"{name}_id")
            elif isinstance(field, forms.ModelMultipleChoiceField):
                # Para M2M uso la lista *_ids
                initial[name] = step_storage.get(f"{name}_ids", [])
            else:
                # Para el resto, leo el mismo nombre
                initial[name] = step_storage.get(name)
        return initial

    # ---- HTTP ----
    def get(self, request):
        # Bloqueo si no es EDITOR
        maybe_redirect = self._ensure_editor(request)
        if maybe_redirect:
            return maybe_redirect
        
        # Tomo el paso actual del querystring; si es inválido, parto desde "ident"
        step = request.GET.get("step") or "ident"
        if step not in self.steps:
            step = "ident"

        storage = self._get_storage(request)
        step_storage = storage.get(step, {})

        # Armo el 'initial' en base a lo que ya guardé en sesión para este paso
        if step == "ident":
            initial = self._initial_from_storage(step_storage, LibroIdentForm)
        elif step == "tecnica":
            initial = self._initial_from_storage(step_storage, LibroTecnicaForm)
        else:
            initial = self._initial_from_storage(step_storage, LibroComercialForm)

        # Creo el form del paso (sin data, solo initial)
        form = self._step_form(step, request.user, data=None, initial=initial)
        ctx = {"step": step, "form": form, "wizard_data": storage}
        return render(request, self.template_name, ctx)

    def post(self, request):
        # De nuevo, solo EDITOR puede postear aquí
        maybe_redirect = self._ensure_editor(request)
        if maybe_redirect:
            return maybe_redirect   
        
        # Leo en qué paso estoy (viene en un input hidden del template)
        storage = self._get_storage(request)
        step = request.POST.get("step") or "ident"
        if step not in self.steps:
            step = "ident"

        form = self._step_form(step, request.user, data=request.POST, initial=None)        
        if not form.is_valid():
            # Si hay errores, vuelvo a pintar el mismo paso con mensajes
            ctx = {"step": step, "form": form, "wizard_data": storage}
            return render(request, self.template_name, ctx)

         # Si el form está OK, serializo y guardo este paso en sesión
        storage[step] = self._serialize_for_session(form)
        self._save_storage(request, storage)

        # Navegación: si apretaron "Anterior", retrocedo un paso
        if "prev" in request.POST:
            prev_idx = max(0, self.steps.index(step) - 1)
            prev_step = self.steps[prev_idx]
            return redirect(f"{reverse('roles:ficha_new')}?step={prev_step}")

        # Si no es el último paso, sigo al siguiente
        if step != "comercial":
            next_idx = min(len(self.steps) - 1, self.steps.index(step) + 1)
            next_step = self.steps[next_idx]
            return redirect(f"{reverse('roles:ficha_new')}?step={next_step}")        

        # --- Paso final: junto todo y creo el registro ---
        data = {}
        for s in self.steps:
            # Merge simple de lo que guardé por paso (último valor pisa al anterior)
            data.update(storage.get(s, {}))

        # Si no definieron código de imagen, uso el ISBN como nombre .png
        if not data.get("codigo_imagen"):
            data["codigo_imagen"] = f"{data.get('isbn','')}.png"

        # Creo el LibroFicha. Django entiende los *_id para asignar FKs.
        # OJO: asumo que las claves y tipos calzan con el modelo.
        libro = LibroFicha.objects.create(**data)

        # Limpio la sesión del wizard para que no queden restos
        self._clear_storage(request)

        # Redirijo al panel principal, nuevamente
        return redirect("roles:panel")

# -----------------------------------------------------------
# Vistas SOLO PROVISIONAL para editar ficha 
# -----------------------------------------------------------

#class LibroEditView(LoginRequiredMixin, View):
    #def get(self, request, isbn):
        #return HttpResponse(f"Editar ficha {isbn}")

class LibroEditView(LoginRequiredMixin, View):
    template_name = "roles/ficha_edit.html"

    def dispatch(self, request, *args, **kwargs):
        # asegura que solo EDITOR puede entrar (igual que en el wizard)
        role = getattr(getattr(request.user, "profile", None), "role", None)
        if role != Profile.ROLE_EDITOR:
            return redirect("roles:panel")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, isbn):
        obj = get_object_or_404(LibroFicha, isbn=isbn)
        form = LibroEditForm(instance=obj, request_user=request.user, allow_change_isbn=False)
        return render(request, self.template_name, {"form": form, "ficha": obj})

    def post(self, request, isbn):
        obj = get_object_or_404(LibroFicha, isbn=isbn)
        form = LibroEditForm(request.POST, instance=obj, request_user=request.user, allow_change_isbn=False)
        if form.is_valid():
            form.save()
            messages.success(request, "Edición exitosa", extra_tags="saved")
            nxt = request.GET.get("next") or request.POST.get("next")
            return redirect(nxt or reverse("roles:panel"))
        # si hay errores, vuelve a pintar el mismo template con los errores
        return render(request, self.template_name, {"form": form, "ficha": obj})

# -----------------------------------------------------------
# SOLO PROVISIONAL para BOTON CARGA MASIVA
# -----------------------------------------------------------

@login_required
def ficha_upload(request):
    # Por ahora no procesamos nada: si llegó archivo, perfecto; si no, igual volvemos.
    return redirect(f"{reverse('roles:ficha_new')}?step={request.POST.get('step','ident')}")


# -----------------------------------------------------------
# MANTENEDOR USUARIOS - LISTAR USUARIOS
# Paginación : 10 x página
# -----------------------------------------------------------
User = get_user_model()

class UsuariosListarView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "roles/usuarios.html"
    context_object_name = "usuarios"
    paginate_by = 10

    def test_func(self):
        p = getattr(self.request.user, "profile", None)
        return getattr(p, "role", None) == Profile.ROLE_ADMIN

    def get_queryset(self):
        q_usuario   = (self.request.GET.get("q_usuario") or "").strip()
        q_editorial = (self.request.GET.get("q_editorial") or "").strip()

        prefetch = Prefetch(
            "usuarioeditorial_set",
            queryset=UsuarioEditorial.objects.select_related("editorial").order_by("editorial__nombre"),
        )

        qs = (User.objects
                .select_related("profile")
                .prefetch_related(prefetch)
                .order_by("first_name", "last_name"))

        if q_usuario:
            qs = qs.filter(
                Q(first_name__icontains=q_usuario) |
                Q(last_name__icontains=q_usuario)  |
                Q(email__icontains=q_usuario)
            )

        if q_editorial:
            qs = qs.filter(usuarioeditorial__editorial__nombre__icontains=q_editorial).distinct()

        # último admin (si hay uno solo)
        admins = list(Profile.objects.filter(role=Profile.ROLE_ADMIN).values_list("user_id", flat=True))
        ultimo_admin_id = admins[0] if len(admins) == 1 else None

        self.extra_context = {
            "q_usuario": q_usuario,
            "q_editorial": q_editorial,
            "editoriales_catalogo": Editorial.objects.all().order_by("nombre"),
            "ultimo_admin_id": ultimo_admin_id,
        }
        return qs

# -----------------------------------------------------------
# MANTENEDOR USUARIOS - EDITAR USUARIOS
# -----------------------------------------------------------

class EditarUsuarioView(LoginRequiredMixin, UserPassesTestMixin, View):
   
    def test_func(self):
        p = getattr(self.request.user, "profile", None)
        return getattr(p, "role", None) == Profile.ROLE_ADMIN

    def post(self, request, user_id):
        usuario = get_object_or_404(User.objects.select_related("profile"), pk=user_id)

        # Datos desde form-encoded o JSON
        data = request.POST
        if request.content_type == "application/json":
            import json
            data = json.loads(request.body.decode("utf-8"))

        form = EditarUsuarioForm({
            "username": usuario.username,
            "email": usuario.email,
            "nombre": data.get("nombre", "").strip(),
            "apellido": data.get("apellido", "").strip(),
            "rol": data.get("rol"),
        })
        # preparar M2M
        editoriales_ids = data.get("editoriales", [])
        if isinstance(editoriales_ids, str):
            editoriales_ids = [e for e in editoriales_ids.split(",") if e]

        form.fields["editoriales"].queryset = Editorial.objects.all()
        if not form.is_valid():
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)

        nuevo_rol = form.cleaned_data["rol"]

        # no permitir quitar ADMIN al único admin
        admins = Profile.objects.filter(role=Profile.ROLE_ADMIN).values_list("user_id", flat=True)
        if usuario.profile.role == Profile.ROLE_ADMIN and len(admins) == 1 and nuevo_rol != Profile.ROLE_ADMIN:
            return JsonResponse({"ok": False, "errors": {"rol": ["No puede quitar el rol ADMIN al único Administrador."]}}, status=400)

        # Guardar nombre/apellido
        usuario.first_name = form.cleaned_data["nombre"]
        usuario.last_name  = form.cleaned_data["apellido"]
        usuario.save(update_fields=["first_name", "last_name"])

        # Guardar rol
        perfil = usuario.profile
        perfil.role = nuevo_rol
        perfil.save(update_fields=["role"])

        # Sincronizacion de editoriales
        if nuevo_rol == Profile.ROLE_EDITOR:
            nuevos = set(int(i) for i in editoriales_ids) if editoriales_ids else set()
            actuales = set(UsuarioEditorial.objects.filter(user=usuario).values_list("editorial_id", flat=True))
            quitar = actuales - nuevos
            agregar = nuevos - actuales
            if quitar:
                UsuarioEditorial.objects.filter(user=usuario, editorial_id__in=quitar).delete()
            if agregar:
                UsuarioEditorial.objects.bulk_create(
                    [UsuarioEditorial(user=usuario, editorial_id=eid) for eid in agregar],
                    ignore_conflicts=True
                )
        else:
            # no-Editor no tiene asignaciones
            UsuarioEditorial.objects.filter(user=usuario).delete()

        return JsonResponse({"ok": True})
    
# -----------------------------------------------------------
# MANTENEDOR USUARIOS - DESHABILITAR/HABILITAR
# UN ÚNICO USUARIO ADMIN NO SE PUEDE DESACTIVAR A SI MISMO
# -----------------------------------------------------------

class ToggleUsuarioActivoView(LoginRequiredMixin, UserPassesTestMixin, View):

    def test_func(self):
        p = getattr(self.request.user, "profile", None)
        return getattr(p, "role", None) == Profile.ROLE_ADMIN

    def post(self, request, user_id):
        usuario = get_object_or_404(User.objects.select_related("profile"), pk=user_id)

        # Cargar JSON body
        data = request.POST
        if request.content_type == "application/json":
            import json
            data = json.loads(request.body.decode("utf-8"))

        activar = bool(data.get("activar"))

        # Si intentan DESACTIVAR al único admin envía error
        if not activar and getattr(usuario, "profile", None) and usuario.profile.role == Profile.ROLE_ADMIN:
            admins = Profile.objects.filter(role=Profile.ROLE_ADMIN, user__is_active=True)\
                                    .values_list("user_id", flat=True)
            if len(admins) == 1 and usuario.id in admins:
                return JsonResponse({
                    "ok": False,
                    "error": "No es posible deshabilitar. Solo hay un usuario ADMIN"
                }, status=400)

        usuario.is_active = activar
        usuario.save(update_fields=["is_active"])

        return JsonResponse({"ok": True, "is_active": usuario.is_active})