"""KPI dashboard route.

Phase 3 refactor: extracted from app/api/__init__.py
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.security.rbac import rbac
from app.services.kpi import KPIManager

router = APIRouter(prefix="/api/v1/kpi", tags=["kpi"])


@router.get("/dashboard")
async def get_kpi_dashboard(
    db: AsyncSession = Depends(get_db),
    user_role: str = Depends(rbac.require("system", "read")),
) -> Any:
    """Enterprise KPI Dashboard - Phase 3 Real Implementation"""
    kpi_manager = KPIManager(db)
    total_convs = await kpi_manager.get_total_conversations()
    avg_res_time = await kpi_manager.get_avg_resolution_time()
    esc_rate = await kpi_manager.get_escalation_rate()
    hit_rate = await kpi_manager.get_knowledge_hit_rate()
    sla_rate = await kpi_manager.get_sla_compliance_rate()
    revenue = await kpi_manager.get_revenue_per_conversation()
    daily = await kpi_manager.get_daily_breakdown(days=7)

    return {
        "success": True,
        "data": {
            "summary": {
                "total_conversations": total_convs,
                "avg_resolution_time_sec": round(avg_res_time, 2),
                "escalation_rate": round(esc_rate * 100, 2),
                "knowledge_hit_rate": round(hit_rate * 100, 2),
                "sla_compliance_rate": round(sla_rate * 100, 2),
                "estimated_revenue_per_conv": round(revenue, 2),
            },
            "daily_trends": daily,
        },
    }
