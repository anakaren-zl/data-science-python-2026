---
name: mapeando-enaho
description: Hace un mapa coroplético de la pobreza monetaria por departamento del Perú con la ENAHO del INEI, con el método oficial y factores de expansión, y lo compara con la referencia del curso. Úsala cuando pidan un mapa de la pobreza por departamento o región, o comparar la pobreza departamental de la ENAHO.
argument-hint: "[año, por defecto 2024]"
---

# Mapear la pobreza de la ENAHO

1. Trabaja desde `tarea_8/`. Si no existe `salidas/personas_2024.parquet`, usa primero la skill `limpiando-enaho`.
2. Si falta `datos/peru_departamental_simple.geojson`, pide al usuario bajarlo (Sesión 06 del curso) y detente.
3. Corre exactamente: `uv run ${CLAUDE_SKILL_DIR}/scripts/mapear.py`.
4. Si el script termina con `ERROR`, muestra el mensaje y detente. Nunca unas por nombre ni completes departamentos a mano. La unión es `departamento` (`ubigeo[:2]`) con `FIRST_IDDP`, ambos como texto de dos dígitos, y deben quedar 25 departamentos con dato.
5. La pobreza departamental es un indicador de nivel hogar: se calcula con el método oficial del INEI (sumaria, `factor07 × mieperho`). El promedio nacional del subtítulo también es el oficial.
6. Lee `salidas/comparacion_mapa.csv`. Con el método oficial, los 25 departamentos deben coincidir al decimal con `referencias/pobreza_departamento_2024.csv`; reporta cualquier fila en `AVISO`. La columna `pobreza_personas_1d` (`facpob07`) es solo diagnóstico.
7. Abre `mapas/pobreza_departamento.png` y revisa dos cosas: que Lima (15) y Callao (07) aparezcan separados y con su valor, y que no haya textos superpuestos.
8. El estilo sale de `../graficando-enaho/scripts/estilo.py`:
   - Escala secuencial de azules en tramos de 10 puntos desde 0.
   - Leyenda horizontal con la unidad.
   - Recuadro ampliado de Lima y Callao.
   - Listas con los cinco departamentos de mayor y de menor pobreza.
