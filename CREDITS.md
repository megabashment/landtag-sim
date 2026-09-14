# Credits & Lizenzen

Dieses Projekt nutzt ausschliesslich offen lizenzierte Assets (keine
proprietaeren/kommerziellen Sprites). Jede hier eingebundene Datei muss in
dieser Tabelle eingetragen werden -- Pflicht, da die Lizenzen sich
unterscheiden (nicht alle CC0).

| Asset | Quelle | Lizenz | Verwendung |
|---|---|---|---|
| Statistik-Icons (6 Pfade) | [game-icons.net](https://game-icons.net) | CC BY 3.0 (Delapouite, sbed) | Statistik-Icons: Arbeitslosenquote, BIP, Bildung, Gesundheit, CO2, Erneuerbare (`frontend/src/statIcons.js`) |
| Party Icons (15 Icons) | [Lucide Icons](https://lucide.dev) | MIT | Party-Archetypen mit Emojis & SVG Pfade (`frontend/src/partyIcons.js`): Grüne, SPD, Linke, CDU, Liberale, Piraten, etc. |
| Ideologie-Icons (3 Icons) | [Lucide Icons](https://lucide.dev) | MIT | Ideologie-Symbole: Grün 🟢, Rot 🔴, Blau 🔵 (`frontend/src/partyIcons.js`) |
| Favicon (Amtsgebäude-Piktogramm) | selbst gezeichnet (Claude, 2026-09-12) | keine (Eigenwerk, keine externe Quelle) | Browser-Tab-Icon (`frontend/public/favicon.svg`) |
| Bundesland-Lagekarten (Niedersachsen, Bayern, Nordrhein-Westfalen) | [Wikimedia Commons](https://commons.wikimedia.org) -- Dateien "Locator map Lower-Saxony in Germany.svg", "Locator map Bavaria in Germany.svg", "Locator map North Rhine-Westphalia in Germany.svg" | CC BY-SA 3.0 (Autor: [TUBS](https://commons.wikimedia.org/wiki/User:TUBS)) | Echte, unveraenderte Vektor-Lagekarten (Deutschland-Umriss, Bundesland farbig hervorgehoben) fuer `BundeslandBadge` (`App.jsx`) -- Dateien liegen unter `frontend/public/maps/{niedersachsen,bayern,nrw}.svg`. Copyleft (Share-Alike): bei Bearbeitung/Ableitung muss die Ableitung ebenfalls CC BY-SA sein; unveraendert weiterverwenden ist unkritisch. |
| Bundesland-Platzhalter-Silhouetten (Fallback) | selbst gezeichnet, KEINE echten Vermessungsdaten | keine (Eigenwerk) | `frontend/src/bundeslandData.js::PLACEHOLDER_SILHOUETTES` -- greift nur, falls fuer ein (kuenftiges) Bundesland noch keine echte Karte unter `REAL_MAP_KEYS` hinterlegt ist |

Hinweis: eingebunden ist jeweils nur das `<path>`-Vektordatum (der schwarze
Hintergrund-Rect der Originaldatei wurde entfernt, Rendering in
`currentColor`) in `frontend/src/statIcons.js`. CC BY 3.0 verlangt
Namensnennung — diese Tabelle plus der Icon-Kommentar in `statIcons.js`
erfuellen das.

## Empfohlene/geprüfte Quellen (siehe Projekt-Setup-Diskussion)

- **game-icons.net** -- ueber 4000 spielespezifische Icons, CC-BY 3.0
  (Namensnennung erforderlich). Erste Wahl fuer Statistik-/Policy-Icons.
- **OpenMoji** -- CC BY-SA 4.0 (Copyleft: Ableitungen muessen unter
  derselben Lizenz weitergegeben werden). Fuer Flaggen/Symbol-Icons.
- **Kenney.nl** -- CC0 (Public Domain). Fallback fuer generische UI-Elemente,
  wenn game-icons.net/OpenMoji nichts Passendes bieten.
- **OpenGameArt.org** / **itch.io** -- Mischlizenzen pro Upload/Pack, vor
  Verwendung jeweils einzeln pruefen und hier eintragen.

## Format fuer neue Eintraege

```
| dateiname.svg | https://quelle.example/pfad | CC-BY 3.0 (Autor: XY) | Policy-Icon "Bildung" |
```
