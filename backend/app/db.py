"""Datenbank-Engine und Session-Handling (SQLModel/SQLAlchemy)."""
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

# pool_pre_ping schuetzt gegen weggebrochene Verbindungen bei lokalem Postgres
# (z.B. nach docker-compose restart).
engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)


def init_db() -> None:
    """Legt alle Tabellen an, falls sie nicht existieren.

    Fuer die MVP-Phase reicht create_all; sobald das Schema sich haeufiger
    aendert, uebernimmt Alembic (siehe backend/alembic/) die Migrationen.
    """
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
