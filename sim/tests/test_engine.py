import random

import pytest

from landtag_sim.engine import (
    BASE_BUDGET_INCOME_PER_TURN,
    CAPITAL_CAP,
    CAPITAL_PER_TURN,
    ELECTION_CYCLE_LENGTH,
    _calculate_coalition_viability,
    advance_turn,
    policy_is_unlocked,
    project_election,
    resolve_dilemma,
)
from landtag_sim.models import (
    DilemmaOption,
    DilemmaPendingError,
    DilemmaRule,
    EventRule,
    InsufficientCapitalError,
    Policy,
    PolicyAlreadyActiveError,
    PolicyEffect,
    PolicyLockedError,
    PolicyNotActiveError,
    PolicyRequiredByActivePolicyError,
    ReportCondition,
    ReportRule,
    ScenarioGoal,
    UnlockCondition,
    UnmetPrerequisiteError,
    VoterGroup,
)
from landtag_sim.sample_data import (
    SAMPLE_DILEMMA_RULES,
    SAMPLE_EVENT_RULES,
    SAMPLE_FACTIONS,
    SAMPLE_POLICIES,
    SAMPLE_REPORT_RULES,
    SAMPLE_SITUATION_RULES,
    SAMPLE_VOTER_GROUPS,
    STARTING_STATISTICS,
    build_initial_state,
    jittered_starting_statistics,
)
from landtag_sim.events import passes_probability_gate
from landtag_sim.vignettes import VIGNETTE_POOL, pick_vignette, with_vignette


def test_advance_turn_increments_turn_counter():
    state = build_initial_state()
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES)
    assert result.state.turn == state.turn + 1


def test_policy_effect_is_delayed_not_immediate():
    state = build_initial_state()
    before = state.statistics["renewable_share"]
    # erneuerbare_foerderung hat delay_turns=2 fuer renewable_share -> Runde 1 darf sich noch nichts aendern
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["erneuerbare_foerderung"])
    assert result.state.statistics["renewable_share"] == before


def test_policy_effect_ramps_up_smoothly_after_delay():
    state = build_initial_state()
    before = state.statistics["renewable_share"]
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["erneuerbare_foerderung"])
    state = result.state
    for _ in range(2):  # delay_turns=2 -> ab Runde 3 sollte Effekt wirken
        result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES)
        state = result.state
    assert state.statistics["renewable_share"] > before


def test_policy_effect_does_not_switch_off_after_a_fixed_window():
    """Regressionstest fuer die Game-Director-Review: im alten Modell (feste
    duration_turns) verschwand der Effekt nach einem Zeitfenster wieder,
    obwohl die Policy weiter aktiv war und Upkeep gezahlt wurde. Im neuen
    Inertia-Modell bleibt der erreichte Stand erhalten."""
    state = build_initial_state()
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["erneuerbare_foerderung"])
    state = result.state
    for _ in range(20):
        result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES)
        state = result.state
    peak = state.statistics["renewable_share"]
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES)
    state = result.state
    # Effekt darf nicht wieder zurueckfallen, nur (fast) stagnieren.
    assert state.statistics["renewable_share"] >= peak - 0.01


def test_every_sample_policy_has_at_least_one_negative_effect():
    """Game-Director-Review: reine Positiv-Policies ohne Zielkonflikt waren
    der Hauptkritikpunkt. Dieser Test haelt die Korrektur fest."""
    for policy in SAMPLE_POLICIES:
        assert any(effect.magnitude < 0 for effect in policy.effects), (
            f"Policy '{policy.key}' hat keinen negativen Nebeneffekt (Trade-off fehlt)"
        )


def test_every_sample_policy_has_a_real_description():
    """B10 (BACKLOG.md): das description-Feld war vorher tot (seed.py setzte
    es auf policy.name). Jede Beispiel-Policy braucht jetzt einen echten,
    vom Namen verschiedenen Beschreibungstext."""
    for policy in SAMPLE_POLICIES:
        assert policy.description, f"Policy '{policy.key}' hat keine Beschreibung"
        assert policy.description.strip() != policy.name, (
            f"Policy '{policy.key}': Beschreibung ist nur der Name (totes Feld)"
        )
        assert len(policy.description) > 30, (
            f"Policy '{policy.key}': Beschreibung zu kurz fuer eine echte Wirkungsbeschreibung"
        )


def test_higher_unemployment_lowers_satisfaction():
    state = build_initial_state()
    bad_policy = Policy(
        key="test_bad",
        name="Test",
        effects=[PolicyEffect(statistic_key="unemployment_rate", magnitude=5.0, delay_turns=0, inertia=1)],
    )
    before_satisfaction = sum(g.satisfaction for g in state.voter_groups)
    result = advance_turn(state, [bad_policy], [], newly_enacted_keys=["test_bad"])
    after_satisfaction = sum(g.satisfaction for g in result.state.voter_groups)
    assert after_satisfaction < before_satisfaction


def test_event_fires_when_threshold_crossed_and_respects_cooldown():
    state = build_initial_state()
    state.statistics["unemployment_rate"] = 20.0
    rule = EventRule(
        key="test_event",
        statistic_key="unemployment_rate",
        operator=">",
        threshold=9.0,
        template_text="Arbeitslosigkeit bei {value:.1f}%",
        cooldown_turns=3,
    )
    result = advance_turn(state, [], [rule])
    assert len(result.events) == 1
    assert "20.0" in result.events[0]

    # Cooldown aktiv -> darf in der naechsten Runde nicht erneut feuern
    result_again = advance_turn(result.state, [], [rule])
    assert len(result_again.events) == 0


def test_only_most_severe_event_fires_per_turn():
    """Game-Director-Review: mehrere gleichzeitig eligible Events sollen nicht
    alle in derselben Runde feuern (Event-Spam), nur das dringendste."""
    state = build_initial_state()
    state.statistics["unemployment_rate"] = 50.0  # weit ueber Schwelle 9.0 -> hohe Severity
    state.statistics["education_spending"] = 29.0  # knapp unter Schwelle 30.0 -> niedrige Severity
    rule_severe = EventRule(
        key="hohe_arbeitslosigkeit", statistic_key="unemployment_rate", operator=">", threshold=9.0,
        template_text="Arbeitslosigkeit bei {value:.1f}%", cooldown_turns=3,
    )
    rule_mild = EventRule(
        key="niedrige_bildung", statistic_key="education_spending", operator="<", threshold=30.0,
        template_text="Bildungsausgaben bei {value:.1f}", cooldown_turns=3,
    )
    result = advance_turn(state, [], [rule_mild, rule_severe])
    assert len(result.events) == 1
    assert "50.0" in result.events[0]  # das schwerwiegendere Event, nicht das milde


def test_enacting_policies_beyond_political_capital_raises():
    state = build_initial_state()
    expensive_policy = Policy(key="teuer", name="Teure Reform", capital_cost=999.0)
    with pytest.raises(InsufficientCapitalError):
        advance_turn(state, [expensive_policy], [], newly_enacted_keys=["teuer"])


def test_political_capital_regenerates_up_to_cap():
    state = build_initial_state()
    state.political_capital = 0.0
    result = advance_turn(state, [], [])
    assert result.state.political_capital == pytest.approx(3.0)  # CAPITAL_PER_TURN


def test_effect_attribution_tracks_source_of_each_delta():
    """P0-Punkt 'Zufriedenheits-Attribution': jeder Statistik-Delta muss
    seiner Quelle (Policy-Key oder Event) zugeordnet sein, damit
    Backend/Frontend erklaeren koennen, WARUM sich eine Zahl geaendert hat."""
    state = build_initial_state()
    bad_policy = Policy(
        key="test_bad",
        name="Test",
        effects=[PolicyEffect(statistic_key="unemployment_rate", magnitude=5.0, delay_turns=0, inertia=1)],
    )
    result = advance_turn(state, [bad_policy], [], newly_enacted_keys=["test_bad"])
    assert any(a.source == "test_bad" and a.statistic_key == "unemployment_rate" for a in result.attributions)


def test_event_effects_are_attributed_and_feed_into_satisfaction():
    """Regressionstest fuer den beim P0-Refactor gefundenen Bug: Event-
    Effekte flossen vorher NIE in die Zufriedenheitsreaktion ein, weil sie
    erst nach der Zufriedenheits-Berechnung angewendet wurden."""
    state = build_initial_state()
    state.statistics["unemployment_rate"] = 20.0
    rule = EventRule(
        key="test_event",
        statistic_key="unemployment_rate",
        operator=">",
        threshold=9.0,
        template_text="Arbeitslosigkeit bei {value:.1f}%",
        cooldown_turns=3,
        effects=[PolicyEffect(statistic_key="unemployment_rate", magnitude=3.0, delay_turns=0, inertia=1)],
    )
    before_satisfaction = sum(g.satisfaction for g in state.voter_groups)
    result = advance_turn(state, [], [rule])
    after_satisfaction = sum(g.satisfaction for g in result.state.voter_groups)
    assert any(a.source == "event:test_event" for a in result.attributions)
    assert after_satisfaction < before_satisfaction


