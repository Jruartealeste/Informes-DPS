"""
PreToolUse (Edit|Write) - refuerzo tecnico de la salvaguarda "Advertys es de
solo lectura" documentada en informes/CLAUDE.md: si un Edit/Write dentro de
informes/ suma una linea que combina una llamada tipo click de Playwright
(.click(, get_by_text, get_by_role, get_by_label, locator() con :has-text)
con una palabra de alta/edicion/borrado (Nuevo, Agregar, Editar, Modificar,
Eliminar, Borrar, Guardar), pide confirmacion explicita en vez de dejarlo
pasar en silencio. No bloquea (permissionDecision "ask", no "deny") porque
ya existen excepciones aprobadas (cerrar_ot.py) que legitimamente clickean
"Guardar"/similares.

No es un chequeo de seguridad exhaustivo (mira new_string/content linea por
linea, no el archivo completo ni el diff real) - es una alarma barata para
que el agente no lo pase por alto, no un firewall.
"""
import json
import re
import sys

DANGEROUS_WORDS = (
    "nuev", "agregar", "editar", "modificar", "eliminar", "borrar", "guardar",
)
CLICK_TOKENS = (
    ".click(", "get_by_text", "get_by_role", "get_by_label", "locator(",
)


def allow():
    sys.exit(0)


def ask(reason: str):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        allow()

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        allow()

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "").replace("\\", "/")
    if "/informes/" not in file_path and not file_path.startswith("informes/"):
        allow()
    if not file_path.endswith(".py"):
        allow()

    content = tool_input.get("content") or tool_input.get("new_string") or ""

    for line in content.splitlines():
        low = line.lower()
        has_click = any(tok in low for tok in CLICK_TOKENS)
        has_word = any(w in low for w in DANGEROUS_WORDS)
        if has_click and has_word:
            ask(
                "Esta linea combina un click de Playwright con una palabra de "
                "alta/edicion/borrado (Nuevo/Agregar/Editar/Modificar/"
                "Eliminar/Borrar/Guardar) en un archivo de informes/, que "
                "debe seguir siendo de solo lectura contra Advertys "
                "(informes/CLAUDE.md, seccion 'Salvaguarda'). Confirmar con "
                "Javier antes de ejecutar este click: "
                f"{line.strip()[:200]}"
            )

    allow()


if __name__ == "__main__":
    main()
