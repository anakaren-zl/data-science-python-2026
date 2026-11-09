"""Limpia la ENAHO del INEI: une personas (módulo 02) con hogares (sumaria, módulo 34) y valida la pobreza.

    uv run .claude/skills/limpiando-enaho/scripts/limpiar.py --anio 2024     # desde tarea_8/

Lee los zip de datos/, filtra a los residentes habituales, construye las variables de análisis y escribe:
    salidas/validacion.txt          cada verificación como [OK], [FALLA] o [AVISO], con valor y referencia
    salidas/personas_<anio>.parquet una fila por residente habitual, con facpob07
    salidas/indicadores.csv         pobreza y pobreza extrema ponderadas, con la columna metodo:
                                    sumaria (factor07 × mieperho) para nacional, área, dominio y departamento;
                                    personas (facpob07) para sexo, grupo de edad y sexo dentro de cada área

Si una verificación esencial falla, escribe validacion.txt y se detiene con un error: no fuerza resultados.
"""
import argparse
import sys
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

# Código del portal de microdatos del INEI y cifras oficiales de referencia, por año
ENCUESTAS = {
    2024: {
        "codigo": "966",
        "residentes": 108_664,
        "pobreza": 27.6,                 # nacional, % de personas
        "pobreza_extrema": 5.5,
        "urbana": 24.8, "rural": 39.3, "lima_metropolitana": 28.2,
    },
}
TOLERANCIA = 0.1                          # puntos porcentuales

LLAVES_HOGAR = ["conglome", "vivienda", "hogar"]
LLAVES_PERSONA = LLAVES_HOGAR + ["codperso"]
ANCHO_LLAVE = {"conglome": 6, "vivienda": 3, "hogar": 2, "codperso": 2, "ubigeo": 6}

DEPARTAMENTOS = {
    "01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho",
    "06": "Cajamarca", "07": "Callao", "08": "Cusco", "09": "Huancavelica", "10": "Huánuco",
    "11": "Ica", "12": "Junín", "13": "La Libertad", "14": "Lambayeque", "15": "Lima",
    "16": "Loreto", "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura",
    "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes", "25": "Ucayali",
}
DOMINIOS = {1: "Costa Norte", 2: "Costa Centro", 3: "Costa Sur", 4: "Sierra Norte", 5: "Sierra Centro",
            6: "Sierra Sur", 7: "Selva", 8: "Lima Metropolitana"}
METODO_HOGAR = "sumaria: factor07 x mieperho"      # método oficial del INEI, para indicadores de nivel hogar
METODO_PERSONA = "personas: facpob07"              # para atributos individuales (sexo, edad)
GRUPOS_EDAD = [(0, 14, "0 a 14 años"), (15, 29, "15 a 29 años"), (30, 44, "30 a 44 años"),
               (45, 64, "45 a 64 años"), (65, 200, "65 años a más")]

VARS_HOGAR = LLAVES_HOGAR + ["ano", "mes", "ubigeo", "dominio", "estrato", "pobreza", "factor07", "mieperho"]
VARS_PERSONA = LLAVES_PERSONA + ["p204", "p205", "p206", "p207", "p208a", "facpob07"]


