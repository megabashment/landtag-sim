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
  createSession: () => request("/sessions", { method: "POST" }),
  getSession: (id) => request(`/sessions/${id}`),
  advanceTurn: (id, enactPolicyKeys) =>
    request(`/sessions/${id}/advance`, {
      method: "POST",
      body: JSON.stringify({ enact_policy_keys: enactPolicyKeys }),
    }),
  // P0-Punkt "Effekt-Vorschau vor Entscheidung" (docs/game-design-roadmap.md):
  // simuliert die naechste Runde, persistiert aber nichts.
  previewTurn: (id, enactPolicyKeys) =>
    request(`/sessions/${id}/preview`, {
      method: "POST",
      body: JSON.stringify({ enact_policy_keys: enactPolicyKeys }),
    }),
  // P1-Punkt "Dilemma-Events mit echten Entscheidungsoptionen": wendet die
  // gewaehlte Option eines offenen Dilemmas an, zaehlt keine eigene Runde.
  resolveDilemma: (id, optionKey) =>
    request(`/sessions/${id}/resolve-dilemma`, {
      method: "POST",
      body: JSON.stringify({ option_key: optionKey }),
    }),
};
