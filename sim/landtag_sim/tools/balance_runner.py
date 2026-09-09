"""Headless Balance-Runner.

Zweck: das Traegheitsmodell (verzoegerte, ueber Zeit verteilte Policy-
Effekte) laesst sich nicht sinnvoll von Hand durchklicken-testen. Dieses
Skript spielt automatisiert alle Kombinationen der Beispiel-Policies ueber
N Runden durch und meldet auffaellige Szenarien (Budget-Kollaps, komplett
eingefrorene oder explodierende Zufriedenheit, verlorene Wahlen).

P1-Ausbaustufe: Policy-Voraussetzungen (Policy.requires) koennen eine
Kombination unmachbar machen, ohne dass Political Capital das Problem ist --
wird wie InsufficientCapitalError als eigenes Flag gemeldet. Ausgeloeste
Dilemmas werden automatisch mit der ERSTEN Option aufgeloest (deterministisch,
damit Runs reproduzierbar bleiben) -- fuer echtes Feintuning der
Dilemma-Balance reicht das nicht, aber es haelt den Runner lauffaehig, ohne
bei jedem Dilemma zu blockieren.

P2-Ausbaustufe (docs/game-design-roadmap.md, Punkt 10): zusaetzlich zu den
bestehenden Budget-/Zufriedenheits-Checks markiert der Runner jetzt Policies,
die in praktisch jedem erfolgreichen Szenario vorkommen ("Dominante-
Strategie-Check", siehe find_dominant_policies) -- Hinweis auf Comptons
"Illusory Choice": wenn eine Policy nie sinnvoll weggelassen wird, ist die
Entscheidung, sie zu waehlen, keine echte Entscheidung mehr.

Aufruf (aus sim/ heraus, nach `pip install -e .`):
    python -m landtag_sim.tools.balance_runner
    python -m landtag_sim.tools.balance_runner --turns 40 --csv out.csv
"""
from __future__ import annotations

import argparse
import csv
import itertools
import math
import sys

from landtag_sim.engine import advance_turn, resolve_dilemma
from landtag_sim.models import InsufficientCapitalError, UnmetPrerequisiteError
from landtag_sim.sample_data import (
    SAMPLE_DILEMMA_RULES,
    SAMPLE_EVENT_RULES,
    SAMPLE_POLICIES,
    build_initial_state,
)


def _advance_and_autoresolve(state, turns_new_keys):
    """advance_turn() plus: falls ein Dilemma ausgeloest wird, sofort mit der
    ersten Option aufloesen, damit der Runner nicht haengen bleibt. Gibt das
    finale TurnResult zurueck (nach etwaiger Aufloesung) sowie ob ein Dilemma
    dabei war."""
    result = advance_turn(state, SAMPLE_POLICIES, SAMPLE_EVENT_RULES, turns_new_keys, SAMPLE_DILEMMA_RULES)
    dilemma_fired = result.pending_dilemma is not None
    if dilemma_fired:
        rule = next(r for r in SAMPLE_DILEMMA_RULES if r.key == result.pending_dilemma.rule_key)
        chosen_option = rule.options[0].key
        result = resolve_dilemma(result.state, SAMPLE_DILEMMA_RULES, chosen_option)
    return result, dilemma_fired


def run_scenario(policy_keys: tuple[str, ...], turns: int) -> dict:
    state = build_initial_state()

    # Political-Capital- und Voraussetzungs-Pruefung passieren in advance_turn
    # selbst (bei Turn 0, wenn die Policies eingefuehrt werden). Schlaegt eine
    # davon fehl, ist die Kombination schlicht nicht spielbar -- kein Absturz,
    # sondern ein Flag.
    try:
        result, dilemma_fired = _advance_and_autoresolve(state, list(policy_keys))
    except InsufficientCapitalError as exc:
        return {
            "policies": "+".join(policy_keys) or "(keine)",
            "policy_keys": policy_keys,
            "min_budget": None,
            "end_satisfaction": None,
            "satisfaction_swing": None,
            "events_fired": 0,
            "dilemmas_fired": 0,
            "election": "-",
            "flags": f"NICHT_MACHBAR(Capital {exc.required}>{exc.available})",
        }
    except UnmetPrerequisiteError as exc:
        return {
            "policies": "+".join(policy_keys) or "(keine)",
            "policy_keys": policy_keys,
            "min_budget": None,
            "end_satisfaction": None,
            "satisfaction_swing": None,
            "events_fired": 0,
            "dilemmas_fired": 0,
            "election": "-",
            "flags": f"NICHT_MACHBAR(Voraussetzung fehlt: {exc.missing_requirement})",
        }

    state = result.state
    min_budget = state.budget
    satisfaction_series: list[float] = [sum(g.satisfaction for g in state.voter_groups) / len(state.voter_groups)]
    events_fired = len(result.events)
    dilemmas_fired = 1 if dilemma_fired else 0
    election_outcomes: list[str] = []
    if result.election_result:
        election_outcomes.append("GEWONNEN" if result.election_result.won else "VERLOREN")

    for _ in range(turns - 1):
        result, dilemma_fired = _advance_and_autoresolve(state, [])
        state = result.state
        min_budget = min(min_budget, state.budget)
        avg_satisfaction = sum(g.satisfaction for g in state.voter_groups) / len(state.voter_groups)
        satisfaction_series.append(avg_satisfaction)
        events_fired += len(result.events)
        dilemmas_fired += 1 if dilemma_fired else 0
        if result.election_result:
            election_outcomes.append("GEWONNEN" if result.election_result.won else "VERLOREN")

    satisfaction_swing = max(satisfaction_series) - min(satisfaction_series) if satisfaction_series else 0.0
    flags = []
    if min_budget < 0:
        flags.append("BUDGET_NEGATIV")
    if satisfaction_swing < 0.5:
        flags.append("ZUFRIEDENHEIT_EINGEFROREN")  # Effekte zu schwach, um etwas zu bewirken
    if satisfaction_series and (satisfaction_series[-1] <= 1.0 or satisfaction_series[-1] >= 99.0):
        flags.append("ZUFRIEDENHEIT_AM_ANSCHLAG")  # Effekte zu stark, Clipping dominiert

    return {
        "policies": "+".join(policy_keys) or "(keine)",
        "policy_keys": policy_keys,
        "min_budget": round(min_budget, 1),
        "end_satisfaction": round(satisfaction_series[-1], 1) if satisfaction_series else None,
        "satisfaction_swing": round(satisfaction_swing, 1),
        "events_fired": events_fired,
        "dilemmas_fired": dilemmas_fired,
        "election": ",".join(election_outcomes) if election_outcomes else "-",
        "flags": ",".join(flags) if flags else "-",
    }


