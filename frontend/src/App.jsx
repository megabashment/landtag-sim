import { useEffect, useState } from "react";
import { api } from "./api";
import { STAT_ICON_PATHS } from "./statIcons";
import { PARTY_ICONS } from "./partyIcons";
import "./App.css";

// B14: kleines Statistik-Icon (game-icons.net, CC BY 3.0 -- siehe CREDITS.md).
// Faellt lautlos aus, wenn fuer einen Key kein Pfad hinterlegt ist.
function StatIcon({ statKey }) {
  const d = STAT_ICON_PATHS[statKey];
  if (!d) return null;
  return (
    <svg className="stat-icon" viewBox="0 0 512 512" aria-hidden="true">
      <path fill="currentColor" d={d} />
    </svg>
  );
}

const FAST_FORWARD_SAFETY_CAP = 40; // Sicherheitsnetz gegen Endlosschleifen im Client

// Nach-P2-Nachschaerfung (Doku-Audit 2026-09-09, siehe mistakes.md/CLAUDE.md
// "Frontend hat keine Verlaufsansicht"): events/attributions/electionResult
// wurden bisher bei JEDEM /advance-Aufruf komplett ueberschrieben -- ein
// Spieler sah nur die letzte Runde, keine Historie. HISTORY_LIMIT begrenzt
// den clientseitigen Verlauf (reines UI-Array, nichts Serverseitiges), damit
// eine lange Partie mit vielen Vorspul-Runden nicht unbegrenzt waechst.
const HISTORY_LIMIT = 60;

// UI-Konstanten, die die Engine kennt, das Backend aber nicht pro Session
// mitschickt (siehe CLAUDE.md): Laenge einer Legislaturperiode (Wahl-Zyklus)
// und die Obergrenze fuer politisches Kapital (CAPITAL_CAP in
// landtag_sim.engine). Rein fuer die Statusleiste-Darstellung.
const ELECTION_CYCLE = 16;
const CAPITAL_CAP = 10;

// M5 "Opposition-Loop" (BACKLOG.md B15): Opposition-Kampagnen (Placeholder für MVP).
// Idealerweise vom Backend kommen, aber für Prototyping hardcoded.
const _OPPOSITION_CAMPAIGNS = [
  {
    key: "arbeitsmarkt_kritik",
    name: "Arbeitsmarkt-Kritik",
    description: "Attacke gegen Regierungs-Arbeitsmarktversprechungen",
    capital_cost: 2.0,
  },
  {
    key: "sozialversprechen_kampagne",
    name: "Sozialversprechen",
    description: "Gemäßigte Positon: gerechtige Verteilung",
    capital_cost: 2.5,
  },
  {
    key: "umwelt_offensiv",
    name: "Umwelt-Offensiv",
    description: "Radikale Grünen-Politik (polarisiert)",
    capital_cost: 3.0,
  },
  {
    key: "budget_kritik",
    name: "Haushalt-Kritik",
    description: "Finanzkonservative Kritik",
    capital_cost: 1.5,
  },
];

// M5 "Opposition-Loop" (BACKLOG.md B15 Phase 4): Sonntagsfrage-Overlay
// im Stil deutscher Umfragen. Zeigt Regierung vs. Opposition mit
// Koalitionsfähigkeit-Schwelle (30%).
// B23 "Party-Gründung (Persistente Meta-Ebene)" Phase 2: Game-Start-Menu
// mit Option "Neue Partei gründen" vs. "Existierende laden"
function GameStartMenu({ onNewParty, onStartClassic, disabled }) {
  return (
    <div className="game-start-menu">
      <h2>Landtag-Simulation</h2>
      <p>Wähle einen Modus zum Starten:</p>
      <button className="button-primary" onClick={onNewParty} disabled={disabled}>
        🟢 Neue Partei gründen
      </button>
      <button className="button-secondary" onClick={onStartClassic} disabled={disabled}>
        ▶ Klassische Partie
      </button>
    </div>
  );
}

// Party-Gründungs-Dialog mit Name-Input und Ideologie-Wahl + Party-Beispiele
function PartyCreationDialog({
  onClose,
  onConfirm,
  disabled,
  name,
  setName,
  ideology,
  setIdeology,
  error
}) {
  // Beispiel-Parteien je Ideologie
  const partyExamples = {
    green: ["die-grünen", "ökobewegung", "naturfreunde"],
    red: ["spd", "linke", "arbeiterpartei"],
    blue: ["cdu", "fwirtschaft", "unternehmerbund"],
  };

  const ideologies = [
    { key: "green", label: "🟢 Grün", desc: "+Umwelt, -Wirtschaft" },
    { key: "red", label: "🔴 Rot", desc: "+Arbeit, -Konservativ" },
    { key: "blue", label: "🔵 Blau", desc: "+Wirtschaft, -Umwelt" },
  ];

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2>Neue Partei gründen</h2>
        {error && <p className="error">{error}</p>}

        <label>
          Parteiname:
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="z.B. Die Grünen"
            disabled={disabled}
          />
        </label>

        <label>Ideologie (Effekte auf Wählergruppen):</label>
        <div className="ideology-buttons">
          {ideologies.map((id) => {
            const examples = partyExamples[id.key] || [];
            return (
              <button
                key={id.key}
                className={`ideology-button ${ideology === id.key ? "selected" : ""}`}
                onClick={() => setIdeology(id.key)}
                disabled={disabled}
              >
                <div className="ideology-label">{id.label}</div>
                <div className="ideology-desc">{id.desc}</div>
                <div className="ideology-examples">
                  {examples.map((partyKey) => {
                    const party = PARTY_ICONS[partyKey];
                    return party ? (
                      <span key={partyKey} title={party.name} className="party-icon">
                        {party.icon}
                      </span>
                    ) : null;
                  })}
                </div>
              </button>
            );
          })}
        </div>

        <div className="button-row">
          <button onClick={onConfirm} disabled={disabled || !name.trim()}>
            Partei gründen
          </button>
          <button onClick={onClose} disabled={disabled} className="button-secondary">
            Abbrechen
          </button>
        </div>
      </div>
    </div>
  );
}

