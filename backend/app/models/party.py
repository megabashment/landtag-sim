"""Politische Partei als persistente Entity über mehrere Sessions/Legislaturen hinweg.

MVP: jede Party hat eine Ideologie (Grün/Rot/Blau), die Voter-Affinität modifiziert.
Langfristig skalierbar auf Bundes-/EU-Ebene und Multi-Party-Koalitionen (M6+).
"""
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class PartyIdeology(str, Enum):
    """Ideologische Ausrichtung einer Partei.

    Effekte auf Voter-Affinität:
    - Grün: +20% Umweltbewusste, -5% Wirtschaft-orientiert
    - Rot: +15% Arbeitnehmer, -8% Konservativ-Bürgerliche
    - Blau: +15% Wirtschaft-orientiert, -10% Umweltbewusste
    """
    GREEN = "green"
    RED = "red"
    BLUE = "blue"


class Party(SQLModel, table=True):
    __tablename__ = "party"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    ideology: PartyIdeology
    founded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Basis-Wahlchancen dieser Partei (0-100), modifiziert durch Voter-Zufriedenheit
    base_electability: float = Field(default=50.0)

    # Partei-Reputation (0-100), beeinflusst Koalitionsfähigkeit und Vertrauen
    reputation: float = Field(default=50.0)

    # Flexibles Feld für zukünftige Erweiterungen (Legacy-Tracking, etc.)
    extra_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
