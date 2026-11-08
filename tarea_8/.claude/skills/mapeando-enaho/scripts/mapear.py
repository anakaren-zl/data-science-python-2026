"""Mapa coroplético de la pobreza monetaria por departamento con la ENAHO (INEI), ponderada con facpob07.

    uv run .claude/skills/mapeando-enaho/scripts/mapear.py      # desde tarea_8/

Lee salidas/personas_<anio>.parquet (la arma la skill limpiando-enaho) y datos/peru_departamental_simple.geojson.
Une por código, departamento (ubigeo[:2]) con FIRST_IDDP como texto de dos dígitos, nunca por nombre. Exige 25
departamentos con dato, compara cada cifra con referencias/pobreza_departamento_2024.csv y guarda
salidas/comparacion_mapa.csv y mapas/pobreza_departamento.png. Reutiliza el estilo de graficando-enaho.
"""
import argparse
import math
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, ListedColormap
from matplotlib.patches import Rectangle
from shapely.geometry import box

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1] / "graficando-enaho" / "scripts"))
import estilo as e  # noqa: E402

GEOJSON = Path("datos") / "peru_departamental_simple.geojson"
REFERENCIA = AQUI.parent / "referencias" / "pobreza_departamento_2024.csv"
LIMA, CALLAO = "15", "07"
PASO = 10                        # tramos de 10 puntos desde 0
TOLERANCIA_AVISO = 0.5           # pp: diferencias mayores se marcan como AVISO en la comparación


def cargar_geo():
    if not GEOJSON.exists():
        sys.exit(f"ERROR: no encuentro {GEOJSON.as_posix()}. Bájenlo de la Sesión 06 del curso y pónganlo en datos/.")
    geo = gpd.read_file(GEOJSON)
    geo["FIRST_IDDP"] = geo["FIRST_IDDP"].astype(str).str.strip().str.zfill(2)
    return geo


def pobreza_departamental(base):
    t = e.pobreza_ponderada(base, ["departamento", "departamento_nombre"]).reset_index()
    t["departamento"] = t.departamento.astype(str).str.zfill(2)
    return t


def unir(geo, t):
    """Une por código como texto; se detiene si no quedan 25 departamentos, todos con dato."""
    m = geo.merge(t, left_on="FIRST_IDDP", right_on="departamento", how="left", validate="1:1")
    sin_dato = m.loc[m.pct.isna(), "FIRST_IDDP"].tolist()
    if len(m) != 25 or sin_dato or m.FIRST_IDDP.nunique() != 25:
        sys.exit(f"ERROR: el mapa necesita 25 departamentos con dato y hay {len(m)} unidades; sin dato: {sin_dato}. "
                 "Revisen que la unión sea ubigeo[:2] con FIRST_IDDP, ambos como texto de dos dígitos.")
    return m


def pobreza_sumaria(base):
    """La misma pobreza con el método del INEI (un registro por hogar, factor07 × mieperho), solo para comparar."""
    h = base.drop_duplicates(["conglome", "vivienda", "hogar"])
    w = h.factor07 * h.mieperho
    g = h.assign(_wp=h.pobre * w, _w=w).groupby("departamento")
    return (g._wp.sum() / g._w.sum() * 100).rename("pct_sumaria")


def comparar(t, salida, sumaria):
    """Compara cada departamento con la referencia del curso y guarda salidas/comparacion_mapa.csv."""
    if not REFERENCIA.exists():
        sys.exit(f"ERROR: falta {REFERENCIA}. Bájenlo de la Sesión 16 del curso.")
    ref = pd.read_csv(REFERENCIA, dtype={"ccdd": str})
    ref["ccdd"] = ref.ccdd.str.zfill(2)
    c = t.merge(ref, left_on="departamento", right_on="ccdd", how="outer", validate="1:1", indicator=True)
    if (c._merge != "both").any():
        sys.exit(f"ERROR: los códigos no coinciden con la referencia: {c.loc[c._merge != 'both', ['departamento', 'ccdd']]}")
    c = pd.DataFrame({
        "ccdd": c.ccdd, "departamento": c.departamento_nombre,
        "pobreza_calculada": c.pct.round(2), "pobreza_calculada_1d": c.pct.round(1),
        "pobreza_referencia": c.pobreza_pct, "diferencia_pp": (c.pct.round(1) - c.pobreza_pct).round(1),
        "pobreza_sumaria_1d": c.ccdd.map(sumaria).round(1),
        "n_muestra": c.n,
    })
    c["diferencia_sumaria_pp"] = (c.pobreza_sumaria_1d - c.pobreza_referencia).round(1) + 0.0   # sin -0.0
    c["diferencia_pp"] = c.diferencia_pp + 0.0
    c["estado"] = np.where(c.diferencia_pp.abs() <= TOLERANCIA_AVISO, "OK", "AVISO")
    c = c.sort_values("ccdd").reset_index(drop=True)
    salida.parent.mkdir(exist_ok=True)
    c.to_csv(salida, index=False, encoding="utf-8")
    exactas = int((c.diferencia_pp == 0).sum())
    print(f"Guardé {salida.as_posix()}: con personas y facpob07, {exactas} de 25 coinciden al decimal con la "
          f"referencia (diferencia máxima {c.diferencia_pp.abs().max():.1f} pp; "
          f"{int((c.estado == 'AVISO').sum())} con AVISO > {TOLERANCIA_AVISO} pp). Con el método de la sumaria, "
          f"{int((c.diferencia_sumaria_pp == 0).sum())} de 25 coinciden.")
    return c


