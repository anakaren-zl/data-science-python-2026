# Referencia · ENAHO 2024 (módulos 34 y 02)

## Archivos

| Módulo | Archivo dentro del zip | Una fila por | Filas | Llaves | Factor |
|---|---|---|---|---|---|
| 34 · Sumaria | `sumaria-2024.dta` | hogar | 33,691 | `conglome`, `vivienda`, `hogar` | `factor07` |
| 02 · Miembros | `enaho01-2024-200.dta` | persona | 117,721 | las tres + `codperso` | `facpob07` |

## Variables de la base limpia (`salidas/personas_2024.parquet`)

| Variable | Origen | Qué es |
|---|---|---|
| `conglome`, `vivienda`, `hogar`, `codperso` | ambos | Llaves, como texto con ceros a la izquierda |
| `ubigeo` | sumaria | Código de distrito, texto de 6 dígitos |
| `departamento` | construida | `ubigeo[:2]`, texto de 2 dígitos |
| `dominio` | sumaria | 1 costa norte, 2 costa centro, 3 costa sur, 4 sierra norte, 5 sierra centro, 6 sierra sur, 7 selva, 8 Lima Metropolitana |
| `estrato` | sumaria | 1–5 urbano (centros poblados de más de 2,000 habitantes), 6–8 rural |
| `urbano`, `area` | construidas | `estrato <= 5`; «Urbana» / «Rural» |
| `p203` | miembros | Parentesco con el jefe del hogar (1 jefe, 2 cónyuge, 3 hijo/a…) |
| `p207`, `sexo` | miembros | 1 hombre, 2 mujer |
| `p208a`, `edad` | miembros | Edad en años cumplidos |
| `pobreza` | sumaria | 1 pobre extremo, 2 pobre no extremo, 3 no pobre. Es un código |
| `pobre`, `pobre_extremo` | construidas | `pobreza <= 2`; `pobreza == 1` |
| `mieperho` | sumaria | Miembros del hogar |
| `factor07` | sumaria | Factor de expansión del hogar |
| `facpob07` | miembros | Factor de expansión de la persona: **úsalo para toda cifra de personas** |

## Residentes habituales

`(p204 == 1 & p205 == 2) | (p204 == 2 & p206 == 1)`

- `p204`: ¿es miembro del hogar? (1 sí, 2 no)
- `p205`: ¿se encuentra ausente del hogar 30 días o más? (1 sí, 2 no)
- `p206`: ¿está presente en el hogar 30 días o más? (1 sí, 2 no)

## Códigos de departamento (`departamento` = `FIRST_IDDP` del GeoJSON)

| Código | Departamento | Código | Departamento | Código | Departamento |
|---|---|---|---|---|---|
| 01 | Amazonas | 10 | Huánuco | 19 | Pasco |
| 02 | Áncash | 11 | Ica | 20 | Piura |
| 03 | Apurímac | 12 | Junín | 21 | Puno |
| 04 | Arequipa | 13 | La Libertad | 22 | San Martín |
| 05 | Ayacucho | 14 | Lambayeque | 23 | Tacna |
| 06 | Cajamarca | 15 | Lima | 24 | Tumbes |
| 07 | Callao | 16 | Loreto | 25 | Ucayali |
| 08 | Cusco | 17 | Madre de Dios | | |
| 09 | Huancavelica | 18 | Moquegua | | |

Lima (15) incluye Lima Metropolitana y Lima Provincias; Callao (07) va aparte.

## Cifras de control (2024)

| Cifra | Con la sumaria (`factor07 × mieperho`), referencia del curso | Con esta base (`facpob07`) |
|---|---|---|
| Pobreza nacional | 27.58 % | 27.53 % |
| Pobreza extrema | 5.5 % | 5.50 % |
| Urbana / rural | 24.8 % / 39.3 % | 24.7 % / 39.4 % |
| Lima Metropolitana (`dominio == 8`) | 28.2 % | 28.0 % |
| Cusco (`departamento == "08"`) | 18.5 % | 18.5 % |

Las diferencias de décimas vienen del factor: la sumaria expande hogares y la base de personas expande personas.
Ambas redondean a la cifra oficial de pobreza nacional (27.6 %).