---
name: limpiando-enaho
description: Limpia y une los módulos 34 (sumaria) y 02 (miembros del hogar) de la ENAHO del INEI, filtra a los residentes habituales, valida la pobreza monetaria oficial y arma una base de personas con factores de expansión. Úsala cuando pidan limpiar, unir o analizar la ENAHO, o calcular la pobreza o la pobreza extrema nacional, por área, dominio, departamento, sexo o edad.
argument-hint: "[año, por defecto 2024]"
---

# Limpiar la ENAHO

1. Trabaja desde `tarea_8/`. Si faltan `datos/966-Modulo34.zip` o `datos/966-Modulo02.zip`, pide al usuario bajarlos del portal de microdatos del INEI (código 966 = 2024) y detente.
2. Corre exactamente: `uv run ${CLAUDE_SKILL_DIR}/scripts/limpiar.py --anio $0`. Si no se indicó año, omite `--anio`: el script usa 2024.
3. Si el script termina con `ERROR`, muestra el mensaje y `salidas/validacion.txt`, y detente. No corrijas a mano ni fuerces cifras.
4. Lee `salidas/validacion.txt`: todas las verificaciones esenciales deben estar en `[OK]`. Los `[AVISO]` se reportan, pero no detienen.
5. Responde con `salidas/indicadores.csv`, con una cifra de un decimal, e indica el método que figura en la columna `metodo`:
   - **Nacional, área, dominio y departamento:** método oficial del INEI, con la sumaria y `factor07 × mieperho`.
   - **Sexo, grupo de edad y sexo por área:** método de personas, con `facpob07`.
6. Para un cálculo que no esté en `indicadores.csv`, usa `salidas/personas_<año>.parquet` con el mismo criterio. Para nivel hogar, filtra `hogar_rep == 1` y pondera con `peso_hogar`. Para atributos individuales, usa todas las filas y pondera con `facpob07`.
7. Antes de usar una variable que no está en la base, o si piden explicar llaves, filtros o diferencias entre métodos, lee `reference.md`.
