from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import EnactedPolicy, GameSession, PolicyDefinition, VoterGroup
from app.models import StatisticValue
from app.models.game import SessionStatus
from app.schemas.game import (
    AdvanceTurnRequest,
    AdvanceTurnResponse,
    AttributionOut,
    CreateSessionResponse,
    DilemmaOptionOut,
    ElectionResultOut,
    PendingDilemmaOut,
    PolicyEffectOut,
    PolicyOut,
    PreviewRequest,
    PreviewResponse,
    ResolveDilemmaRequest,
    ResolveDilemmaResponse,
    SessionStateResponse,
)
from app.seed import ensure_niedersachsen, run_all_seeds
from app.sim_bridge import (
    load_dilemma_rules,
    load_event_rules,
    load_policy_catalog,
    load_sim_state,
    persist_sim_state,
    serialize_pending_dilemma,
)
from landtag_sim.engine import advance_turn, resolve_dilemma
from landtag_sim.models import DilemmaPendingError, InsufficientCapitalError, UnmetPrerequisiteError
from landtag_sim.sample_data import SAMPLE_VOTER_GROUPS, jittered_starting_statistics

router = APIRouter(tags=["game"])


@router.get("/policies", response_model=list[PolicyOut])
def list_policies(db: Session = Depends(get_session)) -> list[PolicyOut]:
    """Dynamischer Policy-Katalog (behebt eine in README.md/CLAUDE.md
    dokumentierte 'Bekannte Vereinfachung'): das Frontend hatte bisher eine
    hart codierte Kopie von sample_data.py::SAMPLE_POLICIES
    (AVAILABLE_POLICIES in App.jsx), die von Hand synchron gehalten werden
    musste. Seeds laufen hier genauso wie in create_session, damit der
    Katalog auch VOR der ersten Session abrufbar ist (z.B. fuer eine
    zukuenftige Startseite mit Policy-Uebersicht)."""
    run_all_seeds(db)
    rows = db.exec(select(PolicyDefinition)).all()
    return [
        PolicyOut(
            key=row.key,
            name=row.name,
            description=row.description,
            category=row.category,
            one_time_cost=row.one_time_cost,
            upkeep_cost=row.upkeep_cost,
            capital_cost=row.capital_cost,
            effects=[PolicyEffectOut(**effect) for effect in row.effects],
            requires=list(row.requires),
        )
        for row in rows
    ]


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(db: Session = Depends(get_session)) -> CreateSessionResponse:
    run_all_seeds(db)
    admin_unit = ensure_niedersachsen(db)

    session = GameSession(admin_unit_id=admin_unit.id, budget=1000.0, current_turn=0)
    db.add(session)
    db.commit()
    db.refresh(session)

    # P2-Punkt "Randomisierte Startbedingungen" (docs/game-design-roadmap.md):
    # kleine Zufallsstreuung pro echter Session, damit nicht jede Partie mit
    # exakt identischen Zahlen beginnt. Tests/Balance-Runner nutzen bewusst
    # weiterhin die unrandomisierte build_initial_state()/STARTING_STATISTICS.
    for stat_key, value in jittered_starting_statistics().items():
        db.add(StatisticValue(session_id=session.id, statistic_key=stat_key, turn_number=0, value=value))

    for vg in SAMPLE_VOTER_GROUPS:
        db.add(
            VoterGroup(
                session_id=session.id,
                name=vg.name,
                population_share=vg.population_share,
                satisfaction=vg.satisfaction,
                weight_economy=vg.weight_economy,
                weight_social=vg.weight_social,
                weight_environment=vg.weight_environment,
            )
        )
    db.commit()

    return CreateSessionResponse(
        session_id=session.id, admin_unit=admin_unit.name, turn=session.current_turn, budget=session.budget
    )


def _pending_dilemma_out(session: GameSession) -> PendingDilemmaOut | None:
    if not session.pending_dilemma:
        return None
    data = session.pending_dilemma
    return PendingDilemmaOut(
        rule_key=data["rule_key"],
        prompt=data["prompt"],
        options=[
            DilemmaOptionOut(key=o["key"], label=o["label"], budget_cost=o.get("budget_cost", 0.0))
            for o in data["options"]
        ],
    )


def _load_state_for_session(db: Session, session: GameSession):
    return load_sim_state(
        db,
        session.id,
        session.current_turn,
        session.budget,
        session.political_capital,
        session.turns_until_election,
        session.event_cooldowns,
        session.dilemma_cooldowns,
        session.pending_dilemma,
    )


