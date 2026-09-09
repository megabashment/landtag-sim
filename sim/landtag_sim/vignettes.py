"""Namens-Vignetten (P2-Punkt, docs/game-design-roadmap.md): kurze,
wiederkehrende fiktive Stimmen, die an Event-/Dilemma-Meldungen angehaengt
werden. Macht abstrakte Statistik-Meldungen ("Arbeitslosenquote erreicht
9.2%") menschlich, ohne die in der Game-Director-Review bewusst
zurueckgestellte volle Buerger-Simulation zu brauchen -- reine
Text-Pool-Erweiterung, kein LLM/NLP.

Auswahl ist DETERMINISTISCH (kein random.choice): dieselbe Regel in
derselben Runde liefert immer dieselbe Vignette. Das haelt den
Balance-Runner reproduzierbar und macht Tests moeglich, die exakte Texte
pruefen wollen.
"""
from __future__ import annotations

import zlib

VIGNETTE_POOL: dict[str, list[str]] = {
    "economy": [
        "Schichtleiter Uwe aus Salzgitter: 'Die Zahlen sehen die da oben ja nicht auf dem Konto.'",
        "Baeckermeisterin Petra: 'Ob sich das fuer uns kleine Betriebe ueberhaupt lohnt?'",
    ],
    "social": [
        "Lehrerin Fatma aus Hannover: 'Endlich merkt man den Unterschied im Klassenzimmer.'",
        "Rentner Dieter: 'Ich hoffe, das hilft auch wirklich den Jungen.'",
    ],
    "environment": [
        "Landwirt Joerg aus der Lueneburger Heide: 'Wenn's dem Boden hilft, mach ich mit.'",
        "Schuelerin Lena bei Fridays for Future: 'Ein Anfang. Aber nur ein Anfang.'",
    ],
}


def pick_vignette(category: str, seed_key: str) -> str | None:
    """Waehlt deterministisch eine Vignette aus dem Pool der Kategorie.

    `seed_key` sollte etwas Rundenspezifisches enthalten (z.B.
    "<regel_key>:<runde>"), damit sich wiederholende Ausloesungen derselben
    Regel nicht IMMER dieselbe Vignette zeigen. zlib.crc32 statt des
    eingebauten hash(): der ist fuer Strings pro Prozess randomisiert
    (PYTHONHASHSEED) und waere damit nicht reproduzierbar zwischen Runs.
    """
    pool = VIGNETTE_POOL.get(category)
    if not pool:
        return None
    index = zlib.crc32(seed_key.encode("utf-8")) % len(pool)
    return pool[index]


def with_vignette(text: str, category: str, seed_key: str) -> str:
    vignette = pick_vignette(category, seed_key)
    if not vignette:
        return text
    return f"{text} {vignette}"
