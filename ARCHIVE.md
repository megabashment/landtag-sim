# ARCHIVE — Abgeschlossene Phasen & Referenz-Dokumentation

Diese Datei archiviert historische Design-Entscheidungen, abgeschlossene Meilenstones und Recherche-Learnings. Siehe `CLAUDE.md` für den aktuellen Stand (M5+).

---

## Recherche-Learnings 2026-09-09 (Community-Analyse)

Verdichtet aus Democracy 3/4 Steam-Diskussionen, Positech-Devblog, Frostpunk/Suzerain und Policymaking-Game-Design-Literatur. Die wichtigsten:

- **L1:** Kein pauschales "Winning" — M5 adressiert mit Opposition-Loop und Party-Persistierung
- **L2:** Situations als mittlerer Zeithorizont → B2 implementiert (Hysterese, self-reinforcing loops)
- **L3:** Self-reinforcing loops brauchen Bremsen → B2 Phase 1 (gedämpfte Kurven, regelbasierte Gegenhebel)
- **L4:** Dilemma-Trigger-Telemetrie → B6 implementiert (Seed-basierte Messungen, 12/24 Szenarien auffällig)
- **L5:** Narrative Konsequenz-Ebene (Media Reports) → B4 implementiert (Regex-Templates, keine LLM, policy-gekoppelt)
- **L6:** Wahlprognose mit Turnout-Transparency → B5 implementiert (Apathie-Modell sichtbar)
- **L7:** Dynamische Policy-Freischaltung → B7 implementiert (`unlock_conditions`, Statistik-gesteuert)
- **L8:** Opposition / Parlament-Datenstrukturen → B8 implementiert (Fraktionen, SessionRole, future-proof)
- **L9:** Zustandsgekoppelte Risiko-Events statt freie Zufallsschocks → B3 implementiert (Probability Gates)
- **L10:** Pacing / Legislatur-Debrief → B1 implementiert (TermSummary, Amtszeit-Bilanz)

---

## Abgeschlossene Meilestones (M1 — M4 Summary)

### M1 — Engine-MVP & Wahl-Mechanik
**P0 "Baseline Simulation"** + **P1 "Dilemmas & Effekt-Vorschau"** + **P2 "Balance & Automation"**

- Core: `advance_turn()`, Policy-System, Voter-Satisfaction, Election Threshold (50%)
- Events (3), Dilemmas (3), Policies (5 → 8), Situations (2 → 5)
- Effekt-Attribution, Dominante-Strategie-Check, Balance-Runner
- Frontend: Basis-Dashboard, Policy-Auswahl, Fast-Forward
- **106 Sim-Tests, 50 Backend-Tests, Frontend Build+Lint clean**

### M2 — Legislatur-Architektur & Narrative Layer
**B1 (TermSummary)** + **B3 (Probability Gates)** + **B4 (Report Rules)** + **B5 (Turnout)** + **B6 (Trigger-Telemetry)**

- Amtszeit-Bilanz mit Start-vs-Ende-Vergleich
- Zustandsgekoppelte Risk-Events (konjunkturdelle-Vorstufe zu Krisen)
- Presseschau-Meldungen (policy-gekoppelt, keine Sim-Wirkung)
- Wahlprognose mit Apathie-Modell
- Trigger-Zählung über Szenarien (telemetrie-Messung)
- **88 Sim-Tests, 55 Backend-Tests, Frontend Build+Lint clean**

### M3 — Policy-Matura & Parlamentarismus
**B7 (Dynamic Unlock)** + **B8 (Factions)** + **B9 (Goal System)** + **B10 (Descriptions)** + **B11 (Docker)**

- Unlock-Conditions (Statistik-getrieben, kein requires-Kette mehr allein)
- Faction-Datenmodell (SessionRole, vorbereitend für Opposition)
- Scenario Goals (optional, unverbindlich, kein Score-Gate)
- Policy-Beschreibungen (User-facing, Wirkungstext)
- Docker-Service für Frontend (full-stack reproducible, LAN-testbar)
- **108 Sim-Tests, 55 Backend-Tests, Frontend Build+Lint clean**

### M4 — VWL-Engine & Content-Expansion
**B2 (Stat-to-Stat Dynamics)** + **B12 (Content Expansion)** + **B13 (Empirical Calibration)** + **B14 (Icons)**

