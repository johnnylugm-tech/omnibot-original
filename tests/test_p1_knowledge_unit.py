import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.knowledge import HybridKnowledgeV7
from app.models.database import KnowledgeBase
from app.models import KnowledgeResult

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.fixture
def knowledge_service(mock_db):
    return HybridKnowledgeV7(db=mock_db)

# 2.2 Phase 1 驗證矩陣 - KnowledgeLayerV1 (Rule Matching)
class TestKnowledgeMatching:
    @pytest.mark.asyncio
    async def test_rule_match_exact(self, knowledge_service, mock_db):
        # Setup mock return value for exact match
        mock_row = MagicMock(spec=KnowledgeBase)
        mock_row.id = 1
        mock_row.question = "如何退貨"
        mock_row.answer = "請聯繫客服退貨"
        mock_row.keywords = ["退貨", "政策"]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_row]
        mock_db.execute.return_value = mock_result
        
        res_list = await knowledge_service._rule_match_list("如何退貨")
        assert len(res_list) == 1
        assert res_list[0].id == 1
        assert res_list[0].confidence == 0.95 # Exact match
        assert res_list[0].source == "rule"

    @pytest.mark.asyncio
    async def test_rule_match_keyword(self, knowledge_service, mock_db):
        # Setup mock return value for keyword match
        mock_row = MagicMock(spec=KnowledgeBase)
        mock_row.id = 2
        mock_row.question = "運費多少"
        mock_row.answer = "滿千免運"
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_row]
        mock_db.execute.return_value = mock_result
        
        res_list = await knowledge_service._rule_match_list("運費")
        assert len(res_list) == 1
        assert res_list[0].confidence == 0.7 # Keyword match

    @pytest.mark.asyncio
    async def test_no_match_escalation(self, knowledge_service, mock_db):
        # Setup mock return value for no match
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        
        res = await knowledge_service.query("隨便問問")
        assert res.id == -1
        assert res.source == "escalate"
        assert "轉接人工客服" in res.content

    def test_rrf_logic(self, knowledge_service):
        # Test RRF scaling and sorting
        res1 = KnowledgeResult(id=1, content="A", confidence=0.0, source="rule", knowledge_id=1)
        res2 = KnowledgeResult(id=2, content="B", confidence=0.0, source="rule", knowledge_id=2)
        
        # doc 1 is rank 1 in list 1, rank 2 in list 2
        # doc 2 is rank 2 in list 1, rank 1 in list 2
        fused = knowledge_service._reciprocal_rank_fusion([[res1, res2], [res2, res1]])
        assert len(fused) == 2
        assert fused[0].id in [1, 2]
        assert fused[0].confidence > 0
