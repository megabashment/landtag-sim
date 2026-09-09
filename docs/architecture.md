# Architekturentscheidungen (ADR-Log)

Kurzform in der Haupt-[README.md](../README.md); hier die ausfuehrliche
Begruendung pro Entscheidung, chronologisch aus dem Projekt-Setup-Gespraech.

## 1. Client/Rendering: React (Vite) im Browser

Alternativen waren Godot (bessere Pixel-Art-Kontrolle) und ein Tauri/
Electron-Wrapper. Entscheidung fuer React, da das Spiel UI-/Daten-lastig ist
(Statistiken, Karten, Formulare) statt sprite-/animationslastig, und der
Nutzer bereits mit React/FastAPI vertraut ist.

## 2. Kommunikation: REST, rundenbasiert

Kein WebSocket im MVP. Passt zum rundenbasierten Spielprinzip (Client sendet
Policy-Entscheidungen, Server rechnet eine Runde, gibt neuen State zurueck).
WebSocket waere erst noetig fuer Multiplayer/Zuschauer-Modus -- explizit
nicht im MVP-Scope.

## 3. Simulation serverseitig, Rendering lokal

Sim-Zustand lebt ausschliesslich im Backend/der Datenbank. Der Client ist
zustandslos bezueglich der Spiellogik und zeigt nur an, was das Backend
zurueckgibt. Verhindert Client-seitiges Cheating und haelt die Spiellogik an
einer Stelle testbar.

## 4. PostgreSQL von Anfang an (nicht SQLite)

Bewusste Entscheidung gegen "erstmal SQLite, spaeter migrieren", um spaetere
Mehrnutzer-/Mehrpartien-Szenarien nicht durch einen Datenbankwechsel
mitten im Projekt zu erschweren.

## 5. Regio-Scope: Niedersachsen statt ganzes Land

Kleinerer, handhabbarer Datensatz fuer den MVP. Wichtige Konsequenz: die
urspruenglich geplanten nationalen Datenquellen (Weltbank, V-Dem) passen
nicht direkt -- siehe [data/README.md](../data/README.md) fuer die
Korrektur (LSN/Regionalstatistik.de statt Weltbank fuer den MVP).

**Skalierungspfad Region -> Nation -> EU ist ein Meta-Ziel, kein MVP-Feature.**
Das Datenmodell (`AdminUnit` mit `level` + selbstreferenzierendem `parent_id`
in `backend/app/models/admin_unit.py`) ist so gebaut, dass eine hoehere
Ebene spaeter nur neue Zeilen braucht, keine Schema-Aenderung. Ob und wann
dieser Weg tatsaechlich gegangen wird, ist offen.

## 6. Kein LLM/NLP fuer Text-/Ereignisgenerierung

Explizite Anforderung: reines Scripting/Regex. Umgesetzt als zwei getrennte
Bausteine:
- `sim/landtag_sim/events.py`: deterministische Schwellenwert-Vergleiche
  (Operator-Dict, kein Ausdrucksparser).
- `sim/landtag_sim/templates.py`: Regex-basiertes Platzhalter-Ersetzen in
  vordefinierten Text-Templates.

## 7. Traegheitsmodell fuer Policy-Effekte

Effekte wirken verzoegert (`delay_turns`) und naehern sich danach exponentiell
geglaettet ihrem Zielwert an (`inertia`, seit dem Game-Director-Review unten
-- urspruenglich ein festes `duration_turns`-Zeitfenster, das nach der Review
verworfen wurde). Naeher am Democracy-Gefuehl, aber schwerer von Hand zu
balancieren -- deshalb der headless Balance-Runner
(`sim/landtag_sim/tools/balance_runner.py`), der alle Policy-Kombinationen
automatisiert durchspielt und Budget-Kollaps, eingefrorene oder an die
Grenze laufende Zufriedenheit markiert.

## 8. Sim-Engine als eigenes, DB-freies Package

`sim/` ist bewusst kein Teil von `backend/app`, sondern ein eigenes,
editable-installierbares Python-Package (`landtag_sim`). Grund: der
Balance-Runner muss hunderte Szenarien schnell durchrechnen koennen, ohne
eine Postgres-Verbindung zu brauchen. `backend/app/sim_bridge.py` ist die
einzige Stelle, die zwischen DB-Modellen und den reinen Sim-Datenklassen
uebersetzt.

## 9. Assets: nur offen lizenziert, nicht zwingend CC0

Siehe [CREDITS.md](../CREDITS.md). Empfehlung: game-icons.net (CC-BY 3.0)
fuer Policy-/Statistik-Icons, OpenMoji (CC BY-SA 4.0, Copyleft beachten)
fuer Flaggen, Kenney.nl (CC0) als Luecken-Fuellung. OpenGameArt.org/itch.io
nur nach Einzelpruefung der jeweiligen Pack-Lizenz.

## 10. Repository oeffentlich

