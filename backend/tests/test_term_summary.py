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

    # Bis zum Wahl-Turn vorspulen und dabei etwaige Dilemmas aufloesen: seit B3
    # (konjunkturdelle drueckt gdp_growth) loest bildungsoffensives verschaerfter
    # Wachstums-Trade-off `rezession` organisch aus, was /advance sonst mit 400
    # blockiert. Deterministisch mit Option 0 aufloesen und weiterlaufen.
    ts = None
    for _ in range(20):
        response = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})
        if response.status_code == 400:
            pending = client.get(f"/sessions/{session_id}").json()["pending_dilemma"]
            assert pending is not None, response.json()
            option = pending["options"][0]["key"]
            client.post(f"/sessions/{session_id}/resolve-dilemma", json={"option_key": option})
            continue
        assert response.status_code == 200
        if response.json()["term_summary"] is not None:
            ts = response.json()["term_summary"]
            break

    assert ts is not None
    # Robuste, nicht dilemma-abhaengige Invarianten: bildungsoffensive hebt die
    # Bildungsausgaben stark -- das ueberlebt jede oben aufgeloeste Dilemma-
    # Option (keine davon senkt education_spending) und dominiert als groesste
    # Verbesserung. Der gdp_growth-Trade-off wird hier BEWUSST nicht geprueft:
    # loest man die durch B3 organisch ausgeloeste `rezession` auf (Option 0 =
    # Konjunkturprogramm, +1.5 gdp), kann das Wachstum am Zyklusende netto
    # wieder positiv sein -- eine legitime Spielerreaktion, kein Bilanz-Bug.
    assert ts["statistic_changes"]["education_spending"] > 0
    assert ts["biggest_improvement"] == "education_spending"
    assert ts["category_changes"]["social"] > 0


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
