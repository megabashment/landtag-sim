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

B6-Ausbaustufe (BACKLOG.md, L4/F6): Trigger-Telemetrie. Positech balanciert
Democracy 4s ~100 Dilemmas datengetrieben nach (Ziel ~1% Trigger-Anteil je
Dilemma; real triggern einige 20x, andere nie). Wir haben keine echte
Telemetrie, koennen das aber im Kleinen nachbilden: der Runner zaehlt ueber
alle Szenarien x N Seeds, wie oft jede Event-/Dilemma-/Situation-Regel
organisch ausloest, und meldet "nie ausgeloest" bzw. ">5x Erwartungswert"
(siehe collect_trigger_counts / classify_triggers). Zweck: MESSEN, was
ueberhaupt triggert, BEVOR mehr Content geschrieben wird.

Aufruf (aus sim/ heraus, nach `pip install -e .`):
    python -m landtag_sim.tools.balance_runner
    python -m landtag_sim.tools.balance_runner --turns 40 --csv out.csv
    python -m landtag_sim.tools.balance_runner --seeds 10   # breitere Telemetrie
"""
from __future__ import annotations

import argparse
import csv
import itertools
import math
import random
import sys

from landtag_sim.engine import advance_turn, resolve_dilemma
from landtag_sim.models import InsufficientCapitalError, PolicyLockedError, UnmetPrerequisiteError
from landtag_sim.sample_data import (
    SAMPLE_DILEMMA_RULES,
    SAMPLE_EVENT_RULES,
    SAMPLE_POLICIES,
    SAMPLE_REPORT_RULES,
    SAMPLE_SITUATION_RULES,
    build_initial_state,
    jittered_starting_statistics,
)


def _advance_and_autoresolve(state, turns_new_keys):
    """advance_turn() plus: falls ein Dilemma ausgeloest wird, sofort mit der
    ersten Option aufloesen, damit der Runner nicht haengen bleibt. Gibt das
    finale TurnResult zurueck (nach etwaiger Aufloesung) sowie ob ein Dilemma
    dabei war."""
    result = advance_turn(
        state,
        SAMPLE_POLICIES,
        SAMPLE_EVENT_RULES,
        turns_new_keys,
        SAMPLE_DILEMMA_RULES,
        report_rules=SAMPLE_REPORT_RULES,
    )
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
    except PolicyLockedError as exc:
        # B7: die Kombination enthaelt eine zu Rundenbeginn noch gesperrte
        # Policy (unlock_conditions nicht erfuellt). Der Combo-Runner enact-et
        # in Runde 0 -- eine erst spaeter freischaltbare Policy ist hier also
        # schlicht nicht spielbar, kein Fehler.
        return {
            "policies": "+".join(policy_keys) or "(keine)",
            "policy_keys": policy_keys,
            "min_budget": None,
            "end_satisfaction": None,
            "satisfaction_swing": None,
            "events_fired": 0,
            "dilemmas_fired": 0,
            "election": "-",
            "flags": f"NICHT_MACHBAR(gesperrt: {exc.unmet_condition})",
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


def all_policy_combinations(policies: list | None = None) -> list[tuple[str, ...]]:
    """Nur Kombinationen, die ihre eigenen Voraussetzungen erfuellen --
    Kombinationen, die z.B. steuersenkung_mittelstand ohne bildungsoffensive
    enthalten, werden gar nicht erst generiert (spart nutzlose
    NICHT_MACHBAR-Zeilen; ein echter Voraussetzungs-Verstoss wird trotzdem
    ueber UnmetPrerequisiteError abgefangen, falls sich das mal aendert).

    B7: Policies mit `unlock_conditions` werden ausgelassen -- der Runner
    enact-et ausschliesslich in Runde 0, wo eine erst spaeter freischaltbare
    Policy zwangslaeufig gesperrt (NICHT_MACHBAR) waere. Sie in jede
    Kombination aufzunehmen wuerde die Ausgabe mit reinem gesperrt-Rauschen
    fluten, ohne je etwas zu testen. Ihre Balance deckt stattdessen ein
    gezielter Engine-Test ab (siehe sim/tests/test_engine.py, Abschnitt B7).
    Der NICHT_MACHBAR(gesperrt)-Zweig in run_scenario bleibt fuer direkte
    Aufrufe als Sicherheitsnetz bestehen."""
    policies = policies if policies is not None else SAMPLE_POLICIES
    enactable = [p for p in policies if not p.unlock_conditions]
    keys = [p.key for p in enactable]
    requires_by_key = {p.key: set(p.requires) for p in enactable}
    combos: list[tuple[str, ...]] = [()]
    for r in range(1, len(keys) + 1):
        for combo in itertools.combinations(keys, r):
            combo_set = set(combo)
            if all(requires_by_key[k] <= combo_set for k in combo):
                combos.append(combo)
    return combos


# ---------------------------------------------------------------------------
# B6 "Dilemma-/Event-Trigger-Telemetrie" (BACKLOG.md, L4/F6)
# ---------------------------------------------------------------------------


def _seeded_initial_state(seed: int):
    """Startzustand mit reproduzierbar gejitterten Startwerten (ein Seed = ein
    Satz Startbedingungen). Bewusst gejittert statt der kanonischen
    STARTING_STATISTICS: verschiedene Seeds ueberschreiten die Trigger-
    Schwellen zu unterschiedlichen Zeitpunkten und decken so mehr Regeln ab.

    WICHTIG: Der B3-Wahrscheinlichkeits-Wuerfel (crc32 aus rule_key:turn, siehe
    events.py::passes_probability_gate) ist vom Seed UNABHAENGIG -- er faellt
    pro Runde gleich. Die Streuung ueber Seeds kommt allein aus den
    Startwerten, nicht aus dem Wuerfel; ein probability<1.0-Event wird dadurch
    nicht ueber Seeds gemittelt, sondern feuert (bei erfuellter Schwelle) in
    denselben Runden. Fuer die Telemetrie reicht das -- es geht um "triggert
    ueberhaupt / wie oft relativ", nicht um exakte Wahrscheinlichkeiten."""
    state = build_initial_state()
    state.statistics = jittered_starting_statistics(random.Random(seed))
    return state


