import pytest

from landtag_sim.engine import advance_turn, resolve_dilemma
from landtag_sim.models import (
    DilemmaOption,
    DilemmaPendingError,
    DilemmaRule,
    EventRule,
    InsufficientCapitalError,
    Policy,
    PolicyEffect,
    UnmetPrerequisiteError,
)
from landtag_sim.sample_data import (
    SAMPLE_DILEMMA_RULES,
    SAMPLE_EVENT_RULES,
    SAMPLE_POLICIES,
    build_initial_state,
)


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
