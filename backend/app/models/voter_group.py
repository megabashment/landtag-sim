"""Waehlergruppen pro Session — vereinfachtes Democracy-Modell.

Statt eines vollen Ideologie-Vektors starten wir mit wenigen, klar
gewichteten Achsen. Das laesst sich spaeter erweitern, ohne bestehende
Partien zu brechen (neue Spalten mit Defaultwert).
"""
from sqlmodel import Field, SQLModel


class VoterGroup(SQLModel, table=True):
    __tablename__ = "voter_group"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="game_session.id", index=True)
    name: str  # z.B. "Landwirtschaft", "Industriearbeiter", "Staedtische Mitte"
    population_share: float  # 0.0 - 1.0, Anteil an Waehlerschaft

    # Aktuelle Zufriedenheit dieser Gruppe, 0-100. Wird jede Runde durch die
    # Sim-Engine (sim/engine.py) auf Basis wirksamer Policy-Effekte aktualisiert.
    satisfaction: float = Field(default=50.0)

    # Grobe Gewichtung, wie stark diese Gruppe auf oekonomische vs. soziale
    # vs. oekologische Themen reagiert (Summe muss nicht 1 ergeben, dient als
    # relativer Multiplikator in der Sim-Engine).
    weight_economy: float = Field(default=1.0)
    weight_social: float = Field(default=1.0)
    weight_environment: float = Field(default=1.0)

    # P2-Punkt "Zufriedenheits-Momentum/Glaettung" (docs/game-design-roadmap.md):
    # gleitender Durchschnitt der Zufriedenheitsreaktion, siehe
    # sim/landtag_sim/models.py::VoterGroup / engine.py::_apply_reaction.
    # Muss ueber Restarts hinweg persistiert werden, sonst "vergisst" eine
    # Session bei jedem Neuladen den nachklingenden Ueberhang.
    satisfaction_momentum: float = Field(default=0.0)

    # B23 Phase 3 Erweiterung: Wählergruppen-Ideologie-Affinität.
    # `ideology_preference` (grün/rot/blau/None): die Ideologie, die diese Gruppe bevorzugt (+20% Bonus)
    # `ideology_dislike` (grün/rot/blau/None): die Ideologie, die diese Gruppe ablehnt (-5% Malus)
    ideology_preference: str | None = Field(default=None)
    ideology_dislike: str | None = Field(default=None)
