"""Kern der Simulation: eine Runde vorwaerts rechnen.

Inertia-Modell (nach Game-Director-Review, siehe docs/architecture.md):
Policy-Effekte naehern sich ihrem Zielwert exponentiell geglaettet an
(inspiriert von Democracy 4s "Inertia"-Parameter) statt in einem festen
Zeitfenster linear zu wirken und danach abrupt zu verschwinden. Eine
Foerderung, die noch aktiv ist und noch bezahlt wird, hoert nicht "zufaellig"
nach N Runden auf zu wirken -- sie bleibt auf dem erreichten Niveau.

Zweite Ressource neben dem Budget: Political Capital (siehe SimState),
begrenzt wie viele Reformen gleichzeitig durchsetzbar sind.

P0-Nachschaerfung (Game-Design-Roadmap, docs/game-design-roadmap.md):
- Jeder Statistik-Delta wird mit seiner Quelle (Policy/Event) attribuiert
  (EffectAttribution), damit Backend/Frontend erklaeren koennen, WARUM sich
  eine Zahl geaendert hat -- vorher war das eine Blackbox.
- turns_until_election ist jetzt Teil der eigentlichen Simulation (vorher
  ein totes Feld nur im DB-Modell) und fuehrt zu einem echten
  Wahlergebnis (ElectionResult) statt dass das Spiel nie endet.
- Nebeneffekt beim Aufraeumen: Event-Effekte flossen bisher NIE in die
  Zufriedenheitsreaktion ein (sie wurden nach der Zufriedenheits-Berechnung
  angewendet) -- ein echter Bug, jetzt mitbehoben.

P1-Ausbaustufe (docs/game-design-roadmap.md):
- Policy-Voraussetzungen (Policy.requires): eine Policy kann erst
  eingefuehrt werden, wenn ihre Voraussetzungen bereits aktiv sind
  (UnmetPrerequisiteError sonst) -- schafft Reihenfolge-Entscheidungen.
- Dilemma-Events (DilemmaRule/DilemmaOption): wie Events regelbasiert
  ausgeloest, aber mit echten Entscheidungsoptionen statt festem Effekt.
  Ein ausgeloestes Dilemma PAUSIERT den weiteren Rundenfortschritt
  (DilemmaPendingError), bis resolve_dilemma() aufgerufen wurde -- das
  erzwingt eine bewusste Spielerentscheidung statt eines automatischen
  Effekts, siehe Frostpunks Book of Laws / Suzerain als Vorbild.

P2-Ausbaustufe (docs/game-design-roadmap.md):
- Namens-Vignetten (vignettes.py): Event-/Dilemma-Texte bekommen eine kurze
  fiktive Stimme angehaengt, passend zur betroffenen Statistik-Kategorie.
- Zufriedenheits-Momentum (_apply_reaction): die Reaktion einer Waehler-
  gruppe wirkt nicht mehr sofort in voller Staerke, sondern als
  exponentiell geglaetteter gleitender Durchschnitt -- macht das Spielgefuehl
  ruhiger/vorhersagbarer, analog zum Policy-Inertia-Modell.
"""
from __future__ import annotations

import operator as _operator

from landtag_sim.dilemmas import evaluate_dilemmas
from landtag_sim.events import evaluate_events
from landtag_sim.reports import evaluate_reports
from landtag_sim.situations import evaluate_situations
from landtag_sim.models import (
    DelayedEffect,
    DilemmaOption,
    DilemmaPendingError,
    DilemmaRule,
    EffectAttribution,
    ElectionProjection,
    ElectionProjectionGroup,
    ElectionResult,
    EnactedPolicy,
    GoalResult,
    InsufficientCapitalError,
    PendingDilemma,
    Policy,
    PolicyAlreadyActiveError,
    PolicyLockedError,
    PolicyNotActiveError,
    PolicyRequiredByActivePolicyError,
    ReportRule,
    RivalParty,
    ScenarioGoal,
    SimState,
    SituationRule,
    TermSummary,
    TurnResult,
    UnmetPrerequisiteError,
)
from landtag_sim.vignettes import with_vignette

# Verhindert Zufriedenheits-/Statistikwerte, die absurd aus dem Ruder laufen
# und Balance-Runs unbrauchbar machen.
SATISFACTION_MIN, SATISFACTION_MAX = 0.0, 100.0

# Regeneration/Obergrenze fuer Political Capital. Bewusst als Modulkonstanten
# statt Parameter -- fuer echtes Ministerien-/Loyalitaetssystem (spaeter,
# nicht MVP) hier ansetzen.
CAPITAL_PER_TURN = 3.0
CAPITAL_CAP = 10.0

# Nach-P2-Nachschaerfung (Balance-Audit 2026-09-09, siehe mistakes.md
# "Budget hatte nie eine Einnahmequelle"): das Budget kannte bis hierhin NUR
# Ausgaben (one_time_cost, upkeep_cost, Dilemma-budget_cost) und NIE eine
# Einnahme -- ohne Policy-Repeal-Mechanik (gibt es bewusst noch nicht)
# bedeutete das: JEDE aktive Policy mit upkeep_cost>0 drainiert das feste
# Start-Budget unaufhaltsam, unabhaengig von guter Politik. Eine simple,
# konstante Grundeinnahme (Landeshaushalt-Basissteuereinnahme, unabhaengig
# von Policies/Statistiken -- ein echtes Steuersatz-System ist bewusst
# ausserhalb des MVP-Scopes) laesst 1-2 gleichzeitig aktive Policies
# langfristig tragbar bleiben, waehrend 3-4 gleichzeitig weiterhin spuerbar
# Budget kosten (siehe test_no_dominant_policy_among_current_sample_policies
# in test_balance_runner.py, das den BUDGET_NEGATIV-Fall miterfasst).
BASE_BUDGET_INCOME_PER_TURN = 15.0

# Wahlmechanik: Schwellenwert fuer die gewichtete Durchschnittszufriedenheit,
# ab dem eine Wahl gewonnen ist, und Laenge des naechsten Zyklus nach einer
# Wahl (Wiederwahl moeglich -- das Spiel endet nicht hart bei LOST, siehe
# routes_game.py fuer die Entscheidung, ob eine Session nach der Wahl weiter
# spielbar bleibt).
ELECTION_APPROVAL_THRESHOLD = 50.0
ELECTION_CYCLE_LENGTH = 16

# B20 "Party-Legacy": der Partei-Ruf (0-100, 50 neutral) wirkt als globaler
# Multiplikator auf die gewichtete Zustimmung. REPUTATION_APPROVAL_SPAN steuert
# die maximale Auslenkung: bei Ruf 0 -> Faktor (1 - SPAN), bei Ruf 100 ->
# (1 + SPAN). 0.10 = bis zu ±10% Amtsbonus/-malus.
REPUTATION_APPROVAL_SPAN = 0.10

# Ruf-Anpassung nach einer Wahl (in routes_game.py angewendet, hier als
# gemeinsame Referenz): Sieg hebt den Ruf, Niederlage senkt ihn staerker
# (Abstrafung wiegt schwerer als Belohnung -- verhindert Ruf-Inflation ueber
# viele gewonnene Zyklen).
REPUTATION_GAIN_ON_WIN = 6.0
REPUTATION_LOSS_ON_DEFEAT = 8.0

# Mehrparteiensystem: Glaettung der Rivalen-Stimmenanteil-Drift pro Runde
# (EMA-Alpha, analog SATISFACTION_MOMENTUM_ALPHA). Klein = traege Gegner.
RIVAL_APPROVAL_ALPHA = 0.30
# Wie stark sich Waehler-Unzufriedenheit auf einer Achse in Rivalen-Zuspruch
# uebersetzt (Prozentpunkte pro "voll unzufrieden"-Einheit).
RIVAL_DISCONTENT_SCALE = 22.0

