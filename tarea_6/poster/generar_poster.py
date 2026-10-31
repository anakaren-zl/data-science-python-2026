"""Genera el póster «Pobreza monetaria en el Perú, 2024».

Usa solo las cifras de mapas/pobreza_departamento.csv y figuras/pobreza_area.csv,
tal como aparecen en esos archivos (sin redondeo adicional).

Uso (desde tarea_6/):
    python poster/generar_poster.py
"""

from pathlib import Path

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "poster"
FUENTES = RAIZ / ".claude" / "skills" / "graficando-enaho" / "fuentes"

# --- Tipografía Montserrat -------------------------------------------------
def fuente(peso):
    return font_manager.FontProperties(fname=str(FUENTES / f"Montserrat-{peso}.ttf"))

BLACK, BOLD, SEMI, MEDIUM, REGULAR = (
    fuente("Black"), fuente("Bold"), fuente("SemiBold"),
    fuente("Medium"), fuente("Regular"),
)

# --- Paleta: azul noche + una sola gama de azules + blanco -----------------
FONDO = "#0b1f3a"
BLANCO = "#ffffff"
AZUL_TENUE = "#1c3a63"     # marcas finas, celdas apagadas
AZUL_MEDIO = "#4f7fb8"     # etiquetas secundarias
AZUL_CLARO = "#9cc3ec"     # texto de apoyo
GAMA = LinearSegmentedColormap.from_list(
    "azules", ["#2a5a94", "#5d93d1", "#a9d0f5", "#e3f1ff"]
)

# --- Datos (las cifras se muestran como texto, tal como están en el CSV) ---
dep = pd.read_csv(RAIZ / "mapas" / "pobreza_departamento.csv",
                  dtype={"departamento": str, "pobreza_pct": str})
dep["valor"] = dep["pobreza_pct"].astype(float)
dep = dep.sort_values("valor", ascending=False).reset_index(drop=True)

area = pd.read_csv(RAIZ / "figuras" / "pobreza_area.csv", dtype={"pct": str})
area["valor"] = area["pct"].astype(float)
area = area.set_index("grupo")


def miles(numero):
    """6486385.0 -> '6,486,385' (el valor es entero en el CSV)."""
    return f"{int(numero):,}"


def pct(valor):
    """Un decimal, con el mismo formato que graficando-enaho y mapeando-enaho."""
    return f"{valor:.1f}"


# --- Lienzo: 12 x 16 pulgadas, coordenadas de 0-120 x 0-160 ----------------
W, H = 120, 160
fig = plt.figure(figsize=(12, 16), facecolor=FONDO)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.set_aspect("equal")
ax.axis("off")
ax.add_patch(Rectangle((0, 0), W, H, color=FONDO, zorder=0))

M = 8  # margen

# --- Cabecera --------------------------------------------------------------
ax.text(M, 151.5, "PERÚ  ·  ENAHO 2024", fontproperties=SEMI, fontsize=10,
        color=AZUL_CLARO, ha="left", va="center")
ax.text(W - M, 151.5, "Nº 01  /  OBSERVACIÓN ANUAL", fontproperties=MEDIUM,
        fontsize=8.5, color=AZUL_MEDIO, ha="right", va="center")
ax.plot([M, W - M], [148.5, 148.5], color=AZUL_TENUE, lw=0.8)

ax.text(M - 0.6, 140.5, "POBREZA", fontproperties=BLACK, fontsize=74,
        color=BLANCO, ha="left", va="center")
ax.text(M - 0.6, 129.5, "MONETARIA", fontproperties=BLACK, fontsize=74,
        color=GAMA(0.55), ha="left", va="center")
ax.text(M, 121.5,
        "Porcentaje de la población en situación de pobreza monetaria, "
        "por área de residencia y por departamento.",
        fontproperties=REGULAR, fontsize=10.5, color=AZUL_CLARO,
        ha="left", va="center")

# --- Bloque 1: área de residencia (retículas de 10 x 10) --------------------
ax.text(M, 114, "01   ÁREA DE RESIDENCIA", fontproperties=BOLD, fontsize=9,
        color=AZUL_MEDIO, ha="left", va="center")
ax.text(W - M, 114, "cada celda = 1 % de la población", fontproperties=REGULAR,
        fontsize=8, color=AZUL_MEDIO, ha="right", va="center")
ax.plot([M, W - M], [111.5, 111.5], color=AZUL_TENUE, lw=0.6)


