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

from landtag_sim.dilemmas import evaluate_dilemmas
from landtag_sim.events import evaluate_events
from landtag_sim.models import (
    DilemmaOption,
    DilemmaPendingError,
    DilemmaRule,
    EffectAttribution,
    ElectionResult,
    EnactedPolicy,
    InsufficientCapitalError,
    PendingDilemma,
    Policy,
    SimState,
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

# Wahlmechanik: Schwellenwert fuer die gewichtete Durchschnittszufriedenheit,
# ab dem eine Wahl gewonnen ist, und Laenge des naechsten Zyklus nach einer
# Wahl (Wiederwahl moeglich -- das Spiel endet nicht hart bei LOST, siehe
# routes_game.py fuer die Entscheidung, ob eine Session nach der Wahl weiter
# spielbar bleibt).
ELECTION_APPROVAL_THRESHOLD = 50.0
ELECTION_CYCLE_LENGTH = 16

# P2-Punkt "Zufriedenheits-Momentum/Glaettung": Anteil der neuen Reaktion,
# der SOFORT einfliesst (Rest wirkt als nachklingender Ueberhang in
# Folgerunden weiter). Kleinerer Wert = traeger/ruhiger, siehe
# _apply_reaction.
SATISFACTION_MOMENTUM_ALPHA = 0.4


def _policy_by_key(policies: list[Policy], key: str) -> Policy | None:
    return next((p for p in policies if p.key == key), None)


def _effect_delta(effect, turns_since_enacted: int) -> float:
    """Delta-Beitrag DIESER Runde (nicht der kumulierte Gesamteffekt).

    contribution(t) = magnitude * (1 - (1-alpha)^t) naehert sich `magnitude`
    an; wir brauchen aber die Differenz zur Vorrunde, weil SimState.statistics
    bereits laufend kumulierte Werte haelt (jede Runde wird nur das Delta
    addiert, siehe advance_turn).
    """
    t = turns_since_enacted - effect.delay_turns
    if t < 0:
        return 0.0
    alpha = 1.0 / max(effect.inertia, 1)
    contrib_today = 1 - (1 - alpha) ** (t + 1)
    contrib_yesterday = 1 - (1 - alpha) ** t if t > 0 else 0.0
    return effect.magnitude * (contrib_today - contrib_yesterday)


def _weighted_approval(state: SimState) -> float:
    total_share = sum(g.population_share for g in state.voter_groups) or 1.0
    return sum(g.satisfaction * g.population_share for g in state.voter_groups) / total_share


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


def _validate_prerequisites(policy_catalog: list[Policy], active_keys: set[str], newly_enacted_keys: list[str]) -> None:
    """P1-Punkt 'Policy-Pfade/Voraussetzungen': jede neu einzufuehrende
    Policy braucht alle in `requires` gelisteten Policy-Keys bereits als
    aktiv (entweder schon vorher aktiv, oder in dieser selben Runde vorher
    in `newly_enacted_keys` gelistet -- Reihenfolge innerhalb einer Runde
    spielt bewusst keine Rolle, nur DASS beide gewaehlt wurden)."""
    already_or_newly_active = active_keys | set(newly_enacted_keys)
    for key in newly_enacted_keys:
        policy = _policy_by_key(policy_catalog, key)
        if policy is None:
            continue
        for requirement in policy.requires:
            if requirement not in already_or_newly_active:
                raise UnmetPrerequisiteError(policy_key=key, missing_requirement=requirement)


def advance_turn(
    state: SimState,
    policy_catalog: list[Policy],
    event_rules: list,
    newly_enacted_keys: list[str] | None = None,
    dilemma_rules: list[DilemmaRule] | None = None,
) -> TurnResult:
    """Rechnet genau eine Runde. Gibt ein TurnResult zurueck (state, events,
    attributions, ggf. election_result/pending_dilemma).

    Reine Funktion: state wird nicht mutiert, sondern geklont -- wichtig,
    damit der Balance-Runner und der Preview-Endpunkt (siehe
    backend/app/api/routes_game.py) denselben Ausgangszustand mehrfach
    wiederverwenden koennen, ohne Seiteneffekte.

    Wirft DilemmaPendingError, wenn state.pending_dilemma noch gesetzt ist --
    der Aufrufer muss zuerst resolve_dilemma() aufrufen, bevor eine weitere
    Runde gespielt werden kann (siehe P1-Punkt "Dilemma-Events").

    Wirft UnmetPrerequisiteError, wenn eine neu einzufuehrende Policy eine
    noch nicht aktive Voraussetzung hat (siehe Policy.requires).

    Wirft InsufficientCapitalError, wenn die neu einzufuehrenden Policies
    mehr Political Capital kosten, als nach der Regeneration dieser Runde
    verfuegbar ist -- bewusst VOR jeder anderen Aenderung geprueft, damit
    ein abgelehnter Zug den State nicht trotzdem mutiert.
    """
    if state.pending_dilemma is not None:
        raise DilemmaPendingError(state.pending_dilemma.rule_key)

    newly_enacted_keys = newly_enacted_keys or []
    dilemma_rules = dilemma_rules or []

    _validate_prerequisites(
        policy_catalog, {ep.policy_key for ep in state.active_policies}, newly_enacted_keys
    )

    new_state = state.clone()
    new_state.turn += 1

    new_state.political_capital = min(CAPITAL_CAP, new_state.political_capital + CAPITAL_PER_TURN)

    required_capital = sum(
        (_policy_by_key(policy_catalog, key).capital_cost if _policy_by_key(policy_catalog, key) else 0.0)
        for key in newly_enacted_keys
    )
    if required_capital > new_state.political_capital:
        raise InsufficientCapitalError(required_capital, new_state.political_capital)
    new_state.political_capital -= required_capital

    for key in newly_enacted_keys:
        new_state.active_policies.append(EnactedPolicy(policy_key=key, enacted_turn=new_state.turn))
        policy = _policy_by_key(policy_catalog, key)
        if policy:
            new_state.budget -= policy.one_time_cost

    attributions: list[EffectAttribution] = []

    # 1) Policy-Effekte anwenden (weich, siehe _effect_delta) und Unterhaltskosten abziehen.
    # Upkeep laeuft jede Runde, solange die Policy aktiv ist -- kein Fenster-Gating
    # mehr wie im alten Modell (siehe Game-Director-Review, docs/architecture.md).
    for enacted in new_state.active_policies:
        policy = _policy_by_key(policy_catalog, enacted.policy_key)
        if policy is None:
            continue
        turns_since_enacted = new_state.turn - enacted.enacted_turn
        new_state.budget -= policy.upkeep_cost
        for effect in policy.effects:
            delta = _effect_delta(effect, turns_since_enacted)
            if delta:
                new_state.statistics[effect.statistic_key] = (
                    new_state.statistics.get(effect.statistic_key, 0.0) + delta
                )
                attributions.append(
                    EffectAttribution(source=policy.key, statistic_key=effect.statistic_key, delta=delta)
                )

    # 2) Dilemmas auswerten -- VOR Events, denn ein ausgeloestes Dilemma ist
    # der "Headline"-Moment dieser Runde (Frostpunk/Suzerain-Vorbild) und
    # unterdrueckt bewusst ein gleichzeitig eligibles passives Event, um
    # Ueberladung zu vermeiden (siehe docs/game-design-roadmap.md, Punkt 4).
    pending_dilemmas = evaluate_dilemmas(new_state, dilemma_rules)
    pending_dilemma = None
    event_texts: list[str] = []
    if pending_dilemmas:
        pending_dilemma = pending_dilemmas[0]
        new_state.pending_dilemma = pending_dilemma
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
            # P2-Punkt "Namens-Vignetten": siehe Dilemma-Zweig oben.
            category = _STAT_CATEGORY.get(rule.statistic_key)
            if category:
                text = with_vignette(text, category, seed_key=f"{rule.key}:{new_state.turn}")
            event_texts.append(text)
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

    # 3) Waehlerzufriedenheit auf Basis ALLER attribuierten Deltas dieser Runde
    # (Policies + Events) anpassen. Vereinfachtes, aber nachvollziehbares Modell:
    # jede Gruppe reagiert gewichtet auf Aenderungen, die grob in
    # economy/social/environment kategorisiert sind (siehe data/README.md).
    # Ein ausgeloestes (aber noch nicht aufgeloestes) Dilemma traegt selbst
    # noch keine Effekte bei -- die kommen erst mit resolve_dilemma().
    _apply_reaction(new_state, attributions)

    # 4) Wahlmechanik: Countdown fortschreiben, bei Erreichen von 0 Ergebnis
    # berechnen und Zyklus neu starten (Wiederwahl moeglich -- ob eine Session
    # nach LOST beendet wird, entscheidet die aufrufende Schicht, siehe
    # backend/app/api/routes_game.py).
    new_state.turns_until_election -= 1
    election_result: ElectionResult | None = None
    if new_state.turns_until_election <= 0:
        approval = _weighted_approval(new_state)
        election_result = ElectionResult(
            approval=approval, threshold=ELECTION_APPROVAL_THRESHOLD, won=approval >= ELECTION_APPROVAL_THRESHOLD
        )
        new_state.turns_until_election = ELECTION_CYCLE_LENGTH

    return TurnResult(
        state=new_state,
        events=event_texts,
        attributions=attributions,
        election_result=election_result,
        pending_dilemma=pending_dilemma,
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
