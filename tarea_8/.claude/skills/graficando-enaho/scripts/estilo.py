"""Estilo común de los gráficos y el mapa de la ENAHO: Montserrat, escala de azules, encabezado y nota de fuente.

Lo usan graficando-enaho/scripts/graficar.py y mapeando-enaho/scripts/mapear.py. No se ejecuta solo.
"""
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402

# --- Paleta ----------------------------------------------------------------------------------------------------
AZUL_MARINO = "#0B2545"      # título, barra de mayor valor, tramo más oscuro del mapa
AZUL = "#2563A8"             # barras
AZUL_PROMEDIO = "#8DA9C4"    # línea del promedio nacional
AZUL_CLARO = "#EAF1FB"       # tramo más claro del mapa
TEXTO_PROMEDIO = "#5A7895"   # etiqueta del promedio: el mismo tono, más oscuro para que se lea sobre blanco
REJILLA = "#E3E9F1"
GRIS_SUBTITULO = "#4A5A6A"
GRIS_NOTA = "#7A8796"
TEXTO = "#1E2B3A"
BLANCO = "#FFFFFF"

DPI = 200
BASE = Path("salidas")
FIGURAS, MAPAS = Path("figuras"), Path("mapas")
UNIDAD = "% de personas en pobreza monetaria"

# --- Tipografía ------------------------------------------------------------------------------------------------
FUENTES = Path(__file__).resolve().parents[1] / "fuentes"
_ARCHIVOS = {"regular": "Montserrat-Regular.ttf", "medium": "Montserrat-Medium.ttf",
             "semibold": "Montserrat-SemiBold.ttf", "bold": "Montserrat-Bold.ttf", "black": "Montserrat-Black.ttf"}


def fuente(peso="regular", tam=10):
    """FontProperties de Montserrat con el peso exacto (se carga desde el archivo, sin depender del sistema)."""
    return font_manager.FontProperties(fname=FUENTES / _ARCHIVOS[peso], size=tam)


def configurar():
    """Registra Montserrat y deja los valores por defecto del estilo (fondo blanco, ticks grises, sin bordes)."""
    faltan = [a for a in _ARCHIVOS.values() if not (FUENTES / a).exists()]
    if faltan:
        sys.exit(f"ERROR: faltan fuentes en {FUENTES}: {faltan}. Bájenlas de "
                 "https://github.com/JulietaUla/Montserrat/tree/master/fonts/ttf")
    sys.stdout.reconfigure(encoding="utf-8")        # tildes legibles también en la consola de Windows
    for a in _ARCHIVOS.values():
        font_manager.fontManager.addfont(str(FUENTES / a))
    plt.rcParams.update({
        "font.family": "Montserrat", "font.weight": "regular", "font.size": 10,
        "figure.facecolor": BLANCO, "axes.facecolor": BLANCO, "savefig.facecolor": BLANCO,
        "axes.edgecolor": REJILLA, "axes.labelcolor": GRIS_SUBTITULO, "text.color": TEXTO,
        "xtick.color": GRIS_SUBTITULO, "ytick.color": GRIS_SUBTITULO,
        "xtick.labelsize": 10, "ytick.labelsize": 10, "axes.unicode_minus": False,
    })


# --- Datos -----------------------------------------------------------------------------------------------------
def cargar_base(anio=2024):
    """Lee salidas/personas_<anio>.parquet; si no existe, termina con un mensaje claro."""
    ruta = BASE / f"personas_{anio}.parquet"
    if not ruta.exists():
        sys.exit(f"ERROR: no existe {ruta.as_posix()}. Usa primero la skill limpiando-enaho:\n"
                 f"    uv run .claude/skills/limpiando-enaho/scripts/limpiar.py --anio {anio}\n"
                 "(desde la carpeta tarea_8/).")
    return pd.read_parquet(ruta)


def pobreza_personas(base, por):
    """Método de personas, para atributos individuales (sexo, edad): residentes habituales ponderados con facpob07.

    Devuelve % de personas pobres, población expandida y tamaño muestral (personas) por grupo.
    """
    g = base.assign(_wp=base.pobre * base.facpob07).groupby(por, observed=True)
    return pd.DataFrame({"pct": g._wp.sum() / g.facpob07.sum() * 100, "poblacion": g.facpob07.sum(),
                         "n": g.size()})


