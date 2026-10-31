---
name: limpiando-enaho
description: Limpia los módulos 34 (sumaria) y 02 (miembros) de la ENAHO del INEI y arma una base de personas con pobreza monetaria y factor de expansión. Úsala cuando pidan limpiar, unir o analizar la ENAHO, o calcular la pobreza nacional, por departamento o región (por ejemplo, Cusco), por área urbana o rural, por sexo o por edad.
argument-hint: [año]
---
# Limpiar la ENAHO

1. Si en `datos/` no están `sumaria-2024.dta` y `enaho01-2024-200.dta` (o sus zip `966-Modulo34.zip` y
   `966-Modulo02.zip`), detente y pide al usuario bajarlos del INEI (código 966 = ENAHO 2024):
   - https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo34.zip
   - https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo02.zip
2. Si ya existe `salidas/personas_2024.parquet`, no vuelvas a limpiar: úsalo. Si no, corre exactamente:
   `uv run ${CLAUDE_SKILL_DIR}/scripts/limpiar.py --anio 2024`
   No reescribas la limpieza a mano ni cambies llaves, filtros o uniones.
3. Lee `salidas/validacion.txt`. Si la pobreza difiere del INEI (27.6 %) en más de 0.1 puntos o no hay
   108,664 residentes, detente y avisa: la base no está bien limpia.
4. Responde con `salidas/personas_2024.parquet`. Toda cifra va ponderada con `facpob07`:
   `100 * np.average(df.pobre, weights=df.facpob07)`. Nunca promedies `pobreza` (es un código) ni cuentes filas.
5. Para un departamento, filtra por código de dos dígitos como texto (`departamento == "08"` es Cusco),
   nunca por nombre. Los códigos están en `reference.md`.
6. Antes de usar una variable que no está en la base, lee `reference.md`.
7. Al responder, di la cifra con un decimal, el año y la fuente: «INEI, ENAHO 2024».