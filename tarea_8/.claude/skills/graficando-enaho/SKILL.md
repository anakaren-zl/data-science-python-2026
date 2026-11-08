---
name: graficando-enaho
description: Hace gráficos de barras de la pobreza monetaria de la ENAHO del INEI por área urbana y rural, sexo, grupo de edad o departamento, ponderados con factores de expansión y con el estilo del proyecto (Montserrat, escala de azules, promedio nacional). Úsala cuando pidan un gráfico, una figura o una visualización de la pobreza con la ENAHO.
argument-hint: "[area | sexo | edad | departamento | todos]"
---

# Graficar la pobreza de la ENAHO

1. Trabaja desde `tarea_8/`. Si no existe `salidas/personas_2024.parquet`, usa primero la skill `limpiando-enaho`.
2. Elige el indicador según el pedido: `area` (urbana y rural), `sexo`, `edad`, `departamento` o `todos`. Si no está claro, usa `todos`.
3. Corre exactamente: `uv run ${CLAUDE_SKILL_DIR}/scripts/graficar.py --indicador $0`.
4. Si el script termina con `ERROR`, muestra el mensaje y detente. No grafiques a mano ni con cifras escritas en el código.
5. Abre cada PNG de `figuras/` y revisa que no haya textos superpuestos ni cortados.
6. Responde con la ruta de cada figura y sus cifras clave, que salen del título y de las barras. Todas están ponderadas con `facpob07`.
7. Para cambiar el diseño, edita `scripts/estilo.py`, que también usa la skill `mapeando-enaho`. Las reglas del estilo son las siguientes:
   - Las barras empiezan en cero, van ordenadas y llevan su valor con un decimal.
   - Hay una línea punteada con el promedio nacional.
   - El título es analítico y el subtítulo indica el periodo y la unidad.
   - Al pie va «Fuente: INEI, ENAHO 2024. Elaboración propia con factores de expansión».
   - La figura se guarda como PNG a 200 dpi.
