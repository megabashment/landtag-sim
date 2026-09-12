# M7 Sprint Plan — Content-Ausbau & Opposition-Gameplay

**Meilenstein M7:** Content-Expansion, Opposition-Verbesserungen, Bundesländer-Skalierung
**Target:** 2026-09-15 bis 2026-10-15
**Status:** Phase 1+2 abgeschlossen (B25-B28, 2026-09-12). Nur Phase 3 (B29) offen.

---

## Übersicht: 5 Features, gruppiert in 3 Phasen

| Phase | Feature | B# | Impact | Aufwand | Priorität |
|-------|---------|-----|--------|---------|-----------|
| **P1** | Event/Dilemma-Expansion | B25 | 4 | 3 | **P0** |
| **P1** | Opposition-Kampagnen UI | B26 | 3 | 2 | **P1** |
| **P2** | Bundes-Skalierung (Nds+Bayern) | B27 | 4 | 5 | **P1** |
| **P2** | Advanced UI (Party-History, Coalition-viz) | B28 | 2 | 3 | **P2** |
| **P3** | Playtesting & Balance-Audit | B29 | 3 | 2 | **P0** |

---

## **Phase 1 (Woche 1-2): Content + Opposition Polish**

### B25: Event/Dilemma-Expansion ✅ DONE (2026-09-12)
**Ziel:** Spielerlebnis diversifizieren, weniger Wiederholungen

**Scope:**
- Events von 8 → 14 (7 neue), Dilemmas von 7 → 12 (5 neue)
- Situations bleiben (5, bereits gut balanciert)
- Neue Events: Fachkräftemangel, Stadtentwicklung, Energie-Krise, Pandemie-Echos, Arbeitsmarkt-Boom, Innovations-Hub, Soziale-Unruhen
- Neue Dilemmas: Zuwanderung-Policy, Arbeitszeit-Flexibilität, Tech-Regulierung, Verkehrswende, Schulreform

**Impl:**
- Neue `EventRule`/`DilemmaRule` in `sample_data.py`
- Balancetest: Balance-Runner mit neuen Rules
- Frontend: keine UI-Änderungen (existing event/dilemma UI reused)
- Tests: 8 neue Sim-Tests für neue Trigger

**Files:**
- `sim/landtag_sim/sample_data.py` (+300 LoC)
- `sim/tests/test_engine.py` (+8 tests)

**Ergebnis:** Events 8→14 (`wirtschaftsboom`, `energiewende_erfolg`,
`pflege_fruehwarnung`, `bildungssparzwang`, `jobmotor`, `energiewende_ausbau`),
Dilemmas 7→12 (`fachkraeftezuwanderung`, `energiewende_ausbaustufe`,
`bildungsnotstand`, `verkehrswende`, `tech_regulierung`) — Namen weichen
von den urspruenglich vorgeschlagenen ab (auf die 6 bestehenden Statistiken
zugeschnitten, keine neuen Stats). Balance-Runner bestaetigt organisches
Ausloesen fuer alle neuen Regeln (kein NIE_AUSGELOEST). Dabei eine
Schwellwert-Falle gefunden + gefixt (`verkehrswende` zu nah am Jitter-Band,
siehe `mistakes.md`).

---

### B26: Opposition-Kampagnen UI Verbesserung ✅ DONE (2026-09-12)
**Ziel:** Opposition-Modus spielbarer machen, Kampagnen sichtbar

**Scope:**
- Opposition-Kampagnen aus Backend laden (statt hardcodiert)
- `GET /opposition-campaigns` Endpoint (Kampagnen + Effekt-Vorschau)
- Frontend: Kampagnen-Katalog-Panel (wie Policy-Katalog, aber für Opposition)
- Kampagnen-Effekte Preview (Zufriedenheits-Deltas pro Gruppe)
- Opposition-Mode Indikator in StatusBar ("Du bist in Opposition")

**Impl:**
- `load_opposition_campaigns()` in `sim_bridge.py`
- API: `GET /opposition-campaigns` Route
- Schema: `OppositionCampaignOut` (key, name, description, capital_cost, satisfaction_deltas)
- Frontend: new `OppositionCampaignPanel` component
- CSS: style opposition campaign cards like policy cards

**Files:**
- `backend/app/api/routes_game.py` (+15 lines)
- `sim/landtag_sim/sample_data.py` (expand OPPOSITION_CAMPAIGNS)
- `backend/app/schemas/game.py` (OppositionCampaignOut)
- `frontend/src/App.jsx` (OppositionCampaignPanel)
- `frontend/src/App.css` (+50 lines)
- `backend/tests/test_opposition.py` (new, 3 tests)

**Tests:**
- Backend: campaign loading, serialization
- Frontend: campaign panel renders, preview works

