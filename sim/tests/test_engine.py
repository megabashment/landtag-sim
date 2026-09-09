import random

import pytest

from landtag_sim.engine import CAPITAL_CAP, CAPITAL_PER_TURN, BASE_BUDGET_INCOME_PER_TURN, advance_turn, resolve_dilemma
from landtag_sim.models import (
    DilemmaOption,
    DilemmaPendingError,
    DilemmaRule,
    EventRule,
    InsufficientCapitalError,
    Policy,
    PolicyAlreadyActiveError,
    PolicyEffect,
    PolicyNotActiveError,
    PolicyRequiredByActivePolicyError,
    UnmetPrerequisiteError,
)
from landtag_sim.sample_data import (
    SAMPLE_DILEMMA_RULES,
    SAMPLE_EVENT_RULES,
    SAMPLE_POLICIES,
    SAMPLE_VOTER_GROUPS,
    STARTING_STATISTICS,
    build_initial_state,
    jittered_starting_statistics,
)
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
    for _ in range(20):
        if result.pending_dilemma is not None:
            break
        result = advance_turn(state, SAMPLE_POLICIES, [], dilemma_rules=SAMPLE_DILEMMA_RULES)
        state = result.state
    assert result.pending_dilemma is not None
    assert result.pending_dilemma.rule_key == "rezession"


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
    for _ in range(20):
        if result.pending_dilemma is not None:
            break
        result = advance_turn(state, SAMPLE_POLICIES, [], dilemma_rules=SAMPLE_DILEMMA_RULES)
        state = result.state
    assert result.pending_dilemma is not None
    assert result.pending_dilemma.rule_key == "pflegeausbau"


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
