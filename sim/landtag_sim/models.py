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


class PolicyLockedError(Exception):
    """B7 "Dynamische Policy-Freischaltung durch Sim-Zustand" (BACKLOG.md, L7):
    eine Policy hat `unlock_conditions`, die im aktuellen Statistik-Zustand
    (noch) nicht erfuellt sind -- sie ist gesperrt und kann nicht eingefuehrt
    werden. Anders als requires (verlangt eine andere AKTIVE Policy) haengt
    das Unlock an einem gesellschaftlichen Zustand (z.B. "renewable_share >
    60"), den der Spieler ueber die Zeit herbeifuehrt -- eine Verschiebung
    oeffnet neue Optionen."""

    def __init__(self, policy_key: str, unmet_condition: str):
        self.policy_key = policy_key
        self.unmet_condition = unmet_condition
        super().__init__(
            f"Policy '{policy_key}' ist noch gesperrt -- Freischalt-Bedingung nicht erfuellt: {unmet_condition}"
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
class UnlockCondition:
    """B7 "Dynamische Policy-Freischaltung durch Sim-Zustand" (BACKLOG.md, L7):
    eine Statistik-Schwelle, die erfuellt sein muss, damit eine Policy
    ueberhaupt einfuehrbar wird. Gleiche Struktur wie ReportCondition, aber
    bewusst ein eigener Typ -- semantisch etwas anderes (Freischaltung einer
    Option statt Ausloesung einer Meldung), und Policy soll nicht vom
    Report-Konzept abhaengen. Mehrere Conditions einer Policy sind
    UND-verknuepft."""

    statistic_key: str
    operator: str  # einer von >, <, >=, <=, ==, !=
    threshold: float


@dataclass
class Policy:
    key: str
    name: str
    # B10 (BACKLOG.md): kurze Wirkungsbeschreibung (ein bis zwei Saetze:
    # Haupteffekt + Trade-off). Rein fuer die Anzeige im Frontend-Katalog --
    # die Sim-Engine wertet das Feld nicht aus. Vorher setzte seed.py
    # description = name (totes Feld).
    description: str = ""
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

    # B7 "Dynamische Policy-Freischaltung durch Sim-Zustand" (BACKLOG.md, L7):
    # Statistik-Schwellen (UND-verknuepft), die erfuellt sein muessen, damit
    # diese Policy einfuehrbar wird. Ergaenzt `requires` (das eine andere
    # aktive Policy verlangt) um eine ZUSTANDS-abhaengige Freischaltung: eine
    # gesellschaftliche Verschiebung oeffnet neue Optionen, statt dass alles
    # von Anfang an waehlbar ist. Leer = jederzeit verfuegbar (wie bisher).
    unlock_conditions: list[UnlockCondition] = field(default_factory=list)


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
class Faction:
    """B8 "Fraktions-/Sitz-Datenmodell (Grundstein Opposition/Parlament)"
    (BACKLOG.md, L8): eine Fraktion im Landtag mit Sitzanzahl und grober
    Haltung auf den drei Themenachsen. **Nur Struktur, noch keine Mechanik**:
    im MVP rein zur Anzeige ("Sitzverteilung im Landtag"), es gibt KEINE
    Koalitionslogik und KEINEN Mehrheitszwang fuer Policies. Das Datenmodell
    wird bewusst jetzt schon richtig angelegt, damit ein spaeterer
    Opposition/Parlament-Ausbau nicht rueckwirkend brechen muss (vgl.
    architecture.md "nicht rueckwirkend aendern").

    `stance_*` liegt grob in [-1, 1]: negativ = die Fraktion draengt auf
    WENIGER staatliche Aktivitaet/Ausgaben auf dieser Achse, positiv = auf
    mehr. Reiner Anzeigewert im MVP (keine Sim-Wirkung).
    """

    name: str
    seats: int
    stance_economy: float = 0.0
    stance_social: float = 0.0
    stance_environment: float = 0.0


@dataclass
class EventRule:
    key: str
    statistic_key: str
    operator: str  # einer von >, <, >=, <=, ==, !=
    threshold: float
    template_text: str
    cooldown_turns: int = 5
    effects: list[PolicyEffect] = field(default_factory=list)

    # B3 "Zustandsgekoppelte Risiko-Events" (BACKLOG.md, L4/L9): bei erfuellter
    # Schwelle feuert die Regel nur mit dieser Wahrscheinlichkeit pro Runde.
    # 1.0 = immer (Verhalten wie vor B3), 0.0 = nie. Der "Wuerfel" ist
    # deterministisch aus Regel-Key + Runde abgeleitet (zlib.crc32, siehe
    # events.py::_passes_probability_gate) -- KEIN random, damit Balance-Runner
    # und Tests reproduzierbar bleiben. Zweck: "Vorstufen"-Regeln mit
    # erreichbarer Schwelle, die die Statistiken graduell Richtung einer sonst
    # unerreichbaren Krisenschwelle druecken (z.B. konjunkturdelle ->
    # rezession), ohne zu einem reinen Zufalls-Schock aus dem Nichts zu werden.
    probability: float = 1.0


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

    # B3 (BACKLOG.md): analog zu EventRule.probability -- bei erfuellter
    # Schwelle feuert das Dilemma nur mit dieser Wahrscheinlichkeit pro Runde
    # (deterministischer crc32-Wuerfel, siehe dilemmas.py).
    probability: float = 1.0


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
class ElectionProjectionGroup:
    """B5 "Wahlprognose mit sichtbarem Turnout/Apathie" (BACKLOG.md, F4/L6):
    die pro Waehlergruppe angezeigte Zeile der Vorausschau -- macht sichtbar,
    WER wackelt und warum (Zufriedenheit + Trend + geschaetzte Beteiligung).
    """

    name: str
    population_share: float
    satisfaction: float
    satisfaction_momentum: float
    estimated_turnout: float  # [0..1], 1.0 = volle Beteiligung
    trend: str  # "steigend" | "stabil" | "fallend"


@dataclass
class ElectionProjection:
    """B5 (BACKLOG.md, F4/L6): Vorausschau auf den Wahlausgang, damit die
    letzten Runden vor der Wahl nicht als Blackbox enden.

    `approval` ist die ENTSCHEIDUNGSRELEVANTE Zahl -- identisch zu dem, was
    die echte Wahl in engine.advance_turn prueft (nach population_share
    gewichtete Durchschnittszufriedenheit, OHNE Turnout). `would_win`
    vergleicht sie mit `threshold`. Es gibt hier also KEINE
    "90%-Prognose-dann-15%-Ergebnis"-Ueberraschung (L6): die Prognose nennt
    exakt die Zahl, an der die Wahl haengt.

    `turnout_adjusted_approval` ist dieselbe Groesse, aber mit modelliertem
    Apathie-Effekt (lauwarme, abkuehlende Anhaenger bleiben zu Hause) --
    reine Zusatzinformation/Fruehwarnung, sie entscheidet die Wahl NICHT.
    """

    approval: float
    turnout_adjusted_approval: float
    threshold: float
    would_win: bool
    groups: list[ElectionProjectionGroup]


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
class ReportCondition:
    """B4 "Narrative Konsequenz-Ebene" (BACKLOG.md): eine Teilbedingung einer
    ReportRule. Mehrere Conditions einer Regel sind UND-verknuepft."""

    statistic_key: str
    operator: str  # einer von >, <, >=, <=, ==, !=
    threshold: float


@dataclass
class ReportRule:
    """B4 "Narrative Konsequenz-Ebene ('Presseschau')" (BACKLOG.md, L5): ein
    rein TEXTLICHES Feedback, das die Kausalkette einer Entwicklung benennt
    ("Firma X schliesst wegen deiner Arbeitsmarkt-Politik"), OHNE
    Sim-Statistiken zu veraendern. Democracy 4s "Media Reports" -- laut
    Community der wirkungsvollste Griff gegen "meine Entscheidungen sind
    folgenlos".

    Feuert nur, wenn ALLE `conditions` erfuellt sind (UND), optionale
    `requires_policy`/`forbids_policy` zusaetzlich passen, und die Regel nicht
    im Cooldown ist. Frequenz-Management (L5): advance_turn wertet Reports
    NACH Events/Dilemmas aus und haengt hoechstens EINEN Report-Text an --
    und auch nur, wenn dieselbe Runde weder ein Event noch ein Dilemma hatte.
    """

    key: str
    conditions: list[ReportCondition]
    template_text: str
    cooldown_turns: int = 12
    requires_policy: str | None = None
    forbids_policy: str | None = None


@dataclass
class ScenarioGoal:
    """B9 "Szenario-/Legislatur-Ziele" (BACKLOG.md, L1/L10; F1 = optionale,
    unverbindliche Ziele): ein optionales Legislatur-Ziel, das am Ende einer
    Amtszeit gegen den Endzustand geprueft wird.

    Bewusst deklarativ (kein Lambda), damit es serialisierbar bleibt und wie
    andere Szenario-Daten behandelt werden kann. `metric` ist entweder ein
    Statistik-Key, oder die Sonderwerte "budget" bzw. "approval" (gewichtete
    Zustimmung wie bei der Wahl). MVP: nur End-Zustands-Pruefung (kein
    "ueber N Runden gehalten"), unverbindlich -- verfehlte Ziele beenden die
    Partie NICHT (die Sandbox bleibt ohne Ziele spielbar, F1).
    """

    key: str
    description: str
    metric: str  # Statistik-Key, "budget" oder "approval"
    operator: str  # einer von >, <, >=, <=, ==, !=
    threshold: float


@dataclass
class GoalResult:
    """B9: Auswertung eines ScenarioGoal am Legislaturende (Teil der
    TermSummary). Reiner Lesewert -- `met` treibt keine Sim-Logik."""

    key: str
    description: str
    met: bool


@dataclass
class TermSummary:
    """B1 "Legislatur-Bogen & Amtszeit-Debrief" (BACKLOG.md): Rueckblick auf
    eine gerade abgeschlossene Legislaturperiode, von advance_turn() genau am
    Wahl-Turn zusammen mit dem ElectionResult zurueckgegeben.

    Reiner Lesewert -- keine Sim-Wirkung, kein Score-Gate. Optionale
    Legislatur-Ziele (B9, `goals`) werden hier als erfuellt/verfehlt
    ausgewiesen, sind aber ebenfalls UNVERBINDLICH: ein verfehltes Ziel
    beendet die Partie nicht (F1-Entscheidung). Harte Siegbedingungen bleiben
    bewusst ausserhalb des Scopes.
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

    # B9 "Szenario-/Legislatur-Ziele" (BACKLOG.md): erfuellt/verfehlt je
    # optionalem Ziel, am Legislaturende gegen den Endzustand geprueft.
    # Leer, wenn keine Ziele definiert sind (reine Sandbox).
    goals: list[GoalResult] = field(default_factory=list)


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

    # B6 "Dilemma-/Event-Trigger-Telemetrie" (BACKLOG.md, L4): Schluessel der
    # in dieser Runde tatsaechlich gefeuerten EventRule(s) -- parallel zu
    # `events` (den gerenderten Texten). Aktuell feuert hoechstens ein Event
    # pro Runde, daher hoechstens ein Eintrag. Dilemmas sind ohnehin ueber
    # `pending_dilemma.rule_key` und Situations ueber
    # `state.active_situations` strukturell auslesbar -- fuer Events fehlte
    # bislang jede maschinenlesbare Quelle des Regel-Keys (nur der freie Text
    # war da), was den Balance-Runner sonst zu einer Cooldown-Heuristik
    # gezwungen haette. Reiner Lesewert, keine Sim-Wirkung.
    triggered_event_keys: list[str] = field(default_factory=list)

    # B1 (BACKLOG.md): nur am Wahl-Turn gesetzt (gleichzeitig mit
    # election_result), sonst None.
    term_summary: TermSummary | None = None

    # B4 "Narrative Konsequenz-Ebene" (BACKLOG.md): hoechstens ein narrativer
    # Presseschau-Text pro Runde, und nur in Runden ohne Event/Dilemma
    # (Frequenz-Management, L5). Reine Anzeige -- keine Sim-Wirkung.
    reports: list[str] = field(default_factory=list)


@dataclass
class DelayedEffect:
    """B2 "Stat-zu-Stat-Wirkungen" (BACKLOG.md): Effekt, der in einer
    zukuenftigen Runde ausgefuehrt wird (z.B. Solow-Lag: gdp_growth > 2%
    wird zu healthcare_quality +0.2 nach 2-3 Runden). Queue in SimState,
    engine.py appliziert diese pro Runde wenn trigger_turn + delay_turns
    erreicht ist."""
    statistic_key: str
    magnitude: float
    trigger_turn: int  # Runde, in der diese DelayedEffect erzeugt wurde
    delay_turns: int   # Warten bis turn >= trigger_turn + delay_turns
    source: str = "solow"  # Kennzeichnung: "solow" fuer Budgetlag, evtl. spaeter andere


@dataclass
class OppositionCampaign:
    """M5 "Opposition-Loop" (BACKLOG.md B15): Kampagne statt Policy fuer die
    Opposition. Beeinflusst Wähler-Zufriedenheit direkt (nicht Statistiken),
    kostet Political Capital, wirkt über Satisfaction-Momentum."""
    key: str
    name: str
    capital_cost: float  # z.B. 2.0 PC
    satisfaction_deltas: dict[str, float]  # pro Waehlergruppe: +/-Satisfaction
    description: str = ""


@dataclass
class SimState:
    turn: int
    budget: float
    statistics: dict[str, float]
    voter_groups: list[VoterGroup]
    active_policies: list[EnactedPolicy] = field(default_factory=list)
    event_cooldowns: dict[str, int] = field(default_factory=dict)

    # B2 "Stat-zu-Stat-Wirkungen" (BACKLOG.md): Queue fuer Effekte mit Lag
    # (z.B. Solow-Modell: gutes Wachstum fuehrt mit Verzoegerung zu besserer
    # Gesundheit). Diese werden in advance_turn pro Runde geprueft und
    # angewendet, wenn ihre Wartezeit abgelaufen ist.
    delayed_effects: list[DelayedEffect] = field(default_factory=list)

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

    # B4 "Narrative Konsequenz-Ebene" (BACKLOG.md): Cooldowns je ReportRule,
    # analog zu event_cooldowns -- verhindert, dass derselbe Presseschau-Text
    # in aufeinanderfolgenden Runden mehrfach erscheint.
    report_cooldowns: dict[str, int] = field(default_factory=dict)

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

    # M5 "Opposition-Loop" (BACKLOG.md B15): Opposition hat eigene Satisfaction
    # je Waehlergruppe (unabhaengig von Regierungs-Stats), aufgebaut via
    # PR-Kampagnen. opposition_mode=True bedeutet: Opposition ist Regierung,
    # Policies laufen weiter, Opposition spielt Kampagnen.
    opposition_mode: bool = False
    opposition_satisfaction: dict[str, float] = field(default_factory=dict)
    opposition_momentum: dict[str, float] = field(default_factory=dict)

    # B23 "Party-Gründung (Persistente Meta-Ebene)" Phase 3: Ideologie der
    # Partei (green/red/blue), wirkt auf Voter-Affinität-Modifikatoren.
    # None = keine Party-Ideologie (klassischer Modus), String = Party.ideology
    party_ideology: str | None = None

    def clone(self) -> "SimState":
        return SimState(
            turn=self.turn,
            budget=self.budget,
            statistics=dict(self.statistics),
            voter_groups=[VoterGroup(**vars(vg)) for vg in self.voter_groups],
            active_policies=list(self.active_policies),
            event_cooldowns=dict(self.event_cooldowns),
            delayed_effects=list(self.delayed_effects),
            political_capital=self.political_capital,
            turns_until_election=self.turns_until_election,
            dilemma_cooldowns=dict(self.dilemma_cooldowns),
            pending_dilemma=self.pending_dilemma,
            report_cooldowns=dict(self.report_cooldowns),
            active_situations=list(self.active_situations),
            term_start_turn=self.term_start_turn,
            term_start_budget=self.term_start_budget,
            term_start_statistics=dict(self.term_start_statistics),
            term_start_approval=self.term_start_approval,
            term_dilemma_count=self.term_dilemma_count,
            term_event_count=self.term_event_count,
            opposition_mode=self.opposition_mode,
            opposition_satisfaction=dict(self.opposition_satisfaction),
            opposition_momentum=dict(self.opposition_momentum),
            party_ideology=self.party_ideology,
        )
