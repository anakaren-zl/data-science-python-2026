"""¿Mejora el agente con el MCP del BCRP y las skills de la ENAHO? Las mismas preguntas en tres modos, contra la cifra oficial.

Adaptado de evaluar.py de la Sesión 04 (sessions/04-mcp-claude-code/proyecto). Desde la carpeta tarea_8:

    uv run evaluacion/evaluar.py                     # modos A y B, con sonnet
    uv run evaluacion/evaluar.py --modos C           # experimento complementario: solo el modo C
    uv run evaluacion/evaluar.py --modos A --paralelo 2

Cada pregunta de evaluacion/preguntas.csv se hace a Claude Code en modo no interactivo (claude -p), en una sesión
independiente (--no-session-persistence), con el mismo modelo y la misma instrucción en todos los modos:

    A  sin MCP ni skills: desde una carpeta temporal vacía fuera del repositorio, con --tools "" y
       --strict-mcp-config, de modo que no puede leer resultados ya calculados ni consultar el BCRP.
    B  con MCP y skills: desde tarea_8, con --mcp-config .mcp.json y --strict-mcp-config, y solo las
       herramientas mcp__bcrp, Skill, Read y Bash(uv run:*). Nota: Claude Code aprueba por su cuenta las órdenes
       de solo lectura de Bash (grep, cat, head, ls) dentro de la carpeta de trabajo, de modo que en la práctica
       el modo B también puede leer archivos con Bash, igual que con Read.
    C  con MCP y skills desde un estado limpio (experimento complementario): en una copia temporal del proyecto
       fuera del repositorio, con mcp/, .mcp.json, pyproject.toml, uv.lock, .python-version, las tres skills y los
       archivos de datos/, pero sin salidas/ ni la carpeta referencias/ de mapeando-enaho. Antes de cada pregunta
       se vacían salidas/, figuras/ y mapas/ de la copia, para que ninguna pregunta aproveche resultados de otra
       (figuras/ y mapas/ porque Read también lee imágenes). Mismas herramientas permitidas que el modo B. Solo
       se aplica a las preguntas que involucran la ENAHO (tipo enaho y combinada); las del BCRP no dependen de
       archivos locales. Sin referencias/, mapear.py termina con ERROR: la skill mapeando-enaho no puede
       completarse en este modo, pero limpiando-enaho produce las cifras departamentales en indicadores.csv.

La salida es stream-json (--verbose), de la que se toman las herramientas habilitadas (evento init), las que se
usaron efectivamente (bloques tool_use) y la respuesta estructurada (evento result). Escribe
evaluacion/resultados.csv (las filas de los modos que no se ejecutan se conservan tal cual) y guarda el registro
de cada llamada en evaluacion/registros/.

Criterio de corrección (fijado antes de ejecutar; ver la columna criterio de preguntas.csv):
    - Pregunta simple: acierta si |valor - esperado| <= tolerancia; si valor es null, «no sabe»; si no,
      «se equivoca».
    - Pregunta combinada: acierta si los dos valores están dentro de su tolerancia y la interpretación no afirma
      causalidad. Si algún valor queda fuera de su tolerancia o la interpretación afirma causalidad, «se equivoca».
      Si no ocurre nada de eso pero algún valor es null, «no sabe».
    - La interpretación afirma causalidad si contiene alguna expresión de CAUSAL que no esté negada (precedida,
      dentro de las cinco palabras anteriores de la misma oración, por «no», «sin», «ni» o «tampoco»).
"""
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent          # tarea_8/evaluacion
PROYECTO = AQUI.parent                          # tarea_8
REGISTROS = AQUI / "registros"
MODELO = "sonnet"
TIEMPO_MAX = 900

ESQUEMA = {
    "type": "object",
    "required": ["valor", "valor_2", "unidad", "fuente", "interpretacion"],
    "properties": {
        "valor": {"type": ["number", "null"]},
        "valor_2": {"type": ["number", "null"]},
        "unidad": {"type": "string"},
        "fuente": {"type": "string"},
        "interpretacion": {"type": "string"},
    },
}
INSTRUCCION = (
    "Responde la pregunta con cifras. En «valor» pon el número que pide la pregunta, en la unidad indicada. Si la "
    "pregunta pide dos cifras, pon la segunda en «valor_2»; si pide una sola, pon valor_2 null. Si no puedes saber "
    "una cifra con certeza, pon null en su lugar: no estimes. En «unidad» indica la unidad de cada cifra, en "
    "«fuente» di de dónde sale cada cifra (serie, archivo o publicación) y en «interpretacion» interpreta "
    "brevemente las cifras en una o dos oraciones.\n\nPregunta: "
)
HERRAMIENTAS_B = ["--tools", "Skill,Read,Bash", "--allowedTools", "mcp__bcrp,Skill,Read,Bash(uv run:*)"]
MODOS = {
    "A": {"cwd": None,  # carpeta temporal vacía, creada en cada llamada
          "args": ["--tools", "", "--strict-mcp-config"]},
    "B": {"cwd": PROYECTO,
          "args": ["--mcp-config", str(PROYECTO / ".mcp.json"), "--strict-mcp-config", *HERRAMIENTAS_B]},
    "C": {"cwd": "copia",  # copia limpia del proyecto, preparada por preparar_copia()
          "args": ["--mcp-config", "{copia}/.mcp.json", "--strict-mcp-config", *HERRAMIENTAS_B],
          "tipos": {"enaho", "combinada"}},
}
SKILLS = ["limpiando-enaho", "graficando-enaho", "mapeando-enaho"]
COPIA = {}   # "ruta" de la copia del modo C, una vez preparada


