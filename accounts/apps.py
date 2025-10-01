"""
Configuración de la aplicación 'accounts'.

Este módulo define la clase de configuración usada por Django para
registrar la aplicación dentro del proyecto. Aquí se especifica:

- El tipo de clave primaria por defecto (BigAutoField).
- El nombre interno de la app, que permite a Django reconocerla
  y enlazarla con sus modelos, vistas, formularios y rutas.

De esta forma, 'accounts' queda integrada en el ecosistema del proyecto
y lista para gestionar las funcionalidades relacionadas con usuarios
y autenticación.
"""

from django.apps import AppConfig

# Definimos la configuración de la aplicación "accounts"
class AccountsConfig(AppConfig):
    # Indicamos que las claves primarias por defecto serán BigAutoField
    default_auto_field = 'django.db.models.BigAutoField'
    # Especificamos el nombre de la app (usada por Django para reconocerla)
    name = 'accounts'

    def ready(self):
        import accounts.signals  # registra la signal