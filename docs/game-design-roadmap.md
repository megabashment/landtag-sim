# Game-Design-Roadmap: 10 gewichtete Optimierungen

Senior-Game-Designer-Durchsicht von Code (`sim/`, `backend/app/`) und Konzept
(README.md, docs/architecture.md) gegen Genre-Erfolgsfaktoren (Democracy 4,
Frostpunk, Suzerain, Tropico) und grundlegende Game-Design-Prinzipien (Sid
Meiers "interessante Entscheidungen", MDA-Framework). Quellen am Ende.

## Gewichtungsmethode

Jeder Vorschlag: **Impact** (1-5, Wirkung auf Spielgefuehl/Erfolgsfaktoren) x
**Aufwand** (1-5, 1=klein) -> **Prioritaet**. Sortiert nach Prioritaet
absteigend.

| # | Vorschlag | Impact | Aufwand | Prioritaet | Status |
|---|---|---|---|---|---|
| 1 | Effekt-Vorschau vor Entscheidung | 5 | 3 | **P0** | erledigt |
| 2 | Wahlmechanik/Siegbedingung | 5 | 3 | **P0** | erledigt |
| 3 | Zufriedenheits-Attribution | 4 | 2 | **P0** | erledigt |
| 4 | Dilemma-Events mit echten Optionen | 5 | 4 | P1 | erledigt |
| 5 | Policy-Pfade/Voraussetzungen | 4 | 3 | P1 | erledigt |
| 6 | Fast-Forward/Pacing-Kontrollen | 3 | 2 | P1 | erledigt |
| 7 | Namens-Vignetten in Event-Texten | 3 | 1 | P2 | offen |
| 8 | Zufriedenheits-Momentum/Glaettung | 3 | 2 | P2 | offen |
| 9 | Randomisierte Startbedingungen | 2 | 1 | P2 | offen |
| 10 | Dominante-Strategie-Check im Balance-Runner | 2 | 2 | P2 | offen |

---

## P0 -- sollte vor jedem weiteren Feature-Ausbau passieren

**Status: alle drei P0-Punkte umgesetzt** (siehe `sim/landtag_sim/engine.py`,
`backend/app/api/routes_game.py`, `frontend/src/App.jsx`). Details je Punkt
unten, Umsetzungsnotizen kursiv markiert.

### 1. Effekt-Vorschau vor Entscheidung

*Umgesetzt:* `POST /sessions/{id}/preview` (siehe `routes_game.py`) ruft
`advance_turn` mit der aktuellen Policy-Auswahl auf und verwirft das
Ergebnis -- kein `persist_sim_state`, kein Commit. Response liefert
`statistic_deltas`, `satisfaction_delta_by_group`, `would_trigger_events`
und ein `feasible`-Flag (fuer Political-Capital-Engpaesse). Frontend ruft
das bei jeder Aenderung der Auswahl automatisch auf und zeigt pro Statistik
einen Pfeil mit grober Groessenklasse (schwach/mittel/stark) statt exakter
Zahl -- wie unten vorgeschlagen. Bewusste Einschraenkung: verzoegerte
Effekte (`delay_turns > 0`) zeigen in der Vorschau der ersten Runde
korrekterweise noch keine Bewegung -- das ist keine Ungenauigkeit, sondern
spiegelt die tatsaechliche Wirkung wider.

Urspruenglicher Vorschlag:

**Problem:** Aktuell sieht der Spieler in `frontend/src/App.jsx` nur Policy-
Name und Political-Capital-Kosten -- keinerlei Hinweis, was eine Policy
bewirkt, bevor er sie aktiviert. Das verletzt Sid Meiers Kernprinzip
"interessante Entscheidungen": eine Entscheidung ist nur dann interessant,
wenn der Spieler ihre Richtung antizipieren kann ("predictable outcomes").
Ohne Vorschau ist die Wahl reines Rätselraten statt Strategie.

**Vorbild:** Frostpunks Book of Laws zeigt bewusst *qualitative* Richtung
("Hoffnung steigt leicht") bei *vager* Quantitaet -- genug Information fuer
eine informierte Entscheidung, ohne die Spannung durch exakte Zahlen zu
zerstoeren.

**Vorschlag:** Neuer Read-only-Endpunkt `POST /sessions/{id}/preview`, der
`advance_turn` mit den ausgewaehlten Policies simuliert, aber verwirft (kein
`persist_sim_state`). Frontend zeigt pro Statistik einen Pfeil (↑/↓) mit
grober Groessenklasse (schwach/mittel/stark) statt exakter Zahl. Technisch
guenstig: die Sim-Engine ist bereits eine reine Funktion
(`sim/landtag_sim/engine.py::advance_turn`), die keinen State mutiert --
Preview ist im Kern ein Aufruf ohne Persistierung.

