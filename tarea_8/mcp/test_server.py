"""El contrato del servidor: si estas pruebas pasan, Claude Code y evaluar.py pueden usarlo.

    uv run pytest -q

Llaman al servidor en memoria, igual que lo haría Claude Code, y piden datos reales al BCRP.
"""
import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from server import mcp


async def _con_cliente(f):
    async with Client(mcp) as c:
        return await f(c)


def llamar(herramienta, **args):
    return asyncio.run(_con_cliente(lambda c: c.call_tool(herramienta, args))).data


def test_buscar_encuentra_el_ipc():
    r = llamar("buscar_series", texto="ipc 12 meses", limite=5)
    assert "PN01273PM" in [x["codigo"] for x in r]
    assert {"codigo", "nombre", "frecuencia"} <= r[0].keys()


def test_cuatro_herramientas_como_minimo():
    nombres = {t.name for t in asyncio.run(_con_cliente(lambda c: c.list_tools()))}
    assert {"buscar_series", "serie", "resumen"} <= nombres
    assert len(nombres) >= 4, "falta su herramienta propia"


def test_serie_mensual():
    r = llamar("serie", codigo="PN01271PM", desde="2025-01", hasta="2025-12")
    assert len(r["datos"]) == 12
    assert r["datos"][0]["periodo"] == "2025-01"
    assert r["datos"][2]["valor"] == pytest.approx(0.81, abs=0.01)   # IPC de Lima, marzo de 2025
    assert r["fuente"].startswith("https://estadisticas.bcrp.gob.pe")


def test_serie_diaria():
    r = llamar("serie", codigo="PD04638PD", desde="2026-10-01", hasta="2026-10-15")
    assert r["datos"][0]["periodo"] == "2026-10-01"
    assert r["datos"][-1] == {"periodo": "2026-10-15", "valor": pytest.approx(3.428, abs=0.001)}


def test_resumen_sin_cuentas_a_mano():
    r = llamar("resumen", codigo="PN01273PM", desde="2025-12", hasta="2026-09")
    assert r["primero"]["valor"] == pytest.approx(1.51, abs=0.01)
    assert r["ultimo"]["valor"] == pytest.approx(4.55, abs=0.01)
    assert r["maximo"]["periodo"] == "2026-09"
    assert {"cambio", "variacion_pct", "promedio", "minimo"} <= r.keys()


def test_codigo_inexistente_da_un_error_claro():
    with pytest.raises(ToolError, match="XX999"):
        llamar("serie", codigo="XX999", desde="2025-01", hasta="2025-02")


def test_un_recurso():
    async def contar(c):
        return len(await c.list_resources()) + len(await c.list_resource_templates())
    assert asyncio.run(_con_cliente(contar)) >= 1


def test_un_prompt():
    assert len(asyncio.run(_con_cliente(lambda c: c.list_prompts()))) >= 1


# --- Pruebas propias: comparar_series ---------------------------------------------------------------------------

def test_comparar_series_misma_frecuencia():
    r = llamar("comparar_series", codigo_a="PN01273PM", codigo_b="PN01271PM", desde="2025-01", hasta="2025-12")
    assert r["frecuencia_comun"] == "Mensual"
    assert r["agregacion"] is None
    assert r["n_comunes"] == 12
    assert [d["periodo"] for d in r["datos"]] == [f"2025-{m:02d}" for m in range(1, 13)]
    assert r["sin_dato"] == {"a": [], "b": []}
    assert r["correlacion"] is not None and -1 <= r["correlacion"] <= 1
    assert r["series"]["a"]["codigo"] == "PN01273PM" and r["series"]["b"]["codigo"] == "PN01271PM"
    assert all(s["fuente"].startswith("https://estadisticas.bcrp.gob.pe") for s in r["series"].values())
    # comparar una serie consigo misma no tiene sentido: error claro, aunque el código venga en minúsculas
    with pytest.raises(ToolError, match="misma serie.*PN01273PM"):
        llamar("comparar_series", codigo_a="PN01273PM", codigo_b=" pn01273pm", desde="2025-01", hasta="2025-12")


def test_comparar_series_agrega_la_diaria_a_mensual():
    r = llamar("comparar_series", codigo_a="PD04638PD", codigo_b="PN01273PM", desde="2026-01", hasta="2026-09")
    assert r["frecuencia_comun"] == "Mensual"
    assert r["n_comunes"] == 9
    assert [d["periodo"] for d in r["datos"]] == [f"2026-{m:02d}" for m in range(1, 10)]
    assert r["agregacion"] and "PD04638PD" in r["agregacion"][0]
    assert r["series"]["a"]["frecuencia"] == "Diaria" and r["series"]["a"]["resumen"]["n"] == 9
    # el valor mensual del tipo de cambio es el promedio de sus días, calculado aquí por separado
    dias = llamar("serie", codigo="PD04638PD", desde="2026-01", hasta="2026-01")["datos"]
    assert r["datos"][0]["valor_a"] == pytest.approx(sum(d["valor"] for d in dias) / len(dias), abs=1e-6)
