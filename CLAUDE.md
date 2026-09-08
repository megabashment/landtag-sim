# CLAUDE.md — Projektgedächtnis für Landtag-Sim

Diese Datei ist der Einstiegspunkt für jede neue Claude-Session an diesem
Projekt. Ziel: nicht bei null anfangen müssen. Ausführliche Herleitungen
stehen in `docs/architecture.md` (Game-Director-Review) und
`docs/game-design-roadmap.md` (Senior-Game-Designer-Review) — diese Datei
fasst nur zusammen, was für den nächsten Arbeitsschritt wichtig ist.

Siehe auch `mistakes.md` für bereits gefundene und behobene Bugs —
**vor größeren Refactors dort nachsehen**, damit dieselben Fehler nicht
zweimal gemacht werden.

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
│   ├── models/        # AdminUnit, StatisticDefinition/-Value, VoterGroup, PolicyDefinition, EventDefinition, DilemmaDefinition, GameSession
│   ├── api/routes_game.py   # /health, /sessions, /sessions/{id}/preview, /sessions/{id}/advance, /sessions/{id}/resolve-dilemma
│   └── sim_bridge.py   # Übersetzt DB <-> reine Sim-Engine (einziger Ort für diese Übersetzung)
├── sim/landtag_sim/
│   ├── engine.py        # Kern: advance_turn() / resolve_dilemma() — reine Funktionen
│   ├── models.py         # Dataclasses: Policy, PolicyEffect, VoterGroup, EventRule, DilemmaRule, DilemmaOption, PendingDilemma, SimState, TurnResult, EffectAttribution, ElectionResult
│   ├── events.py         # Regelbasierte Trigger-Auswertung (passiv, fester Effekt)
│   ├── dilemmas.py        # Regelbasierte Trigger-Auswertung mit echten Entscheidungsoptionen
│   ├── templates.py      # Regex-basiertes Text-Rendering (kein LLM)
│   ├── sample_data.py    # SAMPLE_POLICIES, SAMPLE_EVENT_RULES, SAMPLE_DILEMMA_RULES, SAMPLE_VOTER_GROUPS, STARTING_STATISTICS
│   └── tools/balance_runner.py  # Headless Szenario-Tester über alle (voraussetzungs-gültigen) Policy-Kombinationen
├── frontend/src/App.jsx  # Einzelnes Dashboard, hart codierter Policy-Katalog (GET /policies fehlt noch)
├── data/                 # Datenquellen-Doku (Landesamt für Statistik Niedersachsen statt Weltbank/V-Dem, siehe data/README.md)
└── docs/                 # architecture.md (Game-Director-Review), game-design-roadmap.md (Senior-Game-Designer-Review, 10 gewichtete Vorschläge)
```

### Kernmechaniken

- **Inertia-Modell** (`engine.py::_effect_delta`): Policy-Effekte nähern
  sich ihrem Zielwert exponentiell geglättet an (`inertia`-Parameter,
  Vorbild Democracy 4), nicht linear in einem festen Zeitfenster. Sie
  verschwinden NICHT nach fester Rundenzahl, solange die Policy aktiv ist
  und Upkeep gezahlt wird.
- **Political Capital**: zweite Ressource neben Budget, begrenzt wie viele
  Reformen gleichzeitig durchsetzbar sind (`CAPITAL_PER_TURN = 3.0`,
  `CAPITAL_CAP = 10.0`). Wirft `InsufficientCapitalError`, wenn eine Auswahl
  mehr kostet als verfügbar — State wird dabei NICHT mutiert.
- **Jede Policy hat mindestens einen negativen Nebeneffekt** (Trade-off-
  Pflicht, siehe `test_every_sample_policy_has_at_least_one_negative_effect`)
  — reine Positiv-Policies waren der Hauptkritikpunkt der ersten Review.
- **Event-System**: regelbasierte Trigger (`EventRule`), bei mehreren
  gleichzeitig eligible Events feuert nur das mit der höchsten Severity pro
  Runde (kein Event-Spam).
- **Effekt-Attribution** (`EffectAttribution`): jeder Statistik-Delta trägt
  seine Quelle (Policy-Key oder `event:<key>`) — Backend/Frontend können so
  erklären, WARUM sich eine Zahl geändert hat.
- **Wahlmechanik**: `turns_until_election` zählt jede Runde runter
  (Zykluslänge 16). Bei 0 wird die nach `population_share` gewichtete
  Durchschnittszufriedenheit gegen `ELECTION_APPROVAL_THRESHOLD = 50.0`
  geprüft. Verloren → `SessionStatus.LOST`, Partie endet (`/advance` liefert
  danach HTTP 400). Gewonnen → Session bleibt `ACTIVE`, nächster Zyklus
  beginnt (Wiederwahl = Weiterspielen, kein Spielende).
- **Effekt-Vorschau**: `POST /sessions/{id}/preview` simuliert `advance_turn`
  mit gewählten Policies, verwirft das Ergebnis (kein Persistieren). Liefert
  grobe Richtungs-/Größenklassen (schwach/mittel/stark) statt exakter
  Zahlen — bewusst vage wie Frostpunks Book of Laws.
- **Policy-Voraussetzungen** (`Policy.requires`): eine Policy kann erst
  eingeführt werden, wenn ihre Voraussetzungen bereits aktiv sind (oder in
  derselben Runde mitgewählt werden) — sonst `UnmetPrerequisiteError`.
  Beispiel: `steuersenkung_mittelstand` braucht `bildungsoffensive`.
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

`advance_turn()` gibt ein `TurnResult`-Dataclass zurück (`state`, `events`,
`attributions`, `election_result`, `pending_dilemma`), **kein Tuple** — bei
Änderungen an der Rückgabe immer alle Aufrufer prüfen:
`sim/tests/test_engine.py`, `backend/app/api/routes_game.py`,
`sim/landtag_sim/tools/balance_runner.py`.

## Aktueller Stand (zuletzt aktualisiert nach P1-Umsetzung)

Alle drei P0-Punkte UND alle drei P1-Punkte aus
`docs/game-design-roadmap.md` sind umgesetzt: Effekt-Vorschau,
Wahlmechanik/Siegbedingung, Zufriedenheits-Attribution (P0), Dilemma-Events,
Policy-Voraussetzungen, Fast-Forward (P1). Details und Umsetzungsnotizen
direkt in der Roadmap-Datei je Punkt.

Offene P2-Punkte (kleinere Verbesserungen, siehe Roadmap für Begründung und
Quellen): Namens-Vignetten in Event-Texten, Zufriedenheits-Momentum/
Glättung, randomisierte Startbedingungen, Dominante-Strategie-Check im
Balance-Runner.

Bekannte, bewusst offene Vereinfachungen:
- Wählergruppen sind exklusiv (keine Überlappung) — Democracys
  Kernmechanik braucht überlappende Fraktionen, siehe Game-Director-Review.
- `GET /policies` fehlt — Frontend nutzt eine hart codierte Liste
  (`AVAILABLE_POLICIES` in `App.jsx`, inkl. `requires`), die mit
  `sample_data.py` synchron gehalten werden muss.
- Balance ist noch nicht rund: "erneuerbare_foerderung+bildungsoffensive"
  treibt die Zufriedenheit über 30 Runden auf ~86 und führt praktisch immer
  zum Wahlsieg — Kandidat für den Dominante-Strategie-Check (Roadmap #10).
- Nur ein Beispiel-Dilemma (`arbeitsmarktkrise`) vorhanden — für echte
  Genre-Wirkung braucht es mehrere, an unterschiedliche Statistiken
  gekoppelte Dilemmas.

## Verifikations-Workflow (bei jeder Engine-/Backend-Änderung)

```bash
cd sim && pip install -e . --break-system-packages -q && python -m pytest tests/ -q
python -m landtag_sim.tools.balance_runner --turns 30

