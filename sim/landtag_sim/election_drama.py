"""Wahlnacht-Dramaturgie ("Demokratie-Drama"-Pass, Fortsetzung 2026-09-14,
"mach weiter"): eine Wahl war bisher nur eine Prozentzahl neben "gewonnen"/
"verloren" -- der spannendste Moment des ganzen Spiels (Frostpunk/Suzerain-
Vorbild: die Wahlnacht IST die Story) hatte keine eigene Erzaehlstimme.
Dieses Modul liefert eine deterministische Schlagzeile passend zum
tatsaechlichen Ausgang: Erdrutsch, Zitterpartie oder normaler Abstand --
jeweils fuer Sieg und Niederlage.

Bewusst KEIN LLM/NLP (Projekt-Constraint): deterministische Textbausteine +
crc32-Seed-Auswahl, exakt dieselbe Technik wie opposition_voices.py/
citizen_voices.py.
"""
from __future__ import annotations

import zlib

# Abstand in Prozentpunkten, ab dem eine Wahl als "Erdrutsch" (sehr klar)
# bzw. als "Zitterpartie" (sehr knapp) gilt. Mit Rivalen ist das der Abstand
# zwischen Platz 1 und Platz 2 der Rangliste; ohne Rivalen der Abstand
# zwischen Zustimmung und der 50%-Schwelle.
LANDSLIDE_MARGIN = 18.0
CLOSE_MARGIN = 3.0

HEADLINES: dict[str, list[str]] = {
    "landslide_win": [
        "Erdrutschsieg: Der Landtag hat ein klares Mandat erteilt.",
        "Historisches Ergebnis -- die Konkurrenz wird regelrecht abgehaengt.",
        "Ein Triumph an der Wahlurne, den niemand mehr ernsthaft bestreitet.",
    ],
    "close_win": [
        "Zitterpartie bis zur letzten Stimme -- am Ende reicht es hauchduenn.",
        "Die Wahlnacht zieht sich bis in die Morgenstunden -- ein knapper, aber gueltiger Sieg.",
        "Nur eine Handvoll Stimmen entscheidet die Nacht -- diesmal auf unserer Seite.",
    ],
    "normal_win": [
        "Ein solider Wahlsieg, der Planungssicherheit fuer die naechste Legislatur bringt.",
        "Der Auftrag ist erneuert -- deutlich, aber ohne Euphorie.",
        "Die Waehlerschaft bestaetigt den eingeschlagenen Kurs.",
    ],
    "landslide_loss": [
        "Historische Niederlage -- die Waehlerschaft erteilt eine klare Absage.",
        "Ein Debakel an der Wahlurne, das lange nachwirken wird.",
        "So deutlich hat lange keine Regierung mehr verloren.",
    ],
    "close_loss": [
        "Eine bittere Zitterpartie -- am Ende fehlen nur wenige Stimmen zum Verbleib.",
        "So nah dran und doch verloren -- die Wahlnacht endet in Enttaeuschung.",
        "Ein hauchduenner Ruckschlag, der auch anders haette ausgehen koennen.",
    ],
    "normal_loss": [
        "Ein klarer Denkzettel der Waehlerschaft fuer die vergangene Legislatur.",
        "Die Opposition uebernimmt -- die Botschaft der Waehler war eindeutig.",
        "Ein spuerbarer Rueckschlag, der Konsequenzen erwarten laesst.",
    ],
}


def _standings_margin(standings: list[tuple[str, float]]) -> float:
    """Abstand zwischen Platz 1 und Platz 2 der Rangliste."""
    if len(standings) < 2:
        return 0.0
    sorted_values = sorted((pct for _, pct in standings), reverse=True)
    return abs(sorted_values[0] - sorted_values[1])


def generate_election_headline(
    won: bool, standings: list[tuple[str, float]], approval: float, threshold: float, turn: int
) -> str:
    """Deterministische Wahlnacht-Schlagzeile passend zum tatsaechlichen
    Abstand (mit Rivalen: Platz1-Platz2, sonst: Zustimmung-Schwelle)."""
    margin = _standings_margin(standings) if standings else abs(approval - threshold)

    if margin >= LANDSLIDE_MARGIN:
        category = "landslide_win" if won else "landslide_loss"
    elif margin <= CLOSE_MARGIN:
        category = "close_win" if won else "close_loss"
    else:
        category = "normal_win" if won else "normal_loss"

    pool = HEADLINES[category]
    index = zlib.crc32(f"election:{turn}".encode("utf-8")) % len(pool)
    return pool[index]