function SonntagsfragOverlay({ session }) {
  if (!session) return null;

  // Koalitionsfähigkeit berechnen (Näherung basierend auf Stats + Opposition-Satisfaction)
  // Regierung: aus Stats + Wähler-Zufriedenheit abgeleitet
  const regierungProzent = Math.round(
    ((session.approval ?? 50) + (session.satisfaction_momentum ?? 0)) / 2
  );

  // Opposition: aus opposition_satisfaction abgeleitet
  const oppositionSatisfaction = session.opposition_satisfaction ?? {};
  const avgOppositionSat = Object.values(oppositionSatisfaction).length > 0
    ? Object.values(oppositionSatisfaction).reduce((a, b) => a + b, 0) /
      Object.values(oppositionSatisfaction).length
    : 0;
  const oppositionProzent = Math.round(Math.max(0, Math.min(100, avgOppositionSat)));

  const coalitionThreshold = 30;
  const regierungExceedsThreshold = regierungProzent >= coalitionThreshold;
  const oppositionExceedsThreshold = oppositionProzent >= coalitionThreshold;

  return (
    <div className="sonntagsfrage-overlay">
      <h2 className="sonntagsfrage-title">Sonntagsfrage: Koalitionsfähigkeit</h2>

      <div className="sonntagsfrage-bars">
        <div className="bar-container">
          <div
            className={`bar regierung-bar ${regierungExceedsThreshold ? "viable" : "not-viable"}`}
            style={{ width: `${regierungProzent}%` }}
          >
            <span className="bar-label">Regierung</span>
          </div>
          <span className="bar-percent">{regierungProzent}%</span>
        </div>

        <div className="bar-container">
          <div
            className={`bar opposition-bar ${oppositionExceedsThreshold ? "viable" : "not-viable"}`}
            style={{ width: `${oppositionProzent}%` }}
          >
            <span className="bar-label">Opposition</span>
          </div>
          <span className="bar-percent">{oppositionProzent}%</span>
        </div>
      </div>

      <div className="sonntagsfrage-threshold">
        <div
          className="threshold-line"
          style={{ left: `${coalitionThreshold}%` }}
        />
        <span className="threshold-label">Schwelle: {coalitionThreshold}%</span>
      </div>

      {session.opposition_mode && (
        <p className="hint opposition-mode-hint">
          Du spielst als <strong>Opposition</strong>. Ziel: Koalitionsfähigkeit auf {coalitionThreshold}% oder mehr bringen.
        </p>
      )}
    </div>
  );
}

