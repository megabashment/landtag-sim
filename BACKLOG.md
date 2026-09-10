# BACKLOG — Landtag-Sim

Priorisierte Aufgabenliste nach Milestones. Speist sich aus:

- `docs/game-design-roadmap.md` (die urspruengliche 10-Punkte-Roadmap, **alle
  P0/P1/P2 erledigt**) — deren offene Anschluss-Ideen wandern hierher.
- `docs/architecture.md` "Bekannte offene Punkte" und "Bewusst zurueckgestellt".
- **Community-Recherche 2026-09-09** (Democracy 3/4 Steam-Diskussionen,
  Positech-Devblog, Genre-Nachbarn Frostpunk/Suzerain, Policymaking-Game-
  Designliteratur). Quellen unten. Diese Recherche ist der Grund, warum
  dieses File jetzt existiert.

Format je Punkt: **Titel** · Impact (1-5) × Aufwand (1-5, 1=klein) →
Milestone. Sortiert innerhalb eines Milestones nach Prioritaet.

Nach Abschluss: Checkbox hier abhaken, Umsetzungsnotiz in
`docs/architecture.md` oder `docs/game-design-roadmap.md`, ggf. `mistakes.md`.

---

## Recherche-Learnings 2026-09-09 (Meta-Mechaniken & Loops)

Verdichtet aus den Quellen unten. Jedes Learning ist die Begruendung fuer
mindestens einen Backlog-Punkt weiter unten.

- **L1 — "Kein Winning" ist eine Design-Haltung, keine Ausrede.** Cliff
  Harris (Democracy 4) sagt offen: "This is a sandbox game. Its not really
  about 'winning'." Das ist genau die Kritik der Spieler: nach der 2.-3.
  gewonnenen Wahl "nothing I did really mattered", stundenlanges Budget-
  Nachjustieren ohne spuerbare Veraenderung. **Wir haben schon eine echte
  Sieg/Niederlage-Wahl** (besser als Democracy) — aber KEIN Ziel *jenseits*
  der Wiederwahl. Der Loop trägt aktuell nur bis zur ersten Wahl.
- **L2 — "Situations" sind der fehlende mittlere Zeithorizont.** Democracys
  drittes Zeitraster (neben Einzel-Events und Dauer-Policies): ein
  Zustand, der bei Statistik-Schwelle X *entsteht*, sich **selbst
  verstaerkt** (eigener Effekt auf dieselbe/andere Statistiken) und erst
  bei einer *anderen*, niedrigeren Schwelle wieder verschwindet
  (Hysterese, z.B. an bei 0.6, aus erst bei 0.4). Das erzeugt Spiralen —
  positiv wie negativ — und damit "Story ohne Text". Landtag-Sim hat nur
  Events (einmalig) + Policies (dauerhaft, spielergesetzt). Der mittlere
  Layer fehlt komplett.
- **L3 — Selbstverstaerkende Loops brauchen eine Bremse, sonst sind sie
  unspielbar.** Harris' eigene Post-Mortem-Kritik an D3-Situations: die
  Kurven waren zu steil (-9% GDP sofort), einmal drin kam man nicht mehr
  raus ("death spiral"). Lehre fuer L2: Hysterese + gedaempfte Kurven +
  immer ein regelbasierter Gegen-Hebel (Policy oder Dilemma-Option), der
  raushilft.
- **L4 — Dilemma-Verteilung driftet.** D4-Devblog: mit ~100 Dilemmas
  liegt das Ziel bei 1% Trigger-Anteil je Dilemma; real triggern einige
  20×, andere nie. Positech trackt jeden Trigger (4 GB Datenbank) und
  balanciert datengetrieben nach. Unsere `mistakes.md` sagt dasselbe
  qualitativ: die meisten Trigger-Schwellen sind organisch unerreichbar.
  **Wir brauchen dieselbe Messung** (Trigger-Zaehler im Balance-Runner),
  bevor wir mehr Dilemma-Content schreiben.
- **L5 — Konsequenzen muessen SICHTBAR sein, nicht nur real.** D4s
  "Media Reports": Text-Nachrichten nach einer Entscheidung, die **keine**
  Sim-Werte aendern, sondern nur die Kausalkette benennen ("Firma X
  schliesst wegen deiner Arbeitsmarkt-Politik"). Bedingung: Policy-Kombi +
  Schwelle. Frequenz-gemanagt (nicht jede Runde, tritt zurueck hinter
  echte Events/Dilemmas). Wir haben `EffectAttribution` (Zahlen-Ebene) —
  aber keine narrative Konsequenz-Ebene. Billig zu bauen (Regex-Templates,
  passt zum Kein-LLM-Constraint), hoher Wirkungsgrad.
- **L6 — Wahl-Ueberraschung frustriert, wenn das Modell intransparent
  ist.** D4-Spieler verlieren "aus dem Nichts" (90% Prognose → 15%
  Ergebnis), weil Turnout/Apathie nicht im angezeigten Poll steckt:
  lauwarme Anhaenger bleiben zuhause, wuetende Gegner nicht. Wir haben
  gar keine Wahlprognose im Frontend und kein Turnout-Modell — beim
  Einbau der Prognose von Anfang an Turnout/Apathie sichtbar machen.
- **L7 — Late-Game-Automation-Falle.** D4: nach Elektoral-Dominanz kein
  Fortschrittsgefuehl mehr, GDP gedeckelt, teure Policies dauer-
  gegenfinanziert. Spieler wollen **verkettete Freischaltungen**: eine
  grosse gesellschaftliche Verschiebung soll neue Policies/Steuer-
  Instrumente/Optionen oeffnen, nicht ein isolierter Slider bleiben.
  Wir haben `Policy.requires` (statische Kette) — aber keine
  *dynamische* Freischaltung durch Statistik-Zustaende.
- **L8 — Opposition / Parlament ist der meistgenannte fehlende Layer.**
  D4-Community, wiederholt: (a) nach verlorener Wahl in die Opposition
  statt Game Over; (b) echte Koalitionsverhandlungen mit Kollapsrisiko
  statt Koalitionäre, die stumpf dieselbe Forderung wiederholen; (c)
  Parlament/Mehrheiten statt reiner Direktdurchgriff. Fuer uns: gross,
  klar Post-MVP, aber die **Datenstruktur** (Fraktionen mit Sitzen,
  Session-Rolle Regierung/Opposition) jetzt nicht verbauen.
- **L9 — Assassination/harte Zufalls-Strafen nerven, wenn entkoppelt.**
  D4-Spieler: Attentate von Gruppen, die einen gar nicht hassen; "in
  einem Spiel namens *Democracy* sollte die Hauptstrafe die verlorene
  Wahl sein". Lehre: Zufalls-Schocks (die wir laut `mistakes.md`
  brauchen, um Krisen-Dilemmas erreichbar zu machen) immer an einen
  Sim-Zustand koppeln, nie rein zufaellig, und Eskalation ueber
  Unruhe/Zustimmung statt ueber Insta-Fail.
