"""Regelbasierte Ereignisse: Trigger auf Statistik-Schwellenwerte + Text-Templates.

Bewusst kein LLM/NLP: trigger_condition ist ein kleines, deterministisches
JSON-Ausdrucksformat, das sim/events.py per einfachem Vergleich auswertet.
Die Formulierung kommt aus template_text per Python str.format() bzw. Regex-
Platzhalter-Ersetzung (siehe sim/templates.py).
"""
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON


class EventDefinition(SQLModel, table=True):
    __tablename__ = "event_definition"

    key: str = Field(primary_key=True)
    # Beispiel: {"statistic_key": "unemployment_rate", "operator": ">", "value": 10}
    trigger_condition: dict = Field(sa_column=Column(JSON))
    template_text: str  # z.B. "Die Arbeitslosigkeit erreicht {value:.1f}% - {reaction}."
    # Optionaler direkter Zusatzeffekt des Events (gleiches Format wie Policy-Effekte)
    effects: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    # Verhindert, dass dasselbe Event jede Runde erneut feuert
    cooldown_turns: int = Field(default=5)


class EventLog(SQLModel, table=True):
    __tablename__ = "event_log"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="game_session.id", index=True)
    event_key: str = Field(foreign_key="event_definition.key")
    turn_number: int
    rendered_text: str