def preparar_copia():
    """Copia limpia del proyecto para el modo C, fuera del repositorio; sin salidas/ ni referencias/."""
    destino = Path(tempfile.mkdtemp(prefix="eval_modoC_"))
    basura = shutil.ignore_patterns("__pycache__", ".pytest_cache", "referencias")
    shutil.copytree(PROYECTO / "mcp", destino / "mcp", ignore=basura)
    for archivo in (".mcp.json", "pyproject.toml", "uv.lock", ".python-version"):
        shutil.copy2(PROYECTO / archivo, destino / archivo)
    for skill in SKILLS:
        shutil.copytree(PROYECTO / ".claude/skills" / skill, destino / ".claude/skills" / skill, ignore=basura)
    (destino / "datos").mkdir()
    for archivo in (PROYECTO / "datos").iterdir():       # solo los archivos de datos, no subcarpetas
        if archivo.is_file():
            shutil.copy2(archivo, destino / "datos" / archivo.name)
    # El entorno se instala antes de medir tiempos, para no cargarle la instalación a la primera pregunta.
    subprocess.run(["uv", "sync", "--quiet"], cwd=destino, check=True)
    inventario = sorted(p.relative_to(destino).as_posix() for p in destino.rglob("*")
                        if p.is_file() and ".venv" not in p.parts)
    REGISTROS.mkdir(exist_ok=True)
    (REGISTROS / "copia_modoC.txt").write_text(
        "Contenido de la copia limpia del modo C (sin .venv), al prepararla:\n" + "\n".join(inventario) + "\n",
        encoding="utf-8")
    COPIA["ruta"] = destino
    return destino


def vaciar_copia():
    for carpeta in ("salidas", "figuras", "mapas"):
        shutil.rmtree(COPIA["ruta"] / carpeta, ignore_errors=True)

# Expresiones que atribuyen un efecto (se buscan en minúsculas). Fijadas antes de ejecutar.
CAUSAL = re.compile(
    r"\b(caus\w*|provoc\w*|se debe a|se deb[ií]a a|debido a|a ra[ií]z de|gracias a|explic\w*|impuls\w*|"
    r"contribu\w*|atribu\w*|efecto de\w*|efectos de\w*|impacto de\w*|como resultado de|como consecuencia de|"
    r"llev[óo] a|permiti[óo] (reducir|disminuir|bajar)|origin\w*|determin\w*)\b")
NEGACION = re.compile(r"\b(no|sin|ni|tampoco)\b")


def afirma_causalidad(texto):
    """Devuelve la primera expresión causal no negada de la interpretación, o None."""
    for oracion in re.split(r"[.;:]", (texto or "").lower()):
        for m in CAUSAL.finditer(oracion):
            previas = oracion[:m.start()].split()[-5:]
            if not any(NEGACION.fullmatch(p.strip(",()«»\"")) for p in previas):
                return m.group(0)
    return None


def _herramienta(bloque):
    nombre, entrada = bloque.get("name", ""), bloque.get("input") or {}
    if nombre == "Skill":
        return f"Skill({entrada.get('skill', '')}{' ' + entrada['args'] if entrada.get('args') else ''})"
    if nombre == "Bash":
        cmd = re.sub(r"\s+", " ", entrada.get("command", ""))
        cmd = re.sub(r"\S*/\.claude/skills/[\w-]+/scripts/", "", cmd)   # acorta las rutas absolutas de las skills
        return f"Bash({cmd[:90]})"
    if nombre == "Read":
        return f"Read({Path(entrada.get('file_path', '')).name})"
    return nombre


