"""Gráficos de la pobreza monetaria de la ENAHO (INEI), desde la base limpia y con factores de expansión.

    uv run .claude/skills/graficando-enaho/scripts/graficar.py --indicador todos     # desde tarea_8/

--indicador: area, sexo, edad, departamento, sexo_area o todos. Lee salidas/personas_<anio>.parquet (la arma la
skill limpiando-enaho) y guarda figuras/pobreza_<indicador>.png a 200 dpi.

Método: área y departamento son indicadores de nivel hogar y usan el método oficial del INEI (sumaria, factor07 ×
mieperho); sexo, edad y sexo por área son atributos individuales y usan personas con facpob07. La línea de
referencia es siempre el promedio nacional oficial. Los títulos se redactan con las cifras calculadas aquí.
"""
import argparse
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, MultipleLocator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estilo as e  # noqa: E402

ORDEN_EDAD = ["0 a 14 años", "15 a 29 años", "30 a 44 años", "45 a 64 años", "65 años a más"]
SUJETO_EDAD = {
    "0 a 14 años": "Niñas, niños y adolescentes de 0 a 14 años",
    "15 a 29 años": "Las personas jóvenes de 15 a 29 años",
    "30 a 44 años": "Las personas de 30 a 44 años",
    "45 a 64 años": "Las personas de 45 a 64 años",
    "65 años a más": "Las personas adultas mayores de 65 años a más",
}
CON_ARTICULO = {"Hombre": "los hombres", "Mujer": "las mujeres"}
DIFERENCIA_SUSTANTIVA = 1.5      # pp: la barra mayor va en azul marino solo si supera a la siguiente en esto o más
MINIMO_CASOS = 100               # celdas con menos casos en la muestra se marcan en una nota al pie
COLOR_SEXO = {"Mujer": e.AZUL, "Hombre": e.AZUL_PROMEDIO}
ROTULO_SEXO = {"Mujer": "Mujeres", "Hombre": "Hombres"}


# --- Títulos analíticos: oraciones completas redactadas con los datos ------------------------------------------
def titulo_area(t):
    mayor, menor = t.pct.idxmax(), t.pct.idxmin()
    dif = t.pct[mayor] - t.pct[menor]
    return f"La pobreza monetaria {mayor.lower()} supera a la {menor.lower()} en {dif:.1f} puntos porcentuales"


def titulo_sexo(t):
    mayor, menor = t.pct.idxmax(), t.pct.idxmin()
    if t.pct[mayor] - t.pct[menor] < 1:
        return "La pobreza monetaria afecta casi por igual a mujeres y hombres"
    return f"La pobreza monetaria es mayor entre {CON_ARTICULO[mayor]} que entre {CON_ARTICULO[menor]}"


def titulo_edad(t):
    return f"{SUJETO_EDAD[t.pct.idxmax()]} registran la mayor pobreza monetaria"


def titulo_departamento(t):
    orden = t.pct.sort_values(ascending=False).index
    return (f"{orden[0]} {e.conjuncion_y(orden[1])} {orden[1]} concentran la mayor pobreza monetaria, "
            f"mientras que {orden[-1]} registra la menor")


def titulo_sexo_area(t):
    brecha = (t.loc["Mujer"].pct - t.loc["Hombre"].pct).abs()
    mayor = brecha.idxmax()
    return f"La brecha de pobreza monetaria entre mujeres y hombres es mayor en el área {mayor.lower()}"


# --- Piezas comunes --------------------------------------------------------------------------------------------
def _colores(valores):
    """Un solo azul; la barra mayor en azul marino solo si su diferencia con la siguiente es sustantiva."""
    orden = sorted(valores, reverse=True)
    resaltar = len(orden) > 1 and orden[0] - orden[1] >= DIFERENCIA_SUSTANTIVA
    return [e.AZUL_MARINO if resaltar and v == orden[0] else e.AZUL for v in valores]


def _techo(v, paso=10):
    return math.ceil(v * 1.12 / paso) * paso


