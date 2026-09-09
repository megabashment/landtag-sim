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
│   ├── vignettes.py       # P2: deterministische Namens-Vignetten (Text-Pool, zlib.crc32-Auswahl)
│   ├── sample_data.py    # SAMPLE_POLICIES, SAMPLE_EVENT_RULES, SAMPLE_DILEMMA_RULES, SAMPLE_VOTER_GROUPS, STARTING_STATISTICS, jittered_starting_statistics()
│   └── tools/balance_runner.py  # Headless Szenario-Tester über alle (voraussetzungs-gültigen) Policy-Kombinationen + Dominante-Strategie-Check
├── frontend/src/App.jsx  # Einzelnes Dashboard, Policy-Katalog per GET /policies (api.listPolicies)
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

`advance_turn()` gibt ein `TurnResult`-Dataclass zurück (`state`, `events`,
`attributions`, `election_result`, `pending_dilemma`), **kein Tuple** — bei
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

Bekannte, bewusst offene Vereinfachungen:
- Balance ist trotz der obigen Nachschärfung nicht perfekt rund: die
  Kombination `bildungsoffensive+steuersenkung_mittelstand+
  gesundheitsreform` rutscht im Balance-Runner mit `BUDGET_NEGATIV` ins
  Minus (-345 Budget nach 30 Runden) — kein Free-Lunch/Dominanz-Problem
  mehr, aber ein Hinweis, dass Upkeep-Kosten bei Drei-Policy-Kombinationen
  noch nicht gegengeprüft sind.
- Die meisten ursprünglichen Event-/Dilemma-Schwellenwerte
  (`arbeitsmarktkrise` u.a.) bleiben im organischen Spielverlauf praktisch
  unerreichbar, weil nichts in den Beispiel-Policies die Statistiken so
  stark in Richtung Krise treibt (siehe `mistakes.md`). Bewusst NICHT
  breit behoben (bräuchte z.B. zufällige Wirtschafts-Schock-Events) — bei
  den zwei neuen Dilemmas oben wurde das aber bei der Trigger-Wahl
  berücksichtigt.

## Verifikations-Workflow (bei jeder Engine-/Backend-Änderung)

```bash
cd sim && pip install -e . --break-system-packages -q && python -m pytest tests/ -q
python -m landtag_sim.tools.balance_runner --turns 30

cd ../backend && pip install -r requirements.txt --break-system-packages -q
sudo -u postgres psql -c "DROP DATABASE IF EXISTS landtag_sim;" && sudo -u postgres psql -c "CREATE DATABASE landtag_sim;"
# WICHTIG (siehe mistakes.md "permission denied for schema public"): seit Postgres 15
# hat die App-Rolle sonst kein CREATE-Recht im public-Schema einer frisch angelegten DB.
sudo -u postgres psql -d landtag_sim -c "ALTER DATABASE landtag_sim OWNER TO landtag;"
sudo -u postgres psql -d landtag_sim -c "ALTER SCHEMA public OWNER TO landtag;"
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
