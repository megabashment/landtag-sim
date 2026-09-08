"""Platzhalter: Download der Niedersachsen-Grenzgeometrie fuer Kartenansicht.

Zwei Optionen, beide public-domain/offen:

1. Natural Earth, Admin-1-Ebene (Bundeslaender/Provinzen weltweit), grob
   generalisiert -- reicht fuer eine kleine Uebersichtskarte im UI:
   https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-1-states-provinces/

2. BKG Verwaltungsgebiete VG250 (Bundesamt fuer Kartographie und Geodaesie),
   deutlich genauer, spezifisch fuer Deutschland (falls spaeter Kreis-Ebene
   innerhalb Niedersachsens dargestellt werden soll):
   https://gdz.bkg.bund.de/index.php/default/verwaltungsgebiete-1-250-000-stand-01-01-vg250.html

Fuer den MVP reicht Option 1 (Natural Earth), gefiltert auf
`admin == "Germany"` und `name == "Niedersachsen"`.
"""
from __future__ import annotations

NATURAL_EARTH_ADMIN1_URL = (
    "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip"
)


def download_and_filter_niedersachsen(output_path: str) -> None:
    raise NotImplementedError(
        "Platzhalter -- Download+Filter (z.B. mit geopandas) noch nicht implementiert. "
        f"Quelle: {NATURAL_EARTH_ADMIN1_URL}"
    )
