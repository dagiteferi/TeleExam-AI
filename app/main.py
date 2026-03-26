from __future__ import annotations
import logging
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import api_router
from app.core.config import settings
from app.core.middleware import TelegramAuthContextMiddleware


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    _configure_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="TeleExam AI Backend", version="0.1.0", lifespan=lifespan)

    app.add_middleware(TelegramAuthContextMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app


app = create_app()