def _build_state_response(db: Session, session: GameSession) -> SessionStateResponse:
    sim_state = _load_state_for_session(db, session)
    active_keys = [ep.policy_key for ep in db.exec(
        select(EnactedPolicy).where(EnactedPolicy.session_id == session.id, EnactedPolicy.active == True)  # noqa: E712
    )]
    return SessionStateResponse(
        session_id=session.id,
        turn=session.current_turn,
        budget=session.budget,
        political_capital=session.political_capital,
        turns_until_election=session.turns_until_election,
        status=session.status,
        statistics=sim_state.statistics,
        voter_groups=[vars(g) for g in sim_state.voter_groups],
        active_policy_keys=active_keys,
        pending_dilemma=_pending_dilemma_out(session),
    )


@router.get("/sessions/{session_id}", response_model=SessionStateResponse)
def get_session_state(session_id: int, db: Session = Depends(get_session)) -> SessionStateResponse:
    session = db.get(GameSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")
    return _build_state_response(db, session)


def _validate_policy_keys(db: Session, keys: list[str]) -> None:
    for key in keys:
        if not db.get(PolicyDefinition, key):
            raise HTTPException(status_code=400, detail=f"Unbekannter Policy-Key: {key}")


@router.post("/sessions/{session_id}/preview", response_model=PreviewResponse)
def preview_session_turn(
    session_id: int, body: PreviewRequest, db: Session = Depends(get_session)
) -> PreviewResponse:
    """P0-Punkt 'Effekt-Vorschau vor Entscheidung' (docs/game-design-roadmap.md):
    simuliert `advance_turn` mit den ausgewaehlten Policies, persistiert aber
    NICHTS -- kein persist_sim_state, kein Commit. Die Sim-Engine ist
    ohnehin eine reine Funktion (siehe sim/landtag_sim/engine.py), Preview ist
    im Kern nur ein verworfener Aufruf.

    Nicht durchfuehrbare Kombinationen (Political Capital, fehlende
    Policy-Voraussetzung, offenes Dilemma) werden NICHT als HTTP-Fehler
    behandelt, sondern als `feasible=False` mit Begruendung zurueckgegeben --
    das Frontend ruft diesen Endpunkt bei JEDER Aenderung der Auswahl auf,
    ein 400er waere hier reines Rauschen.
    """
    session = db.get(GameSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")

    _validate_policy_keys(db, body.enact_policy_keys)

    if session.pending_dilemma:
        return PreviewResponse(
            feasible=False,
            infeasible_reason="Ein offenes Dilemma muss zuerst aufgeloest werden.",
            capital_required=0.0,
            capital_available=session.political_capital,
            statistic_deltas={},
            attributions=[],
            would_trigger_events=[],
            would_trigger_dilemma=False,
            satisfaction_delta_by_group={},
        )

    policy_catalog = load_policy_catalog(db)
    event_rules = load_event_rules(db)
    dilemma_rules = load_dilemma_rules(db)
    sim_state = _load_state_for_session(db, session)

    policy_by_key = {p.key: p for p in policy_catalog}
    capital_required = sum(policy_by_key[k].capital_cost for k in body.enact_policy_keys if k in policy_by_key)
    capital_available = min(10.0, sim_state.political_capital + 3.0)  # CAPITAL_CAP/CAPITAL_PER_TURN, siehe engine.py

    try:
        result = advance_turn(sim_state, policy_catalog, event_rules, body.enact_policy_keys, dilemma_rules)
    except InsufficientCapitalError as exc:
        return PreviewResponse(
            feasible=False,
            infeasible_reason=f"Political Capital reicht nicht: benoetigt {exc.required}, verfuegbar {exc.available}.",
            capital_required=exc.required,
            capital_available=exc.available,
            statistic_deltas={},
            attributions=[],
            would_trigger_events=[],
            would_trigger_dilemma=False,
            satisfaction_delta_by_group={},
        )
    except UnmetPrerequisiteError as exc:
        return PreviewResponse(
            feasible=False,
            infeasible_reason=f"Policy '{exc.policy_key}' braucht zuerst '{exc.missing_requirement}' als aktive Policy.",
            capital_required=capital_required,
            capital_available=capital_available,
            statistic_deltas={},
            attributions=[],
            would_trigger_events=[],
            would_trigger_dilemma=False,
            satisfaction_delta_by_group={},
        )

    statistic_deltas: dict[str, float] = {}
    for key, after_value in result.state.statistics.items():
        before_value = sim_state.statistics.get(key, 0.0)
        delta = after_value - before_value
        if delta:
            statistic_deltas[key] = delta

    before_by_name = {g.name: g.satisfaction for g in sim_state.voter_groups}
    satisfaction_delta_by_group = {
        g.name: g.satisfaction - before_by_name.get(g.name, g.satisfaction) for g in result.state.voter_groups
    }

    return PreviewResponse(
        feasible=True,
        infeasible_reason=None,
        capital_required=capital_required,
        capital_available=capital_available,
        statistic_deltas=statistic_deltas,
        attributions=[
            AttributionOut(source=a.source, statistic_key=a.statistic_key, delta=a.delta) for a in result.attributions
        ],
        would_trigger_events=result.events,
        would_trigger_dilemma=result.pending_dilemma is not None,
        satisfaction_delta_by_group=satisfaction_delta_by_group,
    )


@router.post("/sessions/{session_id}/advance", response_model=AdvanceTurnResponse)
def advance_session_turn(
    session_id: int, body: AdvanceTurnRequest, db: Session = Depends(get_session)
) -> AdvanceTurnResponse:
    session = db.get(GameSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")

    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"Session ist beendet (Status: {session.status.value}) -- keine weiteren Runden moeglich",
        )

    if session.pending_dilemma:
        raise HTTPException(
            status_code=400,
            detail="Ein offenes Dilemma muss zuerst aufgeloest werden (POST /sessions/{id}/resolve-dilemma)",
        )

    _validate_policy_keys(db, body.enact_policy_keys)

    policy_catalog = load_policy_catalog(db)
    event_rules = load_event_rules(db)
    dilemma_rules = load_dilemma_rules(db)
    sim_state = _load_state_for_session(db, session)

    try:
        result = advance_turn(sim_state, policy_catalog, event_rules, body.enact_policy_keys, dilemma_rules)
    except InsufficientCapitalError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Nicht genug Political Capital: benoetigt {exc.required}, verfuegbar {exc.available}",
        ) from exc
    except UnmetPrerequisiteError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Policy '{exc.policy_key}' braucht zuerst '{exc.missing_requirement}' als aktive Policy",
        ) from exc
    except DilemmaPendingError as exc:  # defensiv -- oben bereits per session.pending_dilemma abgefangen
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_state = result.state

    for key in body.enact_policy_keys:
        db.add(EnactedPolicy(session_id=session.id, policy_key=key, enacted_turn=new_state.turn))

    persist_sim_state(db, session.id, new_state)

    session.current_turn = new_state.turn
    session.budget = new_state.budget
    session.political_capital = new_state.political_capital
    session.turns_until_election = new_state.turns_until_election
    session.event_cooldowns = dict(new_state.event_cooldowns)
    session.dilemma_cooldowns = dict(new_state.dilemma_cooldowns)
    session.pending_dilemma = serialize_pending_dilemma(new_state.pending_dilemma)

    election_out: ElectionResultOut | None = None
    if result.election_result:
        election_out = ElectionResultOut(
            approval=result.election_result.approval,
            threshold=result.election_result.threshold,
            won=result.election_result.won,
        )
        # Wahlmechanik (P0, siehe docs/game-design-roadmap.md): verlorene Wahl
        # beendet die Session (kein weiteres /advance moeglich, siehe Check
        # oben). Gewonnene Wahl setzt NICHT auf WON, sondern die Session
        # bleibt ACTIVE -- Wiederwahl bedeutet Weiterspielen im naechsten
        # Zyklus, das Spiel endet nicht automatisch beim Gewinnen.
        session.status = SessionStatus.ACTIVE if result.election_result.won else SessionStatus.LOST

    db.add(session)
    db.commit()

    return AdvanceTurnResponse(
        state=_build_state_response(db, session),
        events=result.events,
        attributions=[
            AttributionOut(source=a.source, statistic_key=a.statistic_key, delta=a.delta) for a in result.attributions
        ],
        election_result=election_out,
        pending_dilemma=_pending_dilemma_out(session),
    )


