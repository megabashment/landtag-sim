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
    Faction,
    OppositionCampaign,
    Policy,
    PolicyEffect,
    ReportCondition,
    ReportRule,
    ScenarioGoal,
    SimState,
    SituationRule,
    UnlockCondition,
    VoterGroup,
)

# B13 "Echte Niedersachsen-Statistik-Importe" (BACKLOG.md): die Startwerte
# sind gegen recherchierte reale Niedersachsen-Kennzahlen abgeglichen und
# dokumentiert -- die vollstaendige Herleitung inkl. Quellen und Abrufdatum
# steht in data/sources/niedersachsen_startwerte.md. Kurzfassung je Wert:
#   unemployment_rate  5.9  -- reale Arbeitslosenquote Nds. Jahresdurchschnitt
#                             2024 (LSN). Direkt uebernommen.
#   gdp_growth         1.2  -- reales BIP-Wachstum Nds. 2024 lag bei +0.4%,
#                             einem konjunkturell schwachen Jahr; als
#                             Spielstart bewusst der laengerfristige Nds.-
#                             Korridor (~1.0-1.5%) statt des Ausreisserjahrs,
#                             sonst startet jede Partie direkt in der
#                             konjunkturdelle-/strompreiskrise-Triggerzone.
#   renewable_share   35.0  -- real deckt Nds. seinen Stromverbrauch 2024
#                             bilanziell zu >100% aus Erneuerbaren (54% des
#                             physischen Bruttostromverbrauchs). Das Spiel
#                             modelliert bewusst eine FRUEHERE Phase der
#                             Energiewende (~Nds. Mitte der 2010er), damit der
#                             Ausbau ueberhaupt noch Spiel-Hebel ist.
#   co2_emissions    100.0  -- 0-100-Index, KEINE Tonnen. 100 = Referenz-
#                             niveau des Spielstarts; sinkende Werte = real
#                             beobachteter Rueckgang (Nds. -33.8% ggue. 1990).
#   education_spending 40.0  } bewusst synthetische 0-100-Indizes ohne eine
#   healthcare_quality 60.0  } einzelne amtliche Entsprechung (siehe data-
#                            } README) -- plausibel gesetzt, nicht importiert.
STARTING_STATISTICS = {
    "unemployment_rate": 5.9,
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
        description=(
            "Zuschuesse fuer Wind- und Solarprojekte heben den Erneuerbaren-Anteil "
            "und druecken den CO2-Ausstoss - die Foerderkosten bremsen kurzfristig "
            "das Wirtschaftswachstum."
        ),
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
        description=(
            "Mehr Geld fuer Schulen und Weiterbildung senkt mittelfristig die "
            "Arbeitslosigkeit, kostet aber laufend Haushaltsmittel und daempft "
            "das Wachstum."
        ),
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
        description=(
            "Niedrigere Gewerbesteuer fuer kleine und mittlere Betriebe belebt "
            "Wachstum und Beschaeftigung, reisst aber ein Loch in die "
            "Bildungsausgaben. Setzt eine laufende Bildungsoffensive voraus."
        ),
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
        description=(
            "Investitionen in Kliniken und Pflege heben die Versorgungsqualitaet "
            "spuerbar, die hoeheren Abgaben bremsen jedoch das Wachstum."
        ),
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
    # B2 "Policy-Zerstückelung: Healthcare-Familie" (BACKLOG.md, Phase 2):
    # Die monolithische Gesundheitsreform wird graduell ergaenzt. Kleine,
    # spezialisierte Policies ermöglichen: (a) schnellere Reaktion auf kleine
    # Krisen, (b) weniger "Alles-oder-Nichts"-Planung, (c) Spieler kann
    # Portfolio selbst komponieren (alle drei kombiniert ~5.4 healthcare
    # statt 12.0). Capital-Kosten sind einzeln niedrig, zusammen immer noch
    # substanziell (3+4+4=11 < gesundheitsreform 12, aber teuer genug für echte
    # Trade-offs). Keine requires -- reines Portfolio-Voting.
    Policy(
        key="elektronische_krankenschreibung",
        name="Elektronische Krankenschreibung",
        description=(
            "Digitalisierung von Krankschreibungen spart Arztzeit und Verwaltungs-"
            "aufwand, hebt die Versorgungsqualitaet mit minimalem Budget-Impact. "
            "Kleiner, schnell umsetzbarer erste Schritt in der Digitalisierung "
            "des Gesundheitswesens."
        ),
        one_time_cost=15.0,
        upkeep_cost=2.0,
        capital_cost=1.0,
        effects=[
            PolicyEffect(statistic_key="healthcare_quality", magnitude=0.8, delay_turns=1, inertia=2),
            # Minimal negativer Effekt: Verwaltungsumstellung kostet kurz Geld.
            PolicyEffect(statistic_key="gdp_growth", magnitude=-0.1, delay_turns=1, inertia=2),
        ],
    ),
    Policy(
        key="telemedizin_foerderung",
        name="Telemedizin-Förderung",
        description=(
            "Breitband und Videokonsultationen erweitern den Zugang zur Versorgung "
            "insbesondere in laendlichen Gebieten. Moderater Fokus auf "
            "Flaechendeckung statt Spezialisierung."
        ),
        one_time_cost=20.0,
        upkeep_cost=4.0,
        capital_cost=2.0,
        effects=[
            PolicyEffect(statistic_key="healthcare_quality", magnitude=1.2, delay_turns=2, inertia=3),
            # Infrastrukturkosten und Breitband-Ausbau bremsen kurzfristig Wachstum.
            PolicyEffect(statistic_key="gdp_growth", magnitude=-0.2, delay_turns=1, inertia=2),
        ],
    ),
    Policy(
        key="digitale_patientenakte",
        name="Digitale Patientenakte",
        description=(
            "EHR-System verbessert Koordination und Fehlerquoten, hebt aber die "
            "IT-Sicherheits- und Datenschutz-Anforderungen. Fokus auf "
            "Interoperabilität und Datenschutz."
        ),
        one_time_cost=25.0,
        upkeep_cost=3.0,
        capital_cost=2.0,
        effects=[
            PolicyEffect(statistic_key="healthcare_quality", magnitude=0.9, delay_turns=2, inertia=3),
            # Sicherheitsinfrastruktur kostet Geld, IT-Wartung bremsst Wachstum.
            PolicyEffect(statistic_key="gdp_growth", magnitude=-0.15, delay_turns=1, inertia=2),
        ],
    ),
    # B2 "Policy-Zerstückelung: Erneuerbare-Familie" (BACKLOG.md, Phase 2):
    # Die grosse Foerderprogramm-Policy wird durch spezialisierte kleinere
    # Policies ergaenzt (nicht ersetzt). Spieler kann graduell Ausbau fahren:
    # einzeln +2 bis +2.5 renewable, zusammen +5 (ggü. erneuerbare_foerderung +8).
    # Capital-Kosten gering (1-2), aber kumulativ substanziell. Erlaubt
    # schnellere Reaktionen auf renewable_share-Ziele oder
    # gruenes_wachstum-Situation ohne die volle erneuerbare_foerderung-Bremse.
    Policy(
        key="solar_dachanlagen",
        name="Solar-Dachanlagen-Förderung",
        description=(
            "Zuschuesse fuer Photovoltaik auf privaten und gewerblichen Dächern. "
            "Geringe Flaechenanforderungen, schnelle Amortisation, breite "
            "akzeptance. Kostengünstiger Weg zu lokalem grünem Strom."
        ),
        one_time_cost=10.0,
        upkeep_cost=2.0,
        capital_cost=1.0,
        effects=[
            PolicyEffect(statistic_key="renewable_share", magnitude=2.0, delay_turns=1, inertia=2),
            PolicyEffect(statistic_key="co2_emissions", magnitude=-3.0, delay_turns=2, inertia=3),
            # Moderat: Förderkosten bremsen Wachstum, aber weniger als
            # erneuerbare_foerderung (erneuerbare: -0.6, solar: -0.15).
            PolicyEffect(statistic_key="gdp_growth", magnitude=-0.15, delay_turns=1, inertia=2),
        ],
    ),
    Policy(
        key="windkraft_kleinanlagen",
        name="Windkraft-Kleinanlagen",
        description=(
            "Zuschuesse fuer Windkraftanlagen unter 5 MW, oft als Bürgerbeteiligungs-"
            "projekte. Breitere Dezentralisierung des Stromnetzes, hoeheres "
            "Potenzial als Solar, aber laengere Genehmigungen."
        ),
        one_time_cost=18.0,
        upkeep_cost=3.0,
        capital_cost=2.0,
        effects=[
            PolicyEffect(statistic_key="renewable_share", magnitude=2.5, delay_turns=2, inertia=3),
            PolicyEffect(statistic_key="co2_emissions", magnitude=-4.0, delay_turns=3, inertia=4),
            # Genehmigungskosten, Netzanbindung, Flaechensuche kosten Wachstum.
            PolicyEffect(statistic_key="gdp_growth", magnitude=-0.25, delay_turns=1, inertia=2),
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
        description=(
            "Eine Abgabe auf grosse Vermoegen bringt verlaessliche Mehreinnahmen, "
            "daempft aber private Investitionen und damit das Wachstum."
        ),
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
    # B7 "Dynamische Policy-Freischaltung durch Sim-Zustand" (BACKLOG.md, L7):
    # die folgenden drei Policies sind zu Spielbeginn GESPERRT und werden erst
    # verfuegbar, wenn eine gesellschaftliche Verschiebung ihre
    # unlock_conditions erfuellt (anders als `requires`, das eine andere
    # AKTIVE Policy verlangt). Bewusst an Statistiken gekoppelt, die der
    # Spieler ueber andere Policies/Situations tatsaechlich herbeifuehren kann
    # (Synergie mit B2/B6-Reachability), damit die Freischaltung nicht totes
    # Gewicht bleibt. Hinweis: der Combo-Balance-Runner enact-et alle Policies
    # in Runde 0 und trifft diese daher als NICHT_MACHBAR(gesperrt) an -- das
    # ist erwartet (siehe run_scenario / mistakes.md), ihre Balance wird ueber
    # gezielte Engine-Tests abgedeckt.
    Policy(
        key="digitalpakt_schulen",
        name="Digitalpakt Schulen",
        description=(
            "Breitband, Endgeraete und IT-Wartung fuer alle Schulen bauen auf einer "
            "bereits gut finanzierten Bildungslandschaft auf; hohe Anschubkosten "
            "belasten kurzfristig den Haushalt. Erst verfuegbar, wenn die "
            "Bildungsausgaben hoch genug sind."
        ),
        one_time_cost=25.0,
        upkeep_cost=6.0,
        capital_cost=3.0,
        # Freigeschaltet, sobald in Bildung investiert wurde (bildungsoffensive
        # hebt education_spending 40 -> ~55): eine bereits gut ausgestattete
        # Schullandschaft macht die Digitalisierung erst sinnvoll.
        unlock_conditions=[UnlockCondition(statistic_key="education_spending", operator=">", threshold=50.0)],
        effects=[
            PolicyEffect(statistic_key="education_spending", magnitude=6.0, delay_turns=1, inertia=3),
            # Trade-off: hohe Anschub-/Wartungskosten bremsen kurzfristig das Wachstum.
            PolicyEffect(statistic_key="gdp_growth", magnitude=-0.8, delay_turns=1, inertia=3),
        ],
    ),
    Policy(
        key="gruener_wasserstoff",
        name="Foerderung gruener Wasserstoff",
        description=(
            "Foerderung von Elektrolyse und H2-Infrastruktur senkt die Emissionen "
            "weiter, lohnt sich aber erst bei viel gruenem Strom im Netz und "
            "kostet zusaetzliches Wachstum."
        ),
        one_time_cost=45.0,
        upkeep_cost=9.0,
        capital_cost=4.0,
        # Freigeschaltet, sobald der Erneuerbaren-Anteil hoch genug ist
        # (erneuerbare_foerderung hebt renewable_share 35 -> ~43): Wasserstoff
        # lohnt erst mit reichlich gruenem Strom im Netz.
        unlock_conditions=[UnlockCondition(statistic_key="renewable_share", operator=">", threshold=42.0)],
        effects=[
            PolicyEffect(statistic_key="co2_emissions", magnitude=-8.0, delay_turns=2, inertia=4),
            # Trade-off: teures Foerderprogramm daempft das Wachstum (Umwelt vs.
            # Wirtschaft, analog erneuerbare_foerderung -- nur eine Stufe teurer).
            PolicyEffect(statistic_key="gdp_growth", magnitude=-0.4, delay_turns=1, inertia=3),
        ],
    ),
    Policy(
        key="arbeitsmarkt_sofortprogramm",
        name="Arbeitsmarkt-Sofortprogramm",
        description=(
            "Kurzfristige Lohnzuschuesse und Vermittlungsoffensiven druecken die "
            "Arbeitslosigkeit schnell, gegenfinanziert zu Lasten der "
            "Bildungsausgaben. Nur in einer Arbeitsmarktkrise verfuegbar."
        ),
        one_time_cost=30.0,
        upkeep_cost=10.0,
        capital_cost=4.0,
        # Freigeschaltet erst in einer Arbeitsmarkt-Schieflage
        # (unemployment_rate > 7, z.B. ueber die Situation `abwanderung` oder
        # bildungsoffensives Wachstums-Trade-off erreichbar): ein
        # Kriseninstrument, das es ohne Krise gar nicht braucht.
        unlock_conditions=[UnlockCondition(statistic_key="unemployment_rate", operator=">", threshold=7.0)],
        effects=[
            PolicyEffect(statistic_key="unemployment_rate", magnitude=-2.0, delay_turns=1, inertia=3),
            # Trade-off: schnell gegenfinanziert zu Lasten der Bildungsausgaben.
            PolicyEffect(statistic_key="education_spending", magnitude=-5.0, delay_turns=1, inertia=3),
        ],
    ),
]

SAMPLE_EVENT_RULES = [
    EventRule(
        key="hohe_arbeitslosigkeit",
        statistic_key="unemployment_rate",
        operator=">",
        # B12: 9 -> 8. Der Frueh-Warn-Event soll VOR dem gleichnamigen
        # Krisen-Dilemma `arbeitsmarktkrise` (Schwelle 9) greifen.
        threshold=8.0,
        template_text="Die Arbeitslosenquote erreicht {value:.1f}% - der Druck auf die Landesregierung waechst.",
        cooldown_turns=6,
    ),
    # B12: Schwelle von 30 -> 34 angehoben. Bei Startwert 40 ist 30 organisch
    # nicht erreichbar (Telemetrie flaggte NIE_AUSGELOEST); die staerksten
    # Bildungs-Trade-offs (steuersenkung_mittelstand -6, arbeitsmarkt_
    # sofortprogramm -5) druecken education_spending auf ~29-34.
    EventRule(
        key="niedrige_bildungsausgaben",
        statistic_key="education_spending",
        operator="<",
        threshold=34.0,
        template_text="Bildungsausgaben auf {value:.1f} gesunken - Elternverbaende protestieren.",
        cooldown_turns=6,
    ),
    # B12 "Content-Ausbau": positives Gegenstueck -- eine gut ausgestattete
    # Bildungslandschaft (bildungsoffensive hebt education_spending 40 -> ~55)
    # produziert auch mal eine gute Nachricht statt nur Krisenmeldungen.
    EventRule(
        key="bildungserfolg",
        statistic_key="education_spending",
        operator=">",
        threshold=52.0,
        template_text=(
            "Niedersachsen klettert im laenderuebergreifenden Bildungsvergleich "
            "nach oben - Bildungsindex bei {value:.1f}."
        ),
        cooldown_turns=8,
    ),
    # B12: CO2-Ereigniskette. Nichts in den Policies hebt co2_emissions --
    # der Anstieg kommt aus der Situation `abwanderung` (Rezession =
    # aufgeschobene Modernisierung, aeltere Anlagen laufen laenger). Ab ~106
    # wird daraus eine sichtbare Meldung, ab 108 das Dilemma `klimaschutz-
    # gesetz`, ab 110 die Situation `klimakrise` (siehe unten).
    EventRule(
        key="smogalarm",
        statistic_key="co2_emissions",
        operator=">",
        threshold=104.0,
        template_text=(
            "Anhaltende Inversionswetterlage: mehrere Staedte rufen wegen "
            "Feinstaub Smogalarm aus (Emissionsindex {value:.1f})."
        ),
        cooldown_turns=5,
    ),
    # B12: Erneuerbaren-Meilenstein. erneuerbare_foerderung hebt
    # renewable_share 35 -> ~43; die Schwelle liegt bewusst knapp darunter,
    # damit die Meldung fuer aktiv gruene Regierungen erreichbar ist.
    EventRule(
        key="energiewende_schub",
        statistic_key="renewable_share",
        operator=">",
        threshold=42.0,
        template_text=(
            "Ein neuer Windpark geht ans Netz: der Anteil erneuerbarer Energien "
            "steigt auf {value:.1f}%."
        ),
        cooldown_turns=8,
    ),
    # B12: Gesundheits-Engpass. Abwaertsdruck auf healthcare_quality kommt
    # aus `abwanderung` (Fachkraefte-Abwanderung trifft auch Kliniken, neuer
    # Effekt dort). gesundheitsreform ist der Gegen-Hebel.
    EventRule(
        key="pflege_engpass",
        statistic_key="healthcare_quality",
        operator="<",
        threshold=54.0,
        template_text=(
            "Kliniken auf dem Land duennen ihr Angebot aus - der Versorgungsindex "
            "faellt auf {value:.1f}."
        ),
        cooldown_turns=6,
    ),
    # B12: Ueberhitzungssignal statt Krise -- sehr niedrige Arbeitslosigkeit
    # (bildungsoffensive + arbeitsmarkt_sofortprogramm koennen unemployment
    # deutlich unter 4 druecken) erzeugt Fachkraeftemangel-Schlagzeilen.
    EventRule(
        key="fachkraeftemangel",
        statistic_key="unemployment_rate",
        operator="<",
        threshold=3.8,
        template_text=(
            "Handwerk und Pflege schlagen Alarm: bei {value:.1f}% Arbeitslosigkeit "
            "bleiben Stellen monatelang unbesetzt."
        ),
        cooldown_turns=8,
    ),
    # B3 "Zustandsgekoppelte Risiko-Events" (BACKLOG.md, L4/L9): die Krisen-
    # Dilemmas (rezession bei gdp_growth < 0.0, arbeitsmarktkrise bei
    # unemployment_rate > 9.0) triggern im organischen Spielverlauf fast nie,
    # weil nichts die Statistiken weit genug Richtung Krise treibt (siehe
    # mistakes.md). Reine Zufalls-Schocks waeren die faule Loesung und nerven
    # (L9). `konjunkturdelle` ist stattdessen eine ZUSTANDSGEKOPPELTE Vorstufe:
    # sie greift nur, wenn das Wachstum ohnehin schon schwaechelt
    # (gdp_growth < 0.5), und verstaerkt den Abwaertstrend dann mit
    # `probability` pro Runde (deterministischer crc32-Wuerfel, siehe
    # events.py::passes_probability_gate). Dadurch wird `rezession` aus einer
    # nur leicht negativen Lage heraus organisch erreichbar -- und ueber die
    # Situation `abwanderung` (drueckt bei niedrigem Wachstum die
    # Arbeitslosenquote hoch) mittelbar auch `arbeitsmarktkrise`.
    EventRule(
        key="konjunkturdelle",
        statistic_key="gdp_growth",
        operator="<",
        threshold=0.5,
        template_text=(
            "Konjunkturdelle: die Auftragseingaenge sinken den dritten Monat in "
            "Folge, das Wachstum liegt nur noch bei {value:.1f}%."
        ),
        cooldown_turns=2,
        probability=0.4,
        effects=[
            PolicyEffect(statistic_key="gdp_growth", magnitude=-0.35, delay_turns=0, inertia=1),
        ],
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
    # B12 "Content-Ausbau": vier neue Dilemmas, jeweils an eine Statistik
    # gekoppelt, die ueber die SAMPLE_POLICIES / Situations organisch
    # erreichbar ist (Balance-Runner-Telemetrie als Nachweis, siehe
    # test_balance_runner.py). Bewusst gemischter Ton: klimaschutzgesetz und
    # krankenhausreform sind Krisen, bildungsgipfel ist eine Chance,
    # strompreiskrise ein klassischer Zielkonflikt Preis vs. Umbau.
    DilemmaRule(
        key="klimaschutzgesetz",
        statistic_key="co2_emissions",
        operator=">",
        threshold=106.0,
        prompt_text=(
            "Der Emissionsindex steigt auf {value:.1f}. Ein verbindliches "
            "Landes-Klimaschutzgesetz mit harten Grenzwerten durchsetzen oder "
            "auf freiwillige Branchenvereinbarungen setzen?"
        ),
        cooldown_turns=12,
        options=[
            DilemmaOption(
                key="verbindliche_grenzwerte",
                label="Verbindliche Grenzwerte per Gesetz",
                budget_cost=15.0,
                effects=[
                    PolicyEffect(statistic_key="co2_emissions", magnitude=-9.0, delay_turns=0, inertia=2),
                    # Trade-off: harte Auflagen bremsen die Industrie kurzfristig.
                    PolicyEffect(statistic_key="gdp_growth", magnitude=-0.6, delay_turns=0, inertia=2),
                ],
            ),
            DilemmaOption(
                key="freiwillige_vereinbarung",
                label="Freiwillige Branchenvereinbarungen",
                budget_cost=0.0,
                effects=[
                    # Schwache Wirkung, dafuer kein Wachstumsknick.
                    PolicyEffect(statistic_key="co2_emissions", magnitude=-2.5, delay_turns=0, inertia=2),
                ],
            ),
        ],
    ),
    DilemmaRule(
        key="krankenhausreform",
        statistic_key="healthcare_quality",
        operator="<",
        threshold=50.0,
        prompt_text=(
            "Der Versorgungsindex faellt auf {value:.1f}. Kleine Kliniken zu "
            "Zentren zusammenlegen (effizienter, aber Standortschliessungen) "
            "oder die Haeuser flaechendeckend querfinanzieren?"
        ),
        cooldown_turns=12,
        options=[
            DilemmaOption(
                key="zentralisierung",
                label="Klinikzentren bilden",
                budget_cost=10.0,
                effects=[
                    PolicyEffect(statistic_key="healthcare_quality", magnitude=7.0, delay_turns=1, inertia=3),
                    # Trade-off: Standortschliessungen kosten regional Jobs.
                    PolicyEffect(statistic_key="unemployment_rate", magnitude=0.6, delay_turns=0, inertia=1),
                ],
            ),
            DilemmaOption(
                key="querfinanzierung",
                label="Haeuser flaechendeckend stuetzen",
                budget_cost=55.0,
                effects=[
                    PolicyEffect(statistic_key="healthcare_quality", magnitude=5.0, delay_turns=1, inertia=3),
                ],
            ),
        ],
    ),
    DilemmaRule(
        key="strompreiskrise",
        statistic_key="gdp_growth",
        operator="<",
        threshold=0.6,
        prompt_text=(
            "Hohe Energiekosten bei nur {value:.1f}% Wachstum. Einen "
            "Industriestrompreis aus Landesmitteln subventionieren oder das "
            "Geld in den Netzausbau fuer Erneuerbare lenken?"
        ),
        cooldown_turns=10,
        options=[
            DilemmaOption(
                key="netzausbau",
                label="In den Netzausbau investieren",
                budget_cost=30.0,
                effects=[
                    PolicyEffect(statistic_key="renewable_share", magnitude=4.0, delay_turns=1, inertia=3),
                    # schwaecherer Sofort-Effekt aufs Wachstum als die Subvention
                    PolicyEffect(statistic_key="gdp_growth", magnitude=0.3, delay_turns=1, inertia=2),
                ],
            ),
            DilemmaOption(
                key="industriestrompreis",
                label="Industriestrompreis subventionieren",
                budget_cost=50.0,
                effects=[PolicyEffect(statistic_key="gdp_growth", magnitude=0.8, delay_turns=0, inertia=2)],
            ),
        ],
    ),
    DilemmaRule(
        key="bildungsgipfel",
        statistic_key="education_spending",
        operator=">",
        threshold=55.0,
        prompt_text=(
            "Bildungsindex bei {value:.1f} -- ein Momentum, das man nutzen "
            "koennte. Einen Bildungsgipfel mit Ausbauprogramm einberufen oder "
            "die guten Zahlen fuer Haushaltskonsolidierung nutzen?"
        ),
        cooldown_turns=14,
        options=[
            DilemmaOption(
                key="ausbauprogramm",
                label="Ausbauprogramm beschliessen",
                budget_cost=40.0,
                effects=[
                    PolicyEffect(statistic_key="education_spending", magnitude=5.0, delay_turns=1, inertia=3),
                    PolicyEffect(statistic_key="unemployment_rate", magnitude=-0.4, delay_turns=3, inertia=4),
                ],
            ),
            DilemmaOption(
                key="konsolidieren",
                label="Zahlen fuer Konsolidierung nutzen",
                budget_cost=-25.0,  # entlastet den Haushalt
                effects=[
                    # Trade-off: das Signal "wir sparen jetzt hier" bremst den Schwung.
                    PolicyEffect(statistic_key="education_spending", magnitude=-3.0, delay_turns=1, inertia=2),
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
        # B12: Aktivierung -0.5 -> -0.2 vorgezogen. `abwanderung` ist jetzt die
        # zentrale Reichbarkeits-Achse fuer die co2-/healthcare-Ketten
        # (Effekte unten); bei -0.5 feuerte sie so selten, dass die
        # nachgelagerten Regeln nie erreicht wurden (Telemetrie). Die
        # Hysterese-Luecke zu deactivate (+0.5) bleibt breit.
        activate_threshold=-0.2,
        deactivate_op=">",
        # B12: Hysterese-Fenster verbreitert (0.5 -> 0.9). Einmal in der
        # Abwanderung, endet sie erst bei solider Erholung -- dadurch dauern
        # die Episoden laenger und die nachgelagerten co2-/healthcare-/
        # unemployment-Schwellen werden ueberhaupt erreichbar (Telemetrie).
        deactivate_threshold=0.9,
        template_text="Wirtschaftsflaute: Fachkraefte verlassen das Land.",
        effects=[
            # Spirale: wenn gdp_growth faellt, steigt unemployment als Nebeneffekt
            # (abwanderung von hochqualifizierten Arbeitsplaetzen). Das drueckt
            # gdp_growth weiter nach unten -> Zirkellauf, bis Gegen-Hebel
            # (bildungsoffensive/gesundheitsreform) gdp_growth wieder hebt.
            PolicyEffect(statistic_key="unemployment_rate", magnitude=0.6, delay_turns=0, inertia=1),
            # B12: die Rezession ist die zentrale "Reichbarkeits-Achse" fuer
            # alle sonst unerreichbaren Statistik-Bereiche -- jedes Krisen-
            # Event/-Dilemma/-Situation haengt an ihr. Bewusst MILDE Einzel-
            # Effekte (L3-Warnung "keine death spiral"), aber breit gestreut:
            # aufgeschobene Modernisierung -> aeltere Anlagen laufen laenger
            # (+co2); Fachkraefte-Abwanderung trifft Kliniken (-healthcare);
            # klamme Haushalte kuerzen zuerst bei Schulen (-education). Jede
            # Achse hat einen klaren Gegen-Hebel (erneuerbare_foerderung /
            # gesundheitsreform / bildungsoffensive), Spirale bleibt brechbar.
            PolicyEffect(statistic_key="co2_emissions", magnitude=1.8, delay_turns=0, inertia=1),
            PolicyEffect(statistic_key="healthcare_quality", magnitude=-1.5, delay_turns=0, inertia=1),
            PolicyEffect(statistic_key="education_spending", magnitude=-1.2, delay_turns=0, inertia=1),
        ],
    ),
    SituationRule(
        key="gruenes_wachstum",
        statistic_key="renewable_share",
        activate_op=">",
        # B12: Schwelle 65 -> 42 gesenkt. Nur erneuerbare_foerderung hebt
        # renewable_share ueberhaupt (+8, Startwert 35), Maximum liegt bei
        # ~43 -- 65 war nie erreichbar (Telemetrie: NIE_AUSGELOEST). 42 macht
        # die positive Spirale fuer aktiv gruene Regierungen zugaenglich, die
        # Hysterese-Luecke (Deaktivierung erst bei 37) bleibt erhalten.
        activate_threshold=42.0,
        deactivate_op="<",
        deactivate_threshold=37.0,
        template_text="Energiewende wirkt: Gruendungen boomen.",
        effects=[
            # Positive Spirale: hohe renewable_share foerdert GDP-Wachstum
            # und sauberer Betrieb senkt Emissionen weiter.
            PolicyEffect(statistic_key="gdp_growth", magnitude=0.4, delay_turns=0, inertia=1),
            PolicyEffect(statistic_key="co2_emissions", magnitude=-2.0, delay_turns=0, inertia=1),
        ],
    ),
    # B12: negative CO2-Spirale. Aktiviert erst deutlich ueber dem Startwert
    # (100) -- nur erreichbar, wenn `abwanderung` co2 laenger nach oben
    # gedrueckt hat. Verstaerkt sich selbst (+co2) und bremst zusaetzlich das
    # Wachstum (Investitionsunsicherheit / Klage-Risiko). Gegen-Hebel:
    # erneuerbare_foerderung, gruener_wasserstoff, Dilemma-Option
    # `verbindliche_grenzwerte`.
    SituationRule(
        key="klimakrise",
        statistic_key="co2_emissions",
        activate_op=">",
        activate_threshold=107.0,
        deactivate_op="<",
        deactivate_threshold=100.0,
        template_text="Klimakrise: Hitzeschaeden und Klagen belasten den Standort.",
        effects=[
            PolicyEffect(statistic_key="co2_emissions", magnitude=1.4, delay_turns=0, inertia=1),
            PolicyEffect(statistic_key="gdp_growth", magnitude=-0.3, delay_turns=0, inertia=1),
        ],
    ),
    # B12: positive Bildungs-Spirale als Gegenstueck zu `abwanderung`.
    # bildungsoffensive hebt education_spending 40 -> ~55; ab 58 traegt sich
    # der Effekt selbst (bessere Qualifikation -> weniger Arbeitslosigkeit ->
    # mehr Steuerkraft fuer Bildung). Hysterese: faellt erst bei < 50 wieder aus.
    SituationRule(
        key="bildungsaufstieg",
        statistic_key="education_spending",
        activate_op=">",
        activate_threshold=58.0,
        deactivate_op="<",
        deactivate_threshold=50.0,
        template_text="Bildungsaufstieg: Fachkraefte bleiben, Betriebe siedeln sich an.",
        effects=[
            PolicyEffect(statistic_key="unemployment_rate", magnitude=-0.35, delay_turns=0, inertia=1),
            PolicyEffect(statistic_key="gdp_growth", magnitude=0.2, delay_turns=0, inertia=1),
        ],
    ),
    # B12: negative Gesundheits-Spirale. Erreichbar, wenn `abwanderung`
    # healthcare_quality laenger gedrueckt hat (Startwert 60). Personalflucht
    # verstaerkt sich selbst; Gegen-Hebel: gesundheitsreform, Dilemma
    # `krankenhausreform`.
    SituationRule(
        key="pflegenotstand",
        statistic_key="healthcare_quality",
        activate_op="<",
        activate_threshold=48.0,
        deactivate_op=">",
        deactivate_threshold=55.0,
        template_text="Pflegenotstand: unbesetzte Stellen, Stationen bleiben geschlossen.",
        effects=[
            PolicyEffect(statistic_key="healthcare_quality", magnitude=-1.0, delay_turns=0, inertia=1),
            PolicyEffect(statistic_key="unemployment_rate", magnitude=0.2, delay_turns=0, inertia=1),
        ],
    ),
]


# B4 "Narrative Konsequenz-Ebene ('Presseschau')" (BACKLOG.md, L5): rein
# textliche Konsequenz-Meldungen, die die Kausalkette einer Entwicklung
# benennen, OHNE eine Sim-Statistik zu veraendern. Democracy 4s "Media
# Reports". Jede Regel ist UND-verknuepft (alle conditions muessen erfuellt
# sein); requires_policy/forbids_policy koppeln die Meldung zusaetzlich an
# eine Spieler-Entscheidung, damit der Text wie eine echte Folge WIRKT und
# nicht wie Zufalls-Flavour. advance_turn haengt hoechstens einen Report pro
# Runde an, und nur in Runden ohne Event/Dilemma (Frequenz-Management).
SAMPLE_REPORT_RULES = [
    ReportRule(
        key="bildungsoffensive_wirkt",
        conditions=[
            ReportCondition(statistic_key="education_spending", operator=">", threshold=50.0),
            ReportCondition(statistic_key="unemployment_rate", operator="<", threshold=5.5),
        ],
        requires_policy="bildungsoffensive",
        template_text=(
            "Berufsschulen melden volle Klassen und sinkende Abbrecherquoten -- "
            "Fachleute fuehren das auf die Bildungsoffensive zurueck."
        ),
    ),
    ReportRule(
        key="werksschliessung",
        conditions=[
            ReportCondition(statistic_key="gdp_growth", operator="<", threshold=0.2),
            ReportCondition(statistic_key="unemployment_rate", operator=">", threshold=7.0),
        ],
        template_text=(
            "Ein Automobilzulieferer schliesst sein Werk. Die Geschaeftsfuehrung nennt "
            "die schwache Konjunktur und {unemployment_rate:.1f}% Arbeitslosigkeit als Grund."
        ),
    ),
    ReportRule(
        key="energiewende_vorzeigeland",
        conditions=[
            ReportCondition(statistic_key="renewable_share", operator=">", threshold=55.0),
            ReportCondition(statistic_key="co2_emissions", operator="<", threshold=92.0),
        ],
        template_text=(
            "Ein Bundesministerium bezeichnet das Land als Vorbild bei der Energiewende -- "
            "{renewable_share:.0f}% Erneuerbare im Netz."
        ),
    ),
    ReportRule(
        key="pflegenotstand",
        conditions=[
            ReportCondition(statistic_key="healthcare_quality", operator="<", threshold=50.0),
        ],
        template_text=(
            "Kliniken schliessen Stationen, Verbaende sprechen von einem Pflegenotstand "
            "(Versorgungsindex {healthcare_quality:.0f})."
        ),
    ),
    ReportRule(
        key="vermoegensteuer_debatte",
        conditions=[
            ReportCondition(statistic_key="gdp_growth", operator="<", threshold=0.8),
        ],
        requires_policy="vermoegensteuer",
        template_text=(
            "Wirtschaftsverbaende machen die Vermoegensteuer fuer zurueckhaltende "
            "Investitionen verantwortlich; die Regierung widerspricht."
        ),
    ),
    ReportRule(
        key="klimaklage",
        conditions=[
            ReportCondition(statistic_key="co2_emissions", operator=">", threshold=108.0),
            ReportCondition(statistic_key="renewable_share", operator="<", threshold=40.0),
        ],
        forbids_policy="erneuerbare_foerderung",
        template_text=(
            "Ein Umweltverband reicht Klage gegen das Land ein: die Emissionen steigen, "
            "ein Foerderprogramm fuer Erneuerbare fehlt weiterhin."
        ),
    ),
    ReportRule(
        key="mittelstand_lob",
        conditions=[
            ReportCondition(statistic_key="gdp_growth", operator=">", threshold=2.2),
        ],
        requires_policy="steuersenkung_mittelstand",
        template_text=(
            "Die Handwerkskammer lobt das Investitionsklima; die Auftragsbuecher seien "
            "so voll wie lange nicht."
        ),
    ),
]


# B8 "Fraktions-/Sitz-Datenmodell" (BACKLOG.md, L8): fiktive Sitzverteilung
# eines Landtags, rein zur ANZEIGE ("Sitzverteilung im Landtag"). Noch keine
# Mechanik -- weder Koalitionslogik noch Mehrheitszwang fuer Policies (das ist
# explizit Post-M3, siehe BACKLOG.md). Bewusst generische Fraktionsnamen statt
# realer Parteien, konsistent mit den generischen Waehlergruppen oben. Summe
# der Sitze ist eine glatte Zahl (135), keine reale Landtagsgroesse.
SAMPLE_FACTIONS = [
    Faction(name="Sozialdemokratische Fraktion", seats=42, stance_economy=0.2, stance_social=0.7, stance_environment=0.3),
    Faction(name="Konservative Fraktion", seats=38, stance_economy=-0.4, stance_social=-0.2, stance_environment=-0.3),
    Faction(name="Gruene Fraktion", seats=24, stance_economy=0.1, stance_social=0.4, stance_environment=0.9),
    Faction(name="Liberale Fraktion", seats=17, stance_economy=-0.7, stance_social=-0.1, stance_environment=-0.1),
    Faction(name="Linke Fraktion", seats=14, stance_economy=0.6, stance_social=0.8, stance_environment=0.4),
]


# B9 "Szenario-/Legislatur-Ziele" (BACKLOG.md, L1/L10; F1 = optionale,
# unverbindliche Ziele): am Legislaturende gegen den Endzustand geprueft und
# in der Amtszeit-Bilanz als erfuellt/verfehlt ausgewiesen. UNVERBINDLICH --
# ein verfehltes Ziel beendet die Partie nicht (die Sandbox bleibt ohne Ziele
# spielbar). Bewusst ein Mix aus leicht/schwer und ueber alle Ebenen
# (Umwelt/Wirtschaft/Haushalt/Zustimmung), damit eine Partie eine Richtung
# bekommt, ohne den entspannten Charakter in eine Fail-State-Challenge zu
# kippen. `metric` ist ein Statistik-Key oder die Sonderwerte
# "budget"/"approval".
SAMPLE_SCENARIO_GOALS = [
    ScenarioGoal(
        key="klimaziel",
        description="CO2-Emissionen bis Legislaturende unter 95",
        metric="co2_emissions",
        operator="<",
        threshold=95.0,
    ),
    ScenarioGoal(
        key="arbeitsmarkt",
        description="Arbeitslosenquote bis Legislaturende unter 5,0%",
        metric="unemployment_rate",
        operator="<",
        threshold=5.0,
    ),
    ScenarioGoal(
        key="solide_finanzen",
        description="Haushalt am Ende ueber 900",
        metric="budget",
        operator=">",
        threshold=900.0,
    ),
    ScenarioGoal(
        key="rueckhalt",
        description="Zustimmung am Ende ueber 60 (komfortable Wiederwahl)",
        metric="approval",
        operator=">",
        threshold=60.0,
    ),
]

SAMPLE_OPPOSITION_CAMPAIGNS = [
    OppositionCampaign(
        key="arbeitsmarkt_kritik",
        name="Kritik: Arbeitsmarktversprechungen nicht erfüllt",
        capital_cost=2.0,
        satisfaction_deltas={
            "Arbeitnehmer": 8.0,
            "Umweltbewusste Wähler": 3.0,
            "Junge Familien": 2.0,
        },
        description="Attacke gegen Regierungs-Arbeitsmarktpolitik; wirkt stark bei Arbeitern",
    ),
    OppositionCampaign(
        key="sozialversprechen_kampagne",
        name="Sozialversprechen: Gerechtige Verteilung",
        capital_cost=2.5,
        satisfaction_deltas={
            "Arbeitnehmer": 5.0,
            "Junge Familien": 6.0,
            "Gerechtigkeitsbewusste": 4.0,
        },
        description="Gemäßigte Position; sichere, moderate Wähler-Gewinne",
    ),
    OppositionCampaign(
        key="umwelt_offensiv",
        name="Klimaoffensive: Radikale Ziele",
        capital_cost=3.0,
        satisfaction_deltas={
            "Umweltbewusste Wähler": 12.0,
            "Junge Familien": 4.0,
            "Wirtschaft": -6.0,
        },
        description="Aggressive Grünen-Politik; polarisiert stark",
    ),
    OppositionCampaign(
        key="budget_kritik",
        name="Haushaltskritik: Zu viele Schulden",
        capital_cost=1.5,
        satisfaction_deltas={
            "Konservativ-Bürgerliche": 5.0,
            "Wirtschaft": 4.0,
        },
        description="Finanzkonservative Kritik; billig, aber begrenzte Reichweite",
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
