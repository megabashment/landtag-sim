import { useEffect, useState } from "react";
import { api } from "./api";
import { STAT_ICON_PATHS } from "./statIcons";
import { PARTY_ICONS } from "./partyIcons";
import { PLACEHOLDER_SILHOUETTES, bundeslandKeyFromName, bundeslandMapSrc } from "./bundeslandData";
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

// Nutzer-Feedback (2026-09-13): echte Vektor-Lagekarten (Wikimedia Commons,
// TUBS, CC BY-SA 3.0 -- siehe CREDITS.md/bundeslandData.js) statt der
// vorherigen Platzhalter-Silhouetten. Als <img> auf die statische Datei
// (frontend/public/maps/<key>.svg) statt Inline-SVG -- die Dateien sind
// mit ~680 KB deutlich zu gross fuers JS-Bundle, als Standalone-Datei
// werden sie einmal vom Browser geladen und gecacht. Faellt fuer ein
// Bundesland ohne echte Karte (noch) auf die Platzhalter-Silhouette zurueck.
function BundeslandBadge({ bundeslandKey, size = 40 }) {
  const mapSrc = bundeslandMapSrc(bundeslandKey);
  if (mapSrc) {
    return (
      <img
        className="bundesland-badge"
        src={mapSrc}
        alt=""
        style={{ width: size, height: size }}
      />
    );
  }

  const shape = PLACEHOLDER_SILHOUETTES[bundeslandKey];
  if (!shape) return null;
  return (
    <svg
      className="bundesland-badge"
      width={size}
      height={size}
      viewBox={shape.viewBox}
      aria-hidden="true"
    >
      <path fill="currentColor" d={shape.path} />
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

// M5 "Opposition-Loop" (BACKLOG.md B15 Phase 4): Sonntagsfrage-Overlay
// im Stil deutscher Umfragen. Zeigt Regierung vs. Opposition mit
// Koalitionsfähigkeit-Schwelle (30%).
// B23 "Party-Gründung (Persistente Meta-Ebene)" Phase 2: Game-Start-Menu
// mit Option "Neue Partei gründen" vs. "Existierende laden"
function ScenarioSelectionDialog({ scenarios, onSelect, onClose, disabled }) {
  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2>Szenario wählen</h2>
        <div className="scenarios-list">
          {scenarios.map((s) => (
            <div key={s.key} className="scenario-card">
              <h3>{s.name}</h3>
              <p>{s.description}</p>
              <button onClick={() => onSelect(s.key)} disabled={disabled} className="button-primary">
                Dieses Szenario spielen
              </button>
            </div>
          ))}
        </div>
        <button onClick={onClose} disabled={disabled} className="button-secondary">
          Abbrechen
        </button>
      </div>
    </div>
  );
}

// UX-Onboarding-Redesign (2026-09-13, Nutzer-Feedback: "Bundeskarte -> Partei
// -> los"): der Ersteinstieg ist jetzt ein gefuehrter 2-Schritt-Assistent
// statt eines 4-Buttons-Menus mit vier gleichrangigen, unabhaengigen Pfaden.
// Schritt 1 waehlt das Bundesland (ersetzt die vorherige eigenstaendige
// BundeslandSelectionDialog), Schritt 2 gruendet dafuer die Partei (ersetzt
// PartyCreationDialog) -- danach startet die Partie direkt. Szenario-Modus/
// Klassische Partie/bestehende Partei bleiben als bewusst kleiner gehaltene
// Zweitoptionen erreichbar (siehe .wizard-secondary unten), nicht mehr
// gleichrangig neben dem Hauptpfad.
function NewGameWizard({
  bundeslaender,
  onCreateParty, // (name, ideology, bundeslandKey) => void
  onShowScenarios,
  onStartClassic,
  onContinueParty,
  existingParties,
  disabled,
  error,
}) {
  const [step, setStep] = useState("bundesland"); // "bundesland" | "party"
  const [selectedBundesland, setSelectedBundesland] = useState(null);
  const [name, setName] = useState("");
  const [ideology, setIdeology] = useState("green");

  const statLabel = {
    unemployment_rate: "Arbeitslosigkeit",
    gdp_growth: "BIP-Wachstum",
    education_spending: "Bildungsausgaben",
    healthcare_quality: "Gesundheitsversorgung",
    co2_emissions: "CO2-Emissionen",
    renewable_share: "Erneuerbare",
  };
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
  const ideologyEmoji = { green: "🟢", red: "🔴", blue: "🔵" };

  return (
    <div className="modal-content wizard-card">
      <span className="masthead__kicker">Landtag-Simulation &middot; MVP</span>

      {step === "bundesland" && (
        <>
          <h2>Schritt 1 von 2 &middot; Bundesland wählen</h2>
          <div className="scenarios-list">
            {bundeslaender.map((b) => (
              <div key={b.key} className="scenario-card bundesland-card">
                <div className="bundesland-card-header">
                  <BundeslandBadge bundeslandKey={b.key} size={48} />
                  <h3>{b.name}</h3>
                </div>
                <p>{b.description}</p>
                <ul className="campaign-effects">
                  {Object.entries(b.starting_statistics).map(([key, value]) => (
                    <li key={key}>
                      {statLabel[key] ?? key}: {value.toFixed(1)}
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() => {
                    setSelectedBundesland(b);
                    setStep("party");
                  }}
                  disabled={disabled}
                  className="button-primary"
                >
                  {b.name} wählen
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {step === "party" && selectedBundesland && (
        <>
          <h2>Schritt 2 von 2 &middot; Partei gründen</h2>
          <p className="wizard-context">
            Bundesland: <strong>{selectedBundesland.name}</strong>{" "}
            <button className="link-button" onClick={() => setStep("bundesland")} disabled={disabled}>
              ändern
            </button>
          </p>
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
            <button
              onClick={() => onCreateParty(name, ideology, selectedBundesland.key)}
              disabled={disabled || !name.trim()}
            >
              Partei gründen &amp; loslegen
            </button>
            <button onClick={() => setStep("bundesland")} disabled={disabled} className="button-secondary">
              Zurück
            </button>
          </div>
        </>
      )}

      <div className="wizard-secondary">
        <p className="wizard-secondary__label">Oder:</p>
        <button className="link-button" onClick={onShowScenarios} disabled={disabled}>
          🎯 Szenario spielen
        </button>
        <button className="link-button" onClick={onStartClassic} disabled={disabled}>
          ▶ Klassische Partie (Niedersachsen, ohne Partei)
        </button>

        {existingParties.length > 0 && (
          <div className="existing-parties">
            <h3>Weiter mit einer bestehenden Partei</h3>
            <ul className="existing-parties-list">
              {existingParties.map((p) => (
                <li key={p.id} className="existing-party-row">
                  <span className="existing-party-info">
                    {ideologyEmoji[p.ideology] ?? ""} <strong>{p.name}</strong>
                    <span className="existing-party-meta">
                      {" "}Ruf {p.reputation.toFixed(0)} &middot; {p.terms_won}/{p.terms_played} Legislaturen gewonnen
                    </span>
                  </span>
                  <button className="button-secondary" onClick={() => onContinueParty(p.id)} disabled={disabled}>
                    Weiter
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

// M6 Phase 2 "Advanced Opposition": Koalitions-Dialog nach Wahlverlust
// Spieler kann Koalition mit Opposition akzeptieren um in Regierung zu bleiben
// B28 "Advanced UI" (M7_SPRINT_PLAN.md): Party-Detail-Modal mit Ruf-Verlauf
// (einfacher Balken-Graph, kein Chart-Package noetig) und Term-Tabelle.
// Holt die Daten selbst nach (GET /parties/{id}/detail), damit der Aufrufer
// nur die partyId durchreichen muss.
function PartyDetailModal({ partyId, onClose }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getPartyDetail(partyId)
      .then((result) => {
        if (!cancelled) setDetail(result);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [partyId]);

  const ideologyEmoji = { green: "🟢", red: "🔴", blue: "🔵" };

  return (
    <div className="modal-overlay">
      <div className="modal-content party-detail-modal">
        <h2>Partei-Historie{detail ? `: ${detail.name}` : ""}</h2>
        {error && <p className="error">Fehler: {error}</p>}
        {!detail && !error && <p>Lade…</p>}
        {detail && (
          <>
            <p>
              {ideologyEmoji[detail.ideology] ?? ""} {detail.ideology} &middot; Aktueller Ruf:{" "}
              <strong>{detail.reputation.toFixed(0)}</strong>
            </p>
            {detail.terms.length === 0 ? (
              <p className="hint">Noch keine abgeschlossene Legislaturperiode.</p>
            ) : (
              <>
                <div className="party-history-graph" aria-label="Ruf über Zeit">
                  {detail.terms.map((t, i) => (
                    <div
                      key={i}
                      className="party-history-bar-container"
                      title={`Legislatur ${i + 1} (Runde ${t.turn}): Ruf ${t.reputation_after}`}
                    >
                      <div
                        className={`party-history-bar ${t.won ? "won" : "lost"}`}
                        style={{ height: `${Math.max(2, t.reputation_after)}%` }}
                      />
                      <span className="party-history-bar-label">{i + 1}</span>
                    </div>
                  ))}
                </div>
                <table className="party-history-table">
                  <thead>
                    <tr>
                      <th>Legislatur</th>
                      <th>Ergebnis</th>
                      <th>Zustimmung</th>
                      <th>Ruf-Δ</th>
                      <th>Ruf danach</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.terms.map((t, i) => (
                      <tr key={i}>
                        <td>{i + 1}</td>
                        <td>{t.won ? "✅ Gewonnen" : "❌ Verloren"}</td>
                        <td>{t.approval.toFixed(1)}%</td>
                        <td>
                          {t.reputation_delta > 0 ? "+" : ""}
                          {t.reputation_delta.toFixed(1)}
                        </td>
                        <td>{t.reputation_after.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </>
        )}
        <button onClick={onClose} className="button-secondary">
          Schließen
        </button>
      </div>
    </div>
  );
}

// "Demokratie-Drama"-Pass (Nutzer-Feedback 2026-09-13: "das Spiel ist
// langweilig, der Punkt einer Demokratie-Sim kommt schwer rueber"): Events/
// Presseschau/Oppositions-Zitat waren bisher schlichte <li>-Listen -- eine
// Zeitungsseiten-Praesentation macht dieselben Daten spuerbar, ohne die
// Sim-Logik anzufassen (reines Anzeige-Layout). Nur EIN Element pro Runde
// je Kategorie (Event max. 1, Report max. 1, Oppositions-Zitat max. 1 --
// alles bereits serverseitig so begrenzt), daher passt eine Titelseite
// mit Aufmacher + Meldung + Zitat gut, ohne ueberladen zu wirken.
function FrontPage({ events, reports, oppositionReaction }) {
  if (events.length === 0 && reports.length === 0 && !oppositionReaction) return null;
  return (
    <section className="panel front-page">
      <span className="front-page__masthead">Aktuelle Ausgabe &middot; Runde im Rueckblick</span>
      {events.map((text, i) => (
        <div key={`event-${i}`} className="front-page__story front-page__story--lead">
          <span className="front-page__kicker">Eilmeldung</span>
          <h2 className="front-page__headline">{text}</h2>
        </div>
      ))}
      {reports.map((text, i) => (
        <div key={`report-${i}`} className="front-page__story">
          <span className="front-page__kicker">Presseschau</span>
          <h3 className="front-page__headline front-page__headline--secondary">{text}</h3>
        </div>
      ))}
      {oppositionReaction && (
        <div className="front-page__quote-block">
          <span className="front-page__kicker">Stimme der Opposition</span>
          <blockquote className="front-page__quote">{oppositionReaction}</blockquote>
        </div>
      )}
    </section>
  );
}

function CoalitionDialog({ electionResult, onAccept, onDecline, disabled }) {
  if (!electionResult || electionResult.won || electionResult.coalition_viability < 30) {
    return null; // Nicht anzeigen wenn kein Verlust oder koalition nicht möglich
  }

  const viability = electionResult.coalition_viability.toFixed(1);
  const coalitionPossible = electionResult.coalition_viability >= 30;

  return (
    <div className="modal-overlay">
      <div className="modal-content coalition-dialog">
        <h2>🤝 Koalitionsangebot</h2>
        <p>
          Du hast die Wahl verloren. Die Opposition ist bereit zur Zusammenarbeit!
        </p>
        <div className="coalition-info">
          <div className="coalition-stat">
            <span className="label">Koalitionsviabilität:</span>
            <span className="value">{viability}%</span>
          </div>
          <div className="coalition-stat">
            <span className="label">Zustand:</span>
            <span className={`status ${coalitionPossible ? "possible" : "impossible"}`}>
              {coalitionPossible ? "✓ Möglich" : "✗ Nicht möglich"}
            </span>
          </div>
        </div>

        <p className="coalition-text">
          {coalitionPossible
            ? "Die Opposition ist stark genug, um eine stabile Koalition zu bilden. Mit ihrer Unterstützung kannst du die Regierung fortsetzen."
            : "Die Opposition ist zu schwach. Eine Koalition ist nicht tragfähig."}
        </p>

        <div className="button-row">
          <button
            className="button-primary"
            onClick={onAccept}
            disabled={disabled || !coalitionPossible}
          >
            💪 Koalition akzeptieren
          </button>
          <button className="button-secondary" onClick={onDecline} disabled={disabled}>
            ➡️ In Opposition gehen
          </button>
        </div>
      </div>
    </div>
  );
}

// Mehrparteiensystem (Medium-Scope): Naeherung der aktuellen Zustimmung aus
// den Waehlergruppen (nach population_share gewichtet) -- keine exakte
// Kopie der Ideologie-/Ruf-Modifikatoren der Sim-Engine, nur fuer die
// laufende Sonntagsfrage-Anzeige zwischen den Wahlen gedacht.
function estimatePlayerApproval(voterGroups) {
  if (!voterGroups || voterGroups.length === 0) return 50;
  const totalShare = voterGroups.reduce((sum, g) => sum + g.population_share, 0) || 1;
  const weighted = voterGroups.reduce((sum, g) => sum + g.satisfaction * g.population_share, 0);
  return weighted / totalShare;
}

const RIVAL_IDEOLOGY_COLOR = { green: "#2e7d32", red: "#c62828", blue: "#1565c0" };

function MultiPartySonntagsfrage({ session }) {
  const rivals = session.rival_parties ?? [];
  const playerRaw = Math.max(0, estimatePlayerApproval(session.voter_groups));
  const rivalRaw = rivals.map((r) => ({ ...r, raw: Math.max(0, r.approval) }));
  const total = playerRaw + rivalRaw.reduce((s, r) => s + r.raw, 0) || 1;

  const standings = [
    { name: "Deine Partei", pct: (playerRaw / total) * 100, isPlayer: true },
    ...rivalRaw.map((r) => ({ name: r.name, pct: (r.raw / total) * 100, ideology: r.ideology })),
  ].sort((a, b) => b.pct - a.pct);

  const leading = standings[0];

  return (
    <div className="sonntagsfrage-overlay">
      <h2 className="sonntagsfrage-title">Sonntagsfrage</h2>
      <div className="sonntagsfrage-bars multi-party-bars">
        {standings.map((s) => (
          <div className="bar-container" key={s.name}>
            <div
              className={`bar multi-party-bar ${s.isPlayer ? "player-bar" : ""}`}
              style={{
                width: `${Math.max(2, s.pct)}%`,
                background: s.isPlayer ? undefined : RIVAL_IDEOLOGY_COLOR[s.ideology],
              }}
            >
              <span className="bar-label">{s.name}</span>
            </div>
            <span className="bar-percent">{s.pct.toFixed(1)}%</span>
          </div>
        ))}
      </div>
      <p className="hint">
        {leading.isPlayer
          ? "Deine Partei liegt aktuell vorn."
          : `${leading.name} liegt aktuell vorn -- bei der Wahl zaehlt der hoechste Stimmenanteil.`}
      </p>
    </div>
  );
}

function SonntagsfragOverlay({ session }) {
  if (!session) return null;

  // Mehrparteiensystem: eigene Ansicht, sobald Rivalen-Parteien existieren
  // (nur Party-Sessions, siehe backend/app/api/routes_game.py::seed_rival_parties).
  if (session.rival_parties && session.rival_parties.length > 0) {
    return <MultiPartySonntagsfrage session={session} />;
  }

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
function StatusBar({ session, events, onShowPartyDetail }) {
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
        {/* B28 "Advanced UI" (M7_SPRINT_PLAN.md): Partei-Ruf + Detail-Button,
            nur sichtbar in Party-Sessions (session.party_id gesetzt). */}
        {session.party_id && (
          <div className="field field--party">
            <span className="field__label">Partei</span>
            <span className="field__value">
              {session.party_name} &middot; Ruf {session.party_reputation?.toFixed(0)}
              <button className="party-detail-btn" onClick={onShowPartyDetail} type="button">
                Details
              </button>
            </span>
          </div>
        )}
      </div>

      {/* B28: Session-Dauer-Info -- wie viele Legislaturperioden diese
          Session schon durchlaufen hat (session.turn laeuft ueber mehrere
          Wahl-Zyklen weiter, waehrend turns_until_election pro Zyklus
          zurueckgesetzt wird, siehe engine.py::advance_turn). */}
      <p className="term-session-info hint">
        Legislatur {Math.floor(session.turn / ELECTION_CYCLE) + 1}
        {session.status === "active" ? ` (Runde ${elapsed + 1} von ${ELECTION_CYCLE})` : ""}
      </p>

      {/* B26 "Opposition-Kampagnen UI Verbesserung" (M7_SPRINT_PLAN.md):
          sichtbarer Hinweis, dass gerade Opposition statt Regierung gespielt
          wird -- vorher war das nur indirekt aus dem Mandat-Feld ablesbar. */}
      {session.opposition_mode && (
        <div className="opposition-mode-banner">
          Du bist in Opposition &mdash; wähle eine Kampagne statt Policies.
        </div>
      )}

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

// B26 "Opposition-Kampagnen UI Verbesserung" (M7_SPRINT_PLAN.md): Kampagnen-
// Katalog fuer den Opposition-Modus, analog zum Policy-Katalog. Nur EINE
// Kampagne pro Runde waehlbar (siehe `opposition_campaign_key` in
// AdvanceTurnRequest) -- deshalb Radio-artige Single-Select-Karten statt
// Checkboxen wie beim Policy-Katalog.
function OppositionCampaignPanel({ campaigns, selectedCampaign, onSelect, disabled, politicalCapital }) {
  if (campaigns.length === 0) {
    return (
      <div className="panel">
        <h2>Opposition-Kampagnen</h2>
        <p className="hint">Kampagnen-Katalog konnte nicht geladen werden.</p>
      </div>
    );
  }

  return (
    <div className="panel">
      <h2>Opposition-Kampagnen fuer naechste Runde</h2>
      <div className="policy-cards">
        {campaigns.map((c) => {
          const selected = selectedCampaign === c.key;
          const affordable = politicalCapital >= c.capital_cost;
          return (
            <div
              key={c.key}
              className={`policy-card campaign-card ${selected ? "active" : ""} ${!affordable ? "locked" : ""}`}
            >
              <div className="card-header">
                <label className="card-checkbox">
                  <input
                    type="radio"
                    name="opposition-campaign"
                    disabled={disabled || (!affordable && !selected)}
                    checked={selected}
                    onChange={() => onSelect(selected ? null : c.key)}
                  />
                </label>
                <div className="card-title-section">
                  <h4>{c.name}</h4>
                  <div className="card-badges">
                    <span className="badge cost-badge">🔵 {c.capital_cost} PC</span>
                  </div>
                </div>
              </div>
              <div className="card-details">
                {c.description && <p className="policy-description">{c.description}</p>}
                <ul className="campaign-effects">
                  {Object.entries(c.satisfaction_deltas).map(([group, delta]) => (
                    <li key={group}>
                      {group}: <DeltaArrow delta={delta} />
                    </li>
                  ))}
                </ul>
                {!affordable && !selected && (
                  <p className="hint requirement-hint">
                    ⚠️ Braucht {c.capital_cost} PC, verfuegbar nur {politicalCapital.toFixed(1)}.
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
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
  // Democracy-4-Vorbild "Policy-Repeal" (siehe CLAUDE.md/landtag_sim.
  // engine.py::advance_turn): Policy-Keys, die diese Runde zurueckgezogen
  // werden sollen. Getrennt von selectedPolicies, weil ein Key nie
  // gleichzeitig neu eingefuehrt UND zurueckgezogen werden kann.
  const [selectedRepeals, setSelectedRepeals] = useState([]);
  // B26 "Opposition-Kampagnen UI Verbesserung" (M7): echter Katalog aus
  // GET /opposition-campaigns statt der frueheren unbenutzten Konstante.
  const [oppositionCampaigns, setOppositionCampaigns] = useState([]);
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [showOppositionChoice, setShowOppositionChoice] = useState(false);
  const [events, setEvents] = useState([]);
  const [attributions, setAttributions] = useState([]);
  // B4 "Narrative Konsequenz-Ebene" (BACKLOG.md): rein textliche
  // Presseschau-Meldungen (kein Sim-Effekt), hoechstens eine pro Runde und
  // nur in Runden ohne Ereignis/Dilemma.
  const [reports, setReports] = useState([]);
  // "Demokratie-Drama"-Pass (Nutzer-Feedback 2026-09-13): Oppositions-Zitat
  // eines Rivalen-Fraktionsvorsitzenden, hoechstens eines pro Runde (siehe
  // opposition_voices.py). null ohne Rivalen oder in ruhigen Runden.
  const [oppositionReaction, setOppositionReaction] = useState(null);
  const [electionResult, setElectionResult] = useState(null);
  // M6 Phase 2 "Advanced Opposition": flag zur Kontrolle der Koalitions-Dialog-Anzeige
  const [showCoalitionDialog, setShowCoalitionDialog] = useState(false);
  // B28 "Advanced UI" (M7): Party-Detail-Modal (Ruf-Verlauf + Term-Liste)
  const [showPartyDetail, setShowPartyDetail] = useState(false);
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
  // B23 "Party-Gründung (Persistente Meta-Ebene)": UI-State für den Ersteinstieg.
  // UX-Onboarding-Redesign (2026-09-13): Partei-Formular-State lebt jetzt IM
  // NewGameWizard (nicht mehr hier) -- App.jsx muss nur noch wissen, ob
  // ueberhaupt der Ersteinstieg gezeigt wird.
  const [showGameStart, setShowGameStart] = useState(true);
  // B20 "Party-Legacy": bestehende Parteien fuer "Weiter mit Partei X" im Startmenue
  const [existingParties, setExistingParties] = useState([]);
  // B24 "Scenario Mode": vordefinierte Spielmodi mit Preset-Bedingungen
  const [scenarios, setScenarios] = useState([]);
  const [showScenarioSelection, setShowScenarioSelection] = useState(false);
  // B27 "Bundes-Skalierung" (M7): spielbare Bundeslaender mit eigener Baseline
  const [bundeslaender, setBundeslaender] = useState([]);
  // Policy-Erweiterungsstate: speichert, welche Policies expandiert sind (Key -> true/false)
  const [expandedPolicies, setExpandedPolicies] = useState({});

  function pushHistoryEntry(entry) {
    setHistory((prev) => [entry, ...prev].slice(0, HISTORY_LIMIT));
  }

  function togglePolicyExpanded(policyKey) {
    setExpandedPolicies((prev) => ({ ...prev, [policyKey]: !prev[policyKey] }));
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

  // B20 "Party-Legacy": bestehende Parteien fuer das Startmenue holen, solange
  // keine Session laeuft -- Grundlage fuer "Weiter mit Partei X".
  useEffect(() => {
    if (session) return;
    let cancelled = false;
    api
      .listParties()
      .then((result) => {
        if (!cancelled) setExistingParties(result);
      })
      .catch(() => {
        if (!cancelled) setExistingParties([]);
      });
    return () => {
      cancelled = true;
    };
  }, [session]);

  // B24 "Scenario Mode": vordefinierte Spielmodi beim Start laden
  useEffect(() => {
    if (session) return;
    let cancelled = false;
    api
      .listScenarios()
      .then((result) => {
        if (!cancelled) setScenarios(result);
      })
      .catch(() => {
        if (!cancelled) setScenarios([]);
      });
    return () => {
      cancelled = true;
    };
  }, [session]);

  // B27 "Bundes-Skalierung": spielbare Bundeslaender beim Start laden
  useEffect(() => {
    if (session) return;
    let cancelled = false;
    api
      .listBundeslaender()
      .then((result) => {
        if (!cancelled) setBundeslaender(result);
      })
      .catch(() => {
        if (!cancelled) setBundeslaender([]);
      });
    return () => {
      cancelled = true;
    };
  }, [session]);

  // B26 "Opposition-Kampagnen UI Verbesserung": Kampagnen-Katalog einmalig
  // beim Laden holen -- global wie der Policy-Katalog, nicht pro Session.
  useEffect(() => {
    let cancelled = false;
    api
      .listOppositionCampaigns()
      .then((result) => {
        if (!cancelled) setOppositionCampaigns(result);
      })
      .catch(() => {
        if (!cancelled) setOppositionCampaigns([]);
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
      setOppositionReaction(null);
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

  // UX-Onboarding-Redesign (2026-09-13): nimmt Name/Ideologie/Bundesland
  // jetzt als Argumente statt aus App-State zu lesen -- der NewGameWizard
  // haelt seinen Formular-State selbst (analog zu den anderen
  // handleStart*-Funktionen, die auch direkt einen Parameter bekommen).
  async function handleCreateParty(name, ideology, bundeslandKey) {
    if (!name.trim()) {
      setError("Parteiname erforderlich");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const created = await api.createPartySession(name, ideology, bundeslandKey);
      const state = await api.getSession(created.session_id);
      setSession(state);
      setShowGameStart(false);
      setEvents([]);
      setAttributions([]);
      setReports([]);
      setOppositionReaction(null);
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

  // B20 "Party-Legacy": neue Legislaturperiode fuer eine bestehende Partei
  // starten -- ihr aufgebauter Ruf (Party.reputation) wirkt ab Runde 0.
  async function handleContinueParty(partyId) {
    setError(null);
    setLoading(true);
    try {
      const created = await api.createSessionFromParty(partyId);
      const state = await api.getSession(created.session_id);
      setSession(state);
      setShowGameStart(false);
      setEvents([]);
      setAttributions([]);
      setReports([]);
      setOppositionReaction(null);
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

  // B24 "Scenario Mode": neue Session mit vordefinierten Scenario starten
  async function handleStartScenario(scenarioId) {
    setError(null);
    setLoading(true);
    try {
      const created = await api.createSessionFromScenario(scenarioId);
      const state = await api.getSession(created.session_id);
      setSession(state);
      setShowGameStart(false);
      setShowScenarioSelection(false);
      setEvents([]);
      setAttributions([]);
      setReports([]);
      setOppositionReaction(null);
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
      setOppositionReaction(result.opposition_reaction ?? null);
      setElectionResult(result.election_result);
      setTermSummary(result.term_summary);
      setSelectedPolicies([]);
      setSelectedRepeals([]);
      setSelectedCampaign(null);

      // M6 Phase 2 "Advanced Opposition": Coalition-Dialog bei Wahlverlust
      // wenn coalition_viability >= 30
      if (
        result.election_result &&
        !result.election_result.won &&
        !result.state.opposition_mode &&
        result.election_result.coalition_viability >= 30
      ) {
        setShowCoalitionDialog(true);
      } else if (result.election_result && !result.election_result.won && !result.state.opposition_mode) {
        // Fallback: Wahlverlust ohne Koalition-Option
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
      setOppositionReaction(result.opposition_reaction ?? null);
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

  // M6 Phase 2 "Advanced Opposition": Koalitionsangebot Handling
  async function handleAcceptCoalition() {
    if (!session) return;
    setError(null);
    setLoading(true);
    try {
      const result = await api.respondToElection(session.session_id, { accept_coalition: true });
      setSession({ ...session, role: result.role });
      setShowCoalitionDialog(false);
      setError(result.message);
    } catch (e) {
      setError(`Koalition fehlgeschlagen: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleDeclineCoalition() {
    if (!session) return;
    setError(null);
    setLoading(true);
    try {
      const result = await api.respondToElection(session.session_id, { accept_coalition: false });
      setSession({ ...session, role: result.role });
      setShowCoalitionDialog(false);
      setError(result.message);
    } catch (e) {
      setError(`Opposition-Wechsel fehlgeschlagen: ${e.message}`);
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
      setOppositionReaction(null);
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
        {/* B27 "Bundes-Skalierung" (M7): Bugfix -- admin_unit_name kommt jetzt
            aus der Session statt hart codiert "Niedersachsen" zu sein, sonst
            zeigt der Header bei Bayern-/NRW-Partien den falschen Namen.
            Game-Director-Review (2026-09-12): Bundesland-Badge fuer eine
            minimale raeumliche Verortung neben dem reinen Textnamen. */}
        <div className="masthead__title-row">
          <BundeslandBadge bundeslandKey={bundeslandKeyFromName(session?.admin_unit_name)} size={44} />
          <h1>{session?.admin_unit_name ?? "Niedersachsen"}</h1>
        </div>
      </header>

      {!session && showGameStart && (
        <>
          {/* UX-Onboarding-Redesign (2026-09-13): gefuehrter Assistent
              Bundesland -> Partei -> Start statt vier gleichrangiger
              Menu-Buttons, siehe NewGameWizard. Weiterhin im .modal-overlay-
              Muster (Backdrop) wie alle anderen Dialoge. */}
          <div className="modal-overlay">
            <NewGameWizard
              bundeslaender={bundeslaender}
              onCreateParty={handleCreateParty}
              onShowScenarios={() => setShowScenarioSelection(true)}
              onStartClassic={handleStart}
              onContinueParty={handleContinueParty}
              existingParties={existingParties}
              disabled={loading}
              error={error}
            />
          </div>
          {showScenarioSelection && (
            <ScenarioSelectionDialog
              scenarios={scenarios}
              onSelect={handleStartScenario}
              onClose={() => setShowScenarioSelection(false)}
              disabled={loading}
            />
          )}
          {/* M6 Phase 2 "Advanced Opposition": Koalitions-Dialog */}
          {showCoalitionDialog && (
            <CoalitionDialog
              electionResult={electionResult}
              onAccept={handleAcceptCoalition}
              onDecline={handleDeclineCoalition}
              disabled={loading}
            />
          )}
        </>
      )}

      {error && <p className="error">Fehler: {error}</p>}

      {session && (
        <>
          <StatusBar session={session} events={events} onShowPartyDetail={() => setShowPartyDetail(true)} />
          {/* B28 "Advanced UI" (M7_SPRINT_PLAN.md): Party-Detail-Modal mit
              Ruf-Verlauf + Term-Liste, nur wenn die Session eine Partei hat. */}
          {showPartyDetail && session.party_id && (
            <PartyDetailModal partyId={session.party_id} onClose={() => setShowPartyDetail(false)} />
          )}
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
              {electionResult.standings && electionResult.standings.length > 0 && (
                <ol className="election-standings">
                  {electionResult.standings.map(([name, pct], idx) => (
                    <li
                      key={name}
                      className={name === "Deine Partei" ? "standings-player" : ""}
                    >
                      <span className="standings-rank">{idx + 1}.</span>
                      <span className="standings-name">{name}</span>
                      <span className="standings-pct">{pct.toFixed(1)}%</span>
                    </li>
                  ))}
                </ol>
              )}
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

            {/* B26 "Opposition-Kampagnen UI Verbesserung" (M7_SPRINT_PLAN.md):
                im Opposition-Modus wird der Policy-Katalog durch den
                Kampagnen-Katalog ersetzt -- Policies enacten geht in der
                Opposition sowieso nicht (advance_session_turn ignoriert
                enact_policy_keys, siehe routes_game.py). */}
            {session.opposition_mode && (
              <OppositionCampaignPanel
                campaigns={oppositionCampaigns}
                selectedCampaign={selectedCampaign}
                onSelect={setSelectedCampaign}
                disabled={gameOver || dilemmaPending}
                politicalCapital={session.political_capital}
              />
            )}

            <div className="panel">
              <h2>{session.opposition_mode ? "Naechste Runde" : "Policies fuer naechste Runde"}</h2>
              {!session.opposition_mode && (
              <div className="policies-grid">
                {["economy", "social", "environment"].map((category) => (
                  <div key={category} className="policy-category">
                    <h3 className="category-title">
                      {category === "economy" && "💼 Wirtschaft"}
                      {category === "social" && "👥 Soziales"}
                      {category === "environment" && "🌍 Umwelt"}
                    </h3>
                    <div className="policy-cards">
                      {policies
                        .filter((p) => p.category === category)
                        .map((p) => {
                          const active = session.active_policy_keys.includes(p.key);
                          const missing = unmetRequirements(p);
                          const missingUnlocks = active ? [] : unmetUnlocks(p);
                          const locked = !active && (missing.length > 0 || missingUnlocks.length > 0);
                          const incomeHint = p.income_per_turn > 0 ? `+${p.income_per_turn}` : "";
                          const dependents = active ? activeDependents(p.key) : [];
                          const repealBlocked = dependents.length > 0;
                          const expanded = expandedPolicies[p.key] || false;

                          // B23 Phase 3: Party-Ideologie gibt Bonus in der Kategorie
                          const partyIdeologyBonus =
                            (session.party_ideology === "green" && category === "environment") ||
                            (session.party_ideology === "red" && category === "social") ||
                            (session.party_ideology === "blue" && category === "economy");

                          return (
                            <div
                              key={p.key}
                              className={`policy-card ${active ? "active" : ""} ${locked ? "locked" : ""} ${partyIdeologyBonus ? "bonus" : ""}`}
                            >
                              <div className="card-header">
                                <label className="card-checkbox">
                                  <input
                                    type="checkbox"
                                    disabled={gameOver || dilemmaPending || (active ? repealBlocked : locked)}
                                    checked={active ? selectedRepeals.includes(p.key) : selectedPolicies.includes(p.key)}
                                    onChange={() => (active ? toggleRepeal(p.key) : togglePolicy(p.key))}
                                  />
                                </label>
                                <div className="card-title-section">
                                  <h4>{p.name}</h4>
                                  <div className="card-badges">
                                    {partyIdeologyBonus && (
                                      <span className={`badge bonus-badge bonus-${session.party_ideology}`}>
                                        {session.party_ideology === "green" && "🟢 Grün-Bonus"}
                                        {session.party_ideology === "red" && "🔴 Rot-Bonus"}
                                        {session.party_ideology === "blue" && "🔵 Blau-Bonus"}
                                      </span>
                                    )}
                                    <span className="badge cost-badge">🔵 {p.capital_cost} PC</span>
                                    {incomeHint && <span className="badge income-badge">💰 {incomeHint}</span>}
                                    {active && <span className="badge active-badge">aktiv</span>}
                                  </div>
                                </div>
                                <button
                                  className="expand-btn"
                                  onClick={() => togglePolicyExpanded(p.key)}
                                  title={p.description ? "Details" : ""}
                                >
                                  {expanded ? "▼" : "▶"}
                                </button>
                              </div>

                              {expanded && (
                                <div className="card-details">
                                  {p.description && (
                                    <p className="policy-description">{p.description}</p>
                                  )}
                                  {locked && missing.length > 0 && (
                                    <p className="hint requirement-hint">
                                      ⚠️ Braucht zuerst: {missing.map(policyLabel).join(", ")}
                                    </p>
                                  )}
                                  {locked && missingUnlocks.length > 0 && (
                                    <p className="hint requirement-hint">
                                      🔓 Wird verfuegbar, wenn: {missingUnlocks.join(", ")}
                                    </p>
                                  )}
                                  {repealBlocked && (
                                    <p className="hint requirement-hint">
                                      🔒 Kann nicht zurueckgezogen werden, solange aktiv: {dependents.join(", ")}
                                    </p>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                    </div>
                  </div>
                ))}
              </div>
              )}
              {!session.opposition_mode && selectedCapitalCost > session.political_capital && (
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

          <FrontPage events={events} reports={reports} oppositionReaction={oppositionReaction} />

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
