# CLAUDE.md — Projektgedächtnis für Landtag-Sim

Diese Datei ist der Einstiegspunkt für jede neue Claude-Session an diesem
Projekt. Ziel: nicht bei null anfangen müssen. Ausführliche Herleitungen
stehen in `docs/architecture.md` (Game-Director-Review) und
`docs/game-design-roadmap.md` (Senior-Game-Designer-Review) — diese Datei
fasst nur zusammen, was für den nächsten Arbeitsschritt wichtig ist.

Siehe auch `mistakes.md` für bereits gefundene und behobene Bugs —
**vor größeren Refactors dort nachsehen**, damit dieselben Fehler nicht
zweimal gemacht werden.

## Quick Start

Die häufigsten Befehle (Docker Desktop vorausgesetzt):

```bash
# Backend-Tests
cd backend && python -m pytest tests/ -q

# Sim-Engine-Tests
cd ../sim && python -m pytest tests/ -q

# Frontend Build + Lint
cd ../frontend && npm run build && npm run lint

# Policy-Balance-Check (alle gültigen Kombinationen)
python -m landtag_sim.tools.balance_runner --turns 30

# Kompletter Stack (db + backend + frontend) für manuelles / Handy-Testen
docker compose up --build   # Frontend :5173, Backend :8000
```

Für vollständiges Setup, Handy-Testing im LAN und manuelle E2E-Tests → siehe
**Verifikations-Workflow** und `README.md` ("Vom Handy im lokalen Netz testen").

## Was ist das Projekt

Ein entspanntes Management-Spiel mit starker Anlehnung an die *Democracy*-
Reihe: Policies mit verzögerter Wirkung setzen, Wählergruppen
zufriedenstellen, Budget und Political Capital im Blick behalten, Wahl
gewinnen. MVP-Szenario: **Niedersachsen** (ein Bundesland), Skalierung auf
Nation-/EU-Ebene ist Meta-Ziel, **nicht** Teil des MVP.

Harte Constraints (vom Nutzer vorgegeben, nicht verhandelbar):
- Kein LLM/NLP für Text oder Events — reine Regex-Templates + regelbasierte
  Trigger.
- Sprites/Assets nur aus offen lizenzierten Quellen (nicht zwingend CC0).
- Simulation läuft serverseitig, Rendering client-/lokal.
- Repository ist öffentlich.

## Stack und Architektur

| Bereich | Entscheidung |
|---|---|
| Client | React (Vite), reines Rendering |
| Backend | FastAPI |
| Datenbank | PostgreSQL (von Anfang an, nicht SQLite) |
| Kommunikation | REST, rundenbasiert (kein WebSocket) |
| Sim-Engine | Eigenes Package `landtag_sim` (`sim/`), pip-installierbar (`pip install -e .`), **komplett DB-unabhängig** — reine Dataclasses und Funktionen |

Projektstruktur:

```
landtag-sim/
├── backend/app/
│   ├── models/        # AdminUnit, StatisticDefinition/-Value, VoterGroup, Faction, PolicyDefinition, EventDefinition, DilemmaDefinition, ActiveSituation, GameSession (Status/Role)
│   ├── api/routes_game.py   # /health, /sessions, /sessions/{id}/preview, /sessions/{id}/advance, /sessions/{id}/resolve-dilemma
│   └── sim_bridge.py   # Übersetzt DB <-> reine Sim-Engine (einziger Ort für diese Übersetzung)
├── sim/landtag_sim/
│   ├── engine.py        # Kern: advance_turn() / resolve_dilemma() — reine Funktionen
│   ├── models.py         # Dataclasses: Policy, PolicyEffect, UnlockCondition, VoterGroup, Faction, EventRule, DilemmaRule, DilemmaOption, PendingDilemma, SituationRule, ActiveSituation, ReportRule, ReportCondition, ScenarioGoal, GoalResult, SimState, TurnResult, EffectAttribution, ElectionResult, ElectionProjection, ElectionProjectionGroup, TermSummary
│   ├── events.py         # Regelbasierte Trigger-Auswertung (passiv, fester Effekt); B3: passes_probability_gate()
│   ├── dilemmas.py        # Regelbasierte Trigger-Auswertung mit echten Entscheidungsoptionen
│   ├── situations.py      # B2: Situations-Layer mit Hysterese (Aktivierungs- != Deaktivierungs-Schwelle)
│   ├── reports.py         # B4: narrative Presseschau-Meldungen (UND-Bedingungen, kein Sim-Effekt)
│   ├── templates.py      # Regex-basiertes Text-Rendering (kein LLM)
│   ├── vignettes.py       # P2: deterministische Namens-Vignetten (Text-Pool, zlib.crc32-Auswahl)
│   ├── sample_data.py    # SAMPLE_POLICIES, SAMPLE_EVENT_RULES, SAMPLE_DILEMMA_RULES, SAMPLE_SITUATION_RULES, SAMPLE_REPORT_RULES, SAMPLE_SCENARIO_GOALS, SAMPLE_VOTER_GROUPS, STARTING_STATISTICS, jittered_starting_statistics()
│   └── tools/balance_runner.py  # Headless Szenario-Tester über alle (voraussetzungs-gültigen) Policy-Kombinationen + Dominante-Strategie-Check + B6-Trigger-Telemetrie (--seeds)
├── frontend/src/App.jsx  # Einzelnes Dashboard, Policy-Katalog per GET /policies (api.listPolicies)
│   └── statIcons.js      # B14: game-icons.net-Pfade (CC BY 3.0) pro Statistik-Key, siehe CREDITS.md
├── data/                 # Datenquellen-Doku (Landesamt für Statistik Niedersachsen statt Weltbank/V-Dem, siehe data/README.md)
└── docs/                 # architecture.md (Game-Director-Review), game-design-roadmap.md (Senior-Game-Designer-Review, 10 gewichtete Vorschläge)
```

### Kernmechaniken

**Überblick** — Simulation in Schichten (detailliert unten):
- **Inertia & Ressourcen** — Exponentielle Effekt-Glättung, Political Capital, Budget
- **Policy-System** — Enact/repeal/decay, Voraussetzungen, dynamisches Unlock
- **Risiko & Entscheidungen** — Wahrscheinlichkeits-Events, Dilemmas mit Optionen
- **Wähler & Zufriedenheit** — Gewichtete Approval, Momentum, Wahlprognose mit Turnout
- **Zyklen & Bilanz** — Legislaturperioden, Term Summary, Szenario-Ziele

---

- **Inertia-Modell** (`engine.py::_effect_delta`): Policy-Effekte nähern
  sich ihrem Zielwert exponentiell geglättet an (`inertia`-Parameter,
  Vorbild Democracy 4), nicht linear in einem festen Zeitfenster. Sie
  verschwinden NICHT nach fester Rundenzahl, solange die Policy aktiv ist
  und Upkeep gezahlt wird.
- **Political Capital**: zweite Ressource neben Budget, begrenzt wie viele
  Reformen gleichzeitig durchsetzbar sind (`CAPITAL_PER_TURN = 3.0`,
  `CAPITAL_CAP = 10.0`). Wirft `InsufficientCapitalError`, wenn eine Auswahl
  mehr kostet als verfügbar — State wird dabei NICHT mutiert.
- **Budget-Grundeinnahme** (`BASE_BUDGET_INCOME_PER_TURN = 15.0`,
  Nach-P2-Nachschärfung): jede Runde bekommt das Budget diesen festen
  Betrag gutgeschrieben, unabhängig von Policies/Statistiken (vereinfachte
  Landeshaushalt-Basissteuereinnahme, kein echtes Steuersatz-System im
  MVP-Scope). Vorher hatte das Budget NUR Ausgaben und keine Einnahme —
  bei 3-4 gleichzeitig aktiven Policies blieb Budget trotzdem spürbar unter
  Druck. Siehe `mistakes.md` für die Herleitung.
