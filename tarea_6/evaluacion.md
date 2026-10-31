# Evaluación de las skills: tres pedidos con y sin skills

**Fecha:** 31 de octubre de 2026 · **Herramienta:** Claude Code v2.1 (Opus 5.5) en VS Code, Windows ·
**Datos:** INEI, ENAHO 2024 (módulos 34 y 02)

## Procedimiento

Cada pedido se formuló dos veces, en sesiones nuevas de Claude Code abiertas desde `tarea_6/`:

- **Con skills:** `claude`
- **Sin skills:** `claude --disallowedTools Skill`

En ambas condiciones se usó el modo conversación en lugar de `claude -p`, con el fin de observar en pantalla qué skill
se activaba y registrar la evidencia mediante capturas. Para cada respuesta se anotó qué skills se activaron, la cifra
obtenida, si se ponderó y cómo resultó la figura.

## Resultados

| # | Pedido | Condición | Skills activadas | Cifra | ¿Ponderó? | Figura |
|---|---|---|---|---|---|---|
| 1 | ¿Cuál fue la pobreza en Cusco en 2024? | Con skills | `limpiando-enaho` | **18.5 %** | Sí, `facpob07` | No aplica |
| 1 | ¿Cuál fue la pobreza en Cusco en 2024? | Sin skills | Ninguna | 18.5 % | No calculó: leyó `figuras/pobreza_departamento.csv` | No aplica |
| 2 | Grafica la pobreza urbana y rural (1.ª prueba) | Con skills | `graficando-enaho` | 24.7 % y 39.4 % | Sí, `facpob07` | Correcta; la cifra urbana rozaba la línea del promedio |
| 2 | Grafica la pobreza urbana y rural (tras la corrección) | Con skills | `graficando-enaho` | **24.7 % y 39.4 %** | Sí, `facpob07` | Correcta, con estilo propio y sin superposiciones |
| 2 | Grafica la pobreza urbana y rural | Sin skills | Ninguna (leyó y ejecutó `graficar.py`) | 24.7 % y 39.4 % | Sí, mediante el script del repositorio | Idéntica a la de la skill |
| 3 | Haz un mapa de la pobreza por departamento | Con skills | `mapeando-enaho` | **Cajamarca 45.0 %, Ica 5.9 %** | Sí, `facpob07` | 25 departamentos con dato, unidos por código |
| 3 | Haz un mapa de la pobreza por departamento | Sin skills | Ninguna (leyó y ejecutó `mapear.py`) | Cajamarca 45.0 %, Ica 5.9 % | Sí, mediante el script del repositorio | Idéntica a la de la skill |

Cifras de referencia del curso: Cusco 18.5 %; urbano 24.8 % y rural 39.3 %; Cajamarca 45.0 % e Ica 6.0 %.

## Análisis

**Activación.** En las tres consultas con skills, Claude Code activó la skill pertinente sin que el pedido la
nombrara, lo que confirma que las `description` contienen las palabras con las que un usuario formula la pregunta
(ENAHO, pobreza, Cusco, graficar, mapa, departamento). `limpiando-enaho` no se encadenó en los pedidos 2 y 3 porque
la base limpia ya existía; en ese caso, las skills de gráficos y mapas indican usarla directamente, de modo que el
comportamiento observado es el previsto.

**Corrección iterativa.** La primera prueba del pedido 2 reveló un defecto en `graficando-enaho/SKILL.md`: la
instrucción `--por $0` recibía como argumento la palabra «pobreza», que el script no admite. Aunque Claude lo
advirtió y recurrió a `--por area`, la instrucción era ambigua. Por consiguiente, se reemplazó por una lista cerrada
de grupos válidos (`area`, `sexo`, `edad`, `departamento`), se separó la etiqueta de la cifra urbana de la línea del
promedio y se añadió una nota sobre la diferencia entre 27.5 % y 27.6 %. En la segunda prueba, la skill se ejecutó
sin advertencias y explicó dicha diferencia por iniciativa propia.

**Diferencias con las referencias.** Las cifras de urbano (24.7 % frente a 24.8 %), rural (39.4 % frente a 39.3 %) e
Ica (5.9 % frente a 6.0 %) difieren en una décima de las del curso. Cabe señalar que no se trata de un error de
limpieza: las referencias se calcularon con la sumaria y el factor `factor07 × mieperho`, mientras que las skills
ponderan la base de personas con `facpob07`, tal como exige la skill de ejemplo del curso («toda cifra va ponderada
con `facpob07`»). En los 25 departamentos, la diferencia máxima es de 0.5 puntos (Puno), y el orden de los tres
departamentos con más y con menos pobreza coincide con la referencia. A nivel nacional, ambos métodos redondean a la
cifra oficial del INEI: 27.58 % y 27.53 %, es decir, 27.6 %.

**La condición sin skills.** Este es el hallazgo más relevante de la evaluación. Prohibir la herramienta `Skill` no
impidió que Claude obtuviera respuestas correctas, pero las obtuvo **apoyándose en el trabajo de las skills**: en el
pedido 1 leyó la cifra de un CSV generado por `graficando-enaho`, y en los pedidos 2 y 3 abrió la carpeta
`.claude/skills/` y ejecutó directamente `graficar.py` y `mapear.py`. En ningún caso limpió la ENAHO por su cuenta.
Desde esta perspectiva, la flag `--disallowedTools Skill` bloquea la carga formal de la skill, pero no el acceso a
los archivos del repositorio. Por ello, la comparación no mide qué haría Claude sin ayuda, sino qué hace en un
repositorio donde las decisiones metodológicas ya están fijadas en scripts. Aun así, el resultado respalda el
argumento central de la sesión: una vez que las llaves, el filtro de residentes, la unión y la ponderación quedan
escritos en un script versionado, la respuesta deja de depender de la improvisación del modelo.

## Limitaciones

1. **Contaminación entre condiciones.** Las pruebas sin skills se ejecutaron en el mismo repositorio, con las salidas
   (`salidas/`, `figuras/`, `mapas/`) y los scripts ya presentes. Una comparación más estricta requeriría un clon sin
   `.claude/skills/` ni salidas previas.
2. **Contexto del editor.** Claude Code estaba conectado a VS Code, que le comunica el nombre del último archivo
   abierto (por ejemplo, `[In limpiar.py]`). Se trata de una pista débil, pero puede orientar la búsqueda.
3. **Precisión departamental.** Las cifras por departamento son estimaciones puntuales sin intervalo de confianza;
   el propio Claude lo advirtió en el pedido 1. Muestras como las de Callao (3,457 encuestados) o Madre de Dios
   (2,045) aconsejan leerlas con cautela.