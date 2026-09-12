"""B20 "Party-Legacy" + Mehrparteiensystem (Medium-Scope) durch die echte API.

- Party-Sessions treten gegen die drei festen Rivalen-Parteien an; die Wahl
  entscheidet die Pluralitaet (hoechster Stimmenanteil), nicht mehr die
  50%-Schwelle.
- Nach der Wahl bewegt sich Party.reputation (+6 Sieg / -8 Niederlage) und
  Party.extra_data["terms"] protokolliert die Legislaturperiode.
- GET /parties liefert das Kurzprofil; POST /sessions/from-party/{id} startet
  eine neue Legislatur mit dem aufgebauten Ruf.

Die Ruf-Multiplikator-Mathematik selbst ist in sim/tests/test_engine.py
abgedeckt -- hier geht es um den Transport durch DB + Routes.
"""
from sqlmodel import Session, select

from app.db import engine
from app.models import GameSession, Party, VoterGroup


def _new_party(client, name="Legacy-Testpartei", ideology="green") -> dict:
    resp = client.post("/sessions/new-party", json={"name": name, "ideology": ideology})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_new_party_session_seeds_three_rivals(client):
    body = _new_party(client)
    state = client.get(f"/sessions/{body['session_id']}").json()
    rivals = state["rival_parties"]
    assert len(rivals) == 3
    assert {r["ideology"] for r in rivals} == {"green", "red", "blue"}
    # Ruf startet neutral.
    assert state["party_reputation"] == 50.0


def test_classic_session_has_no_rivals_and_no_reputation(client, session_id):
    state = client.get(f"/sessions/{session_id}").json()
    assert state["rival_parties"] == []
    assert state["party_reputation"] is None


def test_election_with_rivals_reports_standings_and_moves_reputation(client):
    body = _new_party(client)
    sid = body["session_id"]

    # Kurz vor die Wahl setzen, Waehler zufrieden genug fuer eine Plumeralitaet.
    with Session(engine) as db:
        session = db.get(GameSession, sid)
        session.turns_until_election = 1
        db.add(session)
        for vg in db.exec(select(VoterGroup).where(VoterGroup.session_id == sid)):
            vg.satisfaction = 60.0
            db.add(vg)
        db.commit()

    resp = client.post(f"/sessions/{sid}/advance", json={"enact_policy_keys": []}).json()
    er = resp["election_result"]
    assert er is not None
    assert er["standings"], "standings muessen im Mehrparteien-Modus gefuellt sein"
    # Rangliste summiert auf ~100 und ist absteigend sortiert.
    total = sum(pct for _, pct in er["standings"])
    assert abs(total - 100.0) < 0.5
    pcts = [pct for _, pct in er["standings"]]
    assert pcts == sorted(pcts, reverse=True)

    won = er["won"]
    party = client.get("/parties").json()
    mine = next(p for p in party if p["id"] == body["party_id"])
    assert mine["terms_played"] == 1
    if won:
        assert mine["reputation"] == 56.0
        assert mine["terms_won"] == 1
    else:
        assert mine["reputation"] == 42.0
        assert mine["terms_won"] == 0


def test_from_party_starts_new_legislature_with_existing_reputation(client):
    body = _new_party(client, name="Kontinuitaetspartei", ideology="red")
    party_id = body["party_id"]

    # Ruf direkt anheben (statt einen vollen Zyklus zu spielen).
    with Session(engine) as db:
        p = db.get(Party, party_id)
        p.reputation = 80.0
        db.add(p)
        db.commit()

    resp = client.post(f"/sessions/from-party/{party_id}")
    assert resp.status_code == 200, resp.text
    new_sid = resp.json()["session_id"]
    assert new_sid != body["session_id"]

    state = client.get(f"/sessions/{new_sid}").json()
    assert state["party_reputation"] == 80.0
    assert len(state["rival_parties"]) == 3


def test_from_party_unknown_id_returns_404(client):
    resp = client.post("/sessions/from-party/999999")
    assert resp.status_code == 404
