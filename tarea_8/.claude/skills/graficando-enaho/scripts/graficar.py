"""Gráficos de la pobreza monetaria de la ENAHO (INEI), ponderados con facpob07, desde la base limpia.

    uv run .claude/skills/graficando-enaho/scripts/graficar.py --indicador todos     # desde tarea_8/

--indicador: area, sexo, edad, departamento o todos. Lee salidas/personas_<anio>.parquet (la arma la skill
limpiando-enaho) y guarda figuras/pobreza_<indicador>.png a 200 dpi. Los títulos se redactan con las cifras
calculadas aquí; ninguna cifra está escrita a mano.
"""
import argparse
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estilo as e  # noqa: E402

ORDEN_EDAD = ["0 a 14 años", "15 a 29 años", "30 a 44 años", "45 a 64 años", "65 años a más"]
PLURAL = {"Hombre": "hombres", "Mujer": "mujeres"}


# --- Títulos analíticos, redactados con los datos --------------------------------------------------------------
def titulo_area(t):
    mayor, menor = t.pct.idxmax(), t.pct.idxmin()
    dif = t.pct[mayor] - t.pct[menor]
    return f"La pobreza {mayor.lower()} supera a la {menor.lower()} en {dif:.1f} puntos porcentuales"


def titulo_sexo(t):
    mayor, menor = t.pct.idxmax(), t.pct.idxmin()
    dif = t.pct[mayor] - t.pct[menor]
    if dif < 1:
        return f"La pobreza apenas difiere entre mujeres y hombres: {dif:.1f} puntos de brecha"
    return f"La pobreza es mayor en {PLURAL[mayor]}: {dif:.1f} puntos más que en {PLURAL[menor]}"


def titulo_edad(t):
    g = t.pct.idxmax()
    return f"Las personas de {g} tienen la pobreza más alta: {e.pct_txt(t.pct[g])}"


def titulo_departamento(t):
    orden = t.pct.sort_values(ascending=False).index
    return f"{orden[0]} y {orden[1]} tienen la mayor pobreza; {orden[-1]}, la menor"


# --- Gráficos --------------------------------------------------------------------------------------------------
def _colores(valores):
    vmax = max(valores)
    return [e.AZUL_MARINO if v == vmax else e.AZUL for v in valores]


def _techo(v, paso=10):
    return math.ceil(v * 1.12 / paso) * paso


def barras_verticales(t, nacional, titulo, subtitulo, anio, ruta):
    """Barras verticales desde cero, valor con un decimal y línea punteada del promedio nacional."""
    fig = plt.figure(figsize=(10, 6.4))
    w, h = fig.get_size_inches()
    y_fin = e.encabezado(fig, titulo, subtitulo)
    izq, der, inf = 1.15, 0.6, 1.05            # pulgadas: etiquetas del eje y, margen derecho y pie
    ax = fig.add_axes([izq / w, inf / h, 1 - (izq + der) / w, y_fin - 0.55 / h - inf / h])

    n = len(t)
    x = range(n)
    ax.bar(x, t.pct, width=0.56, color=_colores(t.pct), zorder=2)
    techo = _techo(max(t.pct.max(), nacional))
    ax.set_ylim(0, techo)
    # las barras ocupan el 82 % del ancho; el resto queda para la etiqueta del promedio
    ax.set_xlim(-0.6, -0.6 + (n - 0.4 + 0.6) / 0.82)
    for xi, v in zip(x, t.pct):
        ax.text(xi, v + techo * 0.018, e.pct_txt(v), ha="center", va="bottom", zorder=4,
                fontproperties=e.fuente("semibold", 10.5), color=e.TEXTO,
                bbox=dict(facecolor=e.BLANCO, edgecolor="none", pad=1.5))

    # la línea pasa detrás de las barras y termina antes de su etiqueta
    ax.plot([0, 0.835], [nacional, nacional], transform=ax.get_yaxis_transform(), color=e.AZUL_PROMEDIO,
            linestyle=(0, (2, 2.5)), linewidth=1.6, zorder=1.5)
    ax.text(0.85, nacional, f"Promedio nacional\n{e.pct_txt(nacional)}", transform=ax.get_yaxis_transform(),
            ha="left", va="center", fontproperties=e.fuente("medium", 9.5), color=e.TEXTO_PROMEDIO,
            linespacing=1.3)

    ax.set_xticks(list(x), t.index)
    ax.yaxis.set_major_locator(MultipleLocator(10))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f} %"))
    e.ejes_limpios(ax, rejilla="y")
    for etiqueta in ax.get_xticklabels():
        etiqueta.set_fontproperties(e.fuente("medium", 10.5))
        etiqueta.set_color(e.TEXTO)
    e.pie(fig, anio)
    e.guardar(fig, ruta)