- **L10 — Pacing/Debrief.** Policymaking-Game-Literatur (Nesta) +
  Genre: (a) klare Design-Pillars als Filter fuer jeden neuen Vorschlag;
  (b) "take players on a journey" — ein Bogen mit Debrief, nicht ein
  endloser Slider-Sandkasten. Wir haben Fast-Forward (gut) und
  Verlaufsansicht (gut), aber keinen Rueckblick/Score am Wahl- oder
  Legislaturende ("Deine Amtszeit in Zahlen").

---

## Offene Design-Fragen (vor Implementierung zu klaeren)

- ~~**F1:** Soll es ein Ziel *ueber* Wiederwahl hinaus geben?~~ **Geklaert
  mit B9 (2026-09-10): optionale, unverbindliche Ziele.** `ScenarioGoal`-
  Liste wird am Wahl-Turn in `TermSummary.goals` als ✓/✗ ausgewiesen,
  beeinflusst aber weder Sieg/Niederlage noch das Spielende — die Sandbox
  bleibt ohne Ziele spielbar, und verfehlte Ziele sind rein informativ.
- **F2:** Wieviel Simulations-Verkopplung wollen wir? Situations (B2)
  brauchen Statistik-→-Statistik-Effekte. Aktuell wirken nur Policies/
  Events/Dilemmas auf Statistiken, Statistiken nie aufeinander. Das ist
  ein bewusst gezogener Scope-Strich (README "kein echtes GDP-System").
  Situations weichen ihn auf — gewollt?
- **F3:** ~~Zufalls-Schocks ja/nein?~~ **Geklaert mit B3
  (2026-09-09): zustandsgekoppelte "Risiko-Events".** Eine Regel feuert
  nur bei erfuellter Statistik-Schwelle UND deterministischem
  Wuerfel-Durchgang pro Runde (`probability`, `zlib.crc32`-Seed) — nie
  rein zufaellig, nie ohne Sim-Bezug (L9). Umsetzung: siehe B3 unten.
- **F4:** ~~Turnout/Apathie-Modell (L6) — eigener Wert oder abgeleitet?~~
  **Geklaert mit B5 (2026-09-09): abgeleitet** aus `satisfaction` +
  `satisfaction_momentum` (`engine.py::_estimated_turnout`), kein neues
  persistiertes Feld. Nur die Prognose nutzt es; die echte Wahl bleibt
  ungewichtet.
- **F5:** ~~Media Reports (B4) — eigenes Modul oder Flag an `EventRule`?~~
  **Geklaert mit B4 (2026-09-09): eigenes Modul `reports.py` +
  `ReportRule`.** Andere Felder (`conditions`-Liste,
  `requires_policy`/`forbids_policy`), keine Effekte/Severity, eigene
  Frequenz-Regel — ein `silent`-Flag haette `EventRule` ueberladen.
- **F6:** ~~Wie messen wir Dilemma-Balance (L4) ohne echte Telemetrie?~~
  **Geklaert mit B6 (2026-09-09): ja, Balance-Runner-Zaehlung ueber
  Szenarien × N Seeds reicht als Proxy** (`collect_trigger_counts` /
  `classify_triggers`, `--seeds N`). Meldet "nie ausgeloest" und
  ">5× Erwartungswert".

---

## Milestone M2 — Tiefe des Kern-Loops (die Recherche-Kernpunkte)

Ziel: der Loop trägt ueber die erste Wahl hinaus. Reihenfolge ist die
empfohlene Implementierungsreihenfolge (jeder Punkt baut auf dem
vorherigen auf).

- [x] **B1 — Legislatur-Bogen & Amtszeit-Debrief** · Impact 4 × Aufwand 2 → M2
  - *Warum (L1, L10):* der Loop endet gefuehlt nach Wahl 1. Ein klarer
    Bogen + Rueckblick gibt jeder Partie eine Form.
  - *Scope:* Beim `ElectionResult` zusaetzlich eine `TermSummary`
    (Dataclass in `models.py`) zurueckgeben: Start-/End-Statistiken,
    groesste Verbesserung/Verschlechterung je Kategorie, Anzahl
    Dilemmas/Events, End-Budget, Zufriedenheits-Verlauf grob. Backend
    reicht sie im `AdvanceTurnResponse` weiter; Frontend zeigt eine
    "Amtszeit-Bilanz"-Karte beim Wahl-Turn.
  - *Kein Scope:* keine harte Szenario-Siegbedingung (das ist F1/B9).
  - *Anker:* `engine.py::advance_turn` (Wahl-Zweig, Zeile ~316),
    `sim/landtag_sim/models.py`, `routes_game.py`, `App.jsx` Sektion
    "Verlauf".
  - *Tests:* `TermSummary` wird nur am Wahl-Turn gesetzt; Deltas stimmen
    gegen einen bekannten 16-Runden-Lauf.
  - *Umgesetzt (2026-09-09):* `TermSummary`-Dataclass + `TurnResult.
    term_summary` in `sim/landtag_sim/models.py`; `SimState` traegt sechs
    `term_start_*`/`term_*_count`-Felder (lazy beim ersten Rundenwechsel
    befuellt, am Wahl-Turn ueber `_build_term_summary()` ausgewertet und
    danach auf den neuen Zyklus zurueckgesetzt). Bilanzinhalt:
    Start-/End-Runde, Start-/End-Zustimmung, Start-/End-Budget, Anzahl
    Dilemmas/Ereignisse, `statistic_changes` (Netto je Statistik) plus
    richtungs-korrigierte `category_changes` (economy/social/environment,
    positiv = besser fuer Waehler, nutzt `_STAT_DIRECTION`/`_STAT_CATEGORY`)
    und `biggest_improvement`/`biggest_decline`. Persistenz ueber sechs
    neue `GameSession`-Spalten + `sim_bridge.load_sim_state()`-Parameter;
    `AdvanceTurnResponse.term_summary` (`TermSummaryOut`). Frontend:
    "Amtszeit-Bilanz"-Panel (`term-summary`) oberhalb des Grids. Tests:
    6 sim-Engine-Tests (`sim/tests/test_engine.py`, Abschnitt "B1") und
    `backend/tests/test_term_summary.py` (nur am Wahl-Turn gesetzt,
    Policy-getriebene Deltas gegen einen 16-Runden-Lauf, Reset fuer den
    zweiten Zyklus). **Kein** Score-Gate/keine Siegbedingung (bewusst,
    siehe F1/B9).

