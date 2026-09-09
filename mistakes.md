# mistakes.md — Gefundene und behobene Fehler

Log tatsächlich aufgetretener Bugs und Sackgassen in diesem Projekt, mit
Ursache, Fix und Lehre daraus. Zweck: dieselben Fehler nicht in einer
späteren Session wiederholen. Bitte **ergänzen statt löschen**, auch wenn
ein Fehler trivial wirkt — der Wert liegt in der Vollständigkeit.

---

## Event-Effekte flossen nie in die Wählerzufriedenheit ein

**Wo:** `sim/landtag_sim/engine.py::advance_turn`

**Was:** In der ursprünglichen Rundenreihenfolge wurden Events NACH der
Zufriedenheits-Berechnung ausgewertet und ihre Effekte erst danach auf
`new_state.statistics` angewendet. Die Zufriedenheits-Reaktion lief aber nur
über die zu diesem Zeitpunkt bereits gesammelten Policy-Attributionen —
Event-Effekte veränderten also Statistiken, wirkten sich aber **nie**, in
keiner Runde, auf die Wählerzufriedenheit aus.

**Gefunden:** Beim P0-Refactor (Zufriedenheits-Attribution einbauen) beim
Nachvollziehen der Rundenlogik aufgefallen, nicht durch einen fehlschlagenden
Test — es gab schlicht keinen Test, der das geprüft hätte.

**Fix:** Reihenfolge in `advance_turn` umgestellt: Events werden jetzt VOR
der Zufriedenheits-Berechnung ausgewertet, ihre Effekte fließen in dieselbe
`attributions`-Liste wie Policy-Effekte ein. Regressionstest ergänzt:
`test_event_effects_are_attributed_and_feed_into_satisfaction`
(`sim/tests/test_engine.py`).

**Lehre:** Bei mehrstufigen Berechnungen in einer Runde (Policies → Events →
Zufriedenheit → Wahl) die Reihenfolge explizit im Docstring begründen, nicht
nur implizit im Code-Layout. Ein Effekt, der "irgendwo" angewendet wird, aber
nirgends getestet wird, ob er auch wirkt, ist ein blinder Fleck.

---

## Totes Datenmodell-Feld: `turns_until_election` nie gelesen

**Wo:** `backend/app/models/game.py::GameSession.turns_until_election`

**Was:** Das Feld existierte im DB-Modell seit einer frühen Phase, wurde
aber von der Sim-Engine nirgendwo gelesen oder runtergezählt. Das Spiel
hatte dadurch faktisch kein Sieg-/Niederlage-Ziel — jede Partie lief
unbegrenzt weiter, Policy-Entscheidungen waren folgenlos.

**Gefunden:** Beim Senior-Game-Designer-Review (docs/game-design-roadmap.md,
P0-Punkt 2) als schwerwiegendste strukturelle Lücke identifiziert.

**Fix:** Feld in `SimState` (reine Engine, kein DB-Bezug) gespiegelt,
`advance_turn` zählt es jede Runde runter und berechnet bei 0 ein
`ElectionResult`. Siehe CLAUDE.md, Abschnitt "Wahlmechanik".

**Lehre:** Ein Feld im DB-Modell zu ergänzen fühlt sich wie Fortschritt an,
ist aber wirkungslos, solange keine Logik es liest. Bei jedem neuen Feld
sofort fragen: "Wer liest das, und wo wird das getestet?"

---

## Voter-Satisfaction-Vorzeichen invertiert

**Wo:** `sim/landtag_sim/engine.py` (Zufriedenheits-Reaktionsformel)

**Was:** Die erste Version der Reaktionsformel multiplizierte
`delta * category_weight`, ohne zu berücksichtigen, ob ein höherer Wert für
die jeweilige Statistik gut oder schlecht ist. Eine steigende
Arbeitslosigkeit hätte dadurch die Zufriedenheit ERHÖHT statt gesenkt.

