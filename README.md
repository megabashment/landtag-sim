# Landtag-Sim

Ein entspanntes Management-Spiel mit starker Anlehnung an die Mechaniken der
*Democracy*-Reihe: Policies mit verzoegerter Wirkung setzen, Waehlergruppen
zufriedenstellen, Budget im Blick behalten, Wahl gewinnen. MVP-Szenario:
**Niedersachsen**, spaeter skalierbar bis Nation- oder EU-Ebene.

## Architekturentscheidungen (Stand: Projekt-Setup)

| Bereich | Entscheidung | Begruendung |
|---|---|---|
| Client | React (Vite), reines Rendering | Bekannter Stack, schnelles Iterieren |
| Simulation | Serverseitig (FastAPI) | Rendering lokal, Sim-Logik zentral und pruefbar |
| Kommunikation | REST, rundenbasiert | Passt zum rundenbasierten Spielprinzip, kein Multiplayer im MVP |
| Datenbank | PostgreSQL von Anfang an | Skalierung auf mehrere Partien/Nutzer vorbereitet |
| Text/Ereignisse | Regelbasierte Trigger + Regex-Templates | Explizit **kein LLM/NLP** -- deterministisch, testbar |
| Sim-Tiefe | Traegheitsmodell: verzoegert + exponentiell geglaettet (kein hartes Zeitfenster mehr) | Nach Game-Director-Review, siehe [docs/architecture.md](./docs/architecture.md) |
| Ressourcen | Budget **und** Political Capital (begrenzt Reformen/Runde) | Verhindert beliebig viele Policies auf einmal, siehe Review |
| Policy-Design | Jede Policy hat mind. einen negativen Nebeneffekt | Echte Zielkonflikte statt reiner Positiv-Policies, siehe Review |
| Scope | Ein Bundesland (Niedersachsen) statt ganzes Land | Kleinerer, handhabbarer Datensatz fuer den Start |
| Skalierungspfad | Region -> Nation -> EU ist Meta-Ziel, **nicht** Teil des MVP | Datenmodell (`AdminUnit`) ist dafuer vorbereitet, aber nicht befuellt |
| Assets | Nur offen lizenzierte Quellen (game-icons.net, OpenMoji, Kenney), keine CC0-Pflicht | Siehe [CREDITS.md](./CREDITS.md) |
| Repository | Oeffentlich | |

## Warum Niedersachsen anders behandelt wird als geplant

Die urspruengliche Datenquellen-Wahl (Weltbank, V-Dem/Freedom House) gilt nur
auf Nationalebene. Fuer ein Bundesland braucht es eine andere Quelle
(Landesamt fuer Statistik Niedersachsen). Details und der Skalierungspfad
zurueck zu Weltbank/V-Dem auf Nation-Ebene stehen in
[data/README.md](./data/README.md).

## Traegheitsmodell und Balancing