- [ ] **B2 — Situations-Layer (mittlerer Zeithorizont, mit Hysterese)** · Impact 5 × Aufwand 4 → M2
  - *Warum (L2, L3):* der fehlende Layer zwischen Einzel-Event und
    Dauer-Policy. Erzeugt selbsttragende Spiralen = "Story ohne Text".
  - *Scope:*
    - Neue Dataclasses `SituationRule` (`key`, `statistic_key`,
      `activate_op`/`activate_threshold`, `deactivate_op`/
      `deactivate_threshold` → **Hysterese-Pflicht**, `effects:
      list[PolicyEffect]`, `template_text`) und `ActiveSituation`
      (`rule_key`, `since_turn`) in `models.py`.
    - Neues Modul `sim/landtag_sim/situations.py` (analog `events.py`):
      `evaluate_situations(state, rules)` → aktiviert/deaktiviert
      Eintraege in `SimState.active_situations` anhand der beiden
      Schwellen.
    - `engine.py::advance_turn`: nach Policy-Effekten, vor Events, die
      Effekte aktiver Situations anwenden (weich via `_effect_delta` mit
      `since_turn`), attribuiert als `situation:<key>`. Zufriedenheits-
      reaktion fliesst ueber `_apply_reaction` wie gehabt.
    - Startdatensatz: 2-3 Situations in `sample_data.py`, je mit einem
      klaren regelbasierten Gegen-Hebel (L3): z.B. `abwanderung`
      (an: `gdp_growth < -0.5`, aus: `> 0.5`, Effekt: druckt
      `unemployment_rate` weiter hoch → Spirale; Gegen-Hebel:
      `gesundheitsreform`/`bildungsoffensive` heben `gdp_growth`);
      eine *positive* Situation `gruenes_wachstum` (an: `renewable_share
      > 65`, Effekt: `gdp_growth +`, `co2_emissions -`).
    - `balance_runner.py`: meldet, welche Situations in einem Lauf
      je aktiviert wurden und ob eine nie wieder deaktiviert
      ("Death-Spiral-Verdacht", L3).
  - *Anker:* `engine.py::advance_turn`, `sim/landtag_sim/models.py`,
    `sim/landtag_sim/sample_data.py`, `backend/app/sim_bridge.py`
    (Persistenz von `active_situations`), neues DB-Modell
    `backend/app/models/situation.py` + `game_session`-Spalte.
  - *Tests:* Aktivierung bei X, KEINE Deaktivierung zwischen den beiden
    Schwellen (Hysterese), Deaktivierung erst unter der zweiten Schwelle;
    Effekt wird attribuiert; Gegen-Hebel-Policy holt eine negative
    Situation nachweislich wieder raus.
  - *Klaert:* F2.

- [x] **B3 — Zustandsgekoppelte Risiko-Events (Krisen erreichbar machen)** · Impact 3 × Aufwand 2 → M2
  - *Warum (L4, L9, `mistakes.md`):* die vorhandenen Krisen-Dilemmas
    (`arbeitsmarktkrise` etc.) triggern organisch nie. Reine Zufalls-
    Schocks waeren die faule Loesung und nerven (L9).
  - *Scope:* `EventRule`/`DilemmaRule` um ein optionales
    `probability: float = 1.0` erweitern: bei erfuellter Schwelle
    feuert die Regel nur mit dieser Wahrscheinlichkeit pro Runde
    (Seed aus `zlib.crc32(f"{rule.key}:{turn}")` → reproduzierbar,
    kein `random`, konsistent mit `vignettes.py`). Dann 1-2
    "Vorstufen"-Regeln mit *erreichbaren* Schwellen und `probability
    < 1.0`, die die Statistiken Richtung Krisenschwelle druecken (z.B.
    `konjunkturdelle`: `gdp_growth < 0.5` → 30%/Runde, kleiner
    negativer `gdp_growth`-Effekt → macht `rezession`/`arbeitsmarktkrise`
    organisch erreichbar).
  - *Anker:* `sim/landtag_sim/events.py`, `dilemmas.py`, `models.py`,
    `sample_data.py`.
  - *Tests:* Regel mit `probability=1.0` verhaelt sich wie bisher;
    `probability=0.0` feuert nie; gleicher Seed → gleiche Entscheidung;
    E2E: `rezession` wird ueber die Vorstufe in einem 40-Runden-Lauf
    tatsaechlich erreicht.
  - *Klaert:* F3 → **Entscheidung: zustandsgekoppelte "Risiko-Events"**
    (nicht "gar nicht", nicht "freie Zufalls-Events"). Eine Regel feuert
    nur, wenn ihre Statistik-Schwelle erfuellt ist UND ein
    deterministischer Wuerfel pro Runde durchgeht — nie rein zufaellig.
  - *Umgesetzt (2026-09-09):* `EventRule.probability` /
    `DilemmaRule.probability` (Default `1.0` = Verhalten wie vor B3).
    Gate-Funktion `events.py::passes_probability_gate(rule_key, turn,
    probability)` — `zlib.crc32(f"{rule_key}:{turn}")` normiert auf
    `[0,1)`, kein `random`; `dilemmas.py` importiert dieselbe Funktion
    (statt Copy-Paste wie bei `_severity`). Gate greift in
    `evaluate_events` / `evaluate_dilemmas` NACH dem Schwellenvergleich,
    VOR der Severity-Sortierung. Eine Vorstufe in `sample_data.py`:
    `konjunkturdelle` (EventRule, `gdp_growth < 0.5`, `probability=0.4`,
    `cooldown_turns=2`, Effekt `gdp_growth -0.35/Runde`) — greift nur bei
    ohnehin schwaechelndem Wachstum und macht `rezession` aus einer nur
    leicht negativen Lage heraus erreichbar (und via Situation
    `abwanderung` mittelbar auch `arbeitsmarktkrise`). Backend-
    Persistenz OHNE Schema-Migration: `probability` liegt im
    `trigger_condition`-JSON (`seed.py`), `sim_bridge.py` liest
    `cond.get("probability", 1.0)`. Tests: 6 sim-Engine-Tests
    (`sim/tests/test_engine.py`, Abschnitt "B3": `probability=1.0` wie
    vorher, `=0.0` feuert nie, Zwischenwert gated teilweise,
    Determinismus bei gleichem Seed, Dilemma-Gate, E2E `konjunkturdelle`
    → `rezession`) und `backend/tests/test_risk_events.py` (3, DB-Round-
    Trip des `probability`-Felds — beim naechsten lokalen Postgres-Lauf
    mit auszufuehren, hier mangels DB nicht gelaufen). Balance-Runner
    unveraendert bei "Keine vermutlich dominante Policy" / 12 von 24
    Szenarien mit Auffaelligkeiten (identisch zum Stand vor B3).

