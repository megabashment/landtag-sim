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

### Alles zusammen mit Docker

```bash
docker compose up --build
```

## API (MVP)

- `POST /sessions` -- neue Partie fuer Niedersachsen anlegen
- `GET /sessions/{id}` -- aktuellen Zustand abrufen (Statistiken, Waehlergruppen, Budget, Runde, Runden bis zur Wahl)
- `POST /sessions/{id}/preview` -- Effekt-Vorschau: simuliert die naechste Runde mit gegebenen Policies, persistiert nichts (`{"enact_policy_keys": [...]}`)
- `POST /sessions/{id}/advance` -- Runde beenden, optional neue Policies einfuehren (`{"enact_policy_keys": [...]}`); Response enthaelt Attributionen und ggf. ein Wahlergebnis. Schlaegt fehl, wenn eine Policy-Voraussetzung fehlt (siehe `Policy.requires`) oder ein Dilemma noch offen ist
- `POST /sessions/{id}/resolve-dilemma` -- offenes Dilemma mit einer gewaehlten Option aufloesen (`{"option_key": "..."}`); zaehlt keine eigene Runde

## Naechste Schritte fuer die Spielmechanik

Eine gewichtete 10-Punkte-Liste (Impact x Aufwand, Genre-Best-Practices von
Democracy/Frostpunk/Suzerain) steht in
[docs/game-design-roadmap.md](./docs/game-design-roadmap.md).

## Bekannte Vereinfachungen (MVP, bewusst offen fuer Diskussion)

- Wahlergebnis-Berechnung ist implementiert (gewichtete Durchschnitts-
  zufriedenheit gegen Schwellenwert 50, siehe `sim/landtag_sim/engine.py`),
  aber noch mit exklusiven, nicht ueberlappenden Waehlergruppen. Democracys
  Kernmechanik braucht ueberlappende Fraktionen -- bewusst zurueckgestellte
  Verfeinerung, siehe Game-Director-Review in
  [docs/architecture.md](./docs/architecture.md).
- `GET /policies` (dynamischer Policy-Katalog fuers Frontend) fehlt noch --
  Frontend nutzt aktuell eine hart codierte Liste.
- Balance ist trotz Trade-off-Ueberarbeitung noch nicht rund: die Kombination
  "erneuerbare_foerderung+bildungsoffensive" treibt die Zufriedenheit ueber
  30 Runden weiterhin auf ~86 (siehe Balance-Runner-Ausgabe, Details in
  docs/architecture.md) -- das fuehrt inzwischen auch zuverlaessig zum
  Wahlsieg, was die Schieflage sichtbarer macht als vorher.

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