def collect_trigger_counts(
    turns: int,
    seeds: int,
    *,
    policies: list | None = None,
    event_rules: list | None = None,
    dilemma_rules: list | None = None,
    situation_rules: list | None = None,
    report_rules: list | None = None,
    combos: list[tuple[str, ...]] | None = None,
) -> dict:
    """Spielt alle (voraussetzungs-gueltigen) Policy-Kombinationen ueber
    `seeds` gejitterte Startbedingungen und `turns` Runden durch und zaehlt,
    wie oft jede Event-/Dilemma-/Situation-Regel tatsaechlich ausloest.

    Anders als run_scenario (das bewusst OHNE Situations laeuft, um den
    Dominante-Strategie-Check nicht zu verschieben) uebergibt die Telemetrie
    den VOLLEN Regelsatz inkl. Situations -- sie will das komplette organische
    Trigger-Bild, nicht die isolierte Policy-Balance.

    Exakte Zaehlung ohne Heuristik: Event-Keys aus
    TurnResult.triggered_event_keys (B6-Feld), Dilemma-Keys aus
    pending_dilemma.rule_key, Situation-Aktivierungen aus dem Zuwachs von
    state.active_situations pro Runde. Gibt die drei Zaehler-Dicts plus die
    Gesamtzahl simulierter Runden zurueck."""
    policies = policies if policies is not None else SAMPLE_POLICIES
    event_rules = event_rules if event_rules is not None else SAMPLE_EVENT_RULES
    dilemma_rules = dilemma_rules if dilemma_rules is not None else SAMPLE_DILEMMA_RULES
    situation_rules = situation_rules if situation_rules is not None else SAMPLE_SITUATION_RULES
    report_rules = report_rules if report_rules is not None else SAMPLE_REPORT_RULES
    if combos is None:
        combos = all_policy_combinations(policies)

    event_counts = {r.key: 0 for r in event_rules}
    dilemma_counts = {r.key: 0 for r in dilemma_rules}
    situation_counts = {r.key: 0 for r in situation_rules}
    turns_simulated = 0

    def _advance(state, new_keys):
        nonlocal turns_simulated
        before_situations = {s.rule_key for s in state.active_situations}
        result = advance_turn(
            state,
            policies,
            event_rules,
            new_keys,
            dilemma_rules,
            situation_rules=situation_rules,
            report_rules=report_rules,
        )
        for key in result.triggered_event_keys:
            event_counts[key] += 1
        if result.pending_dilemma is not None:
            fired = result.pending_dilemma.rule_key
            dilemma_counts[fired] += 1
            rule = next(r for r in dilemma_rules if r.key == fired)
            result = resolve_dilemma(result.state, dilemma_rules, rule.options[0].key)
        after_situations = {s.rule_key for s in result.state.active_situations}
        for key in after_situations - before_situations:  # neu aktivierte Situations
            situation_counts[key] += 1
        turns_simulated += 1
        return result.state

    for seed in range(seeds):
        for combo in combos:
            state = _seeded_initial_state(seed)
            try:
                state = _advance(state, list(combo))  # Runde 0: Kombination einfuehren
            except (InsufficientCapitalError, UnmetPrerequisiteError, PolicyLockedError):
                continue  # nicht spielbare Kombination -- traegt keine Runden bei
            for _ in range(turns - 1):
                state = _advance(state, [])

    return {
        "event": event_counts,
        "dilemma": dilemma_counts,
        "situation": situation_counts,
        "turns_simulated": turns_simulated,
    }