# P2-Punkt "Zufriedenheits-Momentum/Glaettung": Anteil der neuen Reaktion,
# der SOFORT einfliesst (Rest wirkt als nachklingender Ueberhang in
# Folgerunden weiter). Kleinerer Wert = traeger/ruhiger, siehe
# _apply_reaction.
SATISFACTION_MOMENTUM_ALPHA = 0.4

# B5 "Wahlprognose mit sichtbarem Turnout/Apathie" (BACKLOG.md, F4/L6):
# Apathie-Modell OHNE neues persistiertes Feld -- der geschaetzte Turnout
# einer Waehlergruppe wird aus `satisfaction` + Vorzeichen/Betrag von
# `satisfaction_momentum` abgeleitet (F4-Entscheidung: billiger als ein
# eigener `turnout`-Wert). Idee (L6): "lauwarme, abkuehlende Anhaenger bleiben
# zu Hause" -- eine Gruppe im MITTLEREN Zufriedenheitsband, deren
# Zufriedenheit faellt, hat eine reduzierte effektive Wahlbeteiligung.
# Wuetende Gegner (Zufriedenheit unter dem Floor) mobilisieren dagegen und
# zufriedene Anhaenger (ueber dem Ceiling) stimmen ohnehin ab -- beide mit
# vollem Gewicht. Nur die Prognose nutzt das; die echte Wahl in advance_turn
# bleibt bewusst beim ungewichteten _weighted_approval (siehe project_election).
TURNOUT_APATHY_FLOOR = 30.0
TURNOUT_APATHY_CEILING = 55.0
TURNOUT_MOMENTUM_FULL = 3.0  # momentum <= -diesem Wert -> maximale Apathie
TURNOUT_MIN = 0.6  # so weit kann die effektive Beteiligung einer Gruppe hoechstens fallen
TURNOUT_TREND_DEADZONE = 0.05  # |momentum| darunter zaehlt als "stabil"


def _policy_by_key(policies: list[Policy], key: str) -> Policy | None:
    return next((p for p in policies if p.key == key), None)


def _cumulative_fraction(effect, turns_since_enacted: int) -> float:
    """Anteil von `magnitude`, der nach `turns_since_enacted` Runden Aufbau
    (unter Beruecksichtigung von delay_turns) erreicht ist. Reine Hilfs-
    funktion fuer _effect_delta -- sowohl fuer den Aufbau (Policy aktiv) als
    auch als Ankerpunkt fuer den Abbau (Policy zurueckgezogen, siehe unten)."""
    t = turns_since_enacted - effect.delay_turns
    if t < 0:
        return 0.0
    alpha = 1.0 / max(effect.inertia, 1)
    return 1 - (1 - alpha) ** (t + 1)


def _effect_delta(
    effect,
    current_turn: int,
    enacted_turn: int,
    repealed_turn: int | None = None,
) -> float:
    """Delta-Beitrag DIESER Runde (nicht der kumulierte Gesamteffekt).

    contribution(t) = magnitude * (1 - (1-alpha)^t) naehert sich `magnitude`
    an; wir brauchen aber die Differenz zur Vorrunde, weil SimState.statistics
    bereits laufend kumulierte Werte haelt (jede Runde wird nur das Delta
    addiert, siehe advance_turn).

    Democracy-4-Vorbild fuer Repeal (siehe EnactedPolicy.repealed_turn):
    eine zurueckgezogene Policy verschwindet nicht schlagartig, sondern klingt
    SYMMETRISCH zum Aufbau wieder ab -- mit derselben Alpha-Rate, ausgehend
    von dem Anteil, der bis zur letzten Runde vor dem Repeal erreicht war
    ("frozen_fraction"). Das ist dieselbe exponentielle Glaettung wie beim
    Aufbau, nur rueckwaerts.
    """
    alpha = 1.0 / max(effect.inertia, 1)
    turns_since_enacted = current_turn - enacted_turn

    if repealed_turn is None or current_turn < repealed_turn:
        return effect.magnitude * (
            _cumulative_fraction(effect, turns_since_enacted)
            - _cumulative_fraction(effect, turns_since_enacted - 1)
        )

    # frozen_fraction = der Anteil von magnitude, der in der LETZTEN Runde vor
    # dem Repeal (current_turn == repealed_turn - 1) erreicht war. Ab da klingt
    # er mit derselben Alpha-Rate wieder ab -- symmetrisch zum Aufbau, d.h. der
    # erste Abbau-Schritt ist auch der groesste (bei turns_since_repeal == 0 ist
    # prev_fraction == frozen_fraction, das Delta ist der volle erste
    # Alpha-Schritt nach unten).
    turns_since_enacted_at_repeal = repealed_turn - enacted_turn
    frozen_fraction = _cumulative_fraction(effect, turns_since_enacted_at_repeal - 1)
    turns_since_repeal = current_turn - repealed_turn
    prev_fraction = frozen_fraction * (1 - alpha) ** turns_since_repeal
    current_fraction = frozen_fraction * (1 - alpha) ** (turns_since_repeal + 1)
    return effect.magnitude * (current_fraction - prev_fraction)


def _ideology_modifier(group: VoterGroup, ideology: str | None) -> float:
    """B23 Phase 3 (erweitert um Wählergruppen-Affinitäten): Berechne
    Ideologie-Affinitaets-Modifikator fuer eine Waehlergruppe.

    Zwei Ebenen:
    1. **Explizite Gruppen-Affinitaet** (ideology_preference/dislike):
       - +20% wenn group.ideology_preference == ideology
       - -5% wenn group.ideology_dislike == ideology
    2. **Gewichtungs-basierte Affinitaet** (weight_*-Felder, Fallback):
       - Green: +15% Umwelt (weight_environment > 1.2), -5% Wirtschaft
       - Red: +15% Sozial (weight_social > 1.2), -5% Wirtschaft
       - Blue: +15% Wirtschaft (weight_economy > 1.2), -10% Umwelt

    Normalisiert auf Multiplikator (z.B. +20% = 1.2, -5% = 0.95).
    """
    if ideology is None:
        return 1.0

    # Stufe 1: Explizite Affinity Check
    if ideology == group.ideology_preference:
        return 1.2
    if ideology == group.ideology_dislike:
        return 0.95

    # Stufe 2: Fallback zu gewichtungs-basierten Modifikatoren
    is_economy = group.weight_economy > 1.2
    is_social = group.weight_social > 1.2
    is_environment = group.weight_environment > 1.2

    if ideology == "green":
        if is_environment:
            return 1.15
        elif is_economy:
            return 0.95
        else:
            return 1.0
    elif ideology == "red":
        if is_social:
            return 1.15
        elif is_economy:
            return 0.95
        else:
            return 1.0
    elif ideology == "blue":
        if is_economy:
            return 1.15
        elif is_environment:
            return 0.90
        else:
            return 1.0

    return 1.0


def _reputation_multiplier(reputation: float) -> float:
    """B20 "Party-Legacy": bildet den Partei-Ruf (0-100) linear auf einen
    Zustimmungs-Multiplikator ab. 50 -> 1.0, 0 -> (1 - SPAN), 100 -> (1 + SPAN).
    """
    clamped = max(0.0, min(100.0, reputation))
    return 1.0 + (clamped - 50.0) / 50.0 * REPUTATION_APPROVAL_SPAN


