"""Paso 2 · Limpia la ENAHO 2024 y 2025 y construye la base analítica de niñas, niños y adolescentes de 6 a 17 años.

    python scripts/procesar_datos.py

Lee los zip de datos/originales/ (o sus CSV extraídos), aplica a cada año los mismos siete pasos y guarda en
datos/procesados/:

- base_analitica.csv   una fila por residente habitual de 6 a 17 años entrevistado entre abril y diciembre,
                       con la columna anio (2024 o 2025)
- validacion.txt       las cifras que comprueban la limpieza de cada año contra las cifras oficiales del INEI

Si una comprobación falla, el script se detiene con un AssertionError y no guarda la base.
"""
import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ORIGINALES = RAIZ / "datos" / "originales"
PROCESADOS = RAIZ / "datos" / "procesados"
CODIGOS = {2024: 966, 2025: 1031}  # ENAHO anual en el portal de microdatos del INEI

# Cifras oficiales para validar. Pobreza: INEI, Informe técnico de pobreza monetaria 2016-2025 (2026).
# Asistencia a secundaria: INEI, Estadísticas con enfoque de género (86,6 % en 2024) y Condiciones de vida 2025 (88 %)
OFICIAL = {2024: {"pobreza": 27.6, "asistencia_secundaria": 86.6},
           2025: {"pobreza": 25.7, "asistencia_secundaria": 88.0}}

LLAVES_HOGAR = ["CONGLOME", "VIVIENDA", "HOGAR"]
LLAVES_PERSONA = LLAVES_HOGAR + ["CODPERSO"]
VARS_300 = LLAVES_PERSONA + ["MES", "UBIGEO", "ESTRATO", "P300A", "P301A", "P306", "P307", "P308A", "P313",
                             "P204", "P205", "P206", "P207", "P208A", "FACTORA07"]

LENGUA_INDIGENA = {1, 2, 3, 10, 11, 12, 13, 14, 15}  # P300A: quechua, aimara, otra nativa y lenguas amazónicas
SECUNDARIA_COMPLETA_O_MAS = {6, 7, 8, 9, 10, 11}      # P301A: secundaria completa o estudios superiores
RAZONES = {1: "Problemas económicos", 2: "Trabajo", 3: "Terminó sus estudios", 5: "Problemas familiares",
           6: "De vacaciones", 7: "No hay centro educativo", 8: "Asiste a un CETPRO", 9: "No le interesa estudiar",
           10: "Quehaceres del hogar", 11: "Otra razón"}


# 1 · Leer -------------------------------------------------------------------------------------------
def leer_csv(nombre, columnas, codigo):
    """Lee un CSV del INEI, suelto en datos/originales/ o dentro de su zip, sin importar su separador."""
    suelto = ORIGINALES / nombre
    if suelto.exists():
        fuente = suelto
    else:
        for z in ORIGINALES.glob(f"{codigo}-Modulo*.zip"):
            hallados = [n for n in zipfile.ZipFile(z).namelist() if n.endswith("/" + nombre) or n == nombre]
            if hallados:
                fuente = io.BytesIO(zipfile.ZipFile(z).read(hallados[0]))
                break
        else:
            raise AssertionError(f"No encontré {nombre}. Corre antes scripts/obtener_datos.py")
    # El INEI publicó 2025 con ';' y coma decimal, y 2024 con ',' y punto decimal: se detecta en la cabecera
    if isinstance(fuente, Path):
        fuente = io.BytesIO(fuente.read_bytes())
    cabecera = fuente.readline()
    fuente.seek(0)
    separador = ";" if cabecera.count(b";") > cabecera.count(b",") else ","
    df = pd.read_csv(fuente, sep=separador, encoding="latin-1", usecols=lambda c: c in columnas, dtype=str)
    for c in df.columns:
        df[c] = df[c].str.strip()
        if c not in LLAVES_PERSONA + ["UBIGEO"]:
            df[c] = pd.to_numeric(df[c].str.replace(",", "."), errors="coerce")
    return df


def residente(df):
    """Residente habitual: miembro que no está ausente 30 días o más, o no miembro presente 30 días o más."""
    return ((df.P204 == 1) & (df.P205 == 2)) | ((df.P204 == 2) & (df.P206 == 1))


def es(x, d=0):
    """Número en formato peruano: espacio para los miles y coma decimal (23 345 y 25,67)."""
    texto = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return texto


def pct(x, w):
    return 100 * np.average(x, weights=w)


