// Duenner REST-Client fuers FastAPI-Backend. Rein rundenbasiert (siehe
// docs/architecture.md, Option A der Kommunikationsmodell-Entscheidung) --
// kein WebSocket noetig, solange es kein Multiplayer/Zuschauer-Modus gibt.
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function request(path, options) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export const api = {
  // Dynamischer Policy-Katalog (siehe backend/app/api/routes_game.py::
  // list_policies) -- ersetzt die zuvor hart codierte AVAILABLE_POLICIES-
  // Konstante in App.jsx.
  listPolicies: () => request("/policies"),
  createSession: () => request("/sessions", { method: "POST" }),
  // B23 "Party-Gründung (Persistente Meta-Ebene)": neue Session mit Party
  createPartySession: (name, ideology) =>
    request("/sessions/new-party", {
      method: "POST",
      body: JSON.stringify({ name, ideology }),
    }),
  getSession: (id) => request(`/sessions/${id}`),
  // repealPolicyKeys: Democracy-4-Vorbild "Policy-Repeal" (siehe
  // landtag_sim.engine.py::advance_turn) -- Policies, die diese Runde
  // zurueckgezogen werden sollen. Optional, damit bestehende Aufrufer ohne
  // Repeal-UI nicht angepasst werden muessen.
  // oppositionCampaignKey: M5 "Opposition-Loop" (BACKLOG.md B15) -- Kampagne-Key
  // statt Policy-Enact wenn opposition_mode=true. Optional.
  advanceTurn: (id, enactPolicyKeys, repealPolicyKeys = [], oppositionCampaignKey = null) =>
    request(`/sessions/${id}/advance`, {
      method: "POST",
      body: JSON.stringify({
        enact_policy_keys: enactPolicyKeys,
        repeal_policy_keys: repealPolicyKeys,
        opposition_campaign_key: oppositionCampaignKey,
      }),
    }),
  // P0-Punkt "Effekt-Vorschau vor Entscheidung" (docs/game-design-roadmap.md):
  // simuliert die naechste Runde, persistiert aber nichts.
  previewTurn: (id, enactPolicyKeys, repealPolicyKeys = []) =>
    request(`/sessions/${id}/preview`, {
      method: "POST",
      body: JSON.stringify({ enact_policy_keys: enactPolicyKeys, repeal_policy_keys: repealPolicyKeys }),
    }),
  // P1-Punkt "Dilemma-Events mit echten Entscheidungsoptionen": wendet die
  // gewaehlte Option eines offenen Dilemmas an, zaehlt keine eigene Runde.
  resolveDilemma: (id, optionKey) =>
    request(`/sessions/${id}/resolve-dilemma`, {
      method: "POST",
      body: JSON.stringify({ option_key: optionKey }),
    }),
};
