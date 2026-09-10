from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import EnactedPolicy, Faction, GameSession, PolicyDefinition, VoterGroup
from app.models import StatisticValue
from app.models.game import SessionRole, SessionStatus
from app.schemas.game import (
    AdvanceTurnRequest,
    AdvanceTurnResponse,
    AttributionOut,
    CreateSessionResponse,
    DilemmaOptionOut,
    ElectionProjectionGroupOut,
    ElectionProjectionOut,
    ElectionResultOut,
    FactionOut,
    GoalResultOut,
    PendingDilemmaOut,
    PolicyEffectOut,
    PolicyOut,
    PreviewRequest,
    PreviewResponse,
    ResolveDilemmaRequest,
    ResolveDilemmaResponse,
    SessionStateResponse,
    TermSummaryOut,
    UnlockConditionOut,
)
from app.seed import ensure_niedersachsen, run_all_seeds
from app.sim_bridge import (
    load_dilemma_rules,
    load_event_rules,
    load_policy_catalog,
    load_report_rules,
    load_scenario_goals,
    load_sim_state,
    persist_sim_state,
    serialize_pending_dilemma,
)
from landtag_sim.engine import advance_turn, project_election, resolve_dilemma
from landtag_sim.models import (
    DilemmaPendingError,
    InsufficientCapitalError,
    PolicyAlreadyActiveError,
    PolicyLockedError,
    PolicyNotActiveError,
    PolicyRequiredByActivePolicyError,
    UnmetPrerequisiteError,
)
from landtag_sim.sample_data import SAMPLE_FACTIONS, SAMPLE_VOTER_GROUPS, jittered_starting_statistics

router = APIRouter(tags=["game"])

# B5 "Wahlprognose mit sichtbarem Turnout/Apathie" (BACKLOG.md): die
# Vorausschau wird erst in den letzten Runden vor der Wahl mitgeliefert --
# vorher waere sie nur Rauschen und wuerde die Spannung nehmen.
ELECTION_PROJECTION_WINDOW = 5

