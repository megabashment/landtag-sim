"""Beispieldaten fuer Tests und den Balance-Runner (keine echten Werte).

Sobald data/sources/ echte Niedersachsen-Startwerte liefert (siehe
data/README.md), ersetzt das Backend diese Werte beim Anlegen einer
Session -- der Balance-Runner nutzt bewusst weiterhin synthetische Werte,
damit er unabhaengig von der Datenpipeline lauffaehig bleibt.

Nach Game-Director-Review (docs/architecture.md) hat jede Policy hier
bewusst mindestens einen NEGATIVEN Nebeneffekt -- reine Positiv-Policies
ohne Zielkonflikt sind der Hauptkritikpunkt der Review (siehe dort).
"""
from __future__ import annotations

from landtag_sim.models import DilemmaOption, DilemmaRule, EventRule, Policy, PolicyEffect, SimState, VoterGroup

STARTING_STATISTICS = {
    "unemployment_rate": 6.0,
    "gdp_growth": 1.2,
    "education_spending": 40.0,
    "healthcare_quality": 60.0,
    "co2_emissions": 100.0,
    "renewable_share": 35.0,
}

SAMPLE_VOTER_GROUPS = [
    VoterGroup(name="Landwirtschaft", population_share=0.12, weight_economy=1.4, weight_environment=0.6),
    VoterGroup(name="Industriearbeiter", population_share=0.28, weight_economy=1.6, weight_social=1.0),
    VoterGroup(name="Staedtische Mitte", population_share=0.35, weight_social=1.3, weight_environment=1.3),
    VoterGroup(name="Rentner", population_share=0.25, weight_social=1.5, weight_economy=0.8),
]

# Summe der capital_cost aller drei Policies (11) uebersteigt absichtlich das
# CAPITAL_CAP der Engine (10) -- alle drei gleichzeitig einzufuehren ist nicht
# machbar, jede Paarung schon. Erzwingt echte Prioritaeten statt "alles auf
# einmal" (siehe Game-Director-Review, Political-Capital-Abschnitt).
SAMPLE_POLICIES = [
    Policy(
        key="erneuerbare_foerderung",
        name="Foerderprogramm erneuerbare Energien",
        one_time_cost=50.0,
        upkeep_cost=5.0,
        capital_cost=4.0,
        effects=[
            PolicyEffect(statistic_key="renewable_share", magnitude=8.0, delay_turns=2, inertia=4),
            PolicyEffect(statistic_key="co2_emissions", magnitude=-10.0, delay_turns=3, inertia=5),
            # Trade-off: Foerderkosten daempfen kurzfristig das Wachstum -- trifft
            # wirtschaftlich gewichtete Gruppen (Landwirtschaft, Industriearbeiter).
            PolicyEffect(statistic_key="gdp_growth", magnitude=-0.6, delay_turns=1, inertia=3),
        ],
    ),
    Policy(
        key="bildungsoffensive",
        name="Bildungsoffensive",
        one_time_cost=30.0,
        upkeep_cost=8.0,
        capital_cost=4.0,
        effects=[
            PolicyEffect(statistic_key="education_spending", magnitude=15.0, delay_turns=1, inertia=3),
            PolicyEffect(statistic_key="unemployment_rate", magnitude=-1.5, delay_turns=4, inertia=5),
            # Trade-off: hoehere Ausgaben/Steuerlast bremsen kurzfristig das Wachstum.
            PolicyEffect(statistic_key="gdp_growth", magnitude=-0.4, delay_turns=1, inertia=3),
        ],
    ),
    Policy(
        key="steuersenkung_mittelstand",
        name="Steuersenkung Mittelstand",
        one_time_cost=0.0,
        upkeep_cost=15.0,
        capital_cost=3.0,
        # P1-Punkt "Policy-Pfade/Voraussetzungen" (docs/game-design-roadmap.md):
        # erst waehlbar, wenn die Bildungsoffensive schon laeuft -- konkretes
        # Beispiel aus der Roadmap selbst, schafft eine Reihenfolge-Entscheidung
        # zusaetzlich zur reinen Kombinations-Entscheidung.
        requires=["bildungsoffensive"],
        effects=[
            PolicyEffect(statistic_key="gdp_growth", magnitude=1.0, delay_turns=1, inertia=3),
            PolicyEffect(statistic_key="unemployment_rate", magnitude=-0.5, delay_turns=2, inertia=4),
            # Trade-off: fehlende Einnahmen kuerzen Bildungsausgaben -- trifft
            # sozial gewichtete Gruppen (Staedtische Mitte, Rentner).
            PolicyEffect(statistic_key="education_spending", magnitude=-6.0, delay_turns=2, inertia=4),
        ],
    ),
]

SAMPLE_EVENT_RULES = [
    EventRule(
        key="hohe_arbeitslosigkeit",
        statistic_key="unemployment_rate",
        operator=">",
        threshold=9.0,
        template_text="Die Arbeitslosenquote erreicht {value:.1f}% - der Druck auf die Landesregierung waechst.",
        cooldown_turns=6,
    ),
    EventRule(
        key="niedrige_bildungsausgaben",
        statistic_key="education_spending",
        operator="<",
        threshold=30.0,
        template_text="Bildungsausgaben auf {value:.1f} gesunken - Elternverbaende protestieren.",
        cooldown_turns=6,
    ),
]

# P1-Punkt "Dilemma-Events mit echten Entscheidungsoptionen"
# (docs/game-design-roadmap.md): gleicher Trigger wie das passive Event
# "hohe_arbeitslosigkeit", aber statt eines festen Effekts entscheidet der
# Spieler zwischen zwei Optionen mit echtem Zielkonflikt (kurzfristig teurer
# und sozialvertraeglich vs. staerkere Wirkung, aber zu Lasten der
# Bildungsausgaben). Feuert Vorrang vor passiven Events (siehe engine.py).
SAMPLE_DILEMMA_RULES = [
    DilemmaRule(
        key="arbeitsmarktkrise",
        statistic_key="unemployment_rate",
        operator=">",
        threshold=9.0,
        prompt_text=(
            "Die Arbeitslosenquote erreicht {value:.1f}%. Kurzarbeitergeld ausweiten "
            "oder eine haerte Arbeitsmarktreform durchsetzen?"
        ),
        cooldown_turns=10,
        options=[
            DilemmaOption(
                key="kurzarbeitergeld",
                label="Kurzarbeitergeld ausweiten",
                budget_cost=40.0,
                effects=[PolicyEffect(statistic_key="unemployment_rate", magnitude=-1.0, delay_turns=0, inertia=1)],
            ),
            DilemmaOption(
                key="arbeitsmarktreform",
                label="Arbeitsmarktreform durchsetzen",
                budget_cost=0.0,
                effects=[
                    PolicyEffect(statistic_key="unemployment_rate", magnitude=-2.0, delay_turns=0, inertia=1),
                    # Trade-off: die Reform kuerzt Bildungsausgaben, um schneller zu wirken.
                    PolicyEffect(statistic_key="education_spending", magnitude=-3.0, delay_turns=0, inertia=1),
                ],
            ),
        ],
    ),
]


def build_initial_state() -> SimState:
    return SimState(
        turn=0,
        budget=1000.0,
        statistics=dict(STARTING_STATISTICS),
        voter_groups=[VoterGroup(**vars(vg)) for vg in SAMPLE_VOTER_GROUPS],
        political_capital=10.0,
    )
