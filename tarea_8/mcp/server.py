"""Servidor MCP del BCRP: da acceso a las series oficiales del Banco Central de Reserva del Perú.

Componentes:
    buscar_series            herramienta: encuentra el código de una serie en el catálogo oficial
    serie                    herramienta: descarga los valores de una serie, período a período
    resumen                  herramienta: primer y último valor, cambio, variación %, promedio y extremos
    comparar_series          herramienta: alinea dos series en una frecuencia común y calcula su correlación
    bcrp://serie/{codigo}    recurso: ficha de una serie (nombre, frecuencia, inicio, actualización, enlaces)
    informe                  prompt: pide un informe breve con cada cifra citada (código, periodo y fuente)

Uso, desde la carpeta tarea_8:
    uv run pytest            # corre las pruebas de mcp/test_server.py
    uv run mcp/server.py     # levanta el servidor por stdio (Claude Code lo conecta vía .mcp.json)

Las cuentas las hace Python, no el modelo: así cada cifra sale de una llamada que se puede repetir.
"""
import json
import re
import time
import unicodedata
from functools import cache
from pathlib import Path

import httpx
import pandas as pd
from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError, ToolError

AQUI = Path(__file__).parent
CATALOGO = AQUI / "datos" / "catalogo_bcrp.csv"
URL_CATALOGO = "https://estadisticas.bcrp.gob.pe/estadisticas/series/metadata"
API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": True}

