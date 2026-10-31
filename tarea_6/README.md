# Tarea 6 · Skills de Claude Code para limpiar, graficar y mapear la ENAHO 2024

**Autora:** Ana Karen Zamalloa Lima · Diplomado de Ciencia de Datos para el Análisis Social y la Gestión Pública (PUCP) ·
Sesión 16 · Issue #22

Este proyecto reúne tres skills de Claude Code que trabajan encadenadas: la primera limpia los módulos de la ENAHO
del INEI, la segunda produce gráficos de pobreza y la tercera elabora un mapa por departamento. El propósito es que
cualquier persona que clone el repositorio y formule a Claude Code una pregunta como «¿cuál fue la pobreza en Cusco
en 2024?» o «haz un mapa de la pobreza por departamento» obtenga siempre la misma base, las mismas cifras y las
mismas figuras, con la pobreza oficial del INEI replicada.

![Mapa de la pobreza monetaria por departamento, Perú 2024](mapas/pobreza_departamento.png)

## Las tres skills

| Skill | Entra | Sale |
|---|---|---|
| [`limpiando-enaho`](.claude/skills/limpiando-enaho/SKILL.md) | Módulos 34 (sumaria) y 02 (miembros) del INEI | `salidas/personas_2024.parquet` y `salidas/validacion.txt` |
| [`graficando-enaho`](.claude/skills/graficando-enaho/SKILL.md) | La base limpia y un corte: área, sexo, edad o departamento | `figuras/pobreza_<corte>.png` y su CSV |
| [`mapeando-enaho`](.claude/skills/mapeando-enaho/SKILL.md) | La base limpia y los límites de los 25 departamentos | `mapas/pobreza_departamento.png` y su CSV |

Las skills de gráficos y mapas indican: «Si no existe `salidas/personas_2024.parquet`, usa primero la skill
`limpiando-enaho`». De este modo, un solo pedido puede activar dos skills seguidas.

## Estructura

```text
tarea_6/
├── .claude/skills/
│   ├── limpiando-enaho/    SKILL.md · reference.md · scripts/limpiar.py
│   ├── graficando-enaho/   SKILL.md · scripts/graficar.py · fuentes/ (Montserrat, SIL OFL)
│   └── mapeando-enaho/     SKILL.md · scripts/mapear.py
├── datos/                  archivos del INEI y GeoJSON (no se suben; ver abajo)
├── salidas/validacion.txt  cifras que comprueban la limpieza
├── figuras/                gráficos de barras (PNG a 200 dpi) y sus CSV
├── mapas/                  mapa por departamento y su CSV
├── evaluacion.md           tres pedidos con y sin skills
├── pyproject.toml · uv.lock
└── README.md
```

## Cómo reproducirlo

### 1. Bajar los datos a `tarea_6/datos/`

La carpeta `datos/` está en `.gitignore`, de modo que cada persona debe bajar los archivos desde su navegador:

| Archivo | Enlace | Qué contiene |
|---|---|---|
| Módulo 34 · Sumaria | [966-Modulo34.zip](https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo34.zip) | `sumaria-2024.dta`: una fila por hogar |
| Módulo 02 · Miembros | [966-Modulo02.zip](https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo02.zip) | `enaho01-2024-200.dta`: una fila por persona |
| Límites departamentales | [peru_departamental_simple.geojson](https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/sessions/06-geoespacial/lab/Data/peru_departamental_simple.geojson) | 25 departamentos, con `FIRST_IDDP` |

`966` es el código de la ENAHO 2024 en el portal de microdatos del INEI. Pueden dejarse los zip tal cual o
descomprimir solo `sumaria-2024.dta` y `enaho01-2024-200.dta`: el script acepta ambas formas. Al guardar el GeoJSON,
conviene verificar que el navegador no le añada la extensión `.txt`.

### 2. Instalar el entorno

