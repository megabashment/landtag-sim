from pydantic import BaseModel


class PolicyEffectOut(BaseModel):
    statistic_key: str
    magnitude: float
    delay_turns: int
    inertia: int


class UnlockConditionOut(BaseModel):
    """B7 "Dynamische Policy-Freischaltung durch Sim-Zustand" (BACKLOG.md, L7):
    eine Statistik-Schwelle, die erfuellt sein muss, damit die Policy
    einfuehrbar wird. Das Frontend vergleicht sie gegen die aktuellen
    Session-Statistiken und graut die Policy sonst aus ("Wird verfuegbar,
    wenn …")."""

    statistic_key: str
    operator: str
    threshold: float


class PolicyOut(BaseModel):
    """Dynamischer Policy-Katalog fuer GET /policies -- ersetzt die zuvor
    hart codierte AVAILABLE_POLICIES-Konstante in frontend/src/App.jsx, die
    manuell mit sim/landtag_sim/sample_data.py synchron gehalten werden
    musste (siehe 'Bekannte Vereinfachungen' in README.md/CLAUDE.md)."""

    key: str
    name: str
    description: str
    category: str
    one_time_cost: float
    upkeep_cost: float
    capital_cost: float
    income_per_turn: float
    effects: list[PolicyEffectOut]
    requires: list[str]
    unlock_conditions: list[UnlockConditionOut] = []  # B7


class CreateSessionResponse(BaseModel):
    session_id: int
    admin_unit: str
    turn: int
    budget: float


class DilemmaOptionOut(BaseModel):
    key: str
    label: str
    budget_cost: float


class PendingDilemmaOut(BaseModel):
    """P1-Punkt 'Dilemma-Events mit echten Entscheidungsoptionen'
    (docs/game-design-roadmap.md): ein offenes Dilemma, das ueber
    POST /sessions/{id}/resolve-dilemma aufgeloest werden muss, bevor
    /advance wieder funktioniert. Effekte der Optionen werden bewusst NICHT
    mitgeschickt (kein Preview auf Dilemma-Ebene im MVP) -- nur Label und
    Budget-Kosten, analog zu Frostpunks vager Book-of-Laws-Darstellung."""

    rule_key: str
    prompt: str
    options: list[DilemmaOptionOut]


class ElectionProjectionGroupOut(BaseModel):
    """B5 "Wahlprognose mit sichtbarem Turnout/Apathie" (BACKLOG.md, F4/L6):
    eine Zeile der Wahlvorausschau pro Waehlergruppe."""

    name: str
    population_share: float
    satisfaction: float
    satisfaction_momentum: float
    estimated_turnout: float
    trend: str  # "steigend" | "stabil" | "fallend"


class ElectionProjectionOut(BaseModel):
    """B5 (BACKLOG.md): nur gesetzt, wenn `turns_until_election` klein genug
    ist (siehe routes_game.ELECTION_PROJECTION_WINDOW). `approval` ist die
    entscheidungsrelevante Zahl (wie die echte Wahl, ohne Turnout);
    `turnout_adjusted_approval` legt das Apathie-Modell an (nur Anzeige)."""

    approval: float
    turnout_adjusted_approval: float
    threshold: float
    would_win: bool
    groups: list[ElectionProjectionGroupOut]


class FactionOut(BaseModel):
    """B8 "Fraktions-/Sitz-Datenmodell" (BACKLOG.md, L8): eine Fraktion im
    Landtag. Reine Anzeige ("Sitzverteilung im Landtag"), noch keine
    Mechanik."""

    name: str
    seats: int
    stance_economy: float
    stance_social: float
    stance_environment: float


class SessionStateResponse(BaseModel):
    session_id: int
    turn: int
    budget: float
    political_capital: float
    turns_until_election: int
    status: str
    # B8: Rolle der Spielerpartei ("government"/"opposition"). Im MVP immer
    # "government" (reine Struktur, siehe SessionRole).
    role: str = "government"
    statistics: dict[str, float]
    voter_groups: list[dict]
    active_policy_keys: list[str]
    pending_dilemma: PendingDilemmaOut | None = None
    # B5: Wahlvorausschau, nur in den letzten Runden vor der Wahl gesetzt.
    election_projection: ElectionProjectionOut | None = None
    # B8: Sitzverteilung im Landtag (reine Anzeige).
    factions: list[FactionOut] = []


