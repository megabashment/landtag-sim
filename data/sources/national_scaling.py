"""Platzhalter fuer die spaetere Skalierungsstufe Nation/EU (nicht MVP).

Wenn eine AdminUnit mit level=NATION oder level=SUPRANATIONAL angelegt wird
(siehe backend/app/models/admin_unit.py), liefern diese Quellen die
Startwerte:

- Weltbank Open Data API (https://data.worldbank.org, REST, CC-BY 4.0):
  direktes Pendant zu den LSN-Regionaldaten, aber auf Länderebene.
- V-Dem (https://www.v-dem.net) / Freedom House (https://freedomhouse.org)
  fuer politische Indizes (Demokratie-Score, Pressefreiheit etc.) --
  Lizenzbedingungen jeweils vor Nutzung pruefen, da nicht einheitlich CC.

Bewusst noch nicht implementiert, da MVP-Scope = Niedersachsen (Region).
"""
