"""Regelbasierte Ereignis-Auswertung: einfache Schwellenwert-Vergleiche.

Bewusst kein Ausdrucksparser/Sprachmodell -- ein festes, kleines Set von
Operatoren reicht fuer alle Trigger-Bedingungen und bleibt vollstaendig
deterministisch/testbar.
"""
from __future__ import annotations

import operator as _operator

from landtag_sim.models import EventRule, SimState
from landtag_sim.templates import render_template

_OPERATORS = {
    ">": _operator.gt,
    "<": _operator.lt,
    ">=": _operator.ge,
    "<=": _operator.le,
    "==": _operator.eq,
    "!=": _operator.ne,
}


def _severity(rule: EventRule, value: float) -> float:
    """Wie weit die Statistik den Schwellenwert ueberschreitet, normiert auf den
    Schwellenwert selbst. Nach Game-Director-Review (docs/architecture.md,
    Vorbild Democracy 4s "hoechster Score gewinnt"): mehrere gleichzeitig
    eligible Events sollen nicht alle in derselben Runde feuern, sondern nur
    das dringendste -- sonst wirkt es wie Ereignis-Spam.
    """
    if rule.threshold == 0:
        return abs(value)
    return abs(value - rule.threshold) / abs(rule.threshold)


def evaluate_events(state: SimState, rules: list[EventRule]) -> list[tuple[EventRule, str]]:
    """Gibt alle in dieser Runde ausloesbaren (Regel, gerenderter Text)-Paare
    zurueck, absteigend nach Schweregrad sortiert. Der Aufrufer (engine.py)
    entscheidet, wie viele davon tatsaechlich gefeuert werden -- aktuell nur
    das erste (dringendste), siehe advance_turn.
    """
    triggered: list[tuple[EventRule, str, float]] = []
    for rule in rules:
        cooldown_left = state.event_cooldowns.get(rule.key, 0)
        if cooldown_left > 0:
            continue
        value = state.statistics.get(rule.statistic_key)
        if value is None:
            continue
        compare = _OPERATORS.get(rule.operator)
        if compare is None:
            raise ValueError(f"Unbekannter Operator in Event '{rule.key}': {rule.operator}")
        if compare(value, rule.threshold):
            text = render_template(rule.template_text, {"value": value, "statistic": rule.statistic_key})
            triggered.append((rule, text, _severity(rule, value)))
    triggered.sort(key=lambda item: item[2], reverse=True)
    return [(rule, text) for rule, text, _severity_value in triggered]
