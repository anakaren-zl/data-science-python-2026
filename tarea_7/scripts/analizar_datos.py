"""Paso 3 · Analiza la permanencia escolar con enfoque interseccional en 2024, 2025 y ambos años, y prepara el dashboard.

    python scripts/analizar_datos.py

Lee datos/procesados/base_analitica.csv y guarda en datos/procesados/ las tablas del análisis y en web/data/ los
archivos del dashboard. El enfoque es intercategorial (McCall, 2005): sexo, área, lengua materna y pobreza se adoptan
provisionalmente y se cruzan en 16 posiciones sociales. Siguiendo a Hancock (2007) y Bowleg (2008), lo observado se
contrasta con lo que predice un modelo solo aditivo. El análisis se repite en 2024 para comprobar si los resultados
de 2025 se replican, y se estima también con ambos años juntos, lo que aumenta la precisión.

Indicador: % de residentes de 6 a 17 años que no asisten a la escuela y no han concluido la secundaria.
Todas las cifras están ponderadas con FACTORA07, el factor de expansión del módulo de Educación.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

RAIZ = Path(__file__).resolve().parents[1]
PROCESADOS = RAIZ / "datos" / "procesados"
WEB = RAIZ / "web" / "data"
GEOJSON = RAIZ / "datos" / "originales" / "peru_departamental_simple.geojson"

DEPARTAMENTOS = {"01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho",
                 "06": "Cajamarca", "07": "Callao", "08": "Cusco", "09": "Huancavelica", "10": "Huánuco",
                 "11": "Ica", "12": "Junín", "13": "La Libertad", "14": "Lambayeque", "15": "Lima",
                 "16": "Loreto", "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura",
                 "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes", "25": "Ucayali"}

# Cifras oficiales publicadas por el INEI para el contraste (ENAHO, tasa neta de asistencia a secundaria de 12 a 16 años)
OFICIALES = [
    ("Pobreza monetaria nacional", "2024", 27.6, "INEI (2026), Informe técnico de pobreza monetaria 2016-2025"),
    ("Pobreza monetaria nacional", "2025", 25.7, "INEI (2026), Informe técnico de pobreza monetaria 2016-2025"),
    ("Asistencia a secundaria, total", "2024", 86.6, "INEI (2025), Estadísticas con enfoque de género"),
    ("Asistencia a secundaria, mujeres", "2024", 86.9, "INEI (2025), Estadísticas con enfoque de género"),
    ("Asistencia a secundaria, hombres", "2024", 86.4, "INEI (2025), Estadísticas con enfoque de género"),
    ("Asistencia a secundaria, mujeres rurales", "2024", 85.9, "INEI (2025), Estadísticas con enfoque de género"),
    ("Asistencia a secundaria, hombres rurales", "2024", 84.1, "INEI (2025), Estadísticas con enfoque de género"),
    ("Asistencia a secundaria, total", "2025", 88.0, "INEI (2025), Condiciones de vida en el Perú, III trimestre"),
]
PERIODOS = ["2024", "2025", "2024-2025"]


def tasa(g, var="fuera"):
    """Tasa ponderada con intervalo al 95 % y coeficiente de variación (tamaño efectivo de Kish)."""
    p = np.average(g[var], weights=g.FACTORA07)
    n_ef = g.FACTORA07.sum() ** 2 / (g.FACTORA07 ** 2).sum()
    ee = np.sqrt(p * (1 - p) / n_ef)
    anios = g.anio.nunique()
    return pd.Series({"pct": 100 * p, "ic_inf": 100 * max(p - 1.96 * ee, 0), "ic_sup": 100 * (p + 1.96 * ee),
                      "cv": 100 * ee / p if p > 0 else np.nan, "casos": len(g),
                      # en el periodo acumulado, la población se expresa como promedio anual
                      "fuera_expandido": (g[var] * g.FACTORA07).sum() / anios, "poblacion": g.FACTORA07.sum() / anios})


def periodo(base, nombre):
    return base if nombre == "2024-2025" else base[base.anio == int(nombre)]


def analizar_periodo(base, nombre):
    """Todas las tablas de un periodo. Devuelve un diccionario de DataFrames y el resumen del modelo."""
    b = periodo(base, nombre)
    analisis = b[b.lengua != "Otra"].copy()   # 16 posiciones: lengua castellana o indígena
    for var, col, valor in [("mujer", "sexo", "Mujer"), ("rural", "area", "Rural"),
                            ("indigena", "lengua", "Indígena"), ("pobre", "pobreza", "Pobre")]:
        analisis[var] = (analisis[col] == valor).astype(int)
    t = {}
    t["por_sexo"] = b.groupby("sexo").apply(tasa, include_groups=False).reset_index()
    t["edad_sexo"] = b.groupby(["edad", "sexo"]).apply(tasa, include_groups=False).reset_index()

    # Brecha mujer menos hombre dentro de cada eje
    filas = []
    for eje in ["area", "lengua", "pobreza"]:
        for categoria, g in analisis.groupby(eje):
            m, h = tasa(g[g.mujer == 1]), tasa(g[g.mujer == 0])
            ee = np.sqrt(((m.ic_sup - m.pct) / 1.96) ** 2 + ((h.ic_sup - h.pct) / 1.96) ** 2)
            filas.append({"eje": eje, "categoria": categoria, "mujeres_pct": m.pct, "hombres_pct": h.pct,
                          "brecha_pp": m.pct - h.pct, "brecha_ic_inf": m.pct - h.pct - 1.96 * ee,
                          "brecha_ic_sup": m.pct - h.pct + 1.96 * ee,
                          "casos_mujeres": m.casos, "casos_hombres": h.casos})
    t["brechas_por_eje"] = pd.DataFrame(filas)

    # Las 16 posiciones sociales
    pos = analisis.groupby(["sexo", "area", "lengua", "pobreza"]).apply(tasa, include_groups=False).reset_index()
    pos["referencial"] = pos.cv > 15   # criterio del INEI: CV mayor a 15 % es referencial

    # ¿Aditivo o interseccional? Modelos logísticos ponderados, errores agrupados por conglomerado y año
    datos = analisis.assign(peso=analisis.FACTORA07 / analisis.FACTORA07.mean(),
                            a2025=(analisis.anio == 2025).astype(int),
                            grupo=analisis.anio.astype(str) + analisis.CONGLOME)
    control = " + a2025" if nombre == "2024-2025" else ""
    ajustar = lambda f: smf.glm(f + control, data=datos, family=sm.families.Binomial(), var_weights=datos.peso).fit(
        cov_type="cluster", cov_kwds={"groups": datos.grupo})
    aditivo = ajustar("fuera ~ mujer + rural + indigena + pobre")
    interaccion = ajustar("fuera ~ mujer * (rural + indigena + pobre) + rural:indigena + rural:pobre + indigena:pobre")
    terminos = [x for x in interaccion.params.index if x.startswith("mujer:")]
    wald = interaccion.wald_test(", ".join(f"{x} = 0" for x in terminos), scalar=True)

    claves = ["mujer", "rural", "indigena", "pobre"]
    pos[claves] = np.column_stack([pos.sexo == "Mujer", pos.area == "Rural", pos.lengua == "Indígena",
                                   pos.pobreza == "Pobre"]).astype(int)
    pred = pos[claves].assign(a2025=1 if nombre != "2024" else 0)
    pos["pred_aditivo"] = 100 * aditivo.predict(pred)
    pos["pred_interaccion"] = 100 * interaccion.predict(pred)
    t["posiciones"] = pos
    t["modelo_interacciones"] = pd.DataFrame({"coef": interaccion.params, "ee": interaccion.bse,
                                              "p": interaccion.pvalues,
                                              "odds_ratio": np.exp(interaccion.params)}).reset_index(names="termino")
    resumen = {"wald_chi2": float(wald.statistic), "wald_gl": len(terminos), "wald_p": float(wald.pvalue),
               "aic_aditivo": float(aditivo.aic), "aic_interaccion": float(interaccion.aic), "casos": int(len(datos))}
    for x in terminos:
        clave = x.replace("mujer:", "")
        resumen[f"or_mujer_{clave}"] = float(np.exp(interaccion.params[x]))
        resumen[f"p_mujer_{clave}"] = float(interaccion.pvalues[x])

    # Razones de inasistencia por sexo y diferencia mujeres menos varones con su intervalo al 95 %
    fuera = b[(b.fuera == 1) & b.razon.notna()]
    t["razones"] = ((fuera.groupby(["sexo", "razon"]).FACTORA07.sum() / fuera.groupby("sexo").FACTORA07.sum() * 100)
                    .rename("pct").reset_index().merge(fuera.groupby(["sexo", "razon"]).size().rename("casos").reset_index()))
    dif = []
    for razon in sorted(fuera.razon.unique()):
        val = {}
        for s in ["Mujer", "Hombre"]:
            g = fuera[fuera.sexo == s]
            p_ = np.average(g.razon == razon, weights=g.FACTORA07)
            val[s] = (p_, p_ * (1 - p_) / (g.FACTORA07.sum() ** 2 / (g.FACTORA07 ** 2).sum()))
        d, ee = val["Mujer"][0] - val["Hombre"][0], np.sqrt(val["Mujer"][1] + val["Hombre"][1])
        dif.append({"razon": razon, "mujeres_pct": 100 * val["Mujer"][0], "hombres_pct": 100 * val["Hombre"][0],
                    "diferencia_pp": 100 * d, "ic_inf": 100 * (d - 1.96 * ee), "ic_sup": 100 * (d + 1.96 * ee),
                    "significativa_95": bool(abs(d) > 1.96 * ee)})
    t["razones_diferencias"] = pd.DataFrame(dif)

    dep = b.groupby(["departamento", "sexo"]).apply(tasa, include_groups=False).reset_index()
    dep["nombre"] = dep.departamento.map(DEPARTAMENTOS)
    t["departamentos"] = dep
    for df in t.values():
        df.insert(0, "periodo", nombre)
    return t, resumen


def main():
    base = pd.read_csv(PROCESADOS / "base_analitica.csv", dtype={"departamento": str, "CONGLOME": str})
    tablas, modelos = {}, {}
    for nombre in PERIODOS:
        t, resumen = analizar_periodo(base, nombre)
        modelos[nombre] = resumen
        for k, df in t.items():
            tablas.setdefault(k, []).append(df)
    for k, partes in tablas.items():
        pd.concat(partes).round(4).to_csv(PROCESADOS / f"{k}.csv", index=False)
    (PROCESADOS / "modelo_resumen.json").write_text(json.dumps(modelos, indent=2), encoding="utf-8")

    # Contraste con las cifras oficiales publicadas por el INEI
    val = pd.read_csv(PROCESADOS / "validacion.csv")
    propias = {("Pobreza monetaria nacional", str(r.anio)): r.pobreza for r in val.itertuples()}
    propias.update({("Asistencia a secundaria, total", str(r.anio)): r.asistencia_secundaria for r in val.itertuples()})
    sec = base[base.edad.between(12, 16)]
    for (sexo, area), etiqueta in {("Mujer", None): "mujeres", ("Hombre", None): "hombres",
                                   ("Mujer", "Rural"): "mujeres rurales", ("Hombre", "Rural"): "hombres rurales"}.items():
        for anio, g in sec.groupby("anio"):
            g = g[(g.sexo == sexo) & ((g.area == area) if area else True)]
            propias[(f"Asistencia a secundaria, {etiqueta}", str(anio))] = 100 * np.average(g.asiste_secundaria, weights=g.FACTORA07)
    contraste = pd.DataFrame([{"indicador": i, "anio": a, "este_estudio": propias[(i, a)], "inei": o,
                               "diferencia_pp": propias[(i, a)] - o, "fuente_oficial": f} for i, a, o, f in OFICIALES])
    contraste.round(2).to_csv(PROCESADOS / "contraste_oficial.csv", index=False)

    # Datos del dashboard
    WEB.mkdir(parents=True, exist_ok=True)
    micro = base[["anio", "sexo", "edad", "area", "lengua", "pobreza", "departamento", "fuera", "razon", "FACTORA07"]]
    columnas = {c: micro[c].tolist() for c in micro.columns}
    columnas["FACTORA07"] = micro.FACTORA07.round(3).tolist()
    columnas["razon"] = micro.razon.fillna("").tolist()
    paquete = {
        "micro": columnas,
        # NaN no es JSON válido: las posiciones sin casos guardan sus valores vacíos
        "posiciones": [{k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in fila.items()}
                       for fila in pd.concat(tablas["posiciones"]).round(3).to_dict(orient="records")],
        "modelos": modelos,
        "contraste": contraste.round(2).to_dict(orient="records"),
        "departamentos": DEPARTAMENTOS,
        "validacion": (PROCESADOS / "validacion.txt").read_text(encoding="utf-8"),
    }
    (WEB / "datos.json").write_text(json.dumps(paquete, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
                                   encoding="utf-8")
    geo = json.loads(GEOJSON.read_text(encoding="utf-8"))
    for f in geo["features"]:
        codigo = str(f["properties"]["FIRST_IDDP"]).zfill(2)
        f["properties"] = {"codigo": codigo, "nombre": DEPARTAMENTOS[codigo]}
    assert len(geo["features"]) == 25, "El GeoJSON debe tener 25 departamentos"
    (WEB / "departamentos.geojson").write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # Resumen en pantalla
    ps = pd.concat(tablas["por_sexo"])
    print(ps[["periodo", "sexo", "pct", "ic_inf", "ic_sup", "fuera_expandido"]].round(2).to_string(index=False), "\n")
    br = pd.concat(tablas["brechas_por_eje"])
    print(br[["periodo", "categoria", "mujeres_pct", "hombres_pct", "brecha_pp"]].round(2).to_string(index=False), "\n")
    rd = pd.concat(tablas["razones_diferencias"])
    print(rd[rd.significativa_95].round(1).to_string(index=False), "\n")
    print(contraste.round(2).to_string(index=False), "\n")
    print(json.dumps(modelos, indent=1))


if __name__ == "__main__":
    main()
