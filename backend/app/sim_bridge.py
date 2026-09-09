"""Uebersetzt zwischen DB-Modellen (app.models, Postgres) und der reinen
Sim-Engine (landtag_sim, kein DB-Bezug). Bewusst als einzelner Ort, damit
sich das Sim-Datenformat und das DB-Schema unabhaengig voneinander
weiterentwickeln koennen (siehe sim/README bzw. docs/architecture.md).
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models import (
    EnactedPolicy as DbEnactedPolicy,
)
from app.models import (
    DilemmaDefinition,
    EventDefinition,
    PolicyDefinition,
    StatisticValue,
    VoterGroup as DbVoterGroup,
)
from landtag_sim.models import (
    EnactedPolicy as SimEnactedPolicy,
)
from landtag_sim.models import (
    DilemmaOption,
    DilemmaRule,
    EventRule,
    PendingDilemma,
    Policy,
    PolicyEffect,
    SimState,
    VoterGroup as SimVoterGroup,
)


def load_policy_catalog(db: Session) -> list[Policy]:
    rows = db.exec(select(PolicyDefinition)).all()
    return [
        Policy(
            key=row.key,
            name=row.name,
            one_time_cost=row.one_time_cost,
            upkeep_cost=row.upkeep_cost,
            capital_cost=row.capital_cost,
            income_per_turn=row.income_per_turn,
            effects=[PolicyEffect(**effect) for effect in row.effects],
            requires=list(row.requires),
        )
        for row in rows
    ]


def load_event_rules(db: Session) -> list[EventRule]:
    rows = db.exec(select(EventDefinition)).all()
    rules = []
    for row in rows:
        cond = row.trigger_condition
        rules.append(
            EventRule(
                key=row.key,
                statistic_key=cond["statistic_key"],
                operator=cond["operator"],
                threshold=cond["value"],
                template_text=row.template_text,
                cooldown_turns=row.cooldown_turns,
                effects=[PolicyEffect(**effect) for effect in row.effects],
            )
        )
    return rules


def load_dilemma_rules(db: Session) -> list[DilemmaRule]:
    rows = db.exec(select(DilemmaDefinition)).all()
    rules = []
    for row in rows:
        cond = row.trigger_condition
        rules.append(
            DilemmaRule(
                key=row.key,
                statistic_key=cond["statistic_key"],
                operator=cond["operator"],
                threshold=cond["value"],
                prompt_text=row.prompt_text,
                cooldown_turns=row.cooldown_turns,
                options=[_dilemma_option_from_dict(option) for option in row.options],
            )
        )
    return rules


def _dilemma_option_from_dict(data: dict) -> DilemmaOption:
    return DilemmaOption(
        key=data["key"],
        label=data["label"],
        budget_cost=data.get("budget_cost", 0.0),
        effects=[PolicyEffect(**effect) for effect in data.get("effects", [])],
    )


def _dilemma_option_to_dict(option: DilemmaOption) -> dict:
    return {
        "key": option.key,
        "label": option.label,
        "budget_cost": option.budget_cost,
        "effects": [vars(effect) for effect in option.effects],
    }


def serialize_pending_dilemma(pending: PendingDilemma | None) -> dict | None:
    """PendingDilemma -> JSON-faehiges Dict fuer GameSession.pending_dilemma.

    Persistiert den VOLLSTAENDIG gerenderten Zustand (inkl. Prompt-Text mit
    dem Statistik-Wert zum Ausloese-Zeitpunkt), nicht nur den Dilemma-Key --
    der Prompt darf sich nicht aendern, nur weil sich die Statistik zwischen
    Ausloesen und Aufloesen weiterbewegt hat."""
    if pending is None:
        return None
    return {
        "rule_key": pending.rule_key,
        "prompt": pending.prompt,
        "options": [_dilemma_option_to_dict(o) for o in pending.options],
    }


def deserialize_pending_dilemma(data: dict | None) -> PendingDilemma | None:
    if data is None:
        return None
    return PendingDilemma(
        rule_key=data["rule_key"],
        prompt=data["prompt"],
        options=[_dilemma_option_from_dict(o) for o in data["options"]],
    )


def load_sim_state(
    db: Session,
    session_id: int,
    turn: int,
    budget: float,
    political_capital: float,
    turns_until_election: int = 16,
    event_cooldowns: dict[str, int] | None = None,
    dilemma_cooldowns: dict[str, int] | None = None,
    pending_dilemma: dict | None = None,
) -> SimState:
    latest_values: dict[str, float] = {}
    for row in db.exec(
        select(StatisticValue)
        .where(StatisticValue.session_id == session_id)
        # Sekundaersortierung nach id: mehrere StatisticValue-Zeilen koennen
        # denselben turn_number teilen (z.B. eine Dilemma-Aufloesung schreibt
        # neue Werte, OHNE die Runde zu erhoehen, siehe engine.py::
        # resolve_dilemma) -- ohne Tiebreaker ist die Reihenfolge gleicher
        # turn_number-Werte nicht garantiert, wodurch "letzter Wert gewinnt"
        # zufaellig den falschen Wert haette erwischen koennen.
        .order_by(StatisticValue.turn_number, StatisticValue.id)
    ):
        latest_values[row.statistic_key] = row.value  # letzter Wert pro Key gewinnt

    voter_groups = [
        SimVoterGroup(
            name=vg.name,
            population_share=vg.population_share,
            satisfaction=vg.satisfaction,
            weight_economy=vg.weight_economy,
            weight_social=vg.weight_social,
            weight_environment=vg.weight_environment,
            # P2-Punkt "Zufriedenheits-Momentum/Glaettung": muss geladen werden,
            # sonst "vergisst" die Session den nachklingenden Ueberhang bei
            # jedem Neuladen (siehe engine.py::_apply_reaction).
            satisfaction_momentum=vg.satisfaction_momentum,
        )
        for vg in db.exec(select(DbVoterGroup).where(DbVoterGroup.session_id == session_id))
    ]

    # WICHTIG: bewusst ALLE Zeilen laden, nicht nur die noch aktiven --
    # eine zurueckgezogene Policy (repealed_turn gesetzt) braucht ihren
    # enacted_turn/repealed_turn weiterhin, damit ihre Wirkung beim naechsten
    # Laden korrekt weiter abklingt (siehe landtag_sim.engine.py::
    # _effect_delta). Der State wird bei JEDEM API-Request frisch aus der DB
    # aufgebaut -- ein Filtern auf "aktiv" wuerde das Abkling-Gedaechtnis
    # jeder reparierten Policy sofort und dauerhaft verlieren.
    active_policies = [
        SimEnactedPolicy(policy_key=ep.policy_key, enacted_turn=ep.enacted_turn, repealed_turn=ep.repealed_turn)
        for ep in db.exec(select(DbEnactedPolicy).where(DbEnactedPolicy.session_id == session_id))
    ]

    return SimState(
        turn=turn,
        budget=budget,
        statistics=latest_values,
        voter_groups=voter_groups,
        active_policies=active_policies,
        political_capital=political_capital,
        turns_until_election=turns_until_election,
        event_cooldowns=dict(event_cooldowns or {}),
        dilemma_cooldowns=dict(dilemma_cooldowns or {}),
        pending_dilemma=deserialize_pending_dilemma(pending_dilemma),
    )


def persist_sim_state(db: Session, session_id: int, new_state: SimState) -> None:
    """Schreibt Statistik-Zeitreihe, Zufriedenheit und Budget/Runde zurueck.

    Cooldowns, Political Capital, Wahl-Countdown und offenes Dilemma sind
    reine Session-Felder (siehe app.models.game.GameSession) und werden vom
    Aufrufer (Route) direkt auf das GameSession-Objekt geschrieben, analog zu
    session.political_capital -- diese Funktion bleibt auf die Zeitreihen-
    und Waehlergruppen-Tabellen beschraenkt.

    Hinweis: `db.commit()` liegt bewusst beim Aufrufer (Route), damit ein
    Fehler nach diesem Schritt (z.B. beim Event-Log) die ganze Runde
    zurueckrollt statt einen halb geschriebenen State zu hinterlassen.
    """
    for stat_key, value in new_state.statistics.items():
        db.add(StatisticValue(session_id=session_id, statistic_key=stat_key, turn_number=new_state.turn, value=value))

    db_groups = db.exec(select(DbVoterGroup).where(DbVoterGroup.session_id == session_id)).all()
    by_name = {vg.name: vg for vg in db_groups}
    for sim_group in new_state.voter_groups:
        db_group = by_name.get(sim_group.name)
        if db_group:
            db_group.satisfaction = sim_group.satisfaction
            db_group.satisfaction_momentum = sim_group.satisfaction_momentum
            db.add(db_group)