// Phase 3 des Frontend-Umbaus: die persistente Statusleiste als "Amtsblatt-
// Kopf" -- Ledger-Felder mit Kennzahl je Ressource, plus als Signatur ein
// Legislatur-Band (16 Runden), das den Wahltermin von einer abstrakten Zahl
// in einen sichtbaren Bogen der Amtszeit uebersetzt (L10 "take players on a
// journey"). Die uebrigen Panels folgen in spaeteren Phasen.
function StatusBar({ session, events }) {
  const toElection = session.turns_until_election;
  const elapsed = Math.max(0, Math.min(ELECTION_CYCLE, ELECTION_CYCLE - toElection));
  const urgent = toElection <= 3;
  const capitalSegments = Math.max(
    0,
    Math.min(CAPITAL_CAP, Math.round(session.political_capital))
  );

  // B2 "Situations-Layer": aktuell wirksame Zustaende (Rezession usw.). Dazu
  // ein offenes Dilemma und die Ereignisse der letzten Runde -- zusammen die
  // "Lage" unter der Statusleiste.
  const situations = session.active_situations ?? [];
  const dilemmaPending = Boolean(session.pending_dilemma);
  const roundEvents = events ?? [];

  const roleLabel = session.role === "opposition" ? "Opposition" : "Regierung";
  const statusLabel =
    session.status === "active"
      ? "im Amt"
      : session.status === "lost"
        ? "abgewaehlt"
        : session.status;

  return (
    <>
    <section className="statusbar" aria-label="Lage des Kabinetts">
      <div className="statusbar__fields">
        <div className="field">
          <span className="field__label">Runde</span>
          <span className="field__value">{session.turn}</span>
        </div>
        <div className="field">
          <span className="field__label">Haushalt</span>
          <span className="field__value">{session.budget.toFixed(1)}</span>
        </div>
        <div className="field">
          <span className="field__label">Politisches Kapital</span>
          <span className="field__value">
            {session.political_capital.toFixed(1)}
            <span className="meter" aria-hidden="true">
              {Array.from({ length: CAPITAL_CAP }, (_, i) => (
                <span
                  key={i}
                  className={`meter__seg ${i < capitalSegments ? "meter__seg--on" : ""}`}
                />
              ))}
            </span>
          </span>
        </div>
        <div className="field field--role">
          <span className="field__label">Mandat</span>
          <span className="field__value">
            {roleLabel} &middot; {statusLabel}
          </span>
        </div>
      </div>

      <div className={`term ${urgent ? "term--urgent" : ""}`}>
        <span className="term__count">
          {toElection === 0 ? "Wahltag" : `Wahl in ${toElection} Runden`}
        </span>
        <span
          className="term__ribbon"
          role="img"
          aria-label={`Runde ${elapsed} von ${ELECTION_CYCLE} der Legislaturperiode`}
        >
          {Array.from({ length: ELECTION_CYCLE }, (_, i) => {
            const seal = i === ELECTION_CYCLE - 1;
            const done = i < elapsed;
            return (
              <span
                key={i}
                className={`term__tick ${done ? "term__tick--done" : ""} ${
                  seal ? "term__tick--seal" : ""
                }`}
              />
            );
          })}
        </span>
      </div>
    </section>

    <div className="lage" aria-label="Aktuelle Lage">
      <span className="lage__label">Lage</span>
      {situations.length === 0 && !dilemmaPending && roundEvents.length === 0 ? (
        <span className="lage__calm">Keine besonderen Vorkommnisse.</span>
      ) : (
        <ul className="lage__chips">
          {dilemmaPending && (
            <li className="chip chip--alert">Dilemma zu entscheiden</li>
          )}
          {situations.map((s) => (
            <li key={s.key} className="chip chip--situation" title={s.label}>
              {s.label.split(":")[0]}
              <span className="chip__since">seit R. {s.since_turn}</span>
            </li>
          ))}
          {roundEvents.map((text, i) => (
            <li key={i} className="chip chip--event" title={text}>
              {text}
            </li>
          ))}
        </ul>
      )}
    </div>
    </>
  );
}

// Grobe Groessenklassen statt exakter Zahlen (P0-Punkt "Effekt-Vorschau",
// Vorbild Frostpunks Book of Laws: qualitative Richtung, vage Quantitaet --
// genug fuer eine informierte Entscheidung, ohne die Spannung durch exakte
// Zahlen zu zerstoeren, siehe docs/game-design-roadmap.md).
function magnitudeClass(delta) {
  const abs = Math.abs(delta);
  if (abs < 0.3) return "schwach";
  if (abs < 1.5) return "mittel";
  return "stark";
}

function DeltaArrow({ delta }) {
  if (!delta) return null;
  const up = delta > 0;
  return (
    <span className={`delta ${up ? "delta-up" : "delta-down"}`}>
      {up ? "↑" : "↓"} {magnitudeClass(delta)}
    </span>
  );
}

// B5 "Wahlprognose mit sichtbarem Turnout/Apathie": Trendpfeil je Waehler-
// gruppe (Backend liefert "steigend" | "stabil" | "fallend").
function TrendArrow({ trend }) {
  const glyph = trend === "steigend" ? "↑" : trend === "fallend" ? "↓" : "→";
  const cls = trend === "steigend" ? "delta-up" : trend === "fallend" ? "delta-down" : "";
  return <span className={`delta ${cls}`} title={trend}>{glyph}</span>;
}

