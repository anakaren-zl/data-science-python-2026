"""Servidor MCP del BCRP. Empiecen aquí: buscar_series ya funciona; completen los TODO hasta que pasen las pruebas.

    uv run pytest                                           # el contrato: las 8 pruebas deben pasar
    uv run server.py                                        # el servidor, por stdio
    claude mcp add --scope project bcrp -- uv run server.py # conectarlo a Claude Code

Las cuentas las hace Python, no el modelo: así cada cifra sale de una llamada que se puede repetir.
"""
import re
import time
import unicodedata
from functools import cache
from pathlib import Path

import httpx
import pandas as pd
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from matplotlib import colormaps
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from matplotlib.patches import Polygon

AQUI = Path(__file__).parent
CATALOGO = AQUI / "datos" / "catalogo_bcrp.csv"
URL_CATALOGO = "https://estadisticas.bcrp.gob.pe/estadisticas/series/metadata"
API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": True}

mcp = FastMCP("bcrp", instructions=(
    "Series oficiales del Banco Central de Reserva del Perú (BCRP). Primero busca el código con buscar_series; "
    "luego usa resumen para variaciones, promedios y extremos, y serie para los datos. No calcules a mano: "
    "cita siempre el código de la serie y el periodo."))


def _sin_tildes(s):
    return unicodedata.normalize("NFD", str(s).lower()).encode("ascii", "ignore").decode()


@cache
def catalogo():
    """El catálogo oficial: 17 mil series en unos 7 MB. Se baja una vez y queda en datos/."""
    if not CATALOGO.exists():
        CATALOGO.parent.mkdir(exist_ok=True)
        r = httpx.get(URL_CATALOGO, timeout=120)
        r.raise_for_status()
        CATALOGO.write_text(r.content.decode("latin-1"), encoding="utf-8")
    df = pd.read_csv(CATALOGO, sep=";", dtype=str).fillna("")
    df = df.rename(columns={"Código de serie": "codigo", "Categoría de serie": "categoria", "Grupo de serie": "grupo",
                            "Nombre de serie": "nombre", "Frecuencia": "frecuencia",
                            "Fecha de actualización": "actualizada", "Fecha de inicio": "inicio"})
    df["texto"] = (df.categoria + " " + df.grupo + " " + df.nombre).map(_sin_tildes)
    return df


def _ficha(codigo):
    fila = catalogo().query("codigo == @codigo")
    if fila.empty:
        raise ToolError(f"No existe el código de serie {codigo!r}. Búsquenlo con buscar_series.")
    f = fila.iloc[0]
    return {"codigo": f.codigo, "nombre": f"{f.grupo} - {f.nombre}", "categoria": f.categoria,
            "frecuencia": f.frecuencia, "inicio": f.inicio, "actualizada": f.actualizada}


@mcp.tool(annotations=SOLO_LECTURA)
def buscar_series(texto: str, frecuencia: str | None = None, limite: int = 10) -> list[dict]:
    """Busca series del BCRP por palabras: todas deben aparecer en la categoría, el grupo o el nombre.

    Ejemplos: "ipc 12 meses", "tipo de cambio interbancario venta", "reservas internacionales netas",
    "tasa de referencia", "cobre precio". frecuencia: "Diaria", "Mensual", "Trimestral" o "Anual".
    Devuelve el código, el nombre completo, la frecuencia y desde cuándo hay datos. Si no hay resultados,
    prueben con menos palabras.
    """
    df = catalogo()
    m = pd.Series(True, index=df.index)
    for palabra in _sin_tildes(texto).split():
        m &= df.texto.str.contains(re.escape(palabra))
    if frecuencia:
        m &= df.frecuencia.str.lower() == frecuencia.lower()
    # primero las series vigentes y, entre ellas, las de nombre más corto (las más generales)
    sel = df[m]
    orden = sel.assign(vieja=sel.actualizada < "2025", largo=(sel.grupo + sel.nombre).str.len())
    return [_ficha(c) for c in orden.sort_values(["vieja", "largo"]).head(limite).codigo]


