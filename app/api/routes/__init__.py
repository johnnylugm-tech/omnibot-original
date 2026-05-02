"""Routes package — Phase 3 refactor from God File."""
from app.api.routes.kpi import router as kpi_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.conversations import router as conversations_router

__all__ = ["kpi_router", "knowledge_router", "conversations_router"]
