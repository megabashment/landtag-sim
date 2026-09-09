"""Tests fuer den P2-Punkt 'Dominante-Strategie-Check' im Balance-Runner
(docs/game-design-roadmap.md, Punkt 10). Nutzt synthetische Zeilen statt
echter Simulationslaeufe, damit die Heuristik selbst isoliert geprueft wird
(die Simulationslogik ist bereits in test_engine.py abgedeckt)."""
from landtag_sim.sample_data import SAMPLE_POLICIES
from landtag_sim.tools.balance_runner import all_policy_combinations, find_dominant_policies, run_scenario


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
