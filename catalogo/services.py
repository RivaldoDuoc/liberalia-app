import requests
from decimal import Decimal
from datetime import date

API_BASE = "https://mindicador.cl/api"

def obtener_tipo_cambio(indicador="dolar"):
    url = f"{API_BASE}/{indicador}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    serie = data.get("serie") or []
    if not serie:
        raise ValueError("La API no devolvió datos")
    item = serie[0]
    fecha = date.fromisoformat(item["fecha"][:10])
    valor = Decimal(str(item["valor"]))
    return fecha, valor
