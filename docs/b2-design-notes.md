# B2 Design-Notes: Situations-Layer + ISM-Wirkungsketten

**Datum:** 2026-09-10  
**Status:** Design-Klärung vor Implementierung  
**Zukunft:** Diese Notizen fließen nach Implementierung in `architecture.md` ein.

## Problem: Warum B2 ohne Stat-zu-Stat-Wirkungen "fake" ist

Aktuell (ohne B2):
```
Policy enacten → Statistik ändert sich → Events/Dilemmas feuern bei Schwelle
```

Das fühlt sich isoliert an. Mit B2, aber ohne Stat-zu-Stat:
```
Situation `abwanderung` aktiv → unemployment_rate +0.6 (direkt)
Aber: unemployment hat keine Folge auf gdp_growth
→ Keine echte Spirale, nur eine künstliche Regel
```

Mit B2 + Stat-zu-Stat (neue Architektur):
```
Situation `abwanderung` aktiv → unemployment_rate +0.6
→ Phillips-Kurve: unemployment > NAIRU → gdp_growth sinkt um −0.15
→ Das senkt weitere Jobchancen → weitere Abwanderung
→ Echte Feedback-Loop, emergente Dynamik
```

---

## Design-Entscheidung: VWL-Standards statt Ideologie

Wir orientieren uns an drei etablierten ökonomischen Modellen. Diese sind **politisch neutral** — funktionieren unter Kapitalismus, Sozialdemokratie, gemischten Systemen.

### 1. Phillips-Kurve / Okun's Law
**Kernidee:** Arbeitsmarkt ist über ein Gleichgewicht (NAIRU) mit BIP verbunden.

**Umsetzung:**
```
unemployment_rate ← gdp_growth
- Baseline NAIRU = 5% (natürliche Arbeitslosigkeit)
- Wenn gdp_growth > 2%: unemployment sinkt um −0.15 pro Punkt über +1%
- Wenn gdp_growth < 0%: unemployment steigt um +0.2 pro Punkt unter 0%
- Beschleunigung ab −0.5% (Rezessions-Effekt stärker)
```

**Grund:** Empirisch belegt, in jedem echten Wirtschaftssystem sichtbar.

### 2. Solow-Modell (Humankapital)
**Kernidee:** Bessere Gesundheit/Bildung = höhere Produktivität = langfristiges Wachstum.

**Umsetzung:**
```
healthcare_quality ← gdp_growth
- Mit 2-3-Runden-Lag (Budgetplanungszyklus)
- Boom (gdp > 2%): healthcare +0.2/Turn nach Lag
- Rezession (gdp < 0%): healthcare −0.3/Turn SOFORT (asymmetrisch!)
```

**Grund:** Realistische Politik: Investitionen brauchen Zeit, Sparmaßnahmen sind schnell.

### 3. Umwelt-Kuznets-Kurve
**Kernidee:** CO2-Emissionen hängen vom Entwicklungsstand und Energiequellen ab.

**Umsetzung:**
```
co2_emissions = f(gdp_growth, renewable_share)
- Implizit durch Situations + Policies, keine separate Engine nötig
- Aber: niedrig gdp + niedrig renewable_share = hohe Emissionen (alte Infrastruktur)
- Hohes gdp + hohe renewable_share = saubere Industrie
```

**Grund:** Realistisch — reiche Länder können sich Umweltschutz leisten, arme nicht.

---

## Policy-Architektur: Graduell statt All-or-Nothing

### Aktuelles Problem
- 8 Mega-Policies (z.B. "Gesundheitsreform" PC 4)
- Spieler muss lange sparen, um eine große Reform zu enacten
- Trade-offs sind monolithisch (keine Optionen für "mittlere Wege")

### Neue Architektur: Zerstückelung

**Beispiel: Gesundheitsbereich**

| Policy | PC | Effekte | Narrativ |
|---|---|---|---|
| Elektronische Krankenschreibung | 1 | healthcare +0.8, gdp −0.1 | Digitalisierung, wenig Kosten |
| Telemedizin-Förderung | 2 | healthcare +1.2, gdp −0.2 | Ländlicher Zugang |
| Digitale Patientenakte | 2 | healthcare +0.9, gdp −0.15 | Datenintegration |
| Krankenhausfusion | 2 | healthcare +2.0, gdp −0.3 | Spezialisierung |
| **Vollständige Gesundheitsreform** | 4 | healthcare +12.0, gdp −1.2 | Die große Lösung |

