"""B8 "Fraktions-/Sitz-Datenmodell (Grundstein Opposition/Parlament)"
(BACKLOG.md, L8) durch die echte API.

Deckt die reine Struktur ab (Sitzverteilung + Rolle im State) sowie den
hinter dem Flag DEMOTE_TO_OPPOSITION_ON_LOSS liegenden Datenpfad. KEINE
Mechanik -- Koalitionen/Mehrheiten/Opposition-Loop sind explizit Post-M3.
"""
from sqlmodel import Session, select

import app.api.routes_game as routes_game
from app.db import engine
from app.models import GameSession, VoterGroup


def test_state_includes_factions_and_default_role(client, session_id):
    state = client.get(f"/sessions/{session_id}").json()
    assert state["role"] == "government"
    factions = state["factions"]
    assert len(factions) == 5
    assert all(f["seats"] > 0 for f in factions)
    # absteigend nach Sitzen sortiert (siehe _build_state_response)
    seats = [f["seats"] for f in factions]
    assert seats == sorted(seats, reverse=True)
    # Haltungsachsen werden mitgeliefert
    assert {"stance_economy", "stance_social", "stance_environment"} <= set(factions[0])


def _force_losing_election(session_id: int) -> None:
    """Setzt die Session direkt vor eine verlorene Wahl: naechste Runde ist der
    Wahl-Turn, alle Waehlergruppen sind tief unzufrieden -> Zustimmung < 50."""
    with Session(engine) as db:
        session = db.get(GameSession, session_id)
        session.turns_until_election = 1
        db.add(session)
        for vg in db.exec(select(VoterGroup).where(VoterGroup.session_id == session_id)):
            vg.satisfaction = 5.0
            db.add(vg)
        db.commit()


def test_lost_election_ends_game_by_default(client, session_id, monkeypatch):
    monkeypatch.setattr(routes_game, "DEMOTE_TO_OPPOSITION_ON_LOSS", False)
    _force_losing_election(session_id)
    body = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []}).json()
    assert body["election_result"]["won"] is False
    assert body["state"]["status"] == "lost"
    assert body["state"]["role"] == "government"


def test_lost_election_demotes_to_opposition_when_flag_on(client, session_id, monkeypatch):
    monkeypatch.setattr(routes_game, "DEMOTE_TO_OPPOSITION_ON_LOSS", True)
    _force_losing_election(session_id)
    body = client.post(f"/sessions/{session_id}/advance", json={"enact_policy_keys": []}).json()
    assert body["election_result"]["won"] is False
    # Statt Game Over: Session bleibt aktiv, Rolle wechselt in die Opposition.
    assert body["state"]["status"] == "active"
    assert body["state"]["role"] == "opposition"
