"""Tests fuer die Dilemma-Events end-to-end durch die echte API (nicht nur
die reine Sim-Engine, die schon in sim/tests/test_engine.py::
test_pflegeausbau_dilemma_is_reachable_via_sample_policies abgedeckt ist).
Deckt das P1-Kernstueck ab: ein ausgeloestes Dilemma MUSS /advance hart
blockieren, bis POST /resolve-dilemma aufgerufen wurde.

WICHTIG: echte Sessions (POST /sessions) starten mit
`jittered_starting_statistics()` OHNE festen Seed (siehe app/api/
routes_game.py::create_session) -- anders als sim/tests/test_engine.py,
das bewusst die unrandomisierte build_initial_state() nutzt. Welches
Dilemma zuerst feuert (z.B. `rezession` statt `pflegeausbau`, wenn der
gejitterte gdp_growth-Startwert zufaellig schon niedrig genug ist), ist
daher NICHT deterministisch vorhersagbar. Diese Tests pruefen deshalb den
Mechanismus (blockiert/entsperrt), nicht welches konkrete Dilemma feuert."""

# B12: aus dem Regelsatz abgeleitet statt hart codiert -- der Content-Ausbau
# fuegt laufend Dilemmas hinzu, und welches bei gejittertem Start zuerst
# feuert ist ohnehin nicht deterministisch (siehe Modul-Docstring).
from landtag_sim.sample_data import SAMPLE_DILEMMA_RULES

_KNOWN_DILEMMA_KEYS = {r.key for r in SAMPLE_DILEMMA_RULES}


def _advance_until_dilemma(client, session_id, enact_first_turn, max_turns=40):
    response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": enact_first_turn})
    assert response.status_code == 200
    for _ in range(max_turns):
        if response.json()["pending_dilemma"] is not None:
            return response
        response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})
        assert response.status_code == 200
    return response


def test_gesundheitsreform_organically_triggers_a_dilemma_and_blocks_advance(client, session_id):
    """Organische Erreichbarkeit von pflegeausbau ueber gesundheitsreform
    bereits mit unrandomisierten Startwerten in sim/tests/test_engine.py
    verifiziert (siehe mistakes.md) -- hier zusaetzlich end-to-end durch die
    echte API inkl. Persistenz/Cooldowns (sim_bridge.py), die die reinen
    Sim-Tests nicht abdecken. Wegen des Start-Jitters (siehe Modul-Docstring)
    wird hier nur geprueft, DASS ein bekanntes Dilemma feuert, nicht welches."""
    response = _advance_until_dilemma(client, session_id, ["gesundheitsreform"])
    pending = response.json()["pending_dilemma"]
    assert pending is not None
    assert pending["rule_key"] in _KNOWN_DILEMMA_KEYS
    assert len(pending["options"]) == 2

    blocked = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})
    assert blocked.status_code == 400


def test_resolve_dilemma_unblocks_advance_and_does_not_count_a_turn(client, session_id):
    response = _advance_until_dilemma(client, session_id, ["gesundheitsreform"])
    pending = response.json()["pending_dilemma"]
    turn_before_resolve = response.json()["state"]["turn"]
    chosen_option = pending["options"][0]["key"]

    resolved = client.post(f"/sessions/{session_id}/resolve-dilemma", json={"option_key": chosen_option})
    assert resolved.status_code == 200
    assert resolved.json()["state"]["pending_dilemma"] is None
    # resolve_dilemma() zaehlt bewusst KEINE eigene Runde (siehe engine.py-
    # Docstring und routes_game.py::resolve_session_dilemma).
    assert resolved.json()["state"]["turn"] == turn_before_resolve

    unblocked = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})
    assert unblocked.status_code == 200


def test_resolve_dilemma_with_unknown_option_key_returns_400(client, session_id):
    _advance_until_dilemma(client, session_id, ["gesundheitsreform"])
    response = client.post(f"/sessions/{session_id}/resolve-dilemma", json={"option_key": "nicht_vorhanden"})
    assert response.status_code == 400


def test_resolve_dilemma_without_pending_dilemma_returns_400(client, session_id):
    response = client.post(f"/sessions/{session_id}/resolve-dilemma", json={"option_key": "irgendwas"})
    assert response.status_code == 400
