from backend.models import VocRecord


def test_voc_record_생성_및_기본값(db_session):
    record = VocRecord(
        session_id="s1",
        voc_text="할 일이 저장되지 않아요",
        category="버그제보",
        priority="high",
    )
    db_session.add(record)
    db_session.commit()

    found = db_session.query(VocRecord).filter_by(session_id="s1").first()
    assert found is not None
    assert found.category == "버그제보"
    assert found.priority == "high"
    assert found.escalated is False          # 기본값
    assert found.escalation_status == "open"  # 기본값
    assert found.resolved_at is None
    assert found.created_at is not None


def test_상수_고정값():
    from backend.constants import CATEGORIES, PRIORITIES, ESCALATION_STATUSES
    assert CATEGORIES == ["사용법문의", "버그제보", "기능요청", "불만", "칭찬", "기타"]
    assert PRIORITIES == ["low", "medium", "high"]
    assert ESCALATION_STATUSES == ["open", "resolved"]


def test_설정_기본값_로드():
    from backend.config import settings
    assert settings.llm_provider == "openai_compat"
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.database_url == "sqlite://"  # conftest가 덮어쓴 값