**Gefunden:** Vor dem Ausliefern bemerkt (Code-Review vor Testlauf), nicht
durch einen fehlschlagenden Test.

**Fix:** `_STAT_DIRECTION`-Dict ergänzt (+1/-1 je Statistik), Reaktion wird
zusätzlich mit `_stat_direction(stat_key)` multipliziert.

**Lehre:** Bei jeder neuen Statistik **zwingend** `_STAT_CATEGORY` UND
`_STAT_DIRECTION` in `engine.py` pflegen — sonst wirkt der Effekt lautlos
invertiert. Der Balance-Runner deckt so etwas über die Trendrichtung der
Zufriedenheit auf, aber erst nachträglich; besser: beim Anlegen einer neuen
Statistik direkt einen gerichteten Test schreiben (siehe
`test_higher_unemployment_lowers_satisfaction` als Vorlage).

---

## Regex-Template-Rendering erzeugte kaputte Format-Strings

**Wo:** `sim/landtag_sim/templates.py`

**Was:** `("{" + fmt_spec[1:] + "}").format(context[key])` schnitt das
führende Zeichen des Format-Specs ab (z. B. `:.1f` → `.1f`), wodurch
`{.1f}` entstand — Python interpretiert das als Attributzugriff, nicht als
Formatierung. Ergebnis: `AttributeError` oder falsch gerenderter Text statt
z. B. "9.2%".

**Gefunden:** Durch fehlschlagenden pytest-Lauf.

**Fix:** Slice entfernt: `("{" + fmt_spec + "}").format(context[key])`.

**Lehre:** Bei String-Manipulation an Format-Specs lieber einen expliziten
Test mit einem konkreten erwarteten String schreiben, statt sich auf "sieht
richtig aus" zu verlassen.

---

## Fehlende `StatisticDefinition`-Seeds → Foreign-Key-Verletzung

**Wo:** `backend/app/seed.py`

**Was:** `POST /sessions` schlug mit
`IntegrityError: ForeignKeyViolation` auf `statistic_value.statistic_key`
fehl, weil `StatisticDefinition`-Zeilen nie geseedet wurden — die
Session-Erstellung schrieb `StatisticValue`-Zeilen für Keys, die es in der
Katalog-Tabelle noch nicht gab.

**Fix:** `ensure_statistic_catalog()` ergänzt, mit `STATISTIC_META`-Dict
(Label, Einheit, Kategorie pro Statistik-Key), aufgerufen aus
`run_all_seeds()`.

**Lehre:** Bei neuen Statistik-Keys in `sample_data.py` IMMER auch
`STATISTIC_META` in `seed.py` pflegen — sonst funktioniert die erste
Session-Erstellung auf einer frischen DB nicht, obwohl alle Tests grün sind
(Tests laufen gegen die reine Engine, nicht gegen die DB-Schicht).

---

## Docker-Build-Context: `COPY ../sim` ist ungültig

**Wo:** `backend/Dockerfile`, `docker-compose.yml`

**Was:** `COPY ../sim /sim` im Dockerfile scheiterte, weil Docker keine
Pfade außerhalb des Build-Contexts referenzieren kann (`../` verboten).

**Fix:** Build-Context in `docker-compose.yml` auf das Repo-Root gesetzt
(`context: .`), Dockerfile entsprechend auf `COPY sim /sim`,
`COPY backend/requirements.txt ./`, `COPY backend/. .` umgestellt.

**Lehre:** Sobald ein Docker-Image mehr als ein Verzeichnis braucht (hier:
`sim/` + `backend/`), Build-Context von Anfang an auf die gemeinsame
Elternebene legen, nicht auf das Unterverzeichnis des Hauptservices.

---

## `advance_turn`-Rückgabetyp-Wechsel (Tuple → `TurnResult`) brach Aufrufer

**Wo:** projektweit — `sim/tests/test_engine.py`,
`backend/app/api/routes_game.py`, `sim/landtag_sim/tools/balance_runner.py`