Policy-Effekte wirken nicht sofort, sondern verzoegert (`delay_turns`) und
naehern sich danach exponentiell geglaettet ihrem Zielwert an (`inertia`,
Vorbild Democracy 4) -- sie verschwinden NICHT nach einer festen Rundenzahl
wieder, solange die Policy aktiv ist. Siehe `sim/landtag_sim/engine.py` und
[docs/architecture.md](./docs/architecture.md#game-director-review-nach-mvp-setup-vor-weiterem-ausbau)
fuer die Herleitung (Game-Director-Review). Das macht Balancing von Hand
unpraktikabel, daher gibt es einen headless Balance-Runner, der alle
Policy-Kombinationen automatisiert durchspielt und auffaellige Szenarien
markiert (Budget-Kollaps, eingefrorene/an die Grenze laufende Zufriedenheit,
nicht mit dem verfuegbaren Political Capital machbare Kombinationen):

```bash
cd sim
pip install -e .
python -m landtag_sim.tools.balance_runner --turns 30
```

Der Runner meldet am Ende zusaetzlich vermutlich **dominante Policies**
(Comptons "Illusory Choice"-Heuristik, docs/game-design-roadmap.md Punkt 10):
Policies, die in >90% der erfolgreichen Top-Szenarien vorkommen, sind
vermutlich zu stark oder haben keine gleichwertige Alternative.

## Projektstruktur

```
landtag-sim/
├── backend/          # FastAPI-App, Postgres-Modelle (SQLModel), REST-API
│   └── app/
│       ├── models/   # AdminUnit, StatisticDefinition/-Value, VoterGroup,
│       │             # PolicyDefinition, EventDefinition, GameSession
│       ├── api/      # Routen: /health, /sessions, /sessions/{id}/advance
│       └── sim_bridge.py  # Uebersetzt DB <-> reine Sim-Engine
├── sim/              # Reine Simulationslogik, KEINE DB-Abhaengigkeit
│   └── landtag_sim/
│       ├── engine.py     # Kern: eine Runde vorwaerts rechnen
│       ├── events.py     # Regelbasierte Trigger-Auswertung (passiv)
│       ├── dilemmas.py   # Regelbasierte Trigger-Auswertung mit echten Optionen
│       ├── templates.py  # Regex-basiertes Text-Rendering (kein LLM)
│       └── tools/balance_runner.py  # Headless Szenario-Tester
├── frontend/         # React (Vite) Dashboard
├── data/             # Datenquellen-Doku + Import-Platzhalter
└── CREDITS.md        # Asset-Lizenzen (Pflicht bei jedem neuen Asset)
```

## Lokal starten

### Voraussetzung: PostgreSQL

```bash
docker compose up -d db
# oder: lokale Postgres-Installation, Zugangsdaten siehe backend/.env.example
```

### Backend

```bash
cd sim && pip install -e . && cd ..
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Beim ersten Start werden Tabellen automatisch angelegt (`create_all`) und
Niedersachsen + Beispiel-Policies/Events geseedet (siehe `app/seed.py`).
Sobald das Schema sich haeufiger aendert, uebernimmt Alembic
(`backend/alembic/`) die Migrationen.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### Backend + Datenbank mit Docker

```bash
docker compose up --build
```

Startet nur `db` und `backend` (kein Frontend-Service in
`docker-compose.yml`) -- das Frontend weiterhin separat per `npm run dev`
starten.

### Schnellstart per Skript (Windows/PowerShell)

Nach dem einmaligen Setup oben (oder mit `-Setup` fuer den allerersten
Lauf) startet `start.ps1` Postgres, Backend und Frontend automatisch je in
einem eigenen Fenster und oeffnet den Browser:

```powershell
.\start.ps1          # nur starten (Postgres, Backend, Frontend)
.\start.ps1 -Setup   # zusaetzlich Abhaengigkeiten (neu) installieren
```

## API (MVP)

- `POST /sessions` -- neue Partie fuer Niedersachsen anlegen
- `GET /sessions/{id}` -- aktuellen Zustand abrufen (Statistiken, Waehlergruppen, Budget, Runde, Runden bis zur Wahl)
- `POST /sessions/{id}/preview` -- Effekt-Vorschau: simuliert die naechste Runde mit gegebenen Policies, persistiert nichts (`{"enact_policy_keys": [...]}`)
- `POST /sessions/{id}/advance` -- Runde beenden, optional neue Policies einfuehren (`{"enact_policy_keys": [...]}`); Response enthaelt Attributionen und ggf. ein Wahlergebnis. Am Wahl-Turn zusaetzlich `term_summary` (Amtszeit-Bilanz der abgelaufenen Legislaturperiode: Start-vs-Ende je Statistik/Kategorie, groesster Fort-/Rueckschritt, Dilemma-/Ereignis-Zaehler, Budget-Bilanz -- reiner Rueckblick, keine Siegbedingung; BACKLOG.md B1). Schlaegt fehl, wenn eine Policy-Voraussetzung fehlt (siehe `Policy.requires`) oder ein Dilemma noch offen ist
- `POST /sessions/{id}/resolve-dilemma` -- offenes Dilemma mit einer gewaehlten Option aufloesen (`{"option_key": "..."}`); zaehlt keine eigene Runde
- `GET /policies` -- dynamischer Policy-Katalog (Name, Kosten, Effekte, Voraussetzungen), session-unabhaengig; loest die vorherige hart codierte Kopie im Frontend ab

Alle Endpunkte sind seit dem Doku-Audit 2026-09-09 durch eine eigene
Backend-Testsuite (`backend/tests/`, 24 Tests gegen eine separate Test-DB)
abgedeckt, nicht mehr nur manuell per curl -- siehe CLAUDE.md
Verifikations-Workflow fuer das einmalige Test-DB-Setup. Das Frontend
zeigt ausserdem eine Verlaufsansicht ueber alle gespielten Runden statt nur
der letzten (`App.jsx`, Sektion "Verlauf").

## Naechste Schritte fuer die Spielmechanik

Eine gewichtete 10-Punkte-Liste (Impact x Aufwand, Genre-Best-Practices von
Democracy/Frostpunk/Suzerain) steht in
[docs/game-design-roadmap.md](./docs/game-design-roadmap.md) -- Stand:
**alle 10 Punkte (P0/P1/P2) umgesetzt**, Details und Umsetzungsnotizen je
Punkt direkt dort.

## Bekannte Vereinfachungen (MVP, bewusst offen fuer Diskussion)

- Wahlergebnis-Berechnung ist implementiert (gewichtete Durchschnitts-
  zufriedenheit gegen Schwellenwert 50, siehe `sim/landtag_sim/engine.py`).
  Die vier urspruenglichen Waehlergruppen sind weiterhin exklusiv
  (Summe genau 1.0), aber es gibt inzwischen zwei zusaetzliche,
  ueberlappende Identitaetsgruppen ("Umweltbewusste Waehler",
  "Junge Familien" -- Gesamtsumme aller Gruppen jetzt >1.0), wie es
  Democracys Kernmechanik erwartet; siehe `sample_data.py::
  SAMPLE_VOTER_GROUPS`.
- Balance ist inzwischen deutlich runder: der Dominante-Strategie-Check
  (Roadmap Punkt 10) findet aktuell **keine** dominante Policy mehr (vorher
  war `bildungsoffensive` in 100% der Top-Szenarien vertreten -- behoben
  durch einen staerkeren `gdp_growth`-Trade-off und eine vierte, unabhaengige
  Policy `gesundheitsreform`). Die zuvor als `BUDGET_NEGATIV` markierte
  Dreier-Kombination `bildungsoffensive+steuersenkung_mittelstand+
  gesundheitsreform` ist ebenfalls behoben -- Ursache war kein
  Upkeep-Tuning-Problem, sondern dass das Budget ueberhaupt nie eine
  Einnahmequelle hatte (siehe `BASE_BUDGET_INCOME_PER_TURN` in
  `sim/landtag_sim/engine.py` und `mistakes.md`). Es gibt jetzt eine
  Policy-Repeal-Mechanik (Democracy-4-Vorbild, siehe CLAUDE.md): eine
  zurueckgezogene Policy verschwindet nicht schlagartig, sondern klingt
  ueber mehrere Runden symmetrisch zu ihrem Aufbau ab, Upkeep/Einnahme
  stoppen sofort. Fuenfte Beispiel-Policy `vermoegensteuer` bringt dabei
  die erste echte, spielerseitig wieder abschaltbare Einnahmequelle
  (`Policy.income_per_turn`) neben der pauschalen Grundeinnahme.
- Es gibt jetzt drei Dilemmas (`arbeitsmarktkrise`, `rezession`,
  `pflegeausbau`) statt nur einem, an unterschiedliche Statistiken gekoppelt.
  Die meisten urspruenglichen Event-/Dilemma-Schwellenwerte
  (`arbeitsmarktkrise` eingeschlossen) bleiben aber im organischen
  Spielverlauf praktisch unerreichbar, da nichts in den Beispiel-Policies
  die Statistiken so stark in Richtung Krise treibt -- bewusst nicht breit
  behoben (bräuchte z.B. zufaellige Wirtschafts-Schock-Events).

## Offen-Source-Referenzmaterial fuer Spielmechaniken

Keine direkt wiederverwendbare Codebasis eines Democracy-Clones gefunden,
aber zwei nutzbare Ausgangspunkte:

- **[AI Democracy](https://github.com/cosmin-novac/aidemocracy)** (MIT-Lizenz):
  browserbasierter, von Democracy 4 inspirierter Clone in Vanilla-JS mit
  visuellem Knoten-Graph (State-/Policy-/Voter-Nodes, farbige Kanten fuer
  positive/negative Effekte). Code-Qualitaet mit Vorsicht zu geniessen (laut
  eigener Aussage komplett per LLM ohne manuelles Coding erstellt), aber
  MIT-lizenziert und als visuelles Referenzmodell fuer eine spaetere
  Graph-Darstellung im Frontend brauchbar.
- **Democracy 4 Modding-Dokumentation** (siehe Quellen in
  docs/architecture.md): kein Code, aber eine vollstaendig offengelegte
  Beschreibung des tatsaechlichen Effekt-Formats (CSV-basiert, moddable ohne
  Programmierung) -- direkt Vorbild fuer unser `inertia`-Konzept.