def _ejes_verticales(fig, y_fin, extra_sup=0.0):
    w, h = fig.get_size_inches()
    izq, der, inf = 1.15, 0.6, 1.05            # pulgadas: etiquetas del eje y, margen derecho y pie
    return fig.add_axes([izq / w, inf / h, 1 - (izq + der) / w, y_fin - (0.55 + extra_sup) / h - inf / h])


def _valor_dentro(ax, x, v, techo, color_texto=e.BLANCO):
    """Valor con un decimal dentro de la barra, cerca de su extremo superior (fuera si la barra es muy baja)."""
    if v >= techo * 0.12:
        ax.text(x, v - techo * 0.022, e.pct_txt(v), ha="center", va="top", zorder=4,
                fontproperties=e.fuente("semibold", 10.5), color=color_texto)
    else:
        ax.text(x, v + techo * 0.015, e.pct_txt(v), ha="center", va="bottom", zorder=4,
                fontproperties=e.fuente("semibold", 10.5), color=e.TEXTO)


def _linea_promedio(ax, nacional, hasta=0.835):
    """Línea punteada del promedio nacional, detrás de las barras, con su etiqueta a la derecha."""
    ax.plot([0, hasta], [nacional, nacional], transform=ax.get_yaxis_transform(), color=e.AZUL_PROMEDIO,
            linestyle=(0, (2, 2.5)), linewidth=1.6, zorder=1.5)
    ax.text(hasta + 0.015, nacional, f"Promedio nacional\n{e.pct_txt(nacional)}", transform=ax.get_yaxis_transform(),
            ha="left", va="center", fontproperties=e.fuente("medium", 9.5), color=e.TEXTO_PROMEDIO,
            linespacing=1.3)


def _formato_eje_y(ax, techo):
    ax.set_ylim(0, techo)
    ax.yaxis.set_major_locator(MultipleLocator(10))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f} %"))
    e.ejes_limpios(ax, rejilla="y")
    for etiqueta in ax.get_xticklabels():
        etiqueta.set_fontproperties(e.fuente("medium", 10.5))
        etiqueta.set_color(e.TEXTO)


def _tapar_linea(fig, ax, etiquetas, x_linea, margen_pt=4.5):
    """Pone un fondo blanco ajustado detrás de cada valor que toca o roza la línea vertical del promedio.

    El fondo cubre el número y se extiende lo justo para tapar la línea a su lado (margen_pt a cada lado), con la
    altura del texto: así la línea se interrumpe detrás del número sin tapar las barras vecinas.
    """
    r = fig.canvas.get_renderer()
    margen = margen_pt * fig.dpi / 72
    lx = ax.transData.transform((x_linea, 0))[0]
    inversa = ax.transData.inverted()
    for t in etiquetas:
        bb = t.get_window_extent(r)
        if bb.x0 - margen <= lx <= bb.x1 + margen:
            x0, x1 = min(bb.x0, lx - margen), max(bb.x1, lx + margen)
            alto = 1.5 * fig.dpi / 72
            (dx0, dy0), (dx1, dy1) = inversa.transform([(x0, bb.y0 - alto), (x1, bb.y1 + alto)])
            ax.add_patch(Rectangle((dx0, dy0), dx1 - dx0, dy1 - dy0, facecolor=e.BLANCO, edgecolor="none",
                                   zorder=3))


def _nota_pocos_casos(fig, t):
    pocos = t[t.n < MINIMO_CASOS]
    if pocos.empty:
        return
    w, h = fig.get_size_inches()
    celdas = [f"{ROTULO_SEXO[i[0]].lower()} del área {i[1].lower()}" if isinstance(i, tuple) else str(i)
              for i in pocos.index]
    lista = celdas[0] if len(celdas) == 1 else ", ".join(celdas[:-1]) + " y " + celdas[-1]
    fig.text(0.6 / w, 0.55 / h, f"Nota: la muestra tiene menos de {MINIMO_CASOS:,} casos en {lista}; "
             "estas cifras deben leerse con cautela.", fontproperties=e.fuente("regular", 8.5), color=e.GRIS_NOTA,
             ha="left", va="bottom")


