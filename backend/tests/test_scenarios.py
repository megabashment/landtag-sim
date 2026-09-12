"""B24 "Scenario Mode" (M6 Sprint 1) durch die echte API.

- GET /scenarios liefert alle Szenarien
- POST /sessions/new-scenario/{scenario_id} startet eine Session mit Szenario
- Szenario-Startbedingungen sind in den Szenarien definiert (noch nicht angewendet in Phase 1)
"""


def test_list_scenarios(client):
    """GET /scenarios liefert alle vordefinierten Szenarien."""
    resp = client.get("/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 5  # Mindestens 5 Sample-Szenarien

    # Jedes Szenario hat key, name, description
    for scenario in body:
        assert "key" in scenario
        assert "name" in scenario
        assert "description" in scenario


def test_create_session_from_scenario(client):
    """POST /sessions/new-scenario/{scenario_id} startet eine neue Session."""
    resp = client.post("/sessions/new-scenario/klimakrise_bewaeltigen")
    assert resp.status_code == 200
    body = resp.json()
    assert "session_id" in body
    assert body["turn"] == 0
    assert body["budget"] == 1000.0
    assert body["party_id"] is None  # Keine Party im Szenario-Modus


def test_create_session_from_nonexistent_scenario(client):
    """POST mit unbekannter Scenario-ID gibt 404."""
    resp = client.post("/sessions/new-scenario/nicht_existierendes_szenario")
    assert resp.status_code == 404
