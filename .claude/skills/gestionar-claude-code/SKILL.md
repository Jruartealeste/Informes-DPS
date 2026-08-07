---
name: gestionar-claude-code
description: Use when Javier pide agregar/ajustar un skill, subagent, o la configuración de Claude Code de este proyecto (no un módulo de datos de Advertys). Ej: "agreguemos un subagent para X", "convertí esto en un skill", "revisemos cómo está armado esto para Claude Code".
argument-hint: [descripción de lo que se quiere agregar/ajustar]
---

## Qué hace

Aplica la regla de decisión de este proyecto para extender su propia
configuración de Claude Code (skill nuevo, subagent nuevo, o ninguno de
los dos). Fuente de verdad completa:
[workflows/arquitectura_claude_code.md](../../../informes/workflows/arquitectura_claude_code.md)
— si algo acá y el workflow difieren, gana el workflow (releerlo).

## Regla de decisión (resumen)

1. **¿Es un pedido recurrente con una receta ya estable?** → Skill nuevo,
   mismo molde que los 4 existentes (`actualizar-informe`,
   `refresh-dashboard`, `relevar-modulo`, `verificar-visual`): frontmatter
   `name`/`description`/`argument-hint`, cuerpo corto que remite a un
   workflow en `workflows/` como fuente de verdad completa.
2. **¿Es un paso con output voluminoso (capturas, logs largos) que NO
   necesita `AskUserQuestion` ni ida-y-vuelta con Javier a mitad de
   camino?** → Subagent nuevo (`.claude/agents/<nombre>.md`), con `tools`
   restringido a lo mínimo necesario (preferir solo lectura si el paso es
   de diagnóstico, no de corrección).
3. **¿Necesita confirmaciones de negocio/contables en vivo, o es un caso
   aislado que no se va a repetir?** → No crear nada nuevo. Resolverlo
   inline en la conversación principal.
4. **Nunca proponer un Agent Team** para este proyecto — decisión ya
   tomada y documentada en el workflow (pipeline de un solo desarrollador,
   mayormente secuencial). Re-evaluar solo si cambia algo estructural
   (más de una persona tocando el pipeline a la vez).

## Notas

- No reescribir los skills/workflows existentes al pasar por acá — ya
  siguen el patrón correcto. Sumar, no refactorizar, salvo que Javier pida
  explícitamente lo contrario.
- Mismo criterio YAGNI que ya usa el proyecto en
  `workflows/relevar_modulo_nuevo.md`: no crear una abstracción (skill o
  subagent) "por las dudas" para un pedido que todavía no se repitió.