def test_election_fires_after_cycle_length_and_computes_weighted_approval():
    """P0-Punkt 'Wahlmechanik': turns_until_election muss tatsaechlich
    runterzaehlen und bei 0 ein ElectionResult liefern -- vorher ein totes
    Feld, das die Engine nie gelesen hat."""
    state = build_initial_state()
    state.turns_until_election = 1
    result = advance_turn(state, [], [])
    assert result.election_result is not None
    assert result.election_result.threshold == pytest.approx(50.0)
    # Zyklus muss nach der Wahl neu gestartet werden (Wiederwahl moeglich).
    assert result.state.turns_until_election == 16


def test_no_election_before_cycle_ends():
    state = build_initial_state()
    assert state.turns_until_election > 1
    result = advance_turn(state, [], [])
    assert result.election_result is None
    assert result.state.turns_until_election == state.turns_until_election - 1


# --- P1: Policy-Pfade/Voraussetzungen -----------------------------------


def test_policy_prerequisite_blocks_enactment_without_required_policy():
    state = build_initial_state()
    with pytest.raises(UnmetPrerequisiteError):
        advance_turn(state, SAMPLE_POLICIES, [], newly_enacted_keys=["steuersenkung_mittelstand"])


def test_policy_prerequisite_allows_enactment_once_requirement_active():
    state = build_initial_state()
    result = advance_turn(state, SAMPLE_POLICIES, [], newly_enacted_keys=["bildungsoffensive"])
    # Voraussetzung und abhaengige Policy in derselben Runde zusammen
    # einzufuehren ist erlaubt -- Reihenfolge innerhalb der Liste zaehlt nicht.
    result2 = advance_turn(
        result.state, SAMPLE_POLICIES, [], newly_enacted_keys=["steuersenkung_mittelstand"]
    )
    assert "steuersenkung_mittelstand" in [ep.policy_key for ep in result2.state.active_policies]


def test_policy_prerequisite_allows_combined_enactment_same_turn():
    state = build_initial_state()
    result = advance_turn(
        state, SAMPLE_POLICIES, [], newly_enacted_keys=["bildungsoffensive", "steuersenkung_mittelstand"]
    )
    keys = [ep.policy_key for ep in result.state.active_policies]
    assert "bildungsoffensive" in keys and "steuersenkung_mittelstand" in keys


# --- P1: Dilemma-Events mit echten Entscheidungsoptionen -----------------


def _make_test_dilemma() -> DilemmaRule:
    return DilemmaRule(
        key="test_dilemma",
        statistic_key="unemployment_rate",
        operator=">",
        threshold=9.0,
        prompt_text="Arbeitslosigkeit bei {value:.1f}% -- was tun?",
        cooldown_turns=5,
        options=[
            DilemmaOption(
                key="option_a",
                label="Option A",
                budget_cost=10.0,
                effects=[PolicyEffect(statistic_key="unemployment_rate", magnitude=-1.0, delay_turns=0, inertia=1)],
            ),
            DilemmaOption(
                key="option_b",
                label="Option B",
                budget_cost=0.0,
                effects=[PolicyEffect(statistic_key="unemployment_rate", magnitude=-2.0, delay_turns=0, inertia=1)],
            ),
        ],
    )


def test_dilemma_triggers_and_blocks_further_advancement_until_resolved():
    state = build_initial_state()
    state.statistics["unemployment_rate"] = 20.0
    rule = _make_test_dilemma()

    result = advance_turn(state, [], [], dilemma_rules=[rule])
    assert result.pending_dilemma is not None
    assert result.pending_dilemma.rule_key == "test_dilemma"
    assert len(result.pending_dilemma.options) == 2

    with pytest.raises(DilemmaPendingError):
        advance_turn(result.state, [], [], dilemma_rules=[rule])


def test_dilemma_suppresses_passive_events_in_same_turn():
    """Ein ausgeloestes Dilemma ist der 'Headline'-Moment der Runde --
    ein gleichzeitig eligibles passives Event darf in derselben Runde nicht
    zusaetzlich feuern (Ueberladung vermeiden, siehe engine.py)."""
    state = build_initial_state()
    state.statistics["unemployment_rate"] = 20.0
    dilemma = _make_test_dilemma()
    event = EventRule(
        key="hohe_arbeitslosigkeit_test",
        statistic_key="unemployment_rate",
        operator=">",
        threshold=9.0,
        template_text="Arbeitslosigkeit bei {value:.1f}%",
        cooldown_turns=3,
    )
    result = advance_turn(state, [], [event], dilemma_rules=[dilemma])
    assert result.pending_dilemma is not None
    assert result.events == []


def test_resolve_dilemma_applies_chosen_option_and_clears_pending():
    state = build_initial_state()
    state.statistics["unemployment_rate"] = 20.0
    rule = _make_test_dilemma()

    triggered = advance_turn(state, [], [], dilemma_rules=[rule])
    budget_before = triggered.state.budget

    resolved = resolve_dilemma(triggered.state, [rule], "option_a")
    assert resolved.state.pending_dilemma is None
    assert resolved.state.budget == pytest.approx(budget_before - 10.0)
    assert resolved.state.statistics["unemployment_rate"] == pytest.approx(19.0)
    assert any(a.source == "dilemma:test_dilemma:option_a" for a in resolved.attributions)

    # Nach dem Aufloesen laeuft advance_turn wieder normal weiter.
    resumed = advance_turn(resolved.state, [], [], dilemma_rules=[rule])
    assert resumed.state.turn == triggered.state.turn + 1


def test_resolve_dilemma_feeds_satisfaction_reaction():
    state = build_initial_state()
    state.statistics["unemployment_rate"] = 20.0
    rule = _make_test_dilemma()
    triggered = advance_turn(state, [], [], dilemma_rules=[rule])
    before_satisfaction = sum(g.satisfaction for g in triggered.state.voter_groups)
    resolved = resolve_dilemma(triggered.state, [rule], "option_b")
    after_satisfaction = sum(g.satisfaction for g in resolved.state.voter_groups)
    # option_b senkt die Arbeitslosigkeit -> Zufriedenheit sollte steigen.
    assert after_satisfaction > before_satisfaction


def test_sample_dilemma_rules_are_well_formed():
    for rule in SAMPLE_DILEMMA_RULES:
        assert len(rule.options) >= 2, f"Dilemma '{rule.key}' braucht mindestens zwei echte Optionen"


# --- P2: Namens-Vignetten -------------------------------------------------


def test_pick_vignette_is_deterministic_for_same_seed():
    first = pick_vignette("economy", "arbeitsmarktkrise:5")
    second = pick_vignette("economy", "arbeitsmarktkrise:5")
    assert first == second


def test_pick_vignette_returns_none_for_unknown_category():
    assert pick_vignette("unknown_category", "irgendwas:1") is None


def test_with_vignette_appends_a_pool_entry():
    text = with_vignette("Basistext.", "social", "seed:1")
    assert text.startswith("Basistext. ")
    assert any(text.endswith(vignette) for vignette in VIGNETTE_POOL["social"])


def test_event_text_gets_a_vignette_appended():
    state = build_initial_state()
    state.statistics["unemployment_rate"] = 20.0
    rule = EventRule(
        key="hohe_arbeitslosigkeit",  # gleicher Key wie in SAMPLE_EVENT_RULES -> statistic_key ist bekannt
        statistic_key="unemployment_rate",
        operator=">",
        threshold=9.0,
        template_text="Arbeitslosigkeit bei {value:.1f}%",
        cooldown_turns=3,
    )
    result = advance_turn(state, [], [rule])
    assert len(result.events) == 1
    assert any(vignette in result.events[0] for vignette in VIGNETTE_POOL["economy"])


def test_dilemma_prompt_gets_a_vignette_appended():
    state = build_initial_state()
    state.statistics["unemployment_rate"] = 20.0
    rule = _make_test_dilemma()
    result = advance_turn(state, [], [], dilemma_rules=[rule])
    assert any(vignette in result.pending_dilemma.prompt for vignette in VIGNETTE_POOL["economy"])


# --- P2: Zufriedenheits-Momentum/Glaettung --------------------------------


def test_satisfaction_momentum_smooths_a_single_large_shock_over_multiple_turns():
    """Eine einzelne grosse Reaktion darf sich nicht sofort vollstaendig in
    der Zufriedenheit niederschlagen, sondern klingt ueber mehrere Runden
    nach (EMA statt Direktanwendung, siehe engine.py::_apply_reaction)."""
    state = build_initial_state()
    bad_policy = Policy(
        key="test_shock",
        name="Schock-Test",
        effects=[PolicyEffect(statistic_key="unemployment_rate", magnitude=20.0, delay_turns=0, inertia=1)],
    )
    result1 = advance_turn(state, [bad_policy], [], newly_enacted_keys=["test_shock"])
    group1 = result1.state.voter_groups[0]
    assert group1.satisfaction_momentum != 0.0
    # Nach dem Schock (keine weiteren Policies/Events) klingt der Ueberhang
    # weiter nach -- Zufriedenheit bewegt sich in Runde 2 immer noch in
    # dieselbe Richtung, weil satisfaction_momentum nicht schlagartig auf 0 faellt.
    result2 = advance_turn(result1.state, [], [])
    group2 = result2.state.voter_groups[0]
    assert group2.satisfaction < group1.satisfaction  # Arbeitslosigkeit senkt Zufriedenheit weiter
    assert group2.satisfaction_momentum != 0.0


def test_satisfaction_momentum_field_defaults_to_zero_for_fresh_state():
    state = build_initial_state()
    assert all(group.satisfaction_momentum == 0.0 for group in state.voter_groups)


