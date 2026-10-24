# Correcciones al guion

Fuente: `tarea_3/README.md` (Monitor de Incendios y Exposición Territorial — Perú). El borrador del guion se revisó frase por frase contra el README.

| Escena | Borrador | Versión final | Motivo |
|---|---|---|---|
| 1 | «detecciones de calor» | «detecciones térmicas» | Término técnico más preciso (VIIRS, 375 m). Además, se quitó el año de la narración para no pasar de 60 s; el año sigue en pantalla. |
| 2 | «viven unas veintidós mil setecientas personas» | «se estima que 22 729 personas están en zonas situadas a ≤ 1 km» | WorldPop es una estimación modelada con raster y estadísticas zonales, no un conteo de dónde reside cada persona. |
| 3 | — | Sin cambios | Las cifras (166 y 54) coinciden con el README y no afirman ningún daño. |
| 4 | «a 40–45 m de una detección» | «… de una detección térmica registrada el 16 de octubre» | La distancia se mide al centro del píxel, no al borde del fuego; no prueba que el fuego llegó a las escuelas. |
| 5 | «La exposición recae sobre territorios con brechas previas» | «El análisis también revela brechas de servicios básicos» | La BDPI no tiene coordenadas: la brecha es distrital y no demuestra una proximidad directa entre esas viviendas y las detecciones. |
| 6 | «son prioridad alta para una evaluación» | «Según los criterios del análisis, están entre los distritos prioritarios para una evaluación» | La prioridad viene de una regla analítica explícita, no de una evaluación oficial de daños. Además, al revisar la tabla del dashboard se vio que hay **7** distritos con prioridad alta (también Satipo, Raimondi, Sepahua y Vizcatán del Ene): la frase original daba a entender que solo eran tres. |

**Se mantuvo:** el uso de «detecciones» y «exposición potencial» en lugar de «incendios» y «daños». Es una fortaleza metodológica del guion.
