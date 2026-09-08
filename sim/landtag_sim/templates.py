"""Reine Regex-Textbausteine fuer Ereignis-Meldungen. Kein LLM/NLP.

Platzhalter im Format {key} oder {key:.1f} werden per Regex erkannt und aus
einem Kontext-Dict ersetzt. Fehlt ein Platzhalter im Kontext, wird das
sichtbar im Text markiert statt eine Exception zu werfen -- besser fuer
Balance-Runs, die viele Events automatisiert durchlaufen.
"""
from __future__ import annotations

import re

_PLACEHOLDER_RE = re.compile(r"\{(\w+)(:[^}]+)?\}")


def render_template(template_text: str, context: dict[str, float | str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key, fmt_spec = match.group(1), match.group(2) or ""
        if key not in context:
            return f"[FEHLT:{key}]"
        try:
            return ("{" + fmt_spec + "}").format(context[key]) if fmt_spec else str(context[key])
        except (ValueError, TypeError):
            return str(context[key])

    return _PLACEHOLDER_RE.sub(_replace, template_text)
