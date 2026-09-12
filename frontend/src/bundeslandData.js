// B27-Folgearbeit "Bundesland-Visualisierung" (Game-Director-Review 2026-09-12,
// siehe CLAUDE.md/mistakes.md): der Start-Bildschirm hatte bisher NULL
// raeumliche/geografische Verortung -- nur Text. Diese Datei liefert einen
// Platzhalter-Umriss pro Bundesland fuer die `BundeslandBadge`-Komponente
// in App.jsx (bewusst NICHT hier drin, reine Datenmodul-Konvention wie
// statIcons.js/partyIcons.js -- sonst bricht Fast-Refresh, siehe oxlint
// react(only-export-components)), damit Auswahl-Dialog/Header wenigstens
// eine visuelle Unterscheidung haben, BIS echte kartografische Daten
// eingebunden werden.
//
// WICHTIG -- das hier sind KEINE echten Landesgrenzen, nur ein generischer,
// leicht verzerrter Blob pro Bundesland (unterschiedliche Seitenverhaeltnisse,
// damit sie sich optisch unterscheiden). Fuer echte Umrisse:
//   1. Wikimedia Commons Kategorie "Positionskarte Deutschland" bzw. die
//      einzelnen Bundesland-Lagekarten (Public Domain / CC0, z.B. Datei
//      "Lower Saxony in Germany.svg", "Bavaria in Germany.svg",
//      "North Rhine-Westphalia in Germany.svg" auf commons.wikimedia.org)
//      herunterladen.
//   2. Den <path>-Inhalt extrahieren, hier den jittered_path je Key ersetzen.
//   3. CREDITS.md-Eintrag aktualisieren (Datei + Lizenz + Autor laut
//      Wikimedia-Dateiseite).
// Diese Datei ist bewusst so strukturiert (ein Key -> ein <path>-String),
// dass genau dieser Austausch spaeter ein Einzeiler ist.
export const BUNDESLAND_SILHOUETTES = {
  niedersachsen: {
    // Breit-flach, angelehnt an die Ost-West-Streckung des echten Bundeslands
    // (Kuestenland + Flaeche) -- reine Formsprache, keine echten Grenzen.
    viewBox: "0 0 120 80",
    path: "M12 30 Q8 14 28 12 Q40 4 58 10 Q78 2 96 14 Q112 18 108 34 Q116 46 100 56 Q104 70 82 72 Q64 78 46 70 Q26 76 16 62 Q2 52 12 30 Z",
  },
  bayern: {
    // Hochformat/diagonal, angelehnt an die Nordwest-Suedost-Ausdehnung.
    viewBox: "0 0 90 110",
    path: "M30 6 Q46 2 52 14 Q68 10 74 26 Q86 34 78 50 Q88 62 74 72 Q78 88 60 94 Q56 106 38 102 Q22 108 16 92 Q2 84 10 68 Q0 52 14 40 Q6 24 24 18 Q20 8 30 6 Z",
  },
  nrw: {
    // Kompakter, gedrungener Umriss.
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
