"""B2: Situations-Layer -- regelbasierte Auswertung mit Hysterese.

Ein Zustand (Situation), der bei Statistik-Schwelle X eintritt und erst bei
einer ANDEREN, entgegengesetzten Schwelle Y wieder austritt. Erzeugt selbst-
tragende Spiralen ("Story ohne Text", BACKLOG.md L2/L3).

Anders als Events: Situations sind nicht einmalig, sondern aktiv, solange
ihre Bedingung erfuellt ist. Ihre Effekte wirken wie Policies (exponentiell
geglaettet via _effect_delta mit since_turn).

Beispiel `abwanderung`: activate_op=<, activate_threshold=-0.5 (gdp_growth
faellt unter -0.5), deactivate_op=>, deactivate_threshold=0.5 (erst wieder
raus, wenn gdp_growth > 0.5). Dazwischen bleibt sie aktiv und drueckt
unemployment_rate.
"""
from __future__ import annotations

import operator as _operator

from landtag_sim.models import ActiveSituation, SimState, SituationRule
from landtag_sim.templates import render_template

_OPERATORS = {
    ">": _operator.gt,
    "<": _operator.lt,
    ">=": _operator.ge,
    "<=": _operator.le,
    "==": _operator.eq,
    "!=": _operator.ne,
}


def evaluate_situations(state: SimState, rules: list[SituationRule]) -> tuple[list[ActiveSituation], list[tuple[str, str]]]:
    """Wertet aktive + aktivierbare Situations aus und gibt zwei Dinge zurueck:

    1. Die neue Liste von aktiven Situations (alte, noch aktive + neu
       aktivierte, minus deaktivierte). Wird direkt auf `state.active_situations`
       gespeichert vom Aufrufer (engine.py::advance_turn).
    2. Eine Liste von (rule_key, template_text)-Paaren fuer "Situation activated"-
       Nachrichten ins Frontend (optional).

    Hysterese: eine Situation mit activate_op=<, activate_threshold=-0.5
    und deactivate_op=>, deactivate_threshold=0.5 bleibt aktiv, solange
    die Statistik zwischen -0.5 und 0.5 liegt -- der Bereich "dazwischen"
    ist die Hysterese. Erst wenn sie > 0.5 wird, deaktiviert sie.
    """
    # Aktive Situations am Anfang der Runde
    still_active: list[ActiveSituation] = []
    newly_activated: list[tuple[str, str]] = []

    # 1) Bereits aktive Situations: pruefen, ob sie deaktivieren sollen.
    # Dazu brauchst du die Situation Regel zu ihrer rule_key nachsehen.
    rule_by_key = {rule.key: rule for rule in rules}

    for active in state.active_situations:
        rule = rule_by_key.get(active.rule_key)
        if rule is None:
            # Regel existiert nicht mehr -> Situation automatisch deaktivieren
            continue

        value = state.statistics.get(rule.statistic_key)
        if value is None:
            still_active.append(active)
            continue

        compare_deactivate = _OPERATORS.get(rule.deactivate_op)
        if compare_deactivate is None:
            still_active.append(active)
            continue

        # Deaktivierungs-Bedingung erfuellt -> raus aus der Liste
        if compare_deactivate(value, rule.deactivate_threshold):
            continue  # Nicht in still_active hinzufuegen -> deaktiviert

        # Noch aktiv
        still_active.append(active)

    # 2) Nicht-aktive Situations: pruefen, ob sie aktivieren sollen.
    active_rule_keys = {s.rule_key for s in still_active}

    for rule in rules:
        if rule.key in active_rule_keys:
            continue  # Ist bereits aktiv

        value = state.statistics.get(rule.statistic_key)
        if value is None:
            continue

        compare_activate = _OPERATORS.get(rule.activate_op)
        if compare_activate is None:
            continue

        if compare_activate(value, rule.activate_threshold):
            # Aktivierungs-Bedingung erfuellt
            new_active = ActiveSituation(rule_key=rule.key, since_turn=state.turn)
            still_active.append(new_active)

            # Meldung ins Frontend
            if rule.template_text:
                text = render_template(rule.template_text, {"value": value, "statistic": rule.statistic_key})
                newly_activated.append((rule.key, text))

    return still_active, newly_activated
