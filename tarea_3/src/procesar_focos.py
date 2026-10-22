"""
Procesamiento de las detecciones de FIRMS: control de calidad, integración
con los límites distritales y agrupación espacial en eventos.

El flujo comprende cuatro etapas:
1. Lectura y control de calidad (tipos, valores ausentes, duplicados, rangos
   de coordenadas y ventana temporal).
2. Unión espacial con los distritos: se conservan únicamente las detecciones
   localizadas dentro del territorio peruano y se les asigna el código IDDIST
   (los nombres de distrito no son únicos y, por ello, no se usan como clave).
3. Agrupación espacial: dos detecciones pertenecen al mismo evento cuando se
   encuentran a 1 km o menos, directamente o a través de una cadena de
   detecciones próximas (enlace simple). La distancia se calcula en metros,
   en la proyección UTM 18S (EPSG:32718), nunca en grados.
4. Agregación por distrito y por departamento.

Precisiones conceptuales:
- Una detección es un píxel VIIRS (~375 m) con anomalía térmica; no equivale
  necesariamente a un incendio forestal confirmado.
- Un "evento" es una agrupación analítica de detecciones; no constituye un
  perímetro de incendio ni permite estimar superficie quemada.
- El FRP (Fire Radiative Power, MW) mide la intensidad radiativa instantánea;
  no es una medida de superficie quemada.

Uso (desde la carpeta tarea_3/):
    python src/procesar_focos.py
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
CARPETA_FIRMS = RAIZ / "data" / "raw" / "firms"
RUTA_DISTRITOS = RAIZ / "data" / "raw" / "limites" / "DISTRITOS.shp"
CARPETA_PROCESADOS = RAIZ / "data" / "processed"
CARPETA_TABLAS = RAIZ / "outputs" / "tablas"

CRS_GEOGRAFICO = "EPSG:4326"
CRS_METRICO = "EPSG:32718"        # UTM zona 18 Sur (metros)
DISTANCIA_EVENTO_M = 1000         # parámetro analítico, no un umbral oficial


# --- 1. Lectura y control de calidad ------------------------------------------

def ultimo_archivo_firms() -> tuple[Path, dict]:
    """Devuelve el CSV de FIRMS más reciente y sus metadatos."""
    archivos = sorted(CARPETA_FIRMS.glob("firms_viirs_peru_*.csv"))
    if not archivos:
        raise SystemExit(
            "ERROR: no hay datos de FIRMS en data/raw/firms/. "
            "Ejecute primero: python src/descargar_firms.py"
        )
    csv = archivos[-1]
    meta_path = csv.with_suffix(".json")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return csv, meta


def controlar_calidad(df: pd.DataFrame, inicio: str | None, fin: str | None) -> dict:
    """Registra indicadores de calidad sin eliminar observaciones."""
    informe = {
        "registros": int(len(df)),
        "valores_ausentes_por_columna": {k: int(v) for k, v in df.isna().sum().items() if v},
        "duplicados_exactos": int(df.duplicated().sum()),
        "duplicados_misma_posicion_fecha_hora_satelite": int(
            df.duplicated(["latitude", "longitude", "acq_date", "acq_time", "satellite"]).sum()
        ),
        "latitud_fuera_de_rango": int((~df["latitude"].between(-90, 90)).sum()),
        "longitud_fuera_de_rango": int((~df["longitude"].between(-180, 180)).sum()),
        "confianza": df["confidence"].value_counts().to_dict(),
        "dia_noche": df["daynight"].value_counts().to_dict(),
    }
    if inicio and fin:
        fuera = ~df["acq_date"].between(inicio, fin)
        informe["fuera_de_ventana"] = int(fuera.sum())
    return informe


def preparar_focos(df: pd.DataFrame) -> gpd.GeoDataFrame:
    df = df.copy()
    # Se eliminan solo los duplicados exactos (misma fila repetida por la API).
    df = df.drop_duplicates()
    # acq_time viene como HHMM entero (p. ej., 631 = 06:31 UTC).
    hhmm = df["acq_time"].astype(int).astype(str).str.zfill(4)
    df["fecha_hora_utc"] = pd.to_datetime(df["acq_date"] + " " + hhmm, format="%Y-%m-%d %H%M", utc=True)
    df["confianza"] = df["confidence"].map({"l": "baja", "n": "nominal", "h": "alta"})
    df["id_foco"] = range(1, len(df) + 1)
    return gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["longitude"], df["latitude"]), crs=CRS_GEOGRAFICO
    )


# --- 2. Integración con distritos ---------------------------------------------

def leer_distritos() -> gpd.GeoDataFrame:
    if not RUTA_DISTRITOS.exists():
        raise SystemExit(
            "ERROR: no se encontró data/raw/limites/DISTRITOS.shp. "
            "Ejecute primero: python src/descargar_distritos.py"
        )
    distritos = gpd.read_file(RUTA_DISTRITOS)[
        ["IDDIST", "IDPROV", "IDDPTO", "DISTRITO", "PROVINCIA", "DEPARTAMEN", "geometry"]
    ]
    if distritos.crs is None or distritos.crs.to_epsg() != 4326:
        distritos = distritos.to_crs(CRS_GEOGRAFICO)
    return distritos


def asignar_distrito(focos: gpd.GeoDataFrame, distritos: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    assert focos.crs == distritos.crs, "CRS distintos: reproyectar antes de cruzar"
    unidos = gpd.sjoin(focos, distritos, how="left", predicate="within").drop(columns="index_right")
    # Un punto exactamente sobre un límite podría duplicarse; se conserva una sola fila.
    return unidos.drop_duplicates(subset="id_foco")


# --- 3. Agrupación en eventos -------------------------------------------------

def agrupar_eventos(focos: gpd.GeoDataFrame, distancia_m: float = DISTANCIA_EVENTO_M) -> gpd.GeoDataFrame:
    """Asigna un id de evento por enlace simple a 'distancia_m' metros.

    Se trazan círculos de radio distancia_m/2 alrededor de cada detección; los
    círculos que se tocan se fusionan, y cada polígono resultante define un evento.
    """
    metrico = focos.to_crs(CRS_METRICO)
    zonas = metrico.geometry.buffer(distancia_m / 2).union_all()
    partes = list(zonas.geoms) if zonas.geom_type == "MultiPolygon" else [zonas]
    eventos = gpd.GeoDataFrame({"evento_id": range(1, len(partes) + 1)}, geometry=partes, crs=CRS_METRICO)
    asignados = gpd.sjoin(metrico, eventos, how="left", predicate="within").drop(columns="index_right")
    asignados = asignados.drop_duplicates(subset="id_foco")
    focos = focos.copy()
    focos["evento_id"] = asignados.set_index("id_foco").loc[focos["id_foco"], "evento_id"].values
    return focos


# --- 4. Agregaciones ----------------------------------------------------------

def resumir_eventos(focos: gpd.GeoDataFrame) -> pd.DataFrame:
    g = focos.groupby("evento_id")
    resumen = g.agg(
        detecciones=("id_foco", "size"),
        primera_deteccion_utc=("fecha_hora_utc", "min"),
        ultima_deteccion_utc=("fecha_hora_utc", "max"),
        dias_con_deteccion=("acq_date", "nunique"),
        frp_total_mw=("frp", "sum"),
        frp_max_mw=("frp", "max"),
        lat_centro=("latitude", "mean"),
        lon_centro=("longitude", "mean"),
        IDDIST_principal=("IDDIST", lambda s: s.mode().iat[0]),
        distritos_que_abarca=("IDDIST", "nunique"),
    ).reset_index()
    return resumen.sort_values("detecciones", ascending=False)


def resumir_distritos(focos: gpd.GeoDataFrame, distritos: gpd.GeoDataFrame) -> pd.DataFrame:
    g = focos.groupby("IDDIST")
    resumen = g.agg(
        detecciones=("id_foco", "size"),
        detecciones_confianza_alta=("confianza", lambda s: int((s == "alta").sum())),
        dias_con_deteccion=("acq_date", "nunique"),
        eventos=("evento_id", "nunique"),
        frp_total_mw=("frp", "sum"),
        frp_max_mw=("frp", "max"),
    ).reset_index()
    atributos = distritos.drop(columns="geometry")
    tabla = atributos.merge(resumen, on="IDDIST", how="inner")
    return tabla.sort_values("detecciones", ascending=False)


def resumir_departamentos(focos: gpd.GeoDataFrame) -> pd.DataFrame:
    g = focos.groupby(["IDDPTO", "DEPARTAMEN"])
    return g.agg(
        detecciones=("id_foco", "size"),
        distritos_con_deteccion=("IDDIST", "nunique"),
        eventos=("evento_id", "nunique"),
        dias_con_deteccion=("acq_date", "nunique"),
        frp_total_mw=("frp", "sum"),
    ).reset_index().sort_values("detecciones", ascending=False)


# --- Programa principal -------------------------------------------------------

def main() -> None:
    csv, meta = ultimo_archivo_firms()
    inicio, fin = meta.get("ventana_inicio_utc"), meta.get("ventana_fin_utc")
    print(f"Archivo: {csv.name}")

    crudos = pd.read_csv(csv)
    calidad = controlar_calidad(crudos, inicio, fin)

    focos = preparar_focos(crudos)
    distritos = leer_distritos()
    focos = asignar_distrito(focos, distritos)

    fuera_peru = int(focos["IDDIST"].isna().sum())
    focos = focos[focos["IDDIST"].notna()].copy()
    focos = agrupar_eventos(focos)

    calidad.update({
        "detecciones_fuera_del_peru_descartadas": fuera_peru,
        "detecciones_en_el_peru": int(len(focos)),
        "eventos_identificados": int(focos["evento_id"].nunique()),
        "parametro_distancia_evento_m": DISTANCIA_EVENTO_M,
        "crs_metrico": CRS_METRICO,
    })

    CARPETA_PROCESADOS.mkdir(parents=True, exist_ok=True)
    CARPETA_TABLAS.mkdir(parents=True, exist_ok=True)

    salida = focos.drop(columns=["confidence"]).copy()
    salida["fecha_hora_utc"] = salida["fecha_hora_utc"].dt.strftime("%Y-%m-%dT%H:%MZ")
    salida.to_file(CARPETA_PROCESADOS / "focos_peru.gpkg", layer="focos", driver="GPKG")

    eventos = resumir_eventos(focos)
    por_distrito = resumir_distritos(focos, distritos)
    por_departamento = resumir_departamentos(focos)
    por_dia = focos.groupby("acq_date").size().rename("detecciones").reset_index()

    eventos.to_csv(CARPETA_TABLAS / "eventos.csv", index=False)
    por_distrito.to_csv(CARPETA_TABLAS / "focos_por_distrito.csv", index=False)
    por_departamento.to_csv(CARPETA_TABLAS / "focos_por_departamento.csv", index=False)
    por_dia.to_csv(CARPETA_TABLAS / "focos_por_dia.csv", index=False)
    (CARPETA_TABLAS / "control_calidad_focos.json").write_text(
        json.dumps(calidad, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    print(json.dumps(calidad, indent=2, ensure_ascii=False, default=str))
    print("\nTablas generadas en outputs/tablas/ y capa en data/processed/focos_peru.gpkg")


if __name__ == "__main__":
    main()
