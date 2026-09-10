"""Tests fuer POST /sessions, GET /sessions/{id} und GET /policies --
die Basis-Endpunkte, ohne die kein anderer Endpunkt sinnvoll testbar ist.
"""


def test_create_session_returns_niedersachsen_with_starting_budget(client):
    response = client.post("/sessions")
    assert response.status_code == 200
    body = response.json()
    assert body["admin_unit"] == "Niedersachsen"
    assert body["turn"] == 0
    assert body["budget"] == 1000.0
    assert isinstance(body["session_id"], int)


def test_get_session_state_reflects_freshly_created_session(client, session_id):
    response = client.get(f"/sessions/{session_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["turn"] == 0
    assert body["status"] == "active"
    assert body["active_policy_keys"] == []
    assert body["pending_dilemma"] is None
    # STARTING_STATISTICS aus sim/landtag_sim/sample_data.py -- randomisiert
    # (jittered_starting_statistics), daher nur auf Vorhandensein pruefen,
    # nicht auf exakte Werte.
    for key in ("unemployment_rate", "gdp_growth", "education_spending", "healthcare_quality", "co2_emissions", "renewable_share"):
        assert key in body["statistics"]
    # Ueberlappende Waehlergruppen (Nach-P2-Nachschaerfung, siehe mistakes.md):
    # sechs Gruppen, Summe der population_share > 1.0.
    assert len(body["voter_groups"]) == 6
    total_share = sum(g["population_share"] for g in body["voter_groups"])
    assert total_share > 1.0


def test_get_session_state_404_for_unknown_session(client):
    response = client.get("/sessions/999999")
    assert response.status_code == 404


def test_list_policies_returns_full_sample_catalog(client):
    """GET /policies ist session-unabhaengig -- siehe routes_game.py::
    list_policies. Regressionstest fuer die 'GET /policies fehlt noch'-Luecke
    (README.md 'Bekannte Vereinfachungen', laengst behoben)."""
    response = client.get("/policies")
    assert response.status_code == 200
    policies = response.json()
    keys = {p["key"] for p in policies}
    # Fuenf Beispiel-Policies: vier nach der Balance-Nachschaerfung (siehe
    # mistakes.md "Dominante-Strategie-Check ... Free Lunch"-Bug) plus
    # vermoegensteuer aus der Policy-Repeal-/Einnahmen-Nachschaerfung
    # (Democracy-4-Recherche, siehe CLAUDE.md).
    assert keys == {
        "erneuerbare_foerderung",
        "bildungsoffensive",
        "steuersenkung_mittelstand",
        "gesundheitsreform",
        "vermoegensteuer",
        # B7 "Dynamische Policy-Freischaltung": drei zunaechst gesperrte
        # Policies (unlock_conditions) -- GET /policies liefert sie trotzdem
        # aus (das Frontend graut sie aus), siehe routes_game.py.
        "digitalpakt_schulen",
        "gruener_wasserstoff",
        "arbeitsmarkt_sofortprogramm",
    }
    steuersenkung = next(p for p in policies if p["key"] == "steuersenkung_mittelstand")
    assert steuersenkung["requires"] == ["bildungsoffensive"]
    vermoegensteuer = next(p for p in policies if p["key"] == "vermoegensteuer")
    assert vermoegensteuer["income_per_turn"] > 0
    for policy in policies:
        assert policy["effects"], f"{policy['key']} hat keine Effekte"


def test_list_policies_works_before_any_session_exists(client):
    """list_policies() ruft run_all_seeds() selbst auf -- der Katalog muss
    auch ohne eine vorher angelegte Session abrufbar sein (z.B. fuer eine
    kuenftige Startseite mit Policy-Uebersicht vor dem ersten Spielstart)."""
    response = client.get("/policies")
    assert response.status_code == 200
    assert len(response.json()) > 0