@router.post("/sessions/{session_id}/resolve-dilemma", response_model=ResolveDilemmaResponse)
def resolve_session_dilemma(
    session_id: int, body: ResolveDilemmaRequest, db: Session = Depends(get_session)
) -> ResolveDilemmaResponse:
    """P1-Punkt 'Dilemma-Events mit echten Entscheidungsoptionen': wendet die
    gewaehlte Option eines offenen Dilemmas an. Zaehlt KEINE Runde (siehe
    engine.py::resolve_dilemma) -- Political Capital und Wahl-Countdown
    wurden bereits in der Runde verarbeitet, die das Dilemma ausgeloest hat.
    """
    session = db.get(GameSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")

    if not session.pending_dilemma:
        raise HTTPException(status_code=400, detail="Kein offenes Dilemma fuer diese Session vorhanden")

    dilemma_rules = load_dilemma_rules(db)
    sim_state = _load_state_for_session(db, session)

    try:
        result = resolve_dilemma(sim_state, dilemma_rules, body.option_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    persist_sim_state(db, session.id, result.state)

    session.budget = result.state.budget
    session.event_cooldowns = dict(result.state.event_cooldowns)
    session.dilemma_cooldowns = dict(result.state.dilemma_cooldowns)
    session.pending_dilemma = None

    db.add(session)
    db.commit()

    return ResolveDilemmaResponse(
        state=_build_state_response(db, session),
        attributions=[
            AttributionOut(source=a.source, statistic_key=a.statistic_key, delta=a.delta) for a in result.attributions
        ],
    )