# TODO 1 · serie(codigo, desde, hasta) -> {"codigo", "nombre", "frecuencia", "datos": [{"periodo", "valor"}], "fuente"}
#   La API se llama así: f"{API}/{codigo}/json/{desde}/{hasta}" y responde
#   {"config": {...}, "periods": [{"name": "Ene.2025", "values": ["0.81"]}, ...]}
#   - Fechas que pide la API: 2025-1 (mensual y trimestral), 2025-01-15 (diaria), 2025 (anual).
#   - Nombres que devuelve: "Ene.2025" (mensual), "01.Oct.26" (diaria), "T1.25" (trimestral), "2025" (anual).
#     Setiembre viene como "Set". Devuelvan el periodo como "2025-01", "2026-10-01", "2025-T1" o "2025".
#   - Salten los valores "n.d." y usen la frecuencia de _ficha(codigo) para saber qué formato pedir.
#   - Si recibe muchos pedidos seguidos, la API responde una página HTML en vez de JSON: esperen unos segundos y
#     reintenten (y guarden en caché lo que ya bajaron).
#   - Un código que no existe debe dar un ToolError que diga el código.

MESES = {"Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6, "Jul": 7, "Ago": 8, "Set": 9, "Sep": 9,
         "Oct": 10, "Nov": 11, "Dic": 12}


def _anio(a):
    return a if len(a) == 4 else ("19" if int(a) > 50 else "20") + a


def _periodo(nombre):
    """Turn a BCRP period name into a sortable label.

    "Ene.2025" -> "2025-01" (monthly), "01.Oct.26" -> "2026-10-01" (daily),
    "T1.25" -> "2025-T1" (quarterly), "2025" -> "2025" (annual).
    """
    partes = nombre.split(".")
    if len(partes) == 3:                                  # daily: day.month.year
        dia, mes, anio = partes
        return f"{_anio(anio)}-{MESES[mes]:02d}-{dia}"
    if len(partes) == 2 and partes[0].startswith("T"):    # quarterly: quarter.year
        return f"{_anio(partes[1])}-{partes[0]}"
    if len(partes) == 2:                                  # monthly: month.year
        mes, anio = partes
        return f"{anio}-{MESES[mes]:02d}"
    return nombre                                         # annual: already "2025"


@cache
def _descargar(codigo, desde, hasta):
    """Ask the BCRP API for one series. Retry when it answers with an HTML page instead of JSON."""
    url = f"{API}/{codigo}/json/{desde}/{hasta}"
    for intento in range(4):
        try:
            return url, httpx.get(url, timeout=60).json()["periods"]
        except (httpx.HTTPError, ValueError, KeyError):
            time.sleep(2 * (intento + 1))   # wait 2, 4, 6 and 8 seconds
    raise ToolError(f"El BCRP no respondió con datos para {codigo!r}. Esperen unos segundos y reintenten.")


def _fecha_api(fecha, frecuencia):
    """Turn a user date into the API format: "2025-01" -> "2025-1" and "2025-T1" -> "2025-1"."""
    frecuencia = frecuencia.lower()
    if frecuencia in ("mensual", "trimestral"):
        anio, parte = fecha.split("-")[:2]
        return f"{anio}-{int(parte.lstrip('T'))}"
    if frecuencia == "anual":
        return fecha[:4]
    return fecha                                          # daily: already "2026-10-01"


@mcp.tool(annotations=SOLO_LECTURA)
def serie(codigo: str, desde: str, hasta: str) -> dict:
    """Data points of one BCRP series between two dates, both included.

    Use it after buscar_series, when you need the actual values. Dates: "2025-01" (monthly),
    "2025-01-15" (daily), "2025-T1" (quarterly) or "2025" (annual). Example: codigo="PN01273PM",
    desde="2025-01", hasta="2025-12". Returns the values and the source URL: cite the code and the period.
    """
    ficha = _ficha(codigo)
    frecuencia = ficha["frecuencia"]
    url, periodos = _descargar(codigo, _fecha_api(desde, frecuencia), _fecha_api(hasta, frecuencia))
    datos = [{"periodo": _periodo(p["name"]), "valor": float(p["values"][0])}
             for p in periodos if p["values"][0] != "n.d."]
    return {"codigo": codigo, "nombre": ficha["nombre"], "frecuencia": frecuencia, "datos": datos, "fuente": url}


# TODO 2 · resumen(codigo, desde, hasta): primero, ultimo, cambio, variacion_pct, promedio, maximo y minimo
#   (los tres últimos con su periodo). Úsenla para que el modelo nunca haga cuentas a mano.

def _punto(fila):
    return {"periodo": fila.periodo, "valor": round(float(fila.valor), 4)}


