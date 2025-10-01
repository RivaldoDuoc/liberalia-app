from __future__ import annotations
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse, HttpRequest, JsonResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages

from .models import Profile, UsuarioEditorial, Editorial
from catalogo.models import LibroFicha, TipoTapa, Idioma, Pais, Moneda

from templates.reports.search_result import exportar_excel
from django.db.models import ForeignKey
from datetime import datetime, date, datetime as dt
from django.urls import reverse
from .forms import LibroIdentForm, LibroTecnicaForm, LibroComercialForm, EditarEditorialForm
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

import os
from django.http import FileResponse, QueryDict
from django.conf import settings


import json
import logging
import secrets
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

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
    # Solo libros de editoriales ACTIVAS
    qs = (LibroFicha.objects
          .select_related("editorial")
          .filter(editorial__is_active=True))

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

    # restricción por rol (EDITOR: solo sus editoriales activas)
    if role == Profile.ROLE_EDITOR:
        ed_ids = (UsuarioEditorial.objects
                  .filter(user=user, editorial__is_active=True)  
                  .values_list("editorial_id", flat=True))
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
        params = request.GET.copy()
        params.pop('page', None)
        params.pop('limit', None)

        qs = build_queryset_for_user(request.user, params)
        rows = []
        for obj in qs:
            rec = {}
            for field in obj._meta.fields:
                name = field.name
                val = getattr(obj, name)
                if isinstance(field, ForeignKey):
                    if val is None:
                        rec[name] = None
                    else:
                        rec[name] = getattr(val, 'nombre', None) or getattr(val, 'code', None) or str(val)
                else:
                    rec[name] = val
            rows.append(rec)

        return exportar_excel(rows)


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
# CLASE PARA ELIMINAR FICHA LIBRO
# -----------------------------------------------------------

class LibroDeleteView(LoginRequiredMixin, View):
    def post(self, request, isbn):
        # Validar permisos: solo EDITOR puede borrar
        role = getattr(getattr(request.user, "profile", None), "role", None)
        if role != Profile.ROLE_EDITOR:
            return redirect("roles:panel")

        obj = get_object_or_404(LibroFicha, isbn=isbn)
        titulo = obj.titulo
        obj.delete()

        messages.success(request, f"Eliminación exitosa: {titulo}")
        return redirect("roles:panel")

# -----------------------------------------------------------    

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


# -----------------------------------------------------------
# MANTENEDOR USUARIOS - INVITAR USUARIOS
# -----------------------------------------------------------

# GENERAR MENSAJE 

log = logging.getLogger(__name__)

def _username_from_email(email: str) -> str:
    User = get_user_model()
    base = (email.split("@")[0] or "usuario").lower().replace(" ", "")
    candidate = base
    i = 1
    while User.objects.filter(username=candidate).exists():
        candidate = f"{base}-{i}"
        i += 1
    return candidate


def _enviar_correo_invitacion(email: str, nombre: str, password_temp: str) -> None:
    asunto = "Invitación al Sistema de Gestión de Novedades Liberalia"
    cuerpo = (
        f"Hola {nombre or ''},\n\n"
        "Has sido invitado(a) a la Plataforma de Gestión de Novedades de Liberalia Ediciones.\n"
        "CREDENCIALES DE INGRESO \n"
        f"Correo: {email}\n"
        f"Contraseña Inicial: {password_temp}\n\n"       

        #=============================================================================================
        #COLOCAR URL CORRECTA EN DESPLIEGUE ACÁ : 'https://liberalia.cl/novedades/accounts/login/)
                #=============================================================================================
        f"Ingreso: {getattr(settings, 'SITE_LOGIN_URL', 'http://127.0.0.1:8000/accounts/login/')}\n\n"
        "IMPORTANTE: Si bien tu contraseña inicial no caduca te recomendamos cambiarla al iniciar sesión en el menú respectivo.\n\n"
        "Saludos,\nEquipo Liberalia"
    )
    remitente = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@liberalia.cl")
    
    try:
        send_mail(asunto, cuerpo, remitente, [email], fail_silently=False)
    except Exception as e:
        log.exception("Fallo al enviar correo de invitación: %s", e)


