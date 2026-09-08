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


def ensure_niedersachsen(db: Session) -> AdminUnit:
    existing = db.exec(select(AdminUnit).where(AdminUnit.external_code == NIEDERSACHSEN_CODE)).first()
    if existing:
        return existing
    unit = AdminUnit(name="Niedersachsen", level=AdminLevel.REGION, external_code=NIEDERSACHSEN_CODE)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def ensure_policy_catalog(db: Session) -> None:
    for policy in SAMPLE_POLICIES:
        if db.get(PolicyDefinition, policy.key):
            continue
        db.add(
            PolicyDefinition(
                key=policy.key,
                name=policy.name,
                description=policy.name,
                category="allgemein",
                one_time_cost=policy.one_time_cost,
                upkeep_cost=policy.upkeep_cost,
                capital_cost=policy.capital_cost,
                effects=[vars(e) for e in policy.effects],
                requires=list(policy.requires),
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
