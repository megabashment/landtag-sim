"""B24 "Scenario Mode" (M6): vordefinierte Spielmodi mit Story und Preset-Startbedingungen."""
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON


class ScenarioDefinition(SQLModel, table=True):
    __tablename__ = "scenario_definition"

    key: str = Field(primary_key=True)  # z.B. "klimakrise_bewaeltigen"
    name: str  # "Klimakrise bewältigen" (UI-Label)
    description: str  # Story/Kontext

    # Optionale Overrides für Startstatistiken als JSON, z.B.:
    # {"co2_emissions": 90.0, "renewable_share": 25.0}
    starting_statistics_override: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # Optionale Szenario-spezifische Goals (Goal-Keys als Liste)
    # Falls leer, werden SAMPLE_SCENARIO_GOALS verwendet
    scenario_goal_keys: list[str] = Field(default_factory=list, sa_column=Column(JSON))
