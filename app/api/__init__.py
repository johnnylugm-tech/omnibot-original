"""API endpoints - Phase 1"""
import time
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.models import (
    UnifiedResponse,
)
from app.security import InputSanitizer, PIIMasking, RateLimiter, get_verifier
from app.utils.logger import StructuredLogger

app = FastAPI(title="OmniBot API", version="1.0.0")

# Dependencies (initialized on startup)
sanitizer = InputSanitizer()
pii_masking = PIIMasking()
rate_limiter = RateLimiter()
logger = StructuredLogger("omnibot")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"}
    )


def verify_signature(platform: str, body: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature"""
    verifier = get_verifier(platform, secret)
    if verifier:
        return verifier.verify(body, signature)
    return False


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "uptime_seconds": time.time()}


@app.post("/api/v1/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret: Optional[str] = Header(None)
):
    """Telegram bot webhook"""
    await request.body()

    # Rate limit check
    if not rate_limiter.check("telegram", "user"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Signature verification would go here
    # In production: verify_signature("telegram", body, ...)

    data = await request.json()
    message = data.get("message", {})
    user_id = str(message.get("from", {}).get("id", ""))
    text = message.get("text", "")

    # Sanitize input
    text = sanitizer.sanitize(text)

    # PII masking
    pii_masking.mask(text)
    if pii_masking.should_escalate(text):
        return JSONResponse(
            content={"success": True, "data": {"response": "正在為您轉接人工客服"}},
            status_code=200
        )

    # Query knowledge layer (placeholder)
    result = UnifiedResponse(
        content="請稍後，我們會盡快回覆您",
        source="rule",
        confidence=0.0
    )

    logger.info("telegram_message", user_id=user_id, source=result.source)

    return {"success": True, "data": {"response": result.content}}


@app.post("/api/v1/webhook/line")
async def line_webhook(
    request: Request,
    x_line_signature: Optional[str] = Header(None)
):
    """LINE Messaging API webhook"""
    await request.body()

    if not rate_limiter.check("line", "user"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    data = await request.json()
    events = data.get("events", [])

    responses = []
    for event in events:
        if event.get("type") == "message":
            text = event.get("message", {}).get("text", "")
            text = sanitizer.sanitize(text)

            pii_masking.mask(text)

            response = UnifiedResponse(
                content="請稍後，我們會盡快回覆您",
                source="rule",
                confidence=0.0
            )
            responses.append(response.content)

    return {"success": True, "data": {"responses": responses}}


@app.get("/api/v1/knowledge")
async def query_knowledge(
    q: str,
    category: Optional[str] = None,
    page: int = 1,
    limit: int = 20
):
    """Query knowledge base"""
    return {"success": True, "data": {"items": [], "total": 0, "page": page, "limit": limit}}


@app.post("/api/v1/knowledge")
async def create_knowledge(item: dict):
    """Create knowledge entry"""
    return {"success": True, "data": {"id": 1}}


@app.put("/api/v1/knowledge/{id}")
async def update_knowledge(id: int, item: dict):
    """Update knowledge entry"""
    return {"success": True, "data": {"id": id}}


@app.delete("/api/v1/knowledge/{id}")
async def delete_knowledge(id: int):
    """Delete knowledge entry"""
    return {"success": True, "data": {"deleted": True}}


@app.post("/api/v1/knowledge/bulk")
async def bulk_import(items: list):
    """Bulk import knowledge"""
    return {"success": True, "data": {"imported": len(items)}}


@app.get("/api/v1/conversations")
async def list_conversations(
    page: int = 1,
    limit: int = 20
):
    """List conversations"""
    return {"success": True, "data": {"items": [], "total": 0, "page": page, "limit": limit}}
