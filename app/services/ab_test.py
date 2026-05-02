"""A/B Testing Framework - Phase 3"""
import hashlib
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Experiment


class ABTestManager:
    """Manages variant assignment and experiment execution (Phase 3)"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_variant(self, user_id: str, experiment_id: int) -> str:
        """
        Deterministic variant assignment using SHA-256 hash of user_id + experiment_id.
        Ensures consistency across different app instances.
        """
        key = f"{user_id}:{experiment_id}".encode("utf-8")
        digest = hashlib.sha256(key).hexdigest()
        # Use first 8 chars for 0-99 bucket
        variant_hash = int(digest[:8], 16) % 100

        # Fetch experiment from DB
        stmt = select(Experiment).where(Experiment.id == experiment_id)
        result = await self.db.execute(stmt)
        experiment = result.scalar_one_or_none()

        if not experiment or experiment.status != "running":
            return "control"

        # e.g., {"control": 50, "test_v1": 50}
        split = experiment.traffic_split
        cumulative = 0
        for variant, percentage in split.items():
            cumulative += percentage
            if variant_hash < cumulative:
                return variant

        return "control"

    async def get_active_experiment(self, name: str) -> Optional[Experiment]:
        """Fetch active experiment by name"""
        stmt = select(Experiment).where(Experiment.name ==
                                        name, Experiment.status == "running")
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_prompt_variant(self, user_id: str, experiment_name: str) -> Optional[str]:
        """Convenience method to get a prompt variant for a specific experiment"""
        experiment = await self.get_active_experiment(experiment_name)
        if not experiment:
            return None

        exp_id = int(experiment.id) if experiment.id is not None else 0
        variant_name = await self.get_variant(user_id, exp_id)
        return experiment.variants.get(variant_name, {}).get("prompt")
