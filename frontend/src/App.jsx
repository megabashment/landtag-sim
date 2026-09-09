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

export default function App() {
  const [session, setSession] = useState(null);
  // Dynamischer Policy-Katalog (GET /policies) statt der frueheren hart
  // codierten AVAILABLE_POLICIES-Konstante -- ersetzt eine in README.md/
  // CLAUDE.md dokumentierte "Bekannte Vereinfachung". Wird einmalig beim
  // Laden der App geholt (Katalog ist global, nicht pro Session).
  const [policies, setPolicies] = useState([]);
  const [selectedPolicies, setSelectedPolicies] = useState([]);
  const [events, setEvents] = useState([]);
  const [attributions, setAttributions] = useState([]);
  const [electionResult, setElectionResult] = useState(null);
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
      .previewTurn(session.session_id, selectedPolicies)
      .then((result) => {
        if (!cancelled) setPreview(result);
      })
      .catch(() => {
        if (!cancelled) setPreview(null);
      });
    return () => {
      cancelled = true;
    };
  }, [session, selectedPolicies, dilemmaPending]);

  async function handleStart() {
    setError(null);
    setLoading(true);
    try {
      const created = await api.createSession();
      const state = await api.getSession(created.session_id);
      setSession(state);
      setEvents([]);
      setAttributions([]);
      setElectionResult(null);
      setSelectedPolicies([]);
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
      const result = await api.advanceTurn(session.session_id, selectedPolicies);
      setSession(result.state);
      setEvents(result.events);
      setAttributions(result.attributions);
      setElectionResult(result.election_result);
      setSelectedPolicies([]);
      pushHistoryEntry({
        kind: "advance",
        turn: result.state.turn,
        events: result.events,
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
          attributions: result.attributions,
          election: result.election_result,
          dilemmaTriggered: result.pending_dilemma !== null,
        });
        const shouldStop =
          result.events.length > 0 ||
          result.election_result !== null ||
          result.pending_dilemma !== null ||
          result.state.status !== "active";
        if (shouldStop) break;
      }
      setSession(result.state);
      setEvents(result.events);
      setAttributions(result.attributions);
      setElectionResult(result.election_result);
      setSelectedPolicies([]);
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
      setElectionResult(null);
      pushHistoryEntry({
        kind: "dilemma",
        turn: result.state.turn,
        optionKey,
        events: [],
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

  function unmetRequirements(policy) {
    if (!session) return policy.requires;
    return policy.requires.filter(
      (req) => !session.active_policy_keys.includes(req) && !selectedPolicies.includes(req)
    );
  }

  const selectedCapitalCost = selectedPolicies.reduce((sum, key) => {
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

            <div className="panel">
              <h2>Policies fuer naechste Runde</h2>
              <ul className="policy-list">
                {policies.map((p) => {
                  const active = session.active_policy_keys.includes(p.key);
                  const missing = unmetRequirements(p);
                  const locked = !active && missing.length > 0;
                  return (
                    <li key={p.key}>
                      <label>
                        <input
                          type="checkbox"
                          disabled={active || gameOver || dilemmaPending || locked}
                          checked={selectedPolicies.includes(p.key)}
                          onChange={() => togglePolicy(p.key)}
                        />
                        {p.name} {active ? "(bereits aktiv)" : `(${p.capital_cost} Political Capital)`}
                      </label>
                      {locked && (
                        <p className="hint requirement-hint">
                          Braucht zuerst: {missing.map(policyLabel).join(", ")}
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
