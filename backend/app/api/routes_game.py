from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import AdminUnit, EnactedPolicy, Faction, GameSession, Party, PolicyDefinition, ScenarioDefinition, VoterGroup
from app.models import StatisticValue
from app.models.game import SessionRole, SessionStatus
from app.models.party import PartyIdeology
from app.schemas.game import (
    ActiveSituationOut,
    AdvanceTurnRequest,
    AdvanceTurnResponse,
    AttributionOut,
    BundeslandOut,
    CoalitionResponseRequest,
    CreateSessionResponse,
    DilemmaOptionOut,
    ElectionProjectionGroupOut,
    ElectionProjectionOut,
    ElectionResultOut,
    FactionOut,
    GoalResultOut,
    NewPartyRequest,
    OppositionCampaignOut,
    PartyDetailOut,
    PartySummaryOut,
    PendingDilemmaOut,
    PolicyEffectOut,
    PolicyOut,
    PreviewRequest,
    PreviewResponse,
    ResolveDilemmaRequest,
    ResolveDilemmaResponse,
    RivalPartyOut,
    ScenarioOut,
    SessionStateResponse,
    TermDetailOut,
    TermSummaryOut,
    UnlockConditionOut,
)
from app.seed import ensure_bundesland, ensure_niedersachsen, run_all_seeds
from app.sim_bridge import (
    load_dilemma_rules,
    load_event_rules,
    load_opposition_campaigns,
    load_policy_catalog,
    load_report_rules,
    load_scenario_goals,
    load_sim_state,
    load_situation_rules,
    persist_sim_state,
    seed_rival_parties,
    serialize_pending_dilemma,
    serialize_rival_parties,
)
from landtag_sim.engine import (
    REPUTATION_GAIN_ON_WIN,
    REPUTATION_LOSS_ON_DEFEAT,
    advance_turn,
    project_election,
    resolve_dilemma,
)
from landtag_sim.models import (
    DilemmaPendingError,
    InsufficientCapitalError,
    PolicyAlreadyActiveError,
    PolicyLockedError,
    PolicyNotActiveError,
    PolicyRequiredByActivePolicyError,
    UnmetPrerequisiteError,
)
from landtag_sim.sample_data import (
    SAMPLE_BUNDESLAENDER,
    SAMPLE_FACTIONS,
    SAMPLE_VOTER_GROUPS,
    get_scenario_starting_statistics,
    jittered_starting_statistics,
)

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
DEMOTE_TO_OPPOSITION_ON_LOSS = True


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


@router.get("/opposition-campaigns", response_model=list[OppositionCampaignOut])
def list_opposition_campaigns() -> list[OppositionCampaignOut]:
    """B26 "Opposition-Kampagnen UI Verbesserung" (M7_SPRINT_PLAN.md): der
    Opposition-Kampagnen-Katalog kam bisher NUR aus einer hart codierten
    Frontend-Konstante (`_OPPOSITION_CAMPAIGNS` in App.jsx), die nirgends
    verwendet wurde -- die Kampagnenauswahl war unsichtbar, Opposition-Runden
    schickten immer `opposition_campaign_key=null`. Dieser Endpoint liefert
    den echten Katalog aus sample_data.py, analog zu GET /policies. Nicht
    DB-gestuetzt (wie /scenarios), weil OppositionCampaign kein eigenes
    SQLModel/DB-Modell hat -- reine Sim-Beispieldaten wie SAMPLE_RIVAL_PARTIES."""
    campaigns = load_opposition_campaigns()
    return [
        OppositionCampaignOut(
            key=c.key,
            name=c.name,
            description=c.description,
            capital_cost=c.capital_cost,
            satisfaction_deltas=dict(c.satisfaction_deltas),
        )
        for c in campaigns
    ]