- [x] **B4 — Narrative Konsequenz-Ebene ("Presseschau")** · Impact 4 × Aufwand 2 → M2
  - *Warum (L5):* Konsequenzen sind aktuell nur Zahlen. Text-Feedback,
    das die Kausalkette benennt, ohne die Sim zu veraendern, ist Democracys
    wirkungsvollster Griff gegen "meine Entscheidungen sind folgenlos".
  - *Scope:* Neues Modul `sim/landtag_sim/reports.py` mit `ReportRule`
    (`key`, `conditions: list[(statistic_key, operator, threshold)]`
    — **UND-verknuepft**, optional `requires_policy`/`forbids_policy`,
    `template_text`, `cooldown_turns`). `advance_turn` wertet Reports
    NACH Events/Dilemmas aus und haengt max. 1 Report-Text an
    `TurnResult` (neues Feld `reports: list[str]`), aber **nur wenn diese
    Runde kein Dilemma und kein Event hatte** (Frequenz-Management, L5).
    Regex-Templates + `vignettes.py` fuer Namen — kein LLM.
    5-8 Startregeln in `sample_data.py`.
  - *Anker:* `engine.py::advance_turn` (nach Abschnitt 2b), `models.py`
    (`TurnResult.reports`), `templates.py`/`vignettes.py`, `routes_game.py`
    (`AdvanceTurnResponse`), `App.jsx` (Verlauf-Eintrag zeigt Reports).
  - *Tests:* Report feuert nur bei erfuellter UND-Bedingung; nicht in
    derselben Runde wie ein Event/Dilemma; Cooldown greift; Template-
    Platzhalter werden ersetzt.
  - *Klaert:* F5 → **Entscheidung: eigenes Modul `reports.py` mit
    `ReportRule`** (nicht ein `silent`-Flag an `EventRule`). Sauberere
    Trennung: Reports haben andere Felder (`conditions`-Liste,
    `requires_policy`/`forbids_policy`), keine Effekte, keine Severity,
    und eine eigene Frequenz-Regel (nur in ereignislosen Runden).
  - *Umgesetzt (2026-09-09):* `ReportCondition` / `ReportRule` +
    `TurnResult.reports` + `SimState.report_cooldowns` in `models.py`;
    neues Modul `sim/landtag_sim/reports.py::evaluate_reports(state, rules,
    active_policy_keys)` (UND-Bedingungen, Cooldown, requires/forbids-
    Policy-Gate, deterministische Sortierung nach `rule.key`). `engine.py::
    advance_turn` Abschnitt "2c": wertet Reports NUR aus, wenn diese Runde
    weder ein Event noch ein Dilemma hatte, haengt hoechstens EINEN Text an
    (mit Namens-Vignette passend zur Kategorie der ersten Bedingung), ohne
    jede Statistik-/Zufriedenheitswirkung. 7 Startregeln in `sample_data.py`
    (`SAMPLE_REPORT_RULES`), 4 davon policy-gekoppelt (`bildungsoffensive_
    wirkt`, `vermoegensteuer_debatte`, `klimaklage` (forbids), `mittelstand_
    lob`). Backend: `AdvanceTurnResponse.reports`; `sim_bridge.load_report_
    rules()` liefert die Regeln bewusst OHNE DB (reiner statischer Content,
    kein Session-Zustand — anders als Policies/Events/Dilemmas, siehe
    Docstring), `routes_game` reicht sie an `advance_turn` weiter. Frontend:
    eigenes "Presseschau"-Panel (zurueckhaltender Stil als das Ereignis-
    Panel) + Report-Zeilen in den Verlaufseintraegen; Fast-Forward stoppt
    auch bei einem Report. Tests: 11 sim-Engine-Tests (`sim/tests/test_
    engine.py`, Abschnitt "B4": UND-Bedingungen, Event-/Dilemma-
    Unterdrueckung, Cooldown `[1,4,7]`, Platzhalter, requires/forbids-Gate,
    "kein Sim-Effekt", Vignette, Well-formed-Check, E2E `bildungsoffensive_
    wirkt`) und `backend/tests/test_reports.py` (3, API-Transport — beim
    naechsten lokalen Postgres-Lauf mit auszufuehren). sim-Suite 80 gruen;
    Balance-Runner unveraendert (Reports haben keine Sim-Wirkung).