### 2. Wahlmechanik/Siegbedingung implementieren

*Umgesetzt:* `advance_turn` zaehlt `turns_until_election` jede Runde runter
(siehe `SimState`/`engine.py`). Bei 0 berechnet `_weighted_approval` die
nach `population_share` gewichtete Durchschnittszufriedenheit ueber alle
`VoterGroup`, vergleicht gegen `ELECTION_APPROVAL_THRESHOLD = 50.0` und
liefert ein `ElectionResult`. `routes_game.py::advance_session_turn`
schreibt das Ergebnis in die Session zurueck: **verloren** setzt
`SessionStatus.LOST` und beendet die Partie (`/advance` liefert danach
HTTP 400); **gewonnen** haelt die Session `ACTIVE` und der naechste
16-Runden-Zyklus beginnt (Wiederwahl bedeutet Weiterspielen, nicht
Spielende). End-to-End mit echtem Wahlsieg und echter Wahlniederlage
getestet (siehe `sim/tests/test_engine.py` und manuelle API-Durchlaeufe).

**Problem (Ausgangslage):** `backend/app/models/game.py::GameSession.turns_until_election`
existiert bereits als Feld, wird aber von der Engine nirgendwo gelesen oder
runtergezaehlt -- eine tote Datenmodell-Leiche. Ohne Wahlergebnis am
Zyklusende hat das Spiel kein definiertes Ziel. Das ist der schwerwiegendste
strukturelle Luecke: ohne Sieg-/Niederlage-Bedingung sind alle Policy-
Entscheidungen folgenlos im buchstaeblichen Sinn -- es gibt nichts zu
gewinnen oder zu verlieren. Genau das killt laut Compton/Sid Meier
Entscheidungsrelevanz ("nothing I did really mattered").

**Vorschlag:** `advance_turn` zaehlt `turns_until_election` runter; bei 0
wird ein gewichteter Zufriedenheits-Score ueber alle `VoterGroup` (gewichtet
mit `population_share`) berechnet, gegen einen Schwellenwert verglichen,
`SessionStatus.WON`/`LOST` gesetzt. Einfachste Version zuerst (Schwellenwert
z.B. 50), Verfeinerung (Ueberlappende Gruppen, siehe Game-Director-Review
Punkt 5 in docs/architecture.md) spaeter.

### 3. Zufriedenheits-Attribution ("Warum aendert sich das?")

*Umgesetzt:* Neue Datenklasse `EffectAttribution` (`source`, `statistic_key`,
`delta`) -- jeder Policy- und Event-Effekt wird jetzt einzeln attribuiert
statt in einem anonymen `stat_deltas`-Dict summiert. `TurnResult.attributions`
gibt die volle Liste zurueck, das Backend reicht sie 1:1 im
`AdvanceTurnResponse` weiter, das Frontend zeigt sie als "Ursachen"-Liste an.
Beim Umbau ist zusaetzlich ein echter Bug aufgefallen und behoben worden:
Event-Effekte wurden bisher NACH der Zufriedenheits-Berechnung angewendet
und sind daher NIE in die Waehlerreaktion eingeflossen -- jetzt werden
Events vor der Zufriedenheits-Berechnung ausgewertet und ihre Effekte fliessen
in dieselben Attributionen ein (siehe Regressionstest
`test_event_effects_are_attributed_and_feed_into_satisfaction`).

**Problem (Ausgangslage):** `engine.py` summiert Effekte aus mehreren gleichzeitig aktiven
Policies in `stat_deltas` und wendet sie kollektiv auf die Zufriedenheit an
(`advance_turn`, Abschnitt 2). Der Spieler sieht nur die Endzahl, nicht,
*welche* Policy sie verursacht hat. Sobald 2-3 Policies gleichzeitig laufen,
wird die Zufriedenheitsaenderung ein Blackbox-Rauschen -- schlechtes
Feedback-Loop-Design (MDA: Aesthetics leiden, wenn Dynamics nicht lesbar
sind).

**Vorschlag:** `stat_deltas` um Quellenangabe erweitern (z.B.
`dict[str, list[tuple[str, float]]]` mit Policy-Key statt nur summierter
Zahl), im API-Response pro Runde eine kurze "Ursachen"-Liste mitliefern
("Foerderprogramm erneuerbare Energien: Staedtische Mitte +2.1"). Kleiner
Eingriff in bestehende Datenstruktur, grosser Effekt auf Lesbarkeit.

---

## P1 -- naechste Ausbaustufe

**Status: alle drei P1-Punkte umgesetzt** (siehe `sim/landtag_sim/engine.py`,
`sim/landtag_sim/dilemmas.py`, `backend/app/api/routes_game.py`,
`frontend/src/App.jsx`).

### 4. Dilemma-Events mit echten Entscheidungsoptionen

