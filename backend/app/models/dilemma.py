"""Dilemma-Definitionen (P1-Punkt 'Dilemma-Events mit echten
Entscheidungsoptionen', siehe docs/game-design-roadmap.md).

Gleicher Trigger-Mechanismus wie EventDefinition (trigger_condition), aber
statt eines festen Effekts eine Liste von Optionen -- der Spieler waehlt
aktiv, welches Effekt-Set angewendet wird. Bewusst kein LLM/NLP: prompt_text
und die Options-Labels sind statische, per Regex-Template gerenderte Texte
(siehe sim/landtag_sim/templates.py).
"""
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON


class DilemmaDefinition(SQLModel, table=True):
    __tablename__ = "dilemma_definition"

    key: str = Field(primary_key=True)
    # Gleiches Format wie EventDefinition.trigger_condition:
    # {"statistic_key": "unemployment_rate", "operator": ">", "value": 9.0}
    trigger_condition: dict = Field(sa_column=Column(JSON))
    prompt_text: str
    # Liste von Optionen als JSON, z.B.:
    # [{"key": "option_a", "label": "...", "budget_cost": 40.0,
    #   "effects": [{"statistic_key": "...", "magnitude": -1.0, "delay_turns": 0, "inertia": 1}]}]
    options: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    cooldown_turns: int = Field(default=8)
