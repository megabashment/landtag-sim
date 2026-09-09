"""Tests fuer B1 "Legislatur-Bogen & Amtszeit-Debrief" (BACKLOG.md) auf
API-Ebene: das AdvanceTurnResponse muss genau am Wahl-Turn ein
`term_summary`-Objekt mitliefern (sonst null), mit plausiblen Start-vs-Ende-
Werten fuer die gerade abgelaufene Legislaturperiode.
"""


def test_term_summary_is_null_before_the_election_turn(client, session_id):
    response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})
    assert response.status_code == 200
    assert response.json()["term_summary"] is None


def test_term_summary_is_present_and_plausible_on_the_election_turn(client, session_id):
    """Ein voller Zyklus (ELECTION_CYCLE_LENGTH=16) ohne Policy: term_summary
    ist erst im 16. AdvanceTurnResponse gesetzt und deckt Runde 0..16 ab."""
    response = None
    for turn in range(1, 17):
        response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})
        assert response.status_code == 200
        body = response.json()
        if turn < 16:
            assert body["term_summary"] is None
        else:
            assert body["election_result"] is not None
            ts = body["term_summary"]
            assert ts is not None
            assert ts["term_start_turn"] == 0
            assert ts["term_end_turn"] == 16
            assert ts["dilemmas_faced"] == 0
            # Ohne Policy bewegt sich keine Statistik -> leere Delta-Maps.
            assert ts["statistic_changes"] == {}
            assert ts["end_approval"] == body["election_result"]["approval"]


def test_term_summary_reports_policy_driven_statistic_changes(client, session_id):
    """Mit bildungsoffensive ab Runde 1 muss die Bilanz am Zyklusende einen
    positiven education_spending- und einen negativen gdp_growth-Delta
    ausweisen (der verschaerfte Trade-off, siehe sample_data.py)."""
    first = client.post(
        f"/sessions/{session_id}/advance", json={"enact_policy_keys": ["bildungsoffensive"]}
    )
    assert first.status_code == 200

    response = None
    for _ in range(15):
        response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})
        assert response.status_code == 200

    ts = response.json()["term_summary"]
    assert ts is not None
    assert ts["statistic_changes"]["education_spending"] > 0
    assert ts["statistic_changes"]["gdp_growth"] < 0
    assert ts["biggest_improvement"] == "education_spending"
    assert ts["biggest_decline"] == "gdp_growth"
    assert ts["category_changes"]["social"] > 0
    assert ts["category_changes"]["economy"] < 0


def test_term_tracking_resets_for_the_next_legislative_period(client, session_id):
    """Nach der ersten Wahl muss der zweite Zyklus wieder sauber bei
    term_start_turn == <Wahl-Turn> beginnen und erst an dessen Ende eine
    neue Bilanz liefern."""
    for _ in range(16):
        client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})

    # Erste Runde des zweiten Zyklus: noch keine neue Bilanz.
    mid = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})
    assert mid.json()["term_summary"] is None

    response = None
    for _ in range(15):
        response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})
    ts = response.json()["term_summary"]
    assert ts is not None
    assert ts["term_start_turn"] == 16
    assert ts["term_end_turn"] == 32