# --- Lectura ---------------------------------------------------------------------------------------------------
def _normalizar(nombre):
    """'aÑo' -> 'ano', 'P208A' -> 'p208a': minúsculas y sin tildes ni eñes."""
    s = unicodedata.normalize("NFD", str(nombre).strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def leer_dta(zip_path, nombre):
    """Lee un .dta dentro del zip, con códigos numéricos (sin etiquetas) y llaves como texto con sus ceros."""
    if not zip_path.exists():
        sys.exit(f"ERROR: no encuentro {zip_path}. Bájenlo del portal de microdatos del INEI y pónganlo en datos/.")
    with zipfile.ZipFile(zip_path) as zf:
        miembros = [m for m in zf.namelist() if Path(m).name.lower() == nombre.lower()]
        if not miembros:
            sys.exit(f"ERROR: {zip_path.name} no contiene {nombre}.")
        with zf.open(miembros[0]) as f:
            df = pd.read_stata(f, convert_categoricals=False)
    df.columns = [_normalizar(c) for c in df.columns]
    for llave, ancho in ANCHO_LLAVE.items():
        if llave in df.columns:
            col = df[llave]
            if pd.api.types.is_numeric_dtype(col):          # por si algún año llega como número
                col = col.astype("Int64").astype(str)
            df[llave] = col.astype(str).str.strip().str.zfill(ancho)
    return df, miembros[0]


# --- Utilidades ------------------------------------------------------------------------------------------------
def pct(x, w):
    """Porcentaje ponderado de una variable 0/1."""
    return float((x * w).sum() / w.sum() * 100)


class Registro:
    """Acumula las verificaciones; las esenciales que fallan detienen el script al final."""

    def __init__(self):
        self.lineas, self.fallas = [], []

    def check(self, nombre, ok, obtenido, referencia, esencial=True):
        estado = "OK" if ok else ("FALLA" if esencial else "AVISO")
        self.lineas.append(f"[{estado}] {nombre}: {obtenido} (referencia: {referencia})")
        if not ok and esencial:
            self.fallas.append(nombre)
        return ok

    def seccion(self, titulo):
        self.lineas += ["", titulo, "-" * len(titulo)]


def cerca(valor, ref):
    return abs(valor - ref) <= TOLERANCIA + 1e-9


# --- Pipeline --------------------------------------------------------------------------------------------------
def main():
    sys.stdout.reconfigure(encoding="utf-8")        # tildes legibles también en la consola de Windows
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anio", type=int, default=2024)
    anio = ap.parse_args().anio
    if anio not in ENCUESTAS:
        sys.exit(f"ERROR: no hay código INEI ni cifras de referencia para {anio}. Años disponibles: {list(ENCUESTAS)}.")
    ref = ENCUESTAS[anio]
    datos, salidas = Path("datos"), Path("salidas")
    if not datos.is_dir():
        sys.exit("ERROR: no hay carpeta datos/. Corran el script desde tarea_8/.")
    salidas.mkdir(exist_ok=True)

    # 1. Leer
    hog, f_hog = leer_dta(datos / f"{ref['codigo']}-Modulo34.zip", f"sumaria-{anio}.dta")
    per, f_per = leer_dta(datos / f"{ref['codigo']}-Modulo02.zip", f"enaho01-{anio}-200.dta")
    faltan = [v for v in VARS_HOGAR if v not in hog] + [v for v in VARS_PERSONA if v not in per]
    if faltan:
        sys.exit(f"ERROR: faltan variables en los módulos: {faltan}")
    hog, per = hog[VARS_HOGAR].copy(), per[VARS_PERSONA].copy()

    r = Registro()
    r.seccion("Verificaciones esenciales")

    # 2. Llaves únicas
    dup_h = int(hog.duplicated(LLAVES_HOGAR).sum())
    dup_p = int(per.duplicated(LLAVES_PERSONA).sum())
    r.check("Llaves únicas en la sumaria (conglome, vivienda, hogar)", dup_h == 0,
            f"{dup_h} duplicados en {len(hog):,} hogares", "0 duplicados")
    r.check("Llaves únicas en el módulo 02 (conglome, vivienda, hogar, codperso)", dup_p == 0,
            f"{dup_p} duplicados en {len(per):,} personas", "0 duplicados")

    # 3. Residentes habituales
    filas_02 = len(per)
    residente = ((per.p204 == 1) & (per.p205 == 2)) | ((per.p204 == 2) & (per.p206 == 1))
    per = per[residente].copy()
    r.check("Residentes habituales", len(per) == ref["residentes"],
            f"{len(per):,} de {filas_02:,} filas del módulo 02", f"{ref['residentes']:,}")

    # 4. Unir personas con hogares
    base = per.merge(hog, on=LLAVES_HOGAR, how="left", validate="m:1", indicator=True)
    sin_hogar = int((base._merge != "both").sum())
    r.check("Unión personas-hogares sin pérdidas ni duplicados (validate='m:1')",
            sin_hogar == 0 and len(base) == len(per),
            f"{len(base):,} filas tras unir {len(per):,} personas; {sin_hogar} sin hogar", f"{len(per):,} y 0")
    base = base.drop(columns="_merge")

    # 5. Construir variables
    base["departamento"] = base.ubigeo.str[:2]
    base["departamento_nombre"] = base.departamento.map(DEPARTAMENTOS)
    base["area"] = base.estrato.le(5).map({True: "Urbana", False: "Rural"})
    base["pobre"] = base.pobreza.le(2).astype("int8")
    base["pobre_extremo"] = base.pobreza.eq(1).astype("int8")
    base["sexo"] = base.p207.map({1: "Hombre", 2: "Mujer"})
    edad = base.p208a
    base["grupo_edad"] = pd.Series(pd.NA, index=base.index, dtype="string")
    for lo, hi, etiqueta in GRUPOS_EDAD:
        base.loc[edad.between(lo, hi), "grupo_edad"] = etiqueta
    base["grupo_edad"] = pd.Categorical(base.grupo_edad, [g[2] for g in GRUPOS_EDAD], ordered=True)

    codigos = sorted(base.departamento.unique())
    r.check("Códigos departamentales (ubigeo[:2])",
            len(codigos) == 25 and set(codigos) == set(DEPARTAMENTOS),
            f"{len(codigos)} códigos ({codigos[0]} a {codigos[-1]})", "25 (01 a 25)")

    fp_ok = base.facpob07.notna().all() and (base.facpob07 > 0).all()
    f7_ok = hog.factor07.notna().all() and (hog.factor07 > 0).all()
    r.check("Factores de expansión presentes y positivos",
            bool(fp_ok and f7_ok),
            f"facpob07: {int(base.facpob07.isna().sum())} vacíos, mínimo {base.facpob07.min():.2f}; "
            f"factor07: {int(hog.factor07.isna().sum())} vacíos, mínimo {hog.factor07.min():.2f}",
            "0 vacíos y mínimo > 0")

    w = base.facpob07.astype(float)
    wh = (hog.factor07 * hog.mieperho).astype(float)
    pobre_h = hog.pobreza.le(2).astype(int)
    pob_per = pct(base.pobre, w)
    pob_hog = pct(pobre_h, wh)
    r.check("Pobreza nacional con personas y facpob07", cerca(pob_per, ref["pobreza"]),
            f"{pob_per:.2f} %", f"{ref['pobreza']} % ± {TOLERANCIA} pp")
    r.check("Pobreza nacional con la sumaria y factor07 × mieperho", cerca(pob_hog, ref["pobreza"]),
            f"{pob_hog:.2f} %", f"{ref['pobreza']} % ± {TOLERANCIA} pp")

    # 6. Variables de hogar para el método oficial (sumaria, factor07 × mieperho)
    hog["departamento"] = hog.ubigeo.str[:2]
    hog["departamento_nombre"] = hog.departamento.map(DEPARTAMENTOS)
    hog["area"] = hog.estrato.le(5).map({True: "Urbana", False: "Rural"})
    hog["dominio_nombre"] = hog.dominio.map(DOMINIOS)
    hog["pobre"] = hog.pobreza.le(2).astype("int8")
    hog["pobre_extremo"] = hog.pobreza.eq(1).astype("int8")
    hog["peso_hogar"] = (hog.factor07 * hog.mieperho).astype(float)
    base["dominio_nombre"] = base.dominio.map(DOMINIOS)
    base["peso_hogar"] = (base.factor07 * base.mieperho).astype(float)
    # una fila por hogar marcada para el método de la sumaria: el residente con el menor codperso
    base = base.sort_values(LLAVES_PERSONA).reset_index(drop=True)
    base["hogar_rep"] = (~base.duplicated(LLAVES_HOGAR)).astype("int8")
    w = base.facpob07.astype(float)

    # 7. Verificaciones referenciales: no detienen el script
    r.seccion("Verificaciones referenciales (no detienen el script)")
    wh = hog.peso_hogar
    referenciales = [
        ("Pobreza extrema nacional", hog.pobre_extremo, None, base.pobre_extremo, None, ref["pobreza_extrema"]),
        ("Pobreza urbana (estrato <= 5)", hog.pobre, hog.area.eq("Urbana"), base.pobre, base.area.eq("Urbana"),
         ref["urbana"]),
        ("Pobreza rural (estrato > 5)", hog.pobre, hog.area.eq("Rural"), base.pobre, base.area.eq("Rural"),
         ref["rural"]),
        ("Pobreza en Lima Metropolitana (dominio == 8)", hog.pobre, hog.dominio.eq(8), base.pobre, base.dominio.eq(8),
         ref["lima_metropolitana"]),
    ]
    for nombre, xh, mh, xp, mp, valor_ref in referenciales:
        mh = slice(None) if mh is None else mh
        mp = slice(None) if mp is None else mp
        vh, vp = pct(xh[mh], wh[mh]), pct(xp[mp], w[mp])
        r.check(nombre, cerca(vh, valor_ref),
                f"{vh:.2f} % con la sumaria (método oficial); {vp:.2f} % con personas y facpob07",
                f"{valor_ref} % ± {TOLERANCIA} pp", esencial=False)
    rep = base[base.hogar_rep == 1]
    pob_rep = pct(rep.pobre, rep.peso_hogar)
    r.check("Hogares de la sumaria representados en la base (método oficial desde el parquet)",
            len(rep) == len(hog) and abs(pob_rep - pob_hog) < 1e-6,
            f"{len(rep):,} de {len(hog):,} hogares; pobreza desde el parquet {pob_rep:.2f} %",
            f"{len(hog):,} y {pob_hog:.2f} %", esencial=False)
    r.check("Sexo (p207) y edad (p208a) sin vacíos", base.sexo.notna().all() and base.grupo_edad.notna().all(),
            f"{int(base.sexo.isna().sum())} sin sexo, {int(base.grupo_edad.isna().sum())} sin grupo de edad",
            "0 y 0", esencial=False)

    # 8. Escribir validacion.txt (siempre, también cuando algo falla)
    encabezado = [
        f"Validación de la ENAHO {anio} (INEI) · {datetime.now():%Y-%m-%d %H:%M}",
        f"Archivos: datos/{ref['codigo']}-Modulo34.zip:{f_hog} y datos/{ref['codigo']}-Modulo02.zip:{f_per}",
        f"Tolerancia para la pobreza: {TOLERANCIA} puntos porcentuales",
    ]
    por_hogar = base.groupby(LLAVES_HOGAR).agg(n=("codperso", "size"), m=("mieperho", "first"),
                                               f7=("factor07", "first"), fp=("facpob07", "first"))
    n_distinto = int((por_hogar.n != por_hogar.m).sum())
    mismo_factor = bool(((por_hogar.f7 - por_hogar.fp).abs() < 1e-3).all())
    nota = [
        "", "Criterio de cálculo", "-------------------",
        "Método oficial (sumaria): un registro por hogar, ponderado con factor07 × mieperho. Es el del INEI y el de la",
        "referencia del curso. Se usa en los indicadores de nivel hogar: nacional, área, dominio y departamento.",
        "Método de personas: cada residente habitual del módulo 02, ponderado con facpob07. Se usa en los atributos",
        "individuales (sexo, grupo de edad y sexo dentro de cada área), que no existen en la sumaria.",
        "La columna metodo de indicadores.csv indica cuál se usó en cada fila.",
        "", "Por qué los dos métodos difieren", "--------------------------------",
        f"A nivel nacional, la sumaria da {pob_hog:.2f} % y las personas {pob_per:.2f} %; ambas redondean a "
        f"{ref['pobreza']} %, la cifra oficial.",
        ("En estos archivos facpob07 es igual a factor07 en todos los hogares, así que la diferencia"
         if mismo_factor else "facpob07 y factor07 no coinciden en todos los hogares; esa es una fuente de diferencia,"),
        f"viene de los miembros contados: en {n_distinto:,} de {len(por_hogar):,} hogares, mieperho no coincide con el",
        "número de residentes habituales que deja el filtro de p204, p205 y p206. En grupos pequeños, como un",
        "departamento, la diferencia llega a cinco décimas; por eso las cifras de nivel hogar se calculan con la",
        "sumaria, que reproduce al decimal las del INEI.",
    ]
    resultado = ["", f"Resultado: {'todas las verificaciones esenciales pasaron' if not r.fallas else 'FALLÓ: ' + '; '.join(r.fallas)}"]
    (salidas / "validacion.txt").write_text("\n".join(encabezado + r.lineas + resultado + nota) + "\n", encoding="utf-8")
    print("\n".join(r.lineas + resultado))
    if r.fallas:
        sys.exit(f"ERROR: fallaron verificaciones esenciales ({'; '.join(r.fallas)}). Revisen salidas/validacion.txt; "
                 "no se guardó la base.")

    # 9. Guardar la base y los indicadores
    columnas = (LLAVES_PERSONA + ["ano", "mes", "ubigeo", "departamento", "departamento_nombre", "dominio",
                "dominio_nombre", "estrato", "area", "p207", "sexo", "p208a", "grupo_edad", "pobreza", "pobre",
                "pobre_extremo", "facpob07", "factor07", "mieperho", "peso_hogar", "hogar_rep"])
    base = base[columnas]
    base.to_parquet(salidas / f"personas_{anio}.parquet", index=False)

    filas = []

    def agregar(nivel, grupos, metodo):
        peso, unidad = ("peso_hogar", "hogares") if metodo == METODO_HOGAR else ("facpob07", "personas")
        for (codigo, categoria), g in grupos:
            filas.append({"nivel": nivel, "codigo": codigo, "categoria": categoria, "metodo": metodo,
                          "pobreza_pct": round(pct(g.pobre, g[peso]), 2),
                          "pobreza_extrema_pct": round(pct(g.pobre_extremo, g[peso]), 2),
                          "poblacion": int(round(g[peso].sum())), "n_muestra": len(g), "unidad_muestral": unidad})

    agregar("nacional", [(("PE", "Perú"), hog)], METODO_HOGAR)
    agregar("area", hog.groupby(["area", "area"]), METODO_HOGAR)
    agregar("dominio", hog.groupby(["dominio", "dominio_nombre"]), METODO_HOGAR)
    agregar("departamento", hog.groupby(["departamento", "departamento_nombre"]), METODO_HOGAR)
    agregar("sexo", base.groupby(["sexo", "sexo"]), METODO_PERSONA)
    agregar("grupo_edad", base.groupby(["grupo_edad", "grupo_edad"], observed=True), METODO_PERSONA)
    sa = base.assign(_c=base.sexo + "-" + base.area, _n=base.sexo + " · " + base.area)
    agregar("sexo_area", sa.groupby(["_c", "_n"]), METODO_PERSONA)
    ind = pd.DataFrame(filas)
    ind.insert(0, "anio", anio)
    ind.to_csv(salidas / "indicadores.csv", index=False, encoding="utf-8")
    print(f"\nGuardé salidas/personas_{anio}.parquet ({len(base):,} personas), salidas/indicadores.csv "
          f"({len(ind)} filas) y salidas/validacion.txt")


if __name__ == "__main__":
    main()
