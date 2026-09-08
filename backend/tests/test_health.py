"""Rauchtest fuer den Health-Endpoint.

Hinweis: der App-Startup-Hook (app.main.on_startup) ruft init_db() auf und
braucht daher eine erreichbare Postgres-Verbindung (siehe .env/DATABASE_URL)
-- dieser Test ist kein reiner Unit-Test ohne Infrastruktur. Fuer
DB-unabhaengige Tests siehe sim/tests/test_engine.py.
"""
from fastapi.testclient import TestClient

from app.main import app


def test_health_ok():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
