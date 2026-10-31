"""Limpia los módulos 34 (sumaria) y 02 (miembros) de la ENAHO y arma una base de personas.

    uv run .claude/skills/limpiando-enaho/scripts/limpiar.py --anio 2024

Lee desde datos/ los archivos del INEI, sueltos (sumaria-2024.dta y enaho01-2024-200.dta) o dentro de
sus zip (966-Modulo34.zip y 966-Modulo02.zip), sigue siempre los siete pasos de la sesión 16 y guarda:

- salidas/personas_2024.parquet   una fila por residente habitual, con la pobreza de su hogar
- salidas/validacion.txt          las cifras que comprueban la limpieza contra el INEI

Si una comprobación falla, el script se detiene con un AssertionError y no guarda la base.
"""
import argparse
import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path.cwd()
DATOS = RAIZ / "datos"
SALIDAS = RAIZ / "salidas"

# Código de cada año en el portal de microdatos del INEI
CODIGOS = {2024: 966}

# Cifras oficiales para validar (README de la sesión 16, calculadas con los archivos 2024 del INEI)
OFICIAL = {2024: {"pobreza": 27.6, "hogares": 33_691, "filas_200": 117_721, "residentes": 108_664}}

LLAVES_HOGAR = ["conglome", "vivienda", "hogar"]
LLAVES_PERSONA = LLAVES_HOGAR + ["codperso"]
ANCHO = {"conglome": 6, "vivienda": 3, "hogar": 2, "codperso": 2, "ubigeo": 6}

VARS_SUMARIA = ["ubigeo", "dominio", "estrato", "pobreza", "mieperho", "factor07"]
VARS_PERSONAS = ["p203", "p204", "p205", "p206", "p207", "p208a", "facpob07"]


# 1 · Leer -----------------------------------------------------------------------------------
def leer_dta(zip_path, patron):
    """Lee el .dta del zip cuyo nombre contiene `patron`, sin convertir etiquetas en categorías.
    Si el .dta ya está descomprimido en datos/, lo lee directamente."""
    sueltos = [p for p in DATOS.glob("*.dta") if patron in p.name.lower() and "12g" not in p.name.lower()]
    if len(sueltos) == 1:
        return pd.read_stata(sueltos[0], convert_categoricals=False)
    with zipfile.ZipFile(zip_path) as z:
        nombres = [n for n in z.namelist() if n.lower().endswith(".dta") and patron in n.lower()]
        assert len(nombres) == 1, f"Esperaba un .dta con '{patron}' en {zip_path.name}, hallé {nombres}"
        return pd.read_stata(io.BytesIO(z.read(nombres[0])), convert_categoricals=False)


def como_texto(serie, ancho):
    """Llaves como texto con ceros a la izquierda: 15009 -> '015009'."""
    if pd.api.types.is_numeric_dtype(serie):
        serie = serie.astype("Int64").astype(str)
    return serie.astype(str).str.strip().str.zfill(ancho)


# 2 · Normalizar -----------------------------------------------------------------------------
def normalizar(df):
    """Columnas en minúscula; 'aÑo' (o 'año') pasa a 'anio'."""
    df.columns = [c.lower().replace("ñ", "ni") for c in df.columns]
    for c, n in ANCHO.items():
        if c in df.columns:
            df[c] = como_texto(df[c], n)
    return df


