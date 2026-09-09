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

import random

from landtag_sim.models import (
    DilemmaOption,
    DilemmaRule,
    EventRule,
    Policy,
    PolicyEffect,
    SimState,
    SituationRule,
    VoterGroup,
)

STARTING_STATISTICS = {
    "unemployment_rate": 6.0,
    "gdp_growth": 1.2,
    "education_spending": 40.0,
    "healthcare_quality": 60.0,
    "co2_emissions": 100.0,
    "renewable_share": 35.0,
}


def jittered_starting_statistics(rng: random.Random | None = None, spread: float = 0.05) -> dict[str, float]:
    """P2-Punkt "Randomisierte Startbedingungen" (docs/game-design-roadmap.md):
    kleine Zufallsstreuung (Default +/-5%) um die Basiswerte, damit nicht
    jede Partie mit exakt identischen Zahlen startet.

    NUR fuer echte Partien gedacht (siehe backend/app/api/routes_game.py::
    create_session) -- build_initial_state() unten bleibt bewusst
    UNrandomisiert, damit Tests und der Balance-Runner
    (sim/landtag_sim/tools/balance_runner.py) reproduzierbar bleiben.
    """
    rng = rng or random.Random()
    return {key: value * (1 + rng.uniform(-spread, spread)) for key, value in STARTING_STATISTICS.items()}

SAMPLE_VOTER_GROUPS = [
    VoterGroup(name="Landwirtschaft", population_share=0.12, weight_economy=1.4, weight_environment=0.6),
    VoterGroup(name="Industriearbeiter", population_share=0.28, weight_economy=1.6, weight_social=1.0),
    VoterGroup(name="Staedtische Mitte", population_share=0.35, weight_social=1.3, weight_environment=1.3),
    VoterGroup(name="Rentner", population_share=0.25, weight_social=1.5, weight_economy=0.8),
    # Nach-P2-Nachschaerfung ("Waehlergruppen sind exklusiv", README.md
    # "Bekannte Vereinfachungen"): die vier Gruppen oben sind berufs-/
    # lebensphasenbasiert und schliessen sich gegenseitig aus (Summe exakt
    # 1.0). Democracys Kernmechanik braucht aber ZUSAETZLICH querliegende,
    # ueberlappende Identitaetsgruppen -- ein Landwirt kann z.B. gleichzeitig
    # "umweltbewusst" sein, ein Industriearbeiter kann "junge Familie" sein.
    # Diese zwei Gruppen ueberlappen daher ABSICHTLICH mit den vieren oben
    # (Summe aller population_share > 1.0). engine.py::_weighted_approval
    # normalisiert bereits durch total_share, unabhaengig davon ob die
    # Anteile 1.0 ergeben -- das macht dies zu einer reinen Datenaenderung
    # ohne Engine-/Schema-Aenderung (siehe test_voter_group_shares_
    # deliberately_overlap in test_engine.py).
    VoterGroup(name="Umweltbewusste Waehler", population_share=0.20, weight_environment=1.8, weight_economy=0.7, weight_social=1.0),
    VoterGroup(name="Junge Familien", population_share=0.18, weight_social=1.6, weight_economy=1.1, weight_environment=1.0),
]

