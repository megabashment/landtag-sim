"""Reine Datenklassen der Sim-Engine (kein SQLModel/DB-Bezug)."""
from __future__ import annotations

from dataclasses import dataclass, field


class InsufficientCapitalError(Exception):
    """Die angeforderten Policies kosten mehr Political Capital, als verfuegbar ist."""

    def __init__(self, required: float, available: float):
        self.required = required
        self.available = available
        super().__init__(f"Political Capital reicht nicht: benoetigt {required}, verfuegbar {available}")


class UnmetPrerequisiteError(Exception):
    """P1-Punkt 'Policy-Pfade/Voraussetzungen': eine Policy verlangt eine
    andere, noch nicht aktive Policy (siehe Policy.requires,
    docs/game-design-roadmap.md)."""

    def __init__(self, policy_key: str, missing_requirement: str):
        self.policy_key = policy_key
        self.missing_requirement = missing_requirement
        super().__init__(
            f"Policy '{policy_key}' braucht zuerst '{missing_requirement}' als aktive Policy"
        )


class DilemmaPendingError(Exception):
    """P1-Punkt 'Dilemma-Events mit echten Entscheidungsoptionen': eine Runde
    kann nicht weiter voranschreiten, solange ein Dilemma unresolved ist --
    der Aufrufer muss zuerst resolve_dilemma() aufrufen (siehe engine.py)."""

    def __init__(self, dilemma_key: str):
        self.dilemma_key = dilemma_key
        super().__init__(f"Dilemma '{dilemma_key}' muss zuerst aufgeloest werden, bevor die Runde weitergeht")


class PolicyAlreadyActiveError(Exception):
    """Die Policy ist bereits aktiv (und nicht zurueckgezogen) -- ein zweites
    Enact wuerde ihre Effekte/Kosten verdoppeln, ohne dass die Sim-Engine
    das je vorgesehen haette. Vorher konnte das API-seitig unbemerkt
    passieren; siehe mistakes.md."""

    def __init__(self, policy_key: str):
        self.policy_key = policy_key
        super().__init__(f"Policy '{policy_key}' ist bereits aktiv und kann nicht erneut eingefuehrt werden")


class PolicyNotActiveError(Exception):
    """Repeal einer Policy, die es nicht gibt oder die bereits zurueckgezogen
    wurde (repealed_turn ist schon gesetzt)."""

    def __init__(self, policy_key: str):
        self.policy_key = policy_key
        super().__init__(f"Policy '{policy_key}' ist nicht aktiv und kann nicht zurueckgezogen werden")


class PolicyRequiredByActivePolicyError(Exception):
    """Democracy-4-Vorbild: manche Policies sind voneinander abhaengig
    (Policy.requires). Ein Repeal, das eine noch aktive, abhaengige Policy
    ihrer Voraussetzung beraubt, wird abgelehnt -- statt stillschweigend
    inkonsistente Zustaende zuzulassen."""

    def __init__(self, policy_key: str, dependent_policy_key: str):
        self.policy_key = policy_key
        self.dependent_policy_key = dependent_policy_key
        super().__init__(
            f"Policy '{policy_key}' kann nicht zurueckgezogen werden, solange '{dependent_policy_key}' "
            f"aktiv ist und sie voraussetzt"
        )


@dataclass
class PolicyEffect:
    """Wirkung mit weichem Ein- statt hartem Ausblenden (Democracy-4-Vorbild:
    "Inertia" als exponentieller Glaettungsfaktor statt fixem Zeitfenster,
    siehe docs/architecture.md Abschnitt "Game-Director-Review").

    Die Wirkung naehert sich `magnitude` asymptotisch an -- je groesser
    `inertia`, desto traeger/langsamer. Sie faellt NICHT nach einer festen
    Rundenzahl wieder weg (das war der alte duration_turns-Ansatz); sie
    bleibt auf dem erreichten Niveau, solange die Policy aktiv ist.
    """

    statistic_key: str
    magnitude: float       # Zielwert, dem sich die Wirkung annaehert
    delay_turns: int = 0   # Runden bis die Wirkung ueberhaupt einsetzt
    inertia: int = 3       # Traegheit: groesser = langsamere Annaeherung


