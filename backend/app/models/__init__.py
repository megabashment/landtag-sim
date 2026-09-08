"""Alle Modelle hier importieren, damit SQLModel.metadata sie beim
create_all()/Alembic-Autogenerate kennt."""
from app.models.admin_unit import AdminLevel, AdminUnit
from app.models.dilemma import DilemmaDefinition
from app.models.event import EventDefinition, EventLog
from app.models.game import GameSession, SessionStatus
from app.models.policy import EnactedPolicy, PolicyDefinition
from app.models.statistic import StatisticDefinition, StatisticValue
from app.models.voter_group import VoterGroup

__all__ = [
    "AdminLevel",
    "AdminUnit",
    "DilemmaDefinition",
    "EventDefinition",
    "EventLog",
    "GameSession",
    "SessionStatus",
    "EnactedPolicy",
    "PolicyDefinition",
    "StatisticDefinition",
    "StatisticValue",
    "VoterGroup",
]