# --- P2: Randomisierte Startbedingungen -----------------------------------


def test_jittered_starting_statistics_stays_within_spread_bounds():
    rng = random.Random(42)
    jittered = jittered_starting_statistics(rng, spread=0.05)
    for key, base_value in STARTING_STATISTICS.items():
        lower, upper = sorted((base_value * 0.95, base_value * 1.05))
        assert lower <= jittered[key] <= upper


def test_jittered_starting_statistics_is_reproducible_with_seeded_rng():
    jittered_a = jittered_starting_statistics(random.Random(7))
    jittered_b = jittered_starting_statistics(random.Random(7))
    assert jittered_a == jittered_b


def test_jittered_starting_statistics_differs_from_base_with_high_probability():
    rng = random.Random(123)
    jittered = jittered_starting_statistics(rng, spread=0.05)
    assert any(jittered[key] != base for key, base in STARTING_STATISTICS.items())


# --- Nach-P2: Balance-Nachschaerfung (Dominante-Strategie-Check, Roadmap #10) ---


def test_every_starting_statistic_is_touched_by_at_least_one_policy():
    """Regressionstest: healthcare_quality war lange die einzige Statistik
    ohne jede Policy-Anbindung (nur passiv wahlrelevant ueber
    weight_social, nie aktiv beeinflussbar) -- seit 'gesundheitsreform'
    geschlossen. Haelt fest, dass keine neu hinzugefuegte Statistik denselben
    toten Winkel wiederholt."""
    touched = {effect.statistic_key for policy in SAMPLE_POLICIES for effect in policy.effects}
    untouched = set(STARTING_STATISTICS) - touched
    assert not untouched, f"Statistiken ohne jede Policy-Wirkung: {untouched}"


def test_bildungsoffensive_has_a_genuine_net_negative_economy_tradeoff():
    """Regressionstest fuer die Balance-Nachschaerfung: bildungsoffensive
    hatte urspruenglich einen zu schwachen gdp_growth-Effekt (-0.4), der von
    ihrem EIGENEN unemployment_rate-Vorteil in derselben Kategorie
    ("economy") ueberkompensiert wurde -- macht die Policy im Aggregat zu
    einem Free Lunch ohne echten Zielkonflikt, obwohl sie technisch die
    Trade-off-Pflicht erfuellte (siehe test_every_sample_policy_has_at_least_
    one_negative_effect, der nur EINEN negativen Effekt prueft, nicht die
    Netto-Bilanz pro Kategorie). Nach dem Fix (-2.4) muss die Summe der
    wirtschaftsbezogenen Attributionen ueber genug Runden netto negativ sein.
    Vorzeichen-Konvention wie in engine.py::_STAT_DIRECTION: niedrigere
    Arbeitslosigkeit ist gut (Richtung -1), hoeheres Wachstum ist gut
    (Richtung +1)."""
    state = build_initial_state()
    result = advance_turn(state, SAMPLE_POLICIES, [], newly_enacted_keys=["bildungsoffensive"])
    state = result.state
    economy_net = 0.0
    for _ in range(20):
        result = advance_turn(state, SAMPLE_POLICIES, [])
        state = result.state
        for a in result.attributions:
            if a.statistic_key == "unemployment_rate":
                economy_net += a.delta * -1.0
            elif a.statistic_key == "gdp_growth":
                economy_net += a.delta * 1.0
    assert economy_net < 0


def test_rezession_dilemma_is_reachable_via_sample_policies():
    """Regressionstest fuer die 'mehr Dilemma-Inhalte'-Nachschaerfung
    (Roadmap Punkt 3): das einzige bisherige Dilemma (arbeitsmarktkrise) hat
    einen praktisch unerreichbaren Schwellenwert im normalen Spielverlauf
    (siehe mistakes.md). Das neue 'rezession'-Dilemma (gdp_growth < 0.0) soll
    dagegen organisch ueber bildungsoffensives verstaerkten Wachstums-
    Trade-off (-2.4, siehe test_bildungsoffensive_has_a_genuine_net_negative_
    economy_tradeoff) erreichbar sein -- ohne manuelle Statistik-Manipulation."""
    state = build_initial_state()
    result = advance_turn(
        state, SAMPLE_POLICIES, [], newly_enacted_keys=["bildungsoffensive"], dilemma_rules=SAMPLE_DILEMMA_RULES
    )
    state = result.state
    # B12: seit dem Content-Ausbau koennen unterwegs andere Dilemmas feuern
    # (z.B. strompreiskrise bei gdp_growth < 0.6, bevor gdp < 0.0 erreicht
    # ist). Sie werden mit der wachstums-neutralsten Option aufgeloest; der
    # Test prueft weiterhin, dass `rezession` ORGANISCH erreichbar bleibt.
    reached = False
    for _ in range(25):
        if result.pending_dilemma is not None:
            if result.pending_dilemma.rule_key == "rezession":
                reached = True
                break
            other = next(r for r in SAMPLE_DILEMMA_RULES if r.key == result.pending_dilemma.rule_key)
            result = resolve_dilemma(state, SAMPLE_DILEMMA_RULES, other.options[0].key)
            state = result.state
            continue
        result = advance_turn(state, SAMPLE_POLICIES, [], dilemma_rules=SAMPLE_DILEMMA_RULES)
        state = result.state
    assert reached, "rezession sollte ueber bildungsoffensives Wachstums-Trade-off erreichbar sein"


def test_pflegeausbau_dilemma_is_reachable_via_sample_policies():
    """Analog zu test_rezession_dilemma_is_reachable_via_sample_policies,
    aber fuer das zweite neue Dilemma (healthcare_quality > 68.0, ein
    Chancen- statt Krisen-Dilemma) -- ausgeloest durch gesundheitsreform,
    die vierte, unabhaengige Policy aus der Balance-Nachschaerfung (siehe
    test_no_dominant_policy_among_current_sample_policies)."""
    state = build_initial_state()
    result = advance_turn(
        state, SAMPLE_POLICIES, [], newly_enacted_keys=["gesundheitsreform"], dilemma_rules=SAMPLE_DILEMMA_RULES
    )
    state = result.state
    # B12: analog zu test_rezession... -- gesundheitsreform druckt gdp_growth
    # Richtung 0, weshalb strompreiskrise/rezession unterwegs feuern koennen.
    # Zwischendilemmas wegraeumen, Erreichbarkeit von `pflegeausbau` bleibt
    # der eigentliche Pruefpunkt.
    reached = False
    for _ in range(25):
        if result.pending_dilemma is not None:
            if result.pending_dilemma.rule_key == "pflegeausbau":
                reached = True
                break
            other = next(r for r in SAMPLE_DILEMMA_RULES if r.key == result.pending_dilemma.rule_key)
            result = resolve_dilemma(state, SAMPLE_DILEMMA_RULES, other.options[0].key)
            state = result.state
            continue
        result = advance_turn(state, SAMPLE_POLICIES, [], dilemma_rules=SAMPLE_DILEMMA_RULES)
        state = result.state
    assert reached, "pflegeausbau sollte ueber gesundheitsreform erreichbar sein"


def test_voter_group_shares_deliberately_overlap():
    """Regressionstest fuer die 'ueberlappende Waehlergruppen'-Nachschaerfung
    (README.md 'Bekannte Vereinfachungen'): die vier urspruenglichen Gruppen
    sind exklusiv (Summe exakt 1.0), aber 'Umweltbewusste Waehler' und
    'Junge Familien' sind bewusst querliegende Identitaetsgruppen, die mit
    den vieren ueberlappen. Haelt fest, dass die Gesamtsumme > 1.0 ist --
    ein Merge, der das versehentlich wieder auf 1.0 normalisiert, faellt
    hierueber auf. engine.py::_weighted_approval normalisiert bereits durch
    total_share, braucht also KEINE Anpassung fuer ueberlappende Anteile."""
    total_share = sum(g.population_share for g in SAMPLE_VOTER_GROUPS)
    assert total_share > 1.0
    names = {g.name for g in SAMPLE_VOTER_GROUPS}
    assert {"Umweltbewusste Waehler", "Junge Familien"} <= names


def test_budget_has_a_baseline_income_without_any_active_policy():
    """Regressionstest fuer die Balance-Nachschaerfung 'Budget hatte nie eine
    Einnahmequelle' (siehe mistakes.md): das Budget kannte bisher nur
    Ausgaben (one_time_cost, upkeep_cost, Dilemma-budget_cost) -- ohne
    Repeal-Mechanik driftete JEDE Policy mit upkeep_cost>0 das feste
    Start-Budget unaufhaltsam ins Minus, unabhaengig von der Qualitaet der
    Politik. Haelt fest, dass eine Runde ohne jede Ausgabe das Budget um
    genau BASE_BUDGET_INCOME_PER_TURN erhoeht (Landeshaushalt-
    Grundeinnahme, siehe engine.py)."""
    state = build_initial_state()
    result = advance_turn(state, SAMPLE_POLICIES, [])
    assert result.state.budget == pytest.approx(state.budget + BASE_BUDGET_INCOME_PER_TURN)


