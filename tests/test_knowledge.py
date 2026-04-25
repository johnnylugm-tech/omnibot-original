from app.services.knowledge import KnowledgeLayerV1


def test_knowledge_layer():
    layer = KnowledgeLayerV1(db=None)

    # query method
    res = layer.query("test")
    assert res is not None
    assert res.content == "正在為您轉接人工客服，請稍候..."
    assert res.source == "escalate"
