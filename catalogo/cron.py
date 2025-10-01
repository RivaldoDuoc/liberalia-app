from django.core import management


def actualizar_tc_cron():
    """Wrapper callable para django-crontab.

    Llama al comando de management `actualizar_tc` para mantener la lógica en un solo lugar.
    """
    try:
        management.call_command('actualizar_tc')
    except Exception:
        # Re-raise para que django-crontab lo capture y lo loguee
        raise
