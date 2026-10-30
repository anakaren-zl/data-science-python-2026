"""Figure for the report: how many of the 10 BCRP questions Claude answered right, and how long it took, by mode.

    uv run figura.py        # reads resultados.csv and writes grafico.png

The Montserrat fonts live in fuentes/ (SIL Open Font License, see fuentes/OFL.txt), so the figure looks the same
on any computer.
"""
from pathlib import Path

import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

AQUI = Path(__file__).parent
NEGRA = FontProperties(fname=AQUI / "fuentes" / "Montserrat-Black.ttf")
NORMAL = FontProperties(fname=AQUI / "fuentes" / "Montserrat-Regular.ttf")
FONDO, TINTA, TINTA_SUAVE, REJILLA, ACENTO = "#ffffff", "#0f1b33", "#5a6478", "#dfe5ef", "#0b2a6f"
MODOS = {"memoria": "Memory only", "web": "Web search", "mcp": "BCRP MCP"}
# three shades of the same blue, from pale (memory) to deep (MCP), each bar a light-to-dark gradient
DEGRADADOS = {"memoria": ("#e3ebf7", "#b3c7e6"), "web": ("#b7cbea", "#5f88c8"), "mcp": ("#5a86cc", "#0b2a6f")}


def _barra(ax, y, largo, alto, colores):
    """Horizontal bar filled with a left-to-right gradient (light at the baseline, dark at the tip)."""
    if largo <= 0:
        return
    forma = Rectangle((0, y - alto / 2), largo, alto, facecolor="none", edgecolor="none")
    ax.add_patch(forma)
    degradado = ax.imshow([[i / 255 for i in range(256)]], cmap=LinearSegmentedColormap.from_list("", colores),
                          extent=[0, largo, y - alto / 2, y + alto / 2], aspect="auto", interpolation="bilinear",
                          zorder=2)
    degradado.set_clip_path(forma)


res = pd.read_csv(AQUI / "resultados.csv")
tabla = res.groupby("modo").agg(aciertos=("resultado", lambda r: (r == "acierta").sum()),
                                no_sabe=("resultado", lambda r: (r == "no sabe").sum()),
                                preguntas=("resultado", "size"), segundos=("segundos", "mean"))
tabla = tabla.reindex([m for m in MODOS if m in tabla.index])
n = int(tabla.preguntas.max())

fig = Figure(figsize=(11, 6.2), dpi=220, facecolor=FONDO)
izq, der = fig.subplots(1, 2, gridspec_kw={"wspace": 0.42})
paneles = [(izq, "aciertos", "CORRECT ANSWERS", f"out of {n} questions", lambda v: f"{v:.0f}", n),
           (der, "segundos", "TIME PER QUESTION", "average, in seconds", lambda v: f"{v:.1f}", tabla.segundos.max())]
for ax, columna, titulo, unidad, formato, tope in paneles:
    y = list(range(len(tabla)))[::-1]                    # first mode on top
    ax.set_xlim(0, tope * 1.3)
    ax.set_ylim(-0.6, len(tabla) - 0.4)
    ax.set_facecolor(FONDO)
    for yi, (m, fila) in zip(y, tabla.iterrows()):
        _barra(ax, yi, fila[columna], 0.42, DEGRADADOS[m])
        destacado = m == "mcp"
        ax.annotate(formato(fila[columna]), (fila[columna], yi), xytext=(10, 0), textcoords="offset points",
                    va="center", fontproperties=NEGRA, fontsize=18 if destacado else 13,
                    color=ACENTO if destacado else TINTA_SUAVE)
        if columna == "aciertos" and fila.no_sabe:      # quiet note: how often each mode said "I don't know"
            ax.annotate(f"answered “don't know” {fila.no_sabe:.0f}×", (0, yi - 0.3), fontproperties=NORMAL,
                        fontsize=8, color=TINTA_SUAVE, va="center")
    ax.set_yticks(y, [MODOS[m] for m in tabla.index])
    for etiqueta in ax.get_yticklabels():
        etiqueta.set_fontproperties(NORMAL)
        etiqueta.set_fontsize(11)
    ax.set_xticks([])
    for lado in ["top", "right", "bottom", "left"]:
        ax.spines[lado].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=12, labelcolor=TINTA)
    ax.text(0, 1.06, titulo, transform=ax.transAxes, fontproperties=NEGRA, fontsize=9, color=ACENTO)
    ax.text(0, 1.015, unidad, transform=ax.transAxes, fontproperties=NORMAL, fontsize=8.5, color=TINTA_SUAVE)
    ax.axvline(0, color=REJILLA, linewidth=1, zorder=1)

fig.text(0.06, 0.915, "Only the BCRP MCP got every figure right,", fontproperties=NEGRA, fontsize=20, color=TINTA)
fig.text(0.06, 0.855, "in less than half the time of web search", fontproperties=NEGRA, fontsize=20, color=ACENTO)
fig.text(0.06, 0.81, f"Claude Haiku answering {n} questions on official figures of the Central Reserve Bank of Peru "
         "(BCRP), by how it could look them up", fontproperties=NORMAL, fontsize=9.5, color=TINTA_SUAVE)
fig.add_artist(Line2D([0.06, 0.97], [0.785, 0.785], color=ACENTO, linewidth=1.2))
fig.add_artist(Line2D([0.06, 0.97], [0.075, 0.075], color=REJILLA, linewidth=0.8))
fig.text(0.06, 0.04, "Source: own evaluation with evaluar.py (resultados.csv), October 2026. "
         "A wrong or missing answer counts as not correct.", fontproperties=NORMAL, fontsize=8, color=TINTA_SUAVE)
fig.subplots_adjust(left=0.14, right=0.97, top=0.66, bottom=0.12)
fig.savefig(AQUI / "grafico.png", facecolor=FONDO)
print(tabla)