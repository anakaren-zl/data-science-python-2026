"""
Descarga de edificaciones de Google Open Buildings v3 para la zona de estudio
(provincias de Satipo, Junín, y Atalaya, Ucayali).

Open Buildings distribuye sus datos en archivos CSV comprimidos, uno por cada
celda S2 de nivel 4. Por consiguiente, no es necesario descargar el conjunto
mundial (≈48 GB en su versión de puntos): basta con las cuatro celdas que
cubren la zona de estudio. Dichas celdas se calcularon a partir de la extensión
de las doce provincias/distritos de estudio, con un margen de ~5 km, mediante
la librería s2sphere (nivel 4): 911, 917, 919 y 91b.

Se emplea la versión de **puntos** (centroide de cada huella), en lugar de la
de polígonos, porque el indicador de exposición se basa en la distancia entre
cada edificación y las detecciones; además, resulta considerablemente más
liviana. Cada fila contiene: latitude, longitude, area_in_meters, confidence
(puntaje del modelo, entre 0,65 y 1) y full_plus_code.

Advertencias:
- Una huella representa una edificación detectada en imágenes satelitales, no
  necesariamente una vivienda ocupada.
- El modelo de la v3 se ejecutó en mayo de 2023; la fecha de las imágenes
  varía según la zona y puede ser anterior. No se incluyen todas las
  edificaciones existentes.

Uso (desde la carpeta tarea_3/):
    python src/descargar_open_buildings.py
"""

from __future__ import annotations

import gzip
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
CARPETA_TESELAS = RAIZ / "data" / "raw" / "open_buildings"
RUTA_DISTRITOS = RAIZ / "data" / "raw" / "limites" / "DISTRITOS.shp"
RUTA_SALIDA = RAIZ / "data" / "processed" / "edificaciones_zona.gpkg"

BUCKET = "https://storage.googleapis.com/open-buildings-data"
PREFIJO = "v3/points_s2_level_4_gzip"
CELDAS_S2 = ["911", "917", "919", "91b"]

# Zona de estudio: provincias de Satipo (Junín) y Atalaya (Ucayali).
PROVINCIAS_ESTUDIO = {"SATIPO": "JUNIN", "ATALAYA": "UCAYALI"}
MARGEN_M = 5000          # se incluyen edificaciones hasta 5 km fuera del límite
CRS_METRICO = "EPSG:32718"


def zona_de_estudio() -> gpd.GeoDataFrame:
    distritos = gpd.read_file(RUTA_DISTRITOS)
    filtro = pd.Series(False, index=distritos.index)
    for provincia, departamento in PROVINCIAS_ESTUDIO.items():
        filtro |= (distritos["PROVINCIA"] == provincia) & (distritos["DEPARTAMEN"] == departamento)
    zona = distritos[filtro]
    if zona.empty:
        raise SystemExit("ERROR: no se encontraron las provincias de estudio en el shapefile.")
    return zona


def url_de_celda(token: str) -> str:
    """Localiza el archivo de una celda consultando el listado público del bucket."""
    listado = requests.get(
        "https://storage.googleapis.com/storage/v1/b/open-buildings-data/o",
        params={"prefix": f"{PREFIJO}/{token}_"},
        timeout=60,
    )
    if listado.ok and listado.json().get("items"):
        nombre = listado.json()["items"][0]["name"]
        return f"{BUCKET}/{nombre}"
    # Si el listado no estuviera disponible, se usa la convención de nombres habitual.
    return f"{BUCKET}/{PREFIJO}/{token}_buildings.csv.gz"