def _weighted_approval(state: SimState) -> float:
    """Gewichtete durchschnittliche Zufriedenheit mit optionalem
    Ideologie-Modifikator (B23 Phase 3: Party-Ideologie wirkt auf Affinitaet)
    und Party-Legacy-Multiplikator (B20: Ruf aus vorherigen Legislaturen)."""
    total_share = sum(g.population_share for g in state.voter_groups) or 1.0
    weighted_sum = 0.0
    for g in state.voter_groups:
        modifier = _ideology_modifier(g, state.party_ideology)
        weighted_sum += g.satisfaction * modifier * g.population_share
    raw = weighted_sum / total_share
    return raw * _reputation_multiplier(state.party_reputation)


def _estimated_turnout(group) -> float:
    """B5 (BACKLOG.md, F4/L6): geschaetzte effektive Wahlbeteiligung einer
    Gruppe, abgeleitet aus Zufriedenheit + Zufriedenheits-Momentum -- KEIN
    eigenes persistiertes Feld.

    1.0 = volle Beteiligung. Reduziert wird nur fuer "lauwarme, abkuehlende
    Anhaenger": Zufriedenheit im Band [FLOOR, CEILING] UND fallendes Momentum.
    Je staerker das Momentum faellt, desto tiefer (linear bis TURNOUT_MIN).
    Wuetende Gegner (< FLOOR) und zufriedene Anhaenger (> CEILING) haben volle
    Beteiligung -- die einen mobilisieren, die anderen sind ohnehin dabei.
    """
    momentum = group.satisfaction_momentum
    if momentum >= 0:
        return 1.0
    if not (TURNOUT_APATHY_FLOOR <= group.satisfaction <= TURNOUT_APATHY_CEILING):
        return 1.0
    severity = min(1.0, -momentum / TURNOUT_MOMENTUM_FULL)
    return 1.0 - (1.0 - TURNOUT_MIN) * severity


def _turnout_weighted_approval(state: SimState) -> float:
    """Wie _weighted_approval, aber jede Gruppe zusaetzlich mit ihrer
    geschaetzten Beteiligung (_estimated_turnout) gewichtet. Faellt auf
    _weighted_approval zurueck, wenn rechnerisch niemand waehlen wuerde.
    Wendet auch Ideologie-Modifikatoren an (B23 Phase 3)."""
    total = sum(g.population_share * _estimated_turnout(g) for g in state.voter_groups)
    if total <= 0:
        return _weighted_approval(state)
    weighted_sum = sum(
        g.satisfaction
        * _ideology_modifier(g, state.party_ideology)
        * g.population_share
        * _estimated_turnout(g)
        for g in state.voter_groups
    )
    return weighted_sum / total * _reputation_multiplier(state.party_reputation)


# Ordnet jeder Rivalen-Ideologie die Missstands-Achsen zu, aus denen sie
# Zuspruch zieht: (statistik_key, ist_hoeher_schlechter, referenzwert, spanne).
# "score" = clamp((wert - ref) / span, 0, 1) bzw. invertiert -> [0..1]-Unzufriedenheit.
_RIVAL_DISCONTENT_AXES: dict[str, list[tuple[str, bool, float, float]]] = {
    # Gruene Opposition: profitiert von schmutziger Lage / stockender Energiewende
    "green": [
        ("co2_emissions", True, 45.0, 35.0),
        ("renewable_share", False, 45.0, 30.0),
    ],
    # Rote Opposition: profitiert von sozialer Schieflage
    "red": [
        ("unemployment_rate", True, 6.0, 4.0),
        ("healthcare_quality", False, 55.0, 25.0),
    ],
    # Blaue Opposition: profitiert von wirtschaftlicher Schwaeche
    "blue": [
        ("gdp_growth", False, 1.0, 2.5),
        ("unemployment_rate", True, 6.0, 4.0),
    ],
}


def _rival_discontent_score(state: SimState, ideology: str) -> float:
    """[0..1]: wie stark die aktuelle Lage der Ideologie einer Rivalen-Partei
    in die Haende spielt (Mittel ueber ihre Missstands-Achsen)."""
    axes = _RIVAL_DISCONTENT_AXES.get(ideology, [])
    if not axes:
        return 0.0
    scores = []
    for stat_key, higher_is_worse, ref, span in axes:
        value = state.statistics.get(stat_key, ref)
        raw = (value - ref) / span if higher_is_worse else (ref - value) / span
        scores.append(max(0.0, min(1.0, raw)))
    return sum(scores) / len(scores)


def _update_rival_approval(state: SimState) -> None:
    """Mehrparteiensystem: aktualisiert den Stimmenanteil jeder Rivalen-Partei
    in-place. Ziel = base_strength + Lage-Bonus; weiche EMA-Drift dorthin.
    Kein Zufall -- rein aus dem Sim-Zustand abgeleitet (reproduzierbar)."""
    if not state.rival_parties:
        return
    for rival in state.rival_parties:
        discontent = _rival_discontent_score(state, rival.ideology)
        target = rival.base_strength + discontent * RIVAL_DISCONTENT_SCALE
        target = max(0.0, min(100.0, target))
        delta = target - rival.approval
        rival.momentum = (
            RIVAL_APPROVAL_ALPHA * delta + (1.0 - RIVAL_APPROVAL_ALPHA) * rival.momentum
        )
        rival.approval = max(0.0, min(100.0, rival.approval + rival.momentum))


def _build_election_standings(
    state: SimState, player_approval: float, player_name: str = "Deine Partei"
) -> list[tuple[str, float]]:
    """Normalisiert Spieler-Zustimmung + Rivalen-Stimmenanteile auf 100% und
    gibt eine absteigend sortierte Rangliste [(name, prozent)] zurueck."""
    raw = [(player_name, max(0.0, player_approval))]
    raw += [(r.name, max(0.0, r.approval)) for r in state.rival_parties]
    total = sum(v for _, v in raw) or 1.0
    standings = [(name, round(v / total * 100.0, 1)) for name, v in raw]
    standings.sort(key=lambda t: t[1], reverse=True)
    return standings


def _calculate_coalition_viability(state: SimState, opposition_mode: bool) -> float:
    """M5 "Opposition-Loop" (BACKLOG.md B15): einheitliche Metrik fuer beide
    Rollen (Regierung/Opposition). Regierung wirkt durch objektive Stats +
    Waehler-Zufriedenheit; Opposition nur durch direkte Zufriedenheit
    (unabhaengig von Stats).

    - Regierung: 60% Zufriedenheit + 40% Wirtschafts-Performance
    - Opposition: 100% direkte Opposition-Zufriedenheit (keine Stats)

    Beide landen in [0, 100].
    """
    if not opposition_mode:
        # GOVERNMENT: gewichtete Zufriedenheit + Wirtschafts-Performance
        voter_score = _weighted_approval(state)

        # Vereinfachte Wirtschafts-Performance: GDP + (1-unemployment/10) normiert
        econ_component = (
            (state.statistics.get("gdp_growth", 0.0) + 5.0) / 10.0 +  # GDP im Band [-5, +5] → [0, 1]
            (1.0 - state.statistics.get("unemployment_rate", 5.0) / 10.0)  # unemployment im Band [0, 10%] → [1, 0]
        ) / 2.0
        econ_score = max(0.0, min(100.0, econ_component * 100.0))

        return 0.6 * voter_score + 0.4 * econ_score
    else:
        # OPPOSITION: gewichtete Opposition-Zufriedenheit aller Gruppen
        if not state.opposition_satisfaction:
            return 0.0
        total_share = sum(vg.population_share for vg in state.voter_groups) or 1.0
        return sum(
            state.opposition_satisfaction.get(vg.name, 0.0) * vg.population_share
            for vg in state.voter_groups
        ) / total_share