def pobreza_hogar(base, por=None):
    """Método oficial del INEI, para indicadores de nivel hogar (nacional, área, dominio, departamento).

    Usa una fila por hogar (hogar_rep == 1) ponderada con factor07 × mieperho (peso_hogar), como la sumaria.
    Devuelve % de personas pobres, población expandida y tamaño muestral (hogares) por grupo.
    """
    if "peso_hogar" not in base or "hogar_rep" not in base:
        sys.exit("ERROR: la base no tiene peso_hogar ni hogar_rep. Vuelve a correr la skill limpiando-enaho.")
    h = base[base.hogar_rep == 1]
    h = h.assign(_wp=h.pobre * h.peso_hogar, _g="Perú" if por is None else None)
    g = h.groupby("_g" if por is None else por, observed=True)
    return pd.DataFrame({"pct": g._wp.sum() / g.peso_hogar.sum() * 100, "poblacion": g.peso_hogar.sum(),
                         "n": g.size()})


def promedio_nacional(base):
    """Pobreza nacional oficial (método de la sumaria): la línea de referencia de todos los gráficos."""
    return float(pobreza_hogar(base).pct.iloc[0])


def periodo(base):
    anios = sorted(base["ano"].astype(str).unique())
    return anios[0] if len(anios) == 1 else f"{anios[0]}–{anios[-1]}"


def pct_txt(v):
    return f"{v:.1f} %"


def conjuncion_y(siguiente):
    """«y» o «e» según la palabra que sigue: «Huánuco e Ica», pero «Cusco y Hierro»."""
    s = siguiente.strip().lower()
    return "e" if (s.startswith(("i", "í")) or (s.startswith(("hi", "hí")) and not s.startswith("hie"))) else "y"


def nota_fuente(anio):
    return f"Fuente: INEI, ENAHO {anio}. Elaboración propia con factores de expansión"


# --- Composición -----------------------------------------------------------------------------------------------
def _ajustar(fig, texto, props, ancho_pulg):
    """Parte un texto en líneas que quepan en ancho_pulg pulgadas, medido con la fuente real.

    Usa el menor número de líneas posible y, con ese número, las líneas más parejas: así no queda una palabra
    sola en la segunda línea.
    """
    r = fig.canvas.get_renderer()

    def cabe(lineas):
        for linea in lineas:
            t = fig.text(0, 0, linea, fontproperties=props)
            ancho = t.get_window_extent(r).width / fig.dpi
            t.remove()
            if ancho > ancho_pulg:
                return False
        return True

    opciones = [textwrap.wrap(texto, n) for n in range(len(texto), 10, -1)]
    validas = [o for o in opciones if cabe(o)]
    if not validas:
        return texto
    minimo = min(len(o) for o in validas)
    return "\n".join([o for o in validas if len(o) == minimo][-1])


def encabezado(fig, titulo, subtitulo, margen_x=0.6, margen_sup=0.5, ancho=None):
    """Título (Montserrat Black 20 pt, azul marino) y subtítulo (Regular 12 pt), alineados a la izquierda.

    Las medidas van en pulgadas. Devuelve la altura (fracción de la figura) donde termina el encabezado, para
    colocar el gráfico debajo con aire.
    """
    w, h = fig.get_size_inches()
    ancho = ancho or (w - 2 * margen_x)
    p_tit, p_sub = fuente("black", 20), fuente("regular", 12)
    titulo = _ajustar(fig, titulo, p_tit, ancho)
    subtitulo = _ajustar(fig, subtitulo, p_sub, ancho)
    x = margen_x / w
    y = 1 - margen_sup / h
    t = fig.text(x, y, titulo, fontproperties=p_tit, color=AZUL_MARINO, va="top", ha="left", linespacing=1.15)
    alto_tit = t.get_window_extent(fig.canvas.get_renderer()).height / fig.dpi
    y_sub = y - (alto_tit + 0.14) / h
    s = fig.text(x, y_sub, subtitulo, fontproperties=p_sub, color=GRIS_SUBTITULO, va="top", ha="left",
                 linespacing=1.3)
    alto_sub = s.get_window_extent(fig.canvas.get_renderer()).height / fig.dpi
    return y_sub - alto_sub / h


def pie(fig, anio, margen_x=0.6, margen_inf=0.32):
    """Nota de fuente en 8.5 pt, gris, alineada a la izquierda en el pie."""
    w, h = fig.get_size_inches()
    fig.text(margen_x / w, margen_inf / h, nota_fuente(anio), fontproperties=fuente("regular", 8.5),
             color=GRIS_NOTA, ha="left", va="bottom")


def ejes_limpios(ax, rejilla="y"):
    """Sin bordes superior, derecho ni izquierdo; rejilla muy tenue sobre el eje de valores, detrás de las barras."""
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color("#C9D3DF")
    ax.grid(axis=rejilla, color=REJILLA, linewidth=0.9)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, pad=6)
    for etiqueta in ax.get_xticklabels() + ax.get_yticklabels():
        etiqueta.set_fontproperties(fuente("regular", 10))


def guardar(fig, ruta):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=DPI, facecolor=BLANCO)
    plt.close(fig)
    print(f"Guardé {ruta.as_posix()}")