*Umgesetzt:* Neue Dataclasses `DilemmaOption`/`DilemmaRule`/`PendingDilemma`
(`sim/landtag_sim/models.py`) und ein eigenes Auswertungsmodul
`sim/landtag_sim/dilemmas.py` (gleicher Trigger-/Schweregrad-/Cooldown-
Mechanismus wie `events.py`). Ein ausgeloestes Dilemma ist der "Headline"-
Moment der Runde und unterdrueckt ein gleichzeitig eligibles passives Event
(vermeidet Ueberladung). `advance_turn()` PAUSIERT danach: jeder weitere
Aufruf wirft `DilemmaPendingError`, bis `resolve_dilemma()` mit einem
gewaehlten Options-Key aufgerufen wurde -- das zaehlt bewusst KEINE eigene
Runde (Political Capital/Wahl-Countdown liefen schon in der ausloesenden
Runde). Backend: neuer Endpunkt `POST /sessions/{id}/resolve-dilemma`,
`/advance` und `/preview` lehnen ab bzw. melden `feasible=False`, solange
ein Dilemma offen ist. Frontend zeigt ein blockierendes Panel mit den
Optionen. Ein Beispiel-Dilemma (`arbeitsmarktkrise`, echter Zielkonflikt
zwischen teurer/sozialvertraeglicher und guenstiger/haerterer Option) ist in
`sample_data.py` hinterlegt.

Beim Einbau ist zusaetzlich ein bestehender, bis dahin unbemerkter Bug
aufgefallen und mitbehoben: Event-/Dilemma-Cooldowns wurden vom Backend nie
persistiert (`GameSession` hatte dafuer gar kein Feld) -- jede Anfrage lud
die Engine mit leeren Cooldowns neu, wodurch Cooldowns im laufenden Backend
nie gewirkt haben (nur im Balance-Runner, der denselben State durchgaengig
in einer Python-Variable haelt). Siehe `mistakes.md` fuer Details.

**Problem (Ausgangslage):** `EventDefinition`/`EventRule` sind rein passiv: sie feuern,
zeigen Text, wenden einen festen Effekt an. Genau diese Mechanik -- ein
Ereignis mit 2+ Optionen, zwischen denen der Spieler waehlen muss -- ist in
Frostpunk (Book of Laws) und Suzerain (jede Szene) der wichtigste einzelne
Erfolgsfaktor des Genres: sie zwingt echte Werte-Abwaegungen statt nur
Statistik-Reaktion.

**Vorschlag:** Neues Modell `DilemmaDefinition` (Trigger wie EventDefinition,
aber `options: list[DilemmaOption]` mit je eigenem Effekt-Set und Text).
Engine pausiert an dieser Stelle konzeptionell (im rundenbasierten Modell:
der `/advance`-Call gibt eine offene Dilemma-Frage zurueck statt sofort zu
committen; Client muss erst `/sessions/{id}/resolve-dilemma` aufrufen, bevor
die Runde als beendet gilt). Groesster Einzel-Vorschlag hier, aber auch der
mit dem hoechsten Genre-Wiedererkennungswert.

### 5. Policy-Pfade/Voraussetzungen fuer strategische Differenzierung

*Umgesetzt:* `Policy.requires: list[str]` (statt, wie urspruenglich
vorgeschlagen, an `PolicyEffect` -- gehoert semantisch zur Policy als
Ganzes). `advance_turn()` prueft vor jeder Einfuehrung, ob alle
Voraussetzungen bereits aktiv sind ODER in derselben Runde mit eingefuehrt
werden (Reihenfolge innerhalb einer Auswahl spielt keine Rolle), sonst
`UnmetPrerequisiteError`. Konkret umgesetzt am Beispiel aus der Roadmap
selbst: `steuersenkung_mittelstand` braucht jetzt `bildungsoffensive`.
Frontend deaktiviert die Checkbox und zeigt "Braucht zuerst: ...", solange
die Voraussetzung fehlt. Der Balance-Runner generiert Kombinationen jetzt
voraussetzungs-bewusst (keine sinnlosen NICHT_MACHBAR-Zeilen mehr fuer
Kombinationen, die ihre eigene Regel verletzen).

**Problem (Ausgangslage):** Alle Policies sind ab Runde 1 gleichzeitig verfuegbar
(`sim/landtag_sim/sample_data.py::SAMPLE_POLICIES`). Ohne Freischaltungs-
Reihenfolge gibt es keine "Bauart"/Spielstil-Differenzierung zwischen
Partien -- ein Kernhebel fuer Replayability in Aufbau-/Management-Spielen
(vgl. Frostpunks Tech-Baum, Tropicos Ministerien-Fortschritt).