def project_election(state: SimState) -> ElectionProjection:
    """B5 "Wahlprognose mit sichtbarem Turnout/Apathie" (BACKLOG.md, F4/L6):
    Vorausschau auf den Wahlausgang aus dem aktuellen Zustand.

    `approval` ist EXAKT die Groesse, an der die echte Wahl in advance_turn
    haengt (_weighted_approval, ohne Turnout) -- die Prognose ist damit ein
    ehrlicher Punkt-Schaetzer, keine Blackbox (L6). `turnout_adjusted_approval`
    legt zusaetzlich das Apathie-Modell an (nur Anzeige/Fruehwarnung, siehe
    _estimated_turnout) und die Gruppen-Aufschluesselung zeigt, WER wackelt.
    """
    naive_approval = _weighted_approval(state)
    groups: list[ElectionProjectionGroup] = []
    for group in state.voter_groups:
        momentum = group.satisfaction_momentum
        if momentum > TURNOUT_TREND_DEADZONE:
            trend = "steigend"
        elif momentum < -TURNOUT_TREND_DEADZONE:
            trend = "fallend"
        else:
            trend = "stabil"
        groups.append(
            ElectionProjectionGroup(
                name=group.name,
                population_share=group.population_share,
                satisfaction=group.satisfaction,
                satisfaction_momentum=momentum,
                estimated_turnout=_estimated_turnout(group),
                trend=trend,
            )
        )
    return ElectionProjection(
        approval=naive_approval,
        turnout_adjusted_approval=_turnout_weighted_approval(state),
        threshold=ELECTION_APPROVAL_THRESHOLD,
        would_win=naive_approval >= ELECTION_APPROVAL_THRESHOLD,
        groups=groups,
    )


def _apply_reaction(state: SimState, attributions: list[EffectAttribution]) -> None:
    """Passt die Waehlerzufriedenheit anhand der uebergebenen Attributionen
    an (in-place auf `state`). Ausgelagert, weil sowohl advance_turn (Policy-
    +Event-Effekte einer Runde) als auch resolve_dilemma (Effekte der
    gewaehlten Dilemma-Option) dieselbe Reaktionslogik brauchen.

    P2-Punkt "Zufriedenheits-Momentum/Glaettung": die rohe Reaktion dieser
    Runde wird nicht direkt auf die Zufriedenheit addiert, sondern zuerst in
    `satisfaction_momentum` exponentiell geglaettet (EMA) -- ein einzelner
    grosser Ausschlag wirkt dadurch ueber mehrere Runden nachklingend statt
    schlagartig in einer Runde. `satisfaction_momentum` selbst ist der Wert,
    der jede Runde auf `satisfaction` addiert wird.
    """
    for group in state.voter_groups:
        raw_reaction = 0.0
        for attribution in attributions:
            raw_reaction += (
                attribution.delta * _category_weight(group, attribution.statistic_key) * _stat_direction(attribution.statistic_key)
            )
        group.satisfaction_momentum = (
            group.satisfaction_momentum * (1 - SATISFACTION_MOMENTUM_ALPHA) + raw_reaction * SATISFACTION_MOMENTUM_ALPHA
        )
        group.satisfaction = min(
            SATISFACTION_MAX, max(SATISFACTION_MIN, group.satisfaction + group.satisfaction_momentum)
        )


def _validate_prerequisites(
    policy_catalog: list[Policy],
    active_keys: set[str],
    newly_enacted_keys: list[str],
    newly_repealed_keys: list[str] | None = None,
) -> None:
    """P1-Punkt 'Policy-Pfade/Voraussetzungen': jede neu einzufuehrende
    Policy braucht alle in `requires` gelisteten Policy-Keys bereits als
    aktiv (entweder schon vorher aktiv, oder in dieser selben Runde vorher
    in `newly_enacted_keys` gelistet -- Reihenfolge innerhalb einer Runde
    spielt bewusst keine Rolle, nur DASS beide gewaehlt wurden).

    Repeal-erweitert: eine Voraussetzung, die DIESE Runde gleichzeitig
    zurueckgezogen wird (newly_repealed_keys), zaehlt NICHT mehr als aktiv --
    sonst koennte man in derselben Runde eine Policy einfuehren, deren
    Voraussetzung im selben Atemzug wegfaellt.
    """
    newly_repealed_keys = newly_repealed_keys or []
    already_or_newly_active = (active_keys - set(newly_repealed_keys)) | set(newly_enacted_keys)
    for key in newly_enacted_keys:
        policy = _policy_by_key(policy_catalog, key)
        if policy is None:
            continue
        for requirement in policy.requires:
            if requirement not in already_or_newly_active:
                raise UnmetPrerequisiteError(policy_key=key, missing_requirement=requirement)


_UNLOCK_OPERATORS = {
    ">": _operator.gt,
    "<": _operator.lt,
    ">=": _operator.ge,
    "<=": _operator.le,
    "==": _operator.eq,
    "!=": _operator.ne,
}


def policy_is_unlocked(policy: Policy, statistics: dict[str, float]) -> bool:
    """B7 'Dynamische Policy-Freischaltung': True, wenn ALLE unlock_conditions
    der Policy im gegebenen Statistik-Zustand erfuellt sind (UND-verknuepft);
    leere Bedingungsliste -> immer True (jederzeit verfuegbar, wie vor B7).

    Oeffentlich, weil auch das Backend (GET /policies-Annotation, Preview) und
    Tests dieselbe Logik brauchen -- eine zweite, abweichende Implementierung
    waere die klassische Divergenz-Falle."""
    return _first_unmet_unlock(policy, statistics) is None


def _first_unmet_unlock(policy: Policy, statistics: dict[str, float]) -> str | None:
    """Gibt die erste nicht erfuellte Freischalt-Bedingung als lesbaren String
    zurueck (z.B. 'renewable_share > 60.0'), oder None wenn alle erfuellt --
    fuer die Fehlermeldung/UI-Hinweis nuetzlicher als ein blosses False."""
    for cond in policy.unlock_conditions:
        compare = _UNLOCK_OPERATORS.get(cond.operator)
        if compare is None:
            raise ValueError(
                f"Unbekannter Operator in unlock_condition ({cond.statistic_key}): {cond.operator}"
            )
        value = statistics.get(cond.statistic_key)
        if value is None or not compare(value, cond.threshold):
            return f"{cond.statistic_key} {cond.operator} {cond.threshold}"
    return None


def _validate_unlocks(
    policy_catalog: list[Policy], newly_enacted_keys: list[str], statistics: dict[str, float]
) -> None:
    """B7: jede neu einzufuehrende Policy muss ihre unlock_conditions gegen den
    aktuellen Statistik-Zustand erfuellen -- sonst PolicyLockedError."""
    for key in newly_enacted_keys:
        policy = _policy_by_key(policy_catalog, key)
        if policy is None or not policy.unlock_conditions:
            continue
        unmet = _first_unmet_unlock(policy, statistics)
        if unmet is not None:
            raise PolicyLockedError(policy_key=key, unmet_condition=unmet)


def _validate_new_enactments(active_keys: set[str], newly_enacted_keys: list[str]) -> None:
    """Verhindert ein unbemerktes Doppel-Enact derselben, bereits aktiven
    Policy (vorher ein latenter Bug: die API liess das klaglos zu und
    verdoppelte damit still Effekte/Kosten, siehe mistakes.md)."""
    seen = set(active_keys)
    for key in newly_enacted_keys:
        if key in seen:
            raise PolicyAlreadyActiveError(key)
        seen.add(key)