Kein privates Repo -- Konsequenz: keine Secrets committen (siehe
`.gitignore`), `.env.example` statt `.env` einchecken.

## Game-Director-Review (nach MVP-Setup, vor weiterem Ausbau)

Externe Recherche zu den tatsaechlichen Mechaniken von Democracy 3/4 (Quellen
am Ende dieses Abschnitts) hat mehrere strukturelle Schwaechen unseres MVP-
Ansatzes aufgedeckt. Vier davon wurden **sofort umgesetzt**, zwei bewusst als
Scope-Entscheidung zurueckgestellt.

### Umgesetzt

1. **Hartes Effekt-Fenster statt weicher Traegheit.** Der urspruengliche
   Ansatz (`delay_turns` + `duration_turns`) liess Effekte nach einer festen
   Rundenzahl abrupt verschwinden, obwohl die Policy weiter aktiv war und
   Upkeep bezahlt wurde -- fuer Spieler nicht nachvollziehbar ("wieso hoert
   die Foerderung auf zu wirken?"). Democracy 4 loest das mit einem
   "Inertia"-Parameter: eine exponentiell geglaettete Annaeherung an einen
   Zielwert, die nie hart abschaltet. Umgesetzt in
   `sim/landtag_sim/engine.py::_effect_delta`; `duration_turns` ist komplett
   entfallen, `PolicyEffect.inertia` ersetzt es. Upkeep wird dadurch auch
   gleich einfacher: er laeuft jetzt durchgehend, solange die Policy aktiv
   ist, statt nur waehrend eines Fensters (behebt nebenbei den in der ersten
   Setup-Runde dokumentierten "bekannten Simplifizierungs"-Punkt).

2. **Nur eine Ressource (Budget), keine Handlungsbegrenzung.** Democracy
   trennt Geld (Budget) von "Political Capital" (generiert durch loyale
   Minister), das begrenzt, wie viele Reformen gleichzeitig durchsetzbar
   sind. Ohne diese zweite Ressource konnte ein Spieler beliebig viele
   guenstige Policies auf einmal aktivieren -- die Kernspannung "Prioritaeten
   setzen muessen" fehlte. Umgesetzt: `SimState.political_capital`
   (Regeneration/Obergrenze in `engine.py`, `CAPITAL_PER_TURN`/`CAPITAL_CAP`),
   `Policy.capital_cost`, `InsufficientCapitalError` bei Ueberschreitung. Die
   drei Beispiel-Policies kosten zusammen absichtlich mehr (11) als das Cap
   (10) -- alle drei gleichzeitig einzufuehren ist im MVP bewusst nicht
   machbar, das zeigt der Balance-Runner jetzt als `NICHT_MACHBAR` statt
   eines Absturzes.

3. **Reine Positiv-Policies ohne Zielkonflikt.** Der Balance-Runner aus der
   ersten Setup-Runde zeigte bereits ein Symptom davon: alle drei
   Beispiel-Policies kombiniert trieben die Zufriedenheit auf 89, weil keine
   einzige einen Nachteil hatte. Das widerspricht dem Kern des Genres
   (siehe Democracy-3-Recherche: "practically impossible to control all the
   voters", weil jede Policy Gewinner UND Verlierer hat). Jede Sample-Policy
   in `sim/landtag_sim/sample_data.py` hat jetzt mindestens einen negativen
   Nebeneffekt (z.B. Steuersenkung senkt Bildungsausgaben), gegen-getestet
   durch `test_every_sample_policy_has_at_least_one_negative_effect`.

4. **Alle eligiblen Events feuern gleichzeitig (Event-Spam-Risiko).**
   Democracy 4 evaluiert alle infrage kommenden Events/Dilemmas periodisch
   und laesst nur das mit dem hoechsten Score feuern. Unser `evaluate_events`
   sortiert jetzt nach Schweregrad (`_severity`), `engine.py` feuert bewusst
   nur noch das dringendste Event pro Runde.

### Bewusst zurueckgestellt (dokumentiert, nicht umgesetzt)

5. **Ueberlappende statt exklusive Waehlergruppen.** Democracys zentrale
   Erkenntnis ist, dass eine Person gleichzeitig mehreren Fraktionen angehoert
   (Elternteil UND Kapitalist UND religioes), wodurch es unmoeglich wird,
   allen zu gefallen. Unser `VoterGroup.population_share` behandelt Gruppen
   aktuell als disjunkte Partition. Das ist fuer den MVP-Scope (kein
   Wahlergebnis-Modell existiert noch) unkritisch, wird aber zum echten
   Problem, sobald die Wahlergebnis-Berechnung kommt -- dann muesste eine
   Person doppelt gezaehlt werden koennen. **Vorgemerkt fuer die
   Wahlergebnis-Implementierung, nicht rueckwirkend am MVP-Datenmodell
   geaendert**, um jetzt keine unnoetige Komplexitaet einzufuehren.

6. **Fixe vs. prozentuale Effektgroessen.** Cliff Harris (Democracy-Schoepfer)
   beschreibt einen konkreten Balancing-Fehler aus Democracy 4: ein
   Prozent-Bonus auf Einkommen gibt Reichen absolut mehr als Armen ("Boris
   der Hedgefonds-Manager" vs. "Mavis die Ex-Strassenkehrerin"), was bei
   Pauschal-Leistungen (Buergergeld, Freifahrten) zu absurden Ergebnissen
   fuehrt. Unser Modell hat aktuell keine Einkommens-/Buerger-Ebene --
   Statistiken sind Landeswerte, kein Problem heute. **Wird relevant, sobald
   jemals einkommensbezogene Policies (Steuern, Sozialleistungen) auf
   Buerger-/Klassen-Ebene simuliert werden sollen**; dann architektonisch von
   Anfang an fixe und prozentuale Effekte trennen (nicht nachtraeglich
   reparieren, siehe Positech-Blogpost unten).

### Ehrlich: noch nicht geloest

Der Balance-Runner ist Stand 2026-09-09 komplett gruen (Dominante-
Strategie-Check: "Keine vermutlich dominante Policy gefunden", kein
`BUDGET_NEGATIV`-Flag mehr, siehe mistakes.md "Budget hatte nie eine
Einnahmequelle"). Balancing ist trotzdem iterativ und nie "fertig" --
insbesondere gibt es weiterhin keine Policy-Repeal-Mechanik, und die
Grundeinnahme (`BASE_BUDGET_INCOME_PER_TURN`) ist eine bewusst einfache
Konstante, kein echtes Steuersatz-/GDP-System. Das ist ein bekannter,
offener Punkt fuer kuenftige Iterationen, keiner, der hier schongeredet
werden soll.

### Quellen (Game-Director-Review)

- [Democracy 4 Modding Guide (Steam Community) -- Inertia/Neural-Network-Modell](https://steamcommunity.com/sharedfiles/filedetails/?id=2242250360)
- [Democracy 3 Wiki (Fandom) -- Voter-Faction-Overlap, Situations/Dilemmas](https://democracygame.fandom.com/wiki/Democracy_3)
- [Cliff Harris (Positech) -- Democracy 4: The Fixed Income Rewrite](https://www.positech.co.uk/cliffsblog/2020/06/23/democracy-4-the-fixed-income-rewrite/)
- [Class and Games -- Managing Class in Democracy 4 (Kritik am Klassenmodell)](https://www.classandgames.com/post/managing-class-in-democracy-4)
- [AI Democracy (cosmin-novac/aidemocracy) -- MIT-lizenzierter, browserbasierter Democracy-4-inspirierter Clone](https://github.com/cosmin-novac/aidemocracy)

## Bekannte offene Punkte (nicht MVP-blockierend)

Stand nach dem vollstaendigen Doku-Audit vom 2026-09-09 (siehe CLAUDE.md
"Aktueller Stand" fuer die Details): Wahlergebnis-Berechnung,
`GET /policies`, Balance/Dominante-Strategie, die fehlende Backend-API-
Testsuite UND die fehlende Frontend-Verlaufsansicht sind inzwischen alle
behoben.

**Alle noch offenen Punkte sind seit der Community-Recherche 2026-09-09 in
`BACKLOG.md` (Wurzelverzeichnis) erfasst und priorisiert.** Kurzfassung der
groessten strukturellen Luecken, die die Recherche bestaetigt hat:

- **Fehlender mittlerer Zeithorizont ("Situations").** Wir haben Events
  (einmalig) und Policies (dauerhaft, spielergesetzt), aber keinen
  selbstverstaerkenden Zustand mit Hysterese dazwischen -- Democracys
  Kern-Griff fuer "Story ohne Text" (BACKLOG B2).
- **Loop trägt nicht ueber die erste Wahl hinaus.** Kein Ziel jenseits der
  Wiederwahl, kein Amtszeit-Rueckblick -- exakt die Democracy-4-
  Community-Kritik "nothing I did really mattered" (BACKLOG B1, offene
  Frage F1).
- **Konsequenzen nur als Zahlen, nicht narrativ.** `EffectAttribution`
  deckt die Zahlen-Ebene, aber es fehlt eine Text-Konsequenz-Ebene
  (Democracys "Media Reports", regelbasiert machbar) (BACKLOG B4).
- **Wahlausgang ist eine Blackbox bis Turn 16**, kein Turnout-/Apathie-
  Modell -- Democracy-Spieler verlieren dadurch "aus dem Nichts"
  (BACKLOG B5, offene Frage F4).
- Kleinere offene Punkte (unveraendert, jetzt als BACKLOG B10/B11/B13/B14
  gefuehrt): totes `PolicyDefinition.description`-Feld,
  `docker-compose.yml` ohne Frontend-Service, leere `CREDITS.md`,
  Platzhalter-`data/`.
- Keine Policy-Repeal-Mechanik (siehe "Ehrlich: noch nicht geloest" oben).