def barras_horizontales(t, nacional, titulo, subtitulo, anio, ruta):
    """Barras horizontales de mayor a menor, con altura suficiente para leer los 25 departamentos."""
    t = t.sort_values("pct", ascending=True)        # la mayor queda arriba
    n = len(t)
    fig = plt.figure(figsize=(10, 0.36 * n + 3.2))
    w, h = fig.get_size_inches()
    y_fin = e.encabezado(fig, titulo, subtitulo)
    izq, der, inf = 2.0, 0.75, 1.0
    ax = fig.add_axes([izq / w, inf / h, 1 - (izq + der) / w, y_fin - 0.45 / h - inf / h])

    y = range(n)
    ax.barh(y, t.pct, height=0.66, color=_colores(t.pct), zorder=2)
    limite = max(t.pct.max(), nacional) * 1.12        # aire a la derecha para el valor de la barra mayor
    ax.set_xlim(0, limite)
    ax.set_ylim(-0.6, n - 0.4 + 0.8)                  # espacio arriba para la etiqueta del promedio
    for yi, v in zip(y, t.pct):
        ax.text(v + limite * 0.008, yi, e.pct_txt(v), ha="left", va="center", zorder=4,
                fontproperties=e.fuente("semibold", 9.5), color=e.TEXTO,
                bbox=dict(facecolor=e.BLANCO, edgecolor="none", pad=1.2))

    # la línea pasa detrás de las barras; su etiqueta va arriba, sobre la primera barra
    ax.plot([nacional, nacional], [-0.6, n - 0.4 + 0.2], color=e.AZUL_PROMEDIO, linestyle=(0, (2, 2.5)),
            linewidth=1.6, zorder=1.5)
    ax.text(nacional, n - 0.4 + 0.3, f"Promedio nacional: {e.pct_txt(nacional)}", ha="center", va="bottom",
            fontproperties=e.fuente("medium", 9.5), color=e.TEXTO_PROMEDIO)

    ax.set_yticks(list(y), t.index)
    ax.xaxis.set_major_locator(MultipleLocator(10))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f} %"))
    e.ejes_limpios(ax, rejilla="x")
    ax.spines["bottom"].set_visible(False)
    for etiqueta in ax.get_yticklabels():
        etiqueta.set_fontproperties(e.fuente("medium", 10))
        etiqueta.set_color(e.TEXTO)
    e.pie(fig, anio)
    e.guardar(fig, ruta)


# --- Indicadores -----------------------------------------------------------------------------------------------
def graficar(indicador, base, anio):
    nacional = e.promedio_nacional(base)
    per = e.periodo(base)
    if indicador == "area":
        t = e.pobreza_ponderada(base, "area").sort_values("pct", ascending=False)
        barras_verticales(t, nacional, titulo_area(t), f"Perú, {per} · Por área de residencia · {e.UNIDAD}", anio,
                          e.FIGURAS / "pobreza_area.png")
    elif indicador == "sexo":
        t = e.pobreza_ponderada(base, "sexo").sort_values("pct", ascending=False)
        barras_verticales(t, nacional, titulo_sexo(t), f"Perú, {per} · Por sexo · {e.UNIDAD}", anio,
                          e.FIGURAS / "pobreza_sexo.png")
    elif indicador == "edad":
        # los grupos de edad se ordenan por edad, que es su orden natural
        t = e.pobreza_ponderada(base, "grupo_edad")
        t.index = t.index.astype(str)
        t = t.reindex([g for g in ORDEN_EDAD if g in t.index])
        barras_verticales(t, nacional, titulo_edad(t), f"Perú, {per} · Por grupo de edad · {e.UNIDAD}", anio,
                          e.FIGURAS / "pobreza_edad.png")
    elif indicador == "departamento":
        t = e.pobreza_ponderada(base, "departamento_nombre")
        barras_horizontales(t, nacional, titulo_departamento(t), f"Perú, {per} · Por departamento · {e.UNIDAD}",
                            anio, e.FIGURAS / "pobreza_departamento.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--indicador", choices=["area", "sexo", "edad", "departamento", "todos"], default="todos")
    ap.add_argument("--anio", type=int, default=2024)
    args = ap.parse_args()
    e.configurar()
    base = e.cargar_base(args.anio)
    indicadores = ["area", "sexo", "edad", "departamento"] if args.indicador == "todos" else [args.indicador]
    for ind in indicadores:
        graficar(ind, base, args.anio)


if __name__ == "__main__":
    main()
