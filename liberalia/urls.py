
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
import os

# --------------------------------------------------------------------------
# Definimos todas las rutas del proyecto
# --------------------------------------------------------------------------
urlpatterns = [    
    path('admin/', admin.site.urls), # Panel de administración de Django
    path('accounts/', include('accounts.urls')),   # Rutas de la app 'accounts' para login, logout y manejo de usuarios
    path('', include('accounts.urls_root')),       # Ruta raíz del proyecto: portada simple que redirige según rol
    path("panel/", include("roles.urls", namespace="roles")), # Paneles por rol (Admin, Editor, Consultor) usando namespace 'roles'
    path("catalogo/", include(("catalogo.urls", "catalogo"), namespace="catalogo")),
    # ----------------------------------------------------------------------
    # Flujo de recuperación de contraseña (Password Reset)
    # ----------------------------------------------------------------------

    # Paso 1: vista para solicitar reseteo de contraseña
    path('accounts/password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset.html',
             email_template_name='accounts/password_reset_email.txt',
             subject_template_name='accounts/password_reset_subject.txt',
             success_url=reverse_lazy('password_reset_done'), # redirige al siguiente paso
             from_email=os.getenv('DEFAULT_FROM_EMAIL', 'novedades@liberalia.cl'), # remitente
         ),
         name='password_reset'),

    # Paso 2: confirmación que el email fue enviado
    path('accounts/password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'
         ),
         name='password_reset_done'),
    
    # Paso 3: link del email para restablecer la contraseña
    path('accounts/reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html',
             success_url=reverse_lazy('password_reset_complete'),
         ),
         name='password_reset_confirm'),
    
     # Paso 4: confirmación final de cambio de contraseña
    path('accounts/reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'
         ),
         name='password_reset_complete'),

]