def procesar(anio):
    codigo, oficial = CODIGOS[anio], OFICIAL[anio]
    edu = leer_csv(f"Enaho01A-{anio}-300.csv", VARS_300, codigo)
    miembros = leer_csv(f"Enaho01-{anio}-200.csv", LLAVES_PERSONA + ["P204", "P205", "P206", "P208A"], codigo)
    sumaria = leer_csv(f"Sumaria-{anio}.csv", LLAVES_HOGAR + ["POBREZA", "MIEPERHO", "FACTOR07"], codigo)

    # 2 · Filtrar residentes habituales de 6 a 17 años (edades de la educación básica obligatoria) ----
    base = edu[residente(edu) & edu.P208A.between(6, 17)].copy()
    res_200 = miembros[residente(miembros) & miembros.P208A.between(6, 17)]
    cobertura = len(base) / len(res_200)
    assert cobertura > 0.97, f"El módulo 300 cubre solo {cobertura:.1%} de los residentes de 6 a 17 años"
    assert not base.duplicated(LLAVES_PERSONA).any(), "Hay personas repetidas en el módulo 300"

    # 3 · Unir la condición de pobreza del hogar --------------------------------------------------------
    assert not sumaria.duplicated(LLAVES_HOGAR).any(), "Hay hogares repetidos en la sumaria"
    n = len(base)
    base = base.merge(sumaria[LLAVES_HOGAR + ["POBREZA"]], on=LLAVES_HOGAR, how="left", validate="m:1")
    assert len(base) == n and base.POBREZA.notna().all(), "La unión con la sumaria perdió o duplicó personas"

    # 4 · Construir los ejes de desigualdad y el indicador -----------------------------------------------
    base["sexo"] = base.P207.map({1: "Hombre", 2: "Mujer"})
    base["area"] = np.where(base.ESTRATO <= 5, "Urbana", "Rural")          # estratos 6 a 8 son rurales
    base["lengua"] = np.select([base.P300A.isin(LENGUA_INDIGENA), base.P300A == 4],
                               ["Indígena", "Castellano"], "Otra")
    base["pobreza"] = np.where(base.POBREZA <= 2, "Pobre", "No pobre")   # 1 extrema, 2 no extrema, 3 no pobre
    base["departamento"] = base.UBIGEO.str.zfill(6).str[:2]
    base["edad"] = base.P208A.astype(int)
    base["asiste"] = ((base.P306 == 1) & (base.P307 == 1)).astype(int)
    base["concluyo"] = base.P301A.isin(SECUNDARIA_COMPLETA_O_MAS).astype(int)
    # Interrupción de la trayectoria escolar: no asiste y no ha concluido la secundaria
    base["fuera"] = ((base.asiste == 0) & (base.concluyo == 0)).astype(int)
    base["razon"] = base.P313.map(RAZONES)
    # Asiste a secundaria (para comparar con la tasa neta de asistencia que publica el INEI)
    base["asiste_secundaria"] = ((base.asiste == 1) & (base.P308A == 3)).astype(int)

    # 5 · Periodo lectivo: entre enero y marzo casi todos los no matriculados están «de vacaciones» ------
    vacaciones = (base[(base.MES <= 3) & (base.asiste == 0)].P313 == 6).mean()
    lectivo = base[base.MES >= 4].copy()

    # 6 · Validar contra el INEI -------------------------------------------------------------------------
    sumaria["peso"] = sumaria.FACTOR07 * sumaria.MIEPERHO
    pobreza_nacional = pct(sumaria.POBREZA <= 2, sumaria.peso)
    sec = lectivo[lectivo.edad.between(12, 16)]
    asistencia_sec = pct((sec.asiste == 1) & (sec.P308A == 3), sec.FACTORA07)
    assert abs(pobreza_nacional - oficial["pobreza"]) < 0.1, f"Pobreza {anio} {pobreza_nacional:.2f}; el INEI da {oficial['pobreza']}"
    assert abs(asistencia_sec - oficial["asistencia_secundaria"]) < 1.5, f"Asistencia secundaria {anio} {asistencia_sec:.1f}"
    assert lectivo.departamento.nunique() == 25, "No están los 25 departamentos"

    lectivo["anio"] = anio

    lineas = [
        f"ENAHO {anio} anual (código INEI {codigo})",
        f"Residentes de 6 a 17 años en el módulo 200            {es(len(res_200)):>8}",
        f"Residentes de 6 a 17 años en el módulo 300            {es(len(base)):>8}  ({es(100 * cobertura, 1)} %)",
        f"No matriculados de enero a marzo «de vacaciones»      {es(100 * vacaciones, 1):>8} %",
        f"Base final, entrevistas de abril a diciembre          {es(len(lectivo)):>8}",
        f"  de ellas, mujeres                                   {es((lectivo.sexo == 'Mujer').sum()):>8}",
        f"Pobreza monetaria nacional (sumaria)                  {es(pobreza_nacional, 2):>8} %   INEI {es(oficial['pobreza'], 1)} %",
        f"Tasa neta de asistencia a secundaria, 12 a 16 años    {es(asistencia_sec, 2):>8} %   INEI {es(oficial['asistencia_secundaria'], 1)} %",
        "",
    ]
    metricas = {"anio": anio, "pobreza": pobreza_nacional, "asistencia_secundaria": asistencia_sec,
                "vacaciones_pct": 100 * vacaciones, "casos": len(lectivo), "casos_mujeres": int((lectivo.sexo == "Mujer").sum())}
    return lectivo, lineas, metricas


def main():
    PROCESADOS.mkdir(parents=True, exist_ok=True)
    bases, metricas, lineas = [], [], ["Validación de la limpieza contra las cifras oficiales del INEI", ""]
    for anio in sorted(CODIGOS):
        base, texto, m = procesar(anio)
        bases.append(base)
        metricas.append(m)
        lineas += texto
    pd.DataFrame(metricas).to_csv(PROCESADOS / "validacion.csv", index=False)
    lineas.append("Resultado: todas las comprobaciones pasaron en ambos años (OK).")
    columnas = ["anio", "CONGLOME", "MES", "departamento", "sexo", "edad", "area", "lengua", "pobreza",
                "asiste", "asiste_secundaria", "concluyo", "fuera", "razon", "FACTORA07"]
    base = pd.concat(bases, ignore_index=True)[columnas]
    base.to_csv(PROCESADOS / "base_analitica.csv", index=False)
    (PROCESADOS / "validacion.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    print(f"\nGuardado: datos/procesados/base_analitica.csv ({es(len(base))} filas)")


if __name__ == "__main__":
    main()
