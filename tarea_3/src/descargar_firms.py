"""
Descarga de detecciones de focos de calor (NASA FIRMS, VIIRS 375 m) para el Perú.

El script consulta la API "area" de FIRMS para una ventana móvil de N días
(por defecto, siete) y guarda los resultados sin modificar en data/raw/firms/.
Asimismo, registra un archivo de metadatos con la fecha de descarga, el
intervalo consultado y los productos utilizados, de modo que el análisis
posterior sea trazable y reproducible.

Consideraciones metodológicas:
- Las fechas de FIRMS (acq_date, acq_time) están expresadas en UTC. No
  obstante, el último día de la ventana se define por defecto según la fecha
  de Lima (UTC-5), dado que el día UTC siguiente aún carece de detecciones.
- La API admite como máximo 5 días por consulta; por ello, la ventana se
  divide en bloques consecutivos.
- El recuadro geográfico (bounding box) del Perú incluye porciones de países
  vecinos; en consecuencia, el filtrado definitivo por límites nacionales y
  distritales se realiza en una etapa posterior, no en este script.
- Una detección térmica no equivale necesariamente a un incendio forestal
  confirmado, y varias detecciones pueden corresponder a un mismo evento.

Uso (desde la carpeta tarea_3/):
    python src/descargar_firms.py
    python src/descargar_firms.py --dias 7 --fin 2026-10-21
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

# --- Parámetros generales -----------------------------------------------------

RAIZ = Path(__file__).resolve().parents[1]          # carpeta tarea_3/
CARPETA_SALIDA = RAIZ / "data" / "raw" / "firms"

URL_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

# Recuadro del Perú en el orden que exige FIRMS: oeste, sur, este, norte.
BBOX_PERU = "-81.40,-18.40,-68.60,0.05"

# Productos VIIRS de tiempo casi real (NRT), resolución nominal de 375 m.
PRODUCTOS = {
    "VIIRS_SNPP_NRT": "Suomi NPP / VIIRS",
    "VIIRS_NOAA20_NRT": "NOAA-20 / VIIRS",
    "VIIRS_NOAA21_NRT": "NOAA-21 / VIIRS",
}

MAX_DIAS_POR_CONSULTA = 5


# --- Funciones ----------------------------------------------------------------

def leer_map_key() -> str:
    """Lee la clave FIRMS desde el archivo .env, sin exponerla en el código."""
    load_dotenv(RAIZ / ".env")
    clave = os.getenv("FIRMS_MAP_KEY", "").strip()
    if not clave:
        sys.exit(
            "ERROR: no se encontró FIRMS_MAP_KEY.\n"
            "Verifique que exista el archivo tarea_3/.env con la línea "
            "FIRMS_MAP_KEY=su_clave (sin espacios ni comillas)."
        )
    return clave


def dividir_ventana(inicio: date, fin: date, max_dias: int = MAX_DIAS_POR_CONSULTA):
    """Divide el intervalo [inicio, fin] en bloques de, como máximo, max_dias días.

    Devuelve una lista de tuplas (fecha_inicial, numero_de_dias).
    """
    if fin < inicio:
        raise ValueError("La fecha final no puede ser anterior a la inicial.")
    bloques = []
    actual = inicio
    while actual <= fin:
        dias = min(max_dias, (fin - actual).days + 1)
        bloques.append((actual, dias))
        actual += timedelta(days=dias)
    return bloques


def consultar_firms(clave: str, producto: str, desde: date, dias: int) -> pd.DataFrame:
    """Realiza una consulta a la API de FIRMS y devuelve un DataFrame."""
    url = f"{URL_BASE}/{clave}/{producto}/{BBOX_PERU}/{dias}/{desde.isoformat()}"
    respuesta = requests.get(url, timeout=120)
    respuesta.raise_for_status()
    texto = respuesta.text.strip()

    # FIRMS responde con texto plano (no CSV) cuando la clave o la consulta fallan.
    if not texto or "latitude" not in texto.splitlines()[0]:
        raise RuntimeError(f"Respuesta inesperada de FIRMS para {producto}: {texto[:200]}")

    return pd.read_csv(io.StringIO(texto))


def descargar(dias: int, fin: date) -> None:
    clave = leer_map_key()
    inicio = fin - timedelta(days=dias - 1)
    momento_descarga = datetime.now(timezone.utc)
    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

    print(f"Ventana solicitada (UTC): {inicio} a {fin} ({dias} días)")
    resumen = {}
    tablas = []

    for producto, descripcion in PRODUCTOS.items():
        partes = []
        for desde, n in dividir_ventana(inicio, fin):
            print(f"  - {producto}: {desde} (+{n} días) ...", end=" ")
            try:
                df = consultar_firms(clave, producto, desde, n)
                print(f"{len(df)} registros")
                partes.append(df)
            except Exception as error:  # se registra el error y se continúa
                print(f"ERROR -> {error}")
                resumen.setdefault("errores", []).append(f"{producto} {desde}: {error}")

        if partes:
            df_prod = pd.concat(partes, ignore_index=True)
            df_prod["producto"] = producto
            tablas.append(df_prod)
            resumen[producto] = {
                "descripcion": descripcion,
                "registros": int(len(df_prod)),
                "fecha_min": str(df_prod["acq_date"].min()) if len(df_prod) else None,
                "fecha_max": str(df_prod["acq_date"].max()) if len(df_prod) else None,
            }

    if not tablas:
        sys.exit("ERROR: no se obtuvo ningún registro. Revise la clave y la conexión.")

    focos = pd.concat(tablas, ignore_index=True)
    sello = momento_descarga.strftime("%Y%m%dT%H%MZ")
    archivo_csv = CARPETA_SALIDA / f"firms_viirs_peru_{inicio}_{fin}_{sello}.csv"
    focos.to_csv(archivo_csv, index=False)

    metadatos = {
        "fuente": "NASA FIRMS — API area (https://firms.modaps.eosdis.nasa.gov/api/area/)",
        "productos": list(PRODUCTOS.keys()),
        "bbox_oeste_sur_este_norte": BBOX_PERU,
        "ventana_inicio_utc": str(inicio),
        "ventana_fin_utc": str(fin),
        "zona_horaria_fechas": "UTC (acq_date y acq_time de FIRMS)",
        "fecha_descarga_utc": momento_descarga.isoformat(timespec="seconds"),
        "registros_totales": int(len(focos)),
        "fecha_deteccion_mas_reciente": str(focos["acq_date"].max()),
        "archivo": archivo_csv.name,
        "detalle_por_producto": resumen,
        "advertencia": (
            "Datos crudos dentro de un recuadro geográfico; incluyen zonas de "
            "países vecinos y no han sido filtrados ni deduplicados."
        ),
    }
    archivo_meta = archivo_csv.with_suffix(".json")
    archivo_meta.write_text(json.dumps(metadatos, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nTotal de registros: {len(focos)}")
    print(f"Detección más reciente: {metadatos['fecha_deteccion_mas_reciente']}")
    print(f"Archivo de datos:  {archivo_csv.relative_to(RAIZ)}")
    print(f"Archivo de metadatos: {archivo_meta.relative_to(RAIZ)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga focos VIIRS de FIRMS para el Perú.")
    parser.add_argument("--dias", type=int, default=7, help="Longitud de la ventana (días).")
    # Se toma como referencia la fecha de Lima (UTC-5; el Perú no aplica horario
    # de verano). Así se evita incluir un día UTC que aún no tiene detecciones.
    hoy_lima = datetime.now(timezone(timedelta(hours=-5))).date()
    parser.add_argument(
        "--fin", type=date.fromisoformat, default=hoy_lima,
        help="Último día de la ventana (AAAA-MM-DD). Por defecto, la fecha actual en Lima.",
    )
    args = parser.parse_args()
    descargar(args.dias, args.fin)


if __name__ == "__main__":
    main()
