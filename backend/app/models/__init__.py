"""Alle Modelle hier importieren, damit SQLModel.metadata sie beim
create_all()/Alembic-Autogenerate kennt."""
from app.models.admin_unit import AdminLevel, AdminUnit
from app.models.dilemma import DilemmaDefinition
from app.models.event import EventDefinition, EventLog
from app.models.faction import Faction
from app.models.game import GameSession, SessionRole, SessionStatus
from app.models.policy import EnactedPolicy, PolicyDefinition
from app.models.situation import ActiveSituation
from app.models.statistic import StatisticDefinition, StatisticValue
from app.models.voter_group import VoterGroup

__all__ = [
    "AdminLevel",
    "AdminUnit",
    "ActiveSituation",
    "DilemmaDefinition",
    "EventDefinition",
    "EventLog",
    "Faction",
    "GameSession",
    "SessionRole",
    "SessionStatus",
    "EnactedPolicy",
    "PolicyDefinition",
    "StatisticDefinition",
    "StatisticValue",
    "VoterGroup",
]
