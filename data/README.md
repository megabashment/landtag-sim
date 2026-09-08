# Datenquellen

## Wichtige Korrektur gegenueber der urspruenglichen Planung

In der Projekt-Scoping-Diskussion war zunaechst Weltbank Open Data + V-Dem/
Freedom House als Datenquellen-Set vorgesehen. Das gilt aber nur auf
**Nationalebene**. Da das MVP auf **Niedersachsen** (Bundesland-Ebene) laeuft,
liefern diese Quellen keine ausreichend granularen Werte. Fuer den MVP-Scope
gilt daher:

| Ebene | Quelle | Granularitaet | Lizenz |
|---|---|---|---|
| MVP: Niedersachsen | [Landesamt fuer Statistik Niedersachsen (LSN)](https://www.landesdatenbank.de) bzw. [Regionalstatistik.de](https://www.regionalstatistik.de) (Destatis-Verbund) | Bundesland/Kreis-Ebene | Datenlizenz Deutschland – Namensnennung |
| Kartengeometrie | [Natural Earth](https://www.naturalearthdata.com) (Admin-1-Ebene) oder [GeoBasis-DE / BKG Verwaltungsgebiete (VG250)](https://gdz.bkg.bund.de) | Bundeslandgrenzen als GeoJSON | Public Domain (Natural Earth) bzw. Datenlizenz Deutschland (BKG) |
| Spaeter, Skalierungsstufe Nation | [Weltbank Open Data](https://data.worldbank.org) | Land | CC-BY 4.0 |
| Spaeter, Skalierungsstufe Nation/EU | [V-Dem](https://www.v-dem.net) / [Freedom House](https://freedomhouse.org) | Land | jeweils eigene, meist akademisch-offene Lizenz -- vor Nutzung pruefen |

Das Datenmodell (`backend/app/models/admin_unit.py`, `AdminLevel`) ist bereits
so gebaut, dass eine `AdminUnit` sowohl eine Region (Niedersachsen) als auch
spaeter eine Nation (Deutschland) oder eine supranationale Einheit (EU) sein
kann, jeweils ueber `parent_id` verkettet. Der Umstieg auf eine hoehere Ebene
braucht also kein neues Schema, nur eine neue Importquelle plus neue Zeilen.

## Struktur

- `sources/` -- Import-Skripte, ein Modul pro Quelle. Aktuell Platzhalter
  (siehe Docstrings), da noch keine konkrete Statistik-Auswahl fuer
  Niedersachsen getroffen wurde.
- `geo/` -- heruntergeladene GeoJSON-Dateien. Bewusst in `.gitignore`
  ausgeschlossen (regenerierbar, teils gross) -- Download-Skript statt
  Binaerdaten einchecken.

## Naechster Schritt

Sobald feststeht, welche konkreten Niedersachsen-Statistiken das Spiel
braucht (z.B. Arbeitslosenquote nach Kreis, Bildungsausgaben, CO2-Bilanz),
`sources/lsn_regionalstatistik.py` mit den passenden Tabellencodes aus der
Landesdatenbank fuellen. Die Landesdatenbank bietet einen CSV/Tabellen-Export
pro Statistik -- kein Live-API-Zugriff wie bei Weltbank, daher eher ein
manueller/regelmaessiger Batch-Import als ein Live-Call.