Desde la carpeta `tarea_6/`, con [uv](https://docs.astral.sh/uv/) instalado:

```bash
uv sync
```

Las librerías (pandas, pyarrow, geopandas y matplotlib) están fijadas en `pyproject.toml` y `uv.lock`.

### 3. Usar las skills con Claude Code

Abrir Claude Code **desde `tarea_6/`**, para que encuentre la carpeta `.claude/skills/`, y formular la pregunta:

```bash
claude
> ¿Cuál fue la pobreza en Cusco en 2024?
> Grafica la pobreza urbana y rural
> Haz un mapa de la pobreza por departamento
```

### 4. O correr los scripts directamente

```bash
uv run .claude/skills/limpiando-enaho/scripts/limpiar.py --anio 2024
uv run .claude/skills/graficando-enaho/scripts/graficar.py --por area          # también: sexo, edad, departamento
uv run .claude/skills/mapeando-enaho/scripts/mapear.py
```

## Validación

La limpieza sigue los siete pasos de la sesión (leer, normalizar, filtrar, unir, construir, validar y guardar) y se
detiene con un error si alguna comprobación falla. Los resultados de `salidas/validacion.txt` son:

| Cifra | Resultado | Referencia |
|---|---|---|
| Residentes habituales | **108,664** de 117,721 filas | 108,664 |
| Hogares en la sumaria | 33,691 | 33,691 |
| Pobreza monetaria (sumaria, `factor07 × mieperho`) | **27.58 %** | 27.6 % (INEI) |
| Pobreza monetaria (personas, `facpob07`) | **27.53 %** | 27.6 % (INEI) |
| Pobreza extrema | 5.50 % | 5.5 % |
| Departamentos con dato | 25 | 25 |

Las decisiones que la skill fija para no improvisarlas en cada pedido son:

- las llaves se leen como texto, con ceros a la izquierda;
- la columna `aÑo` se normaliza a `anio`;
- solo se conservan los residentes habituales: `(p204 == 1 & p205 == 2) | (p204 == 2 & p206 == 1)`;
- la unión usa `validate="m:1"`;
- `pobre = pobreza <= 2` es una categoría, nunca un promedio;
- toda cifra de personas se pondera con `facpob07`.

## Gráficos

<p float="left">
  <img src="figuras/pobreza_area.png" width="49%" />
  <img src="figuras/pobreza_edad.png" width="49%" />
</p>

Los gráficos respetan las reglas de la sesión: ponderación con `facpob07`, barras que empiezan en cero y van
ordenadas, una sola gama de azules, el valor escrito en cada barra, un título que dice qué y cuándo, la nota
«Fuente: INEI, ENAHO 2024» y formato PNG a 200 dpi. El estilo (fondo azul noche y tipografía Montserrat en Black,
SemiBold cursiva, Bold y Medium) está fijado en el script, de modo que todas las figuras se ven como un mismo trabajo.

## Evaluación

En las tres consultas con skills, Claude Code activó la skill correcta sin que se la nombrara y replicó las cifras
de referencia: Cusco 18.5 %; urbano 24.7 % y rural 39.4 %; Cajamarca 45.0 %. Una primera prueba permitió detectar y
corregir una instrucción ambigua en `graficando-enaho`. Sin skills, Claude llegó a las mismas cifras, pero
reutilizando las salidas y los scripts de las skills que ya estaban en el repositorio. El detalle, junto con las
diferencias de décimas frente a las referencias y las limitaciones de la prueba, está en
[`evaluacion.md`](evaluacion.md).

## Fuentes

- INEI. *Encuesta Nacional de Hogares (ENAHO) 2024*, módulos 34 y 02. Portal de microdatos.
- Curso Data Science con Python: [sesión 16, Skills ENAHO](https://github.com/d2cml-ai/Data-Science-Python/tree/main/sessions/16-skills-enaho).
- Anthropic. [Skills en Claude Code](https://code.claude.com/docs/en/skills).
- Tipografía [Montserrat](https://github.com/JulietaUla/Montserrat) (SIL Open Font License).