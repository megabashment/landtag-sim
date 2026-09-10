// B23 Party Icons: konsistentes Icon Set basierend auf Lucide Icons (MIT-Lizenz)
// Jedes Icon repräsentiert eine Party-Archetyp nach Ideologie & Name
// Lucide Icons: https://lucide.dev/ (MIT License)

export const PARTY_ICONS = {
  // Grüne Ideologie - Umweltorientiert
  "die-grünen": {
    name: "Die Grünen",
    ideology: "green",
    icon: "🌿", // Leaf - Natur, Umweltschutz
    svgPath: "M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 2c4.418 0 8 3.582 8 8s-3.582 8-8 8-8-3.582-8-8 3.582-8 8-8z",
  },
  "ökobewegung": {
    name: "Ökobewegung",
    ideology: "green",
    icon: "🌳", // Tree - Waldschutz, Nachhaltigkeit
    svgPath: "M12 2c-1.105 0-2 .895-2 2v7H7c-1.105 0-2 .895-2 2s.895 2 2 2h3v2H5c-1.105 0-2 .895-2 2s.895 2 2 2h5v5c0 1.105.895 2 2 2s2-.895 2-2v-5h5c1.105 0 2-.895 2-2s-.895-2-2-2h-5v-2h3c1.105 0 2-.895 2-2s-.895-2-2-2h-3V4c0-1.105-.895-2-2-2z",
  },
  "naturfreunde": {
    name: "Naturfreunde",
    ideology: "green",
    icon: "🌻", // Flower - Biodiversität, Naturschutz
    svgPath: "M12 2c-1.105 0-2 .895-2 2v4.764c-.532-.235-1.12-.353-1.739-.353-2.485 0-4.5 2.015-4.5 4.5S5.776 17.411 8.261 17.411c.619 0 1.207-.118 1.739-.353V22c0 1.105.895 2 2 2s2-.895 2-2v-4.764c.532.235 1.12.353 1.739.353 2.485 0 4.5-2.015 4.5-4.5s-2.015-4.5-4.5-4.5c-.619 0-1.207.118-1.739.353V4c0-1.105-.895-2-2-2z",
  },

  // Rote Ideologie - Sozialdemokratisch/Arbeiterpartei
  "spd": {
    name: "Sozialdemokratische Partei",
    ideology: "red",
    icon: "👥", // People - Soziale Gerechtigkeit
    svgPath: "M12 2c2.21 0 4 1.79 4 4s-1.79 4-4 4-4-1.79-4-4 1.79-4 4-4zm0 8c2.21 0 4 1.79 4 4v2h-8v-2c0-2.21 1.79-4 4-4zm7.5 2c.828 0 1.5.672 1.5 1.5S20.328 15 19.5 15 18 14.328 18 13.5s.672-1.5 1.5-1.5zm-15 0c.828 0 1.5.672 1.5 1.5S5.328 15 4.5 15 3 14.328 3 13.5 3.672 12 4.5 12zm14 3c.828 0 1.5.672 1.5 1.5v1c0 1.105-.895 2-2 2h-2v-2c0-.828.672-1.5 1.5-1.5h1zm-12 0h1c.828 0 1.5.672 1.5 1.5v2H5c-1.105 0-2-.895-2-2v-1c0-.828.672-1.5 1.5-1.5z",
  },
  "linke": {
    name: "Die Linke",
    ideology: "red",
    icon: "✊", // Fist - Arbeiterkampf, Solidarität
    svgPath: "M6 2c-1.105 0-2 .895-2 2v7.236l-2 1.382V22c0 1.105.895 2 2 2h2V11.618L6 10.236V4c0-1.105-.895-2-2-2zm2 0c1.105 0 2 .895 2 2v7h1.236l2-1.382V4c0-1.105-.895-2-2-2h-3zm4 0c1.105 0 2 .895 2 2v7h1.236l2-1.382V4c0-1.105-.895-2-2-2h-3zm4 0c1.105 0 2 .895 2 2v7h1.236l2-1.382V4c0-1.105-.895-2-2-2h-3zm4 0c1.105 0 2 .895 2 2v7h1.236l2-1.382V4c0-1.105-.895-2-2-2h-3zm2 9h2c1.105 0 2 .895 2 2v9c0 1.105-.895 2-2 2h-2c-1.105 0-2-.895-2-2v-9c0-1.105.895-2 2-2z",
  },
  "arbeiterpartei": {
    name: "Arbeiterpartei",
    ideology: "red",
    icon: "🔨", // Hammer - Arbeiter, Handwerk
    svgPath: "M11.5 2l-2 1v3l2 1v-5zm1.5 2l-2 1v3l2 1V4zm3 0c1.105 0 2 .895 2 2v13c0 1.105-.895 2-2 2h-1V4h1zm-8 1v15h-2c-1.105 0-2-.895-2-2V6c0-1.105.895-2 2-2h2zm7 2h5c.552 0 1 .448 1 1v5c0 .552-.448 1-1 1h-5V7z",
  },

  // Blaue Ideologie - Konservativ/Marktwirtschaft
  "cdu": {
    name: "Christlich Demokratische Union",
    ideology: "blue",
    icon: "🛡️", // Shield - Stabilität, Sicherheit
    svgPath: "M12 2L4 6v5c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V6l-8-4z",
  },
  "fwirtschaft": {
    name: "Freihandelsbund",
    ideology: "blue",
    icon: "💼", // Briefcase - Wirtschaft, Business
    svgPath: "M20 6h-2.18C17.16 4.84 15.68 4 14 4c-2.4 0-4.46 1.78-4.9 4H10V4H8v4H6.9C6.46 5.78 4.4 4 2 4c-1.68 0-3.16.84-3.82 2H0v14h20V6zm-6-2c.83 0 1.5.67 1.5 1.5S14.83 7 14 7s-1.5-.67-1.5-1.5S13.17 4 14 4zm4 14H2V8h16v10z",
  },
  "unternehmerbund": {
    name: "Unternehmerbund",
    ideology: "blue",
    icon: "🏢", // Building - Wirtschaft, Unternehmen
    svgPath: "M5 13h2v8H5zm5-8h2v16h-2zm5-2h2v18h-2zm8 0h2v18h-2zM2 21h20v2H2z",
  },

  // Neutrale Ideologie - Verschiedenes
  "liberale": {
    name: "Liberale Partei",
    ideology: null,
    icon: "⭐", // Star - Freiheit, Fortschritt
    svgPath: "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z",
  },
  "zentrum": {
    name: "Zentrumspartei",
    ideology: null,
    icon: "⚖️", // Scales - Ausgleich, Gerechtigkeit
    svgPath: "M13 2v7h8v2h-1v7h-2v-7h-2v7h-2v-7H6v-2h8V2h2zm-6 10h-5v8h5v-8z",
  },
  "unabhängige": {
    name: "Unabhängige",
    ideology: null,
    icon: "👤", // Person - Individualität
    svgPath: "M12 2c2.21 0 4 1.79 4 4s-1.79 4-4 4-4-1.79-4-4 1.79-4 4-4zm0 8c2.67 0 8 1.34 8 4v2H4v-2c0-2.66 5.33-4 8-4z",
  },
  "piraten": {
    name: "Piratenpartei",
    ideology: null,
    icon: "🏴‍☠️", // Pirate - Digital, Freiheit
    svgPath: "M3 5a2 2 0 012-2h3.28a1 1 0 00.948-1.316c-.87-1.855.20-2.945 2.561-2.945 2.362 0 3.431 1.09 2.56 2.945a1 1 0 00.949 1.316H19a2 2 0 012 2v4H3V5zm9 4a2 2 0 100-4 2 2 0 000 4z",
  },
  "tech-partei": {
    name: "Tech-Partei",
    ideology: null,
    icon: "💻", // Code - Innovation, Technologie
    svgPath: "M10 20a10 10 0 1 1 0-20 10 10 0 0 1 0 20zm3.5-9a1.5 1.5 0 1 0-3 0 1.5 1.5 0 0 0 3 0zm-5-4a1 1 0 1 0-2 0 1 1 0 0 0 2 0zm7 6a1 1 0 1 0-2 0 1 1 0 0 0 2 0z",
  },
  "grün-alternativ": {
    name: "Bündnis Grün-Alternative",
    ideology: "green",
    icon: "🌿", // Blend - Hybrid, Alternative
    svgPath: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z",
  },
};

// Komplementäre Ideologie-Icons für die PartyCreationDialog
export const IDEOLOGY_ICONS = {
  green: {
    emoji: "🟢",
    name: "Grün",
    description: "+Umwelt, -Wirtschaft",
    svgPath: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11h-4v4h-2v-4H7v-2h4V7h2v4h4v2z",
  },
  red: {
    emoji: "🔴",
    name: "Rot",
    description: "+Sozial, -Wirtschaft",
    svgPath: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm0-13c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5z",
  },
  blue: {
    emoji: "🔵",
    name: "Blau",
    description: "+Wirtschaft, -Umwelt",
    svgPath: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z",
  },
};

// Hilfsfunktionen für Party-Icon Rendering
export function getPartyIcon(partyKey) {
  return PARTY_ICONS[partyKey] || null;
}

export function getIdeologyIcon(ideology) {
  return IDEOLOGY_ICONS[ideology] || null;
}

// Hilfsfunktion um alle Parteien einer Ideologie zu holen
export function getPartiesByIdeology(ideology) {
  return Object.entries(PARTY_ICONS)
    .filter(([, party]) => party.ideology === ideology)
    .map(([key, party]) => ({ key, ...party }));
}
