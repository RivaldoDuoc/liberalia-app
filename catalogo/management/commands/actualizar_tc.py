# catalogo/management/commands/actualizar_tc.py
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.timezone import now
from pathlib import Path

from catalogo.models import Moneda, VariableExterna
from catalogo.services import obtener_tipo_cambio

class Command(BaseCommand):
    help = "Actualiza tipo de cambio USD y EUR desde miindicador.cl"

    def handle(self, *args, **options):
        pares = {"dolar": "USD", "euro": "EUR"}
        log_path = Path(settings.BASE_DIR) / "cron_tc.log"

        lines = []
        for indicador, iso in pares.items():
            moneda = Moneda.objects.get(code__iexact=iso)
            fecha, valor = obtener_tipo_cambio(indicador)

            obj, created = VariableExterna.objects.update_or_create(
                tipo="TC",
                moneda=moneda,
                defaults={
                    "nombre_tipo": iso,
                    "valor": valor,
                    "fecha_actualizacion": fecha,
                },
            )
            msg = f"{now().isoformat()}  {iso}: {valor}  fecha={fecha}  estado={'CREADO' if created else 'ACTUALIZADO'}"
            self.stdout.write(self.style.SUCCESS(msg))
            lines.append(msg)

        # apéndice al archivo de log
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")
        except Exception as e:
            self.stderr.write(self.style.WARNING(f"No pude escribir log: {e}"))