@dataclass
class Policy:
    key: str
    name: str
    one_time_cost: float = 0.0
    upkeep_cost: float = 0.0
    capital_cost: float = 0.0  # Political-Capital-Kosten, siehe SimState.political_capital

    # Democracy-4-Vorbild: echte Einnahmen-Policies (z.B. Steuern) statt eines
    # unsichtbaren Pauschal-Zuschusses -- der Spieler sieht/waehlt den Hebel,
    # der Geld bringt, und kann ihn per Repeal auch wieder abschalten (siehe
    # engine.py::advance_turn, "Wo kommen positive Budget-Werte her?").
    income_per_turn: float = 0.0

    effects: list[PolicyEffect] = field(default_factory=list)

    # P1-Punkt "Policy-Pfade/Voraussetzungen" (docs/game-design-roadmap.md):
    # Policy-Keys, die bereits AKTIV sein muessen, bevor diese Policy
    # eingefuehrt werden kann. Erzwingt Reihenfolge-Entscheidungen zusaetzlich
    # zu Kombinations-Entscheidungen (Vorbild: Frostpunks Tech-Baum, Tropicos
    # Ministerien-Fortschritt) -- bewusst ohne grosse Tech-Baum-UI im MVP.
    requires: list[str] = field(default_factory=list)


@dataclass
class VoterGroup:
    name: str
    population_share: float
    satisfaction: float = 50.0
    weight_economy: float = 1.0
    weight_social: float = 1.0
    weight_environment: float = 1.0

    # P2-Punkt "Zufriedenheits-Momentum/Glaettung" (docs/game-design-roadmap.md):
    # gleitender Durchschnitt der Zufriedenheitsreaktion (nicht der Zufrieden-
    # heit selbst). Ein einzelner grosser Ausschlag (z.B. ein hartes Dilemma)
    # wirkt dadurch ueber mehrere Runden nachklingend statt in einer Runde
    # schlagartig -- analog zum Policy-Inertia-Modell, siehe engine.py::
    # _apply_reaction.
    satisfaction_momentum: float = 0.0


@dataclass
class EventRule:
    key: str
    statistic_key: str
    operator: str  # einer von >, <, >=, <=, ==, !=
    threshold: float
    template_text: str
    cooldown_turns: int = 5
    effects: list[PolicyEffect] = field(default_factory=list)


@dataclass
class DilemmaOption:
    """Eine von mehreren Antwortmoeglichkeiten auf ein Dilemma-Event
    (P1-Punkt "Dilemma-Events mit echten Entscheidungsoptionen"). Im
    Unterschied zu einem passiven EventRule-Effekt WAEHLT der Spieler
    aktiv zwischen mind. zwei Optionen mit unterschiedlichen Effekt-Sets --
    das ist laut Frostpunk/Suzerain-Vorbild der wichtigste einzelne
    Erfolgsfaktor des Genres (siehe docs/game-design-roadmap.md)."""

    key: str
    label: str
    effects: list[PolicyEffect] = field(default_factory=list)
    budget_cost: float = 0.0  # einmalige Budget-Wirkung dieser Wahl (kann negativ sein)


@dataclass
class DilemmaRule:
    """Trigger wie EventRule, aber mit `options` statt einem festen Effekt.
    Wird ausgeloest wie ein Event (Schwellenwert-Vergleich, Cooldown,
    Schweregrad-Priorisierung bei mehreren gleichzeitig eligible Regeln,
    siehe dilemmas.py), pausiert aber den weiteren Rundenfortschritt bis
    der Spieler eine Option gewaehlt hat (siehe engine.py::advance_turn /
    resolve_dilemma)."""

    key: str
    statistic_key: str
    operator: str
    threshold: float
    prompt_text: str
    options: list[DilemmaOption]
    cooldown_turns: int = 8


@dataclass
class PendingDilemma:
    """Ein ausgeloestes, aber noch nicht aufgeloestes Dilemma. Wird Teil des
    SimState, bis resolve_dilemma() aufgerufen wird -- solange es gesetzt
    ist, lehnt advance_turn() weitere Runden ab (DilemmaPendingError)."""

    rule_key: str
    prompt: str
    options: list[DilemmaOption]


@dataclass
class EnactedPolicy:
    policy_key: str
    enacted_turn: int

    # Democracy-4-Vorbild: Policies werden nicht sofort geloescht, sondern
    # "abgeschaltet" -- ihre Wirkung klingt symmetrisch zum Aufbau wieder ab
    # (siehe engine.py::_effect_delta), statt schlagartig zu verschwinden.
    # None = weiterhin aktiv. WICHTIG: SimState.clone() kopiert
    # active_policies nur flach (gleiche EnactedPolicy-Instanzen) -- ein
    # Repeal muss den Eintrag daher per Ersetzung (neues EnactedPolicy-Objekt)
    # aendern, niemals per In-Place-Mutation eines bestehenden Objekts.
    repealed_turn: int | None = None