class AttributionOut(BaseModel):
    """Ein einzelner Statistik-Delta-Beitrag mitsamt Quelle (P0-Punkt
    'Zufriedenheits-Attribution', siehe docs/game-design-roadmap.md)."""

    source: str
    statistic_key: str
    delta: float


class ElectionResultOut(BaseModel):
    approval: float
    threshold: float
    won: bool


class GoalResultOut(BaseModel):
    """B9 "Szenario-/Legislatur-Ziele" (BACKLOG.md): ein optionales Ziel und
    ob es am Legislaturende erfuellt wurde. Reine Anzeige (unverbindlich)."""

    key: str
    description: str
    met: bool


class TermSummaryOut(BaseModel):
    """B1 "Legislatur-Bogen & Amtszeit-Debrief" (BACKLOG.md): Bilanz einer
    gerade abgeschlossenen Legislaturperiode, nur am Wahl-Turn im
    AdvanceTurnResponse gesetzt (sonst None). Reiner Rueckblick -- keine
    Sim-Wirkung, keine harte Siegbedingung (das ist BACKLOG.md F1/B9)."""

    term_start_turn: int
    term_end_turn: int
    start_approval: float
    end_approval: float
    budget_start: float
    budget_end: float
    dilemmas_faced: int
    events_experienced: int
    statistic_changes: dict[str, float]
    category_changes: dict[str, float]
    biggest_improvement: str | None = None
    biggest_decline: str | None = None
    # B9: optionale Legislatur-Ziele, erfuellt/verfehlt (leer = reine Sandbox).
    goals: list[GoalResultOut] = []


class AdvanceTurnRequest(BaseModel):
    enact_policy_keys: list[str] = []
    # Democracy-4-Vorbild "Policy-Repeal": Policy-Keys, die diese Runde
    # zurueckgezogen werden sollen (siehe landtag_sim.engine.py::advance_turn,
    # newly_repealed_keys). Ihre Wirkung verschwindet nicht sofort, sondern
    # klingt ueber mehrere Runden ab.
    repeal_policy_keys: list[str] = []


class AdvanceTurnResponse(BaseModel):
    state: SessionStateResponse
    events: list[str]
    attributions: list[AttributionOut]
    election_result: ElectionResultOut | None = None
    pending_dilemma: PendingDilemmaOut | None = None
    term_summary: TermSummaryOut | None = None
    # B4 "Narrative Konsequenz-Ebene" (BACKLOG.md): hoechstens ein
    # Presseschau-Text pro Runde, nur in Runden ohne Event/Dilemma. Reine
    # Anzeige, keine Sim-Wirkung.
    reports: list[str] = []


class ResolveDilemmaRequest(BaseModel):
    option_key: str


class ResolveDilemmaResponse(BaseModel):
    state: SessionStateResponse
    attributions: list[AttributionOut]


class PreviewRequest(BaseModel):
    enact_policy_keys: list[str] = []
    # Siehe AdvanceTurnRequest.repeal_policy_keys -- Preview simuliert einen
    # Repeal genauso wie ein Enact, ohne etwas zu persistieren.
    repeal_policy_keys: list[str] = []


class PreviewResponse(BaseModel):
    """Read-only Vorschau (P0-Punkt 'Effekt-Vorschau vor Entscheidung'):
    simuliert eine Runde mit den ausgewaehlten Policies, persistiert aber
    nichts. `statistic_deltas` ist der Netto-Effekt pro Statistik ueber die
    naechste Runde, `feasible=False` bedeutet, dass die Auswahl am
    Political Capital oder an einer fehlenden Policy-Voraussetzung
    scheitern wuerde (`infeasible_reason` unterscheidet die beiden Faelle)."""

    feasible: bool
    infeasible_reason: str | None = None
    capital_required: float
    capital_available: float
    statistic_deltas: dict[str, float]
    attributions: list[AttributionOut]
    would_trigger_events: list[str]
    would_trigger_dilemma: bool
    satisfaction_delta_by_group: dict[str, float]
