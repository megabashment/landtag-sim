"""B27 "Bundes-Skalierung" (M7_SPRINT_PLAN.md) durch die echte API.

- GET /bundeslaender liefert alle spielbaren Bundeslaender mit Baseline
- POST /sessions/new-bundesland/{key} startet eine Session mit dieser Baseline
  (gejittert um die BUNDESLAND-eigene Baseline, nicht um Niedersachsen)
- Sessions verschiedener Bundeslaender sind unabhaengig voneinander
"""

# Jitter-Spread ist +/-5% (siehe jittered_starting_statistics) -- Toleranz
# hier bewusst grosszuegiger (10%), um garantiert nicht auf Rundungs-/
# Float-Kanten zu failen.
JITTER_TOLERANCE = 0.10


def test_list_bundeslaender(client):
    """GET /bundeslaender liefert mindestens die 3 Sample-Bundeslaender."""
    resp = client.get("/bundeslaender")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 3

    keys = {b["key"] for b in body}
    assert {"niedersachsen", "bayern", "nrw"} <= keys

    for bundesland in body:
        assert "key" in bundesland
        assert "name" in bundesland
        assert "description" in bundesland
        assert isinstance(bundesland["starting_statistics"], dict)
        assert len(bundesland["starting_statistics"]) == 6  # alle 6 Statistiken


def test_create_session_from_bundesland(client):
    """POST /sessions/new-bundesland/{key} startet eine neue Session mit
    Bayerns Baseline (nicht Niedersachsens Default)."""
    resp = client.post("/sessions/new-bundesland/bayern")
    assert resp.status_code == 200
    body = resp.json()
    assert "session_id" in body
    assert body["turn"] == 0
    assert body["budget"] == 1000.0
    assert body["admin_unit"] == "Bayern"
    assert body["party_id"] is None
    assert body["scenario_id"] is None


def test_create_session_from_nonexistent_bundesland_returns_404(client):
    resp = client.post("/sessions/new-bundesland/nicht-existierendes-bundesland")
    assert resp.status_code == 404


def test_session_statistics_jitter_around_the_bundesland_baseline(client):
    """Die tatsaechlich gespeicherten Statistiken muessen um BAYERNS Baseline
    (nicht Niedersachsens) streuen -- Regressionstest fuer den Bug, dass
    _seed_session_world() vorher IMMER STARTING_STATISTICS (Niedersachsen)
    gejittert haette, egal welches Bundesland gewaehlt wurde."""
    resp = client.post("/sessions/new-bundesland/bayern")
    session_id = resp.json()["session_id"]
    state = client.get(f"/sessions/{session_id}").json()

    bayern = next(b for b in client.get("/bundeslaender").json() if b["key"] == "bayern")
    for stat_key, baseline in bayern["starting_statistics"].items():
        actual = state["statistics"][stat_key]
        assert abs(actual - baseline) <= abs(baseline) * JITTER_TOLERANCE, (
            f"{stat_key}: {actual} liegt zu weit von Bayern-Baseline {baseline} entfernt"
        )


def test_bayern_and_nrw_sessions_are_independent_and_reflect_distinct_baselines(client):
    """Baseline-Validierung (M7_SPRINT_PLAN.md B27-Tests): Bayern hat eine
    deutlich niedrigere Arbeitslosenquote und ein hoeheres Wachstum als NRW
    -- die beiden Sessions duerfen sich dabei nicht gegenseitig beeinflussen."""
    bayern_resp = client.post("/sessions/new-bundesland/bayern")
    nrw_resp = client.post("/sessions/new-bundesland/nrw")

    bayern_state = client.get(f"/sessions/{bayern_resp.json()['session_id']}").json()
    nrw_state = client.get(f"/sessions/{nrw_resp.json()['session_id']}").json()

    assert bayern_state["statistics"]["unemployment_rate"] < nrw_state["statistics"]["unemployment_rate"]
    assert bayern_state["statistics"]["gdp_growth"] > nrw_state["statistics"]["gdp_growth"]

    # Wiederholtes Anlegen desselben Bundeslands erzeugt KEINE zweite
    # AdminUnit-Zeile (ensure_bundesland ist idempotent, analog ensure_niedersachsen).
    second_bayern_resp = client.post("/sessions/new-bundesland/bayern")
    assert second_bayern_resp.json()["admin_unit"] == bayern_resp.json()["admin_unit"] == "Bayern"


def test_new_party_session_with_bundesland_key_uses_that_baseline(client):
    """UX-Onboarding-Redesign (2026-09-13): POST /sessions/new-party akzeptiert
    jetzt optional bundesland_key -- der neue Ersteinstieg (Bundesland ->
    Partei -> Start) erzeugt Session+Partei in EINEM Schritt statt zwei
    getrennten Endpoints."""
    resp = client.post(
        "/sessions/new-party",
        json={"name": "Bayern-Partei", "ideology": "blue", "bundesland_key": "bayern"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["admin_unit"] == "Bayern"
    assert body["party_name"] == "Bayern-Partei"

    state = client.get(f"/sessions/{body['session_id']}").json()
    assert state["admin_unit_name"] == "Bayern"
    # Statistik muss um Bayerns Baseline streuen, nicht um Niedersachsen
    # (Bayern unemployment_rate 3.6 vs. Niedersachsen 5.9 -- Baender
    # ueberlappen nicht, siehe sample_data.py-Kommentar zu den Bundeslaendern).
    assert state["statistics"]["unemployment_rate"] < 4.5


def test_new_party_session_without_bundesland_key_defaults_to_niedersachsen(client):
    """Rueckwaertskompatibilitaet: bundesland_key ist optional, alte Aufrufer
    (ohne das Feld) starten weiterhin wie bisher in Niedersachsen."""
    resp = client.post("/sessions/new-party", json={"name": "Nds-Partei", "ideology": "green"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["admin_unit"] == "Niedersachsen"


def test_new_party_session_with_unknown_bundesland_key_returns_404(client):
    resp = client.post(
        "/sessions/new-party",
        json={"name": "x", "ideology": "green", "bundesland_key": "atlantis"},
    )
    assert resp.status_code == 404
