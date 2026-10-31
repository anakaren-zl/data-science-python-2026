# Evaluación de las skills mediante tres pedidos con y sin skills

## Diseño de la prueba

La evaluación se realizó el 31 de octubre de 2026 con Claude Code v2.1 (Opus 5.5), ejecutado desde Visual Studio Code
en Windows, sobre la ENAHO 2024 del INEI (módulos 34 y 02). En términos metodológicos, cada pedido se formuló dos
veces y en sesiones nuevas de Claude Code abiertas desde la carpeta `tarea_6/`. En la primera condición, el programa
se inició con el comando `claude`, de modo que las skills estaban disponibles. En la segunda, se inició con
`claude --disallowedTools Skill`, lo que impide la carga formal de cualquier skill.

Cabe señalar que ambas condiciones se ejecutaron en modo conversación y no mediante `claude -p`. Esta decisión
responde a la necesidad de observar en pantalla qué skill se activaba en cada caso y de registrar la evidencia por
medio de capturas. Para cada respuesta se registraron cuatro aspectos, a saber, las skills activadas, la cifra
obtenida, el uso del factor de expansión y las características de la figura producida.

## Resultados

| N.° | Pedido | Condición | Skills activadas | Cifra | Ponderación | Figura |
|---|---|---|---|---|---|---|
| 1 | ¿Cuál fue la pobreza en Cusco en 2024? | Con skills | `limpiando-enaho` | **18.5 %** | Sí, con `facpob07` | No corresponde |
| 1 | ¿Cuál fue la pobreza en Cusco en 2024? | Sin skills | Ninguna | 18.5 % | No calculó la cifra, sino que la leyó de `figuras/pobreza_departamento.csv` | No corresponde |
| 2 | Grafica la pobreza urbana y rural (primera prueba) | Con skills | `graficando-enaho` | 24.7 % y 39.4 % | Sí, con `facpob07` | Correcta, aunque la cifra urbana rozaba la línea del promedio |
| 2 | Grafica la pobreza urbana y rural (tras la corrección) | Con skills | `graficando-enaho` | **24.7 % y 39.4 %** | Sí, con `facpob07` | Correcta, con estilo propio y sin superposiciones |
| 2 | Grafica la pobreza urbana y rural | Sin skills | Ninguna, aunque leyó y ejecutó `graficar.py` | 24.7 % y 39.4 % | Sí, a través del script del repositorio | Idéntica a la producida por la skill |
| 3 | Haz un mapa de la pobreza por departamento | Con skills | `mapeando-enaho` | **Cajamarca 45.0 %, Ica 5.9 %** | Sí, con `facpob07` | 25 departamentos con dato, unidos por código |
| 3 | Haz un mapa de la pobreza por departamento | Sin skills | Ninguna, aunque leyó y ejecutó `mapear.py` | Cajamarca 45.0 %, Ica 5.9 % | Sí, a través del script del repositorio | Idéntica a la producida por la skill |

Las cifras de referencia del curso son 18.5 % para Cusco, 24.8 % para el área urbana, 39.3 % para el área rural,
45.0 % para Cajamarca y 6.0 % para Ica.

## Análisis

### Activación de las skills

En las tres consultas realizadas con skills, Claude Code activó la skill pertinente sin que el pedido la nombrara.
Este resultado indica que las descripciones de cada skill recogen los términos con los que un usuario formularía la
pregunta, tales como ENAHO, pobreza, Cusco, graficar, mapa o departamento. Por otra parte, la skill
`limpiando-enaho` no se encadenó en los pedidos 2 y 3, dado que la base limpia ya existía. En tal circunstancia, las
skills de gráficos y de mapas indican utilizar directamente dicha base, por lo que el comportamiento observado
coincide con el previsto.

### Corrección iterativa

La primera prueba del pedido 2 permitió identificar un defecto en `graficando-enaho/SKILL.md`. La instrucción
`--por $0` recibía como argumento la palabra «pobreza», que el script no admite. Aunque Claude advirtió el problema y
recurrió por su cuenta a `--por area`, la instrucción resultaba ambigua. Por consiguiente, se reemplazó por una lista
cerrada de valores válidos (`area`, `sexo`, `edad` y `departamento`), se separó la etiqueta de la cifra urbana de la
línea del promedio nacional y se incorporó una nota sobre la diferencia entre 27.5 % y 27.6 %. En la segunda prueba,
la skill se ejecutó sin advertencias y explicó dicha diferencia por iniciativa propia, lo que confirma la eficacia de
la corrección.

### Diferencias respecto de las cifras de referencia

Las cifras correspondientes al área urbana (24.7 % frente a 24.8 %), al área rural (39.4 % frente a 39.3 %) y a Ica
(5.9 % frente a 6.0 %) difieren en una décima de las publicadas por el curso. Cabe precisar que estas diferencias no
obedecen a un error de limpieza. En efecto, las referencias se calcularon a partir de la sumaria con el factor
`factor07 × mieperho`, mientras que las skills ponderan la base de personas con `facpob07`, tal como lo exige la
skill de ejemplo presentada en la sesión. En el conjunto de los 25 departamentos, la diferencia máxima asciende a
0.5 puntos porcentuales (Puno), y el orden de los tres departamentos con mayor y menor pobreza coincide plenamente
con la referencia. En concordancia con lo anterior, a nivel nacional ambos procedimientos convergen en la cifra
oficial del INEI, pues 27.58 % y 27.53 % redondean a 27.6 %.

### Comportamiento en ausencia de skills

El hallazgo más relevante de la evaluación se refiere a la condición sin skills. La restricción de la herramienta
`Skill` no impidió que Claude obtuviera respuestas correctas, pero estas se apoyaron en el trabajo previamente
realizado por las skills. En el pedido 1, Claude leyó la cifra de un archivo CSV generado por `graficando-enaho`,
mientras que en los pedidos 2 y 3 abrió la carpeta `.claude/skills/` y ejecutó directamente `graficar.py` y
`mapear.py`. En ningún caso limpió la ENAHO por su cuenta.

Desde esta perspectiva, la opción `--disallowedTools Skill` bloquea la carga formal de la skill, pero no el acceso a
los archivos del repositorio. Por ello, la comparación no mide lo que Claude haría sin ayuda alguna, sino su
comportamiento en un repositorio donde las decisiones metodológicas ya se encuentran fijadas en scripts. Aun así, el
resultado respalda el argumento central de la sesión. Una vez que las llaves, el filtro de residentes, la unión y la
ponderación quedan escritos en un script versionado, la respuesta deja de depender de la improvisación del modelo y
se vuelve reproducible para cualquier persona que trabaje con el repositorio.

## Limitaciones

En primer lugar, existe una contaminación entre condiciones, puesto que las pruebas sin skills se ejecutaron en el
mismo repositorio y con las salidas (`salidas/`, `figuras/` y `mapas/`) y los scripts ya presentes. Una comparación
más estricta requeriría un clon del repositorio sin la carpeta `.claude/skills/` ni salidas previas.

En segundo lugar, Claude Code se encontraba conectado a Visual Studio Code, entorno que le comunica el nombre del
último archivo abierto, como ocurrió con `limpiar.py`. Si bien se trata de una pista débil, podría orientar la
búsqueda del modelo.

Finalmente, las cifras departamentales constituyen estimaciones puntuales sin intervalo de confianza, aspecto que el
propio Claude advirtió en el pedido 1. De manera complementaria, el tamaño de algunas muestras, como las de Callao
(3,457 encuestados) o Madre de Dios (2,045), aconseja interpretar dichas cifras con cautela.