- **Echte Einnahmen-Policies** (`Policy.income_per_turn`, Democracy-4-
  Recherche): zusätzlich zur pauschalen Grundeinnahme gibt es jetzt eine
  echte, vom Spieler gewählte Einnahmequelle — `vermoegensteuer`
  (`income_per_turn=20.0`). Democracy 4 modelliert Budget-Einnahmen nicht
  als unsichtbaren Zuschuss, sondern als Policy mit `MinIncome`/`MaxIncome`
  (siehe offizielle Modding-Doku); `income_per_turn` ist die MVP-taugliche
  Vereinfachung davon (kein Regler, aber ein echter, sichtbarer, per Repeal
  abschaltbarer Hebel statt einer Blackbox). Fließt in `advance_turn`
  genauso wie `upkeep_cost` — nur additiv statt subtraktiv — und stoppt
  sofort bei Repeal.
- **Policy-Repeal** (`EnactedPolicy.repealed_turn`, `advance_turn(...,
  newly_repealed_keys=...)`, Democracy-4-Recherche): eine Policy kann
  zurückgezogen werden, wirkt danach aber NICHT schlagartig verschwunden —
  ihre Effekte klingen symmetrisch zum Aufbau exponentiell ab (dieselbe
  `inertia`/Alpha-Rate rückwärts, siehe `engine.py::_effect_delta`), analog
  zu Democracy 4s gradueller Cancel-Animation. Upkeep UND `income_per_turn`
  stoppen dagegen sofort mit der Repeal-Runde. Repeal kostet ebenfalls
  `capital_cost` (Democracy 4 bepreist Einführung, Repeal und
  Regler-Anpassung separat — MVP vereinfacht auf zwei Fälle: Einführung und
  Repeal teilen sich `capital_cost`, da es noch keine Regler-Policies
  gibt). Drei neue Fehlerfälle: `PolicyAlreadyActiveError` (Doppel-Enact),
  `PolicyNotActiveError` (Repeal einer nie/nicht mehr aktiven Policy),
  `PolicyRequiredByActivePolicyError` (Repeal einer Policy, die eine andere,
  noch aktive Policy per `requires` voraussetzt). WICHTIG:
  `SimState.clone()` kopiert `active_policies` nur FLACH (gleiche
  `EnactedPolicy`-Instanzen) — Repeal ERSETZT den betroffenen Listeneintrag
  durch ein neues Objekt, mutiert nie in-place. Backend: `EnactedPolicy.
  active: bool` wurde zu `repealed_turn: int | None`, `sim_bridge.py::
  load_sim_state()` lädt bewusst ALLE Zeilen (nicht nur aktive), da der
  State bei jedem Request frisch aus der DB aufgebaut wird und eine
  zurückgezogene Policy ihr Abkling-Gedächtnis sonst verlieren würde. API:
  `repeal_policy_keys` auf `AdvanceTurnRequest`/`PreviewRequest`.
- **Jede Policy hat mindestens einen negativen Nebeneffekt** (Trade-off-
  Pflicht, siehe `test_every_sample_policy_has_at_least_one_negative_effect`)
  — reine Positiv-Policies waren der Hauptkritikpunkt der ersten Review.
- **Event-System**: regelbasierte Trigger (`EventRule`), bei mehreren
  gleichzeitig eligible Events feuert nur das mit der höchsten Severity pro
  Runde (kein Event-Spam).
- **Zustandsgekoppelte Risiko-Events** (B3, `EventRule.probability` /
  `DilemmaRule.probability`, Default `1.0`): eine Regel mit erfüllter
  Schwelle feuert zusätzlich nur mit dieser Wahrscheinlichkeit pro Runde.
  Der "Würfel" ist deterministisch (`events.py::passes_probability_gate`,
  `zlib.crc32(f"{rule_key}:{turn}")` normiert auf `[0,1)` — **kein
  `random`**, damit Balance-Runner/Tests reproduzierbar bleiben; `dilemmas.py`
  importiert dieselbe Funktion). Zweck: "Vorstufen"-Regeln mit erreichbarer
  Schwelle, die die Statistiken graduell Richtung einer sonst unerreichbaren
  Krisenschwelle drücken, ohne zu einem reinen Zufalls-Schock zu werden (L9).
  Startdatensatz: `konjunkturdelle` (`gdp_growth < 0.5`, `probability=0.4`)
  drückt `gdp_growth` weiter — macht `rezession` aus leicht negativer Lage
  und (via Situation `abwanderung`) `arbeitsmarktkrise` organisch erreichbar.
  Persistenz ohne Schema-Migration: `probability` steckt im
  `trigger_condition`-JSON (`seed.py`), `sim_bridge.py` liest
  `cond.get("probability", 1.0)`.
- **Narrative Konsequenz-Ebene / "Presseschau"** (B4, `sim/landtag_sim/
  reports.py`, `ReportRule`/`ReportCondition`): rein textliche
  Konsequenz-Meldungen ("Werksschliessung wegen deiner Wirtschaftspolitik"),
  die **keine** Sim-Statistik verändern (kein Effekt, keine Attribution,
  keine Zufriedenheitsreaktion). Eine Regel feuert, wenn **alle**
  `conditions` (UND) erfüllt sind, optionales `requires_policy`/
  `forbids_policy` passt und kein Cooldown läuft. `advance_turn` wertet sie
  in Abschnitt "2c" aus — **nur in Runden ohne Event und ohne Dilemma**
  (Frequenz-Management, L5) — und hängt höchstens **einen** Text an
  `TurnResult.reports` (mit Namens-Vignette, Kategorie aus `conditions[0].
  statistic_key`). Auswahl bei mehreren eligiblen Regeln: deterministisch
  nach `rule.key`. Startdatensatz: `SAMPLE_REPORT_RULES` (7 Regeln, 4
  policy-gekoppelt). Backend: `AdvanceTurnResponse.reports`;
  `sim_bridge.load_report_rules()` liefert die Regeln **ohne DB** (reiner
  statischer Content — bewusste Asymmetrie zu Policies/Events/Dilemmas).
  Frontend: eigenes "Presseschau"-Panel + Verlaufs-Zeilen; Fast-Forward
  stoppt auch bei einem Report.
- **Effekt-Attribution** (`EffectAttribution`): jeder Statistik-Delta trägt
  seine Quelle (Policy-Key oder `event:<key>`) — Backend/Frontend können so
  erklären, WARUM sich eine Zahl geändert hat.
- **Wahlmechanik**: `turns_until_election` zählt jede Runde runter
  (Zykluslänge 16). Bei 0 wird die nach `population_share` gewichtete
  Durchschnittszufriedenheit gegen `ELECTION_APPROVAL_THRESHOLD = 50.0`
  geprüft. Verloren → `SessionStatus.LOST`, Partie endet (`/advance` liefert
  danach HTTP 400). Gewonnen → Session bleibt `ACTIVE`, nächster Zyklus
  beginnt (Wiederwahl = Weiterspielen, kein Spielende).
- **Wahlprognose / Turnout-Apathie** (B5, `engine.py::project_election`):
  Vorausschau auf den Wahlausgang. `ElectionProjection.approval` ist
  **exakt** `_weighted_approval` — die Zahl, an der die echte Wahl hängt
  (keine Blackbox, L6). Zusätzlich `turnout_adjusted_approval`: legt ein
  Apathie-Modell an (`_estimated_turnout`, aus `satisfaction` +
  `satisfaction_momentum` **abgeleitet**, kein neues Feld — F4). Reduziert
  wird nur für "lauwarm UND abkühlend" (`satisfaction` in [30, 55] und
  `momentum < 0` → runter bis `TURNOUT_MIN = 0.6`); wütende Gegner (< 30)
  und Zufriedene (> 55) stimmen voll ab. **Die echte Wahl in `advance_turn`
  nutzt Turnout NICHT** (bewusst — kein Rebalancing nötig); die
  turnout-Zahl ist reine Frühwarnung. Backend liefert
  `SessionStateResponse.election_projection` nur bei `status == ACTIVE` und
  `turns_until_election <= 5` (`ELECTION_PROJECTION_WINDOW`). Frontend:
  "Wenn heute Wahl wäre"-Panel mit Zeile pro Gruppe (Zufriedenheit,
  Trendpfeil, Beteiligung%).