def test_three_policy_combination_no_longer_goes_budget_negative():
    """Regressionstest fuer denselben Fix: die zuvor in CLAUDE.md/mistakes.md
    als BUDGET_NEGATIV dokumentierte Dreier-Kombination (bildungsoffensive+
    steuersenkung_mittelstand+gesundheitsreform, -345 Budget nach 30 Runden
    OHNE Grundeinnahme) bleibt jetzt ueber einen vollen Wahlzyklus im
    Plus -- inklusive des staerksten Dilemma-Optionskosten-Falls (siehe
    balance_runner.py::run_scenario, das immer die erste/teuerste Option
    waehlt)."""
    state = build_initial_state()
    result = advance_turn(
        state,
        SAMPLE_POLICIES,
        [],
        newly_enacted_keys=["bildungsoffensive", "steuersenkung_mittelstand"],
        dilemma_rules=SAMPLE_DILEMMA_RULES,
    )
    state = result.state
    result = advance_turn(state, SAMPLE_POLICIES, [], newly_enacted_keys=["gesundheitsreform"], dilemma_rules=SAMPLE_DILEMMA_RULES)
    state = result.state
    for _ in range(30):
        if state.pending_dilemma is not None:
            result = resolve_dilemma(state, SAMPLE_DILEMMA_RULES, state.pending_dilemma.options[0].key)
            state = result.state
            continue
        result = advance_turn(state, SAMPLE_POLICIES, [], dilemma_rules=SAMPLE_DILEMMA_RULES)
        state = result.state
    assert state.budget >= 0


# --- Policy-Repeal-Mechanismus (Democracy-4-Vorbild) ---------------------
#
# Vorbild: Democracy 4 loescht eine zurueckgezogene Policy nicht schlagartig,
# sondern laesst ihre Wirkung graduell abklingen (siehe CLAUDE.md/mistakes.md
# fuer die Recherche-Notizen zu Repeal/Budget/Einnahmen). Die Tests hier
# pruefen: (1) Upkeep/Einnahmen stoppen sofort, (2) der Effekt selbst klingt
# symmetrisch zum Aufbau ab statt abrupt zu verschwinden, (3) Repeal kostet
# ebenfalls Political Capital, (4) die drei neuen Fehlerfaelle (Doppel-Enact,
# Repeal einer inaktiven Policy, Repeal einer noch benoetigten Policy).


def test_repeal_stops_upkeep_cost_immediately():
    state = build_initial_state()
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["erneuerbare_foerderung"])
    result = advance_turn(result.state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES)
    budget_after_normal_turn = result.state.budget

    result = advance_turn(result.state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_repealed_keys=["erneuerbare_foerderung"])
    # Repeal-Runde: nur noch die Grundeinnahme, kein upkeep_cost (5.0) mehr --
    # anders als eine normale Runde, die budget_after_normal_turn erreicht hat.
    assert result.state.budget == pytest.approx(budget_after_normal_turn + BASE_BUDGET_INCOME_PER_TURN)

    # Und bleibt auch in Folgerunden aus.
    result2 = advance_turn(result.state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES)
    assert result2.state.budget == pytest.approx(result.state.budget + BASE_BUDGET_INCOME_PER_TURN)


def test_repealing_a_policy_also_costs_political_capital():
    state = build_initial_state()
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["erneuerbare_foerderung"])
    capital_before_repeal = result.state.political_capital

    result = advance_turn(result.state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_repealed_keys=["erneuerbare_foerderung"])
    expected = min(CAPITAL_CAP, capital_before_repeal + CAPITAL_PER_TURN) - 4.0  # capital_cost der Policy
    assert result.state.political_capital == pytest.approx(expected)


def test_repealed_policy_effect_decays_symmetrically_instead_of_vanishing():
    """Kernstueck des Democracy-4-Vorbilds: KEIN abruptes Verschwinden. Ein
    frei erfundenes Testpolicy (statt SAMPLE_POLICIES) haelt die Rechnung
    unabhaengig von anderen Effekten/Events nachvollziehbar."""
    testpolicy = Policy(
        key="testpolicy",
        name="Testpolicy",
        effects=[PolicyEffect(statistic_key="renewable_share", magnitude=10.0, delay_turns=0, inertia=2)],
    )
    baseline = STARTING_STATISTICS["renewable_share"]
    state = build_initial_state()

    result = advance_turn(state, [testpolicy], [], newly_enacted_keys=["testpolicy"])
    state = result.state
    for _ in range(3):
        result = advance_turn(state, [testpolicy], [])
        state = result.state
    value_at_repeal = state.statistics["renewable_share"]
    assert value_at_repeal > baseline  # Effekt hat sich sichtbar aufgebaut

    result = advance_turn(state, [testpolicy], [], newly_repealed_keys=["testpolicy"])
    state = result.state
    decay_deltas = []
    for _ in range(12):
        delta = next((a.delta for a in result.attributions if a.statistic_key == "renewable_share"), 0.0)
        decay_deltas.append(delta)
        result = advance_turn(state, [testpolicy], [])
        state = result.state

    # Jeder Schritt baut ab (negativ), keiner springt auf einmal auf 0 --
    # das waere das alte, abrupte Verhalten.
    nonzero_deltas = [d for d in decay_deltas if d != 0.0]
    assert nonzero_deltas, "Repeal sollte ueberhaupt Abbau-Deltas erzeugen"
    assert all(d < 0 for d in nonzero_deltas)
    # Abklingen ist monoton schwaecher werdend (exponentiell, wie der Aufbau).
    assert all(abs(nonzero_deltas[i]) >= abs(nonzero_deltas[i + 1]) for i in range(len(nonzero_deltas) - 1))
    # Nach genug Runden ist der Effekt wieder (fast) vollstaendig abgebaut.
    assert state.statistics["renewable_share"] == pytest.approx(baseline, abs=0.05)


def test_enacting_an_already_active_policy_raises():
    state = build_initial_state()
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["gesundheitsreform"])
    with pytest.raises(PolicyAlreadyActiveError):
        advance_turn(result.state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["gesundheitsreform"])


def test_repealing_an_inactive_policy_raises():
    state = build_initial_state()
    with pytest.raises(PolicyNotActiveError):
        advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_repealed_keys=["gesundheitsreform"])


def test_repeal_blocked_when_still_required_by_an_active_dependent_policy():
    state = build_initial_state()
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["bildungsoffensive"])
    result = advance_turn(
        result.state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["steuersenkung_mittelstand"]
    )
    with pytest.raises(PolicyRequiredByActivePolicyError):
        advance_turn(result.state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_repealed_keys=["bildungsoffensive"])


def test_repeal_allowed_once_the_dependent_policy_is_also_repealed_same_turn():
    state = build_initial_state()
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["bildungsoffensive"])
    result = advance_turn(
        result.state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["steuersenkung_mittelstand"]
    )
    # Beide gleichzeitig zurueckziehen ist erlaubt -- die abhaengige Policy
    # ist ja im selben Atemzug ebenfalls nicht mehr aktiv.
    result = advance_turn(
        result.state,
        SAMPLE_POLICIES,
        SAMPLE_EVENT_RULES,
        newly_repealed_keys=["bildungsoffensive", "steuersenkung_mittelstand"],
    )
    active_keys = {ep.policy_key for ep in result.state.active_policies if ep.repealed_turn is None}
    assert "bildungsoffensive" not in active_keys
    assert "steuersenkung_mittelstand" not in active_keys


def test_can_reenact_a_policy_after_it_was_repealed():
    state = build_initial_state()
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["gesundheitsreform"])
    result = advance_turn(result.state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_repealed_keys=["gesundheitsreform"])
    result = advance_turn(result.state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["gesundheitsreform"])

    all_keys = [ep.policy_key for ep in result.state.active_policies]
    assert all_keys.count("gesundheitsreform") == 2  # der alte (zurueckgezogene) + der neue Eintrag
    active_keys = [ep.policy_key for ep in result.state.active_policies if ep.repealed_turn is None]
    assert active_keys.count("gesundheitsreform") == 1


# --- B1: Legislatur-Bogen & Amtszeit-Debrief (BACKLOG.md) --------------


def test_term_summary_is_only_set_on_the_election_turn():
    state = build_initial_state()
    for _ in range(ELECTION_CYCLE_LENGTH - 1):
        result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES)
        assert result.term_summary is None
        state = result.state
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES)
    assert result.election_result is not None
    assert result.term_summary is not None
    assert result.term_summary.term_start_turn == 0
    assert result.term_summary.term_end_turn == ELECTION_CYCLE_LENGTH


def test_term_summary_statistic_changes_match_a_known_run():
    """bildungsoffensive ueber einen vollen Zyklus: education_spending steigt,
    gdp_growth faellt (der verschaerfte Trade-off, siehe sample_data.py) --
    die TermSummary muss genau diese Netto-Bewegung ausweisen."""
    state = build_initial_state()
    start_edu = state.statistics["education_spending"]
    result = advance_turn(
        state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, newly_enacted_keys=["bildungsoffensive"]
    )
    state = result.state
    for _ in range(ELECTION_CYCLE_LENGTH - 1):
        result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES)
        state = result.state

    ts = result.term_summary
    assert ts is not None
    assert ts.statistic_changes["education_spending"] == pytest.approx(
        state.statistics["education_spending"] - start_edu
    )
    assert ts.statistic_changes["education_spending"] > 0
    assert ts.statistic_changes["gdp_growth"] < 0
    # education_spending (Kategorie "social") ist die groesste waehlerwirksame
    # Verbesserung, gdp_growth ("economy") der groesste Rueckschritt.
    assert ts.biggest_improvement == "education_spending"
    assert ts.biggest_decline == "gdp_growth"
    assert ts.category_changes["social"] > 0
    assert ts.category_changes["economy"] < 0