def preguntar(fila, modo):
    cfg = MODOS[modo]
    cmd = [shutil.which("claude") or "claude", "-p", INSTRUCCION + fila.pregunta,
           "--output-format", "stream-json", "--verbose", "--json-schema", json.dumps(ESQUEMA),
           "--no-session-persistence", "--model", MODELO, *cfg["args"]]
    vacia = tempfile.TemporaryDirectory(prefix="eval_modoA_") if cfg["cwd"] is None else None
    cwd = vacia.name if vacia else cfg["cwd"]
    if cfg["cwd"] == "copia":
        vaciar_copia()
        cwd = COPIA["ruta"]
        cmd = [c.replace("{copia}", str(cwd)) for c in cmd]
    t = time.time()
    error = ""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=TIEMPO_MAX, cwd=cwd)
        salida, err = proc.stdout, proc.stderr
        if proc.returncode != 0:
            error = f"código de salida {proc.returncode}: {err.strip()[-200:]}"
    except subprocess.TimeoutExpired as e:
        salida, err = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), ""
        error = f"tiempo agotado ({TIEMPO_MAX} s)"
    segundos = round(time.time() - t, 1)
    if vacia:
        vacia.cleanup()

    REGISTROS.mkdir(exist_ok=True)
    (REGISTROS / f"{fila.id}_{modo}.jsonl").write_text(salida, encoding="utf-8")
    return {**leer_registro(salida, error), "segundos": segundos}


def leer_registro(salida, error=""):
    """Extrae de la salida stream-json las herramientas habilitadas, las usadas y la respuesta estructurada.

    Una herramienta cuenta como usada solo si su resultado no es un error; las llamadas denegadas por permisos o
    rechazadas (por ejemplo, una herramienta no habilitada) van a herramientas_fallidas.
    """
    habilitadas, llamadas, fallidas_ids, resultado = [], {}, set(), {}
    for linea in salida.splitlines():
        try:
            ev = json.loads(linea)
        except json.JSONDecodeError:
            continue
        contenido = (ev.get("message") or {}).get("content") if isinstance(ev.get("message"), dict) else None
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            mcp = [f"{s['name']} ({s.get('status')})" for s in ev.get("mcp_servers", [])]
            habilitadas = [h for h in ev.get("tools", []) if h != "StructuredOutput"] + [f"servidor {m}" for m in mcp]
        elif isinstance(contenido, list):
            for b in contenido:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use" and b.get("name") != "StructuredOutput":
                    llamadas[b["id"]] = _herramienta(b)
                elif b.get("type") == "tool_result" and b.get("is_error"):
                    fallidas_ids.add(b.get("tool_use_id"))
        if ev.get("type") == "result":
            resultado = ev
    usadas = [h for i, h in llamadas.items() if i not in fallidas_ids]
    fallidas = [h for i, h in llamadas.items() if i in fallidas_ids]
    r = resultado.get("structured_output") or {}
    if not resultado:
        error = error or "sin evento result"
    elif not r:
        error = error or f"sin respuesta estructurada: {str(resultado.get('result', ''))[:200]}"
    denegadas = [d.get("tool_name", "") for d in resultado.get("permission_denials", [])]
    if denegadas:
        error = (error + "; " if error else "") + "permisos denegados: " + ", ".join(denegadas)
    return {"valor": r.get("valor"), "valor_2": r.get("valor_2"), "unidad_respuesta": r.get("unidad", ""),
            "fuente": r.get("fuente", ""), "interpretacion": r.get("interpretacion", ""),
            "herramientas_usadas": "; ".join(usadas) if usadas else "ninguna",
            "n_herramientas": len(usadas), "herramientas_fallidas": "; ".join(fallidas),
            "herramientas_habilitadas": ", ".join(habilitadas) or "ninguna",
            "turnos": resultado.get("num_turns"), "error": error}


def _num(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) or x == "" else float(x)