- **Effekt-Vorschau**: `POST /sessions/{id}/preview` simuliert `advance_turn`
  mit gewählten Policies, verwirft das Ergebnis (kein Persistieren). Liefert
  grobe Richtungs-/Größenklassen (schwach/mittel/stark) statt exakter
  Zahlen — bewusst vage wie Frostpunks Book of Laws.
- **Policy-Voraussetzungen** (`Policy.requires`): eine Policy kann erst
  eingeführt werden, wenn ihre Voraussetzungen bereits aktiv sind (oder in
  derselben Runde mitgewählt werden) — sonst `UnmetPrerequisiteError`.
  Beispiel: `steuersenkung_mittelstand` braucht `bildungsoffensive`.
- **Dynamische Policy-Freischaltung** (B7, `Policy.unlock_conditions:
  list[UnlockCondition]`): eine Policy wird erst einführbar, wenn **alle**
  ihre Statistik-Schwellen (UND) im aktuellen Zustand erfüllt sind — anders
  als `requires` (das eine andere aktive **Policy** verlangt) hängt das an
  einem **gesellschaftlichen Zustand**, den der Spieler über die Zeit
  herbeiführt. Engine erzwingt via `engine.py::_validate_unlocks` →
  `PolicyLockedError` (gegen die Statistiken **vor** der Runde, vor jeder
  Mutation). Geteilte Logik: `engine.py::policy_is_unlocked(policy,
  statistics)` (auch Backend/Frontend/Tests nutzen sie). Beispiele:
  `digitalpakt_schulen` (`education_spending > 50`), `gruener_wasserstoff`
  (`renewable_share > 42`), `arbeitsmarkt_sofortprogramm`
  (`unemployment_rate > 7`). Backend: `PolicyLockedError` → HTTP 400
  (`/advance`) bzw. `feasible=False` (`/preview`); `PolicyOut.
  unlock_conditions` wird ausgeliefert (nicht rausgefiltert), das Frontend
  graut gesperrte Policies aus ("Wird verfügbar, wenn …"). Balance-Runner:
  `all_policy_combinations` lässt unlock-gated Policies weg (nur
  turn-0-enactbare werden kombiniert).
- **Dilemma-Events**: wie Events regelbasiert ausgelöst (`dilemmas.py`,
  gleicher Trigger-/Cooldown-/Schweregrad-Mechanismus), aber mit echten
  Entscheidungsoptionen statt festem Effekt. Ein ausgelöstes Dilemma ist der
  "Headline"-Moment der Runde (unterdrückt ein gleichzeitig eligibles
  passives Event) und **pausiert** `advance_turn()` danach hart:
  jeder weitere Aufruf wirft `DilemmaPendingError`, bis
  `resolve_dilemma(state, dilemma_rules, option_key)` aufgerufen wurde.
  `resolve_dilemma()` zählt bewusst KEINE eigene Runde (Political
  Capital/Wahl-Countdown liefen schon in der auslösenden Runde). Backend-
  Endpunkt: `POST /sessions/{id}/resolve-dilemma`.
- **Namens-Vignetten** (`vignettes.py`): Event-Texte und Dilemma-Prompts
  bekommen eine kurze, deterministisch ausgewählte fiktive Stimme angehängt
  (Kategorie über `_STAT_CATEGORY[rule.statistic_key]`). `zlib.crc32` statt
  `random.choice`/`hash()` — Auswahl bleibt reproduzierbar zwischen Runs.
- **Zufriedenheits-Momentum** (`VoterGroup.satisfaction_momentum`,
  `engine.py::_apply_reaction`): die rohe Reaktion einer Runde wird per EMA
  (`SATISFACTION_MOMENTUM_ALPHA = 0.4`) geglättet, bevor sie auf
  `satisfaction` wirkt — ein einzelner großer Ausschlag klingt über mehrere
  Runden nach statt schlagartig zu wirken. Persistiert über
  `backend/app/models/voter_group.py` + `sim_bridge.py`.
- **Randomisierte Startbedingungen** (`sample_data.py::
  jittered_starting_statistics`): echte Sessions (`POST /sessions`) starten
  mit ±5% Streuung pro Statistik; Tests/Balance-Runner bleiben bei den
  unrandomisierten `STARTING_STATISTICS`.