export default function App() {
  const [session, setSession] = useState(null);
  // Dynamischer Policy-Katalog (GET /policies) statt der frueheren hart
  // codierten AVAILABLE_POLICIES-Konstante -- ersetzt eine in README.md/
  // CLAUDE.md dokumentierte "Bekannte Vereinfachung". Wird einmalig beim
  // Laden der App geholt (Katalog ist global, nicht pro Session).
  const [policies, setPolicies] = useState([]);
  const [selectedPolicies, setSelectedPolicies] = useState([]);
  // Democracy-4-Vorbild "Policy-Repeal" (siehe CLAUDE.md/landtag_sim.
  // engine.py::advance_turn): Policy-Keys, die diese Runde zurueckgezogen
  // werden sollen. Getrennt von selectedPolicies, weil ein Key nie
  // gleichzeitig neu eingefuehrt UND zurueckgezogen werden kann.
  const [selectedRepeals, setSelectedRepeals] = useState([]);
  // M5 "Opposition-Loop" (BACKLOG.md B15): Opposition-Kampagnen-UI
  // const [oppositionCampaigns, setOppositionCampaigns] = useState([]); // TODO: Phase 4c
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [showOppositionChoice, setShowOppositionChoice] = useState(false);
  const [events, setEvents] = useState([]);
  const [attributions, setAttributions] = useState([]);
  // B4 "Narrative Konsequenz-Ebene" (BACKLOG.md): rein textliche
  // Presseschau-Meldungen (kein Sim-Effekt), hoechstens eine pro Runde und
  // nur in Runden ohne Ereignis/Dilemma.
  const [reports, setReports] = useState([]);
  const [electionResult, setElectionResult] = useState(null);
  // B1 "Legislatur-Bogen & Amtszeit-Debrief" (BACKLOG.md): Bilanz der gerade
  // abgelaufenen Legislaturperiode, kommt nur am Wahl-Turn im
  // AdvanceTurnResponse mit (sonst null).
  const [termSummary, setTermSummary] = useState(null);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  // Verlaufsansicht (siehe HISTORY_LIMIT oben): ein Eintrag pro Runde
  // (advance/fast-forward) bzw. pro aufgeloestem Dilemma, neueste zuerst.
  const [history, setHistory] = useState([]);
  // B23 "Party-Gründung (Persistente Meta-Ebene)": UI-State für Partei-Gründungs-Dialog
  const [showGameStart, setShowGameStart] = useState(true);
  const [showPartyCreation, setShowPartyCreation] = useState(false);
  const [partyName, setPartyName] = useState("");
  const [partyIdeology, setPartyIdeology] = useState("green");

  function pushHistoryEntry(entry) {
    setHistory((prev) => [entry, ...prev].slice(0, HISTORY_LIMIT));
  }

  const dilemmaPending = Boolean(session?.pending_dilemma);
  const gameOver = Boolean(session && session.status !== "active");

  function policyLabel(key) {
    const policy = policies.find((p) => p.key === key);
    return policy ? policy.name : key;
  }

  // Policy-Katalog einmalig beim Laden holen (GET /policies) -- unabhaengig
  // von einer Session, damit die Auswahl-UI auch ohne laufende Partie
  // Namen/Kosten/Voraussetzungen kennt.
  useEffect(() => {
    let cancelled = false;
    api
      .listPolicies()
      .then((result) => {
        if (!cancelled) setPolicies(result);
      })
      .catch(() => {
        if (!cancelled) setPolicies([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Effekt-Vorschau (P0.1): sobald sich die Policy-Auswahl aendert, wird die
  // naechste Runde read-only simuliert und verworfen (kein Persistieren,
  // siehe backend/app/api/routes_game.py::preview_session_turn). Waehrend
  // ein Dilemma offen ist oder die Partie beendet ist, gibt es nichts zu
  // previewen -- advance ist ohnehin blockiert.
  useEffect(() => {
    if (!session || session.status !== "active" || dilemmaPending) {
      setPreview(null);
      return;
    }
    let cancelled = false;
    api
      .previewTurn(session.session_id, selectedPolicies, selectedRepeals)
      .then((result) => {
        if (!cancelled) setPreview(result);
      })
      .catch(() => {
        if (!cancelled) setPreview(null);
      });
    return () => {
      cancelled = true;
    };
  }, [session, selectedPolicies, selectedRepeals, dilemmaPending]);

  async function handleStart() {
    setError(null);
    setLoading(true);
    try {
      const created = await api.createSession();
      const state = await api.getSession(created.session_id);
      setSession(state);
      setShowGameStart(false);
      setEvents([]);
      setAttributions([]);
      setReports([]);
      setElectionResult(null);
      setTermSummary(null);
      setSelectedPolicies([]);
      setSelectedRepeals([]);
      setHistory([]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateParty() {
    if (!partyName.trim()) {
      setError("Parteiname erforderlich");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const created = await api.createPartySession(partyName, partyIdeology);
      const state = await api.getSession(created.session_id);
      setSession(state);
      setShowGameStart(false);
      setShowPartyCreation(false);
      setPartyName("");
      setEvents([]);
      setAttributions([]);
      setReports([]);
      setElectionResult(null);
      setTermSummary(null);
      setSelectedPolicies([]);
      setSelectedRepeals([]);
      setHistory([]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleAdvance() {
    if (!session) return;
    setError(null);
    setLoading(true);
    try {
      // M5 "Opposition-Loop": Opposition-Kampagne statt Policies
      const result = await api.advanceTurn(
        session.session_id,
        session.opposition_mode ? [] : selectedPolicies,
        session.opposition_mode ? [] : selectedRepeals,
        session.opposition_mode ? selectedCampaign : null
      );
      setSession(result.state);
      setEvents(result.events);
      setAttributions(result.attributions);
      setReports(result.reports ?? []);
      setElectionResult(result.election_result);
      setTermSummary(result.term_summary);
      setSelectedPolicies([]);
      setSelectedRepeals([]);
      setSelectedCampaign(null);

      // Wahlverlust-Dialog (Opposition-Option)
      if (result.election_result && !result.election_result.won && !result.state.opposition_mode) {
        setShowOppositionChoice(true);
      }

      pushHistoryEntry({
        kind: "advance",
        turn: result.state.turn,
        events: result.events,
        reports: result.reports ?? [],
        attributions: result.attributions,
        election: result.election_result,
        dilemmaTriggered: result.pending_dilemma !== null,
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // P1-Punkt "Fast-Forward/Pacing-Kontrollen" (docs/game-design-roadmap.md):
  // spult ereignislose Runden automatisch durch, ohne dass der Spieler jede
  // einzeln bestaetigen muss -- passt zum "entspannt"-Ziel des Briefings.
  // Rein clientseitig: ruft /advance wiederholt mit leerer Policy-Auswahl
  // auf und bricht ab, sobald etwas Interessantes passiert (Ereignis, Wahl,
  // Dilemma, Spielende) oder ein Sicherheitslimit erreicht ist.
  async function handleFastForward() {
    if (!session) return;
    setError(null);
    setLoading(true);
    try {
      let result = null;
      const skippedEntries = [];
      for (let i = 0; i < FAST_FORWARD_SAFETY_CAP; i++) {
        result = await api.advanceTurn(session.session_id, [], [], null);
        skippedEntries.push({
          kind: "advance",
          turn: result.state.turn,
          events: result.events,
          reports: result.reports ?? [],
          attributions: result.attributions,
          election: result.election_result,
          dilemmaTriggered: result.pending_dilemma !== null,
        });
        const shouldStop =
          result.events.length > 0 ||
          (result.reports?.length ?? 0) > 0 ||
          result.election_result !== null ||
          result.pending_dilemma !== null ||
          result.state.status !== "active";
        if (shouldStop) break;
      }
      setSession(result.state);
      setEvents(result.events);
      setAttributions(result.attributions);
      setReports(result.reports ?? []);
      setElectionResult(result.election_result);
      setTermSummary(result.term_summary);
      setSelectedPolicies([]);
      setSelectedRepeals([]);
      // Vorspulen kann mehrere Runden ueberspringen -- JEDE davon bekommt
      // einen eigenen Verlaufseintrag (neueste zuerst), nicht nur die letzte.
      setHistory((prev) => [...skippedEntries.reverse(), ...prev].slice(0, HISTORY_LIMIT));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // P1-Punkt "Dilemma-Events mit echten Entscheidungsoptionen": wendet die
  // gewaehlte Option an. Zaehlt keine Runde (siehe engine.py::resolve_dilemma).
  async function handleResolveDilemma(optionKey) {
    if (!session) return;
    setError(null);
    setLoading(true);
    try {
      const result = await api.resolveDilemma(session.session_id, optionKey);
      setSession(result.state);
      setAttributions(result.attributions);
      setEvents([]);
      setReports([]);
      setElectionResult(null);
      setTermSummary(null);
      pushHistoryEntry({
        kind: "dilemma",
        turn: result.state.turn,
        optionKey,
        events: [],
        reports: [],
        attributions: result.attributions,
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function togglePolicy(key) {
    setSelectedPolicies((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  }

  // Democracy-4-Vorbild "Policy-Repeal": analog zu togglePolicy, aber fuer
  // bereits aktive Policies, die diese Runde zurueckgezogen werden sollen.
  function toggleRepeal(key) {
    setSelectedRepeals((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  }

  // Democracy-4-Vorbild: eine Policy, von der noch eine aktive Policy
  // abhaengt (Policy.requires), kann nicht zurueckgezogen werden (siehe
  // PolicyRequiredByActivePolicyError in landtag_sim.models) -- die UI
  // blendet den Repeal-Button in dem Fall aus, statt einen 400er zu riskieren.
  function activeDependents(policyKey) {
    if (!session) return [];
    return policies
      .filter((p) => session.active_policy_keys.includes(p.key) && p.requires.includes(policyKey))
      .map((p) => p.name);
  }

  function unmetRequirements(policy) {
    if (!session) return policy.requires;
    return policy.requires.filter(
      (req) => !session.active_policy_keys.includes(req) && !selectedPolicies.includes(req)
    );
  }

  // B7 "Dynamische Policy-Freischaltung durch Sim-Zustand": Freischalt-
  // Bedingungen (Statistik-Schwellen) gegen die aktuellen Session-Statistiken
  // pruefen. Gibt die noch NICHT erfuellten Bedingungen als lesbare Strings
  // zurueck (leer = freigeschaltet). Dieselbe Logik wie engine.py::
  // policy_is_unlocked -- die UI graut die Policy aus, statt einen 400er beim
  // Einfuehren zu riskieren.
  const UNLOCK_OPS = {
    ">": (a, b) => a > b,
    "<": (a, b) => a < b,
    ">=": (a, b) => a >= b,
    "<=": (a, b) => a <= b,
    "==": (a, b) => a === b,
    "!=": (a, b) => a !== b,
  };

  function unmetUnlocks(policy) {
    if (!session || !policy.unlock_conditions) return [];
    return policy.unlock_conditions
      .filter((c) => {
        const value = session.statistics[c.statistic_key];
        const op = UNLOCK_OPS[c.operator];
        return value === undefined || !op || !op(value, c.threshold);
      })
      .map((c) => `${c.statistic_key} ${c.operator} ${c.threshold}`);
  }

  // Political Capital wird fuer Enact UND Repeal faellig (siehe
  // landtag_sim.engine.py::advance_turn, capital_cost).
  const selectedCapitalCost = [...selectedPolicies, ...selectedRepeals].reduce((sum, key) => {
    const policy = policies.find((p) => p.key === key);
    return sum + (policy?.capital_cost ?? 0);
  }, 0);

  function attributionLabel(source) {
    if (source.startsWith("event:")) {
      return `Ereignis: ${source.slice("event:".length)}`;
    }
    if (source.startsWith("dilemma:")) {
      const [, ruleKey, optionKey] = source.split(":");
      return `Dilemma-Entscheidung (${ruleKey}): ${optionKey}`;
    }
    return policyLabel(source);
  }

  return (
    <main className="layout">
      <header className="masthead">
        <span className="masthead__kicker">Landtag-Simulation &middot; MVP</span>
        <h1>Niedersachsen</h1>
      </header>

      {!session && showGameStart && (
        <>
          <GameStartMenu
            onNewParty={() => setShowPartyCreation(true)}
            onStartClassic={handleStart}
            disabled={loading}
          />
          {showPartyCreation && (
            <PartyCreationDialog
              onClose={() => {
                setShowPartyCreation(false);
                setPartyName("");
                setError(null);
              }}
              onConfirm={handleCreateParty}
              disabled={loading}
              name={partyName}
              setName={setPartyName}
              ideology={partyIdeology}
              setIdeology={setPartyIdeology}
              error={error}
            />
          )}
        </>
      )}

      {error && !showPartyCreation && <p className="error">Fehler: {error}</p>}

      {session && (
        <>
          <StatusBar session={session} events={events} />
          <SonntagsfragOverlay session={session} />

          {dilemmaPending && (
            <section className="panel dilemma-banner">
              <h2>Dilemma: Entscheidung erforderlich</h2>
              <p>{session.pending_dilemma.prompt}</p>
              <ul className="dilemma-options">
                {session.pending_dilemma.options.map((o) => (
                  <li key={o.key}>
                    <button onClick={() => handleResolveDilemma(o.key)} disabled={loading}>
                      {o.label} {o.budget_cost ? `(Budget: -${o.budget_cost.toFixed(1)})` : ""}
                    </button>
                  </li>
                ))}
              </ul>
              <p className="hint">
                Solange dieses Dilemma offen ist, kann keine weitere Runde gespielt werden.
              </p>
            </section>
          )}

          {electionResult && (
            <section className={`panel election-banner ${electionResult.won ? "won" : "lost"}`}>
              <h2>{electionResult.won ? "Wahl gewonnen!" : "Wahl verloren."}</h2>
              <p>
                Zufriedenheit (gewichtet): {electionResult.approval.toFixed(1)} / Schwellenwert{" "}
                {electionResult.threshold.toFixed(1)}
              </p>
              {electionResult.won ? (
                <p>Wiederwahl geschafft &mdash; die naechste Legislaturperiode beginnt.</p>
              ) : (
                <>
                  <p>Die Wahl ist verloren.</p>
                  {showOppositionChoice && !session.opposition_mode && (
                    <div className="opposition-choice">
                      <p>
                        <strong>Option:</strong> Du kannst in die Opposition gehen und versuchen,
                        in der nächsten Legislaturperiode eine Koalition zu bilden.
                      </p>
                      <button
                        onClick={() => {
                          setSession({ ...session, opposition_mode: true });
                          setShowOppositionChoice(false);
                        }}
                        className="button-primary"
                      >
                        In Opposition gehen
                      </button>
                      <button
                        onClick={() => setShowOppositionChoice(false)}
                        className="button-secondary"
                      >
                        Partie beenden
                      </button>
                    </div>
                  )}
                  {!showOppositionChoice && !session.opposition_mode && (
                    <p>Die Partie ist beendet. Eine neue Partie kann gestartet werden.</p>
                  )}
                  {session.opposition_mode && (
                    <p>Du spielst jetzt als <strong>Opposition</strong>. Nächste Legislaturperiode beginnt.</p>
                  )}
                </>
              )}
            </section>
          )}

          {termSummary && (
            <section className="panel term-summary">
              <h2>
                Amtszeit-Bilanz &mdash; Runden {termSummary.term_start_turn}&ndash;
                {termSummary.term_end_turn}
              </h2>
              <p>
                Zufriedenheit (gewichtet): {termSummary.start_approval.toFixed(1)} &rarr;{" "}
                {termSummary.end_approval.toFixed(1)} (
                {termSummary.end_approval - termSummary.start_approval >= 0 ? "+" : ""}
                {(termSummary.end_approval - termSummary.start_approval).toFixed(1)})
              </p>
              <p>
                Budget: {termSummary.budget_start.toFixed(1)} &rarr;{" "}
                {termSummary.budget_end.toFixed(1)} &nbsp;&middot;&nbsp; Dilemmas:{" "}
                {termSummary.dilemmas_faced} &nbsp;&middot;&nbsp; Ereignisse:{" "}
                {termSummary.events_experienced}
              </p>
              {termSummary.biggest_improvement && (
                <p>
                  Groesster Fortschritt: <strong>{termSummary.biggest_improvement}</strong> (
                  {termSummary.statistic_changes[termSummary.biggest_improvement] > 0 ? "+" : ""}
                  {termSummary.statistic_changes[termSummary.biggest_improvement].toFixed(2)})
                </p>
              )}
              {termSummary.biggest_decline && (
                <p>
                  Groesster Rueckschritt: <strong>{termSummary.biggest_decline}</strong> (
                  {termSummary.statistic_changes[termSummary.biggest_decline] > 0 ? "+" : ""}
                  {termSummary.statistic_changes[termSummary.biggest_decline].toFixed(2)})
                </p>
              )}
              {Object.keys(termSummary.category_changes).length > 0 && (
                <ul className="term-categories">
                  {Object.entries(termSummary.category_changes).map(([cat, val]) => (
                    <li key={cat}>
                      {cat}: {val >= 0 ? "+" : ""}
                      {val.toFixed(2)} fuer die Waehler
                    </li>
                  ))}
                </ul>
              )}
              {/* B9: optionale Legislatur-Ziele, erfuellt/verfehlt (unverbindlich). */}
              {termSummary.goals && termSummary.goals.length > 0 && (
                <>
                  <h3>Legislatur-Ziele</h3>
                  <ul className="term-goals">
                    {termSummary.goals.map((g) => (
                      <li key={g.key} className={g.met ? "goal-met" : "goal-missed"}>
                        {g.met ? "✓" : "✗"} {g.description}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          )}

          {session.election_projection && (
            <section
              className={`panel election-projection ${
                session.election_projection.would_win ? "won" : "lost"
              }`}
            >
              <h2>Wenn heute Wahl waere</h2>
              <p>
                Gewichtete Zufriedenheit:{" "}
                <strong>{session.election_projection.approval.toFixed(1)}</strong> / Schwellenwert{" "}
                {session.election_projection.threshold.toFixed(1)} &mdash;{" "}
                {session.election_projection.would_win ? "Mehrheit" : "keine Mehrheit"}
              </p>
              <p className="hint">
                Mit modellierter Wahlbeteiligung (Apathie):{" "}
                {session.election_projection.turnout_adjusted_approval.toFixed(1)} &mdash; entscheidet
                die Wahl nicht, zeigt aber, wo die Zustimmung wackelt.
              </p>
              <ul className="projection-groups">
                {session.election_projection.groups.map((g) => (
                  <li key={g.name}>
                    <span className="projection-name">{g.name}</span>
                    <span>
                      Zufriedenheit {g.satisfaction.toFixed(0)} <TrendArrow trend={g.trend} />
                    </span>
                    <span className="projection-turnout">
                      Beteiligung {Math.round(g.estimated_turnout * 100)}%
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="grid">
            <div className="panel">
              <h2>Statistiken</h2>
              <ul>
                {Object.entries(session.statistics).map(([key, value]) => (
                  <li key={key}>
                    <span className="stat-label">
                      <StatIcon statKey={key} />
                      {key}
                    </span>
                    <span className="stat-value">
                      <strong>{value.toFixed(1)}</strong>
                      {preview && <DeltaArrow delta={preview.statistic_deltas[key]} />}
                    </span>
                  </li>
                ))}
              </ul>
              {preview && !preview.feasible && (
                <p className="error">Nicht durchfuehrbar: {preview.infeasible_reason}</p>
              )}
            </div>

            <div className="panel">
              <h2>Waehlergruppen</h2>
              <ul>
                {session.voter_groups.map((g) => (
                  <li key={g.name}>
                    <span>{g.name}</span>
                    <span className="stat-value">
                      <strong>{g.satisfaction.toFixed(0)}</strong>
                      {preview && <DeltaArrow delta={preview.satisfaction_delta_by_group[g.name]} />}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {session.factions && session.factions.length > 0 && (
              <div className="panel">
                <h2>Sitzverteilung im Landtag</h2>
                <ul className="faction-list">
                  {session.factions.map((f) => (
                    <li key={f.name}>
                      <span>{f.name}</span>
                      <span className="faction-seats">{f.seats} Sitze</span>
                    </li>
                  ))}
                </ul>
                <p className="hint">
                  Anzeige &mdash; noch ohne Koalitions-/Mehrheitsmechanik.
                </p>
              </div>
            )}

            <div className="panel">
              <h2>Policies fuer naechste Runde</h2>
              <ul className="policy-list">
                {policies.map((p) => {
                  const active = session.active_policy_keys.includes(p.key);
                  const missing = unmetRequirements(p);
                  const missingUnlocks = active ? [] : unmetUnlocks(p);  // B7
                  const locked = !active && (missing.length > 0 || missingUnlocks.length > 0);
                  // Democracy-4-Vorbild "Woher kommen positive Budget-Werte":
                  // eine echte Einnahmen-Policy (income_per_turn) wird sichtbar
                  // ausgewiesen statt als unsichtbarer Pauschal-Zuschuss zu wirken.
                  const incomeHint = p.income_per_turn > 0 ? ` · +${p.income_per_turn} Einnahme/Runde` : "";
                  const dependents = active ? activeDependents(p.key) : [];
                  const repealBlocked = dependents.length > 0;
                  return (
                    <li key={p.key}>
                      {active ? (
                        <label>
                          <input
                            type="checkbox"
                            disabled={gameOver || dilemmaPending || repealBlocked}
                            checked={selectedRepeals.includes(p.key)}
                            onChange={() => toggleRepeal(p.key)}
                          />
                          {p.name} (aktiv{incomeHint}) &mdash; zurueckziehen ({p.capital_cost} Political Capital)
                        </label>
                      ) : (
                        <label>
                          <input
                            type="checkbox"
                            disabled={gameOver || dilemmaPending || locked}
                            checked={selectedPolicies.includes(p.key)}
                            onChange={() => togglePolicy(p.key)}
                          />
                          {p.name} ({p.capital_cost} Political Capital{incomeHint})
                        </label>
                      )}
                      {p.description && (
                        <p className="policy-description">{p.description}</p>
                      )}
                      {locked && missing.length > 0 && (
                        <p className="hint requirement-hint">
                          Braucht zuerst: {missing.map(policyLabel).join(", ")}
                        </p>
                      )}
                      {locked && missingUnlocks.length > 0 && (
                        <p className="hint requirement-hint">
                          Wird verfuegbar, wenn: {missingUnlocks.join(", ")}
                        </p>
                      )}
                      {repealBlocked && (
                        <p className="hint requirement-hint">
                          Kann nicht zurueckgezogen werden, solange aktiv: {dependents.join(", ")}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ul>
              {selectedCapitalCost > session.political_capital && (
                <p className="error">
                  Ausgewaehlt: {selectedCapitalCost} Political Capital, verfuegbar nur{" "}
                  {session.political_capital.toFixed(1)}.
                </p>
              )}
              {preview && preview.would_trigger_events.length > 0 && (
                <p className="hint">
                  Wuerde voraussichtlich ein Ereignis ausloesen: {preview.would_trigger_events[0]}
                </p>
              )}
              {preview && preview.would_trigger_dilemma && (
                <p className="hint">Wuerde voraussichtlich ein Dilemma ausloesen.</p>
              )}
              <div className="button-row">
                <button onClick={handleAdvance} disabled={loading || gameOver || dilemmaPending}>
                  Runde beenden &rarr;
                </button>
                <button
                  onClick={handleFastForward}
                  disabled={loading || gameOver || dilemmaPending}
                  className="secondary"
                >
                  Vorspulen bis naechstes Ereignis &raquo;
                </button>
              </div>
              {gameOver && <p className="hint">Partie beendet &mdash; keine weiteren Runden moeglich.</p>}
            </div>
          </section>

          {events.length > 0 && (
            <section className="panel events">
              <h2>Ereignisse dieser Runde</h2>
              <ul>
                {events.map((text, i) => (
                  <li key={i}>{text}</li>
                ))}
              </ul>
            </section>
          )}

          {reports.length > 0 && (
            <section className="panel reports">
              <h2>Presseschau</h2>
              <ul>
                {reports.map((text, i) => (
                  <li key={i}>{text}</li>
                ))}
              </ul>
            </section>
          )}

          {attributions.length > 0 && (
            <section className="panel attributions">
              <h2>Ursachen der letzten Aenderungen</h2>
              <ul>
                {attributions.map((a, i) => (
                  <li key={i}>
                    {attributionLabel(a.source)}: {a.statistic_key} {a.delta > 0 ? "+" : ""}
                    {a.delta.toFixed(2)}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {history.length > 0 && (
            <section className="panel history">
              <h2>Verlauf</h2>
              <ul className="history-list">
                {history.map((entry, i) => (
                  <li key={i}>
                    {entry.kind === "dilemma" ? (
                      <>
                        <strong>Runde {entry.turn} &mdash; Dilemma aufgeloest:</strong> {entry.optionKey}
                      </>
                    ) : (
                      <>
                        <strong>Runde {entry.turn}</strong>
                        {entry.election && (
                          <> &mdash; Wahl {entry.election.won ? "gewonnen" : "verloren"} (
                          {entry.election.approval.toFixed(1)}/{entry.election.threshold.toFixed(1)})</>
                        )}
                        {entry.dilemmaTriggered && <> &mdash; Dilemma ausgeloest</>}
                      </>
                    )}
                    {entry.events.length > 0 && (
                      <ul className="history-sub">
                        {entry.events.map((text, j) => (
                          <li key={j}>{text}</li>
                        ))}
                      </ul>
                    )}
                    {entry.reports?.length > 0 && (
                      <ul className="history-sub history-reports">
                        {entry.reports.map((text, j) => (
                          <li key={j}>Presseschau: {text}</li>
                        ))}
                      </ul>
                    )}
                    {entry.attributions.length > 0 && (
                      <ul className="history-sub">
                        {entry.attributions.map((a, j) => (
                          <li key={j}>
                            {attributionLabel(a.source)}: {a.statistic_key} {a.delta > 0 ? "+" : ""}
                            {a.delta.toFixed(2)}
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </main>
  );
}