- [x] **B5 — Wahlprognose mit sichtbarem Turnout/Apathie** · Impact 3 × Aufwand 3 → M2
  - *Warum (L6):* Wahl-Ausgang ist aktuell eine Blackbox bis Turn 16.
    Eine Prognose macht die letzten Runden vor der Wahl spannend statt
    ueberraschend-frustrierend — vorausgesetzt, sie zeigt auch, WER
    wackelt und warum.
  - *Scope:*
    - `engine.py`: `_weighted_approval` um ein Turnout-Gewicht
      ergaenzen (F4-Entscheidung: abgeleitet aus `satisfaction` +
      Vorzeichen von `satisfaction_momentum` — sinkende Zufriedenheit
      unter ~40 senkt effektiven Stimmenanteil der Gruppe). Neue
      Funktion `project_election(state) -> ElectionProjection`
      (gewichtete Zustimmung + je Gruppe: Anteil, Zufriedenheit,
      geschaetzter Turnout, Trend).
    - Backend: `GET /sessions/{id}` liefert die Projection mit, wenn
      `turns_until_election <= 5`.
    - Frontend: kompakte "Wenn heute Wahl waere"-Leiste in den letzten
      5 Runden, pro Gruppe eine Zeile mit Trendpfeil.
  - *Anker:* `engine.py` (`_weighted_approval`, neue `project_election`),
    `models.py` (`ElectionProjection`), `routes_game.py` (`SessionOut`),
    `App.jsx`.
  - *Tests:* Projection == tatsaechliches `ElectionResult`, wenn Turnout-
    Gewicht neutral ist; niedrige+fallende Zufriedenheit einer grossen
    Gruppe senkt die projizierte Zustimmung staerker als niedrige+stabile.
  - *Klaert:* F4 → **Entscheidung: Turnout aus `satisfaction` +
    `satisfaction_momentum` ABGELEITET, kein neues persistiertes Feld.**
    L6 → die Prognose nennt exakt die entscheidungsrelevante Zahl
    (`approval` == echte Wahl), zusaetzlich eine turnout-gewichtete Zahl
    als Fruehwarnung.
  - *Umgesetzt (2026-09-09):* Abweichung vom Anker: `_weighted_approval`
    bleibt UNveraendert (die echte Wahl in `advance_turn` rechnet weiter
    ohne Turnout — kein Rebalancing von B1–B4/Balance-Runner noetig). Neu
    in `engine.py`: `_estimated_turnout(group)` (1.0, ausser fuer
    "lauwarm UND abkuehlend": `satisfaction` im Band [30, 55] UND
    `satisfaction_momentum < 0` → linear bis `TURNOUT_MIN = 0.6`, je
    steiler der Abfall; wuetende Gegner < 30 und zufriedene > 55 stimmen
    voll ab), `_turnout_weighted_approval`, `project_election(state) ->
    ElectionProjection`. `ElectionProjection` / `ElectionProjectionGroup`
    in `models.py`: `approval` (= echte Wahl, ohne Turnout),
    `turnout_adjusted_approval` (nur Anzeige), `threshold`, `would_win`,
    `groups[]` (Anteil, Zufriedenheit, Momentum, `estimated_turnout`,
    `trend` ∈ steigend/stabil/fallend). Backend: `SessionStateResponse.
    election_projection` (`ElectionProjectionOut`), nur gesetzt wenn
    `status == ACTIVE` und `turns_until_election <= ELECTION_PROJECTION_
    WINDOW = 5` (in `_build_state_response`, also auch in jeder
    `AdvanceTurnResponse.state`). Frontend: "Wenn heute Wahl waere"-Panel
    (`App.jsx`, `TrendArrow`) mit gewichteter + turnout-gewichteter Zahl
    und einer Zeile pro Gruppe (Zufriedenheit, Trendpfeil, Beteiligung%);
    CSS `.election-projection`. Tests: 8 sim-Engine-Tests (`sim/tests/
    test_engine.py`, Abschnitt "B5": `approval` == echtes `ElectionResult`,
    Turnout neutral ohne lauwarm-abkuehlende Gruppe, voller Turnout fuer
    stabil/steigend/wuetend/zufrieden, proportionaler Abfall, "abkuehlende
    Basis senkt `turnout_adjusted_approval`", Trend-Labels, `would_win` an
    der Schwelle) und `backend/tests/test_election_projection.py` (2,
    Fenster + Payload-Shape — beim naechsten lokalen Postgres-Lauf mit
    auszufuehren). sim-Suite 88 gruen; Balance-Runner unveraendert.

