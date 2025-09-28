"""
Modelos de la aplicación 'roles'.

Este módulo define la estructura de datos relacionada con los roles de usuario
y su vínculo con las editoriales dentro del sistema. Incluye:

- Editorial: catálogo de editoriales que permite asociar usuarios a una o varias.
- Profile: extensión del modelo de usuario de Django con un rol asignado 
  (ADMIN, EDITOR o CONSULTOR).
- UsuarioEditorial: tabla intermedia que implementa la relación M:N entre 
  usuarios y editoriales, asegurando que un usuario pueda pertenecer a varias 
  editoriales y una editorial pueda tener múltiples usuarios.

De esta manera, se organiza la gestión de perfiles y permisos, facilitando 
el control de acceso y la administración de usuarios según su rol 
y las editoriales a las que pertenecen.
"""
# -----------------------------------------------------------------------------
# Estos modelos cubren tu diagrama:
#   - Editorial: catálogo de editoriales
#   - Profile: 1–1 con el usuario de Django; guarda el rol (ADMIN/EDITOR/CONSULTOR)
#   - UsuarioEditorial: relación M:N entre usuario y editorial (usuario puede
#     pertenecer a varias editoriales y viceversa)
# -----------------------------------------------------------------------------

from django.conf import settings
from django.db import models

# Los valores deben tener un rango
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal



# Definir el catálogo de editoriales para poder asociarlas a los usuarios 
# según su rol y utilizarlas en distintas partes del sistema.
class Editorial(models.Model):
    # Catálogo de editoriales -- ESTÁ ACÁ PARA ASOCIAR EDITORIALES CON EL ROL DEL USUARIO
    nombre = models.CharField(max_length=150)
    id_fiscal = models.CharField(max_length=50, blank=True, null=True)

    #NUEVOS CAMPOS QUE DEBEN AGREGARSE -- ¿Se agrega acá porque dependen de la editorial y no el libro? 

    cargo_origen = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Cargo origen (% sobre el costo del libro)"
    )
    recargo_fletes = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Recargo fletes y gastos (% sobre el costo)"
    )
    gastos_indirectos = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Gastos indirectos (% sobre el costo)"
    )
    margen_comercializacion = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Margen de comercialización (% sobre el costo)"
    )

    #Meta sirve para cambiar el nombre que aparece en el admin de Django.

    class Meta:
        verbose_name = "Editorial"
        verbose_name_plural = "Editoriales"

    # Mostramos el nombre de la editorial en el admin y otros contextos.
    # No tocar
    def __str__(self) -> str:        
        return self.nombre


# Extender la información del usuario con un perfil asociado 1–1, 
# donde se define el rol (editor, consultor o admin) y se agregan 
# helpers para consultar de forma más legible el tipo de usuario.

class Profile(models.Model):
    # Definimos constantes para los roles y evitamos repetir strings sueltos
    ROLE_EDITOR = "EDITOR"
    ROLE_CONSULTOR = "CONSULTOR"
    ROLE_ADMIN = "ADMIN"

    # Choices que usamos en formularios y validaciones
    ROLE_CHOICES = [
        (ROLE_EDITOR, "Editor"),
        (ROLE_CONSULTOR, "Consultor"),
        (ROLE_ADMIN, "Admin"),
    ]

    # Relación 1–1 con el usuario (usar AUTH_USER_MODEL = a prueba de futuro)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,      # si borramos el usuario, borramos también su perfil
        related_name="profile",        # accedemos como user.profile
    )

    # Guardamos el rol; por defecto, todo usuario nuevo será "Consultor"
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_CONSULTOR,
    )

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"

    # Mostramos nombre completo si está definido; de lo contrario, el username
    def __str__(self) -> str:
        # Muestra nombre completo si existe; si no, username
        nombre = getattr(self.user, "get_full_name", lambda: "")() or self.user.username
        return f"{nombre} ({self.role})"


    # Helpers: nos permiten consultar de forma más legible el rol del usuario  
    @property
    def is_admin(self) -> bool:
        return self.role == self.ROLE_ADMIN

    @property
    def is_editor(self) -> bool:
        return self.role == self.ROLE_EDITOR

    @property
    def is_consultor(self) -> bool:
        return self.role == self.ROLE_CONSULTOR



# Crear una tabla intermedia para relacionar usuarios con editoriales, 
# evitando duplicados y manteniendo la relación a prueba de futuro 
# (usando AUTH_USER_MODEL en lugar de User directamente).

class UsuarioEditorial(models.Model):
    # Relación M:N entre usuario y editorial (tabla puente)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    editorial = models.ForeignKey(Editorial, on_delete=models.CASCADE)

    class Meta:
        # Aseguramos que no se repita la combinación usuario-editorial
        constraints = [
            models.UniqueConstraint(
                fields=["user", "editorial"],
                name="unique_usuario_editorial",
            )
        ]
        verbose_name = "Usuario de editorial"
        verbose_name_plural = "Usuarios de editorial"
    
    # Representamos la relación en formato legible
    def __str__(self) -> str:
        return f"{self.user} ↔ {self.editorial}"