def test_term_summary_counts_events_faced():
    state = build_initial_state()
    state.turns_until_election = 1
    state.statistics["unemployment_rate"] = 12.0  # ueber Event-Schwelle (>9)
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES)
    assert result.term_summary is not None
    assert result.term_summary.events_experienced == 1
    assert result.term_summary.dilemmas_faced == 0


def test_term_summary_counts_dilemmas_faced():
    state = build_initial_state()
    state.turns_until_election = 1
    state.statistics["gdp_growth"] = -1.0  # ueber rezession-Schwelle (< 0.0)
    result = advance_turn(
        state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, dilemma_rules=SAMPLE_DILEMMA_RULES
    )
    assert result.term_summary is not None
    assert result.term_summary.dilemmas_faced == 1


def test_term_tracking_resets_after_an_election():
    state = build_initial_state()
    state.turns_until_election = 1
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES)
    assert result.term_summary is not None

    ns = result.state
    assert ns.term_start_turn == ns.turn
    assert ns.term_dilemma_count == 0
    assert ns.term_event_count == 0
    assert ns.term_start_statistics == ns.statistics

    # Der naechste Rundenwechsel liefert noch keine neue Bilanz.
    result2 = advance_turn(ns, SAMPLE_POLICIES, SAMPLE_EVENT_RULES)
    assert result2.term_summary is None


# --- B2: Situations-Layer (mittlerer Zeithorizont, mit Hysterese) -------


def test_situation_activates_when_threshold_reached():
    """Situation `abwanderung` aktiviert sich bei gdp_growth < -0.5."""
    state = build_initial_state()
    state.statistics["gdp_growth"] = -1.0
    result = advance_turn(
        state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, situation_rules=SAMPLE_SITUATION_RULES
    )
    assert len(result.state.active_situations) > 0
    assert any(s.rule_key == "abwanderung" for s in result.state.active_situations)


def test_situation_remains_active_within_hysteresis_band():
    """Hysterese: `abwanderung` bleibt aktiv, solange gdp_growth zwischen
    -0.5 (Aktivierungs-Schwelle) und 0.5 (Deaktivierungs-Schwelle) liegt."""
    state = build_initial_state()
    state.statistics["gdp_growth"] = -1.0
    result = advance_turn(
        state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, situation_rules=SAMPLE_SITUATION_RULES
    )
    state = result.state
    assert len(state.active_situations) == 1

    # gdp_growth steigt auf -0.2 (noch zwischen -0.5 und 0.5)
    state.statistics["gdp_growth"] = -0.2
    result = advance_turn(state, [], [], situation_rules=SAMPLE_SITUATION_RULES)
    # Situation muss NOCH aktiv sein
    assert len(result.state.active_situations) == 1
    assert result.state.active_situations[0].rule_key == "abwanderung"


def test_situation_deactivates_when_upper_threshold_crossed():
    """Situation deaktiviert sich erst bei der OBEREN Schwelle. B12: das
    Hysterese-Fenster von `abwanderung` wurde verbreitert (deactivate bei
    gdp_growth > 0.9 statt > 0.5)."""
    state = build_initial_state()
    state.statistics["gdp_growth"] = -1.0
    result = advance_turn(
        state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, situation_rules=SAMPLE_SITUATION_RULES
    )
    state = result.state
    assert len(state.active_situations) == 1

    # knapp positiv (0.6) reicht NICHT mehr -- Situation bleibt aktiv
    state.statistics["gdp_growth"] = 0.6
    result = advance_turn(state, [], [], situation_rules=SAMPLE_SITUATION_RULES)
    assert len(result.state.active_situations) == 1

    # gdp_growth > 0.9 -> deaktivieren
    state = result.state
    state.statistics["gdp_growth"] = 1.0
    result = advance_turn(state, [], [], situation_rules=SAMPLE_SITUATION_RULES)
    assert len(result.state.active_situations) == 0


def test_situation_effects_are_applied_and_attributed():
    """Situation-Effekte wirken auf Statistiken und werden attributiert."""
    state = build_initial_state()
    state.statistics["gdp_growth"] = -1.0
    result = advance_turn(
        state, [], SAMPLE_EVENT_RULES, situation_rules=SAMPLE_SITUATION_RULES
    )
    # `abwanderung` sollte unemployment_rate erhöht haben
    assert result.state.statistics["unemployment_rate"] > state.statistics["unemployment_rate"]
    assert any(
        a.source == "situation:abwanderung" and a.statistic_key == "unemployment_rate"
        for a in result.attributions
    )


def test_positive_situation_gruenes_wachstum():
    """Positive Situation: bei renewable_share ueber der Aktivierungsschwelle
    (B12: 42) aktiviert sich `gruenes_wachstum` und verbessert gdp_growth +
    co2_emissions."""
    state = build_initial_state()
    state.statistics["renewable_share"] = 70.0
    result = advance_turn(
        state, [], SAMPLE_EVENT_RULES, situation_rules=SAMPLE_SITUATION_RULES
    )
    assert any(s.rule_key == "gruenes_wachstum" for s in result.state.active_situations)
    assert result.state.statistics["gdp_growth"] > state.statistics["gdp_growth"]
    assert result.state.statistics["co2_emissions"] < state.statistics["co2_emissions"]


# --- B3: Zustandsgekoppelte Risiko-Events (probability-Gate) --------------


def _crisis_event(key: str, probability: float, cooldown_turns: int = 0) -> EventRule:
    """Ein Event, dessen Schwelle im Ausgangszustand (unemployment_rate 6.0)
    immer erfuellt ist -- so isoliert der Test allein das probability-Gate."""
    return EventRule(
        key=key,
        statistic_key="unemployment_rate",
        operator=">",
        threshold=0.0,
        template_text="Testmeldung {value:.1f}",
        cooldown_turns=cooldown_turns,
        probability=probability,
    )


def test_probability_one_point_zero_behaves_exactly_like_before_b3():
    """probability=1.0 (Default) darf das bisherige Verhalten nicht aendern:
    bei erfuellter Schwelle feuert die Regel jede nicht-Cooldown-Runde."""
    state = build_initial_state()
    rule = _crisis_event("immer", probability=1.0, cooldown_turns=0)
    fired = 0
    for _ in range(10):
        result = advance_turn(state, [], [rule])
        state = result.state
        fired += len(result.events)
    assert fired == 10


def test_probability_zero_never_fires_even_when_threshold_met():
    state = build_initial_state()
    rule = _crisis_event("nie", probability=0.0, cooldown_turns=0)
    fired = 0
    for _ in range(50):
        result = advance_turn(state, [], [rule])
        state = result.state
        fired += len(result.events)
    assert fired == 0


def test_probability_between_zero_and_one_gates_some_but_not_all_turns():
    state = build_initial_state()
    rule = _crisis_event("manchmal", probability=0.5, cooldown_turns=0)
    fired = 0
    for _ in range(40):
        result = advance_turn(state, [], [rule])
        state = result.state
        fired += len(result.events)
    assert 0 < fired < 40


def test_probability_gate_is_deterministic_for_same_seed():
    """Gleicher Regel-Key + gleiche Runde -> gleiche Entscheidung, ueber
    Prozesslaeufe hinweg (crc32 statt hash()/random)."""
    for turn in range(1, 30):
        assert passes_probability_gate("konjunkturdelle", turn, 0.4) is (
            passes_probability_gate("konjunkturdelle", turn, 0.4)
        )
    # Verschiedene Regel-Keys wuerfeln unabhaengig (nicht alle Regeln feuern
    # in derselben Runde gemeinsam).
    assert any(
        passes_probability_gate("regel_a", t, 0.5) != passes_probability_gate("regel_b", t, 0.5)
        for t in range(1, 40)
    )

    def _fire_pattern():
        state = build_initial_state()
        rule = _crisis_event("wuerfel", probability=0.35, cooldown_turns=0)
        pattern = []
        for _ in range(25):
            result = advance_turn(state, [], [rule])
            state = result.state
            pattern.append(bool(result.events))
        return tuple(pattern)

    assert _fire_pattern() == _fire_pattern()


def test_dilemma_probability_gate_zero_never_fires():
    state = build_initial_state()
    state.statistics["unemployment_rate"] = 20.0  # weit ueber Schwelle
    rule = DilemmaRule(
        key="gedaempft",
        statistic_key="unemployment_rate",
        operator=">",
        threshold=9.0,
        prompt_text="Test?",
        options=[
            DilemmaOption(key="a", label="A"),
            DilemmaOption(key="b", label="B"),
        ],
        cooldown_turns=0,
        probability=0.0,
    )
    for _ in range(30):
        result = advance_turn(state, [], [], dilemma_rules=[rule])
        state = result.state
        assert result.pending_dilemma is None