def reticula(x0, y_sup, valor, color):
    """100 celdas = 100 % de la población; se encienden 'valor' celdas
    (la última, en proporción exacta a la fracción decimal)."""
    lado, paso = 1.7, 2.2
    for k in range(100):
        fila, col = divmod(k, 10)
        x = x0 + col * paso
        y = y_sup - (fila + 1) * paso + (paso - lado)
        ax.add_patch(Rectangle((x, y), lado, lado, color=AZUL_TENUE, lw=0))
        lleno = min(max(valor - k, 0), 1)
        if lleno > 0:
            ax.add_patch(Rectangle((x, y), lado * lleno, lado, color=color, lw=0))
    return lado, paso


bloques = [("Rural", M, GAMA(0.85)), ("Urbana", 64, GAMA(0.35))]
for grupo, x0, color in bloques:
    fila = area.loc[grupo]
    y_sup = 106.5
    reticula(x0, y_sup, fila["valor"], color)
    xt = x0 + 24.5
    ax.text(xt, y_sup - 1.2, grupo.upper(), fontproperties=BOLD, fontsize=10,
            color=AZUL_CLARO, ha="left", va="center")
    ax.text(xt - 0.4, y_sup - 9.2, pct(fila["valor"]), fontproperties=BLACK,
            fontsize=40, color=BLANCO, ha="left", va="center")
    ax.text(xt, y_sup - 15.6, "% en pobreza", fontproperties=MEDIUM,
            fontsize=9.5, color=AZUL_CLARO, ha="left", va="center")
    ax.text(xt, y_sup - 19.4,
            f"Población expandida: {miles(fila['personas_expandidas'])}",
            fontproperties=REGULAR, fontsize=7.5, color=AZUL_MEDIO,
            ha="left", va="center")
    ax.text(xt, y_sup - 21.4,
            f"Encuestados: {miles(fila['encuestados'])}",
            fontproperties=REGULAR, fontsize=7.5, color=AZUL_MEDIO,
            ha="left", va="center")

# --- Bloque 2: departamentos (escalas de 0 a 50 %) --------------------------
ax.text(M, 79.5, "02   DEPARTAMENTOS", fontproperties=BOLD, fontsize=9,
        color=AZUL_MEDIO, ha="left", va="center")
ax.text(W - M, 79.5, "ordenados de mayor a menor", fontproperties=REGULAR,
        fontsize=8, color=AZUL_MEDIO, ha="right", va="center")
ax.plot([M, W - M], [77, 77], color=AZUL_TENUE, lw=0.6)

X0, X1 = 32, 100            # inicio y fin de la escala (0 % y 50 %)
ESC = (X1 - X0) / 50
Y_TOP, PASO = 71.5, 2.42     # primera fila y separación entre filas
y_fin = Y_TOP - (len(dep) - 1) * PASO

# Escala superior y guías verticales cada 10 %
for p in range(0, 51, 10):
    x = X0 + p * ESC
    ax.text(x, 74.6, f"{p} %", fontproperties=MEDIUM, fontsize=7.5,
            color=AZUL_MEDIO, ha="center", va="center")
    ax.plot([x, x], [73.4, y_fin - 1.2], color=AZUL_TENUE, lw=0.6, zorder=1)

vmin, vmax = dep["valor"].min(), dep["valor"].max()
for i, fila in dep.iterrows():
    y = Y_TOP - i * PASO
    t = (fila["valor"] - vmin) / (vmax - vmin)
    color = GAMA(0.15 + 0.85 * t)
    x_fin = X0 + fila["valor"] * ESC
    ax.add_patch(Rectangle((X0, y - 0.62), x_fin - X0, 1.24,
                           color=color, lw=0, zorder=2))
    ax.text(X0 - 1.6, y, fila["nombre"], fontproperties=SEMI if i < 5 else MEDIUM,
            fontsize=9.5, color=BLANCO if i < 5 else AZUL_CLARO,
            ha="right", va="center")
    ax.text(x_fin + 1.2, y, pct(fila["valor"]),
            fontproperties=BOLD if i < 5 else MEDIUM, fontsize=9,
            color=BLANCO, ha="left", va="center")

# --- Pie --------------------------------------------------------------------
ax.plot([M, W - M], [9.5, 9.5], color=AZUL_TENUE, lw=0.8)
ax.text(M, 6.2, "Fuente: INEI, ENAHO 2024", fontproperties=SEMI, fontsize=9,
        color=BLANCO, ha="left", va="center")
ax.text(W - M, 6.2,
        "Cifras ponderadas con el factor de expansión facpob07. "
        "Residentes habituales.",
        fontproperties=REGULAR, fontsize=7.5, color=AZUL_MEDIO,
        ha="right", va="center")

for ext in ("png", "pdf"):
    fig.savefig(SALIDA / f"poster_pobreza_2024.{ext}", dpi=200,
                facecolor=FONDO)
print("Póster guardado en", SALIDA)