def main(anio):
    codigo = CODIGOS[anio]
    zip34, zip02 = DATOS / f"{codigo}-Modulo34.zip", DATOS / f"{codigo}-Modulo02.zip"
    hay = {z: z.exists() or any(DATOS.glob(f"{p}*.dta")) for z, p in
           [(zip34, f"sumaria-{anio}"), (zip02, f"enaho01-{anio}-200")]}
    faltan = [z.name for z, ok in hay.items() if not ok]
    assert not faltan, f"Faltan {faltan} en datos/. Bájalos del INEI (código {codigo} = ENAHO {anio})."

    sumaria = normalizar(leer_dta(zip34, "sumaria"))
    miembros = normalizar(leer_dta(zip02, "200"))
    filas_200 = len(miembros)

    # 3 · Filtrar: residentes habituales ------------------------------------------------------
    # Miembro presente que no está ausente (p204==1 & p205==2) o no miembro presente 30 días o más (p204==2 & p206==1)
    residente = ((miembros.p204 == 1) & (miembros.p205 == 2)) | ((miembros.p204 == 2) & (miembros.p206 == 1))
    personas = miembros.loc[residente, LLAVES_PERSONA + VARS_PERSONAS].copy()

    # 4 · Unir personas y hogares (cada persona con un solo hogar) ----------------------------
    assert not sumaria.duplicated(LLAVES_HOGAR).any(), "Hay hogares repetidos en la sumaria"
    assert not personas.duplicated(LLAVES_PERSONA).any(), "Hay personas repetidas en el módulo 200"
    base = personas.merge(sumaria[LLAVES_HOGAR + VARS_SUMARIA], on=LLAVES_HOGAR, how="left",
                          validate="m:1", indicator=True)
    assert len(base) == len(personas), "La unión perdió o duplicó filas"
    assert (base._merge == "both").all(), "Hay personas sin hogar en la sumaria"
    base = base.drop(columns="_merge")

    # 5 · Construir ---------------------------------------------------------------------------
    base["departamento"] = base.ubigeo.str[:2]
    base["urbano"] = base.estrato <= 5
    base["area"] = np.where(base.urbano, "Urbana", "Rural")
    base["pobre"] = base.pobreza <= 2            # 1 extremo, 2 no extremo, 3 no pobre: es categoría, no número
    base["pobre_extremo"] = base.pobreza == 1
    base["sexo"] = base.p207.map({1: "Hombre", 2: "Mujer"})
    base["edad"] = base.p208a
    base["anio"] = anio

    # 6 · Validar -----------------------------------------------------------------------------
    def pct(df, var, peso):
        return 100 * np.average(df[var], weights=df[peso])

    sumaria["pobre"] = sumaria.pobreza <= 2
    sumaria["pobre_extremo"] = sumaria.pobreza == 1
    sumaria["peso_personas"] = sumaria.factor07 * sumaria.mieperho

    cifras = {
        "Filas del módulo 200": filas_200,
        "Residentes habituales (filas de la base)": len(base),
        "Hogares en la sumaria": len(sumaria),
        "Población expandida (millones, facpob07)": base.facpob07.sum() / 1e6,
        "Pobreza monetaria, sumaria y factor07 × mieperho (%)": pct(sumaria, "pobre", "peso_personas"),
        "Pobreza monetaria, personas y facpob07 (%)": pct(base, "pobre", "facpob07"),
        "Pobreza extrema, personas y facpob07 (%)": pct(base, "pobre_extremo", "facpob07"),
        "Pobreza urbana (estrato <= 5) (%)": pct(base[base.urbano], "pobre", "facpob07"),
        "Pobreza rural (estrato > 5) (%)": pct(base[~base.urbano], "pobre", "facpob07"),
        "Pobreza en Lima Metropolitana (dominio == 8) (%)": pct(base[base.dominio == 8], "pobre", "facpob07"),
        "Departamentos con dato": base.departamento.nunique(),
    }

    ref = OFICIAL.get(anio)
    if ref:
        assert filas_200 == ref["filas_200"], f"El módulo 200 trae {filas_200} filas; esperaba {ref['filas_200']}"
        assert len(sumaria) == ref["hogares"], f"La sumaria trae {len(sumaria)} hogares; esperaba {ref['hogares']}"
        assert len(base) == ref["residentes"], f"Quedaron {len(base)} residentes; esperaba {ref['residentes']}"
        for clave in ["Pobreza monetaria, sumaria y factor07 × mieperho (%)", "Pobreza monetaria, personas y facpob07 (%)"]:
            assert abs(cifras[clave] - ref["pobreza"]) < 0.1, f"{clave} = {cifras[clave]:.2f}; el INEI da {ref['pobreza']}"
    assert base.departamento.nunique() == 25, "No están los 25 departamentos"

    # 7 · Guardar -----------------------------------------------------------------------------
    SALIDAS.mkdir(exist_ok=True)
    columnas = (LLAVES_PERSONA + ["anio", "ubigeo", "departamento", "dominio", "estrato", "urbano", "area",
                                  "p203", "sexo", "edad", "pobreza", "pobre", "pobre_extremo", "mieperho",
                                  "factor07", "facpob07"])
    base[columnas].to_parquet(SALIDAS / f"personas_{anio}.parquet", index=False)

    lineas = [f"Validación de la limpieza · ENAHO {anio} (código INEI {codigo})", ""]
    for k, v in cifras.items():
        lineas.append(f"{k:<56} {v:>12,.2f}" if isinstance(v, (float, np.floating)) else f"{k:<56} {v:>12,}")
    if ref:
        lineas += ["", f"Referencia oficial INEI: pobreza {ref['pobreza']} %, {ref['residentes']:,} residentes, "
                       f"{ref['hogares']:,} hogares.", "Resultado: todas las comprobaciones pasaron (OK)."]
    (SALIDAS / "validacion.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    print(f"\nGuardado: salidas/personas_{anio}.parquet ({len(base):,} filas)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--anio", type=int, default=2024, choices=sorted(CODIGOS))
    main(p.parse_args().anio)