- **Dominante-Strategie-Check** (`balance_runner.py::
  find_dominant_policies`): markiert Policies, die in >90% der
  nicht-eingefrorenen Top-Szenarien (nach End-Zufriedenheit) vorkommen.
  Fand ursprünglich `bildungsoffensive` bei 100% (siehe "Nach-P2-
  Nachschärfung" unten) — mit dem aktuellen 4-Policy-Katalog liefert der
  Runner "Keine vermutlich dominante Policy gefunden."
- **Trigger-Telemetrie** (B6, `balance_runner.py::collect_trigger_counts` /
  `classify_triggers`, CLI `--seeds N`): zählt über alle
  voraussetzungs-gültigen Policy-Kombinationen × N gejitterte
  Startbedingungen, wie oft jede Event-/Dilemma-/Situation-Regel **organisch**
  triggert, und markiert `NIE_AUSGELOEST` bzw. `UEBERREPRAESENTIERT`
  (>5× Erwartungswert bei Gleichverteilung, Democracy-4-Heuristik). Zählt
  **exakt** über `TurnResult.triggered_event_keys` (B6-Feld),
  `pending_dilemma.rule_key` und den Zuwachs von `active_situations` — keine
  Cooldown-Heuristik. Nutzt den **vollen** Regelsatz inkl. Situations (anders
  als `run_scenario`, das bewusst ohne Situations läuft). Der
  B3-`probability`-Würfel ist seed-unabhängig — Seeds streuen die Startwerte,
  nicht den Würfel. Aktueller Befund: `niedrige_bildungsausgaben` (Event) und
  `gruenes_wachstum` (Situation) triggern nie; `arbeitsmarktkrise` ist dank
  B3 jetzt erreichbar.

- **Fraktions-/Sitz-Datenmodell** (B8, `Faction` + `GameSession.role`/
  `SessionRole`): **nur Struktur, keine Mechanik** — eine Sitzverteilung im
  Landtag (`SAMPLE_FACTIONS`, 5 generische Fraktionen) pro Session, rein zur
  Anzeige ("Sitzverteilung im Landtag"). KEINE Koalitionslogik, KEIN
  Mehrheitszwang. Der Spieler ist immer `GOVERNMENT`; `OPPOSITION` existiert
  als Datenwert für eine spätere "nach Wahlniederlage in die Opposition statt
  Game Over"-Mechanik, erreichbar nur hinter `routes_game.
  DEMOTE_TO_OPPOSITION_ON_LOSS` (Default False). **Factions umgehen bewusst
  `sim_bridge`/`SimState`** (keine Sim-Wirkung, würden sonst jeden `clone()`
  belasten) — das Backend liest sie direkt aus der `faction`-Tabelle;
  API: `SessionStateResponse.role` + `factions` (`FactionOut`).
- **Szenario-/Legislatur-Ziele** (B9, `ScenarioGoal` + `GoalResult`,
  BACKLOG.md F1): **optionale, unverbindliche** End-of-Term-Prädikate.
  `ScenarioGoal` definiert key, description, metric (Statistik-Key oder
  "budget"/"approval"), operator, target_value. Am Wahl-Turn wertet
  `engine.py::_evaluate_goals()` jedes Ziel gegen den aktuellen Zustand
  aus (nutzt `_UNLOCK_OPERATORS` aus B7); Ergebnisse landen als
  `GoalResult` (key, description, met: bool) in `TermSummary.goals`.
  Verfehlte Ziele beenden die Partie **nicht** — Sieg/Niederlage hängt
  ausschließlich an der Wahl. `SAMPLE_SCENARIO_GOALS`: 4 Beispielziele
  (klimaziel, arbeitsmarkt, solide_finanzen, rueckhalt). Backend:
  `sim_bridge.load_scenario_goals()` (ohne DB, statischer Content),
  `GoalResultOut` in `TermSummaryOut`, `advance_turn()` nimmt
  `scenario_goals`-Parameter. Frontend: ✓/✗-Liste im
  Amtszeit-Bilanz-Panel.

- **Amtszeit-Bilanz / Legislatur-Bogen** (`TermSummary`, BACKLOG.md B1):
  `SimState` führt pro Legislaturperiode einen Schnappschuss mit
  (`term_start_turn/_budget/_statistics/_approval`, `term_dilemma_count`,
  `term_event_count`) — lazy beim ersten `advance_turn()` befüllt, am
  Wahl-Turn über `_build_term_summary()` zu einer `TermSummary` verrechnet
  und danach auf den neuen Zyklus zurückgesetzt. `TurnResult.term_summary`
  ist **nur am Wahl-Turn** gesetzt (gleichzeitig mit `election_result`).
  Reiner Rückblick (Start-vs-Ende je Statistik, richtungs-korrigierte
  `category_changes`, größter Fort-/Rückschritt, Dilemma-/Ereignis-Zähler,
  Budget-Bilanz) — **kein** Score-Gate, keine Siegbedingung (bewusst, siehe
  BACKLOG.md F1/B9). Persistenz: 6 neue `GameSession`-Spalten +
  `sim_bridge.load_sim_state()`-Parameter; API: `AdvanceTurnResponse.
  term_summary` (`TermSummaryOut`). Frontend: "Amtszeit-Bilanz"-Panel.

`advance_turn()` gibt ein `TurnResult`-Dataclass zurück (`state`, `events`,
`attributions`, `election_result`, `pending_dilemma`, `term_summary`,
`reports`, `triggered_event_keys`), **kein Tuple** — bei
Änderungen an der Rückgabe immer alle Aufrufer prüfen:
`sim/tests/test_engine.py`, `backend/app/api/routes_game.py`,
`sim/landtag_sim/tools/balance_runner.py`.

## Aktueller Stand (zuletzt aktualisiert nach P2-Umsetzung)

Alle 10 Punkte aus `docs/game-design-roadmap.md` sind umgesetzt: Effekt-
Vorschau, Wahlmechanik/Siegbedingung, Zufriedenheits-Attribution (P0),
Dilemma-Events, Policy-Voraussetzungen, Fast-Forward (P1), Namens-Vignetten,
Zufriedenheits-Momentum/Glättung, randomisierte Startbedingungen,
Dominante-Strategie-Check im Balance-Runner (P2). Details und
Umsetzungsnotizen direkt in der Roadmap-Datei je Punkt. Es gibt aktuell
keine offenen Roadmap-Punkte — nächste Schritte wären neue, über die
Roadmap hinausgehende Ideen (z.B. mehr Dilemma-Inhalte, überlappende
Wählergruppen, Balance-Tuning, siehe "Bekannte Vereinfachungen" unten).

Zusätzlich (nach P2, außerhalb der Roadmap-Liste) umgesetzt: `GET /policies`
— dynamischer Policy-Katalog aus der DB (`backend/app/api/routes_game.py::
list_policies`, `PolicyOut`-Schema), löst die vorherige hart codierte
`AVAILABLE_POLICIES`-Konstante in `App.jsx` ab. Frontend holt den Katalog
per `api.listPolicies()` einmalig beim Laden (mittlerweile durch den
kompletten `sim`- und Backend-Testlauf sowie einen Live-curl-Check
bestätigt, siehe unten — die frühere "ungetestet übergeben"-Notiz war nur
für eine Zwischenrunde gültig).

Nach-P2-Nachschärfung (Auftrag "Geh bis zum Ende des Backlogs", 2026-09-09):
- **Dominante-Strategie behoben**: `bildungsoffensive` war 100% dominant —
  Ursache war ein zu schwacher `gdp_growth`-Trade-off (-0.4, von ihrem
  eigenen `unemployment_rate`-Vorteil in derselben Kategorie
  überkompensiert = "Free Lunch") UND strukturelle Überrepräsentation, weil
  `steuersenkung_mittelstand` sie via `requires` voraussetzt. Fix: Trade-off
  auf -2.4 verschärft UND eine vierte, unabhängige Policy
  (`gesundheitsreform`, kein `requires`) ergänzt, die zugleich eine echte
  Lücke schließt (`healthcare_quality` hatte zuvor gar keine
  Policy-Anbindung). Balance-Runner bestätigt jetzt: "Keine vermutlich
  dominante Policy gefunden." Regressionstests: `test_every_starting_
  statistic_is_touched_by_at_least_one_policy`, `test_bildungsoffensive_
  has_a_genuine_net_negative_economy_tradeoff` (`sim/tests/test_engine.py`),
  `test_no_dominant_policy_among_current_sample_policies`
  (`sim/tests/test_balance_runner.py`).
- **Zwei neue Dilemmas**: `rezession` (`gdp_growth < 0.0`, organisch über
  `bildungsoffensive`s verschärften Trade-off erreichbar) und
  `pflegeausbau` (`healthcare_quality > 68.0`, ein Chancen- statt
  Krisen-Dilemma, über `gesundheitsreform` erreichbar). Bewusst so gewählt,
  dass sie — anders als `arbeitsmarktkrise`s Schwellenwert — ohne manuelle
  Statistik-Manipulation im normalen Spielverlauf erreichbar sind (siehe
  Reachability-Analyse in `mistakes.md`). Live per curl gegen `/advance`
  verifiziert (Dilemma feuert organisch, `resolve-dilemma` funktioniert).
  Regressionstests: `test_rezession_dilemma_is_reachable_via_sample_
  policies`, `test_pflegeausbau_dilemma_is_reachable_via_sample_policies`.
- **Überlappende Wählergruppen**: zwei neue, bewusst querliegende Gruppen
  (`Umweltbewusste Wähler`, `Junge Familien`) zu `SAMPLE_VOTER_GROUPS`
  hinzugefügt — überlappen absichtlich mit den vier exklusiven
  Basis-Gruppen (Summe `population_share` jetzt >1.0 statt exakt 1.0).
  Reine Datenänderung, keine Engine-/Schema-Änderung nötig, da
  `engine.py::_weighted_approval` schon durch `total_share` normalisiert.
  Regressionstest: `test_voter_group_shares_deliberately_overlap`.

Doku-Audit (2026-09-09) und direkte Anschluss-Fixes: ein vollständiger
Abgleich von README/CLAUDE.md/architecture.md gegen den tatsächlichen
Code-Stand ergab, dass die `BUDGET_NEGATIV`-Meldung der Dreier-Kombination
KEIN Upkeep-Tuning-Problem war, sondern eine strukturelle Lücke: das Budget
hatte überhaupt nie eine Einnahmequelle, nur Ausgaben — behoben durch
`BASE_BUDGET_INCOME_PER_TURN` (siehe Kernmechaniken oben und
`mistakes.md`). Balance-Runner bestätigt: die Dreier-Kombination bleibt
jetzt über 30 Runden bei +105 Budget statt -345. Regressionstests:
`test_budget_has_a_baseline_income_without_any_active_policy`,
`test_three_policy_combination_no_longer_goes_budget_negative`.

Zwei weitere, im selben Audit identifizierte echte Luecken wurden ebenfalls
geschlossen:

- **Backend-API-Testsuite** (`backend/tests/`): vorher gab es ausser einem
  Health-Check-Smoketest (`test_health.py`) KEINE automatisierten Tests --
  `/sessions`, `/preview`, `/advance`, `/resolve-dilemma`, `/policies`
  wurden ausschliesslich manuell per curl verifiziert. Jetzt 24 Tests
  (`conftest.py` + `test_sessions.py`, `test_advance.py`, `test_preview.py`,
  `test_dilemma.py`) gegen eine EIGENE Test-Datenbank
  (`landtag_sim_test`, siehe Setup unten) -- decken Happy-Path, alle drei
  advance_turn-Fehlerfaelle (Policy-Voraussetzung, Political Capital,
  unbekannter Key), Preview-Feasibility, einen vollen Wahlzyklus, den
  Dilemma-Block-/Resolve-Mechanismus und den LOST-Session-Guard ab. Wichtiger
  Fund dabei: `POST /sessions` nutzt ungeseedeten Start-Jitter
  (`jittered_starting_statistics()` ohne `rng`-Argument) -- Dilemma-Tests
  gegen echte Sessions duerfen deshalb NICHT annehmen, welches konkrete
  Dilemma zuerst feuert (siehe mistakes.md "Erster Backend-API-Testlauf ...
  flackerte wegen ungeseedetem Start-Jitter").
- **Frontend-Verlaufsansicht** (`frontend/src/App.jsx`): `events`/
  `attributions`/`electionResult` wurden vorher bei jedem `/advance`-Aufruf
  ueberschrieben, ein Spieler sah nur die letzte Runde. Neuer, rein
  clientseitiger `history`-State (`HISTORY_LIMIT = 60`) sammelt einen
  Eintrag pro Runde (auch bei Vorspulen -- JEDE uebersprungene Runde
  bekommt einen eigenen Eintrag, nicht nur die letzte) sowie pro
  aufgeloestem Dilemma, gerendert als neue "Verlauf"-Sektion
  (neueste zuerst).

M2-Backlog, B1 "Legislatur-Bogen & Amtszeit-Debrief" (2026-09-09,
BACKLOG.md): erster umgesetzter Punkt aus der Community-Recherche. Am
Wahl-Turn liefert `advance_turn()` jetzt zusätzlich eine `TermSummary`
(Start-vs-Ende-Bilanz der Legislaturperiode) — Details siehe Kernmechaniken-
Abschnitt oben und BACKLOG.md B1. Bewusst OHNE harte Siegbedingung (das
bleibt offene Design-Frage F1/B9). sim-Tests laufen (58 grün, davon 6 neu);
Backend-API-Tests (`backend/tests/test_term_summary.py`, 4 neu) und der
curl-E2E-Check konnten in der Umsetzungs-Session mangels laufendem lokalen
Postgres nicht ausgeführt werden — beim nächsten DB-Lauf nachholen (der
Verifikations-Workflow deckt sie ab).

M2-Backlog, B3 "Zustandsgekoppelte Risiko-Events" (2026-09-09, BACKLOG.md):
klärt Design-Frage F3 (Entscheidung: zustandsgekoppelte Risiko-Events, nicht
freie Zufalls-Schocks). `EventRule.probability` / `DilemmaRule.probability`
(Default `1.0`) plus deterministisches Gate
`events.py::passes_probability_gate` und die Vorstufe `konjunkturdelle` in
`sample_data.py` — Details im Kernmechaniken-Abschnitt "Zustandsgekoppelte
Risiko-Events" und in BACKLOG.md B3. sim-Tests laufen (69 grün, davon 6
neu); `backend/tests/test_risk_events.py` (3 neu, DB-Round-Trip des
`probability`-Felds) konnte mangels lokalem Postgres nicht ausgeführt werden
— beim nächsten DB-Lauf nachholen. Balance-Runner unverändert ("Keine
vermutlich dominante Policy", 12/24 Szenarien auffällig — identisch zum
Stand vor B3).

M2-Backlog, B4 "Narrative Konsequenz-Ebene ('Presseschau')" (2026-09-09,
BACKLOG.md): klärt Design-Frage F5 (Entscheidung: eigenes Modul `reports.py`
mit `ReportRule`, kein `silent`-Flag an `EventRule`). Rein textliche
Konsequenz-Meldungen ohne Sim-Wirkung, max. eine pro Runde und nur in
Runden ohne Event/Dilemma — Details im Kernmechaniken-Abschnitt "Narrative
Konsequenz-Ebene / 'Presseschau'" und in BACKLOG.md B4. Sim (`reports.py`,
`engine.py` Abschnitt 2c, `SAMPLE_REPORT_RULES` mit 7 Regeln), Backend
(`AdvanceTurnResponse.reports`, `sim_bridge.load_report_rules()` bewusst
ohne DB) und Frontend ("Presseschau"-Panel + Verlaufs-Zeilen, Fast-Forward
stoppt auch bei Reports) sind alle angebunden. sim-Tests 80 grün (11 neu);
`frontend`: `npm run build` + `npm run lint` grün (die eine oxlint-Warnung
bei `App.jsx:104` ist vorbestehend, nicht aus B4); `backend/tests/
test_reports.py` (3 neu) mangels lokalem Postgres nicht ausgeführt — beim
nächsten DB-Lauf nachholen. Balance-Runner unverändert (Reports haben keine
Sim-Wirkung).

M2-Backlog, B5 "Wahlprognose mit sichtbarem Turnout/Apathie" (2026-09-09,
BACKLOG.md): klärt F4 (Turnout abgeleitet aus `satisfaction` +
`satisfaction_momentum`, kein neues Feld). Neue Funktion
`engine.py::project_election(state) -> ElectionProjection` — Details im
Kernmechaniken-Abschnitt "Wahlprognose / Turnout-Apathie". Bewusste
Abweichung vom Backlog-Anker: `_weighted_approval` bleibt unangetastet, die
echte Wahl rechnet weiter ohne Turnout (kein Rebalancing von
B1–B4/Balance-Runner). Backend: `SessionStateResponse.election_projection`
(nur `status == ACTIVE` und `turns_until_election <= 5`). Frontend:
"Wenn heute Wahl wäre"-Panel. sim-Tests 88 grün (8 neu); `frontend`:
build + lint grün (dieselbe vorbestehende oxlint-Warnung);
`backend/tests/test_election_projection.py` (2 neu) mangels lokalem Postgres
nicht ausgeführt.

M3-Backlog, B7 "Dynamische Policy-Freischaltung durch Sim-Zustand"
(2026-09-10, BACKLOG.md): erster M3-Punkt. `Policy.unlock_conditions`
(`UnlockCondition`) + `engine.py::policy_is_unlocked` / `_validate_unlocks`
/ `PolicyLockedError` + drei gesperrte Beispiel-Policies — Details im
Kernmechaniken-Abschnitt "Dynamische Policy-Freischaltung" und in
BACKLOG.md B7. **Schema-Änderung**: neue JSON-Spalte
`policy_definition.unlock_conditions` — beim nächsten lokalen Postgres-Lauf
DB-Reset nötig (nicht per `create_all` nachrüstbar; siehe
Verifikations-Workflow / conftest droppt+erstellt ohnehin neu). sim-Tests
102 grün (8 neu: 6 engine + 2 balance_runner); Frontend build+lint grün;
`backend/tests/test_unlock.py` (4 neu) mangels lokalem Postgres nicht
ausgeführt.

M3-Backlog, B8 "Fraktions-/Sitz-Datenmodell (Grundstein Opposition/
Parlament)" (2026-09-10, BACKLOG.md): reine Struktur, keine Mechanik —
`Faction`-Modell + `SessionRole` + Sitzverteilungs-Anzeige. Details im
Kernmechaniken-Abschnitt "Fraktions-/Sitz-Datenmodell" und in BACKLOG.md B8.
**Schema-Änderung**: neue Tabelle `faction` + `game_session.role`-Spalte
(DB-Reset nötig; conftest baut Test-DB neu). Bewusste Abweichung: Factions
umgehen `sim_bridge`/`SimState` (keine Sim-Wirkung). Opposition-nach-
Niederlage nur hinter Flag `DEMOTE_TO_OPPOSITION_ON_LOSS` (Default aus). sim
103 / backend 53 grün (1 sim + 3 backend neu), Frontend build+lint grün.

M3-Backlog, B9 "Szenario-/Legislatur-Ziele" (2026-09-10, BACKLOG.md):
klärt F1 (Entscheidung: optionale, unverbindliche Ziele — kein Score-Gate,
keine Siegbedingung). `ScenarioGoal` + `GoalResult` in models.py,
`_goal_metric_value()` / `_evaluate_goals()` in engine.py (nutzt
`_UNLOCK_OPERATORS` aus B7), `SAMPLE_SCENARIO_GOALS` (4 Ziele) in
sample_data.py, `load_scenario_goals()` in sim_bridge.py (ohne DB),
`GoalResultOut` in schemas, ✓/✗-Liste im Frontend-Bilanz-Panel.
`advance_turn()` nimmt jetzt `scenario_goals`-Parameter. sim 107 / backend
55 grün (4 sim + 2 backend neu), Frontend build+lint grün.

M3-Backlog, B10 "PolicyDefinition.description mit echtem Text" (2026-09-10,
BACKLOG.md): neues `Policy.description`-Feld (models.py, reine Anzeige — die
Engine wertet es nicht aus), alle 8 Beispiel-Policies mit ein bis zwei
Saetzen Wirkungsbeschreibung (Haupteffekt + Trade-off) in sample_data.py.
`seed.py` setzt `description=policy.description or policy.name` (vorher fest
`policy.name`, totes Feld). Frontend rendert die Beschreibung unter jeder
Policy im Katalog (`.policy-description`). sim 108 / backend 55 grün,
Frontend build+lint grün.

M3-Backlog, B11 "docker-compose.yml Frontend-Service" (2026-09-10,
BACKLOG.md): neuer `frontend`-Service (`frontend/Dockerfile`, node:22-alpine,
`vite preview --host` auf Port 5173) — `docker compose up --build` startet
jetzt alle drei Services (db + backend + frontend), end-to-end verifiziert.
`VITE_API_BASE` ist ein Build-ARG (wird ins Bundle eingebacken, NICHT
Laufzeit), `backend`-Service `FRONTEND_ORIGIN` per `${FRONTEND_ORIGIN:-…}`
ueberschreibbar — beide aus optionaler `.env` im Repo-Root
(`.env.example` neu), noetig fuers Handy-Testen im LAN (LAN-IP statt
localhost, danach `docker compose up --build frontend`). Nebenbei einen
vorbestehenden `backend/Dockerfile`-Bug behoben: `pip install -r
requirements.txt` scheiterte an `-e ../sim` (Pfad fehlt im Build-Kontext) —
Zeile wird jetzt vor der Installation rausgefiltert, Sim-Engine kommt
weiterhin separat aus `/sim`. M3 damit vollstaendig (B7–B11 alle erledigt).

M4-Backlog, B12 "Dilemma-/Event-/Situations-Content-Ausbau" (2026-09-10,
BACKLOG.md, L4): Events 3→8, Dilemmas 3→7, Situations 2→5. Zentraler
Design-Kniff: die Rezession-Situation `abwanderung` ist jetzt die
**Reichbarkeits-Achse** — sie wirkt breit (milde Einzeleffekte, L3-Warnung)
auf co2_emissions (+), healthcare_quality (−), education_spending (−) und
unemployment_rate (+), wodurch die vorher organisch unerreichbaren
co2-/healthcare-Krisenschwellen (`smogalarm`, `klimaschutzgesetz`,
`klimakrise`, `pflege_engpass`, `krankenhausreform`, `pflegenotstand`) ueber
laengere Rezessionen erreicht werden. `abwanderung`-Hysterese verbreitert
(activate gdp_growth < −0.2, deactivate > 0.9). Zwei tote Regeln repariert:
`niedrige_bildungsausgaben` (Schwelle 30→34), `gruenes_wachstum` (activate
65→42). Neuer Regressionstest `test_every_sample_rule_is_organically_
reachable` in `sim/tests/test_balance_runner.py` (Telemetrie-Sweep,
ersetzt den alten „bleibt bei 0"-Test) faellt, sobald neuer Content nicht
mehr triggert. `strompreiskrise` (gdp_growth < 0.6) ueberdeckt im vollen
Roster `rezession` (< 0.0) bei Schweregrad + Optionen — die konjunkturdelle-
Vorstufen-Test isoliert deshalb bewusst nur die `rezession`-Regel.
Balance-Runner weiter „keine dominante Policy". sim 108 / backend 55 grün.

M4-Backlog, B13 "Echte Niedersachsen-Statistik-Importe" (2026-09-10,
BACKLOG.md): bewusst der **manuelle Recherche-Anker**, nicht die
GENESIS-API-Pipeline (braucht Registrierung → Fast-Follow, siehe
`data/README.md` „Stand"). Neue Datei `data/sources/niedersachsen_
startwerte.md`: Tabelle Spielwert vs. realer Nds.-Wert (LSN /
Energiewendebericht 2024), Quellen + Abrufdatum, bewusste Abweichungen.
`STARTING_STATISTICS`: `unemployment_rate` 6.0→5.9 (realer Jahreswert
2024); `gdp_growth` (real 2024 nur +0.4%, schwaches Jahr), `renewable_
share` (real Nds. deckt Strom bilanziell >100% erneuerbar), `co2_emissions`
(0-100-Index, keine Tonnen) weichen **bewusst** ab, weil B12-Content und
Balance-Runner darauf getunt sind — 1:1-Import wuerde Freischalt-/
Situations-Schwellen in Runde 0 ausloesen. `education_spending`/
`healthcare_quality` bleiben synthetische Indizes. Kommentarblock ueber
`STARTING_STATISTICS` fasst das je Wert zusammen. Zwei Report-Tests mit
hart codiertem „6.0" auf „5.9" nachgezogen.

M4-Backlog, B14 "Policy-/Statistik-Icons + CREDITS.md" (2026-09-10,
BACKLOG.md): 6 Statistik-Icons von game-icons.net (CC BY 3.0,
Delapouite/sbed) als reine `<path>`-Daten in `frontend/src/statIcons.js`
(kein schwarzer Hintergrund-Rect, `currentColor`). `StatIcon`-Komponente
in App.jsx rendert sie im „Statistiken"-Panel. `CREDITS.md`-Tabelle mit
Lizenzzeile pro Icon (Pflicht, architecture.md Punkt 9). Visuell
verifiziert. M4 damit vollstaendig (B12–B14).

B2-Design-Klärung (vor Implementierung, 2026-09-10): **Stat-zu-Stat-
Wirkungsketten** nach VWL-Standards statt Ideologie. Grundprinzip: ohne
gegenseitige Abhängigkeiten zwischen den 6 Statistiken sind Situations
"fake" (scenario: `abwanderung` erhöht unemployment, aber das hat keine
Folge auf gdp). Drei ökonomische Modelle bilden Backbone:
(1) **Phillips-Kurve/Okun's Law**: gdp_growth ↔ unemployment_rate
    (niedrig gdp → Jobabbau; hohe unemployment → niedriges gdp; NAIRU-
    Baseline 5%)
(2) **Solow-Modell (Humankapital)**: gdp_growth → healthcare_quality
    (gutes Wachstum → höhere Budgets; Rezession → sofort Sparmaßnahmen,
    asymmetrisch, 2-3-Runden-Lag)
(3) **Umwelt-Kuznets-Kurve**: co2_emissions = f(gdp_growth, renewable_share)
    (niedrig gdp + niedrig renewable = hohe Emissionen; hohe gdp + hohe
    renewable = saubere Industrie)

Gleichzeitig: **Policy-Architektur umstrukturieren.** Aktuell: 8 Mega-
Policies (z.B. "Gesundheitsreform" PC 4, healthcare +12, gdp -1.2).
Neu: zerstückelt in 2-4 kleinere, graduell aufbaubare Policies je Bereich
(z.B. "Elektronische Krankenschreibung" PC 1 +0.8, "Telemedizin" PC 2 +1.2,
"Krankenhausfusion" PC 3 +2.0, "Vollreform" PC 4 +12.0). Gewichte bleiben
ähnlich, aber Spielability steigt (Spieler kann gegen kleine Krisen
gegenwirken ohne Mega-Budget). Policy-Telemetrie zeigt: gdp_growth 12 Hebel,
education & unemployment je 8, **healthcare nur 4 (kritisch schwach!)**,
co2 & renewable je 2-4. Fokus: Healthcare zuerst (underrep'd, nur 1 Policy),
dann CO2/Erneuerbare, dann GDP-Bereich (überrep'd, aber Gewichte wichtig).
Neue B2-Beschreibung mit allen Zahlenwerten in BACKLOG.md.

DB-Lauf 2026-09-10 (Docker Desktop jetzt auf Christians Windows-Rechner
installiert): erstmals die komplette Backend-Testsuite lokal ausgeführt und
damit den über B1/B3/B4/B5/B7 aufgelaufenen "beim nächsten DB-Lauf
nachholen"-Rückstand abgearbeitet — **50 Backend-Tests grün** gegen die
dockerisierte Postgres-16 (`docker compose up -d db`, siehe
Verifikations-Workflow). Zwei dabei aufgedeckte veraltete Test-Annahmen
korrigiert (Produkt war korrekt): `test_list_policies_returns_full_sample_
catalog` erwartete nur 5 statt 8 Policies (B7 fügte 3 hinzu);
`test_term_summary_reports_policy_driven_statistic_changes` fuhr 15 Runden
ohne Dilemma-Auflösung, obwohl B3 (konjunkturdelle→rezession) jetzt
organisch ein Dilemma auslöst — Loop löst Dilemmas nun mit Option 0 auf und
prüft nur noch dilemma-unabhängige Invarianten. Die B7-Schemaänderung
(`unlock_conditions`-Spalte) war unkritisch, da `conftest.py` die Test-DB
per drop_all/create_all frisch aufbaut.

M2-Backlog, B6 "Dilemma-/Event-Trigger-Telemetrie im Balance-Runner"
(2026-09-10, BACKLOG.md): klärt F6 (Balance-Runner-Zählung über Szenarien ×
Seeds reicht als Proxy). Kleiner Engine-Zusatz `TurnResult.
triggered_event_keys` (maschinenlesbarer Regel-Key des gefeuerten Events),
dann `collect_trigger_counts` / `classify_triggers` / CLI `--seeds N` im
Balance-Runner — Details im Kernmechaniken-Abschnitt "Trigger-Telemetrie"
und in BACKLOG.md B6. Reine Dev-Tooling-/Sim-Änderung (Backend/Frontend
unberührt). Befund: `niedrige_bildungsausgaben` + `gruenes_wachstum`
triggern nie, `arbeitsmarktkrise` ist dank B3 erreichbar. sim-Tests 94 grün
(6 neu in `test_balance_runner.py`).

Policy-Repeal-Mechanismus (Auftrag "Mach mit dem Policy-Repeal-Mechanismus
weiter, schau vorher in Democracy 4 Mechaniken", 2026-09-09): vor der
Umsetzung wurden gezielt Democracy 4s Repeal-/Budget-/Einnahmen-Mechaniken
recherchiert (offizielle Modding-Dokumentation, Cliff Harris' Blogposts
"Real World Numbers in Democracy 4" und "Modelling the limits to growth",
Steam-Community-Modding-Guide -- zwei Fandom-Wiki-Seiten waren per WebFetch
nicht erreichbar, 402). Kernbefunde: (1) D4 laesst zurueckgezogene Policies
GRADUELL abklingen statt sie sofort zu entfernen; (2) Einfuehrung, Repeal
und Regler-Anpassung kosten politisches Kapital SEPARAT; (3) Einnahmen
kommen aus echten, vom Spieler gewaehlten Steuer-Policies
(`MinIncome`/`MaxIncome`), nicht aus einem unsichtbaren Zuschuss, und
skalieren teils an einer zugrunde liegenden Wirtschaftsstatistik. Daraus
umgesetzt (siehe "Policy-Repeal" und "Echte Einnahmen-Policies" in den
Kernmechaniken oben fuer die Details):
- `EnactedPolicy.repealed_turn` (sim + DB, ersetzt `active: bool`),
  `_effect_delta()` um symmetrischen Abbau erweitert, `advance_turn(...,
  newly_repealed_keys=...)`, drei neue Fehlerklassen
  (`PolicyAlreadyActiveError`, `PolicyNotActiveError`,
  `PolicyRequiredByActivePolicyError`).
- `Policy.income_per_turn` plus neue Beispiel-Policy `vermoegensteuer`
  (`income_per_turn=20.0`, hoechster `capital_cost` aller Policies) --
  Balance-Runner bestaetigt weiterhin "Keine vermutlich dominante Policy
  gefunden" mit jetzt 5 Policies.
- Backend: `repeal_policy_keys` auf `AdvanceTurnRequest`/`PreviewRequest`,
  `sim_bridge.py::load_sim_state()` laedt jetzt ALLE `EnactedPolicy`-Zeilen
  statt nur aktive (siehe Kernmechaniken-Abschnitt fuer die Begruendung).
- Tests: 8 neue sim-Engine-Tests (`sim/tests/test_engine.py`, u.a.
  `test_repealed_policy_effect_decays_symmetrically_instead_of_vanishing`,
  `test_repeal_blocked_when_still_required_by_an_active_dependent_policy`)
  und 10 neue Backend-API-Tests (`backend/tests/test_repeal.py`) --
  inklusive eines Regressionstests dafuer, dass eine zurueckgezogene Policy
  ueber MEHRERE GETRENNTE API-Requests hinweg weiter korrekt abklingt
  (`test_repeal_stops_upkeep_but_keeps_effect_decaying_across_requests`),
  da der State bei jedem Request frisch aus der DB aufgebaut wird.
- Live per curl gegen `/advance`/`/preview` end-to-end verifiziert
  (Enact -> mehrere Runden aufbauen -> Repeal -> Abkling-Kurve ueber
  mehrere Requests beobachtet -- Deltas nahmen exakt mit Faktor `(1-alpha)`
  pro Runde ab, wie von `_effect_delta` erwartet). Dabei eine echte
  Umgebungs-Falle gefunden und in `mistakes.md` dokumentiert: ein
  `SQLModel.metadata.drop_all/create_all`-Reset-Skript ohne vorherigen
  `import app.models` aendert scheinbar erfolgreich, aber tatsaechlich gar
  nichts am DB-Schema.

Bekannte, bewusst offene Vereinfachungen:
- `income_per_turn` ist ein fixer Betrag ohne Regler und ohne Kopplung an
  eine zugrunde liegende Wirtschaftsstatistik — Democracy 4 skaliert echte
  Steuereinnahmen z.B. an den tatsächlichen Alkoholkonsum (siehe
  Recherche-Notizen im Repeal-Abschnitt oben); ein "Steuersatz x
  Wirtschaftsaktivität"-Modell ist bewusst außerhalb des MVP-Scopes.
- Repeal kostet aktuell denselben `capital_cost` wie die Einführung — kein
  eigener, günstigerer "Cancel"-Kostensatz wie in Democracy 4 möglich
  (siehe dort: Einführung/Cancel/Regler-Anpassung sind drei separate
  Kostenfälle). Für die MVP-Policy-Anzahl (kein Regler-System) reicht die
  Vereinfachung.
- ~~Die meisten ursprünglichen Event-/Dilemma-Schwellenwerte
  (`arbeitsmarktkrise` u.a.) bleiben im organischen Spielverlauf praktisch
  unerreichbar~~ — **mit B3 (2026-09-09) adressiert**: die Vorstufe
  `konjunkturdelle` (`EventRule.probability`, siehe Kernmechaniken
  "Zustandsgekoppelte Risiko-Events") drückt `gdp_growth` graduell nach
  unten und macht `rezession` direkt sowie `arbeitsmarktkrise` (über die
  Situation `abwanderung`) erreichbar. Noch offen: weitere Vorstufen für
  Statistiken ohne solche Kette; und die Kette zu `arbeitsmarktkrise` ist
  lang (mehrere Legislaturperioden anhaltend schlechte Wirtschaft nötig).

## Verifikations-Workflow (bei jeder Engine-/Backend-Änderung)

**Lokale DB unter Windows via Docker Desktop (seit 2026-09-10 installiert) —
der bequemste Weg für den Backend-Testlauf:**

```bash
# Postgres 16 hochfahren (nur der db-Service; der backend-Service ist optional):
docker compose -f "C:/Users/chris/Claude Code Projekte/landtag-sim/docker-compose.yml" up -d db
# Warten bis bereit, dann die EIGENE Test-DB anlegen (einmalig; die Rolle
# `landtag` ist hier Bootstrap-Superuser und besitzt beide DBs -> der
# Postgres-15-Schema-Rechte-Fix von unten ist im Container NICHT nötig):
docker exec landtag-sim-db-1 psql -U landtag -d postgres -c "CREATE DATABASE landtag_sim_test OWNER landtag;"
# Backend-Tests (conftest.py biegt DATABASE_URL auf landtag_sim_test und baut
# das Schema per drop_all/create_all frisch auf -> Schemaänderungen wie B7s
# unlock_conditions-Spalte greifen automatisch, kein manueller Reset nötig):
cd backend && python -m pytest tests/ -q
```

Der folgende Linux-/`sudo -u postgres`-Weg ist die Alternative ohne Docker
(z.B. in einer Cloud-Sandbox mit lokalem Postgres):

```bash
cd sim && pip install -e . --break-system-packages -q && python -m pytest tests/ -q
python -m landtag_sim.tools.balance_runner --turns 30

cd ../backend && pip install -r requirements.txt --break-system-packages -q
sudo -u postgres psql -c "DROP DATABASE IF EXISTS landtag_sim;" && sudo -u postgres psql -c "CREATE DATABASE landtag_sim;"
# WICHTIG (siehe mistakes.md "permission denied for schema public"): seit Postgres 15
# hat die App-Rolle sonst kein CREATE-Recht im public-Schema einer frisch angelegten DB.
sudo -u postgres psql -d landtag_sim -c "ALTER DATABASE landtag_sim OWNER TO landtag;"
sudo -u postgres psql -d landtag_sim -c "ALTER SCHEMA public OWNER TO landtag;"
# ACHTUNG bei einem Schema-Update OHNE volles DROP/CREATE DATABASE (z.B. ein
# schneller `SQLModel.metadata.drop_all(engine); create_all(engine)`-Einzeiler):
# vorher `import app.models` ausfuehren, sonst registriert SQLModel die
# Tabellen gar nicht erst und der Reset aendert scheinbar fehlerfrei, aber
# TATSAECHLICH GAR NICHTS am Schema (siehe mistakes.md, Policy-Repeal-
# Nachschaerfung 2026-09-09) -- mit `psql \d <tabelle>` verifizieren.

# Backend-API-Testsuite (backend/tests/, seit Doku-Audit 2026-09-09) braucht
# eine EIGENE Test-DB (siehe conftest.py) -- einmalig anlegen, gleicher
# Postgres-15+-Owner-Fix wie oben:
sudo -u postgres psql -c "CREATE DATABASE landtag_sim_test;"
sudo -u postgres psql -d landtag_sim_test -c "ALTER DATABASE landtag_sim_test OWNER TO landtag;"
sudo -u postgres psql -d landtag_sim_test -c "ALTER SCHEMA public OWNER TO landtag;"
python -m pytest tests/ -q   # laeuft automatisch gegen landtag_sim_test, siehe conftest.py
uvicorn app.main:app --reload &   # dann zusaetzlich per curl End-to-End durchtesten (laeuft
# gegen die normale landtag_sim-Dev-DB, nicht die Test-DB):
# POST /sessions, GET /sessions/{id}, POST /sessions/{id}/preview, POST /sessions/{id}/advance
# — mindestens einen Wahlzyklus (16 Runden) durchspielen, um WON/LOST zu verifizieren
# — Policy mit requires ohne Voraussetzung versuchen (400 erwartet), dann mit Voraussetzung
# — ein Dilemma auslösen (z.B. gesundheitsreform einführen und ein paar Runden warten,
#   siehe mistakes.md "Erster Backend-API-Testlauf"), /advance sollte 400 liefern, dann
#   POST /sessions/{id}/resolve-dilemma und pruefen, dass /advance danach wieder geht
#   und der Cooldown ein sofortiges Retriggern verhindert

cd ../frontend && npm run build && npm run lint
```

Postgres-Zugangsdaten stehen in `backend/.env.example`
(`landtag`/`landtag`@`localhost:5432/landtag_sim`) — Rolle ggf. manuell
anlegen, siehe Kommandos oben.

## Bekannte Umgebungs-Einschränkung: Gerätebrücke

`mcp__remote-devices__device_bash` war in jeder bisherigen Session auf
Christians Windows-Gerät nicht verfügbar ("Workspace unavailable. The
isolated Linux environment on this device failed to start."). Das ist
also der Normalfall, nicht ein einmaliger Fehler — nicht mehrfach neu
versuchen. Funktionierender Workaround:

1. Geänderte Dateien nach `/mnt/user-data/outputs/<name>/` kopieren
   (Verzeichnisstruktur spiegeln).
2. `mcp__remote-devices__device_commit_files` mit `stagedPath` (unter
   `/mnt/user-data/outputs/`, NICHT der rohe Sandbox-Pfad) und `devicePath`
   (`C:\Users\chris\Claude Code Projekte\landtag-sim\...`) pro Datei
   aufrufen — funktioniert zuverlässig in Batches bis 50 Dateien.

## Git / GitHub

Öffentliches Repo: **https://github.com/megabashment/landtag-sim** (Branch
`main`). Der Cloud-Workspace hat ein lokales Git-Repo unter
`/home/claude/landtag-sim`, dessen `main`-Branch `origin/main` trackt
(eingerichtet 2026-09-09, siehe `mistakes.md` für die Vorgeschichte:
ursprünglich zwei komplett unabhängige Historien, jetzt per
`git checkout -B main origin/main` auf den GitHub-Stand ausgerichtet).

**Wichtige Einschränkung:** Diese Session (und vermutlich jede Cloud-
Session ohne explizit erteilten Zugriff) kann NICHT auf dieses Repo pushen
— `git push` scheitert mit einem Proxy-Fehler ("access denied by the git
proxy: ... is not in this session's authorized repository set"). Lesend
geht alles (`git fetch`/`clone`/`ls-remote`, da das Repo öffentlich ist),
schreibend nicht. Es gibt auch keinen verbundenen GitHub-Connector als
Alternative (nur Gmail/Calendar/Drive sind verbunden, Stand P1-Phase).

Das Freischalten für Push-Zugriff kann nur Christian selbst vornehmen
(vermutlich über Verbindungs-/Quellen-Einstellungen der Session/des
Produkts — der genaue Ort ist von hier aus nicht einsehbar). Bis das
passiert (oder ein GitHub-Connector verbunden wird), bleibt der Workflow:
lokal im Workspace committen (git funktioniert normal, nur `push`
schlägt fehl), UND zusätzlich per `device_commit_files`-Workaround in
`C:\Users\chris\Claude Code Projekte\landtag-sim` synchronisieren (das ist
aktuell selbst KEIN Git-Repo, nur ein Datei-Ordner) — Christian committet
und pusht von dort aus selbst. Bei jeder neuen Session zuerst kurz
`git push` gegen einen No-Op-Zustand testen (z.B. nach einem Fetch ohne
neue Commits) um zu sehen, ob sich der Berechtigungsstatus geändert hat,
statt anzunehmen, dass es weiterhin blockiert ist.

## Konventionen

- Deutsche Kommentare/Docstrings im Code (durchgängig beibehalten).
- Jede nicht-triviale Design-Entscheidung wird in `docs/architecture.md`
  oder `docs/game-design-roadmap.md` mit Begründung dokumentiert, nicht nur
  im Code — inklusive ehrlich benannter offener Probleme (siehe "Ehrlich:
  noch nicht gelöst"-Abschnitt in architecture.md).
- Kein Asset ohne Lizenz-Eintrag in `CREDITS.md`.
- `sim/` bleibt strikt DB-frei — jede DB-Kopplung gehört nach
  `backend/app/sim_bridge.py`.
