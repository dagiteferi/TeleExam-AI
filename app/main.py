from __future__ import annotations
import logging
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import api_router, public_api_router
from app.admin.auth import router as admin_auth_router
from app.admin.users import router as admin_users_router
from app.admin.stats import router as admin_stats_router
from app.core.config import settings
from app.core.middleware import RequestIdMiddleware, BotAuthMiddleware, RateLimitMiddleware, request_id_context, telegram_id_context
from app.db.redis import init_redis, close_redis


def add_context_vars_to_log_processor(_, __, event_dict):
    request_id = request_id_context.get()
    if request_id:
        event_dict["request_id"] = request_id
    telegram_id = telegram_id_context.get()
    if telegram_id:
        event_dict["telegram_id"] = telegram_id
    return event_dict


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            add_context_vars_to_log_processor,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    _configure_logging()
    await init_redis()
    yield
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(title="TeleExam AI Backend", version="0.1.0", lifespan=lifespan)

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(BotAuthMiddleware)
    app.add_middleware(RateLimitMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.render import router as render_router
    app.include_router(public_api_router)
    app.include_router(api_router)
    app.include_router(render_router, prefix="/api", tags=["render"])
    app.include_router(admin_auth_router, prefix="/admin", tags=["Admin Auth"])
    app.include_router(admin_users_router, prefix="/admin", tags=["Admin Users"])
    app.include_router(admin_stats_router, prefix="/admin", tags=["Admin Stats"])
    return app


app = create_app()

