"""Policy-Definitionen mit Traegheitsmodell (nach Game-Director-Review, siehe
docs/architecture.md).

Jeder Effekt wirkt nicht sofort und einmalig, sondern ueber delay_turns
verzoegert und naehert sich danach exponentiell geglaettet ("inertia",
Vorbild Democracy 4) seinem Zielwert an -- er faellt NICHT nach einer festen
Rundenzahl wieder weg. sim/tools/balance_runner.py spielt automatisiert viele
Kombinationen durch, um dieses Verhalten zu tunen.

capital_cost ist die zweite Ressource neben one_time_cost/upkeep_cost (siehe
GameSession.political_capital) -- begrenzt, wie viele Reformen gleichzeitig
durchsetzbar sind.
"""
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON


class PolicyDefinition(SQLModel, table=True):
    __tablename__ = "policy_definition"

    key: str = Field(primary_key=True)  # z.B. "erneuerbare_foerderung"
    name: str
    description: str
    category: str  # z.B. "wirtschaft", "umwelt", "bildung"
    one_time_cost: float = Field(default=0.0)  # Budget-Kosten bei Einfuehrung
    upkeep_cost: float = Field(default=0.0)  # Kosten pro Runde, solange aktiv
    capital_cost: float = Field(default=0.0)  # Political-Capital-Kosten bei Einfuehrung/Repeal

    # Democracy-4-Vorbild: echte, laufende Einnahme (z.B. eine Steuer-Policy)
    # statt eines unsichtbaren Pauschal-Zuschusses -- siehe landtag_sim.
    # models.Policy.income_per_turn und engine.py::advance_turn.
    income_per_turn: float = Field(default=0.0)

    # Liste von Effekt-Objekten als JSON, z.B.:
    # [{"statistic_key": "unemployment_rate", "magnitude": -0.3,
    #   "delay_turns": 2, "inertia": 4}]
    # WICHTIG (Game-Director-Review): jede Policy sollte mindestens einen
    # negativen Effekt haben -- reine Positiv-Policies ohne Zielkonflikt
    # untergraben die Kernspannung des Genres.
    effects: list[dict] = Field(default_factory=list, sa_column=Column(JSON))

    # P1-Punkt "Policy-Pfade/Voraussetzungen" (docs/game-design-roadmap.md):
    # Policy-Keys, die bereits aktiv sein muessen, bevor diese Policy
    # eingefuehrt werden kann. Wird von sim/landtag_sim/engine.py geprueft
    # (UnmetPrerequisiteError), nicht hier -- diese Tabelle ist reine
    # Datenhaltung.
    requires: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class EnactedPolicy(SQLModel, table=True):
    __tablename__ = "enacted_policy"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="game_session.id", index=True)
    policy_key: str = Field(foreign_key="policy_definition.key")
    enacted_turn: int

    # Ersetzt das fruehere `active: bool` (siehe mistakes.md/CLAUDE.md,
    # Policy-Repeal-Recherche): eine zurueckgezogene Policy wird nicht
    # geloescht/deaktiviert, sondern behaelt die Runde ihres Repeals, damit
    # ihre Wirkung weiter abklingen kann (siehe landtag_sim.engine.py::
    # _effect_delta) -- ein reines Bool haette diese Information verworfen.
    # None = weiterhin aktiv.
    repealed_turn: int | None = Field(default=None)
