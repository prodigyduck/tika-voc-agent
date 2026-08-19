"""FastAPI 엔드포인트 테스트 (스펙 §6.1)."""
from fastapi.testclient import TestClient

from backend.main import create_app
from tests.fakes import FakeProvider

CLASSIFY_HOWTO = '{"category": "사용법문의", "priority": "low"}'
CLASSIFY_BUG = '{"category": "버그제보", "priority": "high"}'


def make_provider(responses):
    return FakeProvider(responses)


def make_app(provider, session_factory):
    """테스트용 앱 생성"""
    return create_app(provider=provider, session_factory=session_factory)


def test_chat_정상_답변_경로(db_session_factory):
    app = make_app(provider=make_provider([
        CLASSIFY_HOWTO,
        "완료됨 영역을 펼쳐 보세요.\n📖 출처: 03-ui-guide#완료된 할 일 보기",
    ]), session_factory=db_session_factory)
    client = TestClient(app)

    resp = client.post("/api/chat", json={"voc_text": "완료한 할 일이 안 보여요", "session_id": "s1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == "사용법문의"
    assert data["priority"] == "low"
    assert data["escalated"] is False
    assert data["voc_id"] is not None
    assert data["sources"]
    assert "📖 출처" in data["response"]


def test_chat_에스컬레이션_경로(db_session_factory):
    app = make_app(provider=make_provider([CLASSIFY_BUG, "접수했습니다."]), session_factory=db_session_factory)
    client = TestClient(app)

    resp = client.post("/api/chat", json={"voc_text": "앱이 꺼져요", "session_id": "s2"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["escalated"] is True


def test_chat_빈_텍스트_422(db_session_factory):
    app = make_app(provider=make_provider([]), session_factory=db_session_factory)
    client = TestClient(app)
    resp = client.post("/api/chat", json={"voc_text": "", "session_id": "s"})
    assert resp.status_code == 422


def test_llm_미설정시_503(monkeypatch, db_session_factory):
    from backend import config

    monkeypatch.setattr(config.settings, "llm_api_key", "")
    app = make_app(provider=None, session_factory=db_session_factory)
    client = TestClient(app)
    resp = client.post("/api/chat", json={"voc_text": "안녕", "session_id": "s"})
    assert resp.status_code == 503
    assert "LLM_API_KEY" in resp.json()["detail"]


def test_vocs_목록_필터(db_session_factory):
    provider = make_provider([
        CLASSIFY_HOWTO,
        "답변입니다.\n📖 출처: 03-ui-guide#완료된 할 일 보기",
        CLASSIFY_BUG,
        "접수했습니다.",
    ])
    app = make_app(provider=provider, session_factory=db_session_factory)
    client = TestClient(app)
    client.post("/api/chat", json={"voc_text": "완료한 할 일이 안 보여요", "session_id": "a"})
    client.post("/api/chat", json={"voc_text": "앱이 꺼져요", "session_id": "b"})

    all_vocs = client.get("/api/vocs").json()
    assert len(all_vocs) == 2

    bugs = client.get("/api/vocs", params={"category": "버그제보"}).json()
    assert len(bugs) == 1
    assert bugs[0]["category"] == "버그제보"

    escalated = client.get("/api/vocs", params={"escalated": "true"}).json()
    assert len(escalated) == 1


def test_voc_단건_조회_404(db_session_factory):
    app = make_app(provider=make_provider([]), session_factory=db_session_factory)
    client = TestClient(app)
    resp = client.get("/api/vocs/9999")
    assert resp.status_code == 404


def test_status_토글(db_session_factory):
    app = make_app(provider=make_provider([CLASSIFY_BUG, "접수했습니다."]), session_factory=db_session_factory)
    client = TestClient(app)
    voc_id = client.post("/api/chat", json={"voc_text": "앱이 꺼져요", "session_id": "s"}).json()["voc_id"]

    resolved = client.patch(f"/api/vocs/{voc_id}/status", json={"status": "resolved"})
    assert resolved.status_code == 200
    assert resolved.json()["escalation_status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None

    reopened = client.patch(f"/api/vocs/{voc_id}/status", json={"status": "open"})
    assert reopened.json()["escalation_status"] == "open"
    assert reopened.json()["resolved_at"] is None

    invalid = client.patch(f"/api/vocs/{voc_id}/status", json={"status": "확인중"})
    assert invalid.status_code == 422


def test_stats(db_session_factory):
    provider = make_provider([
        CLASSIFY_HOWTO,
        "답변입니다.\n📖 출처: 03-ui-guide#완료된 할 일 보기",
        CLASSIFY_BUG,
        "접수했습니다.",
    ])
    app = make_app(provider=provider, session_factory=db_session_factory)
    client = TestClient(app)
    client.post("/api/chat", json={"voc_text": "완료 안 보여요", "session_id": "a"})
    client.post("/api/chat", json={"voc_text": "꺼져요", "session_id": "b"})

    stats = client.get("/api/stats").json()
    assert stats["total"] == 2
    assert stats["by_category"]["사용법문의"] == 1
    assert stats["by_category"]["버그제보"] == 1
    assert stats["escalated_open"] == 1
    assert len(stats["by_day"]) == 7


def test_health(db_session_factory):
    app = make_app(provider=make_provider([]), session_factory=db_session_factory)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
