"""Platzhalter: Import echter Niedersachsen-Statistiken.

Quelle: Landesamt fuer Statistik Niedersachsen (LSN) ueber die
gemeinsame Landesdatenbank https://www.landesdatenbank.de bzw.
https://www.regionalstatistik.de (Destatis-Regionalverbund).

Anders als die Weltbank-API gibt es hier keinen einfachen REST-Endpunkt
pro Kennzahl -- Tabellen werden ueber die Genesis-Online-Schnittstelle
(GENESIS-API, SOAP/REST-Hybrid, Registrierung noetig) oder per manuellem
CSV-Export abgerufen. Dieses Modul ist bewusst noch ein Geruest: sobald die
konkreten Tabellencodes fuer die im Spiel gebrauchten Statistiken feststehen
(siehe app/seed.py::STATISTIC_META fuer die aktuell im MVP verwendeten Keys),
hier die echten Abruf-/Parse-Funktionen ergaenzen.

Geplanter Ablauf:
1. GENESIS-API-Zugang beantragen (kostenlos, Registrierung):
   https://www.regionalstatistik.de/genesis/online
2. Tabellencode pro Statistik heraussuchen (z.B. Arbeitslosenquote nach
   Kreis, Tabelle "13211-01-05-4").
3. Werte auf Bundesland-Ebene (Niedersachsen, Regionalschluessel "03")
   aggregieren/filtern.
4. In StatisticValue-Zeilen (turn_number=0, "Startwert") ueberfuehren.
"""
from __future__ import annotations


def fetch_statistic(table_code: str, region_code: str = "03") -> dict:
    """Platzhalter. region_code '03' = Niedersachsen (amtlicher Regionalschluessel)."""
    raise NotImplementedError(
        "Noch kein echter GENESIS-API-Abruf implementiert. "
        "Siehe Modul-Docstring fuer den geplanten Ablauf."
    )