mcp = FastMCP("bcrp", instructions=(
    "Series oficiales del Banco Central de Reserva del Perú (BCRP). Primero busca el código con buscar_series; "
    "luego usa resumen para variaciones, promedios y extremos, serie para los datos y comparar_series para "
    "contrastar dos indicadores en los mismos periodos (su correlación no prueba causalidad). No calcules a mano: "
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


# ---------------------------------------------------------------------------------------------------------------
# Herramienta serie: descarga de valores oficiales desde la API del BCRP
# ---------------------------------------------------------------------------------------------------------------
MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
         "jul": 7, "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12}
ORDEN_FRECUENCIA = {"Diaria": 0, "Mensual": 1, "Trimestral": 2, "Anual": 3}
CARPETA_WEB = {"Diaria": "diarias", "Mensual": "mensuales", "Trimestral": "trimestrales", "Anual": "anuales"}
FORMATOS = '"2025" (año), "2025-T1" (trimestre), "2025-01" (mes) o "2026-10-01" (día)'
REINTENTOS = 4


def _rango(fecha, extremo):
    """Primer día ("desde") o último día ("hasta") que abarca "2025", "2025-T1", "2025-01" o "2026-10-01"."""
    f = str(fecha).strip().upper()
    try:
        if re.fullmatch(r"\d{4}", f):
            p = pd.Period(f, "Y")
        elif m := re.fullmatch(r"(\d{4})-T([1-4])", f):
            p = pd.Period(f"{m[1]}Q{m[2]}", "Q")
        elif m := re.fullmatch(r"(\d{4})-(\d{1,2})", f):
            if not 1 <= int(m[2]) <= 12:
                raise ValueError
            p = pd.Period(f"{m[1]}-{int(m[2]):02d}", "M")
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", f):
            p = pd.Period(pd.Timestamp(f), "D")
        else:
            raise ValueError
    except ValueError:
        raise ToolError(f"No entiendo la fecha {fecha!r}. Usen {FORMATOS}.") from None
    return (p.start_time if extremo == "desde" else p.end_time).normalize()


def _fecha_api(dia, frecuencia):
    """El formato de fecha que pide la API según la frecuencia de la serie."""
    if frecuencia == "Diaria":
        return dia.strftime("%Y-%m-%d")
    if frecuencia == "Mensual":
        return f"{dia.year}-{dia.month}"
    if frecuencia == "Trimestral":
        return f"{dia.year}-{dia.quarter}"
    return str(dia.year)


def _anio(a):
    """Años de dos cifras ("26" en "01.Oct.26"): del siglo actual salvo que queden en el futuro."""
    a = int(a)
    if a >= 100:
        return a
    return 2000 + a if 2000 + a <= pd.Timestamp.today().year + 1 else 1900 + a


def _periodo(nombre, frecuencia):
    """"Ene.2025" -> "2025-01", "01.Oct.26" -> "2026-10-01", "T1.25" -> "2025-T1", "2025" -> "2025"."""
    n = nombre.strip()
    try:
        if frecuencia == "Diaria":
            d, mes, a = n.split(".")
            return f"{_anio(a)}-{MESES[mes.lower()[:3]]:02d}-{int(d):02d}"
        if frecuencia == "Mensual":
            mes, a = n.split(".")
            return f"{_anio(a)}-{MESES[mes.lower()[:3]]:02d}"
        if frecuencia == "Trimestral":
            t, a = n.split(".")
            return f"{_anio(a)}-T{int(t.upper().lstrip('T'))}"
        return str(int(n))
    except (ValueError, KeyError):
        raise ToolError(f"No reconozco el periodo {nombre!r} que devolvió el BCRP para una serie {frecuencia}.") from None


@cache
def _descargar(codigo, frecuencia, desde, hasta):
    """Pide la serie a la API. Queda en caché (solo si salió bien): el mismo pedido no vuelve a salir a internet.

    Si la API devuelve HTML en vez de JSON (lo hace cuando recibe muchos pedidos seguidos), espera 1, 2 y 4
    segundos y reintenta.
    """
    url = f"{API}/{codigo}/json/{desde}/{hasta}"
    for intento in range(REINTENTOS):
        try:
            r = httpx.get(url, timeout=60, follow_redirects=True)
            r.raise_for_status()
            cuerpo = r.json()
            break
        except (httpx.HTTPError, ValueError):   # ValueError: la respuesta no era JSON (página HTML)
            if intento == REINTENTOS - 1:
                raise ToolError(f"La API del BCRP no devolvió datos de {codigo} entre {desde} y {hasta} tras "
                                f"{REINTENTOS} intentos. Puede que no haya datos en ese periodo o que la API esté "
                                f"saturada; prueben otro rango o más tarde. URL: {url}") from None
            time.sleep(2 ** intento)
    datos = []
    for p in cuerpo.get("periods", []):
        valor = (p.get("values") or ["n.d."])[0]
        try:
            datos.append((_periodo(p["name"], frecuencia), float(valor)))
        except ValueError:      # "n.d." y otros valores no numéricos se saltan
            continue
    return url, tuple(datos)


def _serie(codigo, desde, hasta):
    codigo = str(codigo).strip().upper()
    ficha = _ficha(codigo)
    frecuencia = ficha["frecuencia"]
    ini, fin = _rango(desde, "desde"), _rango(hasta, "hasta")
    if ini > fin:
        raise ToolError(f"El periodo está al revés: desde={desde!r} es posterior a hasta={hasta!r}.")
    url, datos = _descargar(codigo, frecuencia, _fecha_api(ini, frecuencia), _fecha_api(fin, frecuencia))
    if not datos:
        raise ToolError(f"La serie {codigo} ({ficha['nombre']}) no tiene valores entre {desde} y {hasta}. "
                        f"Hay datos desde {ficha['inicio']}.")
    return {"codigo": codigo, "nombre": ficha["nombre"], "frecuencia": frecuencia,
            "datos": [{"periodo": p, "valor": v} for p, v in datos], "fuente": url}


@mcp.tool(annotations=SOLO_LECTURA)
def serie(codigo: str, desde: str, hasta: str) -> dict:
    """Descarga los valores oficiales de una serie del BCRP entre dos fechas (ambas incluidas).

    Úsenla cuando necesiten los datos período por período (para una tabla o un gráfico). Para variaciones,
    promedios o extremos usen resumen, y para contrastar dos indicadores, comparar_series: no hagan las cuentas
    a mano. Si no conocen el código, búsquenlo primero con buscar_series.

    desde y hasta aceptan "2025" (año), "2025-T1" (trimestre), "2025-01" (mes) o "2026-10-01" (día), sea cual
    sea la frecuencia de la serie: "2025" en una serie mensual abarca de enero a diciembre.
    Devuelve codigo, nombre, frecuencia, datos [{periodo, valor}] y fuente (la URL consultada). Los periodos
    salen como "2025-01" (mensual), "2026-10-01" (diaria), "2025-T1" (trimestral) o "2025" (anual); los
    valores "n.d." se omiten.
    """
    return _serie(codigo, desde, hasta)


# ---------------------------------------------------------------------------------------------------------------
# Herramienta resumen: variaciones, promedios y extremos de una serie
# ---------------------------------------------------------------------------------------------------------------
def _r(x, cifras=6):
    return round(float(x), cifras)


def _estadisticas(datos):
    """Primero, último, cambio, variación %, promedio, máximo y mínimo de [{periodo, valor}] ordenados."""
    s = pd.Series([d["valor"] for d in datos], index=[d["periodo"] for d in datos], dtype=float)
    primero, ultimo = s.iloc[0], s.iloc[-1]
    cambio = ultimo - primero
    return {
        "n": int(s.size),
        "primero": {"periodo": s.index[0], "valor": _r(primero)},
        "ultimo": {"periodo": s.index[-1], "valor": _r(ultimo)},
        "cambio": _r(cambio),
        "variacion_pct": None if primero == 0 else _r(cambio / abs(primero) * 100, 4),
        "promedio": _r(s.mean()),
        "maximo": {"periodo": s.idxmax(), "valor": _r(s.max())},
        "minimo": {"periodo": s.idxmin(), "valor": _r(s.min())},
    }


@mcp.tool(annotations=SOLO_LECTURA)
def resumen(codigo: str, desde: str, hasta: str) -> dict:
    """Resume una serie del BCRP en un periodo; úsenla para cualquier variación, promedio o extremo.

    Devuelve el primer y el último valor con su periodo, el cambio absoluto (último - primero), la variación
    porcentual (cambio / |primero| x 100; None si el primero es 0), el promedio simple de los periodos y el
    máximo y el mínimo con su periodo (si se repiten, el primero en el tiempo), además de n y la fuente.

    Si la serie ya está en porcentaje (inflación, tasas), el cambio está en puntos porcentuales y suele ser lo
    que hay que reportar; la variación porcentual de una tasa rara vez tiene sentido. Las fechas aceptan los
    mismos formatos que serie.
    """
    s = _serie(codigo, desde, hasta)
    return {"codigo": s["codigo"], "nombre": s["nombre"], "frecuencia": s["frecuencia"],
            "desde": desde, "hasta": hasta, **_estadisticas(s["datos"]), "fuente": s["fuente"]}


# ---------------------------------------------------------------------------------------------------------------
# Herramienta comparar_series: dos series alineadas en una frecuencia común y su correlación
# ---------------------------------------------------------------------------------------------------------------
def _a_frecuencia(periodo, frecuencia):
    """Lleva un periodo a la clave de una frecuencia igual o menor: "2026-10-01" -> "2026-10" -> "2026-T4" -> "2026"."""
    if frecuencia == "Anual":
        return periodo[:4]
    if frecuencia == "Trimestral":
        return periodo if "-T" in periodo else f"{periodo[:4]}-T{(int(periodo[5:7]) - 1) // 3 + 1}"
    if frecuencia == "Mensual":
        return periodo[:7]
    return periodo


def _periodos_esperados(desde, hasta, frecuencia):
    """Todos los periodos del rango pedido. En diarias no se calculan: fines de semana y feriados no son faltas."""
    if frecuencia == "Diaria":
        return []
    pr = pd.period_range(_rango(desde, "desde"), _rango(hasta, "hasta"),
                         freq={"Mensual": "M", "Trimestral": "Q", "Anual": "Y"}[frecuencia])
    if frecuencia == "Mensual":
        return [p.strftime("%Y-%m") for p in pr]
    if frecuencia == "Trimestral":
        return [f"{p.year}-T{p.quarter}" for p in pr]
    return [str(p.year) for p in pr]


@mcp.tool(annotations=SOLO_LECTURA)
def comparar_series(codigo_a: str, codigo_b: str, desde: str, hasta: str) -> dict:
    """Contrasta dos series del BCRP en los mismos periodos y calcula su correlación de Pearson.

    Úsenla cuando la pregunta relacione dos indicadores (por ejemplo, tipo de cambio e inflación). Si las
    frecuencias difieren, la serie más frecuente se promedia a la frecuencia de la otra (diaria -> mensual ->
    trimestral -> anual) y lo indica en "agregacion". Las fechas aceptan los mismos formatos que serie.

    Devuelve frecuencia_comun, n_comunes, datos [{periodo, valor_a, valor_b}] (None donde falta un valor),
    sin_dato {a, b} con los periodos del rango que no tienen valor en cada serie (en diarias, solo los que la
    otra sí tiene), correlacion (None si hay menos de 3 periodos comunes o una serie es constante) y, en
    series {a, b}, el código, nombre, frecuencia original, fuente y el resumen de cada una ya alineada.

    codigo_a y codigo_b deben ser series distintas: si son la misma (sin importar mayúsculas ni espacios), se
    devuelve un ToolError en lugar de una correlación trivial de 1.

    La correlación describe una asociación lineal entre los periodos comunes; no demuestra causalidad.
    """
    if str(codigo_a).strip().upper() == str(codigo_b).strip().upper():
        raise ToolError(f"codigo_a y codigo_b son la misma serie ({str(codigo_a).strip().upper()}): comparar_series "
                        f"necesita dos series distintas. Para describir una sola serie usen resumen.")
    a, b = _serie(codigo_a, desde, hasta), _serie(codigo_b, desde, hasta)
    frecuencia = max(a["frecuencia"], b["frecuencia"], key=ORDEN_FRECUENCIA.__getitem__)

    agregacion, alineadas = [], {}
    for clave, s in (("a", a), ("b", b)):
        df = pd.DataFrame(s["datos"])
        df["periodo"] = df.periodo.map(lambda p: _a_frecuencia(p, frecuencia))
        alineadas[clave] = df.groupby("periodo").valor.mean()
        if s["frecuencia"] != frecuencia:
            agregacion.append(f"{s['codigo']} ({s['frecuencia']}) se promedió a frecuencia {frecuencia}: "
                              f"{len(df)} observaciones en {alineadas[clave].size} periodos.")

    tabla = pd.concat(alineadas, axis=1)
    periodos = sorted(set(tabla.index) | set(_periodos_esperados(desde, hasta, frecuencia)))
    tabla = tabla.reindex(periodos)
    comunes = tabla.dropna()

    correlacion = None
    if len(comunes) >= 3 and comunes.a.std() > 0 and comunes.b.std() > 0:
        correlacion = _r(comunes.a.corr(comunes.b), 4)

    def ficha(s, clave):
        datos = [{"periodo": p, "valor": v} for p, v in alineadas[clave].items()]
        return {"codigo": s["codigo"], "nombre": s["nombre"], "frecuencia": s["frecuencia"],
                "resumen": _estadisticas(datos), "fuente": s["fuente"]}

    return {
        "frecuencia_comun": frecuencia,
        "agregacion": agregacion or None,
        "n_comunes": int(len(comunes)),
        "datos": [{"periodo": p,
                   "valor_a": None if pd.isna(f.a) else _r(f.a),
                   "valor_b": None if pd.isna(f.b) else _r(f.b)} for p, f in tabla.iterrows()],
        "sin_dato": {"a": tabla.index[tabla.a.isna()].tolist(), "b": tabla.index[tabla.b.isna()].tolist()},
        "correlacion": correlacion,
        "series": {"a": ficha(a, "a"), "b": ficha(b, "b")},
    }


# ---------------------------------------------------------------------------------------------------------------
# Recurso bcrp://serie/{codigo}: la ficha descriptiva de una serie
# ---------------------------------------------------------------------------------------------------------------
@mcp.resource("bcrp://serie/{codigo}", name="ficha_serie", mime_type="application/json")
def ficha_serie(codigo: str) -> str:
    """Ficha descriptiva de una serie del BCRP: nombre, categoría, frecuencia, inicio, última actualización y
    enlaces a la página oficial y a la API. No trae valores; para eso están serie y resumen."""
    codigo = codigo.strip().upper()
    try:
        f = _ficha(codigo)
    except ToolError as e:
        raise ResourceError(str(e)) from None
    f["pagina"] = (f"https://estadisticas.bcrp.gob.pe/estadisticas/series/"
                   f"{CARPETA_WEB.get(f['frecuencia'], 'mensuales')}/resultados/{codigo}/html")
    f["api"] = f"{API}/{codigo}/json"
    f["fuente"] = "Banco Central de Reserva del Perú (BCRP), estadísticas en línea"
    return json.dumps(f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------------------------------------------
# Prompt informe: informe breve con cada cifra citada
# ---------------------------------------------------------------------------------------------------------------
@mcp.prompt
def informe(tema: str) -> str:
    """Pide un informe breve sobre un tema con series del BCRP, con cada cifra citada y sin datos inventados."""
    return f"""Elabora un informe breve sobre: {tema}

Usa únicamente las series oficiales del BCRP a las que accedes con las herramientas de este servidor.

1. Plan: di qué indicadores necesitas y búscalos con buscar_series. Si una búsqueda no da resultados, prueba con
   menos palabras; si aun así no existe la serie, dilo en lugar de sustituirla por otra sin avisar.
2. Datos: obtén las cifras con resumen (variaciones, promedios, extremos), serie (valores período a período) o
   comparar_series (dos indicadores). No hagas cuentas a mano ni completes valores que las herramientas no
   devolvieron.
3. Citas: junto a cada cifra escribe el código de la serie, el periodo exacto y la fuente, por ejemplo
   "4.55 % (PN01273PM, 2026-09, BCRP)". Si la serie está en porcentaje, reporta los cambios en puntos
   porcentuales.
4. Estructura: resumen ejecutivo (3 a 5 líneas), hallazgos con sus cifras, interpretación y limitaciones
   (cobertura temporal, frecuencia, series agregadas o con periodos sin dato).
5. Cautela: una correlación o una coincidencia temporal no prueban causalidad. Si una herramienta falla o no hay
   datos para el periodo, repórtalo como limitación; nunca inventes cifras ni referencias.

Cierra con una tabla de fuentes: código, nombre de la serie, frecuencia, periodo usado y URL consultada."""


if __name__ == "__main__":
    mcp.run()
