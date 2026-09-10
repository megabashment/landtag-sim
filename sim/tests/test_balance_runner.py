"""Tests fuer den P2-Punkt 'Dominante-Strategie-Check' im Balance-Runner
(docs/game-design-roadmap.md, Punkt 10). Nutzt synthetische Zeilen statt
echter Simulationslaeufe, damit die Heuristik selbst isoliert geprueft wird
(die Simulationslogik ist bereits in test_engine.py abgedeckt)."""
from landtag_sim.models import (
    DilemmaOption,
    DilemmaRule,
    EventRule,
    PolicyEffect,
    SituationRule,
)
from landtag_sim.sample_data import SAMPLE_POLICIES
from landtag_sim.tools.balance_runner import (
    all_policy_combinations,
    classify_triggers,
    collect_trigger_counts,
    find_dominant_policies,
    run_scenario,
)


def _row(policy_keys: tuple[str, ...], end_satisfaction: float, flags: str = "-") -> dict:
    return {
        "policies": "+".join(policy_keys) or "(keine)",
        "policy_keys": policy_keys,
        "min_budget": 100.0,
        "end_satisfaction": end_satisfaction,
        "satisfaction_swing": 10.0,
        "events_fired": 0,
        "dilemmas_fired": 0,
        "election": "-",
        "flags": flags,
    }


def test_policy_present_in_every_top_scenario_is_flagged_dominant():
    rows = [
        _row((), 40.0),
        _row(("a",), 60.0),
        _row(("a", "b"), 90.0),
        _row(("a", "c"), 80.0),
    ]
    dominant_keys = [key for key, _share in find_dominant_policies(rows, ["a", "b", "c"], top_fraction=0.5)]
    # Top 2 (nach end_satisfaction): a+b (90) und a+c (80) -- "a" steckt in beiden.
    assert dominant_keys == ["a"]


def test_policy_missing_from_some_top_scenarios_is_not_flagged():
    rows = [
        _row(("a",), 90.0),
        _row(("b",), 85.0),
        _row((), 10.0),
    ]
    dominant = find_dominant_policies(rows, ["a", "b"], top_fraction=1.0)
    assert dominant == []


def test_infeasible_and_frozen_scenarios_are_excluded_from_the_check():
    rows = [
        _row(("a",), 90.0),
        _row(("a", "b"), None, flags="NICHT_MACHBAR(Capital 20.0>10.0)"),
        _row((), 50.0, flags="ZUFRIEDENHEIT_EINGEFROREN"),
    ]
    # Nur die erste Zeile zaehlt als 'erfolgreich' -> "a" ist dort dominant.
    dominant_keys = [key for key, _share in find_dominant_policies(rows, ["a", "b"], top_fraction=1.0)]
    assert dominant_keys == ["a"]


def test_no_successful_scenarios_returns_empty_list():
    rows = [_row(("a",), None, flags="NICHT_MACHBAR(Capital 5.0>1.0)")]
    assert find_dominant_policies(rows, ["a"]) == []


def test_returned_shares_are_sorted_descending():
    rows = [
        _row(("a", "b"), 90.0),
        _row(("a",), 80.0),
        _row(("b",), 10.0),
    ]
    dominant = find_dominant_policies(rows, ["a", "b"], top_fraction=1.0, threshold=0.0)
    shares = [share for _key, share in dominant]
    assert shares == sorted(shares, reverse=True)


def test_no_dominant_policy_among_current_sample_policies():
    """Integrations-Regressionstest (echte Simulationslaeufe, kein
    synthetisches Fixture): haelt den aktuellen Balance-Zustand der
    SAMPLE_POLICIES fest. bildungsoffensive wurde urspruenglich als 100%
    dominant markiert (zu schwacher Netto-Trade-off UND strukturelle
    Ueberrepraesentation, weil steuersenkung_mittelstand sie voraussetzt);
    behoben durch einen staerkeren gdp_growth-Trade-off und eine vierte,
    unabhaengige Policy (gesundheitsreform), die den Kombinationsraum
    vergroessert (siehe sample_data.py). Schlaegt fehl, falls ein
    kuenftiger Merge eine neue Free-Lunch- oder strukturell dominante
    Policy einfuehrt, ohne dass es auffaellt."""
    rows = [run_scenario(combo, turns=30) for combo in all_policy_combinations()]
    dominant = find_dominant_policies(rows, [p.key for p in SAMPLE_POLICIES])
    assert dominant == [], f"Unerwartet dominante Policies: {dominant}"


# --- B6: Dilemma-/Event-Trigger-Telemetrie -------------------------------


def test_classify_triggers_flags_never_triggered_rules():
    counts = {"nie": 0, "manchmal": 4, "oft": 20}
    rows, _expected = classify_triggers(counts, turns_simulated=100)
    by_key = {r["key"]: r for r in rows}
    assert by_key["nie"]["flag"] == "NIE_AUSGELOEST"
    assert by_key["manchmal"]["flag"] == "-"