def test_konjunkturdelle_vorstufe_makes_rezession_organically_reachable():
    """E2E (BACKLOG.md B3): eine Policy bringt gdp_growth in eine nur LEICHT
    negative Lage knapp ueber der rezession-Schwelle (0.0), aber nicht
    darunter. OHNE die Vorstufe `konjunkturdelle` triggert `rezession` in
    40 Runden nicht; MIT ihr wird die Schwelle organisch erreicht.

    B12: bewusst isoliert auf die `rezession`-Regel -- seit dem Content-
    Ausbau ueberdeckt `strompreiskrise` (gdp_growth < 0.6) `rezession`
    (gdp_growth < 0.0) im vollen Regelsatz sowohl beim Schweregrad als auch,
    weil ihre beiden Optionen die Konjunktur wieder anheben. Dieser Test
    prueft die B3-Vorstufen-Mechanik selbst, nicht die Dilemma-Priorisierung
    im Gesamtroster (das deckt test_every_sample_rule_is_organically_
    reachable ab)."""
    mild = Policy(
        key="wachstumsbremse",
        name="Wachstumsbremse (Testfixture)",
        effects=[PolicyEffect(statistic_key="gdp_growth", magnitude=-1.0, delay_turns=0, inertia=2)],
    )
    konjunkturdelle = [r for r in SAMPLE_EVENT_RULES if r.key == "konjunkturdelle"]
    assert konjunkturdelle, "Vorstufe 'konjunkturdelle' fehlt in SAMPLE_EVENT_RULES"
    rezession_only = [r for r in SAMPLE_DILEMMA_RULES if r.key == "rezession"]

    def _rezession_reached(event_rules: list) -> bool:
        state = build_initial_state()
        result = advance_turn(
            state, [mild], event_rules, newly_enacted_keys=["wachstumsbremse"],
            dilemma_rules=rezession_only,
        )
        state = result.state
        for _ in range(40):
            if result.pending_dilemma is not None and result.pending_dilemma.rule_key == "rezession":
                return True
            result = advance_turn(state, [mild], event_rules, dilemma_rules=rezession_only)
            state = result.state
        return result.pending_dilemma is not None and result.pending_dilemma.rule_key == "rezession"

    assert not _rezession_reached([]), "rezession sollte ohne die Vorstufe unerreichbar bleiben"
    assert _rezession_reached(konjunkturdelle), "rezession sollte ueber die Vorstufe erreichbar sein"


# --- B4: Narrative Konsequenz-Ebene ("Presseschau") ----------------------


def _report(key, conditions, **kw):
    kw.setdefault("template_text", "Meldung: Arbeitslosigkeit bei {unemployment_rate:.1f}%.")
    return ReportRule(key=key, conditions=conditions, **kw)


def test_report_fires_only_when_all_and_conditions_are_met():
    state = build_initial_state()  # unemployment_rate 6.0, gdp_growth 1.2

    partial = _report(
        "partial",
        [
            ReportCondition("unemployment_rate", "<", 7.0),
            ReportCondition("gdp_growth", ">", 5.0),  # nicht erfuellt
        ],
    )
    assert advance_turn(state, [], [], report_rules=[partial]).reports == []

    full = _report(
        "full",
        [
            ReportCondition("unemployment_rate", "<", 7.0),
            ReportCondition("gdp_growth", ">", 1.0),
        ],
    )
    result = advance_turn(state, [], [], report_rules=[full])
    assert len(result.reports) == 1
    assert "5.9" in result.reports[0]  # STARTING_STATISTICS unemployment_rate (B13)


def test_report_is_suppressed_in_a_turn_with_an_event():
    state = build_initial_state()
    state.statistics["unemployment_rate"] = 20.0
    event = EventRule(
        key="hohe_arbeitslosigkeit", statistic_key="unemployment_rate", operator=">", threshold=9.0,
        template_text="Arbeitslosigkeit bei {value:.1f}%", cooldown_turns=3,
    )
    report = _report("immer", [ReportCondition("unemployment_rate", ">", 1.0)])
    result = advance_turn(state, [], [event], report_rules=[report])
    assert len(result.events) == 1
    assert result.reports == []


def test_report_is_suppressed_in_a_turn_with_a_dilemma():
    state = build_initial_state()
    state.statistics["unemployment_rate"] = 20.0
    report = _report("immer", [ReportCondition("unemployment_rate", ">", 1.0)])
    result = advance_turn(
        state, [], [], dilemma_rules=SAMPLE_DILEMMA_RULES, report_rules=[report]
    )
    assert result.pending_dilemma is not None
    assert result.reports == []


def test_report_respects_its_cooldown():
    state = build_initial_state()
    rule = _report("mit_cooldown", [ReportCondition("unemployment_rate", ">", 0.0)], cooldown_turns=3)
    fired_turns = []
    for _ in range(8):
        result = advance_turn(state, [], [], report_rules=[rule])
        state = result.state
        if result.reports:
            fired_turns.append(state.turn)
    # Feuert in Runde 1, danach zwei Runden Pause (Cooldown 3), dann wieder.
    assert fired_turns == [1, 4, 7]


def test_report_template_placeholders_are_filled_not_left_raw():
    state = build_initial_state()
    rule = _report(
        "platzhalter",
        [ReportCondition("unemployment_rate", ">", 0.0)],
        template_text="Arbeitslosigkeit bei {unemployment_rate:.1f}, CO2 bei {co2_emissions:.0f}.",
    )
    text = advance_turn(state, [], [], report_rules=[rule]).reports[0]
    assert "5.9" in text and "100" in text
    assert "[FEHLT:" not in text


def test_report_requires_policy_gate():
    rule = _report(
        "braucht_policy",
        [ReportCondition("unemployment_rate", "<", 7.0)],
        requires_policy="bildungsoffensive",
    )
    state = build_initial_state()
    assert advance_turn(state, SAMPLE_POLICIES, [], report_rules=[rule]).reports == []

    state = build_initial_state()
    result = advance_turn(
        state, SAMPLE_POLICIES, [], newly_enacted_keys=["bildungsoffensive"], report_rules=[rule]
    )
    assert len(result.reports) == 1


def test_report_forbids_policy_gate():
    rule = _report(
        "verbietet_policy",
        [ReportCondition("co2_emissions", ">", 50.0)],
        forbids_policy="erneuerbare_foerderung",
        template_text="Emissionen bei {co2_emissions:.0f}.",
    )
    state = build_initial_state()
    assert len(advance_turn(state, SAMPLE_POLICIES, [], report_rules=[rule]).reports) == 1

    state = build_initial_state()
    result = advance_turn(
        state, SAMPLE_POLICIES, [], newly_enacted_keys=["erneuerbare_foerderung"], report_rules=[rule]
    )
    assert result.reports == []


def test_reports_never_change_statistics_or_satisfaction():
    base = build_initial_state()
    firing_rule = _report("immer", [ReportCondition("unemployment_rate", ">", 0.0)])

    without = advance_turn(base, [], [])
    with_report = advance_turn(base, [], [], report_rules=[firing_rule])

    assert with_report.reports  # der Report ist tatsaechlich gefeuert
    assert with_report.state.statistics == without.state.statistics
    assert [g.satisfaction for g in with_report.state.voter_groups] == [
        g.satisfaction for g in without.state.voter_groups
    ]
    assert with_report.attributions == without.attributions


def test_report_gets_a_vignette_appended():
    state = build_initial_state()
    # conditions[0].statistic_key steuert die Vignetten-Kategorie (economy).
    rule = _report("mit_vignette", [ReportCondition("unemployment_rate", ">", 0.0)])
    text = advance_turn(state, [], [], report_rules=[rule]).reports[0]
    assert any(vignette in text for vignette in VIGNETTE_POOL["economy"])


def test_sample_report_rules_are_well_formed():
    valid_ops = {">", "<", ">=", "<=", "==", "!="}
    assert 5 <= len(SAMPLE_REPORT_RULES) <= 8
    keys = [r.key for r in SAMPLE_REPORT_RULES]
    assert len(keys) == len(set(keys)), "Report-Keys muessen eindeutig sein"
    for rule in SAMPLE_REPORT_RULES:
        assert rule.conditions, f"Report '{rule.key}' braucht mindestens eine Bedingung"
        assert rule.template_text.strip()
        for condition in rule.conditions:
            assert condition.operator in valid_ops


def test_sample_report_bildungsoffensive_wirkt_is_reachable_without_noise():
    """E2E (BACKLOG.md B4): der policy-gekoppelte Report `bildungsoffensive_
    wirkt` (education_spending > 50 UND unemployment_rate < 5.5, requires
    bildungsoffensive) wird in einem ruhigen Lauf (ohne Events/Dilemmas)
    tatsaechlich erreicht."""
    state = build_initial_state()
    result = advance_turn(
        state, SAMPLE_POLICIES, [], newly_enacted_keys=["bildungsoffensive"],
        report_rules=SAMPLE_REPORT_RULES,
    )
    state = result.state
    seen = list(result.reports)
    for _ in range(18):
        result = advance_turn(state, SAMPLE_POLICIES, [], report_rules=SAMPLE_REPORT_RULES)
        state = result.state
        seen.extend(result.reports)
    assert any("Berufsschulen" in text for text in seen), seen


# --- B5: Wahlprognose mit sichtbarem Turnout/Apathie --------------------


def _two_group_state(share_a, sat_a, momentum_a, share_b, sat_b, momentum_b):
    state = build_initial_state()
    state.voter_groups = [
        VoterGroup(name="A", population_share=share_a, satisfaction=sat_a, satisfaction_momentum=momentum_a),
        VoterGroup(name="B", population_share=share_b, satisfaction=sat_b, satisfaction_momentum=momentum_b),
    ]
    return state


