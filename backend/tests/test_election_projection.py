"""B5 "Wahlprognose mit sichtbarem Turnout/Apathie" (BACKLOG.md) end-to-end
durch die echte API. Die Prognose-Rechnung selbst (Turnout-Ableitung,
approval == echte Wahl) ist in sim/tests/test_engine.py Abschnitt "B5"
abgedeckt -- hier geht es nur um das Fenster (nur in den letzten
ELECTION_PROJECTION_WINDOW Runden) und den Transport im SessionStateResponse.
"""
from app.api.routes_game import ELECTION_PROJECTION_WINDOW


def _advance(client, session_id):
    resp = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})
    if resp.status_code == 200 and resp.json()["pending_dilemma"] is not None:
        option = resp.json()["pending_dilemma"]["options"][0]["key"]
        client.post(f"/sessions/{session_id}/resolve-dilemma", json={"option_key": option})
    return resp


def test_projection_absent_early_and_present_in_the_final_window(client, session_id):
    state = client.get(f"/sessions/{session_id}").json()
    assert state["turns_until_election"] > ELECTION_PROJECTION_WINDOW
    assert state["election_projection"] is None

    seen_projection_at = []
    for _ in range(20):
        resp = _advance(client, session_id)
        if resp.status_code != 200:
            break
        state = client.get(f"/sessions/{session_id}").json()
        tue = state["turns_until_election"]
        if state["election_projection"] is not None:
            seen_projection_at.append(tue)
            assert tue <= ELECTION_PROJECTION_WINDOW
        else:
            assert tue > ELECTION_PROJECTION_WINDOW or state["status"] != "active"

    assert seen_projection_at, "Prognose ist nie aufgetaucht"


def test_projection_payload_shape(client, session_id):
    for _ in range(20):
        resp = _advance(client, session_id)
        if resp.status_code != 200:
            break
        projection = client.get(f"/sessions/{session_id}").json()["election_projection"]
        if projection is None:
            continue
        assert set(projection) == {
            "approval",
            "turnout_adjusted_approval",
            "threshold",
            "would_win",
            "groups",
        }
        assert projection["groups"], "Gruppen-Aufschluesselung fehlt"
        for g in projection["groups"]:
            assert set(g) == {
                "name",
                "population_share",
                "satisfaction",
                "satisfaction_momentum",
                "estimated_turnout",
                "trend",
            }
            assert 0.0 <= g["estimated_turnout"] <= 1.0
            assert g["trend"] in {"steigend", "stabil", "fallend"}
        # approval ist die entscheidungsrelevante Zahl -> would_win folgt ihr
        assert projection["would_win"] == (projection["approval"] >= projection["threshold"])
        return
    raise AssertionError("keine Prognose im Testfenster erhalten")
