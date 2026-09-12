"""Einmalige Seed-Daten: Niedersachsen als AdminUnit, Beispiel-Policies/Events.

Nutzt bewusst dieselben Beispieldaten wie der Balance-Runner
(landtag_sim.sample_data), damit Backend-Verhalten und Balance-Tests nicht
auseinanderlaufen. Sobald data/sources/ echte LSN-Daten liefert, ersetzt ein
richtiges Import-Skript (siehe data/README.md) diese Funktion.
"""
from dataclasses import asdict

from sqlmodel import Session, select

from app.models import AdminLevel, AdminUnit, DilemmaDefinition, EventDefinition, PolicyDefinition, StatisticDefinition
from landtag_sim.sample_data import (
    SAMPLE_BUNDESLAENDER,
    SAMPLE_DILEMMA_RULES,
    SAMPLE_EVENT_RULES,
    SAMPLE_POLICIES,
    STARTING_STATISTICS,
)

NIEDERSACHSEN_CODE = "DE-NI"

# label, unit, category pro Statistik-Key aus landtag_sim.sample_data.STARTING_STATISTICS.
# Muss synchron gehalten werden mit sim/landtag_sim/engine.py::_STAT_CATEGORY/_STAT_DIRECTION,
# sonst fehlt einer neuen Statistik entweder hier der DB-Eintrag oder dort die Gewichtung.
STATISTIC_META = {
    "unemployment_rate": ("Arbeitslosenquote", "%", "wirtschaft"),
    "gdp_growth": ("BIP-Wachstum", "%", "wirtschaft"),
    "education_spending": ("Bildungsausgaben", "Index 0-100", "soziales"),
    "healthcare_quality": ("Gesundheitsversorgung", "Index 0-100", "soziales"),
    "co2_emissions": ("CO2-Emissionen", "Index 0-100", "umwelt"),
    "renewable_share": ("Anteil erneuerbare Energien", "%", "umwelt"),
}

# Bugfix (2026-09-13, Nutzer-Feedback "Policy-Schalter nicht klickbar"):
# landtag_sim.models.Policy hat KEIN category-Feld -- ensure_policy_catalog()
# schrieb bisher fuer JEDE Policy hart "allgemein" in die DB. Frontend
# (App.jsx) filtert die Policy-Karten aber nach genau drei Werten:
# "economy" | "social" | "environment" (siehe .policies-grid-Rendering). Da
# "allgemein" gegen keinen davon matcht, war JEDE Kategorie-Box im Policy-
# Katalog permanent leer -- keine einzige Policy war jemals anwaehlbar. Diese
# Zuordnung ist analog zu STATISTIC_META oben die kanonische Quelle (nicht im
# sim-Package, weil "Kategorie" reine Anzeige-Metadaten sind, siehe dortiger
# Kommentar an Policy.description). Kategorie je nach dominantem Effekt
# vergeben, konsistent mit engine.py::_STAT_CATEGORY (unemployment_rate/
# gdp_growth -> economy, education/healthcare -> social, co2/renewable ->
# environment).
POLICY_CATEGORY = {
    "erneuerbare_foerderung": "environment",
    "bildungsoffensive": "social",
    "steuersenkung_mittelstand": "economy",
    "gesundheitsreform": "social",
    "elektronische_krankenschreibung": "social",
    "telemedizin_foerderung": "social",
    "digitale_patientenakte": "social",
    "solar_dachanlagen": "environment",
    "windkraft_kleinanlagen": "environment",
    "vermoegensteuer": "economy",
    "digitalpakt_schulen": "social",
    "gruener_wasserstoff": "environment",
    "arbeitsmarkt_sofortprogramm": "economy",
}


