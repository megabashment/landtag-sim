"""Fraktionen im Landtag pro Session (B8 "Fraktions-/Sitz-Datenmodell",
BACKLOG.md, L8).

**Nur Struktur, noch keine Mechanik** -- im MVP rein zur Anzeige
("Sitzverteilung im Landtag"). Es gibt bewusst KEINE Koalitionslogik und
KEINEN Mehrheitszwang fuer Policies; Opposition-Gameplay ist ein eigener,
spaeterer Backlog-Punkt. Das Datenmodell wird jetzt schon richtig angelegt,
damit ein spaeterer Ausbau nicht rueckwirkend brechen muss (vgl.
docs/architecture.md, "nicht rueckwirkend aendern").

Per-Session gehalten (analog VoterGroup) -- beim Anlegen einer Session aus
landtag_sim.sample_data.SAMPLE_FACTIONS geseedet.
"""
from sqlmodel import Field, SQLModel


class Faction(SQLModel, table=True):
    __tablename__ = "faction"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="game_session.id", index=True)
    name: str  # z.B. "Sozialdemokratische Fraktion"
    seats: int  # Sitze im Landtag dieser Session

    # Grobe Haltung auf den drei Themenachsen, ca. [-1, 1]: negativ = draengt
    # auf weniger staatliche Aktivitaet/Ausgaben, positiv = auf mehr. Reiner
    # Anzeigewert im MVP (keine Sim-Wirkung), siehe landtag_sim.models.Faction.
    stance_economy: float = Field(default=0.0)
    stance_social: float = Field(default=0.0)
    stance_environment: float = Field(default=0.0)
