"""Figura de la evaluación: aciertos por modo (A sin MCP ni skills, B con MCP y skills), por tipo de pregunta.

Desde tarea_8:  uv run evaluacion/grafico_evaluacion.py
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
MODOS = {"A": ("Modo A, sin MCP ni skills", e.AZUL_PROMEDIO, e.AZUL_MARINO),
         "B": ("Modo B, con MCP y skills", e.AZUL, e.BLANCO)}


def main():
    e.configurar()
    res = pd.read_csv(PROYECTO / "evaluacion/resultados.csv")
    res["acierto"] = res.resultado.eq("acierta")
    por_tipo = res.pivot_table(index="tipo", columns="modo", values="acierto", aggfunc="sum").reindex(list(TIPOS))
    n_tipo = res[res.modo == "A"].groupby("tipo").size().reindex(list(TIPOS))
    total = res.groupby("modo").acierto.sum()
    n = int(res.groupby("modo").size().iloc[0])
    grupos = list(TIPOS.values()) + ["Total"]
    valores = {m: list(por_tipo[m].fillna(0).astype(int)) + [int(total.get(m, 0))] for m in MODOS}
    maximos = list(n_tipo.astype(int)) + [n]

    fig = plt.figure(figsize=(10, 6.6))
    a, b = int(total.get("A", 0)), int(total.get("B", 0))
    titulo = (f"Con el MCP y las skills el agente acierta {b} de {n} preguntas, frente a {a} sin ellos"
              if b != a else f"El agente acierta {a} de {n} preguntas en ambos modos")
    tope = e.encabezado(fig, titulo, f"{n} preguntas por modo · Respuestas correctas según el tipo de pregunta",
                        ancho=8.8)
    ax = fig.add_axes([0.11, 0.14, 0.84, tope - 0.23])
    ancho = 0.36
    for i, (m, (etiqueta, color, color_txt)) in enumerate(MODOS.items()):
        xs = [j + (i - 0.5) * (ancho + 0.02) for j in range(len(grupos))]
        barras = ax.bar(xs, valores[m], width=ancho, color=color, label=etiqueta, zorder=2)
        for x, v, mx, barra in zip(xs, valores[m], maximos, barras):
            texto = f"{v} de {mx}"
            if v >= 1:
                ax.text(x, v - 0.25, texto, ha="center", va="top", color=color_txt,
                        fontproperties=e.fuente("semibold", 10))
            else:
                ax.text(x, 0.15, texto, ha="center", va="bottom", color=e.TEXTO,
                        fontproperties=e.fuente("semibold", 10))
    ax.set_xticks(range(len(grupos)), grupos)
    ax.set_ylim(0, n + 0.5)
    ax.set_yticks(range(0, n + 1, 2))
    ax.axvline(len(grupos) - 1.5, color=e.REJILLA, linewidth=1.2, zorder=1)
    e.ejes_limpios(ax)
    for t in ax.get_xticklabels():
        t.set_fontproperties(e.fuente("medium", 11))
        t.set_color(e.TEXTO)
    leyenda = ax.legend(loc="lower left", bbox_to_anchor=(0, 1.02), ncol=2, frameon=False, handlelength=1.2,
                        prop=e.fuente("regular", 11), borderaxespad=0, columnspacing=2.2)
    for t in leyenda.get_texts():
        t.set_color(e.GRIS_SUBTITULO)
    w, h = fig.get_size_inches()
    fig.text(0.6 / w, 0.32 / h, "Fuente: evaluacion/resultados.csv. Elaboración propia con claude -p (sonnet); "
             "respuestas contrastadas con el BCRP y el INEI", fontproperties=e.fuente("regular", 8.5),
             color=e.GRIS_NOTA, ha="left", va="bottom")
    e.guardar(fig, PROYECTO / "figuras/evaluacion_modos.png")


if __name__ == "__main__":
    main()
