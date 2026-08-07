# Aleste General — punto de entrada

Esta carpeta contenedora agrupa dos proyectos hermanos de ALESTE ADS S.A.
que comparten el mismo repo Git pero tienen perfiles de riesgo y ciclos de
vida distintos. Este archivo es solo de orientación — la sustancia está en
el `CLAUDE.md` de cada subproyecto.

```
informes/   # pipeline Advertys -> informes HTML dinamicos. Solo lectura
            # contra Advertys. Ver informes/CLAUDE.md.
ot/         # app web (FastAPI+Postgres) de tareas/OT del equipo. Va a
            # escribir en Advertys (alta de OT). Ver ot/CLAUDE.md.
.claude/    # skills y agents de Claude Code, compartidos por ambos
            # subproyectos (viven acá, no adentro de informes/ u ot/).
Skills/     # referencia general "skill-builder" (no específica de ningún
            # subproyecto de datos).
```

## Cómo operar

- **Antes de tocar código, identificá de qué subproyecto se trata** y leé
  su `CLAUDE.md`: `informes/CLAUDE.md` para cualquier pedido sobre
  módulos de Advertys (cargar exports, regenerar informes, relevar un
  módulo nuevo); `ot/CLAUDE.md` para cualquier pedido sobre la app de
  tareas/OT.
- **Cada subproyecto es su propia raíz de ejecución.** Los comandos
  Python de `informes/` (`python -m modules.<modulo>.<script>`) se corren
  parado en `informes/`, no acá — `cd informes` primero. Mismo criterio
  para lo que se construya en `ot/`.
- **La salvaguarda de "Advertys es de solo lectura" rige solo para
  `informes/`** (ver `informes/CLAUDE.md`). `ot/` tiene su propia política
  de escritura, documentada en `ot/CLAUDE.md` — no asumas que una regla
  aplica al otro subproyecto sin confirmarlo en su CLAUDE.md.
- Los `workflows/*.md` y el `README.md` del pipeline viven dentro de
  `informes/` (`informes/workflows/`, `informes/README.md`), no acá.

## Historia

Hasta 2026-08-03 este repo era un único proyecto (`informes/` vivía en la
raíz, sin carpeta propia) y `ot/` estaba anidado dentro como
`informes/ot/` (originalmente `informes/OTs/`). Se separaron como
hermanas porque `ot/` va a tener credenciales de escritura reales contra
Advertys (crear la OT de sistema) mientras que `informes/` tiene que
seguir siendo estrictamente de solo lectura — dos perfiles de riesgo que
no debían convivir ambiguamente en el mismo árbol.