def _validate_repeals(policy_catalog: list[Policy], active_keys: set[str], newly_repealed_keys: list[str]) -> None:
    """Repeal darf nur eine aktuell aktive Policy treffen (PolicyNotActiveError
    sonst) und darf keine noch aktive, abhaengige Policy ihrer Voraussetzung
    berauben (PolicyRequiredByActivePolicyError, Democracy-4-Vorbild: manche
    Policies sind ohne ihre Grundlage schlicht nicht sinnvoll weiterbetreibbar)."""
    remaining_active = active_keys - set(newly_repealed_keys)
    for key in newly_repealed_keys:
        if key not in active_keys:
            raise PolicyNotActiveError(key)
        for other_policy in policy_catalog:
            if other_policy.key in remaining_active and key in other_policy.requires:
                raise PolicyRequiredByActivePolicyError(policy_key=key, dependent_policy_key=other_policy.key)


# B2 "Stat-zu-Stat-Wirkungen" (BACKLOG.md, docs/b2-design-notes.md):
# VWL-Standard-Modelle, die Statistiken aufeinander wirken lassen.
# Reihenfolge in advance_turn: nach Policy-/Situation-Effekten, vor
# Dilemma-/Event-Auswertung (damit Schwellenwerte auf aktualisierten
# Werten basieren).

def _apply_delayed_effects(state: SimState, attributions: list[EffectAttribution]) -> None:
    """B2 "Solow-Modell (Humankapital)": Effekte mit Lag verwalten.
    Verzögerte Effekte (z.B. gutes Wachstum führt nach 2-3 Runden zu besserer
    Gesundheit) werden aus der Queue angewendet, wenn ihre Wartezeit abgelaufen ist.
    Wird am ANFANG von advance_turn aufgerufen (nach dem turn += 1)."""
    still_pending = []
    for delayed in state.delayed_effects:
        if state.turn >= delayed.trigger_turn + delayed.delay_turns:
            # Effekt ist fällig: anwenden
            state.statistics[delayed.statistic_key] = (
                state.statistics.get(delayed.statistic_key, 0.0) + delayed.magnitude
            )
            attributions.append(
                EffectAttribution(source=f"delayed:{delayed.source}", statistic_key=delayed.statistic_key, delta=delayed.magnitude)
            )
        else:
            # Noch nicht fällig, in die neue Queue
            still_pending.append(delayed)
    state.delayed_effects = still_pending


def _phillips_curve_and_solow(state: SimState, attributions: list[EffectAttribution]) -> None:
    """B2 "Phillips-Kurve + Solow-Modell" (BACKLOG.md, docs/b2-design-notes.md):
    Gegenseitige Abhängigkeiten zwischen Statistiken.

    (1) Phillips-Kurve: unemployment_rate ↔ gdp_growth
        - Wenn unemployment > 5% (NAIRU): gdp_growth senken um −0.1 pro Punkt über 5%
        - Wenn gdp_growth < 0%: unemployment_rate erhöhen um +0.15 pro Punkt unter 0%

    (2) Solow-Modell: gdp_growth → healthcare_quality (mit Lag)
        - Gutes Wachstum (gdp > 2%): queue healthcare +0.2 mit 2-Runden-Lag
        - Schlechtes Wachstum (gdp < 0%): sofort healthcare −0.3 (asymmetrisch!)

    Spielerisch abgestimmt (nicht empirisch kalibriert); Ziel ist mittlere
    Langzeitdynamik, nicht "gdp ist alles"."""

    unemployment = state.statistics.get("unemployment_rate", 5.0)
    gdp = state.statistics.get("gdp_growth", 1.0)
    healthcare = state.statistics.get("healthcare_quality", 60.0)

    # Phillips: unemployment auf gdp auswirken (spielerisch abgestimmt, nicht empirisch)
    # B2-Design-Notes: "eher fühlen, gdp wirkt langfristig" → extrem mild halten
    nairu = 5.0
    if unemployment > nairu:
        delta = -(unemployment - nairu) * 0.004  # winzig (demonstriert Mechanik, keine Messeffekte)
        state.statistics["gdp_growth"] = state.statistics.get("gdp_growth", 0.0) + delta
        attributions.append(
            EffectAttribution(source="phillips:unemployment_to_gdp", statistic_key="gdp_growth", delta=delta)
        )

    # Phillips: gdp auf unemployment auswirken
    if gdp < 0.0:
        delta = abs(gdp) * 0.008  # winzig (demonstriert Mechanik, keine Messeffekte)
        state.statistics["unemployment_rate"] = state.statistics.get("unemployment_rate", 5.0) + delta
        attributions.append(
            EffectAttribution(source="phillips:gdp_to_unemployment", statistic_key="unemployment_rate", delta=delta)
        )

    # Solow: gutes Wachstum → healthcare mit Lag
    if gdp > 2.0:
        # Queue einen delayed effect für 2 Runden später
        # B2-Design-Notes: "eher fühlen" → extrem mild, nur Demonstrationszweck
        state.delayed_effects.append(
            DelayedEffect(
                statistic_key="healthcare_quality",
                magnitude=0.01,  # winzig (demonstriert Mechanik)
                trigger_turn=state.turn,
                delay_turns=2,
                source="solow_boom"
            )
        )

    # Solow: schlechtes Wachstum → healthcare sofort (asymmetrisch!)
    if gdp < 0.0:
        delta = -0.02  # winzig (demonstriert Mechanik, keine Messeffekte)
        state.statistics["healthcare_quality"] = state.statistics.get("healthcare_quality", 60.0) + delta
        attributions.append(
            EffectAttribution(source="solow:recession", statistic_key="healthcare_quality", delta=delta)
        )


