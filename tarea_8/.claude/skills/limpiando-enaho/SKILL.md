---
name: limpiando-enaho
description: Limpia y une los módulos 34 (sumaria) y 02 (miembros del hogar) de la ENAHO del INEI, filtra a los residentes habituales, valida la pobreza monetaria oficial y arma una base de personas con factor de expansión. Úsala cuando pidan limpiar, unir o analizar la ENAHO, o calcular la pobreza o la pobreza extrema nacional, por área, sexo, edad o departamento.
argument-hint: "[año, por defecto 2024]"
---

# Limpiar la ENAHO

1. Trabaja desde `tarea_8/`. Si faltan `datos/966-Modulo34.zip` o `datos/966-Modulo02.zip`, pide al usuario bajarlos del portal de microdatos del INEI (código 966 = 2024) y detente.
2. Corre exactamente: `uv run ${CLAUDE_SKILL_DIR}/scripts/limpiar.py --anio $0`. Si no se indicó año, omite `--anio`: el script usa 2024.
3. Si el script termina con `ERROR`, muestra el mensaje y `salidas/validacion.txt`, y detente. No corrijas a mano ni fuerces cifras.
4. Lee `salidas/validacion.txt`: todas las verificaciones esenciales deben estar en `[OK]`. Los `[AVISO]` se reportan, no detienen.
5. Responde con `salidas/indicadores.csv` o con `salidas/personas_<año>.parquet`. Toda cifra va ponderada con `facpob07` y con un decimal.
6. Antes de usar una variable que no está en la base, o si piden explicar llaves, filtros o diferencias con el INEI, lee `reference.md`.
