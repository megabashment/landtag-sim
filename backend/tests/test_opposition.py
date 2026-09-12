"""B26 "Opposition-Kampagnen UI Verbesserung" (M7_SPRINT_PLAN.md) durch die
echte API.

- GET /opposition-campaigns liefert den Kampagnen-Katalog (ersetzt die
  bisher unbenutzte hart codierte _OPPOSITION_CAMPAIGNS-Konstante im
  Frontend, siehe App.jsx)
- Jede Kampagne ist serialisierbar mit key/name/description/capital_cost/
  satisfaction_deltas
- satisfaction_deltas-Keys entsprechen echten Waehlergruppen-Namen (sonst
  wirkt die Kampagne nicht auf die Koalitionsfaehigkeit, siehe
  engine.py::_calculate_coalition_viability)
"""
from landtag_sim.sample_data import SAMPLE_VOTER_GROUPS


def test_list_opposition_campaigns(client):
    """GET /opposition-campaigns liefert den vollen Kampagnen-Katalog."""
    resp = client.get("/opposition-campaigns")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 4  # Mindestens 4 Sample-Kampagnen

    for campaign in body:
        assert "key" in campaign
        assert "name" in campaign
        assert "description" in campaign
        assert "capital_cost" in campaign
        assert "satisfaction_deltas" in campaign
        assert isinstance(campaign["satisfaction_deltas"], dict)
        assert len(campaign["satisfaction_deltas"]) > 0


def test_opposition_campaign_satisfaction_deltas_target_real_voter_groups(client):
    """Jede Kampagne muss auf echte Waehlergruppen wirken -- sonst geht ihr
    Effekt bei der Koalitionsfaehigkeits-Berechnung ins Leere (siehe
    engine.py::_calculate_coalition_viability, das per `vg.name` nachschlaegt)."""
    resp = client.get("/opposition-campaigns")
    assert resp.status_code == 200
    known_group_names = {g.name for g in SAMPLE_VOTER_GROUPS}

    for campaign in resp.json():
        for group_name in campaign["satisfaction_deltas"]:
            assert group_name in known_group_names, (
                f"Kampagne '{campaign['key']}' zielt auf unbekannte Gruppe '{group_name}'"
            )


def test_opposition_campaign_keys_are_unique(client):
    """Keine doppelten Kampagnen-Keys (waere sonst mehrdeutig beim Anwenden
    per opposition_campaign_key in POST /sessions/{id}/advance)."""
    resp = client.get("/opposition-campaigns")
    keys = [c["key"] for c in resp.json()]
    assert len(keys) == len(set(keys))