**Ergebnis:** Zusaetzlich zum geplanten Scope ein latenter Bug gefunden +
gefixt: `SAMPLE_OPPOSITION_CAMPAIGNS.satisfaction_deltas` referenzierte
Waehlergruppen-Namen, die in keiner `SAMPLE_VOTER_GROUPS`-Gruppe existierten
(z.B. "Arbeitnehmer" statt "Industriearbeiter") -- jede Kampagne war dadurch
seit ihrer Einfuehrung wirkungslos fuer die Koalitionsfaehigkeits-Berechnung
(`engine.py::_calculate_coalition_viability` schlaegt per `vg.name` nach).
Kampagnen 4→6. `backend/tests/test_opposition.py` (3 Tests) prueft jetzt
explizit, dass alle `satisfaction_deltas`-Keys echte Gruppennamen sind.

---

## **Phase 2 (Woche 3-4): Skalierung + UI**

### B27: Bundes-Skalierung (Multi-State Support) ✅ DONE (2026-09-12)
**Ziel:** Bundesländer-Verwaltung, State-Switching in Session

**Scope:**
- `Bundesland` Model (aktuell nur Niedersachsen hardcodiert)
- Feste Liste: Niedersachsen, Bayern, NRW (später erweiterbar)
- Session.admin_unit_id Foreign Key bleibt, aber jedes Bundesland hat eigene Statistik-Baseline
- `GET /bundeslaender` — verfügbare States auflisten
- `POST /sessions/new-bundesland/{bundesland_key}` — Session mit State-Baseline starten
- Kein UI-State-Switching in laufender Session (zu komplex für M7)

**Impl:**
- `backend/app/models/admin_unit.py` (Bundesland Model bereits da, nur erweitern)
- `sample_data.py`: Baseline-Statistiken pro Bundesland (Bayern: mehr Wirtschaft/Bildung, NRW: mehr Industrie/Arbeit)
- Neue Seeds: `seed_bayern()`, `seed_nrw()` (analog zu `seed_niedersachsen()`)
- Routes: `list_bundeslaender()`, `create_session_from_bundesland()`
- Frontend: State-Auswahl im Start-Menu (vor Scenario/Party-Choice)

**Files:**
- `backend/app/models/admin_unit.py` (expand)
- `sim/landtag_sim/sample_data.py` (+100 lines für Bayern/NRW Baselines)
- `backend/app/seed.py` (3 neue seed functions)
- `backend/app/api/routes_game.py` (+30 lines)
- `backend/app/schemas/game.py` (BundeslandOut)
- `frontend/src/App.jsx` (State-Selection component)
- `backend/tests/test_bundeslaender.py` (new, 5 tests)

**Tests:**
- Baseline-Validierung (Bayern GDP höher als Nds, etc.)
- State-Switch isolation (Sessions unabhängig)
- Balance pro State (Balance-Runner mit Bayern/NRW)

**Ergebnis:** `BundeslandDefinition` als sim-seitiges Dataclass (analog
`ScenarioDefinition`), 3 States mit vollstaendiger eigener Baseline (kein
Override). `jittered_starting_statistics()` bekam einen `base=`-Parameter,
damit jedes Bundesland um seine EIGENE Baseline streut statt immer um
Niedersachsen. `balance_runner.py --state` bestaetigt "keine dominante
Policy" fuer alle 3 States. Dabei zwei Bugs in bestehendem Code gefunden +
gefixt: `SessionStateResponse` hatte `party_id`/`party_name`/
`party_ideology` nie (nur `CreateSessionResponse`) -- der B23-Ideologie-
Bonus-Badge zeigte sich dadurch de facto nie im Frontend; und der Header
zeigte immer hart codiert "Niedersachsen" statt des echten Bundeslands.
Beides ergaenzt (`admin_unit_name`-Feld neu). Bayern startet DETERMINISTISCH
(nicht zufaellig) mit dem `fachkraeftezuwanderung`-Dilemma pending (Baseline
liegt komplett unter dessen Schwelle) -- bewusstes Design-Feature, siehe
Kommentar in `sample_data.py`.

**Nicht in M7:**
- Bundes/EU-Ebene (zu komplex, M8+)
- Cross-State-Effekte
- Föderale Verhandlungen

---

### B28: Advanced UI — Party-History + Coalition-Viz ✅ TEILWEISE DONE (2026-09-12)
**Ziel:** Spieler-Orientierung verbessern, Meta-Progress sichtbar

**Scope:**
- Party-Detail-Modal: History, Terms, Reputation-Trend
  - Graph: Ruf über Zeit (Legislaturen)
  - Tabelle: Term-Liste (Legislatur, Wahl-Ergebnis, Ruf-Delta, Punkte-Diff)
- Coalition-History in Election-Result: zeigen ob Coalition akzeptiert/declined wurde
- Opposition-Satisfaction-Meter in Sonntagsfrage (zeige Opposition-Zufriedenheit prozentual)
- Session-Dauer-Info ("Legislatur 3 von 5 Runden gespielt")

