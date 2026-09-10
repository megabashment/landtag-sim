import { useEffect, useState } from "react";
import { api } from "./api";
import "./App.css";

const FAST_FORWARD_SAFETY_CAP = 40; // Sicherheitsnetz gegen Endlosschleifen im Client

// Nach-P2-Nachschaerfung (Doku-Audit 2026-09-09, siehe mistakes.md/CLAUDE.md
// "Frontend hat keine Verlaufsansicht"): events/attributions/electionResult
// wurden bisher bei JEDEM /advance-Aufruf komplett ueberschrieben -- ein
// Spieler sah nur die letzte Runde, keine Historie. HISTORY_LIMIT begrenzt
// den clientseitigen Verlauf (reines UI-Array, nichts Serverseitiges), damit
// eine lange Partie mit vielen Vorspul-Runden nicht unbegrenzt waechst.
const HISTORY_LIMIT = 60;

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
      const result = await api.advanceTurn(session.session_id, selectedPolicies, selectedRepeals);
      setSession(result.state);
      setEvents(result.events);
      setAttributions(result.attributions);
      setReports(result.reports ?? []);
      setElectionResult(result.election_result);
      setTermSummary(result.term_summary);
      setSelectedPolicies([]);
      setSelectedRepeals([]);
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
        result = await api.advanceTurn(session.session_id, []);
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
      <h1>Landtag-Sim &mdash; Niedersachsen (MVP)</h1>

      {!session && (
        <button onClick={handleStart} disabled={loading}>
          Neue Partie starten
        </button>
      )}

      {error && <p className="error">Fehler: {error}</p>}

      {session && (
        <>
          <section className="status-bar">
            <span>Runde {session.turn}</span>
            <span>Budget: {session.budget.toFixed(1)}</span>
            <span>Political Capital: {session.political_capital.toFixed(1)}</span>
            <span>Naechste Wahl in {session.turns_until_election} Runden</span>
            <span>Status: {session.status}</span>
            {/* B8: Rolle der Spielerpartei (im MVP immer "Regierung"). */}
            <span>Rolle: {session.role === "opposition" ? "Opposition" : "Regierung"}</span>
          </section>

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
                <p>Die Partie ist beendet. Eine neue Partie kann gestartet werden.</p>
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
                    <span>{key}</span>
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