def advance_turn(
    state: SimState,
    policy_catalog: list[Policy],
    event_rules: list,
    newly_enacted_keys: list[str] | None = None,
    dilemma_rules: list[DilemmaRule] | None = None,
    newly_repealed_keys: list[str] | None = None,
    situation_rules: list[SituationRule] | None = None,
    report_rules: list[ReportRule] | None = None,
    scenario_goals: list[ScenarioGoal] | None = None,
) -> TurnResult:
    """Rechnet genau eine Runde. Gibt ein TurnResult zurueck (state, events,
    attributions, ggf. election_result/pending_dilemma/term_summary/reports).

    `report_rules` (B4, optional): rein textliche Presseschau-Meldungen ohne
    Sim-Wirkung. advance_turn haengt hoechstens einen Report an TurnResult.reports
    an und nur in Runden ohne Event/Dilemma (siehe Abschnitt 2c).

    Reine Funktion: state wird nicht mutiert, sondern geklont -- wichtig,
    damit der Balance-Runner und der Preview-Endpunkt (siehe
    backend/app/api/routes_game.py) denselben Ausgangszustand mehrfach
    wiederverwenden koennen, ohne Seiteneffekte. SimState.clone() kopiert
    active_policies nur FLACH (gleiche EnactedPolicy-Instanzen) -- ein Repeal
    ERSETZT den betroffenen Listeneintrag daher durch ein neues Objekt statt
    ihn in-place zu mutieren.

    Wirft DilemmaPendingError, wenn state.pending_dilemma noch gesetzt ist --
    der Aufrufer muss zuerst resolve_dilemma() aufrufen, bevor eine weitere
    Runde gespielt werden kann (siehe P1-Punkt "Dilemma-Events").

    Wirft UnmetPrerequisiteError, wenn eine neu einzufuehrende Policy eine
    noch nicht aktive Voraussetzung hat (siehe Policy.requires).

    Wirft PolicyLockedError (B7), wenn eine neu einzufuehrende Policy noch
    gesperrte unlock_conditions hat (Statistik-Schwellen im aktuellen Zustand
    nicht erfuellt, siehe Policy.unlock_conditions).

    Wirft PolicyAlreadyActiveError, wenn eine bereits aktive Policy erneut
    eingefuehrt werden soll, und PolicyNotActiveError/
    PolicyRequiredByActivePolicyError bei einem ungueltigen Repeal (siehe
    _validate_repeals).

    Wirft InsufficientCapitalError, wenn die neu einzufuehrenden UND die neu
    zurueckzuziehenden Policies zusammen mehr Political Capital kosten, als
    nach der Regeneration dieser Runde verfuegbar ist (Democracy-4-Vorbild:
    auch ein Repeal kostet politisches Kapital, siehe capital_cost) --
    bewusst VOR jeder anderen Aenderung geprueft, damit ein abgelehnter Zug
    den State nicht trotzdem mutiert.
    """
    if state.pending_dilemma is not None:
        raise DilemmaPendingError(state.pending_dilemma.rule_key)

    newly_enacted_keys = newly_enacted_keys or []
    newly_repealed_keys = newly_repealed_keys or []
    dilemma_rules = dilemma_rules or []
    situation_rules = situation_rules or []
    report_rules = report_rules or []
    scenario_goals = scenario_goals or []

    active_keys = {ep.policy_key for ep in state.active_policies if ep.repealed_turn is None}
    _validate_prerequisites(policy_catalog, active_keys, newly_enacted_keys, newly_repealed_keys)
    _validate_new_enactments(active_keys, newly_enacted_keys)
    _validate_repeals(policy_catalog, active_keys, newly_repealed_keys)
    # B7: Freischalt-Bedingungen gegen den Statistik-Zustand VOR dieser Runde
    # pruefen (das ist, was der Spieler beim Waehlen sieht) -- vor jeder
    # Mutation, damit ein gesperrter Zug den State nicht veraendert.
    _validate_unlocks(policy_catalog, newly_enacted_keys, state.statistics)

    new_state = state.clone()
    new_state.turn += 1

    attributions: list[EffectAttribution] = []

    # B2 "Stat-zu-Stat-Wirkungen": Delayed Effects aus vorherigen Runden
    # anwenden (z.B. Solow-Lag). Dies MUSS VOR allen Policy-/Situation-
    # Effekten passieren, damit die aktualisierten Werte für die Runde verwendet
    # werden.
    _apply_delayed_effects(new_state, attributions)

    # B1 "Legislatur-Bogen" (BACKLOG.md): beim allerersten Rundenwechsel einer
    # Session ist noch kein Term-Schnappschuss vorhanden -- dann den Zustand
    # VOR dieser Runde als Termbeginn festhalten. Nach einer Wahl setzt der
    # Wahl-Zweig unten das Tracking selbst auf den neuen Zyklus zurueck.
    if not new_state.term_start_statistics:
        new_state.term_start_turn = state.turn
        new_state.term_start_budget = state.budget
        new_state.term_start_statistics = dict(state.statistics)
        new_state.term_start_approval = _weighted_approval(state)
        new_state.term_dilemma_count = 0
        new_state.term_event_count = 0

    new_state.political_capital = min(CAPITAL_CAP, new_state.political_capital + CAPITAL_PER_TURN)
    new_state.budget += BASE_BUDGET_INCOME_PER_TURN

    required_capital = sum(
        (_policy_by_key(policy_catalog, key).capital_cost if _policy_by_key(policy_catalog, key) else 0.0)
        for key in newly_enacted_keys + newly_repealed_keys
    )
    if required_capital > new_state.political_capital:
        raise InsufficientCapitalError(required_capital, new_state.political_capital)
    new_state.political_capital -= required_capital

    for key in newly_enacted_keys:
        new_state.active_policies.append(EnactedPolicy(policy_key=key, enacted_turn=new_state.turn))
        policy = _policy_by_key(policy_catalog, key)
        if policy:
            new_state.budget -= policy.one_time_cost

    # Repeal ERSETZT den betroffenen Eintrag durch ein neues EnactedPolicy-
    # Objekt (siehe Docstring oben) -- der Eintrag bleibt in active_policies,
    # damit seine Effekte weiter abklingen koennen (siehe _effect_delta).
    for key in newly_repealed_keys:
        for index, enacted in enumerate(new_state.active_policies):
            if enacted.policy_key == key and enacted.repealed_turn is None:
                new_state.active_policies[index] = EnactedPolicy(
                    policy_key=enacted.policy_key,
                    enacted_turn=enacted.enacted_turn,
                    repealed_turn=new_state.turn,
                )
                break

    # 1) Policy-Effekte anwenden (weich, siehe _effect_delta) und Unterhalts-
    # kosten/Einnahmen verrechnen. Upkeep/Einnahmen laufen jede Runde, SOLANGE
    # die Policy noch nicht zurueckgezogen wurde (repealed_turn is None) --
    # die Effekte selbst laufen fuer zurueckgezogene Policies weiter (nur
    # abklingend statt aufbauend), siehe _effect_delta.
    for enacted in new_state.active_policies:
        policy = _policy_by_key(policy_catalog, enacted.policy_key)
        if policy is None:
            continue
        if enacted.repealed_turn is None:
            new_state.budget -= policy.upkeep_cost
            new_state.budget += policy.income_per_turn
        for effect in policy.effects:
            delta = _effect_delta(effect, new_state.turn, enacted.enacted_turn, enacted.repealed_turn)
            if delta:
                new_state.statistics[effect.statistic_key] = (
                    new_state.statistics.get(effect.statistic_key, 0.0) + delta
                )
                attributions.append(
                    EffectAttribution(source=policy.key, statistic_key=effect.statistic_key, delta=delta)
                )

    # 1b) Situation-Effekte anwenden (B2 "Situations-Layer", BACKLOG.md) -- NACH
    # Policies, damit sich die selbstverstaerkende Spirale aufbauen kann, aber
    # VOR Dilemmas/Events (damit ein Dilemma noch die aktuelle Liste sieht).
    # Hysterese-Logik: Situations aktivieren/deaktivieren per evaluate_situations,
    # dann Effekte pro aktiver Situation anwenden (konstant pro Runde, solange
    # aktiv -- kein exponentielles Aufbauen wie Policies).
    new_state.active_situations, situation_activated_texts = evaluate_situations(
        new_state, situation_rules
    )

    for active_sit in new_state.active_situations:
        # Alle aktiven Situations durchwuehlen: Effekte anwenden (mit _effect_delta
        # für exponentielles Aufbauen/Abklingen, nicht für Situations selbst, die
        # ja konstant-statisch sind, aber fuer ihre Politik-ähnliche Einbindung).
        # Moment: Situations sind nicht wie Policies mit enacted_turn -- sie haben
        # since_turn, was der Aktivierungs-Turn ist. Fuer Effekte gilt: _effect_delta
        # braucht enacted_turn (wann die Policy/Situation begann). Hier ist das
        # active_sit.since_turn. Aber Situations haben keinen repealed_turn, nur
        # while-sie-aktiv sind.
        # => Einfach: Effekte sind _konstant_ pro Runde, solange die Situation
        # aktiv ist (kein exponentielles Aufbauen wie Policies, sondern sofortiger,
        # konstanter Druck). Das ist die "selbstverstaerkende Spirale".
        rule = next((r for r in situation_rules if r.key == active_sit.rule_key), None)
        if rule is None:
            continue
        for effect in rule.effects:
            # Konstante Wirkung, solange aktiv (kein _effect_delta, das waere
            # exponentielles Aufbauen). Die Situation selbst ist "an" und wirkt
            # voll, solange Bedingung erfuellt.
            new_state.statistics[effect.statistic_key] = (
                new_state.statistics.get(effect.statistic_key, 0.0) + effect.magnitude
            )
            attributions.append(
                EffectAttribution(source=f"situation:{active_sit.rule_key}", statistic_key=effect.statistic_key, delta=effect.magnitude)
            )

    # 1c) Stat-zu-Stat-Wirkungen (B2 "Phillips-Kurve + Solow-Modell", BACKLOG.md) --
    # NACH Policy- und Situation-Effekten, VOR Dilemmas/Events, damit die
    # Schwellenwerte auf den aktuellen, gegenseitig beeinflussten Statistiken
    # basieren. Modelliert gegenseitige Abhängigkeiten zwischen unemployment,
    # gdp_growth, healthcare_quality (ökonomisch neutral, VWL-Standards).
    _phillips_curve_and_solow(new_state, attributions)

    # 2) Dilemmas auswerten -- VOR Events, denn ein ausgeloestes Dilemma ist
    # der "Headline"-Moment dieser Runde (Frostpunk/Suzerain-Vorbild) und
    # unterdrueckt bewusst ein gleichzeitig eligibles passives Event, um
    # Ueberladung zu vermeiden (siehe docs/game-design-roadmap.md, Punkt 4).
    pending_dilemmas = evaluate_dilemmas(new_state, dilemma_rules)
    pending_dilemma = None
    event_texts: list[str] = []
    triggered_event_keys: list[str] = []  # B6: maschinenlesbare Regel-Keys
    if pending_dilemmas:
        pending_dilemma = pending_dilemmas[0]
        new_state.pending_dilemma = pending_dilemma
        new_state.term_dilemma_count += 1  # B1: Dilemmas dieser Legislaturperiode
        rule = next((r for r in dilemma_rules if r.key == pending_dilemma.rule_key), None)
        if rule:
            new_state.dilemma_cooldowns[rule.key] = rule.cooldown_turns
            # P2-Punkt "Namens-Vignetten": Prompt-Text bekommt eine kurze
            # fiktive Stimme angehaengt, passend zur betroffenen Statistik.
            category = _STAT_CATEGORY.get(rule.statistic_key)
            if category:
                pending_dilemma.prompt = with_vignette(
                    pending_dilemma.prompt, category, seed_key=f"{rule.key}:{new_state.turn}"
                )
    else:
        # 2b) Events auswerten (regelbasiert, siehe events.py) -- VOR der
        # Zufriedenheits-Berechnung, damit ihre Effekte in dieselbe Reaktion
        # einfliessen (vorher ein Bug: Event-Effekte veraenderten Statistiken,
        # wirkten sich aber nie auf die Waehlerzufriedenheit aus, siehe
        # Modul-Docstring). Bewusst feuert weiterhin nur das dringendste
        # Event pro Runde (evaluate_events liefert nach Schweregrad sortiert)
        # -- vermeidet Event-Spam in einer einzigen Runde.
        triggered = evaluate_events(new_state, event_rules)
        if triggered:
            rule, text = triggered[0]
            new_state.term_event_count += 1  # B1: Ereignisse dieser Legislaturperiode
            # P2-Punkt "Namens-Vignetten": siehe Dilemma-Zweig oben.
            category = _STAT_CATEGORY.get(rule.statistic_key)
            if category:
                text = with_vignette(text, category, seed_key=f"{rule.key}:{new_state.turn}")
            event_texts.append(text)
            triggered_event_keys.append(rule.key)  # B6
            new_state.event_cooldowns[rule.key] = rule.cooldown_turns
            for effect in rule.effects:
                new_state.statistics[effect.statistic_key] = (
                    new_state.statistics.get(effect.statistic_key, 0.0) + effect.magnitude
                )
                attributions.append(
                    EffectAttribution(
                        source=f"event:{rule.key}", statistic_key=effect.statistic_key, delta=effect.magnitude
                    )
                )
    for key in list(new_state.event_cooldowns):
        if new_state.event_cooldowns[key] > 0:
            new_state.event_cooldowns[key] -= 1
    for key in list(new_state.dilemma_cooldowns):
        if new_state.dilemma_cooldowns[key] > 0:
            new_state.dilemma_cooldowns[key] -= 1

    # 2c) Presseschau / narrative Konsequenz-Ebene (B4 "Narrative Konsequenz-
    # Ebene", BACKLOG.md, L5). Rein textlich -- KEINE Statistik-Wirkung, keine
    # Attribution, keine Zufriedenheitsreaktion. Frequenz-Management: nur in
    # Runden OHNE Event und OHNE Dilemma, und dann hoechstens EIN Report
    # (Reports treten bewusst hinter die "echten" Ereignisse zurueck).
    report_texts: list[str] = []
    if report_rules and not event_texts and pending_dilemma is None:
        current_active_keys = {
            ep.policy_key for ep in new_state.active_policies if ep.repealed_turn is None
        }
        eligible_reports = evaluate_reports(new_state, report_rules, current_active_keys)
        if eligible_reports:
            report_rule, report_text = eligible_reports[0]
            # P2-Punkt "Namens-Vignetten": passend zur Kategorie der ersten
            # Bedingung -- gleiche Technik wie bei Events/Dilemmas.
            category = _STAT_CATEGORY.get(report_rule.conditions[0].statistic_key)
            if category:
                report_text = with_vignette(
                    report_text, category, seed_key=f"report:{report_rule.key}:{new_state.turn}"
                )
            report_texts.append(report_text)
            new_state.report_cooldowns[report_rule.key] = report_rule.cooldown_turns
    for key in list(new_state.report_cooldowns):
        if new_state.report_cooldowns[key] > 0:
            new_state.report_cooldowns[key] -= 1

    # 3) Waehlerzufriedenheit auf Basis ALLER attribuierten Deltas dieser Runde
    # (Policies + Events) anpassen. Vereinfachtes, aber nachvollziehbares Modell:
    # jede Gruppe reagiert gewichtet auf Aenderungen, die grob in
    # economy/social/environment kategorisiert sind (siehe data/README.md).
    # Ein ausgeloestes (aber noch nicht aufgeloestes) Dilemma traegt selbst
    # noch keine Effekte bei -- die kommen erst mit resolve_dilemma().
    _apply_reaction(new_state, attributions)

    # 3b) Mehrparteiensystem: Rivalen-Stimmenanteile aus der aktuellen Lage
    # fortschreiben (weiche EMA-Drift, kein Zufall). No-op ohne Rivalen.
    _update_rival_approval(new_state)

    # 4) Wahlmechanik: Countdown fortschreiben, bei Erreichen von 0 Ergebnis
    # berechnen und Zyklus neu starten (Wiederwahl moeglich -- ob eine Session
    # nach LOST beendet wird, entscheidet die aufrufende Schicht, siehe
    # backend/app/api/routes_game.py).
    new_state.turns_until_election -= 1
    election_result: ElectionResult | None = None
    term_summary: TermSummary | None = None
    if new_state.turns_until_election <= 0:
        approval = _weighted_approval(new_state)
        # Wahlausgang: mit Rivalen zaehlt die Pluralitaet (hoechster
        # Stimmenanteil gewinnt), sonst der klassische Schwellenwert.
        if new_state.rival_parties:
            standings = _build_election_standings(new_state, approval)
            player_share = next(
                (pct for name, pct in standings if name == "Deine Partei"), 0.0
            )
            won = player_share >= max(pct for _, pct in standings)
        else:
            standings = []
            won = approval >= ELECTION_APPROVAL_THRESHOLD
        election_result = ElectionResult(
            approval=approval,
            threshold=ELECTION_APPROVAL_THRESHOLD,
            won=won,
            standings=standings,
        )
        # B1 (BACKLOG.md): Bilanz der gerade abgelaufenen Legislaturperiode
        # bauen -- BEVOR das Term-Tracking auf den naechsten Zyklus
        # zurueckgesetzt wird.
        term_summary = _build_term_summary(new_state, approval, scenario_goals)
        new_state.turns_until_election = ELECTION_CYCLE_LENGTH
        new_state.term_start_turn = new_state.turn
        new_state.term_start_budget = new_state.budget
        new_state.term_start_statistics = dict(new_state.statistics)
        new_state.term_start_approval = approval
        new_state.term_dilemma_count = 0
        new_state.term_event_count = 0

    return TurnResult(
        state=new_state,
        events=event_texts,
        attributions=attributions,
        election_result=election_result,
        pending_dilemma=pending_dilemma,
        term_summary=term_summary,
        reports=report_texts,
        triggered_event_keys=triggered_event_keys,
    )