class InvitarUsuarioView(LoginRequiredMixin, UserPassesTestMixin, View):
    # Requiere que el usuario esté autenticado y además valido su rol
    raise_exception = True

    def handle_no_permission(self):
        # Si no tiene permisos, respondo con error 403 en JSON
        return JsonResponse({"ok": False, "error": "No autorizado."}, status=403)

    def test_func(self):
        # Verifico que el usuario que hace la petición sea ADMIN
        p = getattr(self.request.user, "profile", None)
        return getattr(p, "role", None) == Profile.ROLE_ADMIN

    def post(self, request):
        try:
            # Intento parsear el body como JSON
            try:
                # Si el JSON está mal formado, devuelvo error
                data = json.loads(request.body.decode("utf-8"))
            except Exception:
                return JsonResponse({"ok": False, "errors": {"body": "JSON inválido"}}, status=400)

            # Obtengo y limpio los datos enviados
            nombre    = (data.get("nombre") or "").strip()
            apellido  = (data.get("apellido") or "").strip()
            correo    = (data.get("correo") or "").strip().lower()
            rol       = (data.get("rol") or "").strip().upper()
            ed_ids    = data.get("editoriales") or []
            _id_fiscal = (data.get("id_fiscal") or "").strip()

            # Valido los datos obligatorios
            errors = {}
            if not nombre:
                errors["nombre"] = "Nombre es obligatorio."
            if not apellido:
                errors["apellido"] = "Apellido es obligatorio."
            if not correo:
                errors["correo"] = "Correo es obligatorio."
            if rol not in {Profile.ROLE_CONSULTOR, Profile.ROLE_EDITOR, Profile.ROLE_ADMIN}:
                errors["rol"] = "Rol inválido."
            if rol == Profile.ROLE_EDITOR and not ed_ids:
                errors["editoriales"] = "Selecciona al menos una editorial"

            # Reviso si ya existe un usuario con el mismo correo
            User = get_user_model()
            if User.objects.filter(email=correo).exists():
                errors["ERROR"] = "Ya existe un usuario con este correo."

            # Si hubo errores, los devuelvo
            if errors:
                return JsonResponse({"ok": False, "errors": errors}, status=400)

            # Genero una contraseña inicial para el nuevo usuario
            password_temp = secrets.token_urlsafe(8)

            # Uso una transacción para asegurar consistencia
            with transaction.atomic():
                username = _username_from_email(correo)
                user = User.objects.create_user(
                    username=username,
                    email=correo,
                    first_name=nombre,
                    last_name=apellido,
                    password=password_temp,
                    is_active=True,
                )

                # Creo o actualizo el perfil con el rol asignado
                profile, creado = Profile.objects.get_or_create(user=user, defaults={"role": rol})
                if not creado:
                    # Si el perfil ya existía, se actualiza su rol
                    profile.role = rol
                    profile.save(update_fields=["role"])


                profile.must_change_password = True               
                profile.save(update_fields=["role", "must_change_password"])
    

                # Si es EDITOR, lo asocio con las editoriales seleccionadas
                if rol == Profile.ROLE_EDITOR and ed_ids:
                    editoriales = Editorial.objects.filter(id__in=ed_ids)
                    UsuarioEditorial.objects.bulk_create(
                        [UsuarioEditorial(user=user, editorial=ed) for ed in editoriales],
                        ignore_conflicts=True
                    )

            # Envío el correo de invitación con la contraseña temporal
            _enviar_correo_invitacion(email=correo, nombre=nombre, password_temp=password_temp)
            return JsonResponse({"ok": True})

        # Si ocurre cualquier error inesperado, lo registro en logs
        except Exception as e:
            log.exception("Error en InvitarUsuarioView: %s", e)
            
            # En modo DEBUG muestro detalles, en producción devuelvo error genérico
            if getattr(settings, "DEBUG", False):
                return JsonResponse({"ok": False, "error": f"Error interno: {e.__class__.__name__}: {e}"}, status=500)
            return JsonResponse({"ok": False, "error": "Error interno del servidor."}, status=500)

