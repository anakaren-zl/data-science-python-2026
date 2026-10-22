"""
Exposición potencial de locales educativos y contexto de comunidades nativas
en la zona de estudio (Satipo, Junín, y Atalaya, Ucayali).

Fuentes:
- MINEDU, ESCALE, Padrón web de servicios educativos (corte 14-10-2026).
  Cada fila es un servicio educativo; varios servicios comparten un mismo local
  (CODLOCAL). Para evitar el doble conteo, la unidad de análisis es el LOCAL.
  Las coordenadas (NLAT_IE, NLONG_IE) son reportadas por las UGEL/DRE y pueden
  ser aproximadas. Se usan solo servicios en estado "Activo" y coordenadas no nulas.
- Ministerio de Cultura, BDPI, Localidades indígenas u originarias (versión 5).
  No contiene coordenadas; por ello se agrega a nivel distrital mediante el ubigeo.

Uso (desde la carpeta tarea_3/):
    python src/escuelas_comunidades.py
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

RAIZ = Path(__file__).resolve().parents[1]
RUTA_PADRON = RAIZ / "data" / "raw" / "escuelas" / "Padron_web_20261014" / "Padron_web.dbf"
RUTA_BDPI = RAIZ / "data" / "raw" / "comunidades" / "BDPI_Localidades_indigenas_u_originarios_5.xlsx"
RUTA_FOCOS = RAIZ / "data" / "processed" / "focos_peru.gpkg"
CARPETA_TABLAS = RAIZ / "outputs" / "tablas"
CRS_METRICO = "EPSG:32718"
PREFIJOS_PROVINCIA = ["1206", "2502"]   # Satipo (Junín) y Atalaya (Ucayali)
RADIOS_M = [500, 1000, 5000]


def locales_educativos() -> gpd.GeoDataFrame:
    if not RUTA_PADRON.exists():
        raise SystemExit("ERROR: falta el padrón de ESCALE en data/raw/escuelas/.")
    cols = ["CODLOCAL", "COD_MOD", "CEN_EDU", "D_NIV_MOD", "D_GESTION", "CODGEO",
            "D_DIST", "CEN_POB", "DAREACENSO", "NLAT_IE", "NLONG_IE", "D_ESTADO"]
    p = pyogrio.read_dataframe(RUTA_PADRON, encoding="cp850", read_geometry=False, columns=cols)
    p = p[p["CODGEO"].str[:4].isin(PREFIJOS_PROVINCIA) & (p["D_ESTADO"] == "Activo")]
    p = p[(p["NLAT_IE"] != 0) & p["NLAT_IE"].notna()]
    locales = p.groupby("CODLOCAL").agg(
        nombre=("CEN_EDU", "first"), CODGEO=("CODGEO", "first"), distrito=("D_DIST", "first"),
        centro_poblado=("CEN_POB", "first"), area=("DAREACENSO", "first"),
        servicios=("COD_MOD", "nunique"),
        niveles=("D_NIV_MOD", lambda s: "; ".join(sorted(set(s)))),
        lat=("NLAT_IE", "mean"), lon=("NLONG_IE", "mean"),
    ).reset_index()
    return gpd.GeoDataFrame(locales, geometry=gpd.points_from_xy(locales.lon, locales.lat), crs="EPSG:4326")


def comunidades_por_distrito() -> pd.DataFrame:
    b = pd.read_excel(RUTA_BDPI, sheet_name=1, header=5)
    b["IDDIST"] = b["Ubigeo del Distrito"].astype("Int64").astype(str).str.zfill(6)
    b = b[b["IDDIST"].str[:4].isin(PREFIJOS_PROVINCIA)]
    nativas = b[b["Tipo de Localidad"] == "Comunidad nativa"]
    col_agua = [c for c in b.columns if str(c).startswith("N° de Viviendas sin servicio de agua")][0]
    col_luz = [c for c in b.columns if str(c).startswith("N° de Viviendas sin servicio de electricidad")][0]
    col_viv = [c for c in b.columns if str(c).startswith("N° de Viviendas con poblaci")][0]
    g = nativas.groupby("IDDIST").agg(
        comunidades_nativas=("Nombre de la Localidad", "size"),
        pueblos=("Pueblo Indígena u Originario", lambda s: "; ".join(sorted(set(map(str, s))))),
        viviendas_cn=(col_viv, "sum"), viv_sin_agua_cn=(col_agua, "sum"), viv_sin_luz_cn=(col_luz, "sum"),
    ).reset_index()
    g["pct_sin_agua_cn"] = (100 * g["viv_sin_agua_cn"] / g["viviendas_cn"]).round(1)
    g["pct_sin_luz_cn"] = (100 * g["viv_sin_luz_cn"] / g["viviendas_cn"]).round(1)
    return g


def main() -> None:
    locales = locales_educativos().to_crs(CRS_METRICO)
    focos = gpd.read_file(RUTA_FOCOS).to_crs(CRS_METRICO)
    cerca = gpd.sjoin_nearest(locales, focos[["id_foco", "acq_date", "geometry"]],
                              how="left", distance_col="dist_foco_m").drop_duplicates("CODLOCAL")
    for r in RADIOS_M:
        cerca[f"a_{r}m"] = cerca["dist_foco_m"] <= r
    resumen = {"locales_educativos_activos": int(len(cerca)),
               **{f"locales_a_{r}m": int(cerca[f"a_{r}m"].sum()) for r in RADIOS_M}}

    cerca["IDDIST"] = cerca["CODGEO"]
    esc = cerca.groupby("IDDIST").agg(
        distrito=("distrito", "first"), locales=("CODLOCAL", "size"),
        **{f"locales_a_{r}m": (f"a_{r}m", "sum") for r in RADIOS_M},
    ).reset_index()
    tabla = esc.merge(comunidades_por_distrito(), on="IDDIST", how="left")
    tabla["comunidades_nativas"] = tabla["comunidades_nativas"].fillna(0).astype(int)  # cero observado en la BDPI
    tabla = tabla.sort_values("locales_a_1000m", ascending=False)
    resumen["comunidades_nativas_en_zona"] = int(tabla["comunidades_nativas"].sum())

    CARPETA_TABLAS.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(CARPETA_TABLAS / "escuelas_comunidades_por_distrito.csv", index=False)
    lista = cerca[cerca["a_1000m"]].sort_values("dist_foco_m")[
        ["CODLOCAL", "nombre", "distrito", "centro_poblado", "area", "niveles", "dist_foco_m", "acq_date"]]
    lista.to_csv(CARPETA_TABLAS / "locales_educativos_a_1km.csv", index=False)
    (CARPETA_TABLAS / "escuelas_resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    print(tabla.drop(columns=["pueblos"]).to_string(index=False))
    print(tabla[["distrito", "pueblos"]].to_string(index=False))
    print(lista.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