def _goal_metric_value(state: SimState, end_approval: float, metric: str) -> float | None:
    """B9: loest den Zielwert-Bezug auf -- Sonderwerte "budget"/"approval",
    sonst ein Statistik-Key. None, wenn die Statistik unbekannt ist."""
    if metric == "budget":
        return state.budget
    if metric == "approval":
        return end_approval
    return state.statistics.get(metric)


def _evaluate_goals(
    state: SimState, end_approval: float, scenario_goals: list[ScenarioGoal]
) -> list[GoalResult]:
    """B9: prueft jedes optionale Legislatur-Ziel gegen den Endzustand.
    Unbekannter Metrik-Bezug -> als nicht erfuellt gewertet (statt Absturz)."""
    results: list[GoalResult] = []
    for goal in scenario_goals:
        compare = _UNLOCK_OPERATORS.get(goal.operator)
        if compare is None:
            raise ValueError(f"Unbekannter Operator in ScenarioGoal '{goal.key}': {goal.operator}")
        value = _goal_metric_value(state, end_approval, goal.metric)
        met = value is not None and compare(value, goal.threshold)
        results.append(GoalResult(key=goal.key, description=goal.description, met=met))
    return results


def _build_term_summary(
    state: SimState, end_approval: float, scenario_goals: list[ScenarioGoal] | None = None
) -> TermSummary:
    """Baut die TermSummary (B1) aus den term_start_*-Schnappschuessen auf
    `state` und dessen aktuellem Zustand. `end_approval` wird uebergeben,
    weil der Aufrufer die gewichtete Zustimmung fuer das ElectionResult
    ohnehin schon berechnet hat. `scenario_goals` (B9) werden gegen den
    Endzustand ausgewertet und als erfuellt/verfehlt beigelegt.
    """
    statistic_changes: dict[str, float] = {}
    for key, end_value in state.statistics.items():
        start_value = state.term_start_statistics.get(key, end_value)
        change = end_value - start_value
        if change:
            statistic_changes[key] = change

    # Richtungs-korrigierte Veraenderung: positiv = besser fuer die Waehler,
    # unabhaengig davon ob die Rohzahl gestiegen oder gesunken ist.
    category_changes: dict[str, float] = {}
    voter_effect: dict[str, float] = {}
    for key, change in statistic_changes.items():
        directed = change * _stat_direction(key)
        voter_effect[key] = directed
        category = _STAT_CATEGORY.get(key, "economy")
        category_changes[category] = category_changes.get(category, 0.0) + directed

    biggest_improvement = max(voter_effect, key=voter_effect.get, default=None)
    biggest_decline = min(voter_effect, key=voter_effect.get, default=None)
    if biggest_improvement is not None and voter_effect[biggest_improvement] <= 0:
        biggest_improvement = None
    if biggest_decline is not None and voter_effect[biggest_decline] >= 0:
        biggest_decline = None

    return TermSummary(
        term_start_turn=state.term_start_turn,
        term_end_turn=state.turn,
        start_approval=state.term_start_approval,
        end_approval=end_approval,
        budget_start=state.term_start_budget,
        budget_end=state.budget,
        dilemmas_faced=state.term_dilemma_count,
        events_experienced=state.term_event_count,
        statistic_changes=statistic_changes,
        category_changes=category_changes,
        biggest_improvement=biggest_improvement,
        biggest_decline=biggest_decline,
        goals=_evaluate_goals(state, end_approval, scenario_goals or []),
    )


