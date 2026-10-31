"""Grafica la pobreza monetaria ponderada de la ENAHO por área, sexo, grupo de edad o departamento.

    uv run .claude/skills/graficando-enaho/scripts/graficar.py --por area
    uv run .claude/skills/graficando-enaho/scripts/graficar.py --por sexo --indicador pobre_extremo

Lee salidas/personas_2024.parquet (la base de la skill limpiando-enaho), pondera con facpob07 y guarda
figuras/pobreza_<por>.png a 200 dpi y figuras/pobreza_<por>.csv con las cifras del gráfico.
Las reglas de estilo están fijas aquí para que todos los gráficos salgan iguales.
"""
import argparse
import urllib.request
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap

RAIZ = Path.cwd()
BASE = RAIZ / "salidas" / "personas_{anio}.parquet"
FIGURAS = RAIZ / "figuras"

# Estilo: fondo azul noche, texto blanco y barras en una sola gama de azules (más clara = más pobreza)
AZUL_NOCHE, SOMBRA = "#0b1f3a", "#050f1f"
TINTA, TINTA_SUAVE = "#ffffff", "#a9bdd6"
AZULES = LinearSegmentedColormap.from_list("azules", ["#2a6fc4", "#5598e7", "#9ec5f4", "#e3effd"])
FONDO = dict(facecolor=AZUL_NOCHE, edgecolor="none", pad=3)   # que la línea punteada no tape las cifras

# Montserrat (licencia SIL OFL): se baja una sola vez a la carpeta fuentes/ de la skill
FUENTES = Path(__file__).resolve().parent.parent / "fuentes"
MONTSERRAT = "https://raw.githubusercontent.com/JulietaUla/Montserrat/master/fonts/ttf/Montserrat-{}.ttf"
PESOS = ["Regular", "Medium", "SemiBold", "SemiBoldItalic", "Bold", "Black"]

# Grupos de edad (en años cumplidos, p208a)
EDADES = [0, 15, 30, 45, 65, 200]
ETIQUETAS_EDAD = ["0 a 14", "15 a 29", "30 a 44", "45 a 64", "65 y más"]

DEPARTAMENTOS = {"01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho",
                 "06": "Cajamarca", "07": "Callao", "08": "Cusco", "09": "Huancavelica", "10": "Huánuco",
                 "11": "Ica", "12": "Junín", "13": "La Libertad", "14": "Lambayeque", "15": "Lima",
                 "16": "Loreto", "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura",
                 "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes", "25": "Ucayali"}

TITULOS = {"pobre": "Pobreza monetaria", "pobre_extremo": "Pobreza monetaria extrema"}
GRUPOS = {"area": "área de residencia", "sexo": "sexo", "edad": "grupo de edad", "departamento": "departamento"}


def usar_montserrat():
    """Baja Montserrat la primera vez y la deja lista en sus seis estilos."""
    try:
        for peso in PESOS:
            ttf = FUENTES / f"Montserrat-{peso}.ttf"
            if not ttf.exists():
                FUENTES.mkdir(exist_ok=True)
                urllib.request.urlretrieve(MONTSERRAT.format(peso), ttf)
            font_manager.fontManager.addfont(str(ttf))
        plt.rcParams["font.family"] = "Montserrat"
    except OSError:
        print("Aviso: no se pudo bajar Montserrat; se usa la letra por defecto.")


def tabla(base, por, indicador):
    """% de personas en pobreza por grupo, ponderado con facpob07."""
    if por == "edad":
        base = base.assign(grupo=pd.cut(base.edad, EDADES, right=False, labels=ETIQUETAS_EDAD))
    elif por == "departamento":
        base = base.assign(grupo=base.departamento.map(DEPARTAMENTOS))
    else:
        base = base.assign(grupo=base[por])
    t = (base.groupby("grupo", observed=True)
             .apply(lambda g: pd.Series({"pct": 100 * np.average(g[indicador], weights=g.facpob07),
                                         "personas_expandidas": g.facpob07.sum(),
                                         "encuestados": len(g)}), include_groups=False)
             .reset_index())
    # Ordenadas de mayor a menor; la edad conserva su orden natural
    return t if por == "edad" else t.sort_values("pct", ascending=False, ignore_index=True)