# --- Dibujo ----------------------------------------------------------------------------------------------------
def escala(vmax):
    limites = list(range(0, int(math.ceil(vmax / PASO) * PASO) + 1, PASO))
    base = LinearSegmentedColormap.from_list("azules", [e.AZUL_CLARO, "#9DBBE0", e.AZUL, e.AZUL_MARINO])
    k = len(limites) - 1
    colores = [base(i / (k - 1)) for i in range(k)] if k > 1 else [base(1.0)]
    return limites, ListedColormap(colores), BoundaryNorm(limites, k)


def _texto_sobre(color):
    r, g, b = color[:3]
    return e.BLANCO if (0.299 * r + 0.587 * g + 0.114 * b) < 0.55 else e.AZUL_MARINO


def dibujar(m, nacional, anio, per, ruta):
    limites, cmap, norm = escala(m.pct.max())
    m = m.to_crs(32718)          # UTM 18S: proporciones reales del Perú
    orden = m.sort_values("pct", ascending=False)
    top, bajo = orden.head(5), orden.tail(5).iloc[::-1]

    fig = plt.figure(figsize=(14, 9))
    W, H = fig.get_size_inches()
    titulo = f"{top.departamento_nombre.iloc[0]} encabeza la pobreza monetaria y {bajo.departamento_nombre.iloc[0]} registra la menor"
    subtitulo = f"Perú, {per} · Por departamento · {e.UNIDAD} · Promedio nacional: {e.pct_txt(nacional)}"
    y_fin = e.encabezado(fig, titulo, subtitulo, margen_x=0.6, margen_sup=0.5)

    # Mapa a la izquierda
    alto_mapa = y_fin - 0.3 / H - 1.35 / H
    ax = fig.add_axes([0.6 / W, 1.35 / H, 6.2 / W, alto_mapa])
    ax.set_anchor("C")
    m.plot(column="pct", cmap=cmap, norm=norm, edgecolor=e.BLANCO, linewidth=0.6, ax=ax)
    ax.set_axis_off()
    ax.set_aspect("equal")

    # Recuadro en el mapa que señala la zona ampliada
    lc = m[m.FIRST_IDDP.isin([LIMA, CALLAO])]
    x0, ancho_panel, alto_ins = 7.6, W - 7.6 - 0.6, 3.1          # pulgadas del panel derecho
    c = m.loc[m.FIRST_IDDP == CALLAO].geometry.iloc[0].centroid
    alto_zona = 74_000                                          # metros; el ancho sigue la proporción del panel
    ancho_zona = alto_zona * ancho_panel / alto_ins
    zx, zy = c.x + ancho_zona * 0.22, c.y - alto_zona * 0.04     # centrado algo tierra adentro, donde está Lima
    zona = (zx - ancho_zona / 2, zy - alto_zona / 2, zx + ancho_zona / 2, zy + alto_zona / 2)
    ax.add_patch(Rectangle((zona[0], zona[1]), zona[2] - zona[0], zona[3] - zona[1], fill=False,
                           edgecolor=e.AZUL_MARINO, linewidth=1.0, zorder=5))

    # Leyenda horizontal debajo del mapa
    cax = fig.add_axes([1.7 / W, 0.85 / H, 4.0 / W, 0.16 / H])          # centrada bajo el mapa
    for i in range(len(limites) - 1):
        cax.add_patch(Rectangle((limites[i], 0), PASO, 1, facecolor=cmap(i), edgecolor=e.BLANCO, linewidth=1.2))
    cax.set_xlim(limites[0], limites[-1])
    cax.set_ylim(0, 1)
    cax.set_yticks([])
    cax.set_xticks(limites, [f"{v}" for v in limites])
    for s in cax.spines.values():
        s.set_visible(False)
    cax.tick_params(length=0, pad=4)
    for t in cax.get_xticklabels():
        t.set_fontproperties(e.fuente("regular", 9.5))
    cax.text(0, 1.75, e.UNIDAD[0].upper() + e.UNIDAD[1:], transform=cax.transAxes, ha="left", va="bottom",
             fontproperties=e.fuente("medium", 10), color=e.TEXTO)

    # Panel derecho: ampliación de Lima y Callao
    fig.text(x0 / W, y_fin - 0.35 / H, "Lima y Callao, ampliados", fontproperties=e.fuente("bold", 12),
             color=e.AZUL_MARINO, ha="left", va="top")
    y_ins = y_fin * H - 0.35 - 0.38 - alto_ins
    ins = fig.add_axes([x0 / W, y_ins / H, ancho_panel / W, alto_ins / H])
    ins.set_facecolor("#F7FAFD")                                # el mar, apenas distinto del fondo
    m.plot(column="pct", cmap=cmap, norm=norm, edgecolor=e.BLANCO, linewidth=1.2, ax=ins)
    ins.set_xlim(zona[0], zona[2])
    ins.set_ylim(zona[1], zona[3])
    ins.set_aspect("equal")
    ins.set_xticks([])
    ins.set_yticks([])
    ins.set_xlabel("")
    ins.set_ylabel("")
    for s in ins.spines.values():
        s.set_edgecolor("#C9D3DF")
        s.set_linewidth(0.8)

    caja = dict(boxstyle="round,pad=0.45", facecolor=e.BLANCO, edgecolor="#C9D3DF", linewidth=0.6)
    for codigo, (fx, fy, ha) in {CALLAO: (0.05, 0.83, "left"), LIMA: (0.95, 0.20, "right")}.items():
        fila = lc[lc.FIRST_IDDP == codigo].iloc[0]
        # el punto de cada departamento se toma dentro de la zona ampliada (Lima es mucho más grande que ella)
        punto = fila.geometry.intersection(box(*zona)).representative_point()
        ins.annotate(f"{fila.departamento_nombre}\n{e.pct_txt(fila.pct)}", xy=(punto.x, punto.y),
                     xytext=(fx, fy), textcoords="axes fraction", ha=ha, va="center",
                     fontproperties=e.fuente("bold", 11), color=e.AZUL_MARINO, linespacing=1.25,
                     bbox=caja,
                     arrowprops=dict(arrowstyle="-", color=e.AZUL_MARINO, linewidth=0.8, shrinkA=4, shrinkB=2))

    # Panel derecho: listas de mayor y menor pobreza
    y_listas = y_ins - 0.62
    col_w = ancho_panel / 2
    for j, (rotulo, filas) in enumerate([("Mayor pobreza", top), ("Menor pobreza", bajo)]):
        xc = x0 + j * (col_w + 0.0)
        fig.text(xc / W, y_listas / H, rotulo, fontproperties=e.fuente("bold", 11), color=e.AZUL_MARINO,
                 ha="left", va="top")
        for i, (_, f) in enumerate(filas.iterrows()):
            yi = y_listas - 0.46 - i * 0.34
            color = cmap(norm(f.pct))
            fig.patches.append(Rectangle((xc / W, (yi - 0.075) / H), 0.15 / W, 0.15 / H, transform=fig.transFigure,
                                         facecolor=color, edgecolor="#C9D3DF" if f.pct < 10 else color,
                                         linewidth=0.6))
            fig.text((xc + 0.27) / W, yi / H, f.departamento_nombre, fontproperties=e.fuente("regular", 10),
                     color=e.TEXTO, ha="left", va="center")
            fig.text((xc + col_w - 0.3) / W, yi / H, e.pct_txt(f.pct), fontproperties=e.fuente("semibold", 10),
                     color=e.TEXTO, ha="right", va="center")

    e.pie(fig, anio)
    e.guardar(fig, ruta)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anio", type=int, default=2024)
    anio = ap.parse_args().anio
    e.configurar()
    base = e.cargar_base(anio)
    geo = cargar_geo()
    t = pobreza_departamental(base)
    m = unir(geo, t)
    comparar(t, e.BASE / "comparacion_mapa.csv", pobreza_sumaria(base))
    dibujar(m, e.promedio_nacional(base), anio, e.periodo(base), e.MAPAS / "pobreza_departamento.png")


if __name__ == "__main__":
    main()
