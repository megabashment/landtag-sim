"""B7 "Dynamische Policy-Freischaltung durch Sim-Zustand" (BACKLOG.md) durch
die echte API. Die reine Unlock-Logik ist in sim/tests/test_engine.py
(Abschnitt B7) abgedeckt -- hier: Transport von unlock_conditions in
GET /policies, 400 beim Einfuehren einer gesperrten Policy, feasible=False in
der Preview, und dass eine Policy nach Erfuellen ihrer Bedingung einfuehrbar
wird (Round-Trip inkl. Persistenz)."""


def _advance(client, session_id, enact=None):
    """advance + falls ein Dilemma aufpoppt, sofort mit Option 0 aufloesen."""
    resp = client.post(
        f"/sessions/{session_id}/advance", json={"enact_policy_keys": enact or []}
    )
    if resp.status_code == 200 and resp.json()["pending_dilemma"] is not None:
        option = resp.json()["pending_dilemma"]["options"][0]["key"]
        client.post(f"/sessions/{session_id}/resolve-dilemma", json={"option_key": option})
    return resp


def test_policies_endpoint_exposes_unlock_conditions(client):
    policies = {p["key"]: p for p in client.get("/policies").json()}
    digitalpakt = policies["digitalpakt_schulen"]
    assert digitalpakt["unlock_conditions"] == [
        {"statistic_key": "education_spending", "operator": ">", "threshold": 50.0}
    ]
    # Ungesperrte Policy hat eine leere Liste (kein None).
    assert policies["bildungsoffensive"]["unlock_conditions"] == []


def test_enacting_a_locked_policy_returns_400(client, session_id):
    resp = client.post(
        f"/sessions/{session_id}/advance",
        json={"enact_policy_keys": ["digitalpakt_schulen"]},
    )
    assert resp.status_code == 400
    assert "gesperrt" in resp.json()["detail"]


def test_preview_of_a_locked_policy_is_infeasible(client, session_id):
    resp = client.post(
        f"/sessions/{session_id}/preview",
        json={"enact_policy_keys": ["digitalpakt_schulen"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["feasible"] is False
    assert "gesperrt" in body["infeasible_reason"]


def test_digitalpakt_becomes_enactable_after_education_rises(client, session_id):
    """Round-Trip inkl. Persistenz: bildungsoffensive hebt education_spending
    ueber 50, danach laesst sich digitalpakt_schulen einfuehren."""
    _advance(client, session_id, enact=["bildungsoffensive"])
    for _ in range(25):
        state = client.get(f"/sessions/{session_id}").json()
        if state["statistics"]["education_spending"] > 50.0:
            break
        resp = _advance(client, session_id)
        if resp.status_code != 200:
            break
    assert client.get(f"/sessions/{session_id}").json()["statistics"]["education_spending"] > 50.0

    resp = client.post(
        f"/sessions/{session_id}/advance",
        json={"enact_policy_keys": ["digitalpakt_schulen"]},
    )
    assert resp.status_code == 200
    assert "digitalpakt_schulen" in resp.json()["state"]["active_policy_keys"]