cd ../backend && pip install -r requirements.txt --break-system-packages -q
sudo -u postgres psql -c "DROP DATABASE IF EXISTS landtag_sim;" && sudo -u postgres psql -c "CREATE DATABASE landtag_sim;"
python -m pytest tests/ -q
uvicorn app.main:app --reload &   # dann per curl End-to-End durchtesten:
# POST /sessions, GET /sessions/{id}, POST /sessions/{id}/preview, POST /sessions/{id}/advance
# — mindestens einen Wahlzyklus (16 Runden) durchspielen, um WON/LOST zu verifizieren
# — Policy mit requires ohne Voraussetzung versuchen (400 erwartet), dann mit Voraussetzung
# — ein Dilemma auslösen (z.B. per direktem SQL-UPDATE auf statistic_value, siehe
#   mistakes.md "Dilemma-Persistenz"), /advance sollte 400 liefern, dann
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

## Konventionen

- Deutsche Kommentare/Docstrings im Code (durchgängig beibehalten).
- Jede nicht-triviale Design-Entscheidung wird in `docs/architecture.md`
  oder `docs/game-design-roadmap.md` mit Begründung dokumentiert, nicht nur
  im Code — inklusive ehrlich benannter offener Probleme (siehe "Ehrlich:
  noch nicht gelöst"-Abschnitt in architecture.md).
- Kein Asset ohne Lizenz-Eintrag in `CREDITS.md`.
- `sim/` bleibt strikt DB-frei — jede DB-Kopplung gehört nach
  `backend/app/sim_bridge.py`.
