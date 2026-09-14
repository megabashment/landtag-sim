"""Oppositionsstimmen ("Demokratie-Drama"-Pass, Nutzer-Feedback 2026-09-13:
"das Spiel ist langweilig, der Punkt einer Demokratie-Sim kommt schwer
rueber"): Rivalen-Parteien waren bisher nur Balken in der Sonntagsfrage,
ohne Gesicht oder Stimme. Dieses Modul gibt der Opposition pro Runde EIN
Zitat ihres Fraktionsvorsitzenden, wenn die Statistik-Entwicklung dieser
Runde "ihr" Thema (Ideologie-Achse) verschlechtert hat -- macht sichtbar,
dass da jemand aufmerksam zuschaut und dich angreift, nicht nur ein Balken,
der sich bewegt.

Bewusst KEIN LLM/NLP (Projekt-Constraint, siehe CLAUDE.md/README.md):
deterministische Textbausteine + crc32-Seed-Auswahl, exakt dieselbe Technik
wie vignettes.py -- nur auf Zitat-Ebene statt angehaengter Halbsaetze.
"""
from __future__ import annotations

import zlib

# Ideologie-Achse -> Statistik-Kategorie (siehe engine.py::_STAT_CATEGORY):
# green sorgt sich um Umwelt, red um Soziales, blue um Wirtschaft -- exakt
# dieselbe Zuordnung wie RivalParty.ideology in _update_rival_approval.
IDEOLOGY_TO_CATEGORY = {"green": "environment", "red": "social", "blue": "economy"}

# Ab welcher (gerichteten, waehlerwirksamen) Verschlechterung einer Kategorie
# IN EINER EINZIGEN RUNDE eine Partei reagiert. Negativ, weil "directed"
# Deltas positiv=besser/negativ=schlechter fuer Waehler bedeuten (siehe
# engine.py::_build_term_summary, dieselbe Konvention). Kalibriert gegen
# typische Einzelrunden-Ausschlaege der SAMPLE_POLICIES/-EVENTS (nicht jede
# kleine Schwankung soll eine Attacke ausloesen, sonst nutzt sich der Effekt
# ab -- siehe test_opposition_voices.py fuer die Reichweiten-Pruefung).
REACTION_THRESHOLD = -0.3

QUOTES: dict[str, list[str]] = {
    "green": [
        "Das ist ein Schlag ins Gesicht jeder ernsthaften Klimapolitik.",
        "Wer so mit unserer Umwelt umgeht, verspielt die Zukunft unserer Kinder.",
        "Diese Regierung opfert das Klima fuer kurzfristige Zahlen.",
        "Das ist Politik von gestern -- die Erde kann nicht warten.",
    ],
    "red": [
        "Das trifft wieder die Falschen -- die kleinen Leute zahlen drauf.",
        "Von sozialer Gerechtigkeit ist hier nichts zu spueren.",
        "Diese Politik spaltet unser Land weiter.",
        "Wer so regiert, hat den Kontakt zu den Buergern verloren.",
    ],
    "blue": [
        "Das schadet dem Wirtschaftsstandort nachhaltig.",
        "Wer so wirtschaftet, vertreibt Investitionen aus dem Land.",
        "Ein weiterer Beweis wirtschaftlicher Ahnungslosigkeit dieser Regierung.",
        "So verspielt man den Wohlstand von morgen.",
    ],
}


def pick_quote(ideology: str, seed_key: str) -> str | None:
    """Deterministische Auswahl wie vignettes.py::pick_vignette -- dieselbe
    Partei greift in unterschiedlichen Runden mit unterschiedlichen Zitaten
    an, aber reproduzierbar (kein `random`)."""
    pool = QUOTES.get(ideology)
    if not pool:
        return None
    index = zlib.crc32(seed_key.encode("utf-8")) % len(pool)
    return pool[index]


def turn_category_changes(attributions, stat_category: dict[str, str], stat_direction) -> dict[str, float]:
    """Fasst die Attributionen EINER Runde zu gerichteten Kategorie-Deltas
    zusammen (positiv=besser fuer Waehler, negativ=schlechter) -- dieselbe
    Logik wie engine.py::_build_term_summary, nur pro Runde statt pro
    Legislaturperiode. `stat_direction` ist eine Funktion (Statistik-Key ->
    +1/-1), `stat_category` das _STAT_CATEGORY-Dict aus engine.py."""
    changes: dict[str, float] = {}
    for attribution in attributions:
        category = stat_category.get(attribution.statistic_key)
        if not category:
            continue
        directed = attribution.delta * stat_direction(attribution.statistic_key)
        changes[category] = changes.get(category, 0.0) + directed
    return changes


def generate_opposition_reaction(
    category_changes: dict[str, float], rival_parties: list, turn: int
) -> str | None:
    """Waehlt die Rivalen-Partei mit dem staerksten negativen Treffer auf
    IHRER EIGENEN Achse in dieser Runde und liefert ein formatiertes Zitat
    ("„Zitat" — Name (Partei)"), oder None, wenn keine Partei betroffen ist
    (ruhige Runde -- kein Zitat ist besser als ein erzwungenes). Bei
    mehreren betroffenen Parteien gewinnt die mit dem staerksten Ausschlag
    (gleiches Muster wie "nur das dringendste Event feuert")."""
    worst: tuple[float, object] | None = None
    for rival in rival_parties:
        category = IDEOLOGY_TO_CATEGORY.get(rival.ideology)
        if not category:
            continue
        delta = category_changes.get(category, 0.0)
        if delta >= REACTION_THRESHOLD:
            continue
        if worst is None or delta < worst[0]:
            worst = (delta, rival)

    if worst is None:
        return None

    _, rival = worst
    quote = pick_quote(rival.ideology, seed_key=f"{rival.name}:{turn}")
    if not quote:
        return None
    leader = rival.leader_name or rival.name
    return f'„{quote}“ — {leader} ({rival.name})'
