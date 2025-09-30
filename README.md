# Liberalia - Gestión de Novedades Editoriales

Aplicación web desarrollada con Django y MySQL para gestionar fichas editoriales, usuarios y reportes.

## Tecnologías

- Django (Python)
- MySQL
- Bootstrap
- jQuery

## Cómo ejecutar localmente

1. Clonar el repositorio
2. Crear un entorno virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # o .venv\Scripts\activate en Windows
   ```
3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Configurar `.env` con los datos de conexión a la base MySQL

5. Ejecutar:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

## Integrantes

- Andrea Vilches
- Valentina Sandoval
- Nicolás Correa
- Rivaldo Uribe

 