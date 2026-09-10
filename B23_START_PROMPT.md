# B23 Start-Prompt — Party-Gründung (Persistente Meta-Ebene)

**Session-Datum:** 2026-09-11+ (nach B15 abgeschlossen)

## Kontext

B15 Opposition-Loop ist **Feature-Complete**. Jetzt: Partei wird zur persistenten Entity über Sessions hinweg.

**Status nach B15:**
- ✅ Sim-Engine (Opposition-Satisfaction, Koalitionsfähigkeit berechnet)
- ✅ Backend-API (Opposition-Persistierung, Kampagnen-Verarbeitung)
- ✅ Frontend-UI (Sonntagsfrage-Overlay, Wahl-Dialog)
- 📋 **B23 Planning ready** (siehe CLAUDE.md Sprint 5)

## B23 Scope (3 Phasen)

### **Phase 1: Backend-DB & Ideologie-System**
**Ziel:** Party-Tabelle + Ideologie-Modifikatoren

1. Neue `Party` Model (`backend/app/models/party.py`):
   - `id, name, ideology, founded_at, base_electability, reputation, metadata`
   - Ideologie: "green" | "red" | "blue" (Enum)

2. `GameSession.party_id` Foreign Key hinzufügen

3. Party-Gründungs-Route (`POST /sessions/new-party`):
   - Request: `{name, ideology}`
   - Response: `{session_id, party_id, party_name}`
   - Startet neue Session mit dieser Party

4. Ideologie-Effekte implementieren:
   - Voter-Affinität-Modifikatoren je Ideologie
   - Grüne: +20% Umweltbewusste, -5% Wirtschaft
   - Rot: +15% Arbeitnehmer, -8% Konservativ-Bürgerliche
   - Blau: +15% Wirtschaft, -10% Umweltbewusste

5. Tests: 8 neue Backend-Tests
   - Party-Gründung, Ideologie-Effekte, Persistierung

### **Phase 2: Frontend-UI**
**Ziel:** Game-Start-Menu + Party-Gründungs-Dialog

1. Game-Start-Menu Redesign:
   - "Neue Partei gründen" vs. "Existierende laden"
   - Wahl-Modal statt direkter Start

2. Party-Gründungs-Dialog:
   - Name-Input
   - Ideologie-Wahl (3 Buttons mit Icons + Effekt-Vorschau)
   - "Gründen" Button

3. Party-Header in Session:
   - Partei-Name + Ideologie-Symbol
   - Z.B. "🟢 Grüne Partei" in der Statusleiste

4. Tests: Frontend Build+Lint grün

### **Phase 3: Sim-Engine Ideologie-Effekte**
**Ziel:** Ideologie wirkt auf Voter-Affinität

1. `voter_groups.json` oder im Engine:
   - Ideologie-Multiplikatoren je Wählergruppe
   - `green_multiplier, red_multiplier, blue_multiplier`

2. `_weighted_approval()` updaten:
   - Voter-Affinität × Ideologie-Multiplikator berücksichtigen

3. Tests: 5 neue Sim-Tests
   - Ideologie-Effekte auf Approval
   - Balance-Runner (kein dominantes Ideologie)

## Arbeitspfade (Start morgen)

### Backend Files:
- `backend/app/models/party.py` (neu)
- `backend/app/models/game.py` (GameSession.party_id hinzufügen)
- `backend/app/api/routes_game.py` (POST /sessions/new-party)
- `backend/app/sim_bridge.py` (Party-Ideologie laden)
- `backend/app/schemas/game.py` (PartyOut, NewPartyRequest)
- `backend/tests/test_party.py` (neu, 8 Tests)

### Frontend Files:
- `frontend/src/App.jsx` (Game-Start-Menu + Dialog)
- `frontend/src/api.js` (createPartySession API-Call)
- `frontend/src/App.css` (Dialog-Styling, Party-Header)

### Sim Engine Files:
- `sim/landtag_sim/models.py` (Party Dataclass)
- `sim/landtag_sim/sample_data.py` (SAMPLE_IDEOLOGY_EFFECTS)
- `sim/landtag_sim/engine.py` (_weighted_approval Ideologie-Multiplikator)
- `sim/tests/test_engine.py` (5 neue Tests)

## Design-Highlights (UI)

**Game-Start (neu):**
```
┌─────────────────────────────┐
│ Landtag-Simulation          │
├─────────────────────────────┤
│ [ Neue Partei gründen ]     │
│ [ Existierende laden ]      │
│ [ Demo-Modus (optional) ]   │
└─────────────────────────────┘
```

**Party-Gründungs-Dialog:**
```
┌──────────────────────────┐
│ Neue Partei gründen      │
├──────────────────────────┤
│ Name: [_____________]    │
│                          │
│ Ideologie (Effekte):     │
│ 🟢 Grün  (+Umwelt)       │
│ 🔴 Rot   (+Arbeit)       │
│ 🔵 Blau  (+Wirtschaft)   │
│                          │
│ [ Gründen ] [ Abbrechen ]│
└──────────────────────────┘
```

**Party-Header in Session:**
```
┌─────────────────────────────────┐
│ 🟢 Grüne Partei · Niedersachsen │
└─────────────────────────────────┘
```

## Reihenfolge (empfohlen)

1. **Phase 1a:** Backend-DB (Party-Model, GameSession.party_id)
2. **Phase 1b:** Party-Ideologie-Effekte + Tests
3. **Phase 2a:** Frontend Game-Start-Menu + Dialog
4. **Phase 3:** Sim-Engine Ideologie-Modifikatoren + Tests

Parallel möglich: Frontend Phase 2 während Backend Phase 1 läuft (separation of concerns).

## Notes

- **Ideologie-Multiplikatoren:** Tune nach Balance-Runner (keine dominante Ideologie)
- **DB-Migration:** `gameSession.party_id` Foreign Key hat Default (zuerst NULL, dann nicht-null nach Party-Gründung)
- **Zukunft (M6+):** Multi-Party-Koalition, Bundes-Ebene Partei-Progression

---

**Status:** Ready für 2026-09-11+ Start. B15 dokumentiert, B23 geplant.
