"""B9 "Szenario-/Legislatur-Ziele" (BACKLOG.md, F1 = optionale, unverbindliche
Ziele) durch die echte API. Die Auswertungslogik ist in sim/tests/test_engine.py
(Abschnitt B9) abgedeckt -- hier: Transport der Ziele in
AdvanceTurnResponse.term_summary.goals und die Unverbindlichkeit (verfehlte
Ziele beenden die Partie nicht)."""
from sqlmodel import Session, select

from app.db import engine
from app.models import GameSession, VoterGroup


def _advance(client, session_id):
    resp = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []})
    if resp.status_code == 200 and resp.json()["pending_dilemma"] is not None:
        option = resp.json()["pending_dilemma"]["options"][0]["key"]
        client.post(f"/sessions/{session_id}/resolve-dilemma", json={"option_key": option})
    return resp


def _run_to_term_summary(client, session_id):
    for _ in range(20):
        resp = _advance(client, session_id)
        if resp.status_code != 200:
            continue
        if resp.json()["term_summary"] is not None:
            return resp.json()["term_summary"]
    raise AssertionError("keine TermSummary im Testfenster erhalten")


def test_term_summary_carries_scenario_goals(client, session_id):
    ts = _run_to_term_summary(client, session_id)
    goals = ts["goals"]
    assert goals, "Legislatur-Ziele fehlen in der Amtszeit-Bilanz"
    keys = {g["key"] for g in goals}
    # Die vier Beispielziele aus SAMPLE_SCENARIO_GOALS.
    assert {"klimaziel", "arbeitsmarkt", "solide_finanzen", "rueckhalt"} <= keys
    for g in goals:
        assert set(g) == {"key", "description", "met"}
        assert isinstance(g["met"], bool)
        assert g["description"].strip()


def test_missed_goals_do_not_end_the_game(client, session_id):
    """Unverbindlichkeit (F1): selbst bei tief unzufriedenen Waehlern (Wahl
    verloren, Ziele verfehlt) ist die Bilanz vorhanden und die Ziele werden
    nur ausgewiesen -- das Spielende steuert allein das Wahlergebnis."""
    # Session direkt vor eine verlorene Wahl setzen (analog test_factions).
    with Session(engine) as db:
        session = db.get(GameSession, session_id)
        session.turns_until_election = 1
        db.add(session)
        for vg in db.exec(select(VoterGroup).where(VoterGroup.session_id == session_id)):
            vg.satisfaction = 5.0
            db.add(vg)
        db.commit()

    body = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []}).json()
    assert body["election_result"]["won"] is False
    ts = body["term_summary"]
    assert ts is not None
    # rueckhalt (Zustimmung > 60) muss bei ~5 Zufriedenheit verfehlt sein.
    rueckhalt = next(g for g in ts["goals"] if g["key"] == "rueckhalt")
    assert rueckhalt["met"] is False
    # Unverbindlichkeit (F1): die verfehlten Ziele beenden die Partie nicht --
    # der Ausgang haengt allein am Wahlergebnis. Mit DEMOTE_TO_OPPOSITION_ON_LOSS
    # bedeutet "Wahl verloren" jetzt Rollenwechsel in die Opposition (status
    # bleibt "active"), nicht Game Over.
    assert body["election_result"]["won"] is False
    assert body["state"]["role"] == "opposition"