**Was:** Beim P0-Refactor wurde `advance_turn()` von
`tuple[SimState, list[str]]` auf ein `TurnResult`-Dataclass umgestellt
(wegen der neuen Felder `attributions` und `election_result`). Alle drei
Aufrufer nutzten noch Tuple-Unpacking (`state, _ = advance_turn(...)`) und
wären beim Ausführen sofort gecrasht, wenn die Reihenfolge "erst Engine
fertig schreiben, dann alle Aufrufer nachziehen" nicht eingehalten worden
wäre.

**Fix:** Alle drei Stellen aktualisiert, danach `pytest` + Balance-Runner +
kompletter API-Zyklus gegen frische DB verifiziert, bevor die Änderung als
abgeschlossen galt.

**Lehre:** Bei einer Breaking-API-Änderung an einer zentralen Funktion
NIEMALS Teilaufgaben als "erledigt" markieren, bevor projektweit nach allen
Aufrufern gesucht wurde (`grep -rn "advance_turn"`). Die Reihenfolge
Engine → Tests → Backend → Frontend → Doku hat sich bewährt, weil jede
Stufe die vorherige direkt verifizieren kann.

---

## Geräte-Bash auf dem Windows-Client dauerhaft nicht verfügbar

**Wo:** `mcp__remote-devices__device_bash` (Umgebung, kein Code-Fehler)

**Was:** Jeder Versuch, `device_bash` zu nutzen, scheiterte mit "Workspace
unavailable. The isolated Linux environment on this device failed to
start." — über alle bisherigen Sessions hinweg reproduzierbar.