@dataclass
class EffectAttribution:
    """Ein einzelner Statistik-Delta-Beitrag mitsamt Quelle (Game-Director-
    Review, P0-Punkt "Zufriedenheits-Attribution"): ohne das sieht der
    Spieler nur die Endzahl, nie welche Policy/welches Event sie verursacht
    hat -- schlechtes Feedback-Loop-Design (MDA: Dynamics nicht lesbar)."""

    source: str  # Policy-Key, "event:<event_key>", oder "dilemma:<dilemma_key>:<option_key>"
    statistic_key: str
    delta: float


@dataclass
class ElectionResult:
    """Ergebnis einer Wahl am Ende eines Zyklus (turns_until_election == 0).

    approval ist die nach population_share gewichtete Durchschnitts-
    zufriedenheit aller Waehlergruppen; won=True wenn approval >= threshold.
    """

    approval: float
    threshold: float
    won: bool


@dataclass
class ActiveSituation:
    """B2 "Situations-Layer (mittlerer Zeithorizont, mit Hysterese)"
    (BACKLOG.md): eine momentan aktive Situation (ausgeloest, weil die
    Schwelle erreicht wurde, und seitdem am Wirken). Die Situation bleibt
    aktiv, bis ihr UNTERER Schwellenwert (mit Hysterese) unterschritten wird
    (siehe SituationRule.deactivate_threshold / deactivate_op)."""

    rule_key: str
    since_turn: int


@dataclass
class SituationRule:
    """B2: ein Zustand, der bei Statistik-Schwelle X EINTRITT und erst bei
    einer ANDEREN, niedrigeren Schwelle Y wieder AUSTRITT (Hysterese) --
    selbsttragende Spirale mit eigenem Effekt auf Statistiken. Anders als
    EventRule: Events sind passiv/einmalig, Situations sind aktiv/periodisch
    und selbstverstärkend.

    Beispiel `abwanderung`: aktiviert bei gdp_growth < -0.5, bleibt aktiv
    solange, bremst unemployment_rate weiter, deaktiviert erst wieder bei
    gdp_growth > 0.5. Mit explizitem Gegen-Hebel (z.B. bildungsoffensive
    hebt gdp_growth) ist die Spirale durchbrechbar (L3).
    """

    key: str
    statistic_key: str
    activate_op: str  # einer von >, <, >=, <=, ==, !=
    activate_threshold: float
    deactivate_op: str  # muss "entgegengesetzt" zu activate_op sein
    deactivate_threshold: float
    effects: list[PolicyEffect] = field(default_factory=list)
    template_text: str = ""


@dataclass
class TermSummary:
    """B1 "Legislatur-Bogen & Amtszeit-Debrief" (BACKLOG.md): Rueckblick auf
    eine gerade abgeschlossene Legislaturperiode, von advance_turn() genau am
    Wahl-Turn zusammen mit dem ElectionResult zurueckgegeben.

    Reiner Lesewert -- keine Sim-Wirkung, kein Score-Gate. Harte Szenario-
    Siegbedingungen ("CO2 unter X bis Legislaturende") sind bewusst NICHT
    Teil von B1, sondern eine offene Design-Frage (BACKLOG.md F1/B9).
    """

    term_start_turn: int
    term_end_turn: int
    start_approval: float
    end_approval: float
    budget_start: float
    budget_end: float
    dilemmas_faced: int
    events_experienced: int

    # Netto-Veraenderung je Statistik ueber die Legislaturperiode (Ende minus
    # Start). Nur Statistiken mit tatsaechlicher Bewegung sind enthalten.
    statistic_changes: dict[str, float]

    # Summe der waehlerwirksam gerichteten Veraenderungen je Kategorie
    # (economy/social/environment): positiv = unterm Strich besser fuer die
    # Waehler, negativ = schlechter. Nutzt dieselbe Richtungs-/Kategorie-
    # Zuordnung wie die Zufriedenheitsreaktion (engine.py::_STAT_DIRECTION /
    # _STAT_CATEGORY), damit "Verbesserung" hier dasselbe heisst wie im Spiel.
    category_changes: dict[str, float]

    # Statistik-Key mit der groessten waehlerwirksamen Verbesserung bzw.
    # Verschlechterung ueber die Periode (None, wenn es in die jeweilige
    # Richtung keine Bewegung gab).
    biggest_improvement: str | None
    biggest_decline: str | None


