"""B4 "Narrative Konsequenz-Ebene ('Presseschau')" (BACKLOG.md) end-to-end
durch die echte API. Die reine Auswertungslogik (UND-Bedingungen, Cooldown,
Event/Dilemma-Unterdrueckung, kein Sim-Effekt) ist in
sim/tests/test_engine.py Abschnitt "B4" abgedeckt -- hier geht es nur um den
Transport durch das AdvanceTurnResponse und darum, dass ein policy-
gekoppelter Report auch mit gejittertem Session-Start irgendwann feuert.
"""


def _advance(client, session_id, enact=None):
    """advance + falls ein Dilemma aufpoppt, sofort mit Option 0 aufloesen,
    damit der Lauf nicht blockiert."""
    resp = client.post(
        f"/sessions/{session_id}/advance", json={"enact_policy_keys": enact or []}
    )
    if resp.status_code != 200:
        return resp
    body = resp.json()
    if body["pending_dilemma"] is not None:
        option = body["pending_dilemma"]["options"][0]["key"]
        client.post(f"/sessions/{session_id}/resolve-dilemma", json={"option_key": option})
    return resp


def test_advance_response_always_carries_a_reports_list(client, session_id):
    body = _advance(client, session_id).json()
    assert "reports" in body
    assert isinstance(body["reports"], list)


def test_report_and_event_never_share_a_turn(client, session_id):
    """Frequenz-Management (L5): in einer Runde mit Ereignis kommt kein
    Report mit -- ueber einen laengeren Lauf geprueft."""
    _advance(client, session_id, enact=["bildungsoffensive"])
    for _ in range(30):
        resp = _advance(client, session_id)
        if resp.status_code != 200:
            break
        body = resp.json()
        assert not (body["events"] and body["reports"]), body


def test_bildungsoffensive_eventually_produces_a_press_report(client, session_id):
    """Der policy-gekoppelte Report `bildungsoffensive_wirkt` sollte in einem
    laengeren Lauf mit aktiver Bildungsoffensive mindestens einmal
    erscheinen. Wegen des Start-Jitters (siehe conftest/mistakes.md) wird
    nur geprueft, DASS ein Report-Text auftaucht, nicht welcher."""
    _advance(client, session_id, enact=["bildungsoffensive"])
    for _ in range(50):
        resp = _advance(client, session_id)
        if resp.status_code != 200:
            break
        if resp.json()["reports"]:
            return
    raise AssertionError("kein einziger Presseschau-Text in 50 Runden")
