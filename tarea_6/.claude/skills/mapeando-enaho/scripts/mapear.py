"""Mapa de la pobreza monetaria por departamento con la ENAHO, unido al GeoJSON por código.

    uv run .claude/skills/mapeando-enaho/scripts/mapear.py

Lee salidas/personas_2024.parquet (la base de la skill limpiando-enaho) y datos/peru_departamental_simple.geojson,
calcula la pobreza ponderada con facpob07 por departamento, la une por código (departamento = FIRST_IDDP) y guarda
mapas/pobreza_departamento.png a 200 dpi y mapas/pobreza_departamento.csv con las cifras del mapa.
"""
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, Normalize

# Reutiliza la letra y los colores de graficando-enaho para que todo se vea como un solo trabajo
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "graficando-enaho" / "scripts"))
from graficar import AZUL_NOCHE, DEPARTAMENTOS, TINTA, TINTA_SUAVE, usar_montserrat  # noqa: E402

RAIZ = Path.cwd()
BASE = RAIZ / "salidas" / "personas_{anio}.parquet"
GEOJSON = RAIZ / "datos" / "peru_departamental_simple.geojson"
MAPAS = RAIZ / "mapas"

# Un solo color, de claro (poca pobreza) a oscuro (mucha pobreza), siempre desde 0
AZULES = LinearSegmentedColormap.from_list("azules", ["#eef5fe", "#9ec5f4", "#3987e5", "#1c5cab", "#0d366b"])


def pobreza_por_departamento(base):
    """% de personas pobres por departamento, ponderado con facpob07."""
    return (base.groupby("departamento")
                .apply(lambda g: pd.Series({"pobreza_pct": 100 * np.average(g.pobre, weights=g.facpob07),
                                            "encuestados": len(g)}), include_groups=False)
                .reset_index())


def unir(geo, pobreza):
    """Une por código como texto, nunca por nombre: «APURIMAC» no es «Apurímac»."""
    geo = geo.assign(departamento=geo.FIRST_IDDP.astype(str).str.zfill(2))
    mapa = geo.merge(pobreza, on="departamento", how="left", validate="1:1")
    assert len(mapa) == 25, f"El mapa tiene {len(mapa)} departamentos; deben ser 25"
    assert mapa.pobreza_pct.notna().all(), f"Sin dato: {mapa.loc[mapa.pobreza_pct.isna(), 'NOMBDEP'].tolist()}"
    assert {"07", "15"} <= set(mapa.departamento), "Lima (15) y Callao (07) deben ir separados"
    return mapa


def dibujar(mapa, anio):
    fig, ax = plt.subplots(figsize=(8, 10))
    fig.patch.set_facecolor(AZUL_NOCHE)
    ax.set_facecolor(AZUL_NOCHE)
    norma = Normalize(vmin=0, vmax=50)                                   # la escala empieza en 0
    mapa.plot(column="pobreza_pct", cmap=AZULES, norm=norma, edgecolor=TINTA, linewidth=0.5, ax=ax)   # límites en blanco
    ax.set_axis_off()

    # La cifra sobre cada departamento (Callao, muy pequeño, con una línea hacia el mar)
    for _, f in mapa.iterrows():
        p = f.geometry.representative_point()
        color = AZUL_NOCHE if f.pobreza_pct < 25 else TINTA
        if f.departamento == "07":
            ax.annotate(f"Callao {f.pobreza_pct:.1f} %", xy=(p.x, p.y), xytext=(p.x - 2.2, p.y - 0.3),
                        fontsize=7.5, fontweight="bold", color=TINTA, va="center",
                        arrowprops=dict(arrowstyle="-", color=TINTA, lw=0.6, alpha=0.7))
            continue
        ax.text(p.x, p.y, f"{f.pobreza_pct:.1f}", ha="center", va="center", fontsize=7.5,
                fontweight="bold", color=color)

    # Leyenda con la unidad
    barra = fig.colorbar(plt.cm.ScalarMappable(norm=norma, cmap=AZULES), ax=ax, orientation="horizontal",
                         fraction=0.03, pad=0.02, aspect=40, shrink=0.7)
    barra.set_label("% de personas en situación de pobreza", color=TINTA, fontsize=9, fontweight="semibold")
    barra.outline.set_visible(False)
    barra.ax.tick_params(colors=TINTA, labelsize=8, length=0)

    # Los tres más y menos pobres, como lectura rápida
    orden = mapa.sort_values("pobreza_pct", ascending=False)
    nombre = lambda c: DEPARTAMENTOS[c]  # noqa: E731
    mas = "\n".join(f"{nombre(f.departamento)}  {f.pobreza_pct:.1f} %" for _, f in orden.head(3).iterrows())
    menos = "\n".join(f"{nombre(f.departamento)}  {f.pobreza_pct:.1f} %" for _, f in orden.tail(3)[::-1].iterrows())
    ax.text(0.01, 0.30, "MÁS POBREZA", transform=ax.transAxes, fontsize=8, fontweight="black", color=TINTA_SUAVE)
    ax.text(0.01, 0.29, mas, transform=ax.transAxes, fontsize=9, fontweight="semibold", color=TINTA, va="top",
            linespacing=1.6)
    ax.text(0.01, 0.15, "MENOS POBREZA", transform=ax.transAxes, fontsize=8, fontweight="black",
            color=TINTA_SUAVE)
    ax.text(0.01, 0.14, menos, transform=ax.transAxes, fontsize=9, fontweight="semibold", color=TINTA, va="top",
            linespacing=1.6)

    # El título dice qué y cuándo
    fig.text(0.04, 0.975, f"Pobreza monetaria por departamento, Perú {anio}", fontsize=17, fontweight="black",
             color=TINTA, va="top")
    fig.text(0.04, 0.945, "% de personas en situación de pobreza · los 25 departamentos, unidos por código",
             fontsize=10.5, fontweight="semibold", fontstyle="italic", color=TINTA_SUAVE, va="top")
    fig.text(0.04, 0.012, f"Fuente: INEI, ENAHO {anio}. Residentes habituales, ponderado con facpob07. "
             "Límites: GeoJSON departamental del curso.", fontsize=7.5, color=TINTA_SUAVE)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.08)
    return fig


def main(anio):
    ruta = Path(str(BASE).format(anio=anio))
    assert ruta.exists(), f"No existe {ruta.relative_to(RAIZ)}: corre primero la skill limpiando-enaho"
    assert GEOJSON.exists(), "Falta datos/peru_departamental_simple.geojson (ver README)"

    mapa = unir(gpd.read_file(GEOJSON), pobreza_por_departamento(pd.read_parquet(ruta)))

    MAPAS.mkdir(exist_ok=True)
    usar_montserrat()
    dibujar(mapa, anio).savefig(MAPAS / "pobreza_departamento.png", dpi=200, facecolor=AZUL_NOCHE)
    tabla = (mapa.assign(nombre=mapa.departamento.map(DEPARTAMENTOS))
                 [["departamento", "nombre", "pobreza_pct", "encuestados"]]
                 .sort_values("pobreza_pct", ascending=False))
    tabla.round({"pobreza_pct": 2}).to_csv(MAPAS / "pobreza_departamento.csv", index=False)

    print(f"Pobreza por departamento, {anio} (ponderado con facpob07). 25 departamentos con dato, unidos por código.")
    for _, f in tabla.iterrows():
        print(f"  {f.departamento}  {f.nombre:<15} {f.pobreza_pct:5.1f} %")
    print("Guardado: mapas/pobreza_departamento.png y mapas/pobreza_departamento.csv")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--anio", type=int, default=2024)
    main(p.parse_args().anio)