"""Database Service - Phase 3"""

import typing

from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseService:
    """Mockable Database service for testing"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, stmt: "typing.Any"):
        """Execute statement"""
        return await self.db.execute(stmt)
