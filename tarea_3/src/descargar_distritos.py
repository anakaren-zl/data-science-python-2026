"""
Descarga de los límites distritales del Perú.

Se emplea el mismo shapefile de distritos que utiliza el notebook de la
sesión 07 del curso (dataset "aquiro1994/ds-python-up" en Hugging Face), con
el propósito de mantener la coherencia metodológica con el material docente.
Un shapefile no consiste en un único archivo, sino en un conjunto de archivos
complementarios (.shp, .dbf, .shx, .prj, .cpg); por ello, se descargan todos.

Posteriormente, el script realiza un control de calidad básico: número de
polígonos, sistema de coordenadas, columnas disponibles, geometrías inválidas
y nombres de distrito repetidos (los cuales no son únicos en el Perú).

Uso (desde la carpeta tarea_3/):
    python src/descargar_distritos.py
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
from huggingface_hub import hf_hub_download

RAIZ = Path(__file__).resolve().parents[1]
CARPETA_SALIDA = RAIZ / "data" / "raw" / "limites"

REPO = "aquiro1994/ds-python-up"
BASE = "_data/Folium/DISTRITOS"
EXTENSIONES = ["shp", "dbf", "shx", "prj", "cpg"]


def descargar() -> Path:
    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)
    for ext in EXTENSIONES:
        try:
            ruta_cache = hf_hub_download(REPO, f"{BASE}.{ext}", repo_type="dataset")
            shutil.copy(ruta_cache, CARPETA_SALIDA / f"DISTRITOS.{ext}")
            print(f"  - DISTRITOS.{ext}: descargado")
        except Exception as error:
            # El .cpg es opcional; los demás son indispensables.
            if ext in ("shp", "dbf", "shx"):
                raise SystemExit(f"ERROR: no se pudo descargar DISTRITOS.{ext} -> {error}")
            print(f"  - DISTRITOS.{ext}: no disponible ({error})")
    return CARPETA_SALIDA / "DISTRITOS.shp"


def controlar_calidad(ruta_shp: Path) -> dict:
    distritos = gpd.read_file(ruta_shp)
    columnas_nombre = [c for c in ("DEPARTAMEN", "PROVINCIA", "DISTRITO") if c in distritos.columns]
    repetidos = (
        int(distritos.duplicated(subset=["DISTRITO"]).sum()) if "DISTRITO" in distritos.columns else None
    )
    xmin, ymin, xmax, ymax = distritos.total_bounds
    return {
        "fuente": f"Hugging Face, dataset {REPO}, archivo {BASE}.shp (material del curso, sesión 07)",
        "fecha_descarga_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "numero_poligonos": int(len(distritos)),
        "crs": str(distritos.crs),
        "columnas": [c for c in distritos.columns if c != "geometry"],
        "geometrias_invalidas": int((~distritos.is_valid).sum()),
        "geometrias_vacias": int(distritos.is_empty.sum()),
        "nombres_de_distrito_repetidos": repetidos,
        "extension_xmin_ymin_xmax_ymax": [round(float(v), 4) for v in (xmin, ymin, xmax, ymax)],
        "ejemplo_primeras_filas": distritos[columnas_nombre].head(3).to_dict(orient="records"),
    }


def main() -> None:
    print("Descargando límites distritales...")
    ruta = descargar()
    print("\nControl de calidad:")
    informe = controlar_calidad(ruta)
    (CARPETA_SALIDA / "DISTRITOS_metadatos.json").write_text(
        json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(informe, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