def classify_triggers(
    counts_by_key: dict[str, int], turns_simulated: int, overrep_multiplier: float = 5.0
) -> tuple[list[dict], float]:
    """Reine Klassifikation (kein Simulieren -- leicht isoliert testbar).

    `expected` = Erwartungswert bei Gleichverteilung = Gesamt-Ausloesungen der
    Kategorie / Anzahl Regeln (Democracy-4-Heuristik: bei 100 Dilemmas ~1% je
    Regel). Eine Regel wird als NIE_AUSGELOEST markiert (count == 0) oder als
    UEBERREPRAESENTIERT (count > overrep_multiplier x expected). Gibt die
    Zeilen absteigend nach count (Ties nach Key) plus den Erwartungswert
    zurueck."""
    total = sum(counts_by_key.values())
    n = len(counts_by_key) or 1
    expected = total / n
    rows: list[dict] = []
    for key, count in sorted(counts_by_key.items(), key=lambda kv: (-kv[1], kv[0])):
        flag = "-"
        if count == 0:
            flag = "NIE_AUSGELOEST"
        elif expected > 0 and count > overrep_multiplier * expected:
            flag = "UEBERREPRAESENTIERT"
        rows.append(
            {
                "key": key,
                "count": count,
                "share": (count / turns_simulated) if turns_simulated else 0.0,
                "flag": flag,
            }
        )
    return rows, expected


def _print_trigger_telemetry(counts: dict) -> None:
    turns_simulated = counts["turns_simulated"]
    print(f"\n=== Trigger-Telemetrie ({turns_simulated} simulierte Runden) ===")
    for label, category in (("Events", "event"), ("Dilemmas", "dilemma"), ("Situations", "situation")):
        rows, expected = classify_triggers(counts[category], turns_simulated)
        print(f"\n{label} (Erwartungswert bei Gleichverteilung: {expected:.1f}x/Regel):")
        if not rows:
            print("  (keine Regeln)")
            continue
        for r in rows:
            marker = "" if r["flag"] == "-" else f"   <-- {r['flag']}"
            print(f"  {r['key']:<28} {r['count']:>6}x  ({r['share'] * 100:>5.1f}% der Runden){marker}")


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
    parser.add_argument(
        "--seeds",
        type=int,
        default=5,
        help="B6-Trigger-Telemetrie: Anzahl gejitterter Startbedingungen (mehr = breiteres Trigger-Bild)",
    )
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

    # B6: Trigger-Telemetrie ueber alle Kombinationen x Seeds (eigener,
    # vollstaendiger Lauf inkl. Situations -- siehe collect_trigger_counts).
    telemetry = collect_trigger_counts(args.turns, args.seeds)
    _print_trigger_telemetry(telemetry)

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
