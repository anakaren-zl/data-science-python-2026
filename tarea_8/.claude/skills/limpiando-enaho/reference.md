# Referencia: limpieza de la ENAHO 2024 (INEI)

## Archivos de entrada

| Zip en `datos/` | Archivo que se lee | Una fila por | Filas | Factor |
|---|---|---|---|---|
| `966-Modulo34.zip` | `sumaria-2024.dta` (no `sumaria-2024-12g.dta`) | hogar | 33,691 | `factor07` |
| `966-Modulo02.zip` | `enaho01-2024-200.dta` | persona | 117,721 | `facpob07` |

`966` es el código de la ENAHO 2024 en el portal de microdatos del INEI. Los archivos se leen sin descomprimir, con
`pd.read_stata(..., convert_categoricals=False)`, así que las variables traen códigos numéricos y no etiquetas.

## Llaves

| Nivel | Llave | Ancho |
|---|---|---|
| Hogar | `conglome` + `vivienda` + `hogar` | 6 + 3 + 2 |
| Persona | llave de hogar + `codperso` | + 2 |
| Ubicación | `ubigeo` (departamento, provincia, distrito) | 6 |

Todas las llaves se guardan como texto, con sus ceros iniciales (`zfill`). Si se guardaran como números, el `ubigeo`
010101 se volvería 10101 y `ubigeo[:2]` daría «10» (Huánuco) en lugar de «01» (Amazonas).

Los nombres de columna se pasan a minúsculas y sin tildes ni eñes: `aÑo` → `ano`.

## Criterio de cálculo: dos métodos

| Método | Unidad | Peso | Se usa en | `metodo` en `indicadores.csv` |
|---|---|---|---|---|
| **Oficial (sumaria)** | un registro por hogar | `factor07 × mieperho` | Indicadores de nivel hogar: nacional, área, dominio y departamento | `sumaria: factor07 x mieperho` |
| **Personas** | cada residente habitual | `facpob07` | Atributos individuales: sexo, grupo de edad y sexo dentro de cada área | `personas: facpob07` |

Las cifras de nivel hogar se calculan con el método oficial porque es el que usa el INEI en sus publicaciones y la
referencia del curso, y lo reproduce al decimal:
- nacional: 27.6 %;
- urbana: 24.8 %, y rural: 39.3 %;
- Lima Metropolitana: 28.2 %;
- los 25 departamentos.

La sumaria no tiene sexo ni edad, así que esos atributos solo pueden estimarse con personas y `facpob07`. La línea de
referencia de todos los gráficos es el promedio nacional oficial (27.6 %).

El parquet sirve para los dos métodos:
- **Oficial:** `pobreza_hogar` filtra `hogar_rep == 1` (una fila por hogar) y pondera con `peso_hogar`. En
  `validacion.txt` se comprueba que los 33,691 hogares de la sumaria estén representados.
- **Personas:** `pobreza_personas` usa todas las filas y pondera con `facpob07`.

Las dos funciones están en `graficando-enaho/scripts/estilo.py`.

### Por qué los dos métodos difieren

En 2024, `facpob07` es igual a `factor07` en todos los hogares. La diferencia viene de a quién se cuenta: la sumaria
multiplica por `mieperho`, mientras que la base de personas cuenta a los residentes habituales que deja el filtro.
En 1,846 de los 33,691 hogares esas cifras no coinciden. A nivel nacional, la diferencia es de 0.05 pp (27.58 % y
27.53 %). En un departamento llega a 0.5 pp: Huánuco da 39.0 % con la sumaria y 39.5 % con personas.

## Variables de `salidas/personas_2024.parquet`

