# Niedersachsen-Startwerte — reale Kennzahlen vs. Spielwerte

**Abrufdatum:** 2026-09-10
**Betrifft:** `sim/landtag_sim/sample_data.py::STARTING_STATISTICS` (Backlog B13)

Dieses Dokument haelt fest, wie die sechs Start-Statistiken des Spiels
gegen reale Niedersachsen-Zahlen abgeglichen wurden. Es ersetzt **nicht**
den geplanten GENESIS-API-Import (siehe `lsn_regionalstatistik.py`) — das
bleibt ein spaeterer, automatisierter Schritt. Hier geht es um einen
einmaligen, manuell recherchierten Plausibilitaets-Anker plus die
bewussten Abweichungen.

## Warum Spielwerte teils von der Realitaet abweichen

Der Balance-Runner und die gesamte Content-Erreichbarkeit (Policies,
Events, Dilemmas, Situations aus B12) sind auf die aktuellen Startwerte
getunt. Ein 1:1-Uebernehmen der realen Zahlen (z.B. `renewable_share` von
35 auf 54+) wuerde Freischalt-Schwellen, Situations-Aktivierungen und
Event-Trigger schon in Runde 0 ausloesen und die Progression zerstoeren.
`data/README.md` haelt denselben Grundsatz fest: der Balance-Runner nutzt
bewusst synthetische Werte. Startwerte sind daher **plausibel verankert,
nicht mechanisch importiert**.

## Kennzahlen

| Statistik | Spielwert | Reale Referenz (Nds.) | Quelle | Umgang |
|---|---|---|---|---|
| `unemployment_rate` | **5.9** | Arbeitslosenquote Jahresdurchschnitt 2024: **5,9 %** (Bund: 6,0 %) | LSN-Pressemitteilung „Zahl der Erwerbstätigen … 2024" | direkt übernommen |
| `gdp_growth` | **1.2** | reales BIP-Wachstum 2024: **+0,4 %** (Bund: −0,2 %) | LSN-Pressemitteilung „Bruttoinlandsprodukt in Niedersachsen wuchs 2024 um 0,4 %" | 2024 war konjunkturell schwach; Spielstart nutzt den längerfristigen Nds.-Korridor (~1,0–1,5 %), sonst Start direkt in der `konjunkturdelle`/`strompreiskrise`-Triggerzone |
| `renewable_share` | **35.0** | Anteil Erneuerbare am Bruttostromverbrauch 2024: **54,4 %** physisch bzw. **102,3 %** bilanziell (2022: 89,9 %) | Klimaschutz- und Energieagentur Niedersachsen / Energiewendebericht 2024 | Spiel modelliert bewusst eine **frühere** Energiewende-Phase (~Nds. Mitte 2010er), damit der Ausbau ein Spiel-Hebel bleibt |
| `co2_emissions` | **100.0** | Treibhausgas-Emissionen Nds.: **−33,8 %** ggü. 1990, **−10,9 %** ggü. 2022; ~75 Mt CO₂e (2021) | Energiewendebericht 2024 / „Bericht über die Entwicklung der Treibhausgasemissionen in Niedersachsen" | 0–100-**Index**, keine Tonnen. 100 = Startniveau; sinkende Werte bilden den real beobachteten Rückgang ab |
| `education_spending` | **40.0** | keine einzelne amtliche Entsprechung (Bildungsausgaben je Kopf, Betreuungsquoten etc. sind mehrere Reihen) | — | synthetischer 0–100-Index, plausibel gesetzt |
| `healthcare_quality` | **60.0** | keine einzelne amtliche Entsprechung (Ärztedichte, Bettenzahl, Wartezeiten etc.) | — | synthetischer 0–100-Index, plausibel gesetzt |

## Quellen (Abruf 2026-09-10)

- LSN — Zahl der Erwerbstätigen in Niedersachsen lag im Jahresdurchschnitt 2024 bei 4,2 Millionen Personen
  <https://www.statistik.niedersachsen.de/presse/zahl-der-erwerbstatigen-in-niedersachsen-lag-im-jahresdurchschnitt-2024-bei-4-2-millionen-personen-239033.html>
- LSN — Bruttoinlandsprodukt in Niedersachsen wuchs 2024 um 0,4 %
  <https://www.statistik.niedersachsen.de/presse/bruttoinlandsprodukt-in-niedersachsen-wuchs-2024-um-0-4-240586.html>
- Klimaschutz- und Energieagentur Niedersachsen — Anteil der Erneuerbaren am Bruttostromverbrauch stieg 2024 auf 54,4 Prozent
  <https://www.klimaschutz-niedersachsen.de/aktuelles/Anteil-der-Erneuerbaren-am-Bruttostromverbrauch-stieg-2024-auf-544-Prozent-4273>
- Niedersächsisches Umweltministerium — Energiewendebericht 2024
  <https://www.umwelt.niedersachsen.de/download/217807/Energiewendebericht_2024.pdf>
- Niedersächsisches Umweltministerium — Bericht über die Entwicklung der Treibhausgasemissionen in Niedersachsen
  <https://www.umwelt.niedersachsen.de/download/216883>

Alle genannten Quellen: Datenlizenz Deutschland – Namensnennung (siehe
`data/README.md`).
