"""judge 모듈 테스트 (스펙 2026-08-21 §4·§9)."""
from backend.judge import build_judge_prompt, iter_judge_pending, parse_judge, run_judge, should_judge
from backend.models import VocRecord
from tests.fakes import FakeProvider

VALID = '{"completeness": 4, "accuracy": 5, "fluency": 5, "cause": "재료부족", "reason": "복구 절차가 출처에 없음"}'


def test_parse_유효_json():
    parsed = parse_judge("채점 결과입니다.\n" + VALID)
    assert parsed == {"completeness": 4, "accuracy": 5, "fluency": 5, "cause": "재료부족", "reason": "복구 절차가 출처에 없음"}


def test_parse_무효_json은_none():
    assert parse_judge("JSON 아님") is None
    assert parse_judge('{"completeness": 4') is None


def test_parse_점수_경계_검증():
    base = '{"completeness": %s, "accuracy": 5, "fluency": 5, "cause": "해당없음", "reason": ""}'
    assert parse_judge(base % 6) is None   # 5 초과
    assert parse_judge(base % 0) is None   # 1 미만
    assert parse_judge(base % '"4"') is None  # 정수 아님
    assert parse_judge(base % 1) is not None  # 경계값 1 허용
    assert parse_judge(base % 5) is not None  # 경계값 5 허용


def test_parse_cause_화이트리스트():
    bad = '{"completeness": 4, "accuracy": 5, "fluency": 5, "cause": "모름", "reason": ""}'
    assert parse_judge(bad) is None


def test_parse_reason_200자_절단():
    long_reason = "가" * 300
    parsed = parse_judge(f'{{"completeness": 3, "accuracy": 4, "fluency": 5, "cause": "과정오류", "reason": "{long_reason}"}}')
    assert len(parsed["reason"]) == 200


def test_parse_reason_빈값은_none():
    parsed = parse_judge('{"completeness": 5, "accuracy": 5, "fluency": 5, "cause": "해당없음", "reason": ""}')
    assert parsed["reason"] is None


def _add_record(db, **kw):
    defaults = dict(
        session_id="j", voc_text="티켓을 어떻게 삭제하나요?", category="사용법문의", priority="low",
        answer="삭제 버튼으로 지울 수 있습니다.", answer_sources=["02-managing-todos#티켓 삭제하기"],
    )
    defaults.update(kw)
    record = VocRecord(**defaults)
    db.add(record)
    db.commit()
    return record


def test_should_judge_출처있는_건만():
    class R:
        answer, answer_sources = "답변", ["02-managing-todos#티켓 삭제하기"]
    class E:
        answer, answer_sources = "접수했습니다.", None
    assert should_judge(R()) is True
    assert should_judge(E()) is False


def test_run_judge_레코드_저장(db_session_factory):
    db = db_session_factory()
    record = _add_record(db)
    # 세션을 닫지 않고 유지 - run_judge가 별도 세션을 생성하므로 문제없음

    run_judge(record.id, FakeProvider([VALID]), db_session_factory)

    db = db_session_factory()
    found = db.query(VocRecord).filter(VocRecord.id == record.id).first()
    db.close()
    assert found.judge_scores == {"completeness": 4, "accuracy": 5, "fluency": 5}
    assert found.judge_total == 14
    assert found.judge_cause == "재료부족"
    assert found.judge_reason == "복구 절차가 출처에 없음"
    assert found.judged_at is not None


def test_run_judge_provider_실패는_미채점_유지(db_session_factory):
    db = db_session_factory()
    record = _add_record(db)
    # 세션을 닫지 않고 유지

    run_judge(record.id, FakeProvider([]), db_session_factory)  # generate가 예외 — 잡아야 함

    db = db_session_factory()
    found = db.query(VocRecord).filter(VocRecord.id == record.id).first()
    db.close()
    assert found.judge_total is None


def test_run_judge_에스컬레이션은_llm_호출_없이_스킵(db_session_factory):
    db = db_session_factory()
    record = _add_record(db, answer="접수했습니다.", answer_sources=None, escalated=True)
    # 세션을 닫지 않고 유지

    run_judge(record.id, FakeProvider([]), db_session_factory)  # 응답 소진 예외 없이 통과

    db = db_session_factory()
    found = db.query(VocRecord).filter(VocRecord.id == record.id).first()
    db.close()
    assert found.judge_total is None


def test_build_judge_prompt_재료_포함():
    class R:
        voc_text, answer = "티켓을 어떻게 삭제하나요?", "삭제 버튼으로 지울 수 있습니다."
        answer_sources = ["02-managing-todos#티켓 삭제하기"]
    prompt = build_judge_prompt(R())
    assert "티켓을 어떻게 삭제하나요?" in prompt
    assert "삭제 버튼으로 지울 수 있습니다." in prompt
    assert "--- 02-managing-todos#티켓 삭제하기 ---" in prompt


def test_iter_judge_pending_미채점_대상만(db_session_factory):
    from backend.database import SessionLocal  # noqa: F401 — fixture가 엔진 초기화
    db = db_session_factory()
    _add_record(db, judge_scores={"completeness": 5, "accuracy": 5, "fluency": 5}, judge_total=15, judge_cause="해당없음")  # 이미 채점
    _add_record(db, session_id="p2")  # 미채점 대상
    _add_record(db, session_id="p3", answer="접수했습니다.", answer_sources=None, escalated=True)  # 대상 아님
    pending = iter_judge_pending(db)
    db.close()
    assert len(pending) == 1
