from pydantic import BaseModel


class PolicyEffectOut(BaseModel):
    statistic_key: str
    magnitude: float
    delay_turns: int
    inertia: int


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
    effects: list[PolicyEffectOut]
    requires: list[str]


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


class SessionStateResponse(BaseModel):
    session_id: int
    turn: int
    budget: float
    political_capital: float
    turns_until_election: int
    status: str
    statistics: dict[str, float]
    voter_groups: list[dict]
    active_policy_keys: list[str]
    pending_dilemma: PendingDilemmaOut | None = None


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


class AdvanceTurnRequest(BaseModel):
    enact_policy_keys: list[str] = []


class AdvanceTurnResponse(BaseModel):
    state: SessionStateResponse
    events: list[str]
    attributions: list[AttributionOut]
    election_result: ElectionResultOut | None = None
    pending_dilemma: PendingDilemmaOut | None = None


class ResolveDilemmaRequest(BaseModel):
    option_key: str


class ResolveDilemmaResponse(BaseModel):
    state: SessionStateResponse
    attributions: list[AttributionOut]


class PreviewRequest(BaseModel):
    enact_policy_keys: list[str] = []


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