- [x] **B6 — Dilemma-/Event-Trigger-Telemetrie im Balance-Runner** · Impact 3 × Aufwand 1 → M2
  - *Warum (L4, F6):* bevor mehr Dilemma-Content geschrieben wird, muss
    messbar sein, was ueberhaupt organisch triggert. Positechs Ansatz im
    Kleinen.
  - *Scope:* `balance_runner.py` fuehrt je `EventRule`/`DilemmaRule`/
    (spaeter) `SituationRule` einen Trigger-Zaehler ueber alle
    Szenarien × M Seeds. Report am Ende: Trigger-Anteil je Rule,
    markiert "nie ausgeloest" und ">5× Erwartungswert". Optional
    `--seeds N`.
  - *Anker:* `sim/landtag_sim/tools/balance_runner.py`, Tests in
    `sim/tests/test_balance_runner.py`.
  - *Tests:* synthetischer Lauf mit einer nie-erreichbaren Regel →
    erscheint in "nie ausgeloest"; eine Dauer-Trigger-Regel → in
    "ueberrepraesentiert".
  - *Klaert:* F6 → **Ja, Balance-Runner-Zaehlung ueber Szenarien × Seeds
    reicht als Proxy.** Erwartungswert = Gleichverteilung (Gesamt-
    Ausloesungen der Kategorie / Anzahl Regeln, Democracy-4-Heuristik
    "~1% je Regel"), Overrep-Schwelle 5×.
  - *Umgesetzt (2026-09-09):* Kleiner, allgemein nuetzlicher Engine-
    Zusatz: `TurnResult.triggered_event_keys` (maschinenlesbarer Regel-Key
    des in der Runde gefeuerten Events — vorher nur der freie Text; Dilemmas
    via `pending_dilemma.rule_key`, Situations via `active_situations` waren
    schon strukturell auslesbar). Damit zaehlt der Runner EXAKT, ohne
    Cooldown-Heuristik. Neu in `balance_runner.py`:
    `collect_trigger_counts(turns, seeds, *, policies/…rules/combos)` spielt
    alle voraussetzungs-gueltigen Kombinationen × `seeds` gejitterte
    Startbedingungen (`_seeded_initial_state`, `jittered_starting_
    statistics(Random(seed))`) durch und zaehlt Event-/Dilemma-/Situation-
    Ausloesungen; `classify_triggers(counts, turns_simulated,
    overrep_multiplier=5.0)` (reine, isoliert getestete Klassifikation:
    `NIE_AUSGELOEST` / `UEBERREPRAESENTIERT` + Trigger-Anteil). CLI:
    `--seeds N` (Default 5). Anders als `run_scenario` (bleibt bewusst OHNE
    Situations, um den Dominante-Strategie-Check nicht zu verschieben)
    uebergibt die Telemetrie den VOLLEN Regelsatz inkl. Situations.
    Erste Erkenntnis aus dem Lauf: `niedrige_bildungsausgaben` (Event) und
    `gruenes_wachstum` (Situation) triggern organisch NIE; `arbeitsmarktkrise`
    ist dank B3 (`konjunkturdelle`→`abwanderung`) jetzt erreichbar (~1.5% der
    Runden) statt totes Gewicht. Tests: 6 neue in `sim/tests/test_balance_
    runner.py` (classify: NIE/UEBERREPRAESENTIERT/Anteil/Sortierung; collect:
    synthetisch nie- vs. dauer-erreichbar, Dilemma-/Situation-Zaehlung, plus
    ein Regressionstest, dass die zwei bekannt-unerreichbaren SAMPLE-Regeln
    bei 0 bleiben). sim-Suite 94 gruen. Hinweis: der B3-crc32-Wuerfel ist
    seed-unabhaengig (siehe `_seeded_initial_state`-Docstring) — Seeds
    streuen die Startwerte, nicht den Wuerfel.

---

## Milestone M3 — Systeme rund um den Loop

