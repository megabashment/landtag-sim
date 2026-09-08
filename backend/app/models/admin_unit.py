"""Verwaltungsebene: Region (MVP: Niedersachsen) -> Nation -> EU.

Selbstreferenzierende Hierarchie, damit spaeteres Hochskalieren (siehe
docs/architecture.md) keine neue Tabelle braucht, sondern nur neue Zeilen:
z.B. AdminUnit(name="Niedersachsen", level=REGION, parent=Deutschland),
AdminUnit(name="Deutschland", level=NATION, parent=EU).
"""
from enum import Enum

from sqlmodel import Field, SQLModel


class AdminLevel(str, Enum):
    REGION = "region"          # Bundesland / Kanton / Provinz
    NATION = "nation"          # spaetere Skalierungsstufe
    SUPRANATIONAL = "supranational"  # z.B. EU, spaetere Skalierungsstufe


class AdminUnit(SQLModel, table=True):
    __tablename__ = "admin_unit"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    level: AdminLevel
    parent_id: int | None = Field(default=None, foreign_key="admin_unit.id")

    # ISO/Statistik-Referenzcode, z.B. "DE-NI" fuer Niedersachsen (ISO 3166-2).
    # Wird zum Verknuepfen mit externen Datenquellen (Destatis, Natural Earth) genutzt.
    external_code: str | None = Field(default=None, index=True)