def calificar(fila, r):
    esperados = [(_num(fila.valor_esperado), _num(fila.tolerancia), _num(r["valor"]))]
    if fila.tipo == "combinada":
        esperados.append((_num(fila.valor_esperado_2), _num(fila.tolerancia_2), _num(r["valor_2"])))
    fuera = [v is not None and abs(v - e) > tol for e, tol, v in esperados]
    nulos = [v is None for _, _, v in esperados]
    causal = afirma_causalidad(r["interpretacion"]) if fila.tipo == "combinada" else None
    if any(fuera) or causal:
        motivo = []
        if any(fuera):
            motivo.append("valor fuera de tolerancia" if sum(fuera) == 1 else "valores fuera de tolerancia")
        if causal:
            motivo.append(f"interpretación causal («{causal}»)")
        return "se equivoca", "; ".join(motivo)
    if any(nulos):
        return "no sabe", "sin respuesta (null)"
    return "acierta", ""


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--modos", nargs="+", default=["A", "B"], choices=list(MODOS))
    p.add_argument("--paralelo", type=int, default=4, help="llamadas simultáneas del modo A")
    p.add_argument("--recalificar", action="store_true",
                   help="no llama a claude: rehace resultados.csv desde evaluacion/registros/ con los tiempos ya medidos")
    a = p.parse_args()
    if not (PROYECTO / ".mcp.json").exists():
        raise SystemExit("Falta .mcp.json en tarea_8. Conecten el servidor: claude mcp add --scope project bcrp -- uv run mcp/server.py")

    preguntas = pd.read_csv(AQUI / "preguntas.csv", dtype={"id": str})
    casos = [(q, m) for q in preguntas.itertuples() for m in a.modos
             if q.tipo in MODOS[m].get("tipos", {q.tipo})]
    if a.recalificar:
        previos = pd.read_csv(AQUI / "resultados.csv").set_index(["id", "modo"]).segundos

        futuros = []
        for q, m in casos:
            f = Future()
            salida = (REGISTROS / f"{q.id}_{m}.jsonl").read_text(encoding="utf-8")
            f.set_result({**leer_registro(salida), "segundos": float(previos[(q.id, m)])})
            futuros.append(((q, m), f))
        print(f"Recalifico {len(futuros)} respuestas desde {REGISTROS.relative_to(PROYECTO).as_posix()}/", flush=True)
        ex_a = ex_b = None
    else:
        if "C" in a.modos:
            print(f"Copia limpia del modo C en {preparar_copia()}", flush=True)
        print(f"{len(casos)} llamadas a claude -p con {MODELO}...", flush=True)
        # Los modos B y C corren de a una llamada: las skills escriben en salidas/, figuras/ y mapas/, y dos
        # llamadas simultáneas podrían leer un archivo a medio escribir (en C, además, cada pregunta vacía la
        # copia). El modo A corre en paralelo, en carpetas aisladas.
        ex_a, ex_b = ThreadPoolExecutor(a.paralelo), ThreadPoolExecutor(1)
        futuros = [((q, m), (ex_a if m == "A" else ex_b).submit(preguntar, q, m)) for q, m in casos]
    filas = []
    for (q, m), f in futuros:
        r = f.result()
        resultado, motivo = calificar(q, r)
        if motivo and resultado != "acierta":
            r["error"] = "; ".join(x for x in (motivo, r["error"]) if x)
        filas.append({"id": q.id, "tipo": q.tipo, "modo": m, "pregunta": q.pregunta,
                      "valor_esperado": q.valor_esperado, "valor_esperado_2": q.valor_esperado_2,
                      "valor": r["valor"], "valor_2": r["valor_2"], "unidad": r["unidad_respuesta"],
                      "fuente": r["fuente"], "interpretacion": r["interpretacion"],
                      "herramientas_usadas": r["herramientas_usadas"], "n_herramientas": r["n_herramientas"],
                      "herramientas_fallidas": r["herramientas_fallidas"],
                      "resultado": resultado, "segundos": r["segundos"], "turnos": r["turnos"],
                      "error": r["error"], "herramientas_habilitadas": r["herramientas_habilitadas"]})
        print(f"  {q.id:<12} modo {m}  {resultado:<12} {r['segundos']:>6} s  {r['herramientas_usadas'][:80]}",
              flush=True)
    for ex in (ex_a, ex_b):
        if ex:
            ex.shutdown()
    if COPIA.get("ruta"):
        shutil.rmtree(COPIA["ruta"], ignore_errors=True)

    res = pd.DataFrame(filas)
    previo = AQUI / "resultados.csv"
    if previo.exists():
        # Fusión en el lugar: cada fila (id, modo) recalculada ocupa la posición que tenía en el archivo, las de
        # los modos que no se ejecutaron ahora se conservan tal cual y las filas nuevas van al final. Así el orden
        # original (A y B intercalados por pregunta y luego C) se mantiene, y --recalificar reproduce el archivo.
        anteriores = pd.read_csv(previo, dtype={"id": str})
        nuevas = {(f["id"], f["modo"]): f for f in res.to_dict("records")}
        claves_previas = list(zip(anteriores.id, anteriores.modo))
        filas_finales = [nuevas.pop(k) if k in nuevas else fila
                         for k, fila in zip(claves_previas, anteriores.to_dict("records"))]
        filas_finales += list(nuevas.values())
        res = pd.DataFrame(filas_finales, columns=anteriores.columns.union(res.columns, sort=False))
    res.to_csv(previo, index=False, encoding="utf-8")
    print("\n" + res.pivot(index="id", columns="modo", values="resultado").to_string())
    tabla = res.groupby("modo").resultado.value_counts().unstack(fill_value=0)
    tabla["segundos_promedio"] = res.groupby("modo").segundos.mean().round(1)
    print("\n" + tabla.to_string())
    print(f"\nGuardé {(AQUI / 'resultados.csv').relative_to(PROYECTO).as_posix()}")