- Phillips-Kurve + Solow-Modell (gdp ↔ unemployment, gdp → healthcare, co2 = f(gdp, renewables))
- 8 → 13 Policies (graduated paths in Healthcare + Renewables)
- 3 → 8 Events, 3 → 7 Dilemmas, 2 → 5 Situations (organically reachable via Reachability-Graph)
- Niedersachsen empirical start values (LSN 2024 baseline, consciously abstracted for balance)
- Policy-Icons (game-icons.net CC BY 3.0, CREDITS.md)
- **94 Sim-Tests, 55 Backend-Tests, Frontend Build+Lint clean**
- **Balance-Runner: "Keine vermutlich dominante Policy" (consistent across phases)**

---

## M5 — Opposition-Loop MVP (Complete as of 2026-09-11)

**B15 Phase 1-4:** Opposition-Engine, Backend-API, Frontend-UI (Sonntagsfrage-Overlay)

- `opposition_mode`, `opposition_satisfaction`, `opposition_momentum`
- Opposition-Kampagnen (4 sample), Viability-Berechnung
- After loss: option to go Opposition vs. Game Over (now enabled via `DEMOTE_TO_OPPOSITION_ON_LOSS=True`)
- Multi-bar Sonntagsfrage overlay (Regierung vs. Opposition), 30% coalition threshold
- Opposition-Wahl-Dialog (UI + State management)
- **99 Sim-Tests, 55 Backend-Tests, Frontend Build+Lint clean**
- **Status: MVP READY** (Phase 4c Runden-Ticker optional for later)

---

## M5 Phase 2 — B23 + B20 + Mehrparteiensystem (Complete as of 2026-09-11)

**B23 (Party Persistence)** + **B20 (Party Legacy)** + **Mehrparteiensystem (Rival Dynamics)**

- Voter-Group `ideology_preference` / `ideology_dislike` (green/red/blue preference model)
- `Party` table + Party-Gründungs-Dialog (POST /sessions/new-party)
- `party_reputation` (0-100, 50 neutral) → ±10% approval multiplier
- Election win/loss → ±6/-8 reputation, terms tracked in `Party.extra_data`
- `GET /parties` (party profiles with terms_played/terms_won)
- `POST /sessions/from-party/{id}` (new legislature with legacy reputation)
- `RivalParty` dataclass + 3 fixed AI competitors (Klima-Liste/green, SozialAllianz/red, Wirtschaftsunion/blue)
- EMA-based rival approval drift toward `base_strength + ideology-matched discontent` (Alpha=0.30)
- Election: **plurality voting** with rivals (highest share wins), **threshold-only** without rivals
- `ElectionResult.standings` (normalized to 100%, sorted descending)
- Multi-party Sonntagsfrage bar chart (colored by ideology: player=orange, rivals by ideology color)
- Election result standings table (ranked list with percentages)
- "Weiter mit Partei X" in start menu (loads existing party with legacy reputation)
- **123 Sim-Tests grün, 60 Backend-Tests grün (5 new in test_party_legacy.py)**
- **Balance-Runner unchanged ("Keine dominante Policy")**
- **Frontend: build clean, multi-party Sonntagsfrage verified live in browser**

---

## Historical Issues & Fixes (for reference)

### Budget-System (Early P2)
- **Issue:** Budget had only outflows, no baseline income → Policies kept budget perpetually under pressure
- **Fix:** `BASE_BUDGET_INCOME_PER_TURN=15.0` (simplified Landtag baseline tax revenue)
- **Plus:** `Policy.income_per_turn` for real income-policies (e.g. wealth tax)
- **Reference:** `sim/landtag_sim/engine.py::advance_turn()`, `sim/landtag_sim/sample_data.py::vermoegensteuer`

### Dilemma-Reachability (M4/B12)
- **Issue:** Most Event/Dilemma trigger-thresholds were organically unreach­able (e.g. co2_crisis requiring 95% co2)
- **Fix:** Situations as intermediate layer + reachability-graph analysis
  - `abwanderung` (recession situation) self-reinforces weakness across gdp/healthcare/education/unemployment
  - Creates organic pathways: policy-choice → small stat shift → vorstufe-event (konjunkturdelle) → actual crisis (rezession, arbeitsmarktkrise)
  - B6 telemetry confirmed: all current rules now organically reachable except for very late-game edge cases
