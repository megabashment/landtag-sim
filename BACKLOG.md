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

- **F1:** Soll es ein Ziel *ueber* Wiederwahl hinaus geben (Legislatur-
  Ziele / "Amtszeit-Score" / Szenario-Siegbedingungen wie "CO2 unter X
  bis Legislaturende"), oder bleibt Landtag-Sim bewusst offener Sandbox
  mit Wiederwahl als einzigem Fixpunkt? → betrifft B1, B9.
- **F2:** Wieviel Simulations-Verkopplung wollen wir? Situations (B2)
  brauchen Statistik-→-Statistik-Effekte. Aktuell wirken nur Policies/
  Events/Dilemmas auf Statistiken, Statistiken nie aufeinander. Das ist
  ein bewusst gezogener Scope-Strich (README "kein echtes GDP-System").
  Situations weichen ihn auf — gewollt?
- **F3:** Zufalls-Schocks ja/nein? `mistakes.md` sagt, ohne sie bleiben
  Krisen-Dilemmas totes Gewicht. L9 sagt, wenn dann zustandsgekoppelt.
  Entscheidung: gar nicht / zustandsgekoppelte "Risiko-Events" / freie
  Zufalls-Events mit Seed.
- **F4:** Turnout/Apathie-Modell (L6) — eigener Wert pro Waehlergruppe
  (`turnout`), oder aus `satisfaction` + `satisfaction_momentum`
  abgeleitet (niedrige, sinkende Zufriedenheit → niedriger Turnout bei
  Anhaengern)? Letzteres ist billiger und braucht kein neues Feld.
- **F5:** Media Reports (B4) — eigenes Modul `reports.py` analog
  `events.py`, oder ein Flag an `EventRule` (`silent: bool`, kein Effekt,
  nur Text)? Eigenes Modul ist sauberer, aber mehr Code.
- **F6:** Wie messen wir Dilemma-Balance (L4) ohne echte Telemetrie?
  Vorschlag: Balance-Runner zaehlt Trigger je Rule ueber alle Szenarien
  × N Seeds und meldet Ueber/Unter-Repraesentation — reicht das als
  Proxy?

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

- [ ] **B3 — Zustandsgekoppelte Risiko-Events (Krisen erreichbar machen)** · Impact 3 × Aufwand 2 → M2
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
  - *Klaert:* F3.

- [ ] **B4 — Narrative Konsequenz-Ebene ("Presseschau")** · Impact 4 × Aufwand 2 → M2
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
  - *Klaert:* F5.

- [ ] **B5 — Wahlprognose mit sichtbarem Turnout/Apathie** · Impact 3 × Aufwand 3 → M2
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
  - *Klaert:* F4, L6.

- [ ] **B6 — Dilemma-/Event-Trigger-Telemetrie im Balance-Runner** · Impact 3 × Aufwand 1 → M2
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

---

## Milestone M3 — Systeme rund um den Loop

- [ ] **B7 — Dynamische Policy-Freischaltung durch Sim-Zustand** · Impact 3 × Aufwand 3 → M3
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

- [ ] **B8 — Fraktions-/Sitz-Datenmodell (Grundstein Opposition/Parlament)** · Impact 2 × Aufwand 3 → M3
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

- [ ] **B9 — Szenario-/Legislatur-Ziele (optional, hinter F1)** · Impact 3 × Aufwand 2 → M3
  - *Warum (L1, L10):* falls F1 "ja, es soll Ziele geben" ergibt: eine
    `ScenarioGoal`-Liste je Session ("`co2_emissions` unter X bis
    Legislaturende", "kein Budget-Defizit ueber 3 Runden"), im
    `TermSummary` (B1) als erfuellt/verfehlt ausgewiesen. Optionaler
    Layer, Sandbox bleibt ohne Ziele spielbar.
  - *Abhaengig von:* B1, F1.

- [ ] **B10 — `PolicyDefinition.description` mit echtem Text fuellen** · Impact 2 × Aufwand 1 → M3
  - *Warum (`architecture.md` offene Punkte):* totes Feld
    (`seed.py` setzt `description = policy.name`). Mit B4/L5 im Hinterkopf:
    kurze Wirkungsbeschreibung je Policy, im Frontend-Katalog + Tooltip.
  - *Anker:* `sim/landtag_sim/sample_data.py` (Text an `Policy` oder
    Parallel-Dict), `backend/app/seed.py`, `PolicyOut`, `App.jsx`.

- [ ] **B11 — `docker-compose.yml` Frontend-Service** · Impact 1 × Aufwand 1 → M3
  - *Warum (`architecture.md` offene Punkte):* `docker compose up`
    startet nur `db`+`backend`, README verspricht mehr. Kleiner
    Vite-Service ergaenzen oder README praezisieren.

---

## Milestone M4 — Content & Daten (nach stabilem Systemgeruest)

- [ ] **B12 — Dilemma-/Event-/Situations-Content-Ausbau** · Impact 3 × Aufwand 4 → M4
  - *Voraussetzung:* B6 (Telemetrie) muss stehen — sonst schreiben wir
    blind Content, der nie triggert (L4). Zielgroesse zunaechst ~15
    Dilemmas, ~20 Events, ~6 Situations, jeweils an unterschiedliche
    Statistiken/Policy-Kombis gekoppelt, mit Balance-Runner-Nachweis der
    Erreichbarkeit.
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
