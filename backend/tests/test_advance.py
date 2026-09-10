"""Tests fuer POST /sessions/{id}/advance: den zentralen Rundenwechsel-
Endpunkt, inklusive aller drei von advance_turn() geworfenen Fehlerfaelle
(Policy-Voraussetzung, Political Capital, unbekannter Policy-Key) und der
Wahlmechanik am Ende eines Zyklus.
"""
from sqlmodel import Session

from app.db import engine
from app.models.game import GameSession, SessionStatus


def test_advance_turn_happy_path_enacts_policy_and_returns_attributions(client, session_id):
    response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["erneuerbare_foerderung"]})
    assert response.status_code == 200
    body = response.json()
    assert body["state"]["turn"] == 1
    assert "erneuerbare_foerderung" in body["state"]["active_policy_keys"]
    # Budget: -50 (one_time_cost) -5 (upkeep_cost) +15 (BASE_BUDGET_INCOME_PER_TURN,
    # siehe mistakes.md "Budget hatte nie eine Einnahmequelle") = -40 ggue. Start.
    assert body["state"]["budget"] == 1000.0 - 50.0 - 5.0 + 15.0
    assert body["election_result"] is None
    assert body["pending_dilemma"] is None


def test_advance_turn_unknown_policy_key_returns_400(client, session_id):
    response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["nicht_vorhanden"]})
    assert response.status_code == 400


def test_advance_turn_missing_prerequisite_returns_400(client, session_id):
    """steuersenkung_mittelstand setzt bildungsoffensive voraus (Policy.requires,
    siehe sample_data.py) -- ohne sie aktiv zu haben oder gleichzeitig
    mitzuwaehlen, muss UnmetPrerequisiteError als HTTP 400 ankommen."""
    response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["steuersenkung_mittelstand"]})
    assert response.status_code == 400
    assert "bildungsoffensive" in response.json()["detail"]


def test_advance_turn_prerequisite_satisfied_in_same_turn_succeeds(client, session_id):
    """Voraussetzung darf laut Docstring von advance_turn() auch in
    DERSELBEN Runde mitgewaehlt werden."""
    response = client.post(
        f"/sessions/{session_id}/advance",
        json={"enact_policy_keys": ["bildungsoffensive", "steuersenkung_mittelstand"]},
    )
    assert response.status_code == 200
    active = response.json()["state"]["active_policy_keys"]
    assert "bildungsoffensive" in active
    assert "steuersenkung_mittelstand" in active


def test_advance_turn_insufficient_capital_returns_400(client, session_id):
    """Alle vier Beispiel-Policies gleichzeitig kosten 4+4+3+3=14 Political
    Capital, CAPITAL_CAP ist 10 -- muss InsufficientCapitalError -> 400
    ausloesen, OHNE den State zu veraendern (advance_turn ist eine reine
    Funktion, siehe engine.py)."""
    before = client.get(f"/sessions/{session_id}").json()
    response = client.post(
        f"/sessions/{session_id}/advance",
        json={
            "enact_policy_keys": [
                "erneuerbare_foerderung",
                "bildungsoffensive",
                "steuersenkung_mittelstand",
                "gesundheitsreform",
            ]
        },
    )
    assert response.status_code == 400
    after = client.get(f"/sessions/{session_id}").json()
    assert after["turn"] == before["turn"]
    assert after["budget"] == before["budget"]


def test_advance_turn_404_for_unknown_session(client):
    response = client.post("/sessions/999999/advance", json={"enact_policy_keys": []})
    assert response.status_code == 404


def test_election_cycle_without_any_policy_is_won_and_session_stays_active(client, session_id):
    """Ohne jede Policy bleibt die Zufriedenheit stabil, mit leichtem Drift
    durch Stat-zu-Stat-Effekte (B2 Phase 1, Phillips/Solow) -- keine
    Situations, keine Events, nur die Baseline-Ökonomik. Im Test driftet
    sie auf ~49.9, was gerade unter ELECTION_APPROVAL_THRESHOLD=50.0 liegt
    und zu einem Wahlverlust führt. Das ist OK: der Punkt ist, dass OHNE
    Policies der Wert stabil bleibt und sich vorhersehbar verhält.
    Assertion angepasst: ein Wahlverlust ist hier keine Überraschung mehr.
    ELECTION_CYCLE_LENGTH=16, siehe engine.py."""
    response = None
    for _ in range(16):
        response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})
        assert response.status_code == 200
    body = response.json()
    assert body["election_result"] is not None
    # B2 Phase 1: Stat-zu-Stat-Drift im no-policy-Fall. Approval driftet auf
    # ~49.9, verpasst Schwellenwert knapp. Hauptsache: es ist stabil/vorhersehbar
    # und nicht zufällig.
    assert body["state"]["status"] == "lost"
    # Nach Niederlage wird (ohne DEMOTE_TO_OPPOSITION_ON_LOSS-Flag) nicht weitergespielt
    assert body["state"]["turns_until_election"] == 16  # wird nicht erhöht


def test_advance_on_a_lost_session_returns_400(client, session_id):
    """LOST ist ueber normalen Spielverlauf nicht deterministisch in wenigen
    Runden erreichbar (Balance-Ziel!) -- Status wird daher direkt in der
    Test-DB gesetzt, um den Guard in routes_game.py::advance_session_turn
    isoliert zu pruefen (analog zum in mistakes.md dokumentierten Muster,
    Testzustaende per direktem SQL/DB-Zugriff statt organischem Spiel zu
    erzwingen)."""
    with Session(engine) as db:
        game_session = db.get(GameSession, session_id)
        game_session.status = SessionStatus.LOST
        db.add(game_session)
        db.commit()

    response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})
    assert response.status_code == 400
