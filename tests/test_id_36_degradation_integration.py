"""
Atomic TDD Tests for ID #36: Degradation Integration
Focus: Integrating DegradationManager into the API webhook flow.
"""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_id_36_05_webhook_falls_back_to_rag_on_high_llm_latency():
    """GREEN: If LLM latency > 3s, webhook should skip Layer 3 (LLM) and use Layer 2 (RAG)"""  # noqa: E501
    from app.services.knowledge import KnowledgeResult

    with patch("app.api.routes.webhooks.HybridKnowledgeV7") as MockKnowledge:  # noqa: N806
        mock_instance = MockKnowledge.return_value
        # Mock result for the query, ensure it is awaitable
        mock_instance.query = AsyncMock(
            return_value=KnowledgeResult(
                id=1, content="RAG response", source="rag", confidence=0.9
            )
        )

        with patch("app.api.degradation_manager") as mock_deg_manager:
            mock_deg_manager.get_allowed_layers.return_value = {
                "rule": True,
                "rag": True,
                "llm": False,
            }

            payload = {
                "message": {"from": {"id": 12345}, "text": "Tell me about courses"}
            }

            with (
                patch(
                    "app.api.get_or_create_user", new_callable=AsyncMock
                ) as mock_user,
                patch(
                    "app.api.get_active_conversation", new_callable=AsyncMock
                ) as mock_conv,
                patch(
                    "app.api.get_emotion_tracker", new_callable=AsyncMock
                ) as mock_emo,
                patch("app.api.worker", new_callable=AsyncMock),
            ):
                mock_user.return_value = MagicMock(
                    platform="telegram", platform_user_id="12345", unified_user_id="u1"
                )
                mock_conv.return_value = MagicMock(
                    id=1,
                    unified_user_id="u1",
                    platform="telegram",
                    status="active",
                    dst_state={},
                    resolution_cost=0.0,
                    response_time_ms=0,
                )
                mock_emo.return_value = MagicMock()
                mock_emo.return_value.should_escalate.return_value = False

                response = client.post("/api/v1/webhook/telegram", json=payload)

                assert response.status_code == 200
                assert response.json()["data"]["response"] == "RAG response"

                # Verify HybridKnowledgeV7 was initialized with llm_client=False
                MockKnowledge.assert_called_with(ANY, llm_client=False)