# --- Gráficos --------------------------------------------------------------------------------------------------
def barras_verticales(t, nacional, titulo, subtitulo, anio, ruta):
    """Barras verticales desde cero, valor dentro de la barra y línea punteada del promedio nacional."""
    fig = plt.figure(figsize=(10, 6.4))
    ax = _ejes_verticales(fig, e.encabezado(fig, titulo, subtitulo))
    n = len(t)
    ax.bar(range(n), t.pct, width=0.56, color=_colores(list(t.pct)), zorder=2)
    techo = _techo(max(t.pct.max(), nacional))
    ax.set_xlim(-0.6, -0.6 + (n - 0.4 + 0.6) / 0.82)      # el 18 % derecho queda para la etiqueta del promedio
    for xi, v in enumerate(t.pct):
        _valor_dentro(ax, xi, v, techo)
    _linea_promedio(ax, nacional)
    ax.set_xticks(range(n), t.index)
    _formato_eje_y(ax, techo)
    _nota_pocos_casos(fig, t)
    e.pie(fig, anio)
    e.guardar(fig, ruta)


def barras_agrupadas(t, nacional, titulo, subtitulo, anio, ruta, areas):
    """Pobreza por sexo dentro de cada área: barras agrupadas, mujeres en azul y hombres en azul claro."""
    fig = plt.figure(figsize=(10, 6.6))
    w, h = fig.get_size_inches()
    y_fin = e.encabezado(fig, titulo, subtitulo)
    # leyenda discreta, alineada con el título, entre el encabezado y el gráfico
    y_ley = y_fin * h - 0.42
    x = 0.6
    for sexo in ("Mujer", "Hombre"):
        fig.patches.append(Rectangle((x / w, (y_ley - 0.07) / h), 0.14 / w, 0.14 / h, transform=fig.transFigure,
                                     facecolor=COLOR_SEXO[sexo], edgecolor="none"))
        etiqueta = fig.text((x + 0.22) / w, y_ley / h, ROTULO_SEXO[sexo], fontproperties=e.fuente("regular", 10),
                            color=e.GRIS_SUBTITULO, ha="left", va="center")
        x += 0.22 + etiqueta.get_window_extent(fig.canvas.get_renderer()).width / fig.dpi + 0.35
    ax = _ejes_verticales(fig, y_fin, extra_sup=0.35)

    ancho, sep = 0.36, 0.02
    techo = _techo(max(t.pct.max(), nacional))
    for gi, area in enumerate(areas):
        for sexo, dx in (("Mujer", -(ancho + sep) / 2), ("Hombre", (ancho + sep) / 2)):
            v = t.loc[(sexo, area)].pct
            ax.bar(gi + dx, v, width=ancho, color=COLOR_SEXO[sexo], zorder=2)
            # en el azul claro, el blanco no se lee: el valor va en azul marino
            _valor_dentro(ax, gi + dx, v, techo, e.BLANCO if sexo == "Mujer" else e.AZUL_MARINO)
    n = len(areas)
    ax.set_xlim(-0.6, -0.6 + (n - 0.4 + 0.6) / 0.82)
    _linea_promedio(ax, nacional)
    ax.set_xticks(range(n), areas)
    _formato_eje_y(ax, techo)
    _nota_pocos_casos(fig, t)
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

    ax.barh(range(n), t.pct, height=0.66, color=_colores(list(t.pct)), zorder=2)
    limite = max(t.pct.max(), nacional) * 1.12        # aire a la derecha para el valor de la barra mayor
    ax.set_xlim(0, limite)
    ax.set_ylim(-0.6, n - 0.4 + 0.8)                  # espacio arriba para la etiqueta del promedio
    etiquetas = [ax.text(v + limite * 0.008, yi, e.pct_txt(v), ha="left", va="center", zorder=4,
                         fontproperties=e.fuente("semibold", 9.5), color=e.TEXTO,
                         bbox=dict(facecolor=e.BLANCO, edgecolor="none", pad=1.2))
                 for yi, v in enumerate(t.pct)]

    # la línea pasa detrás de las barras; su etiqueta va arriba, sobre la primera barra
    ax.plot([nacional, nacional], [-0.6, n - 0.4 + 0.2], color=e.AZUL_PROMEDIO, linestyle=(0, (2, 2.5)),
            linewidth=1.6, zorder=1.5)
    _tapar_linea(fig, ax, etiquetas, nacional)
    ax.text(nacional, n - 0.4 + 0.3, f"Promedio nacional: {e.pct_txt(nacional)}", ha="center", va="bottom",
            fontproperties=e.fuente("medium", 9.5), color=e.TEXTO_PROMEDIO)

    ax.set_yticks(range(n), t.index)
    ax.xaxis.set_major_locator(MultipleLocator(10))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f} %"))
    e.ejes_limpios(ax, rejilla="x")
    ax.spines["bottom"].set_visible(False)
    for etiqueta in ax.get_yticklabels():
        etiqueta.set_fontproperties(e.fuente("medium", 10))
        etiqueta.set_color(e.TEXTO)
    _nota_pocos_casos(fig, t)
    e.pie(fig, anio)
    e.guardar(fig, ruta)