def graficar(t, por, indicador, anio, nacional):
    horizontal = len(t) > 6
    alto = 0.32 * len(t) + 1.6 if horizontal else 4.6
    fig, ax = plt.subplots(figsize=(8, alto))
    fig.patch.set_facecolor(AZUL_NOCHE)
    ax.set_facecolor(AZUL_NOCHE)
    # Una sola gama de azules, desde 0: la intensidad acompaña al valor
    colores = [AZULES(v / t.pct.max()) for v in (t.pct.iloc[::-1] if horizontal else t.pct)]

    if horizontal:
        t = t.iloc[::-1]                                       # el mayor queda arriba
        y = np.arange(len(t))
        ax.barh(y - 0.07, t.pct, left=t.pct.max() * 0.006, color=SOMBRA, height=0.68, zorder=1)  # sombra: relieve
        barras = ax.barh(y, t.pct, color=colores, height=0.68, zorder=2)
        ax.set_yticks(y, t.grupo.astype(str))
        ax.set_xlim(0, t.pct.max() * 1.15)                     # empieza en cero
        ax.set_ylim(-0.6, len(t) - 0.4)
        ax.axvline(nacional, color=TINTA, lw=1, alpha=0.55, ls=(0, (3, 3)), zorder=0)   # detrás de las barras
        ax.xaxis.set_visible(False)
        for b, v in zip(barras, t.pct):
            ax.text(v + t.pct.max() * 0.015, b.get_y() + b.get_height() / 2, f"{v:.1f} %",
                    va="center", fontsize=9, fontweight="bold", color=TINTA, bbox=FONDO, zorder=3)
    else:
        x = np.arange(len(t))
        ax.bar(x + 0.025, t.pct - t.pct.max() * 0.012, color=SOMBRA, width=0.6, zorder=1)  # sombra: relieve
        barras = ax.bar(x, t.pct, color=colores, width=0.6, zorder=2)
        ax.set_xticks(x, t.grupo.astype(str))
        ax.set_ylim(0, t.pct.max() * 1.18)                     # empieza en cero
        ax.axhline(nacional, color=TINTA, lw=1, alpha=0.55, ls=(0, (3, 3)), zorder=0)   # detrás de las barras
        ax.yaxis.set_visible(False)
        for b, v in zip(barras, t.pct):
            ax.text(b.get_x() + b.get_width() / 2, v + t.pct.max() * 0.035, f"{v:.1f} %",
                    ha="center", va="bottom", fontsize=13, fontweight="bold", color=TINTA, bbox=FONDO, zorder=3)

    for lado in ["top", "right", "left"] if not horizontal else ["top", "right", "bottom"]:
        ax.spines[lado].set_visible(False)
    ax.spines["bottom" if not horizontal else "left"].set_color(TINTA)
    ax.spines["bottom" if not horizontal else "left"].set_alpha(0.6)
    ax.tick_params(length=0, labelsize=10, colors=TINTA)
    for etiqueta in ax.get_xticklabels() + ax.get_yticklabels():
        etiqueta.set_fontweight("medium")                                    # categorías: Medium

    # El título dice qué y cuándo
    unidad = "pobreza" if indicador == "pobre" else "pobreza extrema"
    fig.text(0.02, 1 - 0.42 / alto, f"{TITULOS[indicador]} por {GRUPOS[por]}, Perú {anio}",
             fontsize=17, fontweight="black", color=TINTA, va="top")          # título: Montserrat Black
    fig.text(0.02, 1 - 0.84 / alto,
             f"% de personas en situación de {unidad} · línea punteada: promedio nacional ({nacional:.1f} %)",
             fontsize=10.5, fontweight="semibold", fontstyle="italic",
             color=TINTA_SUAVE, va="top")                                       # subtítulo: SemiBold cursiva
    fig.text(0.02, 0.012, f"Fuente: INEI, ENAHO {anio}. Residentes habituales, ponderado con facpob07.",
             fontsize=8, color=TINTA_SUAVE)                                     # nota: Regular
    fig.tight_layout(rect=(0, 0.25 / alto, 1, 1 - 1.15 / alto))
    return fig


def main(por, indicador, anio):
    ruta = Path(str(BASE).format(anio=anio))
    assert ruta.exists(), f"No existe {ruta.relative_to(RAIZ)}: corre primero la skill limpiando-enaho"
    base = pd.read_parquet(ruta)
    t = tabla(base, por, indicador)
    nacional = 100 * np.average(base[indicador], weights=base.facpob07)

    FIGURAS.mkdir(exist_ok=True)
    sufijo = "" if indicador == "pobre" else "_extrema"
    png, csv = FIGURAS / f"pobreza{sufijo}_{por}.png", FIGURAS / f"pobreza{sufijo}_{por}.csv"
    usar_montserrat()
    graficar(t, por, indicador, anio, nacional).savefig(png, dpi=200, facecolor=AZUL_NOCHE)
    t.round({"pct": 2, "personas_expandidas": 0}).to_csv(csv, index=False)

    print(f"{TITULOS[indicador]} por {GRUPOS[por]}, {anio} (ponderado con facpob07). Perú: {nacional:.1f} %")
    for _, f in t.iterrows():
        print(f"  {str(f.grupo):<16} {f.pct:5.1f} %   ({int(f.encuestados):,} encuestados)")
    print(f"Guardado: {png.relative_to(RAIZ)} y {csv.relative_to(RAIZ)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--por", choices=list(GRUPOS), default="area")
    p.add_argument("--indicador", choices=list(TITULOS), default="pobre")
    p.add_argument("--anio", type=int, default=2024)
    a = p.parse_args()
    main(a.por, a.indicador, a.anio)