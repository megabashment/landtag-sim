"""B3 "Zustandsgekoppelte Risiko-Events" (BACKLOG.md): das probability-Feld
der EventRule/DilemmaRule muss durch die Persistenzschicht (seed.py ->
EventDefinition.trigger_condition-JSON -> sim_bridge.load_event_rules)
unveraendert wieder herauskommen. Die reine Gate-Logik selbst ist in
sim/tests/test_engine.py abgedeckt -- hier geht es nur um den Round-Trip
durch die DB, den die Sim-Tests nicht sehen.
"""
from sqlmodel import Session

from app.db import engine
from app.sim_bridge import load_dilemma_rules, load_event_rules


def test_konjunkturdelle_vorstufe_is_seeded_with_its_probability(client, session_id):
    """session_id triggert run_all_seeds() -> der Event-Katalog ist befuellt."""
    with Session(engine) as db:
        rules = {r.key: r for r in load_event_rules(db)}

    assert "konjunkturdelle" in rules, "B3-Vorstufe fehlt im geseedeten Event-Katalog"
    konjunkturdelle = rules["konjunkturdelle"]
    assert konjunkturdelle.probability == 0.4
    assert konjunkturdelle.statistic_key == "gdp_growth"
    # drueckt das Wachstum weiter Richtung rezession-Schwelle
    assert any(e.statistic_key == "gdp_growth" and e.magnitude < 0 for e in konjunkturdelle.effects)


def test_ordinary_event_rules_round_trip_with_probability_one(client, session_id):
    with Session(engine) as db:
        rules = {r.key: r for r in load_event_rules(db)}

    # Regeln ohne explizite Wahrscheinlichkeit verhalten sich wie vor B3.
    assert rules["hohe_arbeitslosigkeit"].probability == 1.0
    assert rules["niedrige_bildungsausgaben"].probability == 1.0


def test_dilemma_rules_round_trip_with_default_probability(client, session_id):
    with Session(engine) as db:
        rules = load_dilemma_rules(db)

    assert rules, "Dilemma-Katalog wurde nicht geseedet"
    assert all(r.probability == 1.0 for r in rules)
