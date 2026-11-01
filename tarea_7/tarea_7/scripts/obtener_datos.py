"""Paso 1 · Descarga los microdatos oficiales de la ENAHO 2024 y 2025 (INEI) y los límites departamentales.

    python scripts/obtener_datos.py

Pensado para que lo ejecute Claude Code desde la carpeta tarea_7/. Descarga en datos/originales/, para cada año:

- CODIGO-Modulo02.zip   Características de los miembros del hogar (residentes y factor de expansión)
- CODIGO-Modulo03.zip   Educación (asistencia, nivel aprobado, lengua materna y razones de inasistencia)
- CODIGO-Modulo34.zip   Sumaria (condición de pobreza del hogar)
- peru_departamental_simple.geojson   límites de los 25 departamentos (material del curso, sesión 06)

1031 es el código de la ENAHO 2025 anual y 966 el de la ENAHO 2024 anual en el portal de microdatos del INEI.
Si un archivo ya existe no se vuelve a bajar. Al final se registra la fecha de descarga en datos/originales/descarga.txt.
"""
import datetime as dt
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ORIGINALES = RAIZ / "datos" / "originales"

CODIGOS = {2024: 966, 2025: 1031}
INEI = "https://proyectos.inei.gob.pe/iinei/srienaho/descarga/CSV/{codigo}-Modulo{modulo}.zip"
MODULOS = {"02": "Enaho01-{anio}-200.csv", "03": "Enaho01A-{anio}-300.csv", "34": "Sumaria-{anio}.csv"}
GEOJSON = ("https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/sessions/06-geoespacial/"
           "lab/Data/peru_departamental_simple.geojson")


def bajar(url, destino):
    if destino.exists():
        print(f"Ya existe: {destino.name}")
        return
    print(f"Descargando {url}")
    pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(pedido, timeout=300) as r, open(destino, "wb") as f:
        f.write(r.read())
    print(f"  {destino.name}: {destino.stat().st_size / 1e6:.1f} MB")


def main():
    ORIGINALES.mkdir(parents=True, exist_ok=True)
    for anio, codigo in CODIGOS.items():
        for modulo, csv in MODULOS.items():
            destino = ORIGINALES / f"{codigo}-Modulo{modulo}.zip"
            bajar(INEI.format(codigo=codigo, modulo=modulo), destino)
            # Un zip válido del INEI trae el CSV del módulo; si el portal devolvió una página de error, se detiene
            nombres = [n.split("/")[-1] for n in zipfile.ZipFile(destino).namelist()]
            assert csv.format(anio=anio) in nombres, f"{destino.name} no trae {csv.format(anio=anio)}. Bórralo y reintenta."
    bajar(GEOJSON, ORIGINALES / "peru_departamental_simple.geojson")

    (ORIGINALES / "descarga.txt").write_text(
        "ENAHO anual 2024 (código INEI 966) y 2025 (código INEI 1031), módulos 02, 03 y 34 en formato CSV.\n"
        f"Fuente: https://proyectos.inei.gob.pe/microdatos/\n"
        f"Descargado el {dt.datetime.now():%Y-%m-%d %H:%M}\n", encoding="utf-8")
    print("Listo: los archivos están en datos/originales/")


if __name__ == "__main__":
    main()
