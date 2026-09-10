# Credits & Lizenzen

Dieses Projekt nutzt ausschliesslich offen lizenzierte Assets (keine
proprietaeren/kommerziellen Sprites). Jede hier eingebundene Datei muss in
dieser Tabelle eingetragen werden -- Pflicht, da die Lizenzen sich
unterscheiden (nicht alle CC0).

| Asset | Quelle | Lizenz | Verwendung |
|---|---|---|---|
| `suitcase` (Icon-Pfad) | [game-icons.net/1x1/delapouite/suitcase](https://game-icons.net/1x1/delapouite/suitcase.html) | CC BY 3.0 (Autor: Delapouite) | Statistik-Icon „Arbeitslosenquote" (`frontend/src/statIcons.js`) |
| `two-coins` (Icon-Pfad) | [game-icons.net/1x1/delapouite/two-coins](https://game-icons.net/1x1/delapouite/two-coins.html) | CC BY 3.0 (Autor: Delapouite) | Statistik-Icon „BIP-Wachstum" |
| `graduate-cap` (Icon-Pfad) | [game-icons.net/1x1/delapouite/graduate-cap](https://game-icons.net/1x1/delapouite/graduate-cap.html) | CC BY 3.0 (Autor: Delapouite) | Statistik-Icon „Bildungsausgaben" |
| `health-normal` (Icon-Pfad) | [game-icons.net/1x1/sbed/health-normal](https://game-icons.net/1x1/sbed/health-normal.html) | CC BY 3.0 (Autor: sbed) | Statistik-Icon „Gesundheitsversorgung" |
| `factory` (Icon-Pfad) | [game-icons.net/1x1/delapouite/factory](https://game-icons.net/1x1/delapouite/factory.html) | CC BY 3.0 (Autor: Delapouite) | Statistik-Icon „CO2-Emissionen" |
| `windmill` (Icon-Pfad) | [game-icons.net/1x1/delapouite/windmill](https://game-icons.net/1x1/delapouite/windmill.html) | CC BY 3.0 (Autor: Delapouite) | Statistik-Icon „Anteil erneuerbare Energien" |

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