- **Reference:** `mistakes.md` "Reachability-Analyse 2026-09-10", `BACKLOG.md` B12, `sample_data.py` reachability comments

### Dilemma-Cooldown (B1)
- **Issue:** Test `test_term_summary_carries_scenario_goals` assumed 20 turns without dilemma-interruption
- **Fix:** Dilemmas now can trigger naturally (B3 probability gates enabled) — test now resolves auto with Option[0], only checks dilemma-independent invariants
- **Reference:** `backend/tests/test_scenario_goals.py`, `sim/tests/test_engine.py` dilemma-cooldown comments

### Backend Test Suite (M2 Audit)
- **Issue:** Only Health-Check test, rest was manual curl (pre-2026-09-09)
- **Fix:** Full Backend-Test suite (`backend/tests/`) with separate `landtag_sim_test` DB, `conftest.py` isolation
- **Reference:** `backend/tests/conftest.py`, `CLAUDE.md` "Verifikations-Workflow"

### Policy-Repeal (Post-M2)
- **Issue:** Policy removal was instant; Democracy 4 removes gradually (symmetric inertia)
- **Fix:** `EnactedPolicy.repealed_turn`, `_effect_delta()` symmetric decay, upkeep/income stop immediately
- **Reference:** `sim/landtag_sim/engine.py::_effect_delta`, `sim/tests/test_engine.py` repeal-decay tests, `backend/tests/test_repeal.py`

### Stat-to-Stat Coupling (M4/B2)
- **Issue:** Policies had no interdependencies (gdp change didn't affect unemployment); situations were "fake"
- **Fix:** Phillips-Curve + Solow-Modell in `engine.py::_phillips_curve_and_solow()`
  - Phillips: unemployment ↔ gdp_growth (0.4–0.8% impact, mild)
  - Solow: gdp_growth → healthcare with 2-turn lag (1% boost, 2% recession, asymmetric damping)
  - Kuznets: co2 = f(gdp, renewable) (high growth + renewables = clean)
- **Reference:** `sim/landtag_sim/engine.py` section B2 Phase 1, `BACKLOG.md` B2, `mistakes.md` "VWL-Recherche"

### Test-DB Schema Persistence (B7)
- **Issue:** `SQLModel.metadata.drop_all() + create_all()` without prior `import app.models` made no schema changes
- **Fix:** Always import models FIRST before any drop/create
- **Reference:** `backend/app/db.py`, `mistakes.md` "SQLModel Gotcha"

---

## Full Backlog Archive

Original 82-point backlog (BACKLOG.md, now superseded by M5+ planning):
- B1–B14 all completed
- B15 Opposition-Loop (M5 Phase 1, complete)
- B16–B25+ deferred to M6+ (Scenarios, advanced Diplomacy, Coalition mechanics, etc.)

See original `BACKLOG.md` for design-doc context on each point.

---

## Next Up (from CLAUDE.md M5+)

- **Sprint 5 (Post-Phase 2):** B24 Scenario-Modi (campaign challenges, preset world-states)
- **M6:** Advanced Opposition (real coalition negotiations, parliament majority mechanics), Bundes/EU-Skalierung
- **Content:** More dilemmas, events, policies (sample set is MVP-sized)
- **Quality:** Playtesting, balance fine-tuning, player feedback integration

---

## Reference: Original Game-Design Roadmap (P0–P2, all complete)

See `docs/game-design-roadmap.md` for full context; summary:

**P0 "Baseline Simulation":**
- ✅ Policies with delayed effects (inertia), Budget, Political Capital, Voter-Groups
- ✅ Weekly → Monthly → Yearly fast-forward
- ✅ Election threshold, Wahl-Cycle (16 turns)

**P1 "Dilemma-Events & Effekt-Vorschau":**
- ✅ Dilemma-Events (pausieren advance_turn)
- ✅ Effekt-Vorschau (POST /preview)
- ✅ Policy-Repeal & Decay
- ✅ Namens-Vignetten

**P2 "Balance & Automation":**
- ✅ Balance-Runner (Dominante-Strategie-Check)
- ✅ Zufriedenheits-Momentum (EMA-Glättung)
- ✅ Randomisierte Startbedingungen
- ✅ Fast-Forward (mit Stopps bei Events/Dilemmas/Reports)

---

**This archive is final as of 2026-09-11. For active work, see `CLAUDE.md` M5+ and the main README.**
