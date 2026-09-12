# CLAUDE.md — Projektgedächtnis für Landtag-Sim

**Status: M5 Phase 2 complete (Opposition-Loop MVP + B20/B23 + Mehrparteiensystem, 2026-09-11).** Spiel lauffähig und end-to-end testbar.

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

## Aktueller Stand (M5 Phase 2)

**Test-Suite (2026-09-11):**
- **Sim-Engine:** 123 Tests ✓ (14 neu: B20/Mehrparteiensystem)
- **Backend-API:** 60 Tests ✓ (5 neu in test_party_legacy.py)
- **Frontend:** Build+Lint ✓, multi-party Sonntagsfrage live im Browser verifiziert
- **Balance-Runner:** "Keine vermutlich dominante Policy" (consistent)

**Implementiert (M5 Phase 2):**
- `VoterGroup.ideology_preference` / `ideology_dislike` (green/red/blue) — 6 Sample-Gruppen mit Affinitäten
- `Party` table + Party-Gründungs-Dialog (POST /sessions/new-party)
- `party_reputation` (0-100, 50 neutral) → ±10% Approval-Multiplikator
- Win/Loss → ±6/-8 Ruf, Legislaturen in `Party.extra_data["terms"]` geloggt
- `GET /parties` (Party-Profile mit terms_played/terms_won)
- `POST /sessions/from-party/{id}` (neue Legislatur mit aufgebautem Ruf)
- `RivalParty` + 3 feste AI-Konkurrenten (Klima-Liste/grün, SozialAllianz/rot, Wirtschaftsunion/blau)
- **Plurality-Wahl** mit Rivalen (höchster Anteil gewinnt), **Threshold** ohne Rivalen
- Multi-Party Sonntagsfrage (4-Balken, Farben nach Ideologie)
- Standings in Wahlergebnis (normalisiert auf 100%, sortiert)
- "Weiter mit Partei X" im Start-Menü

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

## Nächste Sprints (M6+)

- **B24 Scenario-Modi** (Kampagnen, Preset-Welten)
- **Advanced Opposition** (echte Koalitionsverhandlungen, Parliament-Majority)
- **Bundes/EU-Skalierung** (regionale Variation, Föderalismus)
- **Content-Ausbau** (mehr Dilemmas, Events, Policies)
- **Playtesting & Balance-Tuning** (Spieler-Feedback-Integration)

---

**Für tiefere Doku:** `docs/architecture.md` (Game-Director-Review), `docs/game-design-roadmap.md` (P0-P2 Roadmap), `ARCHIVE.md` (historische Learnings).

**Für Fehler & Fallstricke:** `mistakes.md`.
