"""Gráfico de la inflación interanual de Lima Metropolitana (BCRP, PN01273PM), enero 2019 a diciembre 2024.

Los datos no se copian a mano: el script levanta el servidor MCP del proyecto (mcp/server.py) con fastmcp.Client
y llama a sus herramientas serie y resumen. El estilo (Montserrat, azules, encabezado) sale de
.claude/skills/graficando-enaho/scripts/estilo.py.

Uso, desde la carpeta tarea_8:
    uv run informes/grafico_bcrp.py
"""
import asyncio
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / ".claude" / "skills" / "graficando-enaho" / "scripts"))
import estilo as e  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

CODIGO = "PN01273PM"
DESDE, HASTA = "2019-01", "2024-12"
META = (1, 3)   # rango meta de inflación del BCRP, en %: es la política monetaria, no un dato de la serie
SALIDA = RAIZ / "figuras" / "bcrp_inflacion_2019_2024.png"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "setiembre", "octubre",
         "noviembre", "diciembre"]


def _contenido(resultado):
    """El dict que devolvió la herramienta (fastmcp lo da en .data o en .structured_content)."""
    datos = getattr(resultado, "data", None)
    if isinstance(datos, dict):
        return datos
    return resultado.structured_content


async def pedir_datos():
    transporte = StdioTransport(command=sys.executable, args=[str(RAIZ / "mcp" / "server.py")], cwd=str(RAIZ))
    async with Client(transporte) as cliente:
        args = {"codigo": CODIGO, "desde": DESDE, "hasta": HASTA}
        serie = _contenido(await cliente.call_tool("serie", args))
        resumen = _contenido(await cliente.call_tool("resumen", args))
    return serie, resumen


def mes_txt(periodo):
    p = pd.Period(periodo, "M")
    return f"{MESES[p.month - 1]} de {p.year}"


def graficar(serie, resumen):
    e.configurar()
    df = pd.DataFrame(serie["datos"])
    df["fecha"] = pd.PeriodIndex(df.periodo, freq="M").to_timestamp()

    maximo, ultimo = resumen["maximo"], resumen["ultimo"]
    titulo = (f"La inflación de Lima Metropolitana llegó a {maximo['valor']:.1f} % en {mes_txt(maximo['periodo'])} "
              f"y cerró 2024 en {ultimo['valor']:.1f} %")
    subtitulo = "Lima Metropolitana, enero de 2019 a diciembre de 2024 · Variación % del IPC en 12 meses, mensual"

    fig = plt.figure(figsize=(10, 6.2))
    tope = e.encabezado(fig, titulo, subtitulo)
    w, h = fig.get_size_inches()
    ax = fig.add_axes([0.9 / w, 0.85 / h, 1 - 1.5 / w, tope - 0.45 / h - 0.85 / h])

    ax.axhspan(*META, color=e.AZUL_CLARO, zorder=0)
    ax.text(df.fecha.iloc[0], META[0] + 0.1, "Rango meta del BCRP (1 % a 3 %)", va="bottom", ha="left",
            fontproperties=e.fuente("medium", 9), color=e.TEXTO_PROMEDIO)
    ax.plot(df.fecha, df.valor, color=e.AZUL, linewidth=2.2, zorder=3)

    for punto, pos in ((maximo, (0, 10)), (ultimo, (0, 10))):
        x = pd.Period(punto["periodo"], "M").to_timestamp()
        ax.scatter([x], [punto["valor"]], s=36, color=e.AZUL_MARINO, zorder=4)
        ax.annotate(f"{punto['valor']:.1f} %", (x, punto["valor"]), xytext=pos, textcoords="offset points",
                    ha="center", va="bottom", fontproperties=e.fuente("bold", 10), color=e.AZUL_MARINO)

    ax.set_ylim(0, 10)
    ax.set_yticks(range(0, 11, 2))
    ax.set_yticklabels([f"{v} %" for v in range(0, 11, 2)])
    ax.set_xlim(df.fecha.iloc[0] - pd.Timedelta(days=20), df.fecha.iloc[-1] + pd.Timedelta(days=25))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    e.ejes_limpios(ax, rejilla="y")

    fig.text(0.6 / w, 0.32 / h, f"Fuente: BCRP, serie {CODIGO} (IPC de Lima Metropolitana, variación % 12 meses), "
             f"{DESDE} a {HASTA}. Elaboración propia", fontproperties=e.fuente("regular", 8.5), color=e.GRIS_NOTA,
             ha="left", va="bottom")
    e.guardar(fig, SALIDA)


def main():
    try:
        serie, resumen = asyncio.run(pedir_datos())
    except Exception as err:    # el servidor no arrancó o la API del BCRP no respondió
        sys.exit(f"ERROR: no pude obtener {CODIGO} del servidor MCP: {err}")
    if not serie or not serie.get("datos"):
        sys.exit(f"ERROR: el servidor MCP no devolvió datos de {CODIGO} entre {DESDE} y {HASTA}.")
    graficar(serie, resumen)
    print(f"{len(serie['datos'])} meses de {CODIGO}; máximo {resumen['maximo']}, último {resumen['ultimo']}")
    print(f"Fuente consultada por el servidor: {serie['fuente']}")


if __name__ == "__main__":
    main()
