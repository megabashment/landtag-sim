# CLAUDE.md — Projektgedächtnis für Landtag-Sim

**Status: M7 Phase 1 in Arbeit (B25 Content-Ausbau + B26 Opposition-Kampagnen-UI, 2026-09-12).** Siehe `M7_SPRINT_PLAN.md` für den vollen Sprint (B25-B29); B27-B29 noch offen.

**Schnelleinstieg:** Für abgeschlossene Phasen (M1-M4), Recherche-Learnings und historische Issues → **`ARCHIVE.md`**. Für Detailarchitkur → `docs/architecture.md`.

---

## Quick Start

```bash
# Backend-Tests
cd backend && python -m pytest tests/ -q

# Sim-Engine-Tests
cd ../sim && python -m pytest tests/ -q

# Frontend Build + Lint
cd ../frontend && npm run build && npm run lint

# Balance-Check
python -m landtag_sim.tools.balance_runner --turns 30

# Full Stack (Docker)
docker compose up --build   # Frontend :5173, Backend :8000
```

---

## Das Projekt

Ein respektvolles Management-Spiel mit Strong Anlehnung an *Democracy*-Reihe:
Policies mit verzögerter Wirkung setzen, Wählergruppen zufriedenstellen, Budget im Blick behalten, Wahl gewinnen.

**MVP-Szenario:** Niedersachsen (ein Bundesland). Harte Constraints (vom Nutzer vorgegeben):
- Kein LLM/NLP — reine Regex-Templates + regelbasierte Trigger
- Assets nur aus offen lizenzierten Quellen (CC0 bevorzugt, aber nicht exklusiv)
- Simulation serverseitig, Rendering client-seitig
- Repository öffentlich

---

## Stack & Architektur (Executive Summary)

| Bereich | Entscheidung |
|---|---|
| **Client** | React (Vite), reines Rendering |
| **Backend** | FastAPI |
| **Datenbank** | PostgreSQL |
| **Kommunikation** | REST, rundenbasiert (kein WebSocket) |
| **Sim-Engine** | Eigenes Package `landtag_sim` (pip-installierbar, **DB-unabhängig**) |

**Projektstruktur:**
```
landtag-sim/
├── backend/app/
│   ├── models/        # GameSession, Party, VoterGroup, Faction, etc.
│   ├── api/routes_game.py   # /sessions, /advance, /preview, /resolve-dilemma, /parties
│   └── sim_bridge.py   # Einziger Ort: DB ↔ Sim-Engine
├── sim/landtag_sim/
│   ├── engine.py        # Kern: advance_turn(), resolve_dilemma() — reine Funktionen
│   ├── models.py         # Dataclasses (Policy, SimState, TurnResult, etc.)
│   ├── events.py, dilemmas.py, situations.py, reports.py   # Regelbasierte Trigger
│   ├── sample_data.py    # SAMPLE_POLICIES (13), SAMPLE_RIVAL_PARTIES (3), etc.
│   └── tools/balance_runner.py  # Headless Szenario-Tester
├── frontend/src/App.jsx  # Single Dashboard, Policy-Katalog per GET /policies
└── data/, docs/         # Quellenforschung, Designdokumentation
```

---

## Kernmechaniken (Kurzfassung)

**Vollständige Referenz:** siehe `docs/architecture.md` "Kernmechaniken" Abschnitt.

