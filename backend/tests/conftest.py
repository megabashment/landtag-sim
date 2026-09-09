"""Gemeinsame Fixtures fuer die Backend-API-Tests.

Bisher (siehe mistakes.md/CLAUDE.md, Doku-Audit 2026-09-09) gab es hier
ausser einem Health-Check-Smoketest KEINE automatisierten Tests -- /sessions,
/preview, /advance, /resolve-dilemma und /policies wurden ausschliesslich
manuell per curl verifiziert. Dieses conftest.py schliesst die Luecke.

WICHTIG: DATABASE_URL wird auf eine EIGENE Test-Datenbank umgebogen, BEVOR
irgendein app.*-Modul importiert wird -- app.config.get_settings() ist
@lru_cache-dekoriert, der zuerst aufgeloeste Wert bleibt fuer den Rest des
Prozesses fix. Das haelt Tests komplett getrennt von der lokalen
Dev-Datenbank (landtag_sim): ein Testlauf legt Tabellen leer/neu an und
wuerde sonst echte lokale Spielstaende zerstoeren.

Einmaliges Setup (analog zum Postgres-15+-Owner-Fix fuer die normale
landtag_sim-DB, siehe mistakes.md "Verifikations-Workflow ... scheiterte
mit 'permission denied for schema public'"):

    sudo -u postgres psql -c "CREATE DATABASE landtag_sim_test;"
    sudo -u postgres psql -d landtag_sim_test -c "ALTER DATABASE landtag_sim_test OWNER TO landtag;"
    sudo -u postgres psql -d landtag_sim_test -c "ALTER SCHEMA public OWNER TO landtag;"

Siehe auch CLAUDE.md "Verifikations-Workflow".
"""
import os

os.environ["DATABASE_URL"] = "postgresql+psycopg2://landtag:landtag@localhost:5432/landtag_sim_test"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.db import engine
from app.main import app


@pytest.fixture(scope="session")
def client():
    """Ein TestClient fuer die gesamte Testsession. Tabellen werden einmal
    zu Beginn komplett neu angelegt (nicht pro Test) -- jeder Test erzeugt
    seine eigene GameSession ueber POST /sessions (fortlaufende IDs) und
    kollidiert daher nicht mit anderen Tests, auch ohne Rollback pro Test.
    Katalogdaten (Policies/Events/Dilemmas) sind ohnehin global und werden
    ueber ensure_*_catalog() idempotent geseedet."""
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def session_id(client) -> int:
    """Legt eine frische Session an und gibt ihre ID zurueck -- Grundlage
    fuer die meisten Tests, die nicht selbst am Session-Erstellungsverhalten
    interessiert sind."""
    response = client.post("/sessions")
    assert response.status_code == 200
    return response.json()["session_id"]
