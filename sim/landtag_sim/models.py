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
        )