@router.get("/bundeslaender", response_model=list[BundeslandOut])
def list_bundeslaender() -> list[BundeslandOut]:
    """B27 "Bundes-Skalierung" (M7_SPRINT_PLAN.md): Liste aller spielbaren
    Bundeslaender mit ihrer Statistik-Baseline. Wie /opposition-campaigns
    NICHT DB-gestuetzt (reine Sim-Beispieldaten aus sample_data.py) --
    die zugehoerige AdminUnit-Zeile wird erst bei der Session-Erstellung
    per ensure_bundesland() angelegt."""
    return [
        BundeslandOut(
            key=b.key,
            name=b.name,
            description=b.description,
            starting_statistics=dict(b.starting_statistics),
        )
        for b in SAMPLE_BUNDESLAENDER
    ]


@router.get("/scenarios", response_model=list[ScenarioOut])
def list_scenarios(db: Session = Depends(get_session)) -> list[ScenarioOut]:
    """B24 "Scenario Mode" (M6): Liste aller verfügbaren Szenarien mit
    Namen und Beschreibungen. Szenarien sind vordefinierte Spielmodi mit
    Preset-Startbedingungen (z.B. "Klimakrise bewältigen" mit hohem
    co2_emissions-Startwert)."""
    run_all_seeds(db)
    rows = db.exec(select(ScenarioDefinition)).all()
    return [
        ScenarioOut(
            key=row.key,
            name=row.name,
            description=row.description,
        )
        for row in rows
    ]


@router.post("/sessions/new-party", response_model=CreateSessionResponse)
def create_party_session(request: NewPartyRequest, db: Session = Depends(get_session)) -> CreateSessionResponse:
    """B23 'Party-Gründung (Persistente Meta-Ebene)': Gründe eine neue Partei
    mit einer Ideologie und starte eine neue Session für diese Partei."""
    run_all_seeds(db)
    admin_unit = ensure_niedersachsen(db)

    # Party gründen
    try:
        ideology = PartyIdeology(request.ideology)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Ungültige Ideologie: {request.ideology}. Erlaubte Werte: green, red, blue"
        )

    party = Party(
        name=request.name,
        ideology=ideology,
        base_electability=50.0,
        reputation=50.0
    )
    db.add(party)
    db.commit()
    db.refresh(party)

    # Session für diese Partei erstellen
    session = GameSession(
        admin_unit_id=admin_unit.id,
        party_id=party.id,
        budget=1000.0,
        current_turn=0
    )
    # Mehrparteiensystem (Medium-Scope): Party-Sessions treten gegen die drei
    # festen Rivalen-Parteien an (klassische parteilose Sessions nicht).
    session.rival_parties = seed_rival_parties()
    db.add(session)
    db.commit()
    db.refresh(session)

    _seed_session_world(db, session.id)

    return CreateSessionResponse(
        session_id=session.id,
        admin_unit=admin_unit.name,
        turn=session.current_turn,
        budget=session.budget,
        party_id=party.id,
        party_name=party.name,
        party_ideology=party.ideology.value,
        scenario_id=None,
        scenario_name=None,
    )