@mcp.tool(annotations=SOLO_LECTURA)
def resumen(codigo: str, desde: str, hasta: str) -> dict:
    """Summary of one BCRP series between two dates: first and last value, change, percent change,
    mean, maximum and minimum (each extreme with its period).

    Use it whenever the question asks for a variation, an average, a peak or a low, so you never do the math
    yourself. Same dates as serie. Example: codigo="PN01273PM", desde="2025-12", hasta="2026-09".
    """
    s = serie(codigo, desde, hasta)
    if not s["datos"]:
        raise ToolError(f"La serie {codigo!r} no tiene datos entre {desde} y {hasta}.")
    df = pd.DataFrame(s["datos"])
    primero, ultimo = df.iloc[0], df.iloc[-1]
    return {"codigo": codigo, "nombre": s["nombre"], "primero": _punto(primero), "ultimo": _punto(ultimo),
            "cambio": round(float(ultimo.valor - primero.valor), 4),
            "variacion_pct": round(float((ultimo.valor / primero.valor - 1) * 100), 2) if primero.valor else None,
            "promedio": round(float(df.valor.mean()), 4),
            "maximo": _punto(df.loc[df.valor.idxmax()]), "minimo": _punto(df.loc[df.valor.idxmin()]),
            "fuente": s["fuente"]}


# TODO 3 · Una herramienta suya, bien descrita. Ideas:
#   - comparar_paises con la API del Banco Mundial, que tampoco pide clave:
#     https://api.worldbank.org/v2/country/PER;CHL;COL/indicator/NY.GDP.MKTP.KD.ZG?format=json&date=2015:2025
#   - correlacion(codigo_a, codigo_b, desde, hasta)
#   - grafico(codigo, desde, hasta) que guarde un PNG en salidas/ y devuelva la ruta


# chart colors: a cyan -> magenta scale that follows the value, gray ink for text, a near-white surface
PALETA, FONDO, TINTA, TINTA_SUAVE, REJILLA = colormaps["cool"], "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
MESES_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _etiqueta(periodo):
    """Short axis label: "2025-01" -> "Jan 2025", "2026-10-01" -> "01 Oct 2026"; other periods stay as they are."""
    p = periodo.split("-")
    if len(p) == 2 and p[1].isdigit():
        return f"{MESES_EN[int(p[1]) - 1]} {p[0]}"
    if len(p) == 3:
        return f"{p[2]} {MESES_EN[int(p[1]) - 1]} {p[0]}"
    return periodo