**Fix/Workaround:** Kein direkter Fix möglich (Umgebungsproblem auf dem
Client). Etablierter Workaround: Dateien nach
`/mnt/user-data/outputs/<name>/` kopieren (Verzeichnisstruktur spiegeln),
dann `device_commit_files` mit `stagedPath` (unter `/mnt/user-data/outputs/`)
und explizitem `devicePath` pro Datei aufrufen. Direkte
`device_commit_files`-Aufrufe mit rohen Sandbox-Pfaden
(`/home/claude/...`) schlagen fehl ("stagedPath must be a file under
/mnt/user-data/outputs/").

**Lehre:** Nicht wiederholt versuchen, `device_bash` zum Laufen zu bringen
— das kostet nur Zeit. Direkt mit dem Copy-then-Commit-Workaround starten,
sobald eine neue Session beginnt und Dateien aufs Gerät sollen. Siehe auch
CLAUDE.md, Abschnitt "Bekannte Umgebungs-Einschränkung".

---

## Event-/Dilemma-Cooldowns wurden vom Backend nie persistiert

**Wo:** `backend/app/sim_bridge.py::load_sim_state`/`persist_sim_state`,
`backend/app/models/game.py::GameSession`

**Was:** `SimState.event_cooldowns` existierte von Anfang an in der reinen
Engine, aber `GameSession` (das DB-Modell) hatte dafür nie ein Feld.
`load_sim_state()` baute bei JEDER Anfrage ein `SimState` mit leerem
`event_cooldowns`-Dict, und `persist_sim_state()` schrieb es nie zurück.
Ergebnis: Cooldowns wirkten im laufenden, ueber die REST-API gespielten
Backend faktisch NIE — nur der Balance-Runner war davon nicht betroffen,
weil er denselben State durchgehend in einer Python-Variable haelt statt
ihn pro Runde aus der DB neu zu laden. Ein Event haette also theoretisch
jede Runde erneut feuern koennen, solange die Ausloese-Bedingung galt.

**Gefunden:** Beim Einbau der Dilemma-Cooldowns (P1-Punkt 4) aufgefallen —
ein Dilemma OHNE persistente Cooldowns waere unspielbar gewesen (haette
jede Runde direkt nach dem Aufloesen wieder ausgeloest, solange die
Statistik ueber dem Schwellenwert blieb), was den Bug fuer die bereits
laenger existierenden Event-Cooldowns erst sichtbar gemacht hat.

**Fix:** `GameSession` um `event_cooldowns: dict` und `dilemma_cooldowns:
dict` (beide JSON-Spalten) ergaenzt. `load_sim_state()`/`_load_state_for_
session()` laden sie jetzt aus der Session, `routes_game.py` schreibt sie
nach jedem `/advance` und `/resolve-dilemma` zurueck (analog zu
`political_capital`).

**Lehre:** Ein Feld, das nur in der reinen Sim-Engine existiert, aber vom
Backend bei jedem Request neu aus der DB aufgebaut wird, MUSS eine
Entsprechung im DB-Modell haben — sonst "vergisst" das Backend es bei jeder
Anfrage, waehrend Tests und der Balance-Runner (die denselben State
durchgehend im Speicher halten) den Bug nie sehen. Bei jedem neuen
`SimState`-Feld pruefen: "Wird das zwischen Requests gebraucht? Wenn ja,
wo genau auf der Session liegt das?"

---

## `StatisticValue`-Zeitreihe ohne Tiebreaker bei gleichem `turn_number`

**Wo:** `backend/app/sim_bridge.py::load_sim_state`

**Was:** Die Abfrage sortierte nur nach `turn_number`
(`.order_by(StatisticValue.turn_number)`), ohne Tiebreaker. Das war
unproblematisch, solange jede Runde genau einmal Werte fuer einen
`turn_number` schrieb. Mit `resolve_dilemma()` (P1-Punkt 4) aendert sich
das: eine Dilemma-Aufloesung schreibt NEUE `StatisticValue`-Zeilen fuer
DENSELBEN `turn_number` wie die Runde, die das Dilemma ausgeloest hat (weil
das Aufloesen bewusst keine Runde zaehlt). Ohne Tiebreaker war nicht
garantiert, dass die neueren (nach dem Aufloesen geschriebenen) Werte beim
naechsten Laden auch tatsaechlich gewinnen.

**Gefunden:** Beim Implementieren von `resolve_dilemma()` als potenzielles
Risiko erkannt, bevor es sich als sichtbarer Bug gezeigt hat (kein
fehlschlagender Test, sondern Code-Review vor dem Ausliefern).

**Fix:** Sekundaersortierung nach der Auto-Increment-`id` ergaenzt:
`.order_by(StatisticValue.turn_number, StatisticValue.id)` — spaeter
eingefuegte Zeilen fuer denselben `turn_number` gewinnen jetzt zuverlaessig.

**Lehre:** Sobald eine Zeitreihen-Tabelle mehr als eine Zeile pro
Zeitstempel bekommen kann (hier: weil eine Aktion bewusst keine neue
"Zeit" erzeugt), IMMER einen expliziten Tiebreaker in der Sortierung
einplanen — "letzter Wert gewinnt" ist nur so eindeutig wie die Sortierung,
die dahinter steht.

---

## Projekt hatte lange kein echtes Git-Remote, obwohl "Repository öffentlich" Anforderung war

**Wo:** Projektweit (Prozess-Fehler, kein Code-Bug)

**Was:** Der Nutzer hatte "Repository öffentlich" als harte Anforderung
ganz am Anfang des Projekts genannt. Ueber mehrere Phasen (P0, P1) wurde
ausschliesslich per `device_commit_files`-Workaround synchronisiert (siehe
Eintrag oben zu `device_bash`), OHNE je zu pruefen, ob ueberhaupt ein
Git-Remote existiert oder etwas gepusht wurde. Erst auf explizite
Nachfrage des Nutzers ("Hast du das gut gepusht?") kam heraus: das lokale
Git-Repo im Cloud-Workspace hatte nur einen einzigen alten Commit ohne
Remote, und der Windows-Ordner des Nutzers war ueberhaupt kein Git-Repo.

**Gefunden:** Durch direkte Nutzerfrage, nicht proaktiv.

**Fix/Status:** Der Nutzer hatte (vermutlich ueber eigene Tools/eine andere
Session) bereits `https://github.com/megabashment/landtag-sim` angelegt und
gepusht -- per Diff verifiziert, dass der Remote-Stand exakt dem lokalen
P0+P1-Arbeitsstand entspricht. Das lokale Git-Repo im Workspace wurde
danach auf `origin/main` ausgerichtet (`git checkout -B main origin/main`,
alte unabhaengige Historie blieb als `master`-Branch erhalten). Diese
Session kann aber NICHT selbst pushen (Proxy verweigert: Repo nicht in der
"authorized repository set" dieser Session) -- siehe CLAUDE.md, Abschnitt
"Git / GitHub".

**Lehre:** Bei einer expliziten Anforderung wie "Repository öffentlich"
IM VERLAUF DES PROJEKTS aktiv pruefen, ob sie bereits erfuellt ist (`git
remote -v`, `git log`), statt sie nur beim initialen Setup einmal zu
notieren und danach nie wieder zu verifizieren. Ausserdem: die
Faehigkeiten dieser Session sind nicht symmetrisch -- lesend auf ein
oeffentliches GitHub-Repo zugreifen (`fetch`/`clone`) funktioniert immer,
schreibend (`push`) braucht eine explizite Autorisierung, die nicht
automatisch aus "das Repo ist oeffentlich" folgt. Bei Unsicherheit frueh
mit einem risikolosen `git push` (z.B. wenn ohnehin nichts zu pushen ist)
testen, statt es stillschweigend anzunehmen.

---

## Verifikations-Workflow (`DROP DATABASE`+`CREATE DATABASE`) scheiterte mit "permission denied for schema public"

**Wo:** Backend-E2E-Test waehrend der P2-Umsetzung, Postgres 16 im
Cloud-Workspace. Betrifft den in `CLAUDE.md` dokumentierten
Verifikations-Workflow.

**Was:** `sudo -u postgres psql -c "DROP DATABASE ..."` gefolgt von
`CREATE DATABASE ...` (beides als Superuser `postgres`) erzeugt eine neue
Datenbank, deren `public`-Schema dem Superuser `postgres` gehoert -- NICHT
der App-Rolle `landtag` aus `DATABASE_URL`. Seit Postgres 15 hat `PUBLIC`
(alle Rollen) standardmaessig KEIN `CREATE`-Recht mehr im `public`-Schema
einer fremden Datenbank (vorher stillschweigend erteilt). Der App-Start
(`init_db()` -> `SQLModel.metadata.create_all(engine)`) scheiterte dadurch
beim allerersten `CREATE TYPE ... ENUM` mit
`psycopg2.errors.InsufficientPrivilege: permission denied for schema
public` -- obwohl exakt derselbe Befehlsablauf in frueheren Sessions
(vor Postgres 15/16 als Docker-Image-Version, oder mit bereits vorhandener
Rollen-Eigentuemerschaft) anstandslos funktioniert hatte.

**Gefunden:** Beim End-to-End-Test der P2-Backend-Aenderungen
(`satisfaction_momentum`-Persistenz, `jittered_starting_statistics`) --
`uvicorn` schlug beim Start fehl, Fehler stand direkt im Log.

**Fix:** Nach `CREATE DATABASE` zusaetzlich Eigentuemerschaft explizit auf
die App-Rolle uebertragen, BEVOR die App startet:

```bash
sudo -u postgres psql -c "DROP DATABASE IF EXISTS landtag_sim;"
sudo -u postgres psql -c "CREATE DATABASE landtag_sim;"
sudo -u postgres psql -d landtag_sim -c "ALTER DATABASE landtag_sim OWNER TO landtag;"
sudo -u postgres psql -d landtag_sim -c "ALTER SCHEMA public OWNER TO landtag;"
```

Falls die Rolle `landtag` in einer frischen Umgebung noch gar nicht
existiert: `sudo -u postgres psql -c "CREATE ROLE landtag LOGIN PASSWORD
'landtag';"` davor.

**Lehre:** Der `DROP DATABASE`+`CREATE DATABASE`-Schnipsel in `CLAUDE.md`
war unvollstaendig fuer Postgres-Versionen mit den seit v15 verschaerften
`public`-Schema-Standardrechten -- jetzt in `CLAUDE.md` direkt mit den
`ALTER ... OWNER TO`-Zeilen ergaenzt, damit kuenftige Sessions nicht erneut
denselben Fehler debuggen muessen. Allgemeiner: ein Verifikations-Schnipsel,
der frueher mal funktioniert hat, ist keine Garantie, dass er es mit der
aktuellen Postgres-Version im Workspace immer noch tut -- bei einem
Startup-Fehler zuerst den vollen Traceback lesen (hier stand die Ursache
klar in der letzten Zeile), statt vorschnell einen Code-Bug in den eigenen
Aenderungen zu vermuten.

## Dominante-Strategie-Check bestand trotz "Trade-off-Pflicht" -- der "Free Lunch"-Bug

**Wo:** Balance-Nachschaerfung nach P2, `sim/landtag_sim/sample_data.py`
(`bildungsoffensive`), aufgedeckt durch `balance_runner.py::
find_dominant_policies`.

**Was:** Jede Policy muss laut `test_every_sample_policy_has_at_least_one_
negative_effect` mindestens EINEN negativen Effekt haben --
`bildungsoffensive` erfuellte das technisch (`gdp_growth: -0.4`). Trotzdem
war sie in 100% der Top-Szenarien des Balance-Runners vertreten. Ursache:
die Policy hat ZWEI Effekte in derselben `_STAT_CATEGORY` ("economy") --
`unemployment_rate: -1.5` (gut) und `gdp_growth: -0.4` (schlecht) -- und der
positive Effekt ueberkompensierte den negativen im Netto-Aggregat der
Kategorie bei weitem. Ein Test, der nur "mindestens ein negativer Effekt"
prueft, erkennt das nicht -- er prueft Existenz, nicht Netto-Bilanz pro
Kategorie. Ergebnis: eine Policy, die sich wie eine reine Positiv-Policy
spielt, obwohl sie formal die Trade-off-Pflicht erfuellt ("Free Lunch").

**Gefunden:** `python -m landtag_sim.tools.balance_runner --turns 30`
meldete `bildungsoffensive: 100%` unter "vermutlich dominante Policies".
Eine erste Tuning-Runde (Magnitude von -0.4 auf -2.4 verschaerft) reduzierte
die Dominanz NICHT vollstaendig, weil ein zweiter, unabhaengiger Faktor
mitspielte: `steuersenkung_mittelstand.requires = ["bildungsoffensive"]`
sorgt strukturell dafuer, dass `bildungsoffensive` in praktisch jeder
"guten" Kombination auftaucht, die auch `steuersenkung_mittelstand`
enthaelt -- unabhaengig von der numerischen Balance. Bei nur 3 Policies
gibt es schlicht zu wenig unabhaengige Alternativen, um das zu verduennen.

**Fix:** Zwei Teile. (1) `gdp_growth`-Magnitude auf -2.4 verschaerft, damit
die Kategorie "economy" im Aggregat tatsaechlich netto negativ ausfaellt
(Regressionstest: `test_bildungsoffensive_has_a_genuine_net_negative_
economy_tradeoff`, prueft die Summe der Attributionen ueber 20 Runden, NICHT
nur die rohen Magnitudes). (2) Eine vierte, komplett unabhaengige Policy
(`gesundheitsreform`, kein `requires`) ergaenzt, die zusaetzlich eine echte
Luecke schliesst (`healthcare_quality` hatte zuvor ueberhaupt keine
Policy-Anbindung -- Regressionstest: `test_every_starting_statistic_is_
touched_by_at_least_one_policy`). Erst beide Teile zusammen brachten den
Balance-Runner auf "Keine vermutlich dominante Policy gefunden."

**Lehre:** "Jede Policy hat mindestens einen negativen Effekt" ist eine
Existenz-Pruefung, kein Balance-Garant -- zwei Effekte in DERSELBEN
Statistik-Kategorie koennen sich gegenseitig aufheben oder sogar
ueberkompensieren. Bei einer Dominanz-Meldung im Balance-Runner zuerst
pruefen, ob die Ursache numerisch ist (zu schwacher Trade-off) ODER
strukturell (eine `requires`-Kette ueberrepraesentiert eine Policy
kombinatorisch) -- eine rein numerische Korrektur behebt eine strukturelle
Ursache nicht, egal wie stark man die Zahlen dreht.

## Die meisten Event-/Dilemma-Schwellenwerte sind im organischen Spielverlauf unerreichbar

**Wo:** Analyse waehrend der Arbeit an neuen Dilemma-Inhalten
(`sim/landtag_sim/sample_data.py::SAMPLE_DILEMMA_RULES`,
`SAMPLE_EVENT_RULES`).

**Was:** Schwellenwerte wie `unemployment_rate > 9.0` oder
`education_spending < 30.0` (Startwerte liegen typischerweise weit davon
entfernt, z.B. `unemployment_rate` startet um 6) werden von KEINER
Beispiel-Policy in eine Richtung getrieben, die den Schwellenwert erreicht
-- die vorhandenen Policies bewegen Statistiken tendenziell in die
"gesunde" Richtung, nicht in Richtung Krise. Ohne gezielte SQL-Manipulation
(wie im Verifikations-Workflow fuer E2E-Tests beschrieben) feuern diese
Regeln in normalem Spielverlauf praktisch nie.

**Gefunden:** Beim Entwerfen zweier neuer Dilemmas wurde bewusst geprueft,
ob deren Trigger ueber die VORHANDENEN bzw. neu hinzugefuegten
Beispiel-Policies erreichbar sind (nicht nur "well-formed" im Sinne von
`test_sample_dilemma_rules_are_well_formed"), was den Blick auf die
bestehenden Regeln lenkte.

**Fix (bewusst NUR fuer die zwei neuen Dilemmas, nicht breit):**
`rezession` (`gdp_growth < 0.0`) nutzt `bildungsoffensive`s eigenen,
verschaerften `gdp_growth`-Trade-off (-2.4) als organischen Treiber;
`pflegeausbau` (`healthcare_quality > 68.0`) nutzt `gesundheitsreform`s
eigenen positiven Effekt (+12.0). Beide per Live-curl gegen `/advance`
UND per Regressionstest (`test_rezession_dilemma_is_reachable_via_sample_
policies`, `test_pflegeausbau_dilemma_is_reachable_via_sample_policies`)
bestaetigt: sie feuern innerhalb weniger Runden bei alleiniger Einfuehrung
der jeweiligen Policy, ohne sich gegenseitig oder `arbeitsmarktkrise`
spuerbar zu stoeren.

**Lehre:** Eine breite Behebung (z.B. zufaellige Wirtschafts-Schock-Events,
die Statistiken aktiv in Richtung Krise treiben) wurde bewusst NICHT
umgesetzt -- zu grosser Scope fuer diese Iteration. Wichtig ist aber, dass
kuenftige neue Event-/Dilemma-Regeln IMMER gegen die tatsaechlich
verfuegbaren Policy-Effekte auf Erreichbarkeit geprueft werden (nicht nur
auf Schema-Validitaet), sonst haeufen sich weitere "totgeborene" Regeln wie
`arbeitsmarktkrise`.