# B8 "Fraktions-/Sitz-Datenmodell" (BACKLOG.md, L8): wenn True, wird eine
# verlorene Wahl NICHT zu SessionStatus.LOST (Game Over), sondern die Session
# bleibt ACTIVE und wechselt in die Opposition (role=OPPOSITION). Default aus
# -- es gibt im MVP noch KEINEN Opposition-Gameplay-Loop (das ist ein eigener
# spaeterer Backlog-Punkt); das Flag verdrahtet nur den Datenpfad, damit der
# spaetere Ausbau nicht rueckwirkend brechen muss.
DEMOTE_TO_OPPOSITION_ON_LOSS = False


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
            income_per_turn=row.income_per_turn,
            effects=[PolicyEffectOut(**effect) for effect in row.effects],
            requires=list(row.requires),
            unlock_conditions=[UnlockConditionOut(**c) for c in (row.unlock_conditions or [])],  # B7
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

    # B8: Sitzverteilung im Landtag pro Session seeden (reine Anzeige-Daten,
    # noch keine Mechanik -- siehe app/models/faction.py).
    for f in SAMPLE_FACTIONS:
        db.add(
            Faction(
                session_id=session.id,
                name=f.name,
                seats=f.seats,
                stance_economy=f.stance_economy,
                stance_social=f.stance_social,
                stance_environment=f.stance_environment,
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
        session.term_start_turn,
        session.term_start_budget,
        session.term_start_statistics,
        session.term_start_approval,
        session.term_dilemma_count,
        session.term_event_count,
    )


def _election_projection_out(session: GameSession, sim_state) -> ElectionProjectionOut | None:
    """B5 (BACKLOG.md): Wahlvorausschau nur in den letzten
    ELECTION_PROJECTION_WINDOW Runden einer laufenden Partie. `sim_state`
    traegt die aktuelle Zufriedenheit inkl. satisfaction_momentum je Gruppe
    (aus sim_bridge), aus denen project_election den geschaetzten Turnout
    ableitet."""
    if session.status != SessionStatus.ACTIVE:
        return None
    if session.turns_until_election > ELECTION_PROJECTION_WINDOW:
        return None
    projection = project_election(sim_state)
    return ElectionProjectionOut(
        approval=projection.approval,
        turnout_adjusted_approval=projection.turnout_adjusted_approval,
        threshold=projection.threshold,
        would_win=projection.would_win,
        groups=[
            ElectionProjectionGroupOut(
                name=g.name,
                population_share=g.population_share,
                satisfaction=g.satisfaction,
                satisfaction_momentum=g.satisfaction_momentum,
                estimated_turnout=g.estimated_turnout,
                trend=g.trend,
            )
            for g in projection.groups
        ],
    )


def _build_state_response(db: Session, session: GameSession) -> SessionStateResponse:
    sim_state = _load_state_for_session(db, session)
    active_keys = [ep.policy_key for ep in db.exec(
        select(EnactedPolicy).where(EnactedPolicy.session_id == session.id, EnactedPolicy.repealed_turn == None)  # noqa: E711
    )]
    # B8: Sitzverteilung im Landtag (reine Anzeige), stabil nach Sitzen absteigend.
    faction_rows = db.exec(select(Faction).where(Faction.session_id == session.id)).all()
    factions = [
        FactionOut(
            name=f.name,
            seats=f.seats,
            stance_economy=f.stance_economy,
            stance_social=f.stance_social,
            stance_environment=f.stance_environment,
        )
        for f in sorted(faction_rows, key=lambda f: f.seats, reverse=True)
    ]
    return SessionStateResponse(
        session_id=session.id,
        turn=session.current_turn,
        budget=session.budget,
        political_capital=session.political_capital,
        turns_until_election=session.turns_until_election,
        status=session.status,
        role=session.role,
        statistics=sim_state.statistics,
        voter_groups=[vars(g) for g in sim_state.voter_groups],
        active_policy_keys=active_keys,
        pending_dilemma=_pending_dilemma_out(session),
        election_projection=_election_projection_out(session, sim_state),
        factions=factions,
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
    _validate_policy_keys(db, body.repeal_policy_keys)

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
    # Political Capital wird fuer Enact UND Repeal faellig (Democracy-4-
    # Vorbild, siehe landtag_sim.engine.py::advance_turn).
    capital_required = sum(
        policy_by_key[k].capital_cost
        for k in body.enact_policy_keys + body.repeal_policy_keys
        if k in policy_by_key
    )
    capital_available = min(10.0, sim_state.political_capital + 3.0)  # CAPITAL_CAP/CAPITAL_PER_TURN, siehe engine.py

    try:
        result = advance_turn(
            sim_state,
            policy_catalog,
            event_rules,
            body.enact_policy_keys,
            dilemma_rules,
            body.repeal_policy_keys,
        )
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
    except PolicyAlreadyActiveError as exc:
        return PreviewResponse(
            feasible=False,
            infeasible_reason=f"Policy '{exc.policy_key}' ist bereits aktiv.",
            capital_required=capital_required,
            capital_available=capital_available,
            statistic_deltas={},
            attributions=[],
            would_trigger_events=[],
            would_trigger_dilemma=False,
            satisfaction_delta_by_group={},
        )
    except PolicyLockedError as exc:
        return PreviewResponse(
            feasible=False,
            infeasible_reason=(
                f"Policy '{exc.policy_key}' ist noch gesperrt -- "
                f"Freischalt-Bedingung nicht erfuellt: {exc.unmet_condition}."
            ),
            capital_required=capital_required,
            capital_available=capital_available,
            statistic_deltas={},
            attributions=[],
            would_trigger_events=[],
            would_trigger_dilemma=False,
            satisfaction_delta_by_group={},
        )
    except PolicyNotActiveError as exc:
        return PreviewResponse(
            feasible=False,
            infeasible_reason=f"Policy '{exc.policy_key}' ist nicht aktiv und kann nicht zurueckgezogen werden.",
            capital_required=capital_required,
            capital_available=capital_available,
            statistic_deltas={},
            attributions=[],
            would_trigger_events=[],
            would_trigger_dilemma=False,
            satisfaction_delta_by_group={},
        )
    except PolicyRequiredByActivePolicyError as exc:
        return PreviewResponse(
            feasible=False,
            infeasible_reason=(
                f"Policy '{exc.policy_key}' kann nicht zurueckgezogen werden, solange "
                f"'{exc.dependent_policy_key}' aktiv ist und sie voraussetzt."
            ),
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
    _validate_policy_keys(db, body.repeal_policy_keys)

    policy_catalog = load_policy_catalog(db)
    event_rules = load_event_rules(db)
    dilemma_rules = load_dilemma_rules(db)
    report_rules = load_report_rules()
    scenario_goals = load_scenario_goals()
    sim_state = _load_state_for_session(db, session)

    try:
        result = advance_turn(
            sim_state,
            policy_catalog,
            event_rules,
            body.enact_policy_keys,
            dilemma_rules,
            body.repeal_policy_keys,
            report_rules=report_rules,
            scenario_goals=scenario_goals,
        )
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
    except PolicyAlreadyActiveError as exc:
        raise HTTPException(status_code=400, detail=f"Policy '{exc.policy_key}' ist bereits aktiv") from exc
    except PolicyLockedError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Policy '{exc.policy_key}' ist noch gesperrt -- "
                f"Freischalt-Bedingung nicht erfuellt: {exc.unmet_condition}"
            ),
        ) from exc
    except PolicyNotActiveError as exc:
        raise HTTPException(
            status_code=400, detail=f"Policy '{exc.policy_key}' ist nicht aktiv und kann nicht zurueckgezogen werden"
        ) from exc
    except PolicyRequiredByActivePolicyError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Policy '{exc.policy_key}' kann nicht zurueckgezogen werden, solange "
                f"'{exc.dependent_policy_key}' aktiv ist und sie voraussetzt"
            ),
        ) from exc
    except DilemmaPendingError as exc:  # defensiv -- oben bereits per session.pending_dilemma abgefangen
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_state = result.state

    for key in body.enact_policy_keys:
        db.add(EnactedPolicy(session_id=session.id, policy_key=key, enacted_turn=new_state.turn))

    # Repeal AKTUALISIERT die bestehende Zeile (repealed_turn setzen), statt
    # sie zu loeschen oder eine neue anzulegen -- die Sim-Engine braucht
    # enacted_turn UND repealed_turn weiterhin, um die abklingende Wirkung zu
    # berechnen (siehe sim_bridge.py::load_sim_state).
    if body.repeal_policy_keys:
        rows_by_key: dict[str, list[EnactedPolicy]] = {}
        for row in db.exec(
            select(EnactedPolicy).where(
                EnactedPolicy.session_id == session.id, EnactedPolicy.repealed_turn == None  # noqa: E711
            )
        ):
            rows_by_key.setdefault(row.policy_key, []).append(row)
        for key in body.repeal_policy_keys:
            rows = rows_by_key.get(key, [])
            if rows:
                rows[0].repealed_turn = new_state.turn
                db.add(rows[0])

    persist_sim_state(db, session.id, new_state)

    session.current_turn = new_state.turn
    session.budget = new_state.budget
    session.political_capital = new_state.political_capital
    session.turns_until_election = new_state.turns_until_election
    session.event_cooldowns = dict(new_state.event_cooldowns)
    session.dilemma_cooldowns = dict(new_state.dilemma_cooldowns)
    session.pending_dilemma = serialize_pending_dilemma(new_state.pending_dilemma)

    # B1 "Legislatur-Bogen" (BACKLOG.md): Term-Tracking der Sim-Engine
    # zurueckschreiben (die Engine setzt es am Wahl-Turn selbst auf den neuen
    # Zyklus zurueck, siehe landtag_sim.engine._build_term_summary).
    session.term_start_turn = new_state.term_start_turn
    session.term_start_budget = new_state.term_start_budget
    session.term_start_statistics = dict(new_state.term_start_statistics)
    session.term_start_approval = new_state.term_start_approval
    session.term_dilemma_count = new_state.term_dilemma_count
    session.term_event_count = new_state.term_event_count

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
        if result.election_result.won:
            session.status = SessionStatus.ACTIVE
            session.role = SessionRole.GOVERNMENT
        elif DEMOTE_TO_OPPOSITION_ON_LOSS:
            # B8 (hinter Flag, Default aus): statt Game Over in die Opposition
            # -- Datenpfad fuer einen spaeteren Opposition-Loop. Im MVP gibt es
            # dort noch KEIN abweichendes Gameplay.
            session.status = SessionStatus.ACTIVE
            session.role = SessionRole.OPPOSITION
        else:
            session.status = SessionStatus.LOST

    db.add(session)
    db.commit()

    term_summary_out: TermSummaryOut | None = None
    if result.term_summary:
        ts = result.term_summary
        term_summary_out = TermSummaryOut(
            term_start_turn=ts.term_start_turn,
            term_end_turn=ts.term_end_turn,
            start_approval=ts.start_approval,
            end_approval=ts.end_approval,
            budget_start=ts.budget_start,
            budget_end=ts.budget_end,
            dilemmas_faced=ts.dilemmas_faced,
            events_experienced=ts.events_experienced,
            statistic_changes=ts.statistic_changes,
            category_changes=ts.category_changes,
            biggest_improvement=ts.biggest_improvement,
            biggest_decline=ts.biggest_decline,
            goals=[GoalResultOut(key=g.key, description=g.description, met=g.met) for g in ts.goals],
        )

    return AdvanceTurnResponse(
        state=_build_state_response(db, session),
        events=result.events,
        attributions=[
            AttributionOut(source=a.source, statistic_key=a.statistic_key, delta=a.delta) for a in result.attributions
        ],
        election_result=election_out,
        pending_dilemma=_pending_dilemma_out(session),
        term_summary=term_summary_out,
        reports=result.reports,
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
