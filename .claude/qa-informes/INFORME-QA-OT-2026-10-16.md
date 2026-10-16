# QA ot/ — 2026-10-16 — Tareas: links y simplificación

## Entorno y alcance

- Server descartable `qa_server.py --sqlite` en `:8126` (Docker no disponible:
  no se ejercitó Postgres). Login simulado como ADMIN.
- Pantalla: **Tareas** (tabla, drawer de tarea, hoja Duplicar). Escritorio
  1400 px y mobile 375 px.
- Cambios probados: celda Links como hipervínculo y menú con varios vínculos,
  varios vínculos por tarea en el drawer, y la nueva pasada de simplificación
  (botones → ícono, textos explicativos → "?").
- **No probado:** la migración `e8b2f5c1a7d3` contra Postgres; la hoja de
  mail con "Enviar en la misma cadena" en el navegador (el seed no tiene mails
  encadenados — el render lo cubre `test_mail_cadena.py`); tema claro.

## Altos

Ninguno.

## Medios (corregidos)

- Botón de calendario de las fechas en el drawer no hacía nada: el drawer
  corta la propagación de clicks y el listener era de burbuja. Pasó a captura.
- El "?" (`info-tip`) tampoco abría dentro de drawers por la misma razón
  (hasta hoy solo se usaba en Anunciantes, fuera de drawer). Pasó a captura.
- El panel del "?" se ajustaba a la ventana y no al drawer: en mobile quedaba
  cortado a la izquierda. Ahora se ajusta al drawer que lo contiene.

## Bajos

- 404 de un recurso en consola al cargar (no identificado; parece el
  favicon, previo a estos cambios).

## Simplificación

| Pantalla | Elemento actual | Propuesta | Ícono | Riesgo de confusión | Hecho |
|---|---|---|---|---|---|
| Tareas | "Filtros" (ícono + texto en escritorio) | ícono solo | filtros | bajo | aplicado |
| Drawer tarea | "Enviar mail" | ícono solo | sobre | bajo | aplicado |
| Drawer tarea | "Duplicar" | ícono solo | duplicar | bajo | aplicado |
| Drawer tarea | "+ Agregar vínculo" | ícono solo | + | bajo: está bajo "Links" | aplicado |
| Drawer tarea | nota "Se completa en Fase 2…" | "?" junto a "Número de factura" | ? | bajo | aplicado |
| Duplicar | hint "Se abre el formulario con los datos copiados…" | "?" junto a la pregunta | ? | bajo | aplicado |
| Mail | hint "Se manda como respuesta…" | "?" en la fila del checkbox | ? | bajo | aplicado |
| Tareas | "Necesitan revisión 12" / "Vencidas 0 +N por vencer" | ícono + número ("+N" por vencer) | alerta / reloj | medio: el número solo no dice qué cuenta; title y aria-label lo explican | aplicado (OK de Javier) |
| Campo OT | hint "Primera OT de este anunciante…" | "?" | ? | medio: aparece una sola vez y avisa algo que se hace en ese momento | propuesta |

Quedan como están: Guardar y "Nueva OT/tarea" (acción principal), Anular
(destructivo), "Agrupar por OT" (acción del dominio), Cancelar (ya oculto en
mobile), y los avisos de estado ("Asigná una OT arriba…", "sin mail
cargado", "no tiene responsables").

## Lo que funcionó bien

- Link de la celda abre en **pestaña nueva** (`target="_blank"`, confirmado con
  clic real: el navegador intentó abrir drive.google.com en otra pestaña) y
  no abre el drawer.
- Varios vínculos: agregar/quitar filas, guardado uno por línea sin vacíos ni
  repetidos, menú en la tabla sin recortes, mail sugerido con todos.
- Pie del drawer con íconos a la misma altura que Guardar/Anular (39 px
  escritorio, 44 px mobile); sin scroll horizontal a 375 px; 138 tests en verde.