def ensure_niedersachsen(db: Session) -> AdminUnit:
    existing = db.exec(select(AdminUnit).where(AdminUnit.external_code == NIEDERSACHSEN_CODE)).first()
    if existing:
        return existing
    unit = AdminUnit(name="Niedersachsen", level=AdminLevel.REGION, external_code=NIEDERSACHSEN_CODE)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def ensure_bundesland(db: Session, bundesland_key: str) -> AdminUnit:
    """B27 "Bundes-Skalierung" (M7_SPRINT_PLAN.md): analog zu
    ensure_niedersachsen(), aber generisch fuer jedes SAMPLE_BUNDESLAENDER-
    Bundesland. `ensure_niedersachsen()` bleibt als eigene Funktion bestehen
    (viele bestehende Callsites), ist aber inhaltlich identisch mit
    `ensure_bundesland(db, "niedersachsen")` -- beide finden/erzeugen
    dieselbe AdminUnit-Zeile ueber denselben external_code."""
    bundesland = next((b for b in SAMPLE_BUNDESLAENDER if b.key == bundesland_key), None)
    if not bundesland:
        raise ValueError(f"Unbekanntes Bundesland: {bundesland_key}")

    existing = db.exec(select(AdminUnit).where(AdminUnit.external_code == bundesland.external_code)).first()
    if existing:
        return existing
    unit = AdminUnit(name=bundesland.name, level=AdminLevel.REGION, external_code=bundesland.external_code)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def ensure_policy_catalog(db: Session) -> None:
    for policy in SAMPLE_POLICIES:
        category = POLICY_CATEGORY.get(policy.key, "economy")
        existing = db.get(PolicyDefinition, policy.key)
        if existing:
            # Selbstheilend fuer bereits laufende DBs: die alte "allgemein"-
            # Kategorie (siehe Bugfix-Kommentar bei POLICY_CATEGORY) muss
            # HIER nachgezogen werden, sonst bleibt eine schon existierende
            # PolicyDefinition-Zeile dauerhaft falsch (create_all migriert
            # keine bestehenden Zeilen, siehe mistakes.md Postgres-Owner-Fix).
            if existing.category != category:
                existing.category = category
                db.add(existing)
            continue
        db.add(
            PolicyDefinition(
                key=policy.key,
                name=policy.name,
                description=policy.description or policy.name,
                category=category,
                one_time_cost=policy.one_time_cost,
                upkeep_cost=policy.upkeep_cost,
                capital_cost=policy.capital_cost,
                income_per_turn=policy.income_per_turn,
                effects=[vars(e) for e in policy.effects],
                requires=list(policy.requires),
                unlock_conditions=[vars(c) for c in policy.unlock_conditions],  # B7
            )
        )
    db.commit()


def ensure_event_catalog(db: Session) -> None:
    for rule in SAMPLE_EVENT_RULES:
        if db.get(EventDefinition, rule.key):
            continue
        db.add(
            EventDefinition(
                key=rule.key,
                trigger_condition={
                    "statistic_key": rule.statistic_key,
                    "operator": rule.operator,
                    "value": rule.threshold,
                    # B3 (BACKLOG.md): Wahrscheinlichkeit pro Runde bei erfuellter
                    # Schwelle. Im trigger_condition-JSON abgelegt statt als eigene
                    # Spalte -- keine Schema-Migration noetig, sim_bridge liest sie
                    # mit cond.get("probability", 1.0).
                    "probability": rule.probability,
                },
                template_text=rule.template_text,
                effects=[vars(e) for e in rule.effects],
                cooldown_turns=rule.cooldown_turns,
            )
        )
    db.commit()


def ensure_dilemma_catalog(db: Session) -> None:
    for rule in SAMPLE_DILEMMA_RULES:
        if db.get(DilemmaDefinition, rule.key):
            continue
        db.add(
            DilemmaDefinition(
                key=rule.key,
                trigger_condition={
                    "statistic_key": rule.statistic_key,
                    "operator": rule.operator,
                    "value": rule.threshold,
                    "probability": rule.probability,  # B3, siehe ensure_event_catalog
                },
                prompt_text=rule.prompt_text,
                options=[asdict(option) for option in rule.options],
                cooldown_turns=rule.cooldown_turns,
            )
        )
    db.commit()


def ensure_statistic_catalog(db: Session) -> None:
    for key in STARTING_STATISTICS:
        if db.get(StatisticDefinition, key):
            continue
        label, unit, category = STATISTIC_META.get(key, (key, "", "allgemein"))
        db.add(StatisticDefinition(key=key, label=label, unit=unit, category=category))
    db.commit()


def run_all_seeds(db: Session) -> None:
    ensure_niedersachsen(db)
    ensure_statistic_catalog(db)
    ensure_policy_catalog(db)
    ensure_event_catalog(db)
    ensure_dilemma_catalog(db)

    from app.sim_bridge import seed_scenarios

    seed_scenarios(db)