- **Inertia-Modell:** Policy-Effekte nähern sich exponentiell geglättet an (nicht linear)
- **Political Capital:** zweite Ressource, begrenzt Reformen-Gleichzeitigkeit
- **Budget + Einnahmen:** `BASE_BUDGET_INCOME_PER_TURN=15.0` + real `income_per_turn` per Policy
- **Policy-Repeal:** Schrittweise Abklingung (symmetrisch zu Aufbau), nicht sofort
- **Effekt-Attribution:** Jeder Stat-Delta trägt Quelle (Policy-Key oder `event:<key>`)
- **Wahl:** After 16 turns, `_weighted_approval` gegen THRESHOLD (50% oder Pluralität mit Rivalen)
- **Wahlprognose (B5):** `ElectionProjection` mit Turnout-Apathie-Modell (sichtbar)
- **Policy-Freischaltung (B7):** `unlock_conditions` sperren Policies bis Statistik-Schwelle erreicht
- **Fraktionen (B8):** Reine Struktur (SessionRole, kein Mechanik-Impact, vorbereitet für Opposition)
- **Legislatur-Ziele (B9):** Optional, unverbindlich, kein Score-Gate
- **Situations (B2):** Self-reinforcing loops mit Hysterese (ein- & ausschalten an unterschiedlichen Schwellen)
- **Narrative Reports (B4):** Text-Konsequenzen ohne Sim-Impact (policy-gekoppelt, max. eine pro Runde)
- **Zustandsgekoppelte Risk-Events (B3):** `probability` Gates, deterministisch (crc32-Seed, kein `random`)
- **Rival Parties (Mehrparteiensystem):** EMA-basierte Drift von `base_strength` + Ideologie-Discontent, Election = Plurality (höchster Anteil gewinnt)
- **Party-Reputation (B20):** 0-100 Scale, ±10% Approval-Multiplikator, ±6/-8 auf Win/Loss, Legislaturen geloggt
- **Opposition-Loop (B15):** `opposition_mode`, `opposition_satisfaction`, Koalition-Viability, "In Opposition statt Game Over" auf Wahl-Niederlage

---

## Aktueller Stand (M7 Phase 1)

**Test-Suite (2026-09-12):**
- **Sim-Engine:** 131 Tests ✓ (8 neue: B25 Event-/Dilemma-Trigger)
- **Backend-API:** 66 Tests ✓ (3 neue: `test_opposition.py`)
- **Frontend:** Build+Lint ✓, Opposition-Kampagnen-Panel + StatusBar-Banner live verifiziert
- **Balance-Runner:** "Keine vermutlich dominante Policy", alle 6 neuen Events + 5 neuen Dilemmas triggern organisch (kein NIE_AUSGELOEST)

**Implementiert (M7 Phase 1):**

### B25 Event/Dilemma-Expansion
- Events 8 → 14 (6 neue: `wirtschaftsboom`, `energiewende_erfolg`, `pflege_fruehwarnung`, `bildungssparzwang`, `jobmotor`, `energiewende_ausbau`)
- Dilemmas 7 → 12 (5 neue: `fachkraeftezuwanderung`, `energiewende_ausbaustufe`, `bildungsnotstand`, `verkehrswende`, `tech_regulierung`)
- Alle neuen Regeln nutzen die bestehenden 6 Statistiken, meist als Zwischenstufe vor/nach einer bereits kalibrierten Schwelle (gleiches Muster wie `hohe_arbeitslosigkeit` vor `arbeitsmarktkrise`)
- **Wichtig:** Schwellen MUESSEN ausserhalb des Jitter-Bands der Statistik liegen (`jittered_starting_statistics`, Basis × [0.95, 1.05]), sonst feuert die Regel schon vor jeder Spielerentscheidung — siehe `mistakes.md` ("Neue Dilemma-Schwelle zu nah am Jitter-Band")

### B26 Opposition-Kampagnen-UI
- `GET /opposition-campaigns` — echter Kampagnen-Katalog (ersetzt die bisher unbenutzte hart codierte `_OPPOSITION_CAMPAIGNS`-Konstante im Frontend)
- `OppositionCampaignPanel` (Frontend): Kampagnen-Karten mit Single-Select (Radio), Effekt-Vorschau pro Wählergruppe, PC-Kosten
- Opposition-Mode-Banner in der StatusBar ("Du bist in Opposition")
- `SAMPLE_OPPOSITION_CAMPAIGNS`: 4 → 6 Kampagnen; **Bugfix:** `satisfaction_deltas`-Keys zeigten vorher auf nicht-existente Wählergruppen-Namen (z.B. "Arbeitnehmer" statt "Industriearbeiter") und wirkten dadurch NIE auf die Koalitionsfähigkeit — jetzt auf echte `SAMPLE_VOTER_GROUPS`-Namen korrigiert

