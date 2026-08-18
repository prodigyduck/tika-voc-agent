"""에이전트 상태 — 파이프라인 진행에 따라 점진적으로 채워진다 (스펙 §4.3)."""
from typing import List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    voc_text: str           # 입력: 원본 VOC
    session_id: str         # 입력: 이력 추적 식별자
    category: str           # classify 결과 — CATEGORIES 중 하나
    priority: str           # classify 결과 — PRIORITIES 중 하나
    manual_chunks: List[dict]   # retrieve 결과 [{file, section, content}]
    answer: str             # answer 결과 (마크다운)
    answer_sources: List[str]   # 출처 ["03-ui-guide#할 일 삭제하기"]
    escalated: bool         # escalate 결과
    escalation_reason: str
    escalation_message: str  # 접수 안내 문구
    response: str           # respond 결과 (최종 마크다운)
    voc_id: int             # save 결과
    error: str              # 파이프라인 에러 (있으면)