| Variable | Origen | Construcción |
|---|---|---|
| `conglome`, `vivienda`, `hogar`, `codperso` | 02 | Llaves, texto |
| `ano`, `mes` | 34 | Año y mes de la encuesta |
| `ubigeo` | 34 | Texto de 6 dígitos |
| `departamento` | 34 | `ubigeo[:2]`, texto de 2 dígitos (01 a 25) |
| `departamento_nombre` | — | Nombre oficial con tildes (Áncash, Apurímac, Huánuco, Junín, San Martín…) |
| `dominio`, `dominio_nombre` | 34 | 1–3 costa norte, centro y sur; 4–6 sierra norte, centro y sur; 7 selva; 8 Lima Metropolitana |
| `estrato` | 34 | 1–8 según el tamaño del centro poblado (1–5 urbano, 6–8 rural) |
| `area` | — | `Urbana` si `estrato <= 5`; `Rural` si no |
| `p207`, `sexo` | 02 | 1 = `Hombre`, 2 = `Mujer` |
| `p208a`, `grupo_edad` | 02 | Edad en años; grupos 0–14, 15–29, 30–44, 45–64 y 65 a más |
| `pobreza` | 34 | 1 = pobre extremo, 2 = pobre no extremo, 3 = no pobre |
| `pobre` | — | 1 si `pobreza <= 2` |
| `pobre_extremo` | — | 1 si `pobreza == 1` |
| `facpob07` | 02 | Factor de personas: método de personas |
| `factor07`, `mieperho` | 34 | Factor de hogares y número de miembros |
| `peso_hogar` | — | `factor07 × mieperho`: método oficial |
| `hogar_rep` | — | 1 en una sola fila por hogar (el menor `codperso`): método oficial |

## Criterios de construcción

1. **Residentes habituales:** `((p204 == 1) & (p205 == 2)) | ((p204 == 2) & (p206 == 1))`. Son los miembros del hogar
   que no estuvieron ausentes 30 días o más, más los no miembros que estuvieron presentes 30 días o más. Quedan
   108,664 de 117,721 filas.
2. **Unión:** personas con hogares por la llave de hogar, con `merge(..., how="left", validate="m:1")`. La unión no
   debe perder ni duplicar filas.
3. **Porcentaje ponderado:** `sum(x * peso) / sum(peso) * 100`, con el peso que corresponda según el método.
4. **Pobreza:** es la pobreza monetaria que publica el INEI en la variable `pobreza` de la sumaria.

## Valores de validación (`salidas/validacion.txt`)

| Verificación | Tipo | Referencia | Resultado 2024 |
|---|---|---|---|
| Llaves únicas en la sumaria y en el módulo 02 | esencial | 0 duplicados | 0 y 0 |
| Unión sin pérdidas ni duplicados | esencial | 108,664 filas | 108,664 |
| Residentes habituales | esencial | 108,664 | 108,664 |
| Códigos departamentales | esencial | 25 | 25 |
| `facpob07` y `factor07` presentes y positivos | esencial | sin vacíos, > 0 | sí |
| Pobreza nacional, personas y `facpob07` | esencial | 27.6 % ± 0.1 pp | 27.53 % |
| Pobreza nacional, sumaria y `factor07 × mieperho` | esencial | 27.6 % ± 0.1 pp | 27.58 % |
| Pobreza extrema nacional (sumaria) | referencial | 5.5 % | 5.50 % |
| Pobreza urbana (sumaria) | referencial | 24.8 % | 24.81 % |
| Pobreza rural (sumaria) | referencial | 39.3 % | 39.30 % |
| Lima Metropolitana, `dominio == 8` (sumaria) | referencial | 28.2 % | 28.21 % |
| Hogares de la sumaria representados en el parquet | referencial | 33,691 | 33,691 |

Las verificaciones referenciales también registran la cifra con el método de personas, para comparar. Si una
verificación esencial falla, el script escribe `validacion.txt` y se detiene sin guardar la base.

## Salidas

| Archivo | Contenido |
|---|---|
| `salidas/personas_2024.parquet` | Una fila por residente habitual (108,664), con las variables de arriba |
| `salidas/indicadores.csv` | Columnas `nivel`, `codigo`, `categoria`, `metodo`, `pobreza_pct`, `pobreza_extrema_pct`, `poblacion` (expandida), `n_muestra` y `unidad_muestral` (hogares o personas). Niveles: nacional, area, dominio y departamento (sumaria); sexo, grupo_edad y sexo_area (personas) |
| `salidas/validacion.txt` | Cada verificación como `[OK]`, `[FALLA]` o `[AVISO]`, con el valor obtenido y el de referencia, más el criterio de cálculo |
