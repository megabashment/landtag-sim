"""Tests fuer den Policy-Repeal-Mechanismus ueber die echte API
(POST /sessions/{id}/advance mit repeal_policy_keys, siehe
landtag_sim.engine.py::advance_turn und die Democracy-4-Recherche in
CLAUDE.md). Ergaenzt die reinen Sim-Engine-Tests in sim/tests/test_engine.py
um die Backend-spezifischen Teile: DB-Persistenz der EnactedPolicy-Zeile
(repealed_turn statt active), und dass load_sim_state() eine zurueckgezogene
Policy beim naechsten Request weiter korrekt abklingen laesst (siehe
sim_bridge.py, "WICHTIG: bewusst ALLE Zeilen laden")."""


def test_repeal_removes_policy_from_active_keys(client, session_id):
    response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["erneuerbare_foerderung"]})
    assert response.status_code == 200
    assert "erneuerbare_foerderung" in response.json()["state"]["active_policy_keys"]

    response = client.post(f"/sessions/{session_id}/advance", json={"repeal_policy_keys": ["erneuerbare_foerderung"]})
    assert response.status_code == 200
    assert "erneuerbare_foerderung" not in response.json()["state"]["active_policy_keys"]


def test_repeal_stops_upkeep_but_keeps_effect_decaying_across_requests(client, session_id):
    """Regressionstest fuer den sim_bridge.py-Fix: load_sim_state() darf
    zurueckgezogene EnactedPolicy-Zeilen NICHT mehr herausfiltern, sonst
    verliert jeder neue Request das Abkling-Gedaechtnis der Policy sofort
    (der State wird bei jedem API-Call frisch aus der DB aufgebaut)."""
    client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["erneuerbare_foerderung"]})
    for _ in range(3):
        client.post(f"/sessions/{session_id}/advance", json={})
    before_repeal = client.get(f"/sessions/{session_id}").json()
    renewable_before = before_repeal["statistics"]["renewable_share"]

    repeal_response = client.post(
        f"/sessions/{session_id}/advance", json={"repeal_policy_keys": ["erneuerbare_foerderung"]}
    )
    assert repeal_response.status_code == 200

    # Zwei weitere, GETRENNTE Requests (jeder baut den State frisch aus der
    # DB auf) -- der Effekt muss dabei WEITER abklingen, nicht auf einen
    # Schlag verschwinden oder "vergessen" werden.
    values = []
    for _ in range(2):
        result = client.post(f"/sessions/{session_id}/advance", json={})
        values.append(result.json()["state"]["statistics"]["renewable_share"])

    assert values[0] < renewable_before
    assert values[1] < values[0]  # klingt weiter ab, nicht eingefroren
    assert "erneuerbare_foerderung" not in client.get(f"/sessions/{session_id}").json()["active_policy_keys"]


def test_repealing_never_enacted_policy_returns_400(client, session_id):
    response = client.post(f"/sessions/{session_id}/advance", json={"repeal_policy_keys": ["gesundheitsreform"]})
    assert response.status_code == 400
    assert "gesundheitsreform" in response.json()["detail"]


def test_enacting_already_active_policy_returns_400(client, session_id):
    client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["gesundheitsreform"]})
    response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["gesundheitsreform"]})
    assert response.status_code == 400
    assert "gesundheitsreform" in response.json()["detail"]


def test_repeal_blocked_when_required_by_active_dependent_policy(client, session_id):
    client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["bildungsoffensive"]})
    client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["steuersenkung_mittelstand"]})

    response = client.post(f"/sessions/{session_id}/advance", json={"repeal_policy_keys": ["bildungsoffensive"]})
    assert response.status_code == 400
    assert "steuersenkung_mittelstand" in response.json()["detail"]

    # Zustand blieb dabei unveraendert -- beide weiterhin aktiv.
    active = client.get(f"/sessions/{session_id}").json()["active_policy_keys"]
    assert "bildungsoffensive" in active
    assert "steuersenkung_mittelstand" in active


def test_can_reenact_a_policy_after_repeal(client, session_id):
    client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["gesundheitsreform"]})
    client.post(f"/sessions/{session_id}/advance", json={"repeal_policy_keys": ["gesundheitsreform"]})
    response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["gesundheitsreform"]})
    assert response.status_code == 200
    assert "gesundheitsreform" in response.json()["state"]["active_policy_keys"]


def test_preview_reports_repeal_capital_cost_and_stays_read_only(client, session_id):
    client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["erneuerbare_foerderung"]})
    before = client.get(f"/sessions/{session_id}").json()

    response = client.post(
        f"/sessions/{session_id}/preview", json={"repeal_policy_keys": ["erneuerbare_foerderung"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["feasible"] is True
    assert body["capital_required"] == 4.0  # capital_cost von erneuerbare_foerderung

    after = client.get(f"/sessions/{session_id}").json()
    assert after == before  # Preview persistiert nichts


def test_preview_of_repealing_an_inactive_policy_is_infeasible(client, session_id):
    response = client.post(
        f"/sessions/{session_id}/preview", json={"repeal_policy_keys": ["gesundheitsreform"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["feasible"] is False
    assert "gesundheitsreform" in body["infeasible_reason"]


def test_policy_catalog_exposes_income_per_turn_for_vermoegensteuer(client):
    response = client.get("/policies")
    assert response.status_code == 200
    vermoegensteuer = next(p for p in response.json() if p["key"] == "vermoegensteuer")
    assert vermoegensteuer["income_per_turn"] == 20.0


def test_enacting_vermoegensteuer_increases_budget_via_income_per_turn(client, session_id):
    before = client.get(f"/sessions/{session_id}").json()["budget"]
    response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["vermoegensteuer"]})
    assert response.status_code == 200
    after = response.json()["state"]["budget"]
    # +BASE_BUDGET_INCOME_PER_TURN (15) +income_per_turn (20) -upkeep_cost (2)
    # -one_time_cost (0), siehe sample_data.py::vermoegensteuer.
    assert after == before + 15.0 + 20.0 - 2.0