def descargar_celda(token: str) -> Path:
    destino = CARPETA_TESELAS / f"{token}_buildings.csv.gz"
    if destino.exists() and destino.stat().st_size > 0:
        print(f"  - celda {token}: ya descargada ({destino.stat().st_size / 1e6:.1f} MB)")
        return destino
    url = url_de_celda(token)
    print(f"  - celda {token}: descargando {url}")
    with requests.get(url, stream=True, timeout=300) as r:
        if r.status_code == 404:
            raise SystemExit(f"ERROR: no existe el archivo de la celda {token} ({url}).")
        r.raise_for_status()
        temporal = destino.with_suffix(".parcial")
        with open(temporal, "wb") as f:
            shutil.copyfileobj(r.raw, f)
        temporal.rename(destino)
    print(f"    {destino.stat().st_size / 1e6:.1f} MB")
    return destino


def filtrar_celda(ruta: Path, limites: tuple[float, float, float, float]) -> pd.DataFrame:
    """Lee la celda por bloques y conserva solo las filas dentro del recuadro."""
    oeste, sur, este, norte = limites
    partes = []
    with gzip.open(ruta, "rt", encoding="utf-8") as f:
        for bloque in pd.read_csv(f, chunksize=500_000,
                                  usecols=["latitude", "longitude", "area_in_meters",
                                           "confidence", "full_plus_code"]):
            dentro = bloque["longitude"].between(oeste, este) & bloque["latitude"].between(sur, norte)
            partes.append(bloque[dentro])
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def main() -> None:
    CARPETA_TESELAS.mkdir(parents=True, exist_ok=True)
    RUTA_SALIDA.parent.mkdir(parents=True, exist_ok=True)

    zona = zona_de_estudio()
    zona_buffer = zona.to_crs(CRS_METRICO).buffer(MARGEN_M).union_all()
    zona_buffer = gpd.GeoSeries([zona_buffer], crs=CRS_METRICO).to_crs("EPSG:4326")
    limites = tuple(zona_buffer.total_bounds)
    print(f"Zona de estudio: {len(zona)} distritos; recuadro con margen: {[round(v, 3) for v in limites]}")

    print("Descargando celdas S2 de Open Buildings (puntos):")
    tablas = []
    for token in CELDAS_S2:
        ruta = descargar_celda(token)
        tabla = filtrar_celda(ruta, limites)
        print(f"    filas dentro del recuadro: {len(tabla):,}")
        tablas.append(tabla)

    edif = pd.concat(tablas, ignore_index=True)
    # Una misma huella no debería repetirse entre celdas; se verifica por plus code.
    duplicados = int(edif.duplicated(subset="full_plus_code").sum())
    edif = edif.drop_duplicates(subset="full_plus_code")

    edif = gpd.GeoDataFrame(
        edif, geometry=gpd.points_from_xy(edif["longitude"], edif["latitude"]), crs="EPSG:4326"
    )
    # Recorte fino: solo las edificaciones dentro de la zona más el margen de 5 km.
    edif = edif[edif.within(zona_buffer.iloc[0])].copy()
    edif["id_edificacion"] = range(1, len(edif) + 1)
    edif.to_file(RUTA_SALIDA, layer="edificaciones", driver="GPKG")

    meta = {
        "fuente": "Google Open Buildings v3 (puntos), https://sites.research.google/gr/open-buildings/",
        "licencia": "CC BY 4.0 / ODbL v1.0 (a elección del usuario)",
        "celdas_s2_nivel4": CELDAS_S2,
        "zona_estudio": PROVINCIAS_ESTUDIO,
        "margen_m": MARGEN_M,
        "fecha_descarga_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "edificaciones": int(len(edif)),
        "duplicados_entre_celdas_eliminados": duplicados,
        "confianza_min": float(edif["confidence"].min()) if len(edif) else None,
        "confianza_mediana": float(edif["confidence"].median()) if len(edif) else None,
        "edificaciones_confianza_>=0.75": int((edif["confidence"] >= 0.75).sum()),
        "area_mediana_m2": float(edif["area_in_meters"].median()) if len(edif) else None,
        "advertencia": "Huella detectada no equivale a vivienda ocupada; imágenes anteriores a mayo de 2023.",
    }
    RUTA_SALIDA.with_name("edificaciones_zona_metadatos.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