def _seed_session_world(
    db: Session,
    session_id: int,
    scenario_statistics_override: dict[str, float] | None = None,
    base_statistics: dict[str, float] | None = None,
) -> None:
    """Seedet Startstatistiken (mit Jitter), Waehlergruppen (inkl. B23-
    Ideologie-Affinitaeten) und die Landtags-Sitzverteilung fuer eine frisch
    angelegte Session. Gemeinsam genutzt von create_session,
    create_party_session, create_session_from_party und (B27)
    create_session_from_bundesland.

    B24 "Scenario Mode": falls scenario_statistics_override gesetzt,
    werden diese Werte ueber die Jitter-Werte fuer bestimmte Statistiken
    gelegt.

    B27 "Bundes-Skalierung": falls base_statistics gesetzt (z.B.
    BundeslandDefinition.starting_statistics), wird DARUM gejittert statt um
    STARTING_STATISTICS (Niedersachsen) -- jedes Bundesland streut um seine
    EIGENE Baseline. scenario_statistics_override wirkt trotzdem weiterhin
    zusaetzlich (Kombination bisher nicht genutzt, aber unterstuetzt)."""
    stats = jittered_starting_statistics(base=base_statistics)
    if scenario_statistics_override:
        stats.update(scenario_statistics_override)

    for stat_key, value in stats.items():
        db.add(StatisticValue(session_id=session_id, statistic_key=stat_key, turn_number=0, value=value))

    for vg in SAMPLE_VOTER_GROUPS:
        db.add(
            VoterGroup(
                session_id=session_id,
                name=vg.name,
                population_share=vg.population_share,
                satisfaction=vg.satisfaction,
                weight_economy=vg.weight_economy,
                weight_social=vg.weight_social,
                weight_environment=vg.weight_environment,
                ideology_preference=vg.ideology_preference,
                ideology_dislike=vg.ideology_dislike,
            )
        )

    for f in SAMPLE_FACTIONS:
        db.add(
            Faction(
                session_id=session_id,
                name=f.name,
                seats=f.seats,
                stance_economy=f.stance_economy,
                stance_social=f.stance_social,
                stance_environment=f.stance_environment,
            )
        )
    db.commit()


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(db: Session = Depends(get_session)) -> CreateSessionResponse:
    run_all_seeds(db)
    admin_unit = ensure_niedersachsen(db)

    session = GameSession(admin_unit_id=admin_unit.id, budget=1000.0, current_turn=0)
    db.add(session)
    db.commit()
    db.refresh(session)

    # P2-Punkt "Randomisierte Startbedingungen": Jitter + Waehlergruppen +
    # Sitzverteilung (gemeinsame Seed-Logik, siehe _seed_session_world).
    _seed_session_world(db, session.id)

    return CreateSessionResponse(
        session_id=session.id,
        admin_unit=admin_unit.name,
        turn=session.current_turn,
        budget=session.budget,
        scenario_id=None,
        scenario_name=None,
    )


@router.get("/parties", response_model=list[PartySummaryOut])
def list_parties(db: Session = Depends(get_session)) -> list[PartySummaryOut]:
    """B20 "Party-Legacy": alle bisher gegruendeten Parteien mit ihrem
    aktuellen Ruf und der Zahl gespielter Legislaturperioden -- Grundlage fuer
    den "Weiter mit Partei X"-Einstieg im Frontend."""
    parties = db.exec(select(Party).order_by(Party.founded_at)).all()
    out: list[PartySummaryOut] = []
    for p in parties:
        terms = (p.extra_data or {}).get("terms", [])
        out.append(
            PartySummaryOut(
                id=p.id,
                name=p.name,
                ideology=p.ideology.value,
                reputation=p.reputation,
                terms_played=len(terms),
                terms_won=sum(1 for t in terms if t.get("won")),
            )
        )
    return out


@router.get("/parties/{party_id}/detail", response_model=PartyDetailOut)
def get_party_detail(party_id: int, db: Session = Depends(get_session)) -> PartyDetailOut:
    """B28 "Advanced UI" (M7_SPRINT_PLAN.md): komplette Partei-Historie fuer
    das Party-Detail-Modal (Ruf-ueber-Zeit-Graph + Term-Tabelle). Im
    Unterschied zu list_parties() (nur Zaehlwerte) hier die volle
    Term-Liste inkl. Ruf-Delta pro Legislaturperiode.

    `.get(...)` statt direktem Dict-Unpacking fuer die Term-Eintraege:
    Terms, die VOR B28 protokolliert wurden, haben noch keine
    reputation_delta/reputation_after-Felder (siehe advance_session_turn) --
    robust mit 0.0 statt eines 422/500 bei altem Datenbestand."""
    party = db.get(Party, party_id)
    if not party:
        raise HTTPException(status_code=404, detail="Partei nicht gefunden")

    terms_raw = (party.extra_data or {}).get("terms", [])
    terms = [
        TermDetailOut(
            turn=t.get("turn", 0),
            won=bool(t.get("won", False)),
            approval=t.get("approval", 0.0),
            reputation_delta=t.get("reputation_delta", 0.0),
            reputation_after=t.get("reputation_after", party.reputation),
        )
        for t in terms_raw
    ]
    return PartyDetailOut(
        id=party.id,
        name=party.name,
        ideology=party.ideology.value,
        reputation=party.reputation,
        terms=terms,
    )