- [x] **B7 — Dynamische Policy-Freischaltung durch Sim-Zustand** · Impact 3 × Aufwand 3 → M3
  - *Warum (L7):* `Policy.requires` ist eine statische Kette. Spieler
    wollen, dass eine gesellschaftliche Verschiebung *neue* Optionen
    oeffnet ("Automatisierung hoch → neue Steuer-/Sozial-Policies
    verfuegbar").
  - *Scope:* `Policy.unlock_conditions: list[(statistic_key, operator,
    threshold)]` (zusaetzlich zu `requires`). `GET /policies` und die
    `advance_turn`-Vorpruefung filtern eine Policy raus, solange die
    Bedingungen nicht erfuellt sind; Frontend zeigt sie ausgegraut mit
    "Wird verfuegbar, wenn …". Braucht 2-3 Beispiel-Policies hinter
    Situations-/Statistik-Schwellen (Synergie mit B2).
  - *Anker:* `models.py`, `engine.py::_validate_prerequisites` (neue
    Schwester-Funktion `_validate_unlocks`), `routes_game.py::
    list_policies`, `App.jsx`.
  - *Umgesetzt (2026-09-10):* neuer Dataclass `UnlockCondition`
    (`statistic_key`/`operator`/`threshold`, bewusst eigener Typ statt
    Wiederverwendung von `ReportCondition` — Policy soll nicht vom
    Report-Konzept abhaengen) + `Policy.unlock_conditions`. Engine:
    `policy_is_unlocked(policy, statistics)` (oeffentlich, damit
    Backend/Frontend/Tests dieselbe Logik teilen), `_first_unmet_unlock`
    (lesbarer Hinweis), `_validate_unlocks` (in `advance_turn` VOR jeder
    Mutation, gegen den Statistik-Zustand VOR der Runde), neue Exception
    `PolicyLockedError`. Drei gesperrte Beispiel-Policies in
    `sample_data.py`: `digitalpakt_schulen` (`education_spending > 50`, via
    bildungsoffensive), `gruener_wasserstoff` (`renewable_share > 42`, via
    erneuerbare_foerderung), `arbeitsmarkt_sofortprogramm`
    (`unemployment_rate > 7`, via Krise/Situation `abwanderung` — Synergie
    B2). Abweichung von "filtern raus": Policies werden NICHT aus
    `GET /policies` entfernt (session-los, kennt keine Statistiken),
    sondern mit `unlock_conditions` ausgeliefert; das Frontend graut sie
    aus ("Wird verfuegbar, wenn …") und die Engine erzwingt hart
    (PolicyLockedError → 400 in `/advance`, `feasible=False` in `/preview`).
    Balance-Runner: `all_policy_combinations` laesst unlock-gated Policies
    weg (nur turn-0-enactbare Policies werden kombiniert — sonst nur
    gesperrt-Rauschen), NICHT_MACHBAR(gesperrt)-Zweig als Sicherheitsnetz
    fuer Direktaufrufe. Persistenz: neue JSON-Spalte
    `policy_definition.unlock_conditions` (Schema-Reset noetig, siehe
    Verifikations-Workflow) + `seed.py`/`sim_bridge.py`; API:
    `PolicyOut.unlock_conditions` (`UnlockConditionOut`). Tests: 6 neue
    sim-Engine-Tests (Abschnitt B7: `policy_is_unlocked` UND-Logik,
    Locked-raises-und-mutiert-nicht, unlocked-succeeds, Sample-Policies zu
    Start gesperrt, E2E digitalpakt via bildungsoffensive) + 2 im
    Balance-Runner (Combos schliessen gesperrte aus; Direkt-run_scenario
    meldet NICHT_MACHBAR(gesperrt)) + `backend/tests/test_unlock.py` (4,
    beim naechsten DB-Lauf). sim-Suite 102 gruen; Frontend build+lint gruen.

- [x] **B8 — Fraktions-/Sitz-Datenmodell (Grundstein Opposition/Parlament)** · Impact 2 × Aufwand 3 → M3
  - *Warum (L8):* der am haeufigsten gewuenschte fehlende Layer. Voll
    ausbauen ist Post-MVP, aber das Datenmodell jetzt richtig anlegen
    spart einen spaeteren Bruch (vgl. `architecture.md` Punkt 5, "nicht
    rueckwirkend aendern").
  - *Scope (nur Struktur, keine Mechanik):* `GameSession.role`
    (`GOVERNMENT`/`OPPOSITION`), `Faction`-Modell (`name`, `seats`,
    `stance_economy/social/environment`). Noch KEINE Koalitionslogik,
    KEIN Mehrheitszwang fuer Policies — nur Anzeige im Frontend
    ("Sitzverteilung im Landtag"). Bei Wahlniederlage optional
    `role = OPPOSITION` statt `SessionStatus.LOST` (hinter Flag).
  - *Anker:* neue `backend/app/models/faction.py`, `game_session`-Spalten,
    `sim_bridge.py`, `sample_data.py`.
  - *Explizit offen gelassen:* Koalitionsverhandlungen mit Kollapsrisiko,
    Parlaments-Abstimmung je Policy, Opposition-Gameplay-Loop — eigener
    Backlog-Punkt, wenn M3 steht.
  - *Umgesetzt (2026-09-10):* `Faction`-Dataclass (`sim/landtag_sim/
    models.py`) + `SAMPLE_FACTIONS` (5 generische Fraktionen, 135 Sitze) in
    `sample_data.py`; DB-Modell `backend/app/models/faction.py` (per Session,
    analog VoterGroup) + `SessionRole`-Enum + `GameSession.role`-Spalte.
    Seeding pro Session in `create_session` (wie VoterGroups). Anzeige:
    `SessionStateResponse.role` + `factions` (`FactionOut`, nach Sitzen
    sortiert); Frontend zeigt "Sitzverteilung im Landtag"-Panel + Rolle in
    der Status-Leiste. Wahlniederlage-Zweig hinter
    `routes_game.DEMOTE_TO_OPPOSITION_ON_LOSS` (Default False → weiterhin
    `LOST`; True → `role=OPPOSITION`, Session bleibt `ACTIVE`). **Bewusste
    Abweichung vom Anker:** Factions gehen NICHT durch `sim_bridge`/`SimState`
    — sie haben keine Sim-Wirkung, würden aber sonst jeden `clone()` pro Runde
    belasten; Backend liest sie direkt aus der `faction`-Tabelle. Tests: 1
    sim-Test (SAMPLE_FACTIONS well-formed) + `backend/tests/test_factions.py`
    (3: Struktur/Sortierung/Default-Rolle, LOST-Default, Opposition-Flag via
    monkeypatch). **Schema-Änderung**: neue Tabelle `faction` +
    `game_session.role`-Spalte (DB-Reset nötig; conftest baut Test-DB neu).
    sim 103 / backend 53 grün, Frontend build+lint grün.

- [x] **B9 — Szenario-/Legislatur-Ziele (optional, unverbindlich)** · Impact 3 × Aufwand 2 → M3
  - *Warum (L1, L10):* F1 geklaert: optionale, unverbindliche Ziele.
  - *Scope:* `ScenarioGoal` (models.py), `GoalResult` (key, description,
    met), `_goal_metric_value()` + `_evaluate_goals()` (engine.py,
    nutzt `_UNLOCK_OPERATORS` aus B7), `TermSummary.goals`. Vier
    Beispielziele in `SAMPLE_SCENARIO_GOALS` (klimaziel, arbeitsmarkt,
    solide_finanzen, rueckhalt). Backend: `load_scenario_goals()` in
    sim_bridge (ohne DB, statischer Content), `GoalResultOut` in
    TermSummaryOut. Frontend: ✓/✗-Liste in der Amtszeit-Bilanz.
    Verfehlte Ziele haben **keinen** Einfluss auf Sieg/Niederlage.
  - *Umsetzung 2026-09-10:* sim 107 / backend 55 grün, Frontend
    build+lint grün.

- [x] **B10 — `PolicyDefinition.description` mit echtem Text fuellen** · Impact 2 × Aufwand 1 → M3
  - *Warum (`architecture.md` offene Punkte):* totes Feld
    (`seed.py` setzte `description = policy.name`).
  - *Umsetzung 2026-09-10:* neues `Policy.description`-Feld (models.py),
    reine Anzeige — die Engine wertet es nicht aus. Alle 8 Beispiel-
    Policies mit ein bis zwei Saetzen Wirkungsbeschreibung (Haupteffekt
    + Trade-off) in `sample_data.py`. `seed.py` setzt jetzt
    `description=policy.description or policy.name`. Frontend rendert die
    Beschreibung unter jeder Policy im Katalog (`.policy-description`).
    Regressionstests: `test_every_sample_policy_has_a_real_description`
    (sim), erweiterte Assertion in `test_list_policies_returns_full_
    sample_catalog` (backend). sim 108 / backend 55 grün, Frontend
    build+lint grün.

- [x] **B11 — `docker-compose.yml` Frontend-Service** · Impact 1 × Aufwand 1 → M3
  - *Warum (`architecture.md` offene Punkte):* `docker compose up`
    startete nur `db`+`backend`, README versprach mehr.
  - *Umsetzung 2026-09-10:* neuer `frontend`-Service (`frontend/Dockerfile`,
    node:22-alpine, `npm run build` + `vite preview --host` auf Port 5173).
    `VITE_API_BASE` als Build-ARG (ins Bundle eingebacken), `FRONTEND_ORIGIN`
    des `backend`-Service jetzt per `${FRONTEND_ORIGIN:-…}` ueberschreibbar
    — beide aus einer optionalen `.env` im Repo-Root (`.env.example` neu),
    noetig fuers Testen vom Handy im LAN (LAN-IP statt localhost). Dabei
    einen vorbestehenden Bug im `backend/Dockerfile` mitbehoben: `pip install
    -r requirements.txt` scheiterte an der Zeile `-e ../sim` (Pfad existiert
    im Build-Kontext nicht) — wird jetzt vor der Installation rausgefiltert,
    die Sim-Engine kommt weiterhin separat aus `/sim`. `docker compose up
    --build` startet nun alle drei Services, end-to-end verifiziert
    (Session-Anlage, CORS-Preflight). README-Abschnitt "Alles mit Docker" +
    "Vom Handy im lokalen Netz testen" ergaenzt.

---

## Milestone M4 — Content & Daten (nach stabilem Systemgeruest)

- [x] **B12 — Dilemma-/Event-/Situations-Content-Ausbau** · Impact 3 × Aufwand 4 → M4
  - *Voraussetzung:* B6 (Telemetrie) muss stehen — sonst schreiben wir
    blind Content, der nie triggert (L4).
  - *Umsetzung 2026-09-10:* Events 3→8, Dilemmas 3→7, Situations 2→5.
    Bewusst **nicht** die urspruengliche 20/15/6-Zielgroesse angepeilt —
    L4 sagt Erreichbarkeit vor Menge; ein solider, komplett
    verifizierter Satz jetzt, mehr Content entlang derselben Achsen ist
    billiger Fast-Follow. Kern-Kniff: die Rezession (`abwanderung`) ist
    jetzt die zentrale Reichbarkeits-Achse — sie wirkt breit auf
    co2/healthcare/education/unemployment (milde Einzeleffekte, L3), womit
    die vorher toten co2-/healthcare-Krisenschwellen organisch erreichbar
    werden. `abwanderung`-Hysterese verbreitert (activate -0.2, deactivate
    0.9). Zwei bisher tote Regeln (`niedrige_bildungsausgaben`,
    `gruenes_wachstum`) repariert. Jede Statistik hat jetzt Krisen- UND
    Chancen-Content. Neuer Regressionstest
    `test_every_sample_rule_is_organically_reachable` (ersetzt den alten
    „diese Regeln bleiben bei 0"-Test) — Telemetrie-Sweep, faellt wenn
    neuer Content nicht triggert. Balance-Runner unveraendert „keine
    dominante Policy". sim 108 / backend 55 grün.
- [ ] **B13 — Echte Niedersachsen-Statistik-Importe** · Impact 2 × Aufwand 3 → M4
  - *Warum (`architecture.md`):* `data/` enthaelt nur Platzhalter-Module.
    LSN/Regionalstatistik.de-Startwerte fuer `STARTING_STATISTICS`
    verankern (Quellen-Doku in `data/README.md` existiert schon).
- [ ] **B14 — Policy-/Statistik-Icons + `CREDITS.md` befuellen** · Impact 1 × Aufwand 2 → M4
  - game-icons.net (CC-BY 3.0) / Kenney (CC0), jeder Eintrag mit
    Lizenzzeile in `CREDITS.md` (Pflicht laut `architecture.md` Punkt 9).

---

## Bewusst NICHT im Backlog (Scope-Grenzen bestaetigt durch Recherche)

- **Kein LLM fuer Text/Events** — bleibt hart (`CLAUDE.md`). B4 (Presseschau)
  und Vignetten decken das narrative Beduerfnis mit Regex-Templates ab.
- **Kein Buerger-/Einkommens-Individualmodell** — Democracys "Fixed Income
  Rewrite"-Schmerz (`architecture.md` Punkt 6) gilt nur bei Policies auf
  Klassen-/Personenebene. Solange Statistiken Landeswerte bleiben, kein
  Thema. Erst relevant, wenn je einkommensbezogene Policies auf
  Buergerebene kommen.
- **Kein Insta-Fail durch Attentat/Skandal** (L9) — Eskalation immer ueber
  Zustimmung/Unruhe, Hauptstrafe bleibt die verlorene Wahl.
- **Voller Opposition-/Koalitions-Gameplay-Loop** — nur das Datenmodell
  (B8), der Loop selbst ist explizit vertagt.

---

## Quellen (Recherche 2026-09-09)

- [Democracy 4 — "How to win the game?" (Steam, Dev-Antwort "sandbox, not about winning")](https://steamcommunity.com/app/1410710/discussions/0/3200370471674035223)
- [Democracy 4 — "Disappointed with late-game automation" (Steam)](https://steamcommunity.com/app/1410710/discussions/0/3088898048342489006/)
- [Democracy 4 — "Losing election out of nowhere?" (Steam, Turnout/Apathie)](https://steamcommunity.com/app/1410710/discussions/0/3058490685017920476/)
- [Democracy 4 — "Too Many Assassination Attempts" (Steam)](https://steamcommunity.com/app/1410710/discussions/0/2993169283948607260/)
- [Cliffski's Blog — Balancing Democracy 4 using stats and number crunching](https://www.positech.co.uk/cliffsblog/2021/01/27/balancing-democracy-4-using-stats-and-number-crunching/)
- [Cliffski's Blog — Consequences in Democracy 4 (Media Reports)](https://www.positech.co.uk/cliffsblog/2020/04/11/consequences-in-democracy-4/)
- [Cliffski's Blog — Democracy 3 and its situation mechanics. Broken in implementation? (Hysterese, Death Spirals)](https://www.positech.co.uk/cliffsblog/2016/05/08/democracy-3-and-its-situation-mechanics-broken-in-implementation/)
- [Cliffski's Blog — Democracy 4: The Fixed Income Rewrite](https://www.positech.co.uk/cliffsblog/2020/06/23/democracy-4-the-fixed-income-rewrite/)
- [Cliffski's Blog — Democracy 4 Multi Party Support / party politics refinement](https://www.positech.co.uk/cliffsblog/2022/04/08/yet-more-refinement-and-complexity-regarding-party-politics-in-democracy-4/)
- [Democracy 4 — Coalitions (Steam Discussion)](https://steamcommunity.com/app/1410710/discussions/0/3115896179323975934/)
- [Democracy 3 — General discussion regarding the mechanics of situations (Steam)](https://steamcommunity.com/app/245470/discussions/0/364040961443899185/)
- [Nesta — Five rules for designing a policymaking game](https://www.nesta.org.uk/report/ahead-of-the-game/five-rules-designing-policymaking-game/)
- [Game Developer — The Design Pillars of Eco](https://www.gamedeveloper.com/design/the-design-pillars-of-eco)
- [Frostpunk's Book of Laws — Player Decisions design analysis](https://gamedesignthinking.com/frostpunk-players-decisions/)
- [Suzerain review / design (kfjwrites, Strategineer — Konsequenzschwere)](https://strategineer.com/blog/2021-04-05/)
