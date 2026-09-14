"""Buergerstimmen ("Demokratie-Drama"-Pass, Fortsetzung 2026-09-13, "mach es
noch lebendiger"): so wie opposition_voices.py den Rivalen-Parteien ein
Gesicht gibt, gibt dieses Modul den Waehlergruppen selbst eine Stimme -- bis
hierhin waren sie im "Waehlergruppen"-Panel nur ein Name mit einer Zahl. Pro
Runde spricht hoechstens EINE Gruppe, und nur wenn ihre Zufriedenheit gerade
besonders extrem ist (sehr niedrig ODER sehr hoch) -- die dramatischste
Stimmung der Runde bekommt das Wort, ruhige Mittelwerte bleiben stumm.

Bewusst KEIN LLM/NLP (Projekt-Constraint, siehe CLAUDE.md/README.md):
deterministische Textbausteine + crc32-Seed-Auswahl, exakt dieselbe Technik
wie opposition_voices.py/vignettes.py.
"""
from __future__ import annotations

import zlib

# Ab welcher Zufriedenheit eine Gruppe als "empoert" (negativ) bzw.
# "begeistert" (positiv) gilt und damit ueberhaupt zu Wort kommt. Bewusst mit
# Luft zur Mitte (50) -- nicht jede kleine Randbewegung soll ein Zitat
# ausloesen, sonst nutzt sich der Effekt ab (analog opposition_voices.py
# REACTION_THRESHOLD).
NEGATIVE_THRESHOLD = 32.0
POSITIVE_THRESHOLD = 72.0


def _dominant_category(group) -> str:
    """Welches Thema dieser Gruppe am wichtigsten ist -- dasselbe
    weight_*-Feld, das auch engine.py::_ideology_modifier auswertet."""
    weights = {
        "economy": group.weight_economy,
        "social": group.weight_social,
        "environment": group.weight_environment,
    }
    return max(weights, key=weights.get)


QUOTES: dict[str, dict[str, list[str]]] = {
    "negative": {
        "economy": [
            "Die Preise steigen, aber mein Lohn nicht -- so kann das nicht weitergehen.",
            "Von der Wirtschaftspolitik dieser Regierung sehe ich in meinem Portemonnaie nichts.",
            "Wer soll das noch bezahlen? Wir jedenfalls nicht mehr lange.",
        ],
        "social": [
            "Auf uns wird einfach vergessen -- so fuehlt sich das jedenfalls an.",
            "Die Versprechen waren gross, uebrig geblieben ist wenig.",
            "Wenn es eng wird, sind wir die Ersten, die es spueren.",
        ],
        "environment": [
            "Diese Regierung nimmt die Klimakrise nicht ernst genug.",
            "Wir hinterlassen unseren Kindern ein Land in schlechterem Zustand.",
            "Auf Sonntagsreden folgen zu selten echte Taten.",
        ],
    },
    "positive": {
        "economy": [
            "Endlich merkt man, dass diese Regierung etwas fuer uns unternimmt.",
            "Es geht bergauf -- das spueren wir im Alltag.",
            "So macht Wirtschaftspolitik wieder Hoffnung.",
        ],
        "social": [
            "Zum ersten Mal seit Langem fuehle ich mich gesehen.",
            "Das ist genau die Politik, die wir uns gewuenscht haben.",
            "Endlich zieht jemand mit uns an einem Strang.",
        ],
        "environment": [
            "Es tut sich wirklich etwas -- das macht Mut fuer die Zukunft.",
            "Endlich eine Regierung, die die Umwelt ernst nimmt.",
            "So stelle ich mir verantwortungsvolle Politik vor.",
        ],
    },
}


def _sentiment_and_extremity(group) -> tuple[str, float] | None:
    """None, wenn die Gruppe (noch) zu neutral ist, um zu Wort zu kommen.
    Sonst (sentiment, Abstand-zur-Schwelle) -- groesserer Abstand = dramatischer,
    entscheidet bei mehreren gleichzeitig extremen Gruppen, wer gewinnt."""
    if group.satisfaction <= NEGATIVE_THRESHOLD:
        return "negative", NEGATIVE_THRESHOLD - group.satisfaction
    if group.satisfaction >= POSITIVE_THRESHOLD:
        return "positive", group.satisfaction - POSITIVE_THRESHOLD
    return None


def pick_quote(sentiment: str, category: str, seed_key: str) -> str | None:
    """Deterministische Auswahl wie opposition_voices.py::pick_quote --
    dieselbe Gruppe zitiert in unterschiedlichen Runden unterschiedliche
    Saetze, aber reproduzierbar (kein `random`)."""
    pool = QUOTES.get(sentiment, {}).get(category)
    if not pool:
        return None
    index = zlib.crc32(seed_key.encode("utf-8")) % len(pool)
    return pool[index]


def generate_citizen_voice(voter_groups: list, turn: int) -> str | None:
    """Waehlt die Waehlergruppe mit der EXTREMSTEN Zufriedenheit dieser Runde
    (am weitesten unter/ueber ihrer jeweiligen Schwelle) und liefert ein
    formatiertes Zitat, oder None, wenn keine Gruppe extrem genug ist (ruhige
    Runde -- kein Zitat ist besser als ein erzwungenes)."""
    most_extreme: tuple[float, object, str] | None = None
    for group in voter_groups:
        result = _sentiment_and_extremity(group)
        if result is None:
            continue
        sentiment, extremity = result
        if most_extreme is None or extremity > most_extreme[0]:
            most_extreme = (extremity, group, sentiment)

    if most_extreme is None:
        return None

    _, group, sentiment = most_extreme
    category = _dominant_category(group)
    quote = pick_quote(sentiment, category, seed_key=f"{group.name}:{turn}")
    if not quote:
        return None
    return f'„{quote}“ — eine Stimme aus der Gruppe „{group.name}“'