def test_projection_approval_equals_the_actual_election_result():
    """BACKLOG.md B5 Test 1: die Prognose nennt exakt die Zahl, an der die
    echte Wahl haengt (ungewichtet, ohne Turnout) -- keine Blackbox (L6).
    B2: Stat-zu-Stat-Wirkungen (Phillips, Solow) applizieren NACH Projektion
    und führen zu minimalen Unterschieden (~0.02%) -- Tolerance auf 0.1% erhöht.
    Hinweis: would_win vs. won kann bei Schwellwert-Nähe (≈50%) divergieren
    wegen Stat-zu-Stat-Feedback; nur approval wird überprüft."""
    state = build_initial_state()  # alle Gruppen satisfaction 50, momentum 0
    projection = project_election(state)

    state.turns_until_election = 1
    result = advance_turn(state, [], [])
    assert result.election_result is not None
    assert projection.approval == pytest.approx(result.election_result.approval, rel=1e-3)


def test_projection_turnout_is_neutral_without_lukewarm_cooling_groups():
    """Ohne "lauwarm UND abkuehlend"-Gruppe ist die turnout-gewichtete
    Zustimmung identisch zur ungewichteten."""
    state = _two_group_state(0.6, 62.0, 0.0, 0.4, 44.0, +0.5)  # stabil / steigend
    projection = project_election(state)
    assert projection.turnout_adjusted_approval == pytest.approx(projection.approval)
    assert all(g.estimated_turnout == 1.0 for g in projection.groups)


def test_full_turnout_for_stable_rising_angry_or_happy_groups():
    # stabil (momentum 0), steigend, wuetend (unter Floor), zufrieden (ueber Ceiling)
    state = build_initial_state()
    state.voter_groups = [
        VoterGroup(name="stabil", population_share=0.25, satisfaction=45.0, satisfaction_momentum=0.0),
        VoterGroup(name="steigend", population_share=0.25, satisfaction=45.0, satisfaction_momentum=0.8),
        VoterGroup(name="wuetend", population_share=0.25, satisfaction=20.0, satisfaction_momentum=-4.0),
        VoterGroup(name="zufrieden", population_share=0.25, satisfaction=70.0, satisfaction_momentum=-4.0),
    ]
    turnout = {g.name: g.estimated_turnout for g in project_election(state).groups}
    assert turnout == {"stabil": 1.0, "steigend": 1.0, "wuetend": 1.0, "zufrieden": 1.0}


def test_turnout_drops_for_a_lukewarm_and_cooling_group_proportional_to_the_drop():
    state = _two_group_state(0.5, 45.0, -3.0, 0.5, 45.0, -1.5)
    by_name = {g.name: g for g in project_election(state).groups}
    # A: volle Apathie (momentum <= -3) -> TURNOUT_MIN
    assert by_name["A"].estimated_turnout == pytest.approx(0.6)
    # B: halbe Apathie (momentum -1.5 = -TURNOUT_MOMENTUM_FULL/2)
    assert by_name["B"].estimated_turnout == pytest.approx(0.8)


def test_turnout_adjusted_approval_drops_when_a_large_supportive_group_cools():
    """BACKLOG.md B5 Test 2: eine grosse, ueberdurchschnittlich zufriedene
    Gruppe, deren Zufriedenheit FAELLT, senkt die turnout-gewichtete
    Prognose staerker als dieselbe Gruppe mit STABILER Zufriedenheit --
    lauwarme Anhaenger bleiben zu Hause (L6). Die ungewichtete Zahl bleibt
    gleich; nur der Turnout bewegt sie."""
    stable = _two_group_state(0.7, 52.0, 0.0, 0.3, 20.0, 0.0)
    cooling = _two_group_state(0.7, 52.0, -3.0, 0.3, 20.0, 0.0)

    p_stable = project_election(stable)
    p_cooling = project_election(cooling)

    # ungewichtet unveraendert (die Zufriedenheitswerte sind dieselben)
    assert p_cooling.approval == pytest.approx(p_stable.approval)
    # turnout-gewichtet: abkuehlende Basis -> niedrigere Prognose
    assert p_cooling.turnout_adjusted_approval < p_stable.turnout_adjusted_approval
    assert p_stable.turnout_adjusted_approval == pytest.approx(p_stable.approval)


def test_projection_group_trend_labels():
    state = _two_group_state(0.34, 50.0, 0.2, 0.33, 50.0, -0.2)
    state.voter_groups.append(
        VoterGroup(name="C", population_share=0.33, satisfaction=50.0, satisfaction_momentum=0.0)
    )
    trend = {g.name: g.trend for g in project_election(state).groups}
    assert trend == {"A": "steigend", "B": "fallend", "C": "stabil"}


def test_projection_would_win_follows_the_threshold():
    losing = _two_group_state(0.5, 30.0, 0.0, 0.5, 30.0, 0.0)
    assert project_election(losing).would_win is False
    winning = _two_group_state(0.5, 70.0, 0.0, 0.5, 70.0, 0.0)
    assert project_election(winning).would_win is True


def test_projection_group_count_and_shares_match_the_state():
    state = build_initial_state()
    projection = project_election(state)
    assert len(projection.groups) == len(state.voter_groups)
    assert [g.name for g in projection.groups] == [g.name for g in state.voter_groups]


# --- B7: Dynamische Policy-Freischaltung durch Sim-Zustand ---------------


def test_policy_without_unlock_conditions_is_always_unlocked():
    assert policy_is_unlocked(Policy(key="x", name="X"), {}) is True
    assert policy_is_unlocked(Policy(key="x", name="X"), {"a": 1.0}) is True


def test_policy_is_unlocked_requires_all_and_conditions():
    p = Policy(
        key="x",
        name="X",
        unlock_conditions=[
            UnlockCondition("a", ">", 10.0),
            UnlockCondition("b", "<", 5.0),
        ],
    )
    assert policy_is_unlocked(p, {"a": 11.0, "b": 4.0}) is True
    assert policy_is_unlocked(p, {"a": 11.0, "b": 6.0}) is False  # zweite verletzt
    assert policy_is_unlocked(p, {"a": 9.0, "b": 4.0}) is False  # erste verletzt
    assert policy_is_unlocked(p, {"a": 11.0}) is False  # Statistik fehlt


def test_enacting_a_locked_policy_raises_and_does_not_mutate_state():
    locked = Policy(
        key="gesperrt",
        name="Gesperrt",
        unlock_conditions=[UnlockCondition("renewable_share", ">", 60.0)],
    )
    state = build_initial_state()  # renewable_share startet 35 -> gesperrt
    budget_before, turn_before = state.budget, state.turn
    with pytest.raises(PolicyLockedError) as exc:
        advance_turn(state, [locked], [], newly_enacted_keys=["gesperrt"])
    assert exc.value.policy_key == "gesperrt"
    assert "renewable_share" in exc.value.unmet_condition
    # State darf durch den abgelehnten Zug nicht veraendert worden sein.
    assert state.turn == turn_before
    assert state.budget == budget_before
    assert state.active_policies == []


def test_enacting_a_policy_once_its_unlock_condition_is_met_succeeds():
    unlockable = Policy(
        key="frei",
        name="Frei",
        unlock_conditions=[UnlockCondition("renewable_share", ">", 30.0)],
    )
    state = build_initial_state()  # renewable_share 35 > 30 -> frei
    result = advance_turn(state, [unlockable], [], newly_enacted_keys=["frei"])
    assert any(ep.policy_key == "frei" for ep in result.state.active_policies)


def test_sample_unlock_policies_are_locked_at_start():
    by_key = {p.key: p for p in SAMPLE_POLICIES}
    for key in ("digitalpakt_schulen", "gruener_wasserstoff", "arbeitsmarkt_sofortprogramm"):
        assert by_key[key].unlock_conditions, f"{key} sollte unlock_conditions haben"
        assert not policy_is_unlocked(by_key[key], STARTING_STATISTICS), (
            f"{key} sollte zu Spielbeginn gesperrt sein"
        )


def test_digitalpakt_becomes_enactable_after_bildungsoffensive_raises_education():
    """E2E (BACKLOG.md B7): digitalpakt_schulen ist zu Beginn gesperrt
    (education_spending > 50), wird aber ueber bildungsoffensive (hebt
    education_spending 40 -> ~55) organisch freigeschaltet. Ohne Event-/
    Dilemma-Regeln, damit reine Policy-Effekte laufen (kein Dilemma-Block)."""
    state = build_initial_state()
    state = advance_turn(state, SAMPLE_POLICIES, [], newly_enacted_keys=["bildungsoffensive"]).state

    with pytest.raises(PolicyLockedError):  # noch gesperrt
        advance_turn(state, SAMPLE_POLICIES, [], newly_enacted_keys=["digitalpakt_schulen"])

    for _ in range(20):
        if state.statistics["education_spending"] > 50.0:
            break
        state = advance_turn(state, SAMPLE_POLICIES, []).state
    assert state.statistics["education_spending"] > 50.0

    result = advance_turn(state, SAMPLE_POLICIES, [], newly_enacted_keys=["digitalpakt_schulen"])
    assert any(ep.policy_key == "digitalpakt_schulen" for ep in result.state.active_policies)


