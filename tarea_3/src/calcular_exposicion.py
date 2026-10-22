"""
Exposición potencial de edificaciones a las detecciones recientes de incendios
en la zona de estudio (Satipo, Junín, y Atalaya, Ucayali).

Método:
- Ambas capas se reproyectan a UTM 18S (EPSG:32718) para medir distancias en metros.
- Para cada edificación se calcula la distancia a la detección VIIRS más cercana
  (sjoin_nearest). Así, cada edificación se cuenta UNA sola vez, con independencia
  del número de focos que tenga alrededor (se evita el doble conteo).
- Se consideran todas las detecciones del Perú, no solo las de la zona, para no
  subestimar la proximidad de las edificaciones situadas cerca del límite.
- Radios exploratorios: 500 m, 1 km y 5 km (parámetros analíticos, no umbrales oficiales).
- La distancia se mide respecto del centro del píxel detectado, no del borde real del fuego.
- Análisis de sensibilidad: se repite el conteo con edificaciones de confianza >= 0,75.

Uso (desde la carpeta tarea_3/):
    python src/calcular_exposicion.py
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RUTA_FOCOS = RAIZ / "data" / "processed" / "focos_peru.gpkg"
RUTA_EDIF = RAIZ / "data" / "processed" / "edificaciones_zona.gpkg"
RUTA_DISTRITOS = RAIZ / "data" / "raw" / "limites" / "DISTRITOS.shp"
CARPETA_TABLAS = RAIZ / "outputs" / "tablas"
CRS_METRICO = "EPSG:32718"
RADIOS_M = [500, 1000, 5000]
PROVINCIAS_ESTUDIO = {"SATIPO": "JUNIN", "ATALAYA": "UCAYALI"}


def main() -> None:
    for ruta in (RUTA_FOCOS, RUTA_EDIF, RUTA_DISTRITOS):
        if not ruta.exists():
            raise SystemExit(f"ERROR: falta {ruta.relative_to(RAIZ)}. Ejecute antes los scripts previos.")

    focos = gpd.read_file(RUTA_FOCOS).to_crs(CRS_METRICO)
    edif = gpd.read_file(RUTA_EDIF).to_crs(CRS_METRICO)
    distritos = gpd.read_file(RUTA_DISTRITOS).to_crs(CRS_METRICO)
    filtro = pd.Series(False, index=distritos.index)
    for prov, dep in PROVINCIAS_ESTUDIO.items():
        filtro |= (distritos["PROVINCIA"] == prov) & (distritos["DEPARTAMEN"] == dep)
    zona = distritos[filtro][["IDDIST", "DISTRITO", "PROVINCIA", "DEPARTAMEN", "geometry"]]

    # Distrito de cada edificación (las del margen de 5 km fuera de la zona quedan sin distrito de estudio).
    edif = gpd.sjoin(edif, zona, how="left", predicate="within").drop(columns="index_right")
    edif = edif.drop_duplicates(subset="id_edificacion")

    # Distancia a la detección más cercana.
    cercano = gpd.sjoin_nearest(
        edif[["id_edificacion", "geometry"]], focos[["id_foco", "evento_id", "geometry"]],
        how="left", distance_col="dist_foco_m",
    ).drop_duplicates(subset="id_edificacion")
    edif = edif.merge(cercano[["id_edificacion", "id_foco", "evento_id", "dist_foco_m"]], on="id_edificacion")

    en_zona = edif[edif["IDDIST"].notna()].copy()
    for r in RADIOS_M:
        en_zona[f"a_{r}m"] = en_zona["dist_foco_m"] <= r
    en_zona["conf_075"] = en_zona["confidence"] >= 0.75

    resumen = {"edificaciones_en_zona": int(len(en_zona)),
               "edificaciones_en_zona_conf_075": int(en_zona["conf_075"].sum())}
    for r in RADIOS_M:
        resumen[f"edificaciones_a_{r}m"] = int(en_zona[f"a_{r}m"].sum())
        resumen[f"edificaciones_a_{r}m_conf_075"] = int((en_zona[f"a_{r}m"] & en_zona["conf_075"]).sum())
        resumen[f"proporcion_a_{r}m"] = round(float(en_zona[f"a_{r}m"].mean()), 4)
    resumen["distancia_mediana_m"] = round(float(en_zona["dist_foco_m"].median()), 1)

    por_distrito = en_zona.groupby(["IDDIST", "DISTRITO", "PROVINCIA"]).agg(
        edificaciones=("id_edificacion", "size"),
        **{f"a_{r}m": (f"a_{r}m", "sum") for r in RADIOS_M},
        a_1000m_conf_075=("conf_075", lambda s: int((s & en_zona.loc[s.index, "a_1000m"]).sum())),
        distancia_mediana_m=("dist_foco_m", "median"),
    ).reset_index()
    por_distrito["proporcion_a_1000m"] = (por_distrito["a_1000m"] / por_distrito["edificaciones"]).round(4)

    focos_zona = focos.merge(zona[["IDDIST"]], on="IDDIST")
    act = focos_zona.groupby("IDDIST").agg(detecciones=("id_foco", "size"),
                                          eventos=("evento_id", "nunique"),
                                          dias_con_deteccion=("acq_date", "nunique")).reset_index()
    por_distrito = por_distrito.merge(act, on="IDDIST", how="left")
    # Cero observado (sin detecciones) se distingue explícitamente de dato ausente.
    for c in ("detecciones", "eventos", "dias_con_deteccion"):
        por_distrito[c] = por_distrito[c].fillna(0).astype(int)
    por_distrito = por_distrito.sort_values("a_1000m", ascending=False)

    # Eventos con más edificaciones a 1 km (cada edificación asignada a su foco más cercano).
    por_evento = (en_zona[en_zona["a_1000m"]].groupby("evento_id").size()
                  .rename("edificaciones_a_1000m").reset_index()
                  .sort_values("edificaciones_a_1000m", ascending=False))

    CARPETA_TABLAS.mkdir(parents=True, exist_ok=True)
    por_distrito.to_csv(CARPETA_TABLAS / "exposicion_por_distrito.csv", index=False)
    por_evento.to_csv(CARPETA_TABLAS / "exposicion_por_evento.csv", index=False)
    (CARPETA_TABLAS / "exposicion_resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    en_zona[en_zona["a_1000m"]].to_crs("EPSG:4326")[["id_edificacion", "IDDIST", "confidence", "dist_foco_m", "geometry"]] \
        .to_file(RAIZ / "data" / "processed" / "edificaciones_expuestas_1km.gpkg", driver="GPKG")

    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    print(por_distrito.to_string(index=False))


if __name__ == "__main__":
    main()