def test_classify_triggers_flags_overrepresented_rules():
    # 1 Dauer-Trigger + 6 nie-Trigger -> Erwartungswert 30/7 ~= 4.3,
    # der Dauer-Trigger (30) liegt weit ueber 5x davon.
    counts = {"dauer": 30, "a": 0, "b": 0, "c": 0, "d": 0, "e": 0, "f": 0}
    rows, expected = classify_triggers(counts, turns_simulated=30)
    by_key = {r["key"]: r for r in rows}
    assert 30 > 5 * expected
    assert by_key["dauer"]["flag"] == "UEBERREPRAESENTIERT"
    assert by_key["a"]["flag"] == "NIE_AUSGELOEST"


def test_classify_triggers_computes_share_and_sorts_descending():
    counts = {"a": 2, "b": 8}
    rows, _expected = classify_triggers(counts, turns_simulated=40)
    assert [r["key"] for r in rows] == ["b", "a"]  # absteigend nach count
    assert rows[0]["share"] == 8 / 40


def test_collect_trigger_counts_separates_reachable_from_unreachable_events():
    """Synthetischer Lauf (kein Policy-Katalog): eine nie erreichbare Regel
    landet bei 0 Ausloesungen, eine dauernd erfuellte feuert jede Runde
    (dank exaktem triggered_event_keys-Feld auch bei cooldown_turns=1)."""
    never = EventRule(
        key="nie_erreichbar",
        statistic_key="unemployment_rate",
        operator=">",
        threshold=10_000.0,
        template_text="unmoeglich",
        cooldown_turns=1,
    )
    always = EventRule(
        key="immer_erreichbar",
        statistic_key="unemployment_rate",
        operator=">",
        threshold=0.0,  # unemployment startet ~6 -> immer erfuellt
        template_text="immer",
        cooldown_turns=1,
    )
    counts = collect_trigger_counts(
        turns=5,
        seeds=1,
        policies=[],
        event_rules=[never, always],
        dilemma_rules=[],
        situation_rules=[],
        report_rules=[],
        combos=[()],
    )
    assert counts["turns_simulated"] == 5
    assert counts["event"]["nie_erreichbar"] == 0
    assert counts["event"]["immer_erreichbar"] == 5


def test_collect_trigger_counts_tracks_dilemmas_and_situations():
    dilemma = DilemmaRule(
        key="test_dilemma",
        statistic_key="unemployment_rate",
        operator=">",
        threshold=0.0,
        prompt_text="?",
        options=[DilemmaOption(key="a", label="A"), DilemmaOption(key="b", label="B")],
        cooldown_turns=1,
    )
    situation = SituationRule(
        key="test_situation",
        statistic_key="unemployment_rate",
        activate_op=">",
        activate_threshold=0.0,  # sofort aktiv
        deactivate_op="<",
        deactivate_threshold=-1.0,  # bleibt aktiv
        effects=[],
    )
    counts = collect_trigger_counts(
        turns=4,
        seeds=1,
        policies=[],
        event_rules=[],
        dilemma_rules=[dilemma],
        situation_rules=[situation],
        report_rules=[],
        combos=[()],
    )
    # Dilemma feuert (mind. einmal), Situation aktiviert sich genau einmal
    # (danach dauerhaft aktiv -> kein erneutes "neu aktiviert").
    assert counts["dilemma"]["test_dilemma"] >= 1
    assert counts["situation"]["test_situation"] == 1


def test_run_scenario_marks_unlock_gated_policy_as_infeasible_at_turn_zero():
    """B7: der Combo-Runner enact-et in Runde 0 -- eine erst spaeter
    freischaltbare Policy (unlock_conditions bei Spielstart nicht erfuellt)
    muss als NICHT_MACHBAR(gesperrt) gemeldet werden statt den Lauf zu
    sprengen."""
    row = run_scenario(("digitalpakt_schulen",), turns=5)
    assert "NICHT_MACHBAR(gesperrt" in row["flags"]


def test_unlock_gated_policies_are_excluded_from_combinations():
    """B7: `all_policy_combinations` laesst Policies mit unlock_conditions weg
    (nicht turn-0-enactbar) -- keine gesperrt-Rauschzeilen im Combo-Lauf."""
    locked = {"digitalpakt_schulen", "gruener_wasserstoff", "arbeitsmarkt_sofortprogramm"}
    keys_in_combos = {k for combo in all_policy_combinations() for k in combo}
    assert not (keys_in_combos & locked)


def test_every_sample_rule_is_organically_reachable():
    """B12 "Content-Ausbau" (BACKLOG.md, L4): nach dem Ausbau soll KEINE
    Event-/Dilemma-/Situations-Regel mehr toter Inhalt sein. Frueher waren
    `niedrige_bildungsausgaben` und `gruenes_wachstum` dauerhaft bei 0
    (siehe Git-Historie) -- jetzt triggert ueber die Rezession-Achse
    (`abwanderung` wirkt breit auf co2/healthcare/education/unemployment)
    jede Regel mindestens einmal im Szenarien-x-Seeds-Sweep. Schlaegt der
    Test fehl, ist neuer Content nicht erreichbar -> Schwellen/Effekte
    nachziehen, nicht den Test aufweichen."""
    counts = collect_trigger_counts(turns=32, seeds=5)
    never = {
        f"{kind}:{key}"
        for kind in ("event", "dilemma", "situation")
        for key, n in counts[kind].items()
        if n == 0
    }
    assert not never, f"nicht erreichbare Regeln (toter Content): {sorted(never)}"
