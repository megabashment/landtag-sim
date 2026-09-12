from pydantic import BaseModel


class ScenarioOut(BaseModel):
    """B24 "Scenario Mode" (M6): ein vordefiniertes Spielszenario mit Story und Preset-Startbedingungen."""

    key: str
    name: str
    description: str


class BundeslandOut(BaseModel):
    """B27 "Bundes-Skalierung" (M7_SPRINT_PLAN.md): ein spielbares Bundesland
    mit eigener Statistik-Baseline (siehe landtag_sim.models.BundeslandDefinition).
    `starting_statistics` wird mitgeschickt, damit das Frontend die
    Charakteristik VOR der Session-Erstellung anzeigen kann (analog zur
    Effekt-Vorschau bei Policies)."""

    key: str
    name: str
    description: str
    starting_statistics: dict[str, float]


class PartyOut(BaseModel):
    """B23 "Party-Gründung (Persistente Meta-Ebene)" (BACKLOG.md):
    eine Partei mit persistenter Ideologie über mehrere Sessions hinweg."""

    id: int
    name: str
    ideology: str  # "green" | "red" | "blue"
    founded_at: str
    base_electability: float
    reputation: float


class NewPartyRequest(BaseModel):
    """Request zum Gründen einer neuen Partei und Starten einer Session."""

    name: str
    ideology: str  # "green" | "red" | "blue"
    # UX-Onboarding-Redesign (2026-09-13): Bundesland VOR der Partei waehlen
    # (Reihenfolge Karte -> Partei -> Start). Optional + None-Default, damit
    # bestehende Aufrufer (z.B. alte Frontend-Builds) ohne dieses Feld
    # weiterhin wie bisher in Niedersachsen starten.
    bundesland_key: str | None = None


class PartySummaryOut(BaseModel):
    """B20 "Party-Legacy" (BACKLOG.md M6): Kurzprofil einer bestehenden Partei
    fuer den "Weiter mit Partei X"-Einstieg -- Ruf + gespielte/gewonnene
    Legislaturperioden aus Party.extra_data["terms"]."""

    id: int
    name: str
    ideology: str
    reputation: float
    terms_played: int
    terms_won: int


class TermDetailOut(BaseModel):
    """B28 "Advanced UI" (M7_SPRINT_PLAN.md): eine einzelne, abgeschlossene
    Legislaturperiode aus Party.extra_data["terms"]."""

    turn: int  # Wahl-Turn, an dem diese Legislaturperiode endete
    won: bool
    approval: float
    reputation_delta: float
    reputation_after: float


class PartyDetailOut(BaseModel):
    """B28 "Advanced UI": vollstaendige Partei-Historie fuer das
    Party-Detail-Modal (Ruf-ueber-Zeit-Graph + Term-Tabelle)."""

    id: int
    name: str
    ideology: str
    reputation: float
    terms: list[TermDetailOut]


class RivalPartyOut(BaseModel):
    """Mehrparteiensystem (Medium-Scope): aktueller Stand einer computer-
    gesteuerten Gegnerpartei (Anzeige in der Sonntagsfrage)."""

    name: str
    ideology: str
    approval: float


class CreateSessionResponse(BaseModel):
    """Alte Definition bleibt, aber PartyOut wird auch in Party-Gründung verwendet.
    B24 "Scenario Mode": optional scenario_id und scenario_name."""

    session_id: int
    admin_unit: str
    turn: int
    budget: float
    party_id: int | None = None
    party_name: str | None = None
    party_ideology: str | None = None
    scenario_id: str | None = None
    scenario_name: str | None = None


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


class OppositionCampaignOut(BaseModel):
    """M5 "Opposition-Loop" (BACKLOG.md B15): PR-Kampagne statt Policy
    fuer die Opposition. Wirkt auf Waehler-Satisfaction, kostet PC."""

    key: str
    name: str
    description: str
    capital_cost: float
    satisfaction_deltas: dict[str, float]  # pro Wählergruppe


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


class ActiveSituationOut(BaseModel):
    """B2 "Situations-Layer" (BACKLOG.md, L2): ein aktuell wirksamer Zustand
    (z.B. "abwanderung"/Rezession). Fuer die Statusleisten-Lageanzeige --
    `label` ist der `template_text` der Regel, `since_turn` seit wann er
    laeuft. Fehlt eine Regel zum gespeicherten `key` (Content entfernt),
    faellt `label` auf den Key zurueck."""

    key: str
    label: str
    since_turn: int


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
    # B2: aktuell wirksame Situations (Lageanzeige in der Statusleiste).
    active_situations: list[ActiveSituationOut] = []
    # B20 "Party-Legacy": aktueller Ruf der Partei (0-100, 50 neutral). None
    # im parteilosen klassischen Modus.
    party_reputation: float | None = None
    # B28 "Advanced UI" (M7_SPRINT_PLAN.md): Bugfix -- diese drei Felder
    # fehlten hier komplett (nur CreateSessionResponse hatte sie), obwohl
    # das Frontend `session.party_ideology` schon seit B23 Phase 3 fuer den
    # Ideologie-Bonus-Badge referenziert. Nach dem ersten GET /sessions/{id}
    # (das IMMER SessionStateResponse liefert, nie CreateSessionResponse)
    # war das Feld dadurch faktisch immer undefined -- der Bonus-Badge
    # zeigte sich nie. Siehe mistakes.md.
    party_id: int | None = None
    party_name: str | None = None
    party_ideology: str | None = None
    # B27 "Bundes-Skalierung" (M7_SPRINT_PLAN.md): Bugfix -- admin_unit (Name
    # des Bundeslands) war ebenfalls nur in CreateSessionResponse vorhanden,
    # das Frontend zeigte deshalb IMMER hart codiert "Niedersachsen" im
    # Header an, auch fuer Bayern-/NRW-Sessions.
    admin_unit_name: str | None = None
    # Mehrparteiensystem: aktuelle Stimmenanteile der Rivalen-Parteien
    # (Sonntagsfrage). Leer im Einzel-Partei-Modus.
    rival_parties: list[RivalPartyOut] = []


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
    # Mehrparteiensystem: [(partei_name, stimmenanteil_prozent)] absteigend.
    # Leer im klassischen Einzel-Partei-Modus (dann zaehlt approval>=threshold).
    standings: list[tuple[str, float]] = []
    # M6 Phase 2 "Advanced Opposition": Koalitionsviabilität [0, 100]
    # Bei Niederlage >= 30 kann Koalition angeboten werden
    coalition_viability: float = 0.0


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
    # M5 "Opposition-Loop" (BACKLOG.md B15): wenn opposition_mode==True,
    # wird opposition_campaign_key statt enact_policy_keys verwendet.
    opposition_campaign_key: str | None = None


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


class CoalitionResponseRequest(BaseModel):
    """M6 Phase 2 "Advanced Opposition": Spieler-Entscheidung nach
    Wahlverlust: Koalition mit Opposition akzeptieren oder ablehnen."""

    accept_coalition: bool


class CoalitionResponseOut(BaseModel):
    """Bestätigung der Koalitionsentscheidung. Wenn akzeptiert und möglich,
    bleibt der Spieler in der Regierung. Sonst wechsel in Opposition."""

    accepted: bool
    message: str  # "Koalition akzeptiert!" oder "Opposition bernommen"