### B24 Scenario-Modi (M6)
- `ScenarioDefinition` Model mit `starting_statistics_override`
- `GET /scenarios` — Liste vordefinierter Spielmodi (5 Sample-Szenarien)
- `POST /sessions/new-scenario/{scenario_id}` — Session mit Szenario-Startbedingungen
- Frontend Szenario-Auswahl im Start-Menu mit Beschreibungen
- Scenario-Statistik-Overrides werden auf Jitter angewendet

### Advanced Opposition (Coalition, M6)
- `ElectionResult.coalition_viability` [0-100] — Viabilität Regierungs-Opposition-Koalition
- Berechnung basiert auf Opposition-Zufriedenheit aus Sim-Engine
- `POST /sessions/{id}/respond-to-election` — Coalition Accept/Decline Endpoint
- Coalition nur wenn viability ≥ 30% und vom Spieler akzeptiert
- UI-Dialog mit Koalitionsviabilität, Annahme hält GOVERNMENT-Role, Ablehnung → OPPOSITION
- Frontend Koalitions-Dialog mit Styling, wird bei Wahlverlust (viability ≥30) gezeigt

---

## Verifikations-Workflow

**Mit Docker Desktop (empfohlen):**

```bash
# Postgres starten
docker compose -f .../docker-compose.yml up -d db
# Test-DB anlegen (einmalig)
docker exec landtag-sim-db-1 psql -U landtag -d postgres \
  -c "CREATE DATABASE landtag_sim_test OWNER landtag;"

# Backend-Tests (gegen separate landtag_sim_test)
cd backend && python -m pytest tests/ -q

# Sim-Tests
cd ../sim && python -m pytest tests/ -q
```

**Wichtig:** `conftest.py` isoliert die Test-DB per `drop_all/create_all` — Schema-Änderungen (z.B. B7 unlock_conditions) greifen automatisch.

**Für Produktions-DB-Reset nötig:** `docker compose down -v && up --build` (einmalig bei Schema-Änderungen, da `init_db` bewusst `create_all`-only ist).

---

## Git / GitHub

**Öffentliches Repo:** https://github.com/megabashment/landtag-sim

**Constraint (Cloud-Session):** `git push` funktioniert nicht (Proxy-Block). Workaround: lokal committen, `device_commit_files` zur Windows-Dev-Box synchronisieren, dort pushen.

---

## Konventionen

- **Deutsch:** Kommentare/Docstrings durchgängig Deutsch
- **`sim/` bleibt DB-frei:** Alle DB-Kopplungen gehören nach `backend/app/sim_bridge.py`
- **Kein Asset ohne Lizenz:** Jedes Icon/Grafik in `CREDITS.md` eintragen
- **Reine Funktionen:** `engine.py` hat keine Seiten-Effekte, testet deterministisch (crc32-Seeds, kein `random`)

---

## Bekannte, bewusst offene Vereinfachungen

- `income_per_turn` ist fixer Betrag (kein Regler, keine Kopplung an Wirtschaftsstatistik)
- Repeal kostet denselben `capital_cost` wie Einführung (kein separater "Cancel"-Satz wie in D4)
- Opposition-Koalitionsverhandlungen sind Zielrechnung, nicht echte Mechanik (M6+)

---

## Nächste Sprints (M7+)

**M6 abgeschlossen — B24 + Advanced Opposition live. M7 Phase 1 (B25+B26) abgeschlossen** (siehe `M7_SPRINT_PLAN.md`).

Offene Prioritäten (M7 Phase 2+3):
- **B27 Bundes/EU-Skalierung** (Bayern + NRW als weitere Bundesländer, State-Baseline)
- **B28 Advanced UI** (Party-History-Modal, Coalition-Viz, Session-Dauer-Info)
- **B29 Playtesting & Balance-Audit** (Balance-Runner pro State, `docs/balance-notes.md`)

---

**Für tiefere Doku:** `docs/architecture.md` (Game-Director-Review), `docs/game-design-roadmap.md` (P0-P2 Roadmap), `ARCHIVE.md` (historische Learnings).

**Für Fehler & Fallstricke:** `mistakes.md`.
