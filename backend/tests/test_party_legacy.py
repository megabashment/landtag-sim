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
    # "Demokratie-Drama"-Pass (2026-09-13): jede Rivalen-Partei hat einen
    # Fraktionsvorsitzenden-Namen fuer die Oppositions-Zitate (siehe
    # opposition_voices.py) -- kein leerer String.
    assert all(r["leader_name"] for r in rivals)


def test_opposition_reaction_appears_when_rivals_axis_worsens(client):
    """bildungsoffensive senkt gdp_growth (economy) stark -- die blaue
    Wirtschaftsunion muss irgendwann in den ersten Runden per Zitat
    reagieren (siehe opposition_voices.py)."""
    body = _new_party(client, name="Reaktionstest", ideology="green")
    sid = body["session_id"]

    reactions = []
    resp = client.post(f"/sessions/{sid}/advance", json={"enact_policy_keys": ["bildungsoffensive"]})
    assert resp.status_code == 200
    reactions.append(resp.json()["opposition_reaction"])
    for _ in range(4):
        resp = client.post(f"/sessions/{sid}/advance", json={})
        if resp.status_code == 400:
            pending = client.get(f"/sessions/{sid}").json()["pending_dilemma"]
            if pending:
                client.post(f"/sessions/{sid}/resolve-dilemma", json={"option_key": pending["options"][0]["key"]})
            continue
        reactions.append(resp.json()["opposition_reaction"])

    assert any(r is not None for r in reactions), "Erwartete mindestens ein Oppositions-Zitat"
    fired = next(r for r in reactions if r is not None)
    assert "Wirtschaftsunion" in fired


def test_election_result_carries_a_headline(client):
    """Fortsetzung "Demokratie-Drama"-Pass ("mach weiter", 2026-09-14): die
    Wahlnacht bekommt eine Schlagzeile, siehe election_drama.py."""
    body = _new_party(client, name="Wahlnachttest", ideology="red")
    sid = body["session_id"]

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
    assert er["headline"] != ""


def test_citizen_voice_appears_when_a_group_is_extremely_dissatisfied(client, session_id):
    """Fortsetzung "Demokratie-Drama"-Pass ("mach es noch lebendiger",
    2026-09-13): eine extrem unzufriedene Waehlergruppe muss per Zitat
    zu Wort kommen -- auch im klassischen Modus ohne Rivalen-Parteien
    (siehe citizen_voices.py)."""
    with Session(engine) as db:
        group = db.exec(select(VoterGroup).where(VoterGroup.session_id == session_id)).first()
        group.satisfaction = 3.0
        db.add(group)
        db.commit()

    resp = client.post(f"/sessions/{session_id}/advance", json={})
    assert resp.status_code == 200
    assert resp.json()["citizen_voice"] is not None


def test_advance_response_exposes_wildcard_event_field(client, session_id):
    """wildcard_event ist immer im Response-Body vorhanden (haeufig None,
    siehe wildcard_events.py) -- reiner Vertrags-/Serialisierungstest."""
    resp = client.post(f"/sessions/{session_id}/advance", json={})
    assert resp.status_code == 200
    assert "wildcard_event" in resp.json()


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


def test_party_detail_reports_full_term_history(client):
    """B28 "Advanced UI" (M7_SPRINT_PLAN.md): GET /parties/{id}/detail liefert
    die komplette Term-Historie inkl. reputation_delta/reputation_after --
    nicht nur die Zaehlwerte wie GET /parties."""
    body = _new_party(client, name="Detailpartei", ideology="blue")
    sid = body["session_id"]
    party_id = body["party_id"]

    with Session(engine) as db:
        session = db.get(GameSession, sid)
        session.turns_until_election = 1
        db.add(session)
        for vg in db.exec(select(VoterGroup).where(VoterGroup.session_id == sid)):
            vg.satisfaction = 60.0
            db.add(vg)
        db.commit()

    resp = client.post(f"/sessions/{sid}/advance", json={"enact_policy_keys": []}).json()
    won = resp["election_result"]["won"]

    detail = client.get(f"/parties/{party_id}/detail")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == party_id
    assert body["name"] == "Detailpartei"
    assert body["ideology"] == "blue"
    assert len(body["terms"]) == 1

    term = body["terms"][0]
    assert term["turn"] == 1  # turns_until_election wurde oben auf 1 gesetzt
    assert term["won"] == won
    if won:
        assert term["reputation_delta"] == 6.0
        assert term["reputation_after"] == 56.0
    else:
        assert term["reputation_delta"] == -8.0
        assert term["reputation_after"] == 42.0
    assert body["reputation"] == term["reputation_after"]


def test_party_detail_of_fresh_party_has_empty_terms(client):
    """Eine frisch gegruendete Partei (noch keine abgeschlossene
    Legislaturperiode) hat eine leere Term-Liste, aber existiert (kein 404)."""
    body = _new_party(client, name="Frischling", ideology="red")
    detail = client.get(f"/parties/{body['party_id']}/detail")
    assert detail.status_code == 200
    assert detail.json()["terms"] == []
    assert detail.json()["reputation"] == 50.0


def test_party_detail_unknown_id_returns_404(client):
    resp = client.get("/parties/999999/detail")
    assert resp.status_code == 404


def test_from_party_unknown_id_returns_404(client):
    resp = client.post("/sessions/from-party/999999")
    assert resp.status_code == 404
