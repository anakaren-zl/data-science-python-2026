"""Figura de la evaluación: aciertos por modo y por tipo de pregunta.

Modos: A sin MCP ni skills; B con MCP y skills desde tarea_8; C con MCP y skills desde una copia limpia (solo
preguntas de la ENAHO y combinadas). Desde tarea_8:  uv run evaluacion/grafico_evaluacion.py
Lee evaluacion/resultados.csv y guarda figuras/evaluacion_modos.png con el estilo del proyecto.
"""
import sys
from pathlib import Path

import pandas as pd

PROYECTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROYECTO / ".claude/skills/graficando-enaho/scripts"))
import estilo as e  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

TIPOS = {"bcrp": "BCRP", "enaho": "ENAHO", "combinada": "Combinadas"}
MODOS = {"A": ("A, sin MCP ni skills", e.AZUL_PROMEDIO, e.AZUL_MARINO),
         "B": ("B, con MCP y skills", e.AZUL, e.BLANCO),
         "C": ("C, con MCP y skills desde un estado limpio", e.AZUL_MARINO, e.BLANCO)}


def main():
    e.configurar()
    res = pd.read_csv(PROYECTO / "evaluacion/resultados.csv")
    res["acierto"] = res.resultado.eq("acierta")
    modos = [m for m in MODOS if m in set(res.modo)]
    aciertos = res.pivot_table(index="tipo", columns="modo", values="acierto", aggfunc="sum")
    casos = res.pivot_table(index="tipo", columns="modo", values="acierto", aggfunc="size")
    grupos = list(TIPOS) + ["total"]
    aciertos.loc["total"], casos.loc["total"] = aciertos.sum(), casos.sum()

    fig = plt.figure(figsize=(10.5, 6.8))
    pct = {m: round(100 * aciertos.loc["total", m] / casos.loc["total", m]) for m in modos}
    if "C" in pct and pct["C"] == pct["B"]:
        titulo = f"Con MCP y skills el agente acierta el {pct['B']} % en los modos B y C, frente al {pct['A']} % sin ellos"
    elif "C" in pct:
        titulo = (f"Con MCP y skills el agente acierta el {pct['B']} % en el modo B y el {pct['C']} % en el C, "
                  f"frente al {pct['A']} % sin ellos")
    else:
        titulo = f"Con MCP y skills el agente acierta el {pct['B']} % de las preguntas, frente al {pct['A']} % sin ellos"
    tope = e.encabezado(fig, titulo, "% de respuestas correctas sobre las preguntas respondidas por cada modo · "
                                     "El modo C cubre solo la ENAHO", ancho=9.3)
    ax = fig.add_axes([0.1, 0.14, 0.86, tope - 0.21])
    ancho = 0.26
    for i, m in enumerate(modos):
        etiqueta, color, color_txt = MODOS[m]
        desplazamiento = (i - (len(modos) - 1) / 2) * (ancho + 0.015)
        con_etiqueta = False
        for j, g in enumerate(grupos):
            x = j + desplazamiento
            n = casos.loc[g, m] if g in casos.index else float("nan")
            if pd.isna(n) or n == 0:
                ax.text(x, 1.5, "no\naplica", ha="center", va="bottom", color=e.GRIS_NOTA, linespacing=1.1,
                        fontproperties=e.fuente("regular", 9))
                continue
            v = int(aciertos.loc[g, m])
            alto = 100 * v / n                                    # % sobre las preguntas respondidas por el modo
            ax.bar(x, alto, width=ancho, color=color, zorder=2, label=None if con_etiqueta else etiqueta)
            con_etiqueta = True
            dentro = alto > 0                                     # la etiqueta va dentro de toda barra visible
            ax.text(x, alto - 2.5 if dentro else alto + 1.5, f"{v} de {int(n)}", ha="center",
                    va="top" if dentro else "bottom", color=color_txt if dentro else e.TEXTO,
                    fontproperties=e.fuente("semibold", 9.5))
    ax.set_xticks(range(len(grupos)), [TIPOS.get(g, "Total") for g in grupos])
    ax.set_ylim(0, 106)
    ax.set_yticks(range(0, 101, 25), [f"{t} %" for t in range(0, 101, 25)])
    ax.axvline(len(grupos) - 1.5, color=e.REJILLA, linewidth=1.2, zorder=1)
    e.ejes_limpios(ax)
    for t in ax.get_xticklabels():
        t.set_fontproperties(e.fuente("medium", 11))
        t.set_color(e.TEXTO)
    manejadores, etiquetas = ax.get_legend_handles_labels()
    orden = sorted(range(len(etiquetas)), key=lambda k: etiquetas[k])
    leyenda = ax.legend([manejadores[k] for k in orden], [f"Modo {etiquetas[k]}" for k in orden],
                        loc="lower left", bbox_to_anchor=(0, 1.02), ncol=3, frameon=False, handlelength=1.2,
                        prop=e.fuente("regular", 10), borderaxespad=0, columnspacing=1.6)
    for t in leyenda.get_texts():
        t.set_color(e.GRIS_SUBTITULO)
    w, h = fig.get_size_inches()
    fig.text(0.6 / w, 0.32 / h, "Fuente: evaluacion/resultados.csv. Elaboración propia con claude -p (sonnet); "
             "respuestas contrastadas con el BCRP y el INEI", fontproperties=e.fuente("regular", 8.5),
             color=e.GRIS_NOTA, ha="left", va="bottom")
    e.guardar(fig, PROYECTO / "figuras/evaluacion_modos.png")


if __name__ == "__main__":
    main()
