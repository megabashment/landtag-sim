"""B2: Situations-Layer -- DB-Modell fuer aktive Situations.

Eine Situation ist ein Zustand, der sich selbst verstaerkt (Spirale), mit
Hysterese-Logik (unterschiedliche Aktivierungs- und Deaktivierungs-
Schwellen, siehe BACKLOG.md L2/L3). Persistiert pro GameSession.
"""
from sqlmodel import Field, SQLModel


class ActiveSituation(SQLModel, table=True):
    __tablename__ = "active_situation"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="game_session.id")
    rule_key: str  # referenziert SituationRule.key aus sample_data.py
    since_turn: int  # Runde, in der diese Situation aktiviert wurde
