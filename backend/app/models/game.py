"""Eine Spielpartie (Session), verknuepft mit genau einer AdminUnit.

MVP: admin_unit ist immer Niedersachsen. Die Fremdschluessel-Struktur
erlaubt aber schon jetzt eine Session auf Nation- oder EU-Ebene, sobald
dort Daten vorhanden sind (siehe docs/architecture.md, Skalierungspfad).
"""
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON


class SessionStatus(str, Enum):
    ACTIVE = "active"
    WON = "won"
    LOST = "lost"  # z.B. Wahl verloren oder Budget-Kollaps


class GameSession(SQLModel, table=True):
    __tablename__ = "game_session"

    id: int | None = Field(default=None, primary_key=True)
    admin_unit_id: int = Field(foreign_key="admin_unit.id")
    name: str = Field(default="Neue Partie")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    current_turn: int = Field(default=0)
    budget: float = Field(default=0.0)
    status: SessionStatus = Field(default=SessionStatus.ACTIVE)

    # Zweite Ressource neben dem Budget (nach Game-Director-Review, siehe
    # docs/architecture.md): begrenzt, wie viele Reformen gleichzeitig
    # durchsetzbar sind. Regeneration/Obergrenze siehe sim/landtag_sim/engine.py
    # (CAPITAL_PER_TURN, CAPITAL_CAP).
    political_capital: float = Field(default=10.0)

    # Rundenabstand bis zur naechsten Wahl (MVP: ein voller Zyklus bis zum Ergebnis)
    turns_until_election: int = Field(default=16)

    # P1-Punkt "Dilemma-Events": bisher gab es HIER keine Persistenz fuer
    # Event-Cooldowns -- ein latenter Bug, der beim Einbau der Dilemma-
    # Cooldowns aufgefallen ist (siehe mistakes.md): jede Runde lud
    # sim_bridge.load_sim_state() die Sim-Engine mit einem leeren
    # event_cooldowns-Dict neu, wodurch Cooldowns im laufenden Backend nie
    # wirkten. Jetzt explizit auf der Session gespeichert und bei jedem
    # advance/resolve zurueckgeschrieben.
    event_cooldowns: dict = Field(default_factory=dict, sa_column=Column(JSON))
    dilemma_cooldowns: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # B1 "Legislatur-Bogen & Amtszeit-Debrief" (BACKLOG.md): Schnappschuss der
    # Werte zu Beginn der laufenden Legislaturperiode plus laufende Zaehler.
    # Reine Session-Felder wie turns_until_election -- die Sim-Engine
    # (landtag_sim.engine.advance_turn) baut daraus am Wahl-Turn die
    # TermSummary und setzt sie danach auf den neuen Zyklus zurueck.
    term_start_turn: int = Field(default=0)
    term_start_budget: float = Field(default=0.0)
    term_start_statistics: dict = Field(default_factory=dict, sa_column=Column(JSON))
    term_start_approval: float = Field(default=50.0)
    term_dilemma_count: int = Field(default=0)
    term_event_count: int = Field(default=0)

    # Voll serialisiertes PendingDilemma (rule_key, gerenderter Prompt-Text,
    # Optionen inkl. Effekten) statt nur des Keys -- der Prompt wurde beim
    # Ausloesen mit dem damaligen Statistik-Wert gerendert und darf sich
    # nicht aendern, nur weil sich die Statistik inzwischen weiterbewegt hat.
    pending_dilemma: dict | None = Field(default=None, sa_column=Column(JSON))
