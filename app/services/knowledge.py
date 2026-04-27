"""Knowledge Layer Phase 1 - Rule matching only"""
import numpy as np
from typing import List, Optional
from sqlalchemy import select, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sentence_transformers import SentenceTransformer

from app.models.database import KnowledgeBase
from app.models import KnowledgeResult


class HybridKnowledgeV7:
    """Phase 2: Hybrid Knowledge Layer with RAG, RRF, and LLM support"""
    EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM = 384

    def __init__(self, db: AsyncSession, llm_client=None):
        self.db = db
        self.llm = llm_client
        self.model = SentenceTransformer(self.EMBEDDING_MODEL)

    async def query(self, query_text: str, user_context: dict = None) -> KnowledgeResult:
        """Query knowledge using Layer 1 (Rule) -> Layer 2 (RAG) -> Layer 3 (LLM)"""
        # Layer 1: Rule matching (40%)
        result = await self._rule_match(query_text)
        if result is not None and result.confidence > 0.9:
            return KnowledgeResult(
                id=result.id,
                content=result.content,
                confidence=result.confidence,
                source="rule",
                knowledge_id=result.knowledge_id,
            )

        # Layer 2: RAG + RRF (40%)
        rule_results = await self._rule_match_list(query_text)
        rag_results = await self._rag_search(query_text)

        rrf_results = self._reciprocal_rank_fusion(
            [rule_results, rag_results], k=60
        )

        if rrf_results and rrf_results[0].confidence > 0.7:
            return KnowledgeResult(
                id=rrf_results[0].id,
                content=rrf_results[0].content,
                confidence=rrf_results[0].confidence,
                source="rag",
                knowledge_id=rrf_results[0].knowledge_id,
            )

        # Layer 3: LLM generation (10%)
        if self.llm:
            llm_res = await self._llm_generate(query_text, user_context)
            if llm_res:
                # Layer 5: Grounding Check (Verify LLM response against context)
                if await self._grounding_check(llm_res, rule_results + rag_results):
                    return llm_res
                else:
                    return self._escalate(query_text, reason="hallucination_detected")

        # Layer 4: Human escalation (10%)
        return self._escalate(query_text, reason="out_of_scope")

    async def _grounding_check(self, response: KnowledgeResult, sources: list[KnowledgeResult]) -> bool:
        """L5: Grounding Check - Verify response against sources"""
        if not sources:
            return True # Fallback if no sources but LLM still generated something (risky)
        
        # Simple grounding: check if any keyword from sources is in the response
        # In production, this would be another LLM call or NLI model
        source_text = " ".join([s.content for s in sources])
        # Very simple heuristic: check if response has some overlap with sources
        words = [w for w in response.content.split() if len(w) > 2]
        if not words: return True
        
        matches = sum(1 for w in words if w in source_text)
        return matches / len(words) > 0.1 # At least 10% grounding for this simple version

    def _reciprocal_rank_fusion(
        self, results_lists: list[list[KnowledgeResult]], k: int = 60
    ) -> list[KnowledgeResult]:
        """RRF algorithm to fuse multiple search results"""
        rrf_scores: dict[int, float] = {}
        id_to_result: dict[int, KnowledgeResult] = {}

        for results in results_lists:
            for rank, item in enumerate(results, 1):
                doc_id = item.id
                if doc_id not in rrf_scores:
                    rrf_scores[doc_id] = 0.0
                    id_to_result[doc_id] = item
                rrf_scores[doc_id] += 1.0 / (rank + k)

        sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)

        return [
            KnowledgeResult(
                id=doc_id,
                content=id_to_result[doc_id].content,
                confidence=min(1.0, rrf_scores[doc_id] * 10), # Heuristic scaling
                source=id_to_result[doc_id].source,
                knowledge_id=id_to_result[doc_id].knowledge_id,
            )
            for doc_id in sorted_ids[:3]
        ]

    async def _rule_match(self, query_text: str) -> Optional[KnowledgeResult]:
        results = await self._rule_match_list(query_text)
        return results[0] if results else None

    async def _rule_match_list(self, query_text: str) -> list[KnowledgeResult]:
        stmt = (
            select(KnowledgeBase)
            .where(
                KnowledgeBase.is_active == True,
                or_(
                    KnowledgeBase.question.ilike(f"%{query_text}%"),
                    KnowledgeBase.keywords.any(query_text)
                )
            )
            .order_by(KnowledgeBase.version.desc())
            .limit(5)
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return [
            KnowledgeResult(
                id=row.id,
                content=row.answer,
                confidence=0.95 if query_text.lower() in row.question.lower() else 0.7,
                source="rule",
                knowledge_id=row.id,
            )
            for row in rows
        ]

    async def _rag_search(self, query_text: str) -> list[KnowledgeResult]:
        """Vector search using pgvector"""
        embedding = self.model.encode([query_text])[0].tolist()
        # Use pgvector cosine distance <=>
        # Note: In SQLAlchemy, we use text() or custom operators for pgvector if not using a specific extension
        stmt = text(
            "SELECT id, answer, 1 - (embeddings <=> :emb::vector) AS similarity "
            "FROM knowledge_base "
            "WHERE is_active = TRUE AND embedding_model = :model "
            "ORDER BY embeddings <=> :emb::vector "
            "LIMIT 5"
        )
        result = await self.db.execute(
            stmt, 
            {"emb": str(embedding), "model": self.EMBEDDING_MODEL}
        )
        rows = result.fetchall()
        return [
            KnowledgeResult(
                id=row[0],
                content=row[1],
                confidence=float(row[2]),
                source="rag",
                knowledge_id=row[0],
            )
            for row in rows
        ]

    async def _llm_generate(self, query: str, context: Optional[dict] = None) -> Optional[KnowledgeResult]:
        """LLM response generation (Simulated for Phase 3)"""
        # Simulate thinking delay
        import asyncio
        await asyncio.sleep(0.1)
        
        state_str = context.get('state', 'IDLE') if context else 'IDLE'
        
        return KnowledgeResult(
            id=0,
            content=f"根據您的對話狀態 {state_str}，我理解您想詢問 '{query}'。這是為您生成的個人化回覆。",
            confidence=0.85,
            source="llm",
            knowledge_id=0
        )

    def _escalate(self, query_text: str, reason: str) -> KnowledgeResult:
        return KnowledgeResult(
            id=-1,
            content="正在為您轉接人工客服，請稍候...",
            confidence=0.0,
            source="escalate",
        )