@dataclass
class TurnResult:
    """Rueckgabe von engine.advance_turn -- geordnete Alternative zu einem
    wachsenden Tupel, damit spaetere Erweiterungen nicht wieder alle
    Aufrufer per Tupel-Unpacking brechen.
    """

    state: SimState
    events: list[str]
    attributions: list[EffectAttribution]
    election_result: ElectionResult | None = None

    # P1-Punkt "Dilemma-Events": gesetzt, wenn diese Runde ein neues Dilemma
    # ausgeloest hat. Der Aufrufer (Backend) muss vor der naechsten Runde
    # resolve_dilemma() aufrufen -- advance_turn() lehnt sonst ab.
    pending_dilemma: PendingDilemma | None = None

    # B1 (BACKLOG.md): nur am Wahl-Turn gesetzt (gleichzeitig mit
    # election_result), sonst None.
    term_summary: TermSummary | None = None


@dataclass
class SimState:
    turn: int
    budget: float
    statistics: dict[str, float]
    voter_groups: list[VoterGroup]
    active_policies: list[EnactedPolicy] = field(default_factory=list)
    event_cooldowns: dict[str, int] = field(default_factory=dict)

    # Zweite Ressource neben dem Geldbudget (Democracy-Vorbild: "politisches
    # Kapital", generiert durch loyale Minister, begrenzt wie viele Reformen
    # gleichzeitig durchsetzbar sind -- verhindert, dass beliebig viele
    # guenstige Policies auf einmal aktiviert werden).
    political_capital: float = 10.0

    # Countdown bis zur naechsten Wahl (Game-Director-Review, P0-Punkt
    # "Wahlmechanik"): war zuvor ein totes Feld nur im DB-Modell, jetzt Teil
    # der eigentlichen Simulation, damit der Balance-Runner Wahlzyklen
    # mittesten kann.
    turns_until_election: int = 16

    # P1-Punkt "Dilemma-Events": Cooldowns analog zu event_cooldowns, plus
    # ein aktuell offenes, noch nicht aufgeloestes Dilemma (falls vorhanden).
    dilemma_cooldowns: dict[str, int] = field(default_factory=dict)
    pending_dilemma: PendingDilemma | None = None

    # B2 "Situations-Layer (mittlerer Zeithorizont, mit Hysterese)" (BACKLOG.md):
    # liste von momentan aktiven Situations (ausgeloeste Zustaende mit Hysterese,
    # die sich selbst verstaerken und graduelle Spiralen erzeugen -- "Story ohne
    # Text"). regelbasiert ausgeloest wie Events, aber mit Deaktivierungs-
    # Schwellenwert < Aktivierungs-Schwelle und eigenen Effekten pro Runde
    # (weich via _effect_delta, wie Policies).
    active_situations: list[ActiveSituation] = field(default_factory=list)

    # B1 "Legislatur-Bogen & Amtszeit-Debrief" (BACKLOG.md): Schnappschuss der
    # Werte zu Beginn der laufenden Legislaturperiode plus laufende Zaehler.
    # advance_turn() befuellt sie beim ersten Aufruf lazy und setzt sie nach
    # jeder Wahl auf den neuen Zyklus zurueck; am Wahl-Turn dienen sie als
    # Basis fuer die TermSummary. Persistenz: reine Session-Felder analog
    # turns_until_election (backend/app/models/game.py + sim_bridge.py).
    term_start_turn: int = 0
    term_start_budget: float = 0.0
    term_start_statistics: dict[str, float] = field(default_factory=dict)
    term_start_approval: float = 50.0
    term_dilemma_count: int = 0
    term_event_count: int = 0

    def clone(self) -> "SimState":
        return SimState(
            turn=self.turn,
            budget=self.budget,
            statistics=dict(self.statistics),
            voter_groups=[VoterGroup(**vars(vg)) for vg in self.voter_groups],
            active_policies=list(self.active_policies),
            event_cooldowns=dict(self.event_cooldowns),
            political_capital=self.political_capital,
            turns_until_election=self.turns_until_election,
            dilemma_cooldowns=dict(self.dilemma_cooldowns),
            pending_dilemma=self.pending_dilemma,
            active_situations=list(self.active_situations),
            term_start_turn=self.term_start_turn,
            term_start_budget=self.term_start_budget,
            term_start_statistics=dict(self.term_start_statistics),
            term_start_approval=self.term_start_approval,
            term_dilemma_count=self.term_dilemma_count,
            term_event_count=self.term_event_count,
        )