**Vorschlag:** `PolicyEffect`-Nachbar-Feld `requires: list[str]` (Policy-Keys,
die vorher aktiv/abgeschlossen sein muessen). Erzwingt keine grosse
Tech-Baum-UI im MVP, aber macht z.B. "Steuersenkung Mittelstand" erst nach
"Bildungsoffensive" waehlbar -- schafft Reihenfolge-Entscheidungen
zusaetzlich zu Kombinations-Entscheidungen.

### 6. Fast-Forward/Pacing-Kontrollen

*Umgesetzt:* Frontend-Button "Vorspulen bis naechstes Ereignis"
(`App.jsx::handleFastForward`) ruft `/advance` wiederholt mit leerer
Policy-Auswahl auf (Sicherheitslimit 40 Iterationen) und stoppt, sobald
Ereignisse, ein Wahlergebnis, ein Dilemma oder ein Partie-Ende auftreten --
exakt wie vorgeschlagen, rein clientseitig, keine Backend-Aenderung noetig.

**Problem (Ausgangslage):** Das urspruengliche Briefing verlangt explizit ein
"entspanntes" Spiel, aber jede Runde braucht aktuell einen expliziten
Klick/API-Call ohne die Option, mehrere ereignislose Runden zu ueberspringen.
Das erzeugt unnoetige Mikromanagement-Ermuedung -- Gegenteil von entspannt.

**Vorschlag:** Frontend-Button "Vorspulen bis naechstes Ereignis" (mehrere
`/advance`-Calls mit leerem `enact_policy_keys` hintereinander, Abbruch
sobald `events` nicht leer ist oder eine Wahl ansteht). Rein clientseitig
umsetzbar, keine Backend-Aenderung noetig.

---

## P2 -- kleine Verbesserungen, guter Aufwand/Wirkung-Faktor

### 7. Namens-Vignetten in Event-Texten

Statt reiner Statistik-Meldungen ("Arbeitslosenquote erreicht 9.2%") kurze,
wiederkehrende fiktive Stimmen einstreuen ("Fabrikarbeiterin Sina aus
Salzgitter: 'Wo soll das noch hinfuehren?'"). Macht abstrakte Zahlen
menschlich (Democracy/Suzerain-Erfolgsfaktor), ohne die in der letzten
Review bewusst zurueckgestellte volle Buerger-Simulation zu brauchen --
reine Text-Pool-Erweiterung in `sim/landtag_sim/sample_data.py`.

### 8. Zufriedenheits-Momentum/Glaettung

Zufriedenheit reagiert aktuell direkt und ungeglaettet auf jedes Effekt-
Delta (`engine.py`, Abschnitt 2). Ein leichter Traegheits-Faktor (analog zum
Policy-Inertia-Modell) wuerde das Spielgefuehl ruhiger und vorhersagbarer
machen -- passt zum "entspannt"-Ziel und reduziert Zahlenrauschen weiter
(ergaenzt Punkt 3).

### 9. Randomisierte Startbedingungen

Jede neue Partie (`POST /sessions`) startet aktuell mit exakt identischen
Werten aus `STARTING_STATISTICS`. Eine kleine Zufallsstreuung (z.B. ±5% pro
Statistik) sorgt fuer unterschiedliche Startsituationen zwischen Partien --
guenstiger Replayability-Hebel, ohne die Balance grundlegend zu veraendern.

### 10. Dominante-Strategie-Check im Balance-Runner

Der bestehende `sim/landtag_sim/tools/balance_runner.py` prueft bereits auf
Budget-Kollaps und Zufriedenheits-Extreme. Ergaenzung um Comptons "Illusory
Choice"-Heuristik: markiere Policies, die in praktisch jeder erfolgreichen
Kombination vorkommen (>90% der nicht-eingefrorenen Top-Szenarien) als
"vermutlich dominant" -- ein Hinweis, dass diese Policy zu stark oder eine
Konkurrenz-Policy zu schwach ist. Prozess-/Tooling-Verbesserung, kein
Gameplay-Feature.

---

## Quellen

- [Designing Interesting Decisions in Games (And When Not To) -- Caleb Compton](https://remptongames.medium.com/designing-interesting-decisions-in-games-and-when-not-to-452af04d0e66)
- [GDC 2012: Sid Meier on interesting decisions](https://www.gamedeveloper.com/design/gdc-2012-sid-meier-on-how-to-see-games-as-sets-of-interesting-decisions)
- [Frostpunk's Book of Laws -- Player Decisions design analysis](https://gamedesignthinking.com/frostpunk-players-decisions/)
- [Suzerain -- A Political Video Game (Strategineer)](https://strategineer.com/blog/2021-04-05/)
- Bezug zur vorherigen Review: [docs/architecture.md](./architecture.md#game-director-review-nach-mvp-setup-vor-weiterem-ausbau)
