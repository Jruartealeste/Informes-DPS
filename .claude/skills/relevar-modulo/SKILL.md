---
name: relevar-modulo
description: Use when Javier pide un informe de una sección de Advertys que todavía no existe como módulo (no aparece en la tabla de "Módulos armados" del README) — armar un pipeline nuevo desde cero. Ej: "necesito un informe de [sección de Advertys]", "sumá un módulo para X".
argument-hint: [nombre-del-modulo-nuevo]
---

## Qué hace

Arma el pipeline completo (`config.py`, `ingest.py`,
`generate_html_report.py`, `explore.py`) para relevar una sección de
Advertys que todavía no tiene informe. Receta validada 3/3 veces (Órdenes
de Trabajo, Compras, Facturas). Fuente de verdad completa:
[workflows/relevar_modulo_nuevo.md](../../../informes/workflows/relevar_modulo_nuevo.md).

## Salvaguarda — Advertys es de solo lectura

Este skill hace Playwright en vivo contra Advertys. Login, navegación y
exportación a Excel están permitidos sin pedir autorización. Pero si
**cualquier** click en `explore.py` apunta a un elemento cuyo texto,
título o `id` sugiera alta, edición o borrado ("Nuevo", "Agregar",
"Editar", "Modificar", "Eliminar", "Borrar", "Guardar" fuera de un filtro
de vista) — **parar y pedir aprobación explícita a Javier antes de
ejecutar ese click**. No se asume, no se prueba "para ver qué hace".

## Pasos

1. Elegir un `explore.py` existente como punto de partida (Compras o
   Facturas son los más recientes) y adaptarlo: login con `.env`, navegar
   hasta la vista real de `$0`, probar el export a Excel.
   - Si hay nodos de menú repetidos en el árbol, navegar por **ID exacto
     del nodo**, no por texto — confirmar con `page.screenshot()` que el
     click llegó a la vista correcta antes de seguir.
2. Revisar el widget de filtro de la vista y ponerlo en su opción más
   amplia antes de exportar. No asumir "Abierta/Todas" — cada vista puede
   variar (Facturas, por ejemplo, tiene un combo "Filtro" cuyo default
   trae casi nada).
3. Inspeccionar el Excel exportado: columnas, nulos, duplicados, candidata
   a clave única (puede ser compuesta — pasó en Compras y Facturas). Ojo
   "N°" vs "Nº": revisar el byte UTF-8 exacto si un mapeo nuevo tira
   `KeyError`.
4. **Confirmar con Javier** cualquier ambigüedad de negocio/contable antes
   de mapear columnas — no asumir (ejemplo real: Compras tiene dos
   columnas literales "Importe s/IVA", una siempre positiva y otra con
   signo contable).
5. Armar `modules/$0/{config.py, ingest.py, generate_html_report.py}`
   reusando `common.normalizar_fecha`/`normalizar_numero` y
   `db.get_connection()` de la raíz. Mismo patrón que los módulos
   existentes — no crear una abstracción genérica multi-módulo (ver nota
   abajo).
6. Generar el HTML e invocar el skill `verificar-visual` antes de dar el
   módulo por terminado.
7. Registrar el módulo en la lista `MODULOS` de `generate_dashboard.py`
   — `(id, label, config.REPORT_HTML_OUTPUT_PATH)`, tomando el path desde
   el `config.py` del módulo nuevo, no escrito a mano — y correr
   `python generate_dashboard.py`.
8. Documentar en README.md: sumar el módulo a la tabla de "Módulos
   armados" + una sección de notas propias si hubo gotchas, para que el
   próximo módulo no repita la misma exploración a ciegas.

## Notas

- Comandos parados en `informes/` (la raíz del pipeline, no la raíz del
  repo — que también contiene `ot/`): `cd informes` primero si la sesión
  arrancó en la raíz del repo.
- No construir un framework genérico multi-módulo — duplicar el patrón
  simple por módulo es la decisión ya tomada (ver workflow), reevaluar
  solo si esto crece a 4-5 módulos.
- Este skill necesita idas y vueltas con Javier (confirmaciones de
  negocio, revisar screenshots de exploración) — no es fire-and-forget,
  no asumir que se puede correr de punta a punta sin pausas.
