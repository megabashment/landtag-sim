"""Statistik-Definitionen und Zeitreihen-Werte pro AdminUnit und Spielzug.

Zwei Tabellen statt einer breiten Tabelle mit einer Spalte pro Statistik:
neue Kennzahlen (z.B. beim Hochskalieren auf Nation-Ebene) brauchen dann
keine Schema-Migration, sondern nur eine neue StatisticDefinition-Zeile.
"""
from sqlmodel import Field, SQLModel


class StatisticDefinition(SQLModel, table=True):
    __tablename__ = "statistic_definition"

    key: str = Field(primary_key=True)  # z.B. "unemployment_rate"
    label: str  # Anzeige-Name, z.B. "Arbeitslosenquote"
    unit: str  # z.B. "%", "EUR", "Index 0-100"
    category: str  # z.B. "wirtschaft", "soziales", "umwelt", "politik"
    description: str | None = None


class StatisticValue(SQLModel, table=True):
    __tablename__ = "statistic_value"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="game_session.id", index=True)
    statistic_key: str = Field(foreign_key="statistic_definition.key", index=True)
    turn_number: int = Field(index=True)
    value: float
