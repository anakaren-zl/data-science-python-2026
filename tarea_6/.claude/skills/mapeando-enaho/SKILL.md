---
name: mapeando-enaho
description: Hace un mapa coroplético de la pobreza monetaria de la ENAHO del INEI por departamento del Perú, unido a los límites departamentales por código. Úsala cuando pidan un mapa de la pobreza, comparar regiones o departamentos en un mapa, o ver dónde hay más o menos pobreza en el Perú.
---
# Mapear la ENAHO

1. Si no existe `salidas/personas_2024.parquet`, usa primero la skill `limpiando-enaho`.
2. Si falta `datos/peru_departamental_simple.geojson`, pide al usuario bajarlo de:
   https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/sessions/06-geoespacial/lab/Data/peru_departamental_simple.geojson
3. Corre exactamente: `uv run ${CLAUDE_SKILL_DIR}/scripts/mapear.py`
4. Muestra la ruta `mapas/pobreza_departamento.png` y responde con los departamentos de más y menos pobreza
   que imprime el script, con un decimal y la fuente «INEI, ENAHO 2024».

## Reglas fijas (ya están en el script; no las cambies)

- Une por código: `departamento` (`ubigeo[:2]`) con `FIRST_IDDP`, ambos como texto.
- Nunca por nombre: «APURIMAC» no es «Apurímac».
- Exige 25 departamentos y ninguno sin dato; si falla, revisa la unión, no la quites.
- Un solo color de claro a oscuro, desde 0 (más oscuro = más pobreza); nunca arcoíris.
- Leyenda con la unidad: % de personas en situación de pobreza.
- Lima (15) y Callao (07) van separados.
- Pondera con `facpob07`.

## Estilo

Usa la letra Montserrat y el fondo azul noche de `graficando-enaho`, para que gráficos y mapa se vean como un
solo trabajo. PNG a 200 dpi en `mapas/`, con un CSV al lado con las cifras.