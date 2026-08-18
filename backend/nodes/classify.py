"""VOC 분류 노드 — 유형 6종 + 우선순위 3단 판정 (스펙 §4.2).

LLM 실패/파싱 실패 시 기타/medium 폴백 — 사용자는 에러를 보지 않는다 (스펙 §4.5).
"""
import json
import re
from typing import Any, Dict, Optional

from backend.constants import CATEGORIES, PRIORITIES
from backend.llm.base import LLMProvider

CLASSIFY_PROMPT = """당신은 todo 앱 'tika'의 VOC(고객 소리) 분류 전문가입니다.

사용자 VOC를 다음 기준으로 분류합니다.

[유형 (category)]
- 사용법문의: 앱 사용법이나 기능에 대한 질문
- 버그제보: 오동작, 오류, 예상과 다른 동작에 대한 보고
- 기능요청: 새 기능이나 개선 요청
- 불만: 불만족스러운 감정 표현
- 칭찬: 칭찬, 긍정 피드백
- 기타: 어느 유형에도 속하지 않음

[우선순위 (priority)]
- high: 데이터 손실, 앱 사용 불가, 매우 심각한 불만
- medium: 기능 요청, 일반적인 불만, 판단이 애매한 경우
- low: 단순 질문, 칭찬, 가벼운 의견

[사용자 VOC]
{voc_text}

아래 JSON 형식만 출력하세요. 다른 설명은 금지합니다.
{{"category": "위 6종 중 하나", "priority": "low|medium|high 중 하나"}}"""

FALLBACK_CLASSIFICATION = {"category": "기타", "priority": "medium"}


def parse_classification(text: str) -> Dict[str, str]:
    """LLM 출력에서 분류 JSON 추출. 실패 시 기타/medium 폴백 (스펙 §4.5)."""
    match = re.search(r"\{[^{}]*\}", text or "", re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            data = None
        if (
            isinstance(data, dict)
            and data.get("category") in CATEGORIES
            and data.get("priority") in PRIORITIES
        ):
            return {"category": data["category"], "priority": data["priority"]}
    return dict(FALLBACK_CLASSIFICATION)


def make_classify_node(provider: Optional[LLMProvider]):
    def classify_node(state: Dict[str, Any]) -> Dict[str, Any]:
        voc_text = state["voc_text"]
        if provider is None:
            return {**FALLBACK_CLASSIFICATION, "error": "LLM provider 미설정 — 폴백 분류 사용"}
        try:
            raw = provider.generate(
                CLASSIFY_PROMPT.format(voc_text=voc_text), temperature=0.0
            )
        except Exception as exc:  # 우아한 열화 — 분류 실패가 전체를 죽이지 않게
            print(f"[classify] LLM 호출 실패, 폴백 분류 사용: {exc}")
            return {**FALLBACK_CLASSIFICATION, "error": f"classify 실패: {exc}"}
        return parse_classification(raw)

    return classify_node