@router.post("/sessions/new-scenario/{scenario_id}", response_model=CreateSessionResponse)
def create_session_from_scenario(scenario_id: str, db: Session = Depends(get_session)) -> CreateSessionResponse:
    """B24 "Scenario Mode" (M6): startet eine neue Session mit einem
    vordefinierten Szenario (Preset-Startbedingungen, Story). Szenarien
    können beliebig oft gespielt werden."""
    scenario = db.get(ScenarioDefinition, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Szenario nicht gefunden")

    run_all_seeds(db)
    admin_unit = ensure_niedersachsen(db)

    session = GameSession(
        admin_unit_id=admin_unit.id,
        scenario_id=scenario_id,
        budget=1000.0,
        current_turn=0,
        rival_parties=seed_rival_parties(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # B24 "Scenario Mode": apply scenario-spezifische Startbedingungen
    _seed_session_world(
        db,
        session.id,
        scenario_statistics_override=scenario.starting_statistics_override,
    )

    return CreateSessionResponse(
        session_id=session.id,
        admin_unit=admin_unit.name,
        turn=session.current_turn,
        budget=session.budget,
        party_id=None,
        party_name=None,
        party_ideology=None,
        scenario_id=scenario.key,
        scenario_name=scenario.name,
    )


@router.post("/sessions/new-bundesland/{bundesland_key}", response_model=CreateSessionResponse)
def create_session_from_bundesland(bundesland_key: str, db: Session = Depends(get_session)) -> CreateSessionResponse:
    """B27 "Bundes-Skalierung" (M7_SPRINT_PLAN.md): startet eine neue Session
    mit der Statistik-Baseline eines bestimmten Bundeslands statt des
    Niedersachsen-Defaults. Kein State-Wechsel INNERHALB einer laufenden
    Session (siehe M7_SPRINT_PLAN.md "Nicht in M7") -- die Session bleibt fuer
    ihre gesamte Laufzeit bei diesem Bundesland."""
    bundesland = next((b for b in SAMPLE_BUNDESLAENDER if b.key == bundesland_key), None)
    if not bundesland:
        raise HTTPException(status_code=404, detail=f"Unbekanntes Bundesland: {bundesland_key}")

    run_all_seeds(db)
    admin_unit = ensure_bundesland(db, bundesland_key)

    session = GameSession(
        admin_unit_id=admin_unit.id,
        budget=1000.0,
        current_turn=0,
        rival_parties=seed_rival_parties(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # B27: um die EIGENE Baseline des Bundeslands jittern, nicht um
    # Niedersachsen (siehe _seed_session_world/jittered_starting_statistics).
    _seed_session_world(db, session.id, base_statistics=bundesland.starting_statistics)

    return CreateSessionResponse(
        session_id=session.id,
        admin_unit=admin_unit.name,
        turn=session.current_turn,
        budget=session.budget,
        party_id=None,
        party_name=None,
        party_ideology=None,
        scenario_id=None,
        scenario_name=None,
    )


@router.post("/sessions/from-party/{party_id}", response_model=CreateSessionResponse)
def create_session_from_party(party_id: int, db: Session = Depends(get_session)) -> CreateSessionResponse:
    """B20 "Party-Legacy": startet eine neue Legislaturperiode fuer eine
    BESTEHENDE Partei. Ihr aufgebauter Ruf (Party.reputation) wirkt ab Runde 0
    als Amtsbonus/-malus (siehe engine._reputation_multiplier)."""
    party = db.get(Party, party_id)
    if not party:
        raise HTTPException(status_code=404, detail="Partei nicht gefunden")

    run_all_seeds(db)
    admin_unit = ensure_niedersachsen(db)

    session = GameSession(
        admin_unit_id=admin_unit.id,
        party_id=party.id,
        budget=1000.0,
        current_turn=0,
        rival_parties=seed_rival_parties(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    _seed_session_world(db, session.id)

    return CreateSessionResponse(
        session_id=session.id,
        admin_unit=admin_unit.name,
        turn=session.current_turn,
        budget=session.budget,
        party_id=party.id,
        party_name=party.name,
        party_ideology=party.ideology.value,
        scenario_id=None,
        scenario_name=None,
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
    # B23 Phase 3: Party-Ideologie laden (falls vorhanden)
    # B20 "Party-Legacy": Ruf der Partei aus vorherigen Legislaturen laden
    party_ideology = None
    party_reputation = 50.0
    if session.party_id:
        party = db.get(Party, session.party_id)
        if party:
            party_ideology = party.ideology.value
            party_reputation = party.reputation

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
        session.opposition_mode,
        session.opposition_satisfaction,
        session.opposition_momentum,
        party_ideology,
        party_reputation,
        session.rival_parties,
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
    # B28 "Advanced UI" (M7_SPRINT_PLAN.md): party_id/party_name fuer den
    # "Partei-Details"-Button im Frontend (verlinkt zu GET /parties/{id}/detail).
    # party_ideology kommt bereits aus sim_state (siehe _load_state_for_session),
    # war aber bisher NICHT im Response-Objekt -- Bugfix, siehe SessionStateResponse.
    party_name = None
    if session.party_id:
        party_row = db.get(Party, session.party_id)
        party_name = party_row.name if party_row else None

    # B27 "Bundes-Skalierung": Bundesland-Name fuer den Header (Bugfix --
    # war bisher nur einmalig in CreateSessionResponse verfuegbar).
    admin_unit_row = db.get(AdminUnit, session.admin_unit_id)
    admin_unit_name = admin_unit_row.name if admin_unit_row else None
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
    # B2: aktuell wirksame Situations fuer die Lageanzeige. `label` aus dem
    # template_text der Regel; unbekannter key (Content entfernt) -> key.
    situation_labels = {r.key: r.template_text for r in load_situation_rules()}
    active_situations = [
        ActiveSituationOut(
            key=s.rule_key,
            label=situation_labels.get(s.rule_key) or s.rule_key,
            since_turn=s.since_turn,
        )
        for s in sorted(sim_state.active_situations, key=lambda s: s.since_turn)
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
        active_situations=active_situations,
        party_reputation=sim_state.party_reputation if session.party_id else None,
        party_id=session.party_id,
        party_name=party_name,
        party_ideology=sim_state.party_ideology if session.party_id else None,
        admin_unit_name=admin_unit_name,
        rival_parties=[
            RivalPartyOut(name=r.name, ideology=r.ideology, approval=round(r.approval, 1))
            for r in sim_state.rival_parties
        ],
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
    situation_rules = load_situation_rules()
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
            situation_rules=situation_rules,
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


def _apply_opposition_campaign(sim_state, campaign_key: str) -> tuple[float, dict[str, float]]:
    """M5 "Opposition-Loop" (BACKLOG.md B15): wendet eine Opposition-Kampagne
    auf den State an. Returnt (capital_cost, satisfaction_deltas).

    Updatet im State:
    - opposition_satisfaction: +delta pro Gruppe
    - opposition_momentum: EMA-Glättung wie bei Regierungs-Policies
    """
    campaigns = load_opposition_campaigns()
    campaign = next((c for c in campaigns if c.key == campaign_key), None)
    if not campaign:
        raise ValueError(f"Opposition-Kampagne '{campaign_key}' nicht gefunden")

    # Satisfaction-Deltas anwenden + Momentum-EMA
    SATISFACTION_MOMENTUM_ALPHA = 0.4  # siehe engine.py (samme value)
    for group_name, delta in campaign.satisfaction_deltas.items():
        # Initialisiere opposition_satisfaction/momentum falls leer
        if not sim_state.opposition_satisfaction:
            sim_state.opposition_satisfaction = {g.name: 0.0 for g in sim_state.voter_groups}
            sim_state.opposition_momentum = {g.name: 0.0 for g in sim_state.voter_groups}

        current = sim_state.opposition_satisfaction.get(group_name, 0.0)
        current_momentum = sim_state.opposition_momentum.get(group_name, 0.0)

        # EMA-Glättung: Momentum nähert sich dem Raw-Delta an
        new_momentum = SATISFACTION_MOMENTUM_ALPHA * delta + (1 - SATISFACTION_MOMENTUM_ALPHA) * current_momentum

        # Zufriedenheit wird vom Momentum beeinflusst (wie bei Policies)
        new_satisfaction = current + new_momentum

        # Clamping auf [0, 100]
        new_satisfaction = max(0.0, min(100.0, new_satisfaction))

        sim_state.opposition_satisfaction[group_name] = new_satisfaction
        sim_state.opposition_momentum[group_name] = new_momentum

    return campaign.capital_cost, dict(campaign.satisfaction_deltas)


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

    # Opposition-Modus? Kampagne statt Policies
    if session.opposition_mode and body.opposition_campaign_key:
        # keine Policy-Validierung nötig für Opposition
        opposition_campaign_keys = []
    else:
        _validate_policy_keys(db, body.enact_policy_keys)
        _validate_policy_keys(db, body.repeal_policy_keys)
        opposition_campaign_keys = []

    policy_catalog = load_policy_catalog(db)
    event_rules = load_event_rules(db)
    dilemma_rules = load_dilemma_rules(db)
    report_rules = load_report_rules()
    scenario_goals = load_scenario_goals()
    situation_rules = load_situation_rules()
    sim_state = _load_state_for_session(db, session)

    # Opposition-Kampagne vor advance_turn verarbeiten
    if session.opposition_mode and body.opposition_campaign_key:
        try:
            capital_cost, _ = _apply_opposition_campaign(sim_state, body.opposition_campaign_key)
            if sim_state.political_capital < capital_cost:
                raise HTTPException(
                    status_code=400,
                    detail=f"Nicht genug Political Capital für Kampagne: benötigt {capital_cost}, verfügbar {sim_state.political_capital}",
                )
            sim_state.political_capital -= capital_cost
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = advance_turn(
            sim_state,
            policy_catalog,
            event_rules,
            body.enact_policy_keys if not session.opposition_mode else [],
            dilemma_rules,
            body.repeal_policy_keys if not session.opposition_mode else [],
            report_rules=report_rules,
            scenario_goals=scenario_goals,
            situation_rules=situation_rules,
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

    # M5 "Opposition-Loop" (BACKLOG.md B15): Opposition-Zufriedenheit speichern
    session.opposition_mode = new_state.opposition_mode
    session.opposition_satisfaction = dict(new_state.opposition_satisfaction)
    session.opposition_momentum = dict(new_state.opposition_momentum)

    # Mehrparteiensystem: fortgeschriebene Rivalen-Stimmenanteile zurueckschreiben
    session.rival_parties = serialize_rival_parties(new_state.rival_parties)

    election_out: ElectionResultOut | None = None
    if result.election_result:
        election_out = ElectionResultOut(
            approval=result.election_result.approval,
            threshold=result.election_result.threshold,
            won=result.election_result.won,
            standings=[list(s) for s in result.election_result.standings],
            coalition_viability=result.election_result.coalition_viability,
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

        # B20 "Party-Legacy": Ruf der Partei nach der Wahl anpassen und die
        # Legislaturperiode in Party.extra_data["terms"] protokollieren. Sieg
        # hebt den Ruf, Niederlage senkt ihn staerker (siehe engine-Konstanten
        # REPUTATION_GAIN_ON_WIN / REPUTATION_LOSS_ON_DEFEAT).
        if session.party_id:
            party = db.get(Party, session.party_id)
            if party:
                reputation_before = party.reputation
                if result.election_result.won:
                    party.reputation = min(100.0, party.reputation + REPUTATION_GAIN_ON_WIN)
                else:
                    party.reputation = max(0.0, party.reputation - REPUTATION_LOSS_ON_DEFEAT)
                data = dict(party.extra_data or {})
                terms = list(data.get("terms", []))
                terms.append(
                    {
                        "turn": new_state.turn,
                        "won": bool(result.election_result.won),
                        "approval": round(result.election_result.approval, 1),
                        # B28 "Advanced UI" (M7_SPRINT_PLAN.md): tatsaechlich
                        # angewendetes Ruf-Delta + Ruf NACH der Wahl speichern
                        # (statt es spaeter aus den REPUTATION_*-Konstanten
                        # zurueckzurechnen) -- bleibt auch dann historisch
                        # korrekt, wenn diese Konstanten spaeter mal angepasst werden.
                        "reputation_delta": round(party.reputation - reputation_before, 1),
                        "reputation_after": round(party.reputation, 1),
                    }
                )
                data["terms"] = terms
                party.extra_data = data
                db.add(party)

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


@router.post("/sessions/{session_id}/respond-to-election")
def respond_to_election(
    session_id: int, body: CoalitionResponseRequest, db: Session = Depends(get_session)
) -> dict[str, str]:
    """M6 Phase 2 "Advanced Opposition": Spieler-Entscheidung nach Wahlverlust.
    Wenn coalition_viability >= 30 und accept_coalition=True, bleibt die Partie
    im GOVERNMENT-Modus (kein Demote zu OPPOSITION). Sonst Standard-Demote."""
    session = db.get(GameSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")

    # Koalition ist nur möglich, wenn die letzte Wahl verloren wurde und
    # coalition_viability ausreichend hoch ist. Der Client sollte die UI
    # entsprechend disablen, aber wir validieren hier auch serverseitig.
    if not session.election_result or session.election_result.get("won", False):
        raise HTTPException(status_code=400, detail="Keine Wahlniederlage vorhanden")

    coalition_viability = session.election_result.get("coalition_viability", 0.0)
    if body.accept_coalition and coalition_viability < 30.0:
        raise HTTPException(
            status_code=400,
            detail=f"Koalition nicht möglich: Viabilität {coalition_viability:.1f}% < 30%",
        )

    # Entscheidung in Session speichern (für künftige Geschichtsanzeige)
    if session.extra_data is None:
        session.extra_data = {}
    session.extra_data["last_coalition_decision"] = {
        "accepted": body.accept_coalition,
        "viability": coalition_viability,
    }

    # Logik: Falls Koalition akzeptiert und möglich, bleibt GOVERNMENT.
    # Sonst Demote zu OPPOSITION.
    if body.accept_coalition and coalition_viability >= 30.0:
        # Koalition akzeptiert: bleibe in Regierung
        session.role = SessionRole.GOVERNMENT
        message = f"Koalition akzeptiert! Zusammenarbeit mit Opposition ermöglicht Regierungsfortbestand."
    else:
        # Koalition abgelehnt oder nicht möglich: gehe in Opposition
        session.role = SessionRole.OPPOSITION
        message = f"Opposition übernommen. Versuche, die nächste Wahl zu gewinnen."

    db.add(session)
    db.commit()
    return {"message": message, "role": session.role.value}


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
