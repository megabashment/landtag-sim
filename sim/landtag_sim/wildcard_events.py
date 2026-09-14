"""Wildcard-Ereignisse ("Demokratie-Drama"-Pass, Fortsetzung 2026-09-14,
"mach weiter"): die haeufigste Situation in einer ruhigen Legislatur-Phase
ist eine Runde, in der WEDER ein Event noch ein Dilemma noch ein Report
feuert -- "Keine besonderen Vorkommnisse." Genau diese komplett leeren
Runden fuehlen sich am meisten nach Tabellenkalkulation an, deshalb setzt
dieses Modul genau dort an: eine seltene, rein textliche Farbmeldung OHNE
jede Statistik-Wirkung, ausserhalb des sorgfaeltig balancierten Dilemma-/
Event-Pools (die duerfen nicht verwaessert werden). Kein Balance-Risiko,
weil es schlicht keine Effekte gibt.

Bewusst KEIN LLM/NLP (Projekt-Constraint): deterministische Textbausteine +
crc32-Seed-Auswahl, exakt dieselbe Technik wie citizen_voices.py.
"""
from __future__ import annotations

import zlib

# Von 100 geprueften "leeren" Runden feuert im Schnitt WILDCARD_FIRE_PERCENT
# ein Wildcard -- bewusst selten, sonst nutzt sich der Ueberraschungseffekt
# ab (dieselbe Kalibrierungslogik wie EventRule.probability).
WILDCARD_FIRE_PERCENT = 15

WILDCARDS: list[str] = [
    "Ein Sommerinterview sorgt fuer ungewohnte Aufmerksamkeit -- ohne messbare Folgen, aber alle reden darueber.",
    "Ein Kabarettist macht sich im Abendprogramm ueber die Landesregierung lustig -- die Einschaltquote schnellt hoch.",
    "Ein Nachbar-Bundesland wirbt mit einem spoettischen Vergleichsplakat an der Landesgrenze.",
    "Ein Buerger uebergibt persoenlich einen handgeschriebenen Forderungskatalog vor dem Landtag -- die Presse ist begeistert.",
    "Ein virales Video zeigt eine Abgeordnete beim Eisessen waehrend einer Plenardebatte -- Internet-Sensation des Tages.",
    "Der Landtag debattiert ungewoehnlich lange und leidenschaftlich ueber die neue Kantinen-Speisekarte.",
    "Eine Journalistin stellt in der Pressekonferenz eine Frage, mit der niemand gerechnet hat.",
    "Eine Schulklasse besucht den Landtag und stellt ueberraschend kluge Fragen an die Ministerbank.",
    "Ein technischer Defekt an der Abstimmungsanlage sorgt fuer zehn Minuten Chaos im Plenarsaal -- am Ende nur zum Schmunzeln.",
    "Ein Boulevardblatt kuert die Landesregierung zur \"unauffaelligsten des Jahres\" -- gemeint ist das als Kompliment.",
]


def maybe_generate_wildcard(turn: int) -> str | None:
    """None in den meisten Runden (siehe WILDCARD_FIRE_PERCENT); der
    Aufrufer entscheidet, wann diese Funktion ueberhaupt geprueft wird
    (siehe engine.py: nur in Runden ohne Event/Dilemma/Report)."""
    roll = zlib.crc32(f"wildcard-roll:{turn}".encode("utf-8")) % 100
    if roll >= WILDCARD_FIRE_PERCENT:
        return None
    index = zlib.crc32(f"wildcard-pick:{turn}".encode("utf-8")) % len(WILDCARDS)
    return WILDCARDS[index]