**Spielmechanik:**
- Spieler kann gegen kleine Krise mit 1-2 kleinen Policies ankämpfen
- Oder langfristig graduell aufbauen
- Zusammensetzung ist flexibel (nicht alle braucht es)

### Kritische Bereiche für Zerstückelung

**Policy-Telemetrie (Häufigkeit der Ziele):**
```
gdp_growth:              12 Hebel (7 Policies, 5 Dilemmas) → überrep'd
education_spending:       8 Hebel (4 Policies, 4 Dilemmas) → gut
unemployment_rate:        8 Hebel (3 Policies, 5 Dilemmas) → gut
healthcare_quality:       4 Hebel (1 Policy!, 3 Dilemmas)  → KRITISCH SCHWACH!
co2_emissions:            4 Hebel (2 Policies, 2 Dilemmas) → schwach
renewable_share:          2 Hebel (1 Policy, 1 Dilemma)    → sehr schwach
```

**Priorität für Zerstückelung:**
1. **Healthcare** (nur 1 Policy aktuell, aber 3 Dilemma-Optionen → Imbalance)
2. **CO2/Erneuerbare** (schwach, aber wichtig für Kuznets-Kette)
3. **GDP-Bereich** (überrep'd, aber Gewichte sind narrativ wichtig)

---

## Situations: Minimales Set für echte Spiralen

Nicht alle möglichen Situations bauen, sondern mit 2-3 Kern-Spiralen starten.

### `abwanderung` (Rezessions-Spiral, negativ)
```
Trigger: gdp_growth < −0.2
Deaktiviert: gdp_growth > 0.9 (breites Hysterese-Fenster)
Effekte pro Turn:
  + unemployment_rate +0.6
  + co2_emissions +1.8 (alte Infrastruktur)
  − healthcare_quality −1.5 (Fachkräfte-Abwanderung)
  − education_spending −1.2 (Haushaltskürzungen)
```

**Gegen-Hebel:**
- `bildungsoffensive` (hebt gdp, bricht Spirale)
- Neue kleine Healthcare-Policies (stabilisieren)
- `steuersenkung_mittelstand` (hebt gdp kurzfristig)

### `gruenes_wachstum` (Positive Spiral)
```
Trigger: renewable_share > 42%
Deaktiviert: renewable_share < 37%
Effekte pro Turn:
  + gdp_growth +0.5
  − co2_emissions −2.0
```

**Mechanik:** Selbstverstärkend — hoher renewable Anteil führt zu besserer Konjunktur, die weitere Investitionen ermöglicht.

---

## Test-Strategie

1. **Stat-zu-Stat-Funktionen**
   - Phillips: gdp < 0% → unemployment steigt ✓
   - Solow: gdp > 2% nach 2 Runden → healthcare steigt ✓
   - Lag korrekt modelliert ✓

2. **Situations mit Spiralen**
   - `abwanderung` aktiviert bei gdp < −0.2 ✓
   - Effekte werden pro Turn angewendet ✓
   - Deaktiviert erst bei gdp > 0.9 (nicht vorher) ✓

3. **Gegen-Hebel**
   - Policy X bricht `abwanderung` nachweislich (E2E-Test) ✓
   - Balance-Runner meldet keine Death-Spirals ✓

4. **Emergenz**
   - E2E: Spieler kann eine 8-Runden-Rezessions-Episode durchspielen und gegenwirken

---

## Implementierungs-Fahrplan

1. **Stat-zu-Stat-Engine** (`engine.py`, neuer Abschnitt nach Policy-Effekte, vor Events)
   - Phillips-Kurve
   - Solow (mit Lag)
   - Balance-Tests

2. **Situations-Mechanik** (existiert schon teilweise, aber komplettieren)
   - `abwanderung`, `gruenes_wachstum` testen
   - Death-Spiral-Detection im Balance-Runner

3. **Policy-Zerstückelung** (granular, mit Balance-Runner-Validation)
   - Healthcare-Familie (3-4 kleine Policies)
   - CO2/Erneuerbare-Familie
   - GDP-Familie

4. **Integration + Balance**
   - Balance-Runner über alle Kombis + Stat-zu-Stat
   - Keine dominante Policy ✓
   - Alle Situations erreichbar ✓