def all_policy_combinations() -> list[tuple[str, ...]]:
    """Nur Kombinationen, die ihre eigenen Voraussetzungen erfuellen --
    Kombinationen, die z.B. steuersenkung_mittelstand ohne bildungsoffensive
    enthalten, werden gar nicht erst generiert (spart nutzlose
    NICHT_MACHBAR-Zeilen; ein echter Voraussetzungs-Verstoss wird trotzdem
    ueber UnmetPrerequisiteError abgefangen, falls sich das mal aendert)."""
    keys = [p.key for p in SAMPLE_POLICIES]
    requires_by_key = {p.key: set(p.requires) for p in SAMPLE_POLICIES}
    combos: list[tuple[str, ...]] = [()]
    for r in range(1, len(keys) + 1):
        for combo in itertools.combinations(keys, r):
            combo_set = set(combo)
            if all(requires_by_key[k] <= combo_set for k in combo):
                combos.append(combo)
    return combos


def find_dominant_policies(
    rows: list[dict], policy_keys: list[str], top_fraction: float = 0.5, threshold: float = 0.9
) -> list[tuple[str, float]]:
    """P2-Punkt 'Dominante-Strategie-Check' (docs/game-design-roadmap.md,
    Punkt 10, nach Comptons "Illusory Choice"-Heuristik).

    'Erfolgreich' = spielbar (keine NICHT_MACHBAR-Flag) und nicht
    eingefroren (keine ZUFRIEDENHEIT_EINGEFROREN-Flag) -- eingefrorene
    Szenarien sagen nichts ueber Dominanz aus, ihre Policies wirken schlicht
    nicht. 'Top' = die nach End-Zufriedenheit sortierten oberen
    `top_fraction` dieser erfolgreichen Szenarien (Default: obere Haelfte).

    Kommt eine Policy in mehr als `threshold` (Default 90%) dieser
    Top-Szenarien vor, ist die Entscheidung fuer sie vermutlich keine echte
    Wahl mehr -- entweder ist die Policy zu stark, oder ihr fehlt eine
    gleichwertige Konkurrenz-Policy.

    Gibt (policy_key, anteil)-Paare zurueck, absteigend nach Anteil sortiert.
    """
    successful = [
        r
        for r in rows
        if "NICHT_MACHBAR" not in r["flags"]
        and "ZUFRIEDENHEIT_EINGEFROREN" not in r["flags"]
        and r["end_satisfaction"] is not None
    ]
    if not successful:
        return []
    successful.sort(key=lambda r: r["end_satisfaction"], reverse=True)
    cutoff = max(1, math.ceil(len(successful) * top_fraction))
    top_scenarios = successful[:cutoff]

    dominant = []
    for key in policy_keys:
        share = sum(1 for r in top_scenarios if key in r["policy_keys"]) / len(top_scenarios)
        if share > threshold:
            dominant.append((key, share))
    dominant.sort(key=lambda item: item[1], reverse=True)
    return dominant


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--turns", type=int, default=30, help="Anzahl simulierter Runden pro Szenario")
    parser.add_argument("--csv", type=str, default=None, help="Optional: Ergebnisse zusaetzlich als CSV schreiben")
    args = parser.parse_args()

    rows = [run_scenario(combo, args.turns) for combo in all_policy_combinations()]

    header = [
        "policies", "min_budget", "end_satisfaction", "satisfaction_swing",
        "events_fired", "dilemmas_fired", "election", "flags",
    ]
    col_width = {h: max(len(h), *(len(str(row[h])) for row in rows)) for h in header}
    print(" | ".join(h.ljust(col_width[h]) for h in header))
    print("-+-".join("-" * col_width[h] for h in header))
    for row in rows:
        print(" | ".join(str(row[h]).ljust(col_width[h]) for h in header))

    flagged = [r for r in rows if r["flags"] != "-"]
    print(f"\n{len(flagged)}/{len(rows)} Szenarien mit Auffaelligkeiten markiert.")

    dominant = find_dominant_policies(rows, [p.key for p in SAMPLE_POLICIES])
    if dominant:
        print("\nVermutlich dominante Policies (>90% der Top-Szenarien nach Zufriedenheit, siehe Compton 'Illusory Choice'):")
        for key, share in dominant:
            print(f"  - {key}: {share * 100:.0f}%")
    else:
        print("\nKeine vermutlich dominante Policy gefunden.")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            # extrasaction="ignore": rows tragen seit dem P2-Dominante-
            # Strategie-Check zusaetzlich das interne "policy_keys"-Tupel
            # (fuer find_dominant_policies), das nicht in die CSV soll.
            writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV geschrieben nach {args.csv}")


if __name__ == "__main__":
    sys.exit(main())