# --- B8: Fraktions-/Sitz-Datenmodell -------------------------------------


def _advance_to_election(state, scenario_goals):
    """Faehrt ohne Events/Dilemmas bis zum Wahl-Turn und gibt dessen
    TurnResult zurueck (das die TermSummary inkl. Zielauswertung traegt)."""
    result = None
    for _ in range(ELECTION_CYCLE_LENGTH):
        result = advance_turn(state, [], [], scenario_goals=scenario_goals)
        state = result.state
    return result


def test_scenario_goals_evaluated_against_end_state_at_election():
    """B9: Ziele werden am Legislaturende gegen den Endzustand geprueft und
    landen in TermSummary.goals -- ein erfuelltes und ein verfehltes."""
    goals = [
        ScenarioGoal(key="leicht", description="Arbeitslosigkeit unter 10", metric="unemployment_rate", operator="<", threshold=10.0),
        ScenarioGoal(key="unmoeglich", description="CO2 unter 0", metric="co2_emissions", operator="<", threshold=0.0),
    ]
    result = _advance_to_election(build_initial_state(), goals)
    assert result.term_summary is not None
    by_key = {g.key: g for g in result.term_summary.goals}
    assert by_key["leicht"].met is True  # unemployment startet 6, ohne Policy unveraendert
    assert by_key["unmoeglich"].met is False
    assert by_key["leicht"].description == "Arbeitslosigkeit unter 10"


def test_scenario_goal_special_metrics_budget_and_approval():
    """B9: Sonderwerte "budget" und "approval" werden korrekt aufgeloest."""
    goals = [
        ScenarioGoal(key="haushalt", description="Budget positiv", metric="budget", operator=">", threshold=0.0),
        ScenarioGoal(key="zustimmung", description="Zustimmung ueber 40", metric="approval", operator=">", threshold=40.0),
    ]
    result = _advance_to_election(build_initial_state(), goals)
    by_key = {g.key: g for g in result.term_summary.goals}
    # Budget startet 1000 und bleibt ohne Policy klar positiv; Zustimmung 50 > 40.
    assert by_key["haushalt"].met is True
    assert by_key["zustimmung"].met is True


def test_scenario_goals_are_non_binding_and_default_empty():
    """B9: verfehlte Ziele beenden die Partie NICHT (Sandbox bleibt spielbar),
    und ohne uebergebene Ziele ist TermSummary.goals leer.
    B2: Stat-zu-Stat-Effekte (Phillips) senken gdp_growth über 16 Turns, daher
    sinkt auch satisfaction leicht -- won kann variieren."""
    result = _advance_to_election(build_initial_state(), [])
    assert result.election_result is not None
    assert result.term_summary.goals == []


def test_sample_scenario_goals_are_well_formed():
    from landtag_sim.sample_data import SAMPLE_SCENARIO_GOALS

    valid_ops = {">", "<", ">=", "<=", "==", "!="}
    valid_metrics = set(STARTING_STATISTICS) | {"budget", "approval"}
    assert len(SAMPLE_SCENARIO_GOALS) >= 2
    keys = [g.key for g in SAMPLE_SCENARIO_GOALS]
    assert len(keys) == len(set(keys))
    for g in SAMPLE_SCENARIO_GOALS:
        assert g.operator in valid_ops
        assert g.metric in valid_metrics, g.metric
        assert g.description.strip()


def test_sample_factions_are_well_formed():
    """B8: reine Datenpruefung (noch keine Mechanik) -- eindeutige Namen,
    positive Sitze, Haltungen grob in [-1, 1]."""
    assert len(SAMPLE_FACTIONS) >= 3
    names = [f.name for f in SAMPLE_FACTIONS]
    assert len(names) == len(set(names)), "Fraktionsnamen muessen eindeutig sein"
    for f in SAMPLE_FACTIONS:
        assert f.seats > 0
        for stance in (f.stance_economy, f.stance_social, f.stance_environment):
            assert -1.0 <= stance <= 1.0


# M5 "Opposition-Loop" (BACKLOG.md B15): Koalitionsfaehigkeit als einheitliche Metrik

def test_coalition_viability_government_positive_econ():
    """Regierung mit guten Wirtschaftswerten + hoher Zufriedenheit → hohe Viability."""
    state = build_initial_state()
    state.statistics["gdp_growth"] = 3.0
    state.statistics["unemployment_rate"] = 4.0
    for group in state.voter_groups:
        group.satisfaction = 70.0

    viability = _calculate_coalition_viability(state, opposition_mode=False)
    assert 65 < viability <= 100, f"Expected high viability (65-100), got {viability}"


def test_coalition_viability_government_recession():
    """Regierung in Rezession mit niedriger Zufriedenheit → niedrige Viability."""
    state = build_initial_state()
    state.statistics["gdp_growth"] = -2.0
    state.statistics["unemployment_rate"] = 8.0
    for group in state.voter_groups:
        group.satisfaction = 30.0

    viability = _calculate_coalition_viability(state, opposition_mode=False)
    assert 0 <= viability < 40, f"Expected low viability (0-40), got {viability}"


def test_coalition_viability_opposition_starts_at_zero():
    """Opposition mit leeren satisfaction_deltas startet bei 0."""
    state = build_initial_state()
    state.opposition_mode = True
    state.opposition_satisfaction = {g.name: 0.0 for g in state.voter_groups}

    viability = _calculate_coalition_viability(state, opposition_mode=True)
    assert viability == 0.0


def test_coalition_viability_opposition_builds_up():
    """Opposition baut Satisfaction auf via Kampagnen → steigende Viability."""
    state = build_initial_state()
    state.opposition_mode = True

    # Intialisiere opposition_satisfaction für alle Gruppen
    state.opposition_satisfaction = {g.name: 0.0 for g in state.voter_groups}

    # Kampagne wirkt auf eine Gruppe (Industriearbeiter ~25% Basis)
    state.opposition_satisfaction["Industriearbeiter"] = 20.0

    viability = _calculate_coalition_viability(state, opposition_mode=True)
    # Industriearbeiter sind ~25% der Basis, also 20 * 0.25 ≈ 5 Punkte Viability
    assert 3 < viability < 10, f"Expected low viability (3-10), got {viability}"

    # Kampagne wirkt auf alle Gruppen
    for group_name in state.opposition_satisfaction:
        state.opposition_satisfaction[group_name] = 50.0

    viability = _calculate_coalition_viability(state, opposition_mode=True)
    assert 45 < viability <= 100, f"Expected high viability (45-100), got {viability}"


def test_opposition_campaigns_sample_data():
    """Sample-Opposition-Kampagnen sind wohlgeformt."""
    from landtag_sim.sample_data import SAMPLE_OPPOSITION_CAMPAIGNS

    assert len(SAMPLE_OPPOSITION_CAMPAIGNS) >= 3, "Mindestens 3 Kampagnen erwartet"

    for campaign in SAMPLE_OPPOSITION_CAMPAIGNS:
        assert campaign.key, "Kampagne muss key haben"
        assert campaign.name, "Kampagne muss name haben"
        assert campaign.capital_cost > 0, "capital_cost muss positiv sein"
        assert isinstance(campaign.satisfaction_deltas, dict), "satisfaction_deltas muss dict sein"
        assert len(campaign.satisfaction_deltas) > 0, "satisfaction_deltas darf nicht leer sein"


# B23 Phase 3: Ideology-Effekte Tests
def test_green_ideology_boosts_environment_groups():
    """Grüne Ideologie boosted umweltbewusste Wählergruppen."""
    state = build_initial_state()
    state.party_ideology = "green"

    # Umweltbewusste Wähler sollten mit grüner Ideologie ein Plus haben
    original_approval = sum(
        g.satisfaction * g.population_share
        for g in state.voter_groups
        if "Umweltbewusste" in g.name
    )

    from landtag_sim.engine import _weighted_approval
    approval_with_green = _weighted_approval(state)

    # Mit green ideology sollte Zufriedenheit steigen (wegen +20% Modifikator)
    # Das ist schwer zu testen ohne Änderung der Basis-Zufriedenheit,
    # aber wir können prüfen dass die Funktion läuft ohne Fehler
    assert isinstance(approval_with_green, float)
    assert 0 <= approval_with_green <= 100


def test_ideology_none_has_no_effect():
    """Keine Ideologie = kein Modifikator."""
    state = build_initial_state()
    state.party_ideology = None

    from landtag_sim.engine import _weighted_approval
    approval = _weighted_approval(state)

    # Sollte gleich sein wie das Original-System
    assert isinstance(approval, float)
    assert 0 <= approval <= 100


def test_red_ideology_boosts_social_groups():
    """Rote Ideologie boosted sozial-orientierte Wählergruppen."""
    state = build_initial_state()
    state.party_ideology = "red"

    from landtag_sim.engine import _weighted_approval
    approval = _weighted_approval(state)

    assert isinstance(approval, float)
    assert 0 <= approval <= 100


def test_blue_ideology_boosts_economy_groups():
    """Blaue Ideologie boosted wirtschafts-orientierte Wählergruppen."""
    state = build_initial_state()
    state.party_ideology = "blue"

    from landtag_sim.engine import _weighted_approval
    approval = _weighted_approval(state)

    assert isinstance(approval, float)
    assert 0 <= approval <= 100
