"""
Población potencialmente expuesta en la zona de estudio (Satipo y Atalaya).

Fuente: WorldPop Global 2015–2030, R2025A v1, Perú 2026, versión "constrained",
100 m (0,000833°), unidad: personas por píxel (conteo, no densidad; la suma
nacional ≈ 34 millones confirma la unidad). NoData = -99999.

Método (siguiendo la sesión 07 del curso):
1. Se generan zonas de proximidad de 500 m, 1 km y 5 km alrededor de TODAS las
   detecciones (en metros, UTM 18S) y se DISUELVEN en un único polígono por
   radio, de modo que un mismo píxel no se suma dos veces aunque esté cerca de
   varios focos.
2. Cada zona se intersecta con cada distrito de estudio.
3. Se calcula la suma de píxeles con rasterstats.zonal_stats, declarando el
   nodata explícitamente y con all_touched=False (se incluye un píxel cuando su
   centro cae dentro del polígono), para no sobrestimar.
Advertencia: es población estimada por modelo para 2026, asignada a píxeles con
edificaciones; no es un conteo censal ni indica personas afectadas.
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import rasterio
from rasterio.mask import mask
from rasterstats import zonal_stats

RAIZ = Path(__file__).resolve().parents[1]
RUTA_POB = RAIZ / "data" / "raw" / "poblacion" / "per_pop_2026_CN_100m_R2025A_v1.tif"
RUTA_FOCOS = RAIZ / "data" / "processed" / "focos_peru.gpkg"
RUTA_DISTRITOS = RAIZ / "data" / "raw" / "limites" / "DISTRITOS.shp"
RUTA_RECORTE = RAIZ / "data" / "processed" / "poblacion_zona.tif"
CARPETA_TABLAS = RAIZ / "outputs" / "tablas"
CRS_METRICO = "EPSG:32718"
RADIOS_M = [500, 1000, 5000]
PROVINCIAS_ESTUDIO = {"SATIPO": "JUNIN", "ATALAYA": "UCAYALI"}


def main() -> None:
    if not RUTA_POB.exists():
        raise SystemExit("ERROR: falta el raster de WorldPop en data/raw/poblacion/.")
    distritos = gpd.read_file(RUTA_DISTRITOS)
    filtro = pd.Series(False, index=distritos.index)
    for prov, dep in PROVINCIAS_ESTUDIO.items():
        filtro |= (distritos["PROVINCIA"] == prov) & (distritos["DEPARTAMEN"] == dep)
    zona = distritos[filtro][["IDDIST", "DISTRITO", "PROVINCIA", "geometry"]].reset_index(drop=True)

    # Recorte del raster nacional a la zona (lectura parcial, como en clase).
    with rasterio.open(RUTA_POB) as src:
        assert src.crs.to_epsg() == 4326, "CRS distinto al de los vectores"
        nodata = src.nodata
        datos, transform = mask(src, zona.to_crs(src.crs).geometry, crop=True, nodata=nodata)
        perfil = src.profile | {"height": datos.shape[1], "width": datos.shape[2], "transform": transform}
    with rasterio.open(RUTA_RECORTE, "w", **perfil) as dst:
        dst.write(datos)

    focos = gpd.read_file(RUTA_FOCOS).to_crs(CRS_METRICO)
    zona_m = zona.to_crs(CRS_METRICO)

    filas = []
    resumen = {"fuente": "WorldPop R2025A v1, PER 2026, constrained 100 m, personas por píxel"}
    total = zonal_stats(zona, str(RUTA_RECORTE), stats=["sum"], nodata=nodata, all_touched=False)
    zona["poblacion_total"] = [round(s["sum"] or 0) for s in total]
    resumen["poblacion_total_zona"] = int(zona["poblacion_total"].sum())

    for r in RADIOS_M:
        anillo = gpd.GeoDataFrame(geometry=[focos.buffer(r).union_all()], crs=CRS_METRICO)
        inter = gpd.overlay(zona_m, anillo, how="intersection").to_crs("EPSG:4326")
        st = zonal_stats(inter, str(RUTA_RECORTE), stats=["sum"], nodata=nodata, all_touched=False)
        inter[f"poblacion_a_{r}m"] = [round(s["sum"] or 0) for s in st]
        filas.append(inter[["IDDIST", f"poblacion_a_{r}m"]])
        resumen[f"poblacion_a_{r}m"] = int(inter[f"poblacion_a_{r}m"].sum())

    tabla = zona.drop(columns="geometry")
    for f in filas:
        tabla = tabla.merge(f, on="IDDIST", how="left")
    for r in RADIOS_M:  # distrito sin zona de proximidad = cero observado
        tabla[f"poblacion_a_{r}m"] = tabla[f"poblacion_a_{r}m"].fillna(0).astype(int)
    tabla["pct_a_1000m"] = (100 * tabla["poblacion_a_1000m"] / tabla["poblacion_total"]).round(1)
    tabla = tabla.sort_values("poblacion_a_1000m", ascending=False)
    resumen["pct_a_1000m"] = round(100 * resumen["poblacion_a_1000m"] / resumen["poblacion_total_zona"], 1)

    CARPETA_TABLAS.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(CARPETA_TABLAS / "poblacion_por_distrito.csv", index=False)
    (CARPETA_TABLAS / "poblacion_resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    print(tabla.to_string(index=False))


if __name__ == "__main__":
    main()