# --- Indicadores -----------------------------------------------------------------------------------------------
def graficar(indicador, base, anio):
    nacional = e.promedio_nacional(base)          # oficial: sumaria con factor07 × mieperho
    per = e.periodo(base)
    sub = lambda por: f"Perú, {per} · {por} · {e.UNIDAD}"  # noqa: E731
    if indicador == "area":
        t = e.pobreza_hogar(base, "area").sort_values("pct", ascending=False)
        barras_verticales(t, nacional, titulo_area(t), sub("Por área de residencia"), anio,
                          e.FIGURAS / "pobreza_area.png")
    elif indicador == "sexo":
        t = e.pobreza_personas(base, "sexo").sort_values("pct", ascending=False)
        barras_verticales(t, nacional, titulo_sexo(t), sub("Por sexo"), anio, e.FIGURAS / "pobreza_sexo.png")
    elif indicador == "edad":
        # los grupos de edad se ordenan por edad, que es su orden natural
        t = e.pobreza_personas(base, "grupo_edad")
        t.index = t.index.astype(str)
        t = t.reindex([g for g in ORDEN_EDAD if g in t.index])
        barras_verticales(t, nacional, titulo_edad(t), sub("Por grupo de edad"), anio, e.FIGURAS / "pobreza_edad.png")
    elif indicador == "departamento":
        t = e.pobreza_hogar(base, "departamento_nombre")
        barras_horizontales(t, nacional, titulo_departamento(t), sub("Por departamento"), anio,
                            e.FIGURAS / "pobreza_departamento.png")
    elif indicador == "sexo_area":
        t = e.pobreza_personas(base, ["sexo", "area"])
        # las áreas, de mayor a menor pobreza (método de personas, el mismo de las barras)
        areas = list(e.pobreza_personas(base, "area").pct.sort_values(ascending=False).index)
        barras_agrupadas(t, nacional, titulo_sexo_area(t), sub("Por sexo y área de residencia"), anio,
                         e.FIGURAS / "pobreza_sexo_area.png", areas)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--indicador", choices=["area", "sexo", "edad", "departamento", "sexo_area", "todos"],
                    default="todos")
    ap.add_argument("--anio", type=int, default=2024)
    args = ap.parse_args()
    e.configurar()
    base = e.cargar_base(args.anio)
    indicadores = (["area", "sexo", "edad", "departamento", "sexo_area"] if args.indicador == "todos"
                   else [args.indicador])
    for ind in indicadores:
        graficar(ind, base, args.anio)


if __name__ == "__main__":
    main()
