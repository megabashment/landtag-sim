// B27-Folgearbeit "Bundesland-Visualisierung" (Nutzer-Feedback 2026-09-13):
// echte, oeffentlich lizenzierte Vektor-Lagekarten statt der urspruenglichen
// Platzhalter-Silhouetten. Quelle: Wikimedia Commons, Autor "TUBS", CC BY-SA
// 3.0 (Namensnennung + Weitergabe unter derselben Lizenz -- siehe CREDITS.md).
// Dateien liegen unverändert (keine Bearbeitung/Ableitung) unter
// frontend/public/maps/<key>.svg und werden als <img> eingebunden (siehe
// BundeslandBadge in App.jsx), nicht inline -- bei ~680 KB pro Datei waere
// das Inline-Rendering im JS-Bundle unnoetig aufgeblaeht; als statische
// Datei wird sie einmal vom Browser geladen und gecacht.
//
// REAL_MAP_KEYS markiert, fuer welche Bundeslaender eine echte Karte existiert.
// Faellt ein Key hier NICHT rein (z.B. ein neu hinzugefuegtes Bundesland ohne
// bereits beschaffte Karte), zeigt BundeslandBadge stattdessen die
// Platzhalter-Silhouette aus PLACEHOLDER_SILHOUETTES -- kein hartes Nichts.
export const REAL_MAP_KEYS = new Set(["niedersachsen", "bayern", "nrw"]);

export function bundeslandMapSrc(bundeslandKey) {
  return REAL_MAP_KEYS.has(bundeslandKey) ? `/maps/${bundeslandKey}.svg` : null;
}

// Fallback-Silhouetten (siehe Kommentar oben) -- bewusst KEINE echten
// Landesgrenzen, nur ein generischer, leicht verzerrter Blob pro Bundesland,
// falls fuer einen Key (noch) keine echte Karte in REAL_MAP_KEYS steht.
export const PLACEHOLDER_SILHOUETTES = {
  niedersachsen: {
    viewBox: "0 0 120 80",
    path: "M12 30 Q8 14 28 12 Q40 4 58 10 Q78 2 96 14 Q112 18 108 34 Q116 46 100 56 Q104 70 82 72 Q64 78 46 70 Q26 76 16 62 Q2 52 12 30 Z",
  },
  bayern: {
    viewBox: "0 0 90 110",
    path: "M30 6 Q46 2 52 14 Q68 10 74 26 Q86 34 78 50 Q88 62 74 72 Q78 88 60 94 Q56 106 38 102 Q22 108 16 92 Q2 84 10 68 Q0 52 14 40 Q6 24 24 18 Q20 8 30 6 Z",
  },
  nrw: {
    viewBox: "0 0 100 90",
    path: "M20 14 Q34 2 52 8 Q70 2 82 16 Q96 24 88 40 Q98 52 84 62 Q88 78 68 80 Q54 90 38 80 Q18 82 14 64 Q0 54 10 38 Q2 22 20 14 Z",
  },
};

// Backend liefert nur den Anzeigenamen (SessionStateResponse.admin_unit_name,
// z.B. "Bayern"), keinen Key -- kleine Rueck-Abbildung fuer den Header, statt
// dafuer extra einen bundesland_key durchs ganze Schema zu ziehen.
const NAME_TO_KEY = {
  Niedersachsen: "niedersachsen",
  Bayern: "bayern",
  "Nordrhein-Westfalen": "nrw",
};

export function bundeslandKeyFromName(name) {
  return NAME_TO_KEY[name] ?? null;
}