def resolve_dilemma(state: SimState, dilemma_rules: list[DilemmaRule], option_key: str) -> TurnResult:
    """Wendet die vom Spieler gewaehlte Option eines offenen Dilemmas an.

    Anders als advance_turn() zaehlt dies KEINE Runde -- Political Capital,
    Wahl-Countdown etc. wurden bereits in der Runde verarbeitet, die das
    Dilemma ausgeloest hat (siehe advance_turn, Abschnitt 2). Wirft
    ValueError, wenn kein Dilemma offen ist oder der Options-Key unbekannt
    ist -- beides Programmierfehler des Aufrufers, kein Spielzustand.
    """
    if state.pending_dilemma is None:
        raise ValueError("Kein offenes Dilemma zum Aufloesen vorhanden")

    rule = next((r for r in dilemma_rules if r.key == state.pending_dilemma.rule_key), None)
    if rule is None:
        raise ValueError(f"Unbekanntes Dilemma: {state.pending_dilemma.rule_key}")
    option: DilemmaOption | None = next((o for o in rule.options if o.key == option_key), None)
    if option is None:
        raise ValueError(f"Unbekannte Option '{option_key}' fuer Dilemma '{rule.key}'")

    new_state = state.clone()
    new_state.pending_dilemma = None
    new_state.budget -= option.budget_cost

    attributions = [
        EffectAttribution(source=f"dilemma:{rule.key}:{option.key}", statistic_key=effect.statistic_key, delta=effect.magnitude)
        for effect in option.effects
    ]
    for attribution in attributions:
        new_state.statistics[attribution.statistic_key] = (
            new_state.statistics.get(attribution.statistic_key, 0.0) + attribution.delta
        )
    _apply_reaction(new_state, attributions)

    return TurnResult(state=new_state, events=[], attributions=attributions, election_result=None, pending_dilemma=None)


# Grobe Statistik->Kategorie Zuordnung fuer die Zufriedenheits-Gewichtung.
# Bewusst simpel gehalten (Dict statt Regelwerk) -- bei Bedarf pro Statistik
# in StatisticDefinition.category (DB) spiegeln und von dort laden.
_STAT_CATEGORY = {
    "unemployment_rate": "economy",
    "gdp_growth": "economy",
    "education_spending": "social",
    "healthcare_quality": "social",
    "co2_emissions": "environment",
    "renewable_share": "environment",
}


def _category_weight(group, stat_key: str) -> float:
    category = _STAT_CATEGORY.get(stat_key, "economy")
    return {
        "economy": group.weight_economy,
        "social": group.weight_social,
        "environment": group.weight_environment,
    }[category]


# Vorzeichen: +1 wenn ein hoeherer Wert fuer die Waehlerzufriedenheit gut ist,
# -1 wenn ein hoeherer Wert schlecht ist (z.B. Arbeitslosigkeit, Emissionen).
# WICHTIG bei neuen Statistiken immer mitpflegen, sonst wirkt der Effekt
# invertiert -- der Balance-Runner (sim/tools/balance_runner.py) hilft, das
# ueber die Trendrichtung der Zufriedenheit aufzudecken.
_STAT_DIRECTION = {
    "unemployment_rate": -1.0,
    "gdp_growth": 1.0,
    "education_spending": 1.0,
    "healthcare_quality": 1.0,
    "co2_emissions": -1.0,
    "renewable_share": 1.0,
}


def _stat_direction(stat_key: str) -> float:
    return _STAT_DIRECTION.get(stat_key, 1.0)
