from app.models.database import (
    Conversation,
    EscalationQueue,
    KnowledgeBase,
    Message,
    PlatformConfig,
    User,
    UserFeedback,
)


def test_model_imports():
    user = User(platform="test", platform_user_id="123")
    assert user.platform == "test"

    conv = Conversation(platform="test", status="active")
    assert conv.status == "active"

    msg = Message(role="user", content="hello")
    assert msg.role == "user"

    kb = KnowledgeBase(category="faq", question="q", answer="a")
    assert kb.category == "faq"

    config = PlatformConfig(platform="web", enabled=True)
    assert config.enabled is True

    eq = EscalationQueue(reason="test")
    assert eq.reason == "test"

    fb = UserFeedback(feedback="good")
    assert fb.feedback == "good"