# Summe der capital_cost der urspruenglichen drei Policies (erneuerbare_
# foerderung+bildungsoffensive+steuersenkung_mittelstand = 11) uebersteigt
# absichtlich das CAPITAL_CAP der Engine (10) -- alle drei gleichzeitig
# einzufuehren ist nicht machbar, jede Paarung schon. Erzwingt echte
# Prioritaeten statt "alles auf einmal" (siehe Game-Director-Review,
# Political-Capital-Abschnitt). gesundheitsreform und vermoegensteuer kamen
# spaeter dazu (siehe deren eigene Kommentare) und verschaerfen dasselbe
# Prinzip weiter, statt es aufzuweichen.
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
        upkeep_cost=10.0,
        capital_cost=4.0,
        # Balance-Nachschaerfung (Dominante-Strategie-Check, Roadmap #10):
        # der Balance-Runner hatte bildungsoffensive als praktisch immer
        # gewaehlte Strategie markiert (100% der Top-Szenarien). Ursache war
        # kein zu schwacher NEGATIVER Effekt per se (den gab es schon), sondern
        # dass er innerhalb derselben Kategorie ("economy") von einem noch
        # groesseren POSITIVEN Effekt (unemployment_rate) ueberkompensiert
        # wurde -- macht die Policy im Aggregat zu einem echten "Free Lunch"
        # ohne Zielkonflikt, obwohl sie technisch die Trade-off-Pflicht
        # erfuellte (test_every_sample_policy_has_at_least_one_negative_effect
        # prueft nur EINEN negativen Effekt, nicht die Netto-Bilanz pro
        # Kategorie). Fix: gdp_growth-Bremse deutlich verstaerkt (-0.4 -> -2.4),
        # damit die Policy netto auch auf der Wirtschaftsseite kostet -- ein
        # echter Trade-off Soziales-vs-Wirtschaft, analog zu erneuerbare_
        # foerderungs Umwelt-vs-Wirtschaft-Abwaegung. Upkeep leicht erhoeht
        # (8 -> 10) fuer zusaetzlichen Budgetdruck.
        effects=[
            PolicyEffect(statistic_key="education_spending", magnitude=15.0, delay_turns=1, inertia=3),
            PolicyEffect(statistic_key="unemployment_rate", magnitude=-1.5, delay_turns=4, inertia=5),
            PolicyEffect(statistic_key="gdp_growth", magnitude=-2.4, delay_turns=1, inertia=3),
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
    Policy(
        key="gesundheitsreform",
        name="Gesundheitsreform",
        one_time_cost=40.0,
        upkeep_cost=12.0,
        capital_cost=3.0,
        # Nach-P2-Nachschaerfung (Dominante-Strategie-Check, Roadmap #10):
        # healthcare_quality war bisher die EINZIGE Statistik ohne jede
        # Policy-Anbindung (nur Wahlwirkung ueber weight_social, nie aktiv
        # beeinflussbar) -- echte Luecke, kein reiner Balance-Kniff. Vierte,
        # von bildungsoffensive UNABHAENGIGE Policy (kein requires) verkleinert
        # ausserdem den Kombinationsraum, in dem bildungsoffensive rein
        # strukturell (wegen steuersenkung_mittelstands requires-Kette) in
        # fast jedem Szenario auftauchte -- das allein durch Zahlen-Tuning an
        # bildungsoffensive zu beheben ist unmoeglich, solange sie die
        # einzige "Basis"-Policy fuer eine andere ist (siehe balance_runner.py
        # find_dominant_policies-Docstring fuer die Heuristik).
        effects=[
            PolicyEffect(statistic_key="healthcare_quality", magnitude=12.0, delay_turns=2, inertia=4),
            # Trade-off: hoehere Gesundheitsausgaben/-abgaben bremsen das
            # Wachstum -- einzige Kategorie, die diese Policy beruehrt, also
            # ein sauberer Zielkonflikt ohne Ueberkompensation wie bei der
            # urspruenglichen bildungsoffensive (siehe deren Kommentar oben).
            PolicyEffect(statistic_key="gdp_growth", magnitude=-1.2, delay_turns=1, inertia=3),
        ],
    ),
    # Democracy-4-Recherche (siehe CLAUDE.md "Woher kommen positive Budget-
    # Werte?"): D4 modelliert Budget-Einnahmen nicht als unsichtbaren
    # Pauschal-Zuschuss, sondern als vom Spieler gewaehlte, sichtbare
    # Steuer-Policy (MinIncome/MaxIncome je nach Reglerposition). Diese
    # Policy ist die erste echte Einnahmequelle im Sinne von
    # Policy.income_per_turn -- BASE_BUDGET_INCOME_PER_TURN (engine.py)
    # bleibt bewusst zusaetzlich bestehen (unmodellierte "Basissteuer" des
    # Landes, siehe dortiger Kommentar), diese Policy kommt on top und ist
    # per Repeal wieder abschaltbar. Hoechster capital_cost aller Policies:
    # eine Vermoegensteuer ist politisch die umkaempfteste Massnahme, macht
    # sie mit zwei anderen teuren Policies zusammen am selben Wahlzyklus
    # kaum machbar (Democracy-4-Vorbild: echte Prioritaeten statt "alles auf
    # einmal", siehe Political-Capital-Kommentar oben).
    Policy(
        key="vermoegensteuer",
        name="Vermoegensteuer",
        one_time_cost=0.0,
        upkeep_cost=2.0,  # Verwaltungsaufwand der Erhebung
        capital_cost=5.0,
        income_per_turn=20.0,
        effects=[
            # Trade-off: hoehere Belastung bremst private Investitionen --
            # trifft wirtschaftlich gewichtete Gruppen (Landwirtschaft,
            # Industriearbeiter), analog zu erneuerbare_foerderungs
            # Umwelt-vs-Wirtschaft-Abwaegung.
            PolicyEffect(statistic_key="gdp_growth", magnitude=-1.4, delay_turns=1, inertia=4),
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
    # Nach-P2-Nachschaerfung ("Bekannte Vereinfachungen": bisher nur ein
    # einziges Beispiel-Dilemma, alle an unemployment_rate gekoppelt).
    # Beide neuen Dilemmas sind bewusst an Statistiken gekoppelt, die
    # tatsaechlich ueber die SAMPLE_POLICIES organisch erreichbar sind --
    # nicht nur ueber direkte State-Manipulation wie in der
    # Verifikations-Anleitung fuer arbeitsmarktkrise (siehe mistakes.md).
    # "rezession" triggert z.B. schon durch alleiniges Einfuehren von
    # bildungsoffensive nach dessen Balance-Nachschaerfung (staerkerer
    # gdp_growth-Trade-off, siehe dort) -- kein Test-only-Szenario.
    DilemmaRule(
        key="rezession",
        statistic_key="gdp_growth",
        operator="<",
        threshold=0.0,
        prompt_text=(
            "Das Wirtschaftswachstum faellt auf {value:.1f}% -- erste Stimmen "
            "sprechen von Rezession. Sofortiges Konjunkturprogramm oder auf "
            "Konsolidierung setzen?"
        ),
        cooldown_turns=10,
        options=[
            DilemmaOption(
                key="konjunkturprogramm",
                label="Sofortiges Konjunkturprogramm",
                budget_cost=60.0,
                effects=[PolicyEffect(statistic_key="gdp_growth", magnitude=1.5, delay_turns=0, inertia=2)],
            ),
            DilemmaOption(
                key="konsolidierung",
                label="Auf Konsolidierung setzen (Sparkurs)",
                budget_cost=0.0,
                effects=[
                    PolicyEffect(statistic_key="gdp_growth", magnitude=0.4, delay_turns=0, inertia=2),
                    # Trade-off: der Sparkurs kuerzt zuerst bei den Bildungsausgaben.
                    PolicyEffect(statistic_key="education_spending", magnitude=-4.0, delay_turns=0, inertia=1),
                ],
            ),
        ],
    ),
    # "pflegeausbau" ist bewusst ein POSITIVES Dilemma (Chance statt Krise) --
    # trigger durch eine gute Entwicklung (healthcare_quality steigt nach
    # gesundheitsreform), nicht durch eine schlechte. Sorgt fuer Abwechslung
    # zum sonst durchgehend krisengetriebenen Ton der Dilemmas.
    DilemmaRule(
        key="pflegeausbau",
        statistic_key="healthcare_quality",
        operator=">",
        threshold=68.0,
        prompt_text=(
            "Die Gesundheitsversorgung erreicht einen Indexwert von {value:.1f} -- "
            "spuerbar bessere Versorgung. Die Reform weiter ausbauen oder das "
            "Budget jetzt schonen?"
        ),
        cooldown_turns=12,
        options=[
            DilemmaOption(
                key="weiter_ausbauen",
                label="Reform weiter ausbauen",
                budget_cost=35.0,
                effects=[PolicyEffect(statistic_key="healthcare_quality", magnitude=6.0, delay_turns=0, inertia=2)],
            ),
            DilemmaOption(
                key="budget_schonen",
                label="Budget schonen, Ausbau stoppen",
                budget_cost=0.0,
                effects=[
                    # Trade-off: der abrupte Stopp mitten in der Reform
                    # verunsichert kurzfristig Beschaeftigte im Gesundheitssektor.
                    PolicyEffect(statistic_key="unemployment_rate", magnitude=0.3, delay_turns=0, inertia=1),
                ],
            ),
        ],
    ),
]


# B2 "Situations-Layer (mittlerer Zeithorizont, mit Hysterese)" (BACKLOG.md):
# Zustaende mit self-reinforcing Spiralen-Effekt. Im Gegensatz zu Events sind
# Situations nicht einmalig, sondern bleiben aktiv, solange eine Bedingung
# erfuellt ist (Hysterese: unterschiedliche Aktivierungs-/Deaktivierungs-
# Schwellen). Ihre Effekte wirken konstant pro Runde und spiegeln Dynamics
# ohne expliziten Text ("Story ohne Text", L2/L3).

SAMPLE_SITUATION_RULES = [
    SituationRule(
        key="abwanderung",
        statistic_key="gdp_growth",
        activate_op="<",
        activate_threshold=-0.5,
        deactivate_op=">",
        deactivate_threshold=0.5,
        template_text="Wirtschaftsflaute: Fachkraefte verlassen das Land.",
        effects=[
            # Spirale: wenn gdp_growth faellt, steigt unemployment als Nebeneffekt
            # (abwanderung von hochqualifizierten Arbeitsplaetzen). Das drueckt
            # gdp_growth weiter nach unten -> Zirkellauf, bis Gegen-Hebel
            # (bildungsoffensive/gesundheitsreform) gdp_growth wieder hebt.
            PolicyEffect(statistic_key="unemployment_rate", magnitude=0.5, delay_turns=0, inertia=1),
        ],
    ),
    SituationRule(
        key="gruenes_wachstum",
        statistic_key="renewable_share",
        activate_op=">",
        activate_threshold=65.0,
        deactivate_op="<",
        deactivate_threshold=55.0,
        template_text="Energiewende wirkt: Gruendungen boomen.",
        effects=[
            # Positive Spirale: hohe renewable_share foerdert GDP-Wachstum
            # und sauberer Betrieb senkt Emissionen weiter.
            PolicyEffect(statistic_key="gdp_growth", magnitude=0.4, delay_turns=0, inertia=1),
            PolicyEffect(statistic_key="co2_emissions", magnitude=-2.0, delay_turns=0, inertia=1),
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
