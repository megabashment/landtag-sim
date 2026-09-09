"""Tests fuer POST /sessions/{id}/preview -- P0-Punkt 'Effekt-Vorschau vor
Entscheidung' (docs/game-design-roadmap.md). Preview darf NIE persistieren:
jeder Test prueft das explizit gegen GET /sessions/{id}.
"""


def test_preview_does_not_persist_any_state(client, session_id):
    before = client.get(f"/sessions/{session_id}").json()
    response = client.post(f"/sessions/{session_id}/preview", json={"enact_policy_keys": ["erneuerbare_foerderung"]})
    assert response.status_code == 200
    body = response.json()
    assert body["feasible"] is True

    after = client.get(f"/sessions/{session_id}").json()
    assert after == before
    assert after["active_policy_keys"] == []


def test_preview_reports_required_and_available_capital(client, session_id):
    response = client.post(f"/sessions/{session_id}/preview", json={"enact_policy_keys": ["erneuerbare_foerderung"]})
    body = response.json()
    assert body["feasible"] is True
    assert body["capital_required"] == 4.0  # erneuerbare_foerderung.capital_cost, siehe sample_data.py
    assert body["capital_available"] == 10.0  # CAPITAL_CAP direkt zu Beginn


def test_preview_reports_infeasible_for_missing_prerequisite(client, session_id):
    response = client.post(f"/sessions/{session_id}/preview", json={"enact_policy_keys": ["steuersenkung_mittelstand"]})
    assert response.status_code == 200
    body = response.json()
    assert body["feasible"] is False
    assert "bildungsoffensive" in body["infeasible_reason"]


def test_preview_reports_infeasible_for_insufficient_capital(client, session_id):
    response = client.post(
        f"/sessions/{session_id}/preview",
        json={
            "enact_policy_keys": [
                "erneuerbare_foerderung",
                "bildungsoffensive",
                "steuersenkung_mittelstand",
                "gesundheitsreform",
            ]
        },
    )
    body = response.json()
    assert body["feasible"] is False
    assert body["capital_required"] == 14.0
    assert body["capital_available"] == 10.0


def test_preview_rejects_unknown_policy_key(client, session_id):
    response = client.post(f"/sessions/{session_id}/preview", json={"enact_policy_keys": ["nicht_vorhanden"]})
    assert response.status_code == 400


def test_preview_404_for_unknown_session(client):
    response = client.post("/sessions/999999/preview", json={"enact_policy_keys": []})
    assert response.status_code == 404
