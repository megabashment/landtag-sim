from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_game, routes_health
from app.config import get_settings
from app.db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # MVP: create_all statt Alembic-Migration beim Start. Sobald das Schema
    # sich stabilisiert, per `alembic upgrade head` ersetzen (siehe backend/alembic/).
    init_db()
    yield


app = FastAPI(title="Landtag-Sim API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_health.router)
app.include_router(routes_game.router)
