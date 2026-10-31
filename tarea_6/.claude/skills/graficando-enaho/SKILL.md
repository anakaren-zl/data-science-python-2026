---
name: graficando-enaho
description: Hace gráficos de barras de la pobreza monetaria de la ENAHO del INEI por área urbana y rural, sexo, grupo de edad o departamento, siempre ponderados con el factor de expansión. Úsala cuando pidan graficar, comparar o visualizar la pobreza o la pobreza extrema de la ENAHO en un gráfico o figura.
argument-hint: [area|sexo|edad|departamento]
---
# Graficar la ENAHO

1. Si no existe `salidas/personas_2024.parquet`, usa primero la skill `limpiando-enaho`.
2. Elige el grupo según el pedido: `area` (urbana y rural), `sexo`, `edad` o `departamento`.
   Si piden pobreza extrema, agrega `--indicador pobre_extremo`.
3. Corre exactamente: `uv run ${CLAUDE_SKILL_DIR}/scripts/graficar.py --por $0`
4. Muestra la ruta del PNG y responde con las cifras que imprime el script, con un decimal.

## Reglas fijas (ya están en el script; no las cambies)

- Pondera siempre con `facpob07`; nunca cuentes encuestados.
- Barras que empiezan en cero, ordenadas de mayor a menor (la edad conserva su orden natural).
- Una sola gama de azules (más clara = más pobreza) y el valor escrito en cada barra.
- Línea punteada con el promedio nacional, detrás de las barras.
- El título dice qué y cuándo: «Pobreza monetaria por área de residencia, Perú 2024».
- Nota al pie: «Fuente: INEI, ENAHO 2024».
- PNG a 200 dpi en `figuras/`, con un CSV al lado con las cifras.

## Estilo

Fondo azul noche (`#0b1f3a`) con texto y líneas blancas. Letra Montserrat (licencia SIL OFL), guardada en
`fuentes/`: título en Black, subtítulo en SemiBold cursiva, cifras en Bold y categorías en Medium.
Si el pedido necesita otro corte (por ejemplo, dominio), copia el estilo de `graficar.py` en vez de inventar
uno nuevo y lee `.claude/skills/limpiando-enaho/reference.md` para los códigos.