---
name: graficando-enaho
description: Hace gráficos de barras de la pobreza monetaria de la ENAHO del INEI por área urbana y rural, sexo, grupo de edad, departamento o sexo dentro de cada área, con factores de expansión y el estilo del proyecto (Montserrat, escala de azules, promedio nacional oficial). Úsala cuando pidan un gráfico, una figura o una visualización de la pobreza con la ENAHO, incluidas las brechas entre mujeres y hombres.
argument-hint: "[area | sexo | edad | departamento | sexo_area | todos]"
---

# Graficar la pobreza de la ENAHO

1. Trabaja desde `tarea_8/`. Si no existe `salidas/personas_2024.parquet`, usa primero la skill `limpiando-enaho`.
2. Elige el indicador según el pedido:
   - `area`: urbana y rural.
   - `sexo`.
   - `edad`.
   - `departamento`.
   - `sexo_area`: mujeres y hombres dentro de cada área, en barras agrupadas.
   - `todos`, si el pedido no es claro.
3. Corre exactamente: `uv run ${CLAUDE_SKILL_DIR}/scripts/graficar.py --indicador $0`.
4. Si el script termina con `ERROR`, muestra el mensaje y detente. No grafiques a mano ni con cifras escritas en el código.
5. Abre cada PNG de `figuras/` y revisa que no haya textos superpuestos ni cortados.
6. Responde con la ruta de cada figura y sus cifras clave, e indica el método de cada una:
   - **Área y departamento:** método oficial del INEI, con la sumaria y `factor07 × mieperho`.
   - **Sexo, edad y sexo por área:** método de personas, con `facpob07`.
   - **Línea de referencia:** siempre el promedio nacional oficial (27.6 % en 2024).
7. Si `sexo_area` u otra figura muestra una nota de «menos de 100 casos», repórtala como cifra poco precisa.
8. Para cambiar el diseño, edita `scripts/estilo.py`, que también usa la skill `mapeando-enaho`. Las reglas del estilo son las siguientes:
   - **Barras:** empiezan en cero, van ordenadas y tienen un solo azul. La mayor va en azul marino solo si supera a la siguiente en 1.5 pp o más.
   - **Valores:** van con un decimal; en las barras verticales, dentro de la barra.
   - **Títulos:** son oraciones analíticas, sin dos puntos.
   - **Fuente:** al pie va «Fuente: INEI, ENAHO 2024. Elaboración propia con factores de expansión».
   - **Formato:** PNG a 200 dpi.
