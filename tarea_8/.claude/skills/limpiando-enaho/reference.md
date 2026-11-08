# Referencia: limpieza de la ENAHO 2024 (INEI)

## Archivos de entrada

| Zip en `datos/` | Archivo que se lee | Una fila por | Filas | Factor |
|---|---|---|---|---|
| `966-Modulo34.zip` | `sumaria-2024.dta` (no `sumaria-2024-12g.dta`) | hogar | 33,691 | `factor07` |
| `966-Modulo02.zip` | `enaho01-2024-200.dta` | persona | 117,721 | `facpob07` |

`966` es el código de la ENAHO 2024 en el portal de microdatos del INEI. Se leen sin descomprimir, con
`pd.read_stata(..., convert_categoricals=False)`, así que las variables traen códigos numéricos y no etiquetas.

## Llaves

| Nivel | Llave | Ancho |
|---|---|---|
| Hogar | `conglome` + `vivienda` + `hogar` | 6 + 3 + 2 |
| Persona | llave de hogar + `codperso` | + 2 |
| Ubicación | `ubigeo` (departamento, provincia, distrito) | 6 |

Todas se guardan como texto y con sus ceros iniciales (`zfill`). Con números, `ubigeo` 010101 se volvería 10101 y
`ubigeo[:2]` daría «10» (Huánuco) en lugar de «01» (Amazonas).

Los nombres de columna se pasan a minúsculas y sin tildes ni eñes: `aÑo` → `ano`.

## Variables de la base `salidas/personas_2024.parquet`

| Variable | Origen | Construcción |
|---|---|---|
| `conglome`, `vivienda`, `hogar`, `codperso` | 02 | Llaves, texto |
| `ano`, `mes` | 34 | Año y mes de la encuesta |
| `ubigeo` | 34 | Texto de 6 dígitos |
| `departamento` | 34 | `ubigeo[:2]`, texto de 2 dígitos (01 a 25) |
| `departamento_nombre` | — | Nombre oficial con tildes (Áncash, Apurímac, Huánuco, Junín, San Martín…) |
| `dominio` | 34 | 1–3 costa norte, centro y sur; 4–6 sierra norte, centro y sur; 7 selva; 8 Lima Metropolitana |
| `estrato` | 34 | 1–8 según el tamaño del centro poblado (1–5 urbano, 6–8 rural) |
| `area` | — | `Urbana` si `estrato <= 5`; `Rural` si no |
| `p207`, `sexo` | 02 | 1 = `Hombre`, 2 = `Mujer` |
| `p208a`, `grupo_edad` | 02 | Edad en años; grupos 0–14, 15–29, 30–44, 45–64 y 65 a más |
| `pobreza` | 34 | 1 = pobre extremo, 2 = pobre no extremo, 3 = no pobre |
| `pobre` | — | 1 si `pobreza <= 2` |
| `pobre_extremo` | — | 1 si `pobreza == 1` |
| `facpob07` | 02 | Factor de expansión de personas: **pondera toda cifra** |
| `factor07`, `mieperho` | 34 | Factor de hogares y número de miembros; solo para validar con el método de la sumaria |

## Criterios

1. **Residentes habituales:** `((p204 == 1) & (p205 == 2)) | ((p204 == 2) & (p206 == 1))`. Es decir, miembros
   del hogar que no estuvieron ausentes 30 días o más, más los no miembros que estuvieron presentes 30 días o más.
   Quedan 108,664 de 117,721 filas.
2. **Unión:** personas con hogares por la llave de hogar, `merge(..., how="left", validate="m:1")`. No debe perder
   ni duplicar filas.
3. **Ponderación:** `facpob07` para personas. Un porcentaje es `sum(x * facpob07) / sum(facpob07) * 100`.
4. **Pobreza:** monetaria, la que publica el INEI en la variable `pobreza` de la sumaria.

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
| Pobreza extrema nacional | referencial | 5.5 % | 5.50 % |
| Pobreza urbana | referencial | 24.8 % | 24.74 % |
| Pobreza rural | referencial | 39.3 % | 39.44 % (39.30 % con la sumaria) |
| Lima Metropolitana (`dominio == 8`) | referencial | 28.2 % | 28.03 % (28.21 % con la sumaria) |

Si una verificación esencial falla, el script escribe `validacion.txt` y se detiene sin guardar la base.

## Por qué los dos métodos difieren

En 2024, `facpob07` es igual a `factor07` en todos los hogares. La diferencia viene de a quién se cuenta: la sumaria
multiplica por `mieperho` y la base de personas cuenta a los residentes habituales. En 1,846 de los 33,691 hogares
esas cifras no coinciden. Por eso, algunas cifras por grupo difieren del INEI hasta en cinco décimas. Con el método
de la sumaria, las 25 cifras departamentales de la referencia del curso coinciden al decimal.

## Salidas

| Archivo | Contenido |
|---|---|
| `salidas/personas_2024.parquet` | Una fila por residente habitual (108,664), con las variables de arriba |
| `salidas/indicadores.csv` | `nivel` (nacional, area, sexo, grupo_edad, departamento), `codigo`, `categoria`, `pobreza_pct`, `pobreza_extrema_pct`, `poblacion` (expandida) y `n_muestra` |
| `salidas/validacion.txt` | Cada verificación como `[OK]`, `[FALLA]` o `[AVISO]`, con el valor obtenido y el de referencia |
