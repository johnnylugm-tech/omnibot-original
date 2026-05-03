"""API endpoints — refactored: routes split into dedicated modules."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.background.monitoring import (
    automated_monitoring_loop as automated_monitoring_loop,
)
from app.api.deps import (
    DAILY_COST_CAP as DAILY_COST_CAP,
)
from app.api.deps import (
    LINE_CHANNEL_SECRET as LINE_CHANNEL_SECRET,
)
from app.api.deps import (
    MESSENGER_APP_SECRET as MESSENGER_APP_SECRET,
)
from app.api.deps import (
    REDIS_URL as REDIS_URL,
)
from app.api.deps import (
    TELEGRAM_BOT_TOKEN as TELEGRAM_BOT_TOKEN,
)
from app.api.deps import (
    WHATSAPP_APP_SECRET as WHATSAPP_APP_SECRET,
)
from app.api.deps import (
    degradation_manager as degradation_manager,
)
from app.api.deps import (
    ip_whitelist as ip_whitelist,
)
from app.api.deps import (
    logger as logger,
)

# Import helpers FIRST so routes.webhooks can import them from app.api
from app.api.helpers import (
    get_active_conversation as get_active_conversation,
)
from app.api.helpers import (
    get_emotion_tracker as get_emotion_tracker,
)
from app.api.helpers import (
    get_or_create_user as get_or_create_user,
)
from app.api.routes import (
    health as health,
)
from app.api.routes import (
    knowledge as knowledge,
)
from app.api.routes import (
    kpi as kpi,
)
from app.api.routes import (
    webhooks as webhooks,
)
from app.api.routes.webhooks import (
    line_webhook as line_webhook,
)
from app.api.routes.webhooks import (
    messenger_webhook as messenger_webhook,
)
from app.api.routes.webhooks import (
    process_webhook_message as process_webhook_message,
)
from app.api.routes.webhooks import (
    set_worker as set_worker,
)
from app.api.routes.webhooks import (
    telegram_webhook as telegram_webhook,
)
from app.api.routes.webhooks import (
    whatsapp_webhook as whatsapp_webhook,
)
from app.models.database import AsyncSessionLocal as AsyncSessionLocal
from app.services.knowledge import HybridKnowledgeV7 as HybridKnowledgeV7
from app.services.kpi import KPIManager as KPIManager
from app.services.worker import AsyncMessageProcessor as AsyncMessageProcessor
from app.utils.i18n import i18n as i18n
from app.utils.tracing import setup_tracing as setup_tracing

setup_tracing()

# Global worker — injected into webhooks module after creation
_worker: Optional[AsyncMessageProcessor] = None
worker = _worker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan: start worker + monitoring, teardown on exit."""
    global _worker
    try:
        _worker = await AsyncMessageProcessor.create(REDIS_URL)
        logger.info("worker_started", redis_url=REDIS_URL)
    except Exception as e:
        logger.error("worker_start_failed", error=str(e))

    set_worker(_worker)

    monitor_task = asyncio.create_task(automated_monitoring_loop())

    yield

    monitor_task.cancel()
    if _worker:
        await _worker.close()


app = FastAPI(title="OmniBot API", version="1.1.0", lifespan=lifespan)

# ── Exception handlers ─────────────────────────────────────────────────────────


@app.exception_handler(asyncio.TimeoutError)
async def timeout_exception_handler(
    request: Request, exc: asyncio.TimeoutError
) -> JSONResponse:
    return JSONResponse(status_code=504, content={"detail": "LLM_TIMEOUT"})


@app.exception_handler(TimeoutError)
async def timeout_error_exception_handler(
    request: Request, exc: TimeoutError
) -> JSONResponse:
    return JSONResponse(status_code=504, content={"detail": "LLM_TIMEOUT"})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    content: dict[str, Any] = {"detail": exc.detail}
    if exc.status_code == 401:
        content["error_code"] = "AUTH_TOKEN_EXPIRED"
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": i18n.translate("error"),
            "error_code": "INTERNAL_ERROR",
        },
    )


# ── Route registration ─────────────────────────────────────────────────────────

app.include_router(webhooks.router)
app.include_router(knowledge.router)
app.include_router(kpi.router)
app.include_router(health.router)
