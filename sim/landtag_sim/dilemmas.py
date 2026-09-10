"""Regelbasierte Dilemma-Auswertung -- gleicher Trigger-Mechanismus wie
events.py (Schwellenwert-Vergleich, Schweregrad-Priorisierung, Cooldown),
aber das Ergebnis ist keine feste Wirkung, sondern ein `PendingDilemma`
mit mehreren Optionen (siehe models.py::DilemmaRule/DilemmaOption). Der
Spieler entscheidet aktiv, welcher Effekt-Satz angewendet wird --
regelbasiert und deterministisch, kein LLM/NLP.
"""
from __future__ import annotations

import operator as _operator

from landtag_sim.events import passes_probability_gate
from landtag_sim.models import DilemmaRule, PendingDilemma, SimState
from landtag_sim.templates import render_template

_OPERATORS = {
    ">": _operator.gt,
    "<": _operator.lt,
    ">=": _operator.ge,
    "<=": _operator.le,
    "==": _operator.eq,
    "!=": _operator.ne,
}


def _severity(rule: DilemmaRule, value: float) -> float:
    if rule.threshold == 0:
        return abs(value)
    return abs(value - rule.threshold) / abs(rule.threshold)


def evaluate_dilemmas(state: SimState, rules: list[DilemmaRule]) -> list[PendingDilemma]:
    """Gibt alle in dieser Runde ausloesbaren Dilemmas zurueck, absteigend
    nach Schweregrad sortiert. Der Aufrufer (engine.py) feuert wie bei
    Events nur das dringendste pro Runde -- ein zweites gleichzeitiges
    Dilemma waere ohnehin nicht sinnvoll bedienbar, solange eines offen ist.
    """
    triggered: list[tuple[PendingDilemma, float]] = []
    for rule in rules:
        cooldown_left = state.dilemma_cooldowns.get(rule.key, 0)
        if cooldown_left > 0:
            continue
        value = state.statistics.get(rule.statistic_key)
        if value is None:
            continue
        compare = _OPERATORS.get(rule.operator)
        if compare is None:
            raise ValueError(f"Unbekannter Operator in Dilemma '{rule.key}': {rule.operator}")
        if compare(value, rule.threshold):
            if not passes_probability_gate(rule.key, state.turn, rule.probability):
                continue  # B3: Schwelle erfuellt, aber der Wuerfel dieser Runde nicht
            prompt = render_template(rule.prompt_text, {"value": value, "statistic": rule.statistic_key})
            triggered.append(
                (PendingDilemma(rule_key=rule.key, prompt=prompt, options=rule.options), _severity(rule, value))
            )
    triggered.sort(key=lambda item: item[1], reverse=True)
    return [pending for pending, _severity_value in triggered]