## Descarga de plantilla Excel para carga masiva de fichas
@login_required
def descargar_plantilla_excel(request):
       # 1. Definir la ruta completa al archivo
    # Usamos settings.BASE_DIR para garantizar que la ruta sea absoluta y correcta
    # 'static/file/carga_masiva.xlsx' es la ruta relativa desde la raíz del proyecto.
    ruta_archivo = os.path.join(
        settings.BASE_DIR, 
        'static', 
        'file', 
        'carga_masiva.xlsx'
    )

    # Verifica si el archivo existe (opcional, pero buena práctica)
    if not os.path.exists(ruta_archivo):
        # Manejar el error si el archivo no se encuentra
        return HttpResponse("El archivo no se encontró.", status=404)

    # 2. Servir el archivo usando FileResponse
    try:
        # Abre el archivo en modo binario de lectura ('rb')
        response = FileResponse(open(ruta_archivo, 'rb'), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        
        # 3. Configurar el encabezado de descarga
        # 'attachment' fuerza al navegador a descargar el archivo en lugar de mostrarlo
        response['Content-Disposition'] = 'attachment; filename="plantilla_carga_masiva.xlsx"'
        
        return response
    except Exception as e:
        # Manejo de errores de lectura
        return HttpResponse(f"Error al servir el archivo: {e}", status=500)


@login_required
def upload_fichas_json(request):
    print(">>> upload_fichas_json called")
    """
    Endpoint que acepta POST JSON { rows: [ {..fila..}, ... ] }
    Valida mínimamente y crea LibroFicha por fila. Devuelve JSON con resumen.
    Reglas simplificadas:
    - Debe ser usuario con role EDITOR
    - Resuelve FKs buscando por 'nombre' (editorial, tipo_tapa) o por code (idioma, pais, moneda)
    - Retorna detalles de filas fallidas
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    # rol
    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    if role != Profile.ROLE_EDITOR:
        return JsonResponse({'ok': False, 'error': 'No autorizado'}, status=403)

    import json
    from decimal import Decimal
    from datetime import datetime, timedelta, date

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    rows = payload.get('rows') or []
    created = 0
    failed = []
    logger = logging.getLogger(__name__)

    # Helpers
    def excel_date_to_date(n):
        # Excel serial (1900-based) -> date; handle ints/floats
        try:
            base = datetime(1899, 12, 30)
            return (base + timedelta(days=float(n))).date()
        except Exception:
            return None

    def resolve_editorial(val):
        if val is None:
            return None
        v = str(val).strip()
        if v.isdigit():
            try:
                return Editorial.objects.get(pk=int(v))
            except Editorial.DoesNotExist:
                return None
        return Editorial.objects.filter(nombre__iexact=v).first()

    def resolve_tipo_tapa(val):
        if val is None: return None
        v = str(val).strip()
        return TipoTapa.objects.filter(nombre__iexact=v).first()

    def resolve_idioma(val):
        if val is None: return None
        v = str(val).strip()
        return Idioma.objects.filter(code__iexact=v).first() or Idioma.objects.filter(nombre__iexact=v).first()

    def resolve_pais(val):
        if val is None: return None
        v = str(val).strip()
        return Pais.objects.filter(code__iexact=v).first() or Pais.objects.filter(nombre__iexact=v).first()

    def resolve_moneda(val):
        if val is None: return None
        v = str(val).strip()
        return Moneda.objects.filter(code__iexact=v).first() or Moneda.objects.filter(nombre__iexact=v).first()

    # --- 1) VALIDAR TODO SIN INSERTAR ---
    validated = []
    input_isbns = []
    for idx, row in enumerate(rows, start=1):
        isbn = str(row.get('isbn') or '').strip()
        input_isbns.append(isbn)

    # chequear duplicados dentro del archivo
    from collections import Counter
    counts = Counter(input_isbns)
    duplicates_in_file = {k for k, v in counts.items() if k and v > 1}

    # chequear existentes en DB
    existing_isbns = set(LibroFicha.objects.filter(isbn__in=[i for i in input_isbns if i]).values_list('isbn', flat=True))

    for idx, row in enumerate(rows, start=1):
        try:
            # simple checks
            isbn = str(row.get('isbn') or '').strip()
            titulo = str(row.get('titulo') or '').strip()
            if not isbn or not titulo:
                raise ValueError('isbn/titulo obligatorios')
            if isbn in duplicates_in_file:
                raise ValueError('ISBN duplicado dentro del archivo')
            if isbn in existing_isbns:
                raise ValueError('ISBN ya existe en la base de datos')

            editorial = resolve_editorial(row.get('editorial'))
            if not editorial:
                raise ValueError('Editorial no encontrada')

            tipo_tapa = resolve_tipo_tapa(row.get('tipo_tapa'))
            if not tipo_tapa:
                raise ValueError('Tipo tapa no encontrado')

            # ints
            try:
                numero_paginas = int(row.get('numero_paginas'))
            except Exception:
                raise ValueError('numero_paginas inválido')

            idioma = resolve_idioma(row.get('idioma_original'))
            if not idioma:
                raise ValueError('Idioma original no encontrado')

            try:
                numero_edicion = int(row.get('numero_edicion'))
            except Exception:
                raise ValueError('numero_edicion inválido')

            # fecha
            fecha_val = row.get('fecha_edicion')
            fecha = None
            if isinstance(fecha_val, (int, float)):
                fecha = excel_date_to_date(fecha_val)
            elif isinstance(fecha_val, str):
                try:
                    fecha = datetime.fromisoformat(fecha_val).date()
                except Exception:
                    # try common formats
                    try:
                        fecha = datetime.strptime(fecha_val, '%Y-%m-%d').date()
                    except Exception:
                        fecha = None
            elif hasattr(fecha_val, 'year'):
                fecha = date(fecha_val.year, fecha_val.month, fecha_val.day)

            if not fecha:
                raise ValueError('fecha_edicion inválida')

            pais = resolve_pais(row.get('pais_edicion'))
            if not pais:
                raise ValueError('Pais edición no encontrado')

            # comerciales
            try:
                precio = Decimal(str(row.get('precio')))
            except Exception:
                raise ValueError('precio inválido')

            moneda = resolve_moneda(row.get('moneda'))
            if not moneda:
                raise ValueError('Moneda no encontrada')

            try:
                descuento = Decimal(str(row.get('descuento_distribuidor') or '0'))
            except Exception:
                raise ValueError('descuento_distribuidor inválido')

            # preparar datos limpios para crear
            clean = {
                'isbn': isbn,
                'titulo': titulo,
                'ean': row.get('ean') or None,
                'editorial': editorial,
                'autor': row.get('autor') or '',
                'autor_prologo': row.get('autor_prologo') or None,
                'traductor': row.get('traductor') or None,
                'ilustrador': row.get('ilustrador') or None,
                'tipo_tapa': tipo_tapa,
                'numero_paginas': numero_paginas,
                'alto_cm': row.get('alto_cm') or None,
                'ancho_cm': row.get('ancho_cm') or None,
                'grosor_cm': row.get('grosor_cm') or None,
                'peso_gr': row.get('peso_gr') or None,
                'idioma_original': idioma,
                'numero_edicion': numero_edicion,
                'fecha_edicion': fecha,
                'pais_edicion': pais,
                'numero_impresion': row.get('numero_impresion') or None,
                'tematica': row.get('tematica') or None,
                'precio': precio,
                'moneda': moneda,
                'descuento_distribuidor': descuento,
                'resumen_libro': row.get('resumen_libro') or '',
                'codigo_imagen': row.get('codigo_imagen') or None,
                'rango_etario': row.get('rango_etario') or None,
                'subtitulo': row.get('subtitulo') or None,
            }

            validated.append((idx, clean, row))

        except Exception as e:
            # Map some internal messages to user-friendly messages
            raw_msg = str(e)
            if 'ISBN ya existe' in raw_msg:
                client_msg = 'Ese ISBN ya existe'
            else:
                client_msg = raw_msg

            # Log full details server-side (stack/row) but don't expose row_data to the client
            try:
                logger.error("Carga masiva - fila %s: %s ; datos: %s", idx, raw_msg, row)
            except Exception:
                # fallback to simple print if logging misconfigured
                print(f"Carga masiva - fila {idx}: {raw_msg} ; datos: {row}")

            failed.append({'row': idx, 'error': client_msg})

    # Si hubo fallos en validación, retornamos sin insertar nada
    if failed:
        return JsonResponse({'ok': False, 'created': 0, 'failed': len(failed), 'errors': failed}, status=400)

    # --- 2) CREAR todos los registros en bloque dentro de una transacción ---
    from django.db import transaction
    instances = []
    for idx, clean, orig_row in validated:
        instances.append(LibroFicha(**clean))

    try:
        with transaction.atomic():
            LibroFicha.objects.bulk_create(instances)
        created = len(instances)
    except Exception as e:
        # error inesperado al insertar: loggear detalles y retornar mensaje genérico al cliente
        try:
            logger.exception("Error al insertar cargas masivas: %s", e)
        except Exception:
            print("Error al insertar cargas masivas:", e)
        return JsonResponse({'ok': False, 'created': 0, 'failed': len(instances), 'errors': [{'row': None, 'error': 'Error interno al crear registros. Contacte al administrador.'}]}, status=500)

    return JsonResponse({'ok': True, 'created': created, 'failed': len(failed), 'errors': failed})


# -----------------------------------------------------------
# MANTENEDOR DE EDITORIALES - LISTAR TODAS LAS EDITORIALES
# -----------------------------------------------------------

class EditorialesListarView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "roles/editoriales.html"
    context_object_name = "editoriales"
    paginate_by = 10

    def test_func(self):
        perfil = getattr(self.request.user, "profile", None)
        return getattr(perfil, "role", None) == Profile.ROLE_ADMIN

    def get_queryset(self):
        q_nombre   = (self.request.GET.get("q_nombre")   or "").strip()
        q_idfiscal = (self.request.GET.get("q_idfiscal") or "").strip()
        estado     = (self.request.GET.get("estado")     or "all").strip().lower()
        if estado not in {"all", "active", "inactive"}:
            estado = "all"

        prefetch_usuarios_activos = Prefetch(
            "usuarioeditorial_set",
            queryset=UsuarioEditorial.objects.select_related("user")
                     .filter(user__is_active=True).order_by("user__email"),
        )

        qs = Editorial.objects.prefetch_related(prefetch_usuarios_activos).order_by("nombre")

        if q_nombre:
            qs = qs.filter(nombre__icontains=q_nombre)
        if q_idfiscal:
            qs = qs.filter(id_fiscal__icontains=q_idfiscal)

        # ←—— Filtro por estado
        if estado == "active":
            qs = qs.filter(is_active=True)
        elif estado == "inactive":
            qs = qs.filter(is_active=False)

        # Preservar filtros en la paginación
        qs_dict = QueryDict(mutable=True)
        if q_nombre:   qs_dict["q_nombre"]   = q_nombre
        if q_idfiscal: qs_dict["q_idfiscal"] = q_idfiscal
        if estado:     qs_dict["estado"]     = estado

        self.extra_context = {
            "q_nombre": q_nombre,
            "q_idfiscal": q_idfiscal,
            "estado": estado,                
            "base_qs": urlencode(qs_dict),
        }
        return qs


# -----------------------------
# EDITAR EDITORIAL 
# -----------------------------
class EditarEditorialView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Actualiza una Editorial.
    - Requiere rol ADMIN.
    - Acepta POST form-encoded o JSON (Content-Type: application/json).
    - Devuelve JSON con ok/errores.
    """

    def test_func(self):
        perfil = getattr(self.request.user, "profile", None)
        return getattr(perfil, "role", None) == Profile.ROLE_ADMIN

    def post(self, request, editorial_id: int):
        editorial = get_object_or_404(Editorial, pk=editorial_id)

        data = request.POST
        if request.content_type == "application/json":
            import json
            try:
                data = json.loads(request.body.decode("utf-8"))
            except Exception:
                return JsonResponse({"ok": False, "errors": {"__all__": ["JSON inválido"]}}, status=400)

        form = EditarEditorialForm(
            data={
                "nombre": (data.get("nombre") or "").strip(),
                "id_fiscal": (data.get("id_fiscal") or "").strip(),
                "cargo_origen": data.get("cargo_origen"),
                "gastos_indirectos": data.get("gastos_indirectos"),
                "recargo_fletes": data.get("recargo_fletes"),
                "margen_comercializacion": data.get("margen_comercializacion"),
            },
            instance=editorial
        )

        if not form.is_valid():
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)

        form.save()
        return JsonResponse({"ok": True})
    

# -----------------------------
# Vista — endpoint para alternar estado de Editorial habilitada/deshabilitada
# -----------------------------

class ToggleEditorialEstadoView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Habilita/Deshabilita una Editorial.
    - Requiere rol ADMIN (mismo test_func que ya usas).
    - POST: alterna el estado o respeta 'activo' si viene en el body.
    Respuesta: { ok: True, nuevo_estado: bool }
    """
    def test_func(self):
        perfil = getattr(self.request.user, "profile", None)
        # Ajusta si tu app usa otro método para validar admin
        return getattr(perfil, "role", None) == Profile.ROLE_ADMIN

    def post(self, request, editorial_id: int):
        ed = get_object_or_404(Editorial, pk=editorial_id)

        # Si llega un JSON con {"activo": true/false}, lo respeta;
        # si no, invierte el estado.
        activo = None
        if request.content_type == "application/json":
            import json
            try:
                data = json.loads(request.body.decode("utf-8"))
                if "activo" in data:
                    activo = bool(data["activo"])
            except Exception:
                pass

        if activo is None:
            ed.is_active = not ed.is_active
        else:
            ed.is_active = activo

        ed.save(update_fields=["is_active"])
        return JsonResponse({"ok": True, "nuevo_estado": ed.is_active})