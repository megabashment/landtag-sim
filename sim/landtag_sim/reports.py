"""B4 "Narrative Konsequenz-Ebene ('Presseschau')" -- regelbasierte
Auswertung rein textlicher Konsequenz-Meldungen.

Anders als Events/Dilemmas veraendert ein Report KEINE Sim-Statistik und
kostet nichts -- er benennt nur die Kausalkette einer Entwicklung
("Werksschliessung wegen deiner Wirtschaftspolitik"). Vorbild: Democracy 4s
"Media Reports". Regex-Templates + vignettes.py fuer Namen, kein LLM/NLP.

Frequenz-Management (BACKLOG.md L5): der Aufrufer (engine.py::advance_turn)
haengt hoechstens EINEN Report pro Runde an und auch nur, wenn dieselbe
Runde weder ein Event noch ein Dilemma hatte -- Reports treten bewusst
hinter die "echten" Ereignisse zurueck.
"""
from __future__ import annotations

import operator as _operator

from landtag_sim.models import ReportRule, SimState
from landtag_sim.templates import render_template

_OPERATORS = {
    ">": _operator.gt,
    "<": _operator.lt,
    ">=": _operator.ge,
    "<=": _operator.le,
    "==": _operator.eq,
    "!=": _operator.ne,
}


def evaluate_reports(
    state: SimState, rules: list[ReportRule], active_policy_keys: set[str]
) -> list[tuple[ReportRule, str]]:
    """Gibt alle in dieser Runde ausloesbaren (Regel, gerenderter Text)-Paare
    zurueck, deterministisch nach `rule.key` sortiert. Der Aufrufer nimmt
    davon nur das erste (engine.py::advance_turn) -- die Sortierung nach Key
    haelt diese Auswahl reproduzierbar (es gibt fuer Reports keinen
    Schweregrad-Begriff wie bei Events).

    Eine Regel ist ausloesbar, wenn:
    - sie nicht im Cooldown ist,
    - ihr optionales `requires_policy` aktiv und ihr optionales
      `forbids_policy` NICHT aktiv ist,
    - sie mindestens eine Bedingung hat und ALLE Bedingungen erfuellt sind
      (UND-Verknuepfung).
    """
    eligible: list[tuple[ReportRule, str]] = []
    for rule in rules:
        if state.report_cooldowns.get(rule.key, 0) > 0:
            continue
        if rule.requires_policy and rule.requires_policy not in active_policy_keys:
            continue
        if rule.forbids_policy and rule.forbids_policy in active_policy_keys:
            continue
        if not rule.conditions:
            continue
        if all(_condition_met(state, condition) for condition in rule.conditions):
            context: dict[str, float | str] = dict(state.statistics)
            context["turn"] = state.turn
            eligible.append((rule, render_template(rule.template_text, context)))
    eligible.sort(key=lambda pair: pair[0].key)
    return eligible


def _condition_met(state: SimState, condition) -> bool:
    value = state.statistics.get(condition.statistic_key)
    if value is None:
        return False
    compare = _OPERATORS.get(condition.operator)
    if compare is None:
        raise ValueError(
            f"Unbekannter Operator in Report-Bedingung ({condition.statistic_key}): {condition.operator}"
        )
    return compare(value, condition.threshold)