**Impl:**
- Schema: `PartyDetailOut` (include terms mit win/loss/reputation-delta)
- API: `GET /parties/{id}/detail` — Party mit kompletter History
- Frontend: new `PartyDetailModal` component
- CSS: History-Graph (einfacher Canvas oder SVG bar chart)
- Sonntagsfrage: Opposition-Satisfaction-Bar hinzufügen

**Files:**
- `backend/app/api/routes_game.py` (+20 lines)
- `backend/app/schemas/game.py` (PartyDetailOut, TermDetailOut)
- `frontend/src/App.jsx` (PartyDetailModal component)
- `frontend/src/App.css` (+80 lines für History-Visualisierung)

**Tests:**
- Party-Detail API returns correct history
- Frontend renders modal without crashes

**Ergebnis:** Party-Detail-Modal (Ruf-Verlauf als Balkengraph + Term-Tabelle)
und Session-Dauer-Info ("Legislatur N (Runde X von 16)") umgesetzt.
Opposition-Satisfaction-Meter in der Sonntagsfrage war bereits VOR B28
vorhanden (M5/M6-Arbeit, `oppositionProzent`-Balken in
`SonntagsfragOverlay`) -- kein neuer Code noetig. **Nicht umgesetzt:**
Coalition-History im Election-Result (ob eine Koalition akzeptiert/
abgelehnt wurde, wird aktuell nirgends persistent protokolliert) -- als
offener Rest fuer B29 oder einen spaeteren Sprint vermerkt.

---

## **Phase 3 (Woche 5): Validierung + Polish**

### B29: Playtesting & Balance-Audit
**Ziel:** Sicherstellen dass Gameplay-Loop stabil bleibt unter neuen Features

**Scope:**
- Balance-Runner mit allen 3 States + 5 Scenarios: "keine dominante Policy pro State"
- Neue Events/Dilemmas sollten nicht unfair sein (Schwellenwerte kalibrieren)
- Opposition-Kampagnen balance check: Sind einige Kampagnen zu stark?
- Manual 10-Game Testlauf (verschiedene Szenarien, States, Party-Strategien)
- Bug-Report-Sammlung + Fix-Priorisierung

**Impl:**
- ~~`balance_runner.py` erweitern: --state flag (niedersachsen|bayern|nrw)~~ **bereits in B27 erledigt**
- Test-Suite: `test_balance_all_states.py` (neue Events/Dilemmas getestet)
- Dokumentation: Balance-Notes in `docs/balance-notes.md` schreiben
- Bug-Tracking: `KNOWN_ISSUES.md` aktualisieren

**Files:**
- `sim/landtag_sim/tools/balance_runner.py` (+40 lines)
- `sim/tests/test_balance.py` (+10 tests)
- `docs/balance-notes.md` (new, 100 lines)

**Tests:**
- Balance-Runner grün für alle 3 States
- No critical bugs in 10-game manual test
- New Events/Dilemmas have sane probability-gates

---

## **Success Criteria für M7**

| Kriterium | Target |
|-----------|--------|
| **Tests** | 130+ Sim-Tests, 70+ Backend-Tests, Frontend build sauber |
| **Features** | Alle 5 B-Nummern implementiert + getestet |
| **Balance** | Balance-Runner grün für Nds + Bayern + NRW, alle Scenarios |
| **Content** | 14 Events, 12 Dilemmas, 3 States, Opposition-Katalog sichtbar |
| **UI** | Kein Game-Breaking Bugs, Party-History lesbar, Coalition-Viz klar |

---

## **Reihenfolge (Empfohlen)**

1. **B25 zuerst** (Content-Add ist niedrig-Risiko, gibt schnelle Wins)
2. **B26 parallel zu B25** (Opposition-UI, kurz, unabhängig)
3. **B27 nach B25+B26** (Skalierung, braucht stabile Base)
4. **B28 nach B27** (UI-Polish, non-critical)
5. **B29 ganz am Ende** (Audit + Fixes basierend auf vorangegangenen)

---

## **Abhängigkeiten & Integrationspunkte**

- **B25 → B29:** Balance-Runner muss neue Events testen
- **B26 → B29:** Opposition-Kampagnen müssen ausgebalanciert sein
- **B27 → alles:** State-Baseline unterscheidet sich, alle Features müssen State-agnostisch sein
- **B28 → B27:** Party-History hängt von Term-Tracking ab (bereits done in B20/M5)

---

## **Open Questions**

1. **Wie viele Events/Dilemmas sind genug?** Aktuell 8+7, Target 14+12 (verdoppelt). Gut?
2. **Sollen Opposition-Kampagnen State-spezifisch sein?** (z.B. Bayern: Industrie-Kampagne?) → Nein für M7, später
3. **Sollte man während Wahl auch Option für State-Wechsel geben?** → Nein, zu komplex, Session bleibt im State
4. **Playtesting: User-Testing oder nur Claude-Tests?** → Nur Claude für M7, User-Testing später (M8)

---

**Nächster Schritt:** Starten wir mit **B25 (Event/Dilemma-Expansion)** oder lieber **B26 (Opposition-UI)** zuerst?
