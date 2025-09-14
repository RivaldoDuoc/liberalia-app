"""
Módulo de vistas para la aplicación 'accounts'.

Este archivo gestiona las operaciones principales de autenticación de usuarios:
- Inicio de sesión mediante correo electrónico y contraseña.
- Cierre de sesión del usuario autenticado.
- Redirección automática al panel correspondiente según el rol del perfil 
  (Administrador, Editor o Consultor).

De esta forma, se centraliza la lógica de acceso y navegación inicial del sistema,
garantizando seguridad y una experiencia personalizada para cada usuario.
"""


from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views import View

from .forms import EmailLoginForm  


# Obtenemos el modelo de usuario activo en el proyecto
User = get_user_model()

# --------------------------------------------------------------------------
# Vista basada en clases para manejar el login por email
# --------------------------------------------------------------------------
class LoginView(View):
    template_name = 'accounts/login.html'  # plantilla que renderizamos

    def get(self, request):
        # Si el usuario ya está autenticado, lo redirigimos a la raíz
        if request.user.is_authenticated:
            return redirect('/')  
        # Si no está logueado, mostramos el formulario vacío
        return render(request, self.template_name, {'form': EmailLoginForm()})

    def post(self, request):
        # Recibimos los datos del formulario
        form = EmailLoginForm(request.POST)
        if not form.is_valid():
            # Si el formulario no es válido, mostramos un mensaje de error
            messages.error(request, 'Revisa los campos del formulario.')
            return render(request, self.template_name, {'form': form})
        
        # Normalizamos email y obtenemos la contraseña
        email = form.cleaned_data['email'].strip().lower()
        password = form.cleaned_data['password']

        # Intentamos obtener el usuario por email y autenticarlo
        try:
            user = User.objects.get(email__iexact=email)
            user_auth = authenticate(request, username=user.username, password=password)
        except User.DoesNotExist:
            user_auth = None

        # Si la autenticación falla, mostramos mensaje de error
        if user_auth is None:
            messages.error(request, 'Correo o contraseña inválidos.')
            return render(request, self.template_name, {'form': form})

        # Si la autenticación es correcta, hacemos login
        login(request, user_auth)        
        return redirect('/')

# --------------------------------------------------------------------------
# Función para cerrar sesión
# --------------------------------------------------------------------------
def logout_view(request):
    logout(request)   
    return redirect('accounts:login')

# --------------------------------------------------------------------------
# Vista de inicio que redirige según el rol del usuario
# --------------------------------------------------------------------------
def home(request):
    from django.urls import reverse
    from django.shortcuts import redirect
    from roles.models import Profile

    # Función interna para determinar la URL según rol
    def _role_redirect(user):
        r = getattr(getattr(user, "profile", None), "role", None)
        if r == Profile.ROLE_ADMIN:     return reverse("roles:panel")
        if r == Profile.ROLE_EDITOR:    return reverse("roles:panel")
        if r == Profile.ROLE_CONSULTOR: return reverse("roles:panel")
        return reverse("accounts:login") # fallback por si no hay rol

    # Si el usuario está autenticado, lo redirigimos según su rol
    if request.user.is_authenticated:
        return redirect(_role_redirect(request.user))
    
    # Si no está logueado, lo llevamos al login
    return redirect("accounts:login")