@mcp.tool(annotations={"openWorldHint": True})
def grafico(codigo: str, desde: str, hasta: str, titulo: str | None = None) -> dict:
    """Line chart (PNG) of one BCRP series between two dates, saved in the salidas/ folder.

    Use it when the user asks to see, plot or chart a series, or needs a figure for a report.
    Same dates as serie. titulo is optional: a short sentence with the main finding, for example
    "Inflation in Lima climbed back above 4% in 2026"; without it, the chart uses the official series name.
    Example: codigo="PN01273PM", desde="2024-01", hasta="2026-09".
    Returns the path of the PNG, the last value, the maximum, the minimum and the source URL.
    """
    s = serie(codigo, desde, hasta)
    if not s["datos"]:
        raise ToolError(f"La serie {codigo!r} no tiene datos entre {desde} y {hasta}.")
    df = pd.DataFrame(s["datos"])
    x, y = list(range(len(df))), list(df.valor)          # one position per period, evenly spaced
    ultimo, maximo, minimo = df.iloc[-1], df.loc[df.valor.idxmax()], df.loc[df.valor.idxmin()]
    piso = min(y) - (max(y) - min(y)) * 0.2               # room below the line for the "Low" label
    tope = max(y) + (max(y) - min(y)) * 0.18              # room above the line for the "High" label
    color = lambda v: PALETA((v - piso) / (max(y) - piso or 1))   # low values cyan, high values magenta

    fig = Figure(figsize=(10, 5.6), dpi=200, facecolor=FONDO)
    ax = fig.subplots()
    ax.set_facecolor(FONDO)
    ax.set_xlim(x[0] - 0.6, x[-1] + 0.6)
    ax.set_ylim(piso, tope)

    # soft gradient under the line: a vertical cyan -> magenta image cut to the shape of the area
    area = Polygon([(x[0], piso), *zip(x, y), (x[-1], piso)], facecolor="none", edgecolor="none")
    ax.add_patch(area)
    fondo = ax.imshow([[i / 255] for i in range(256)], cmap=PALETA, aspect="auto", origin="lower",
                      extent=[x[0], x[-1], piso, max(y)], alpha=0.22, zorder=1)
    fondo.set_clip_path(area)

    # the line, one short segment per period, each colored by its value
    tramos = [[(x[i], y[i]), (x[i + 1], y[i + 1])] for i in range(len(x) - 1)]
    linea = LineCollection(tramos, cmap=PALETA, linewidth=2.6, capstyle="round", joinstyle="round", zorder=2)
    linea.set_array([(y[i] + y[i + 1]) / 2 for i in range(len(x) - 1)])
    linea.set_clim(piso, max(y))
    ax.add_collection(linea)

    # selective labels: the last value stands out; the peak and the low stay quiet
    ax.scatter([x[-1]], [y[-1]], s=80, color=color(y[-1]), edgecolor=FONDO, linewidth=2, zorder=3)
    ax.annotate(f"{ultimo.valor:,.2f}", (x[-1], y[-1]), xytext=(9, 0), textcoords="offset points",
                va="center", fontsize=11, fontweight="bold", color=TINTA)
    for fila, sube in [(maximo, True), (minimo, False)]:
        if fila.name != len(df) - 1:
            ax.scatter([fila.name], [fila.valor], s=30, color=FONDO, edgecolor=color(fila.valor), linewidth=1.6,
                       zorder=3)
            ax.annotate(f"{'High' if sube else 'Low'} {fila.valor:,.2f}\n{_etiqueta(fila.periodo)}",
                        (fila.name, fila.valor), xytext=(0, 10 if sube else -12), textcoords="offset points",
                        ha="center", va="bottom" if sube else "top", fontsize=8, color=TINTA_SUAVE)

    paso = max(1, len(df) // 7)                           # at most about 7 labels on the x axis
    ax.set_xticks(x[::paso], [_etiqueta(p) for p in df.periodo[::paso]])
    ax.grid(axis="y", color=REJILLA, linewidth=1)
    ax.set_axisbelow(True)
    for lado in ["top", "right", "left", "bottom"]:
        ax.spines[lado].set_visible(False)
    ax.tick_params(colors=TINTA_SUAVE, labelsize=9, length=0, pad=6)

    fig.text(0.06, 0.93, titulo or s["nombre"], fontsize=15, fontweight="bold", color=TINTA)
    subtitulo = f"{s['nombre']} · " if titulo else ""
    fig.text(0.06, 0.885, f"{subtitulo}{codigo} · {_etiqueta(df.periodo.iloc[0])} to {_etiqueta(ultimo.periodo)}",
             fontsize=10, color=TINTA_SUAVE)
    fig.text(0.06, 0.03, "Source: Banco Central de Reserva del Perú (BCRP), estadisticas.bcrp.gob.pe",
             fontsize=8, color=TINTA_SUAVE)
    fig.subplots_adjust(left=0.06, right=0.93, top=0.84, bottom=0.12)
    archivo = AQUI / "salidas" / f"{codigo}_{desde}_{hasta}.png"
    archivo.parent.mkdir(exist_ok=True)
    fig.savefig(archivo, facecolor=FONDO)
    return {"archivo": str(archivo), "codigo": codigo, "nombre": s["nombre"], "puntos": len(df),
            "ultimo": _punto(ultimo), "maximo": _punto(maximo), "minimo": _punto(minimo), "fuente": s["fuente"]}


# TODO 4 · Un recurso, por ejemplo la plantilla bcrp://serie/{codigo} con la ficha de la serie.


@mcp.resource("bcrp://serie/{codigo}")
def ficha(codigo: str) -> dict:
    """Catalog card of one BCRP series: full name, category, frequency, first date and last update."""
    return _ficha(codigo)


# TODO 5 · Un prompt, por ejemplo informe(tema) que pida citar el código y el periodo de cada cifra.


@mcp.prompt
def informe(tema: str) -> str:
    """Short brief on a topic, built only from official BCRP figures that anyone can check."""
    return (f"Write a short brief in five bullet points about «{tema}» with official BCRP data. "
            "First find the right series with buscar_series; then use resumen for changes, averages, highs and lows, "
            "and serie when you need the values. Do not do any math yourself. After every figure, cite the series "
            "code and the period, for example (PN01273PM, 2026-09). If a chart helps, make one with grafico.")


if __name__ == "__main__":
    mcp.run()