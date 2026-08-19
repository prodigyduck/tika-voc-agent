---
name: voc-pipeline
description: tika-agent 백엔드 파이프라인(LangGraph 노드/그래프/API) 구현 방법과 TDD 체크리스트.
---

# VOC 파이프라인 구현 방법

## 구조

- 그래프: `backend/agent.py` (조립만), 노드: `backend/nodes/` 파일당 하나
- 경로: classify → (route) → retrieve → answer → respond → save / escalate → respond → save
- 상태: `backend/state.py` AgentState (total=False, 점진적 채움)

## TDD 체크리스트

1. 테스트 먼저 작성 — LLM 노드는 `tests/fakes.py`의 `FakeProvider` 사용
2. 실패 확인 후 최소 구현 → 통과 확인 → 커밋
3. 실패 경로 테스트 필수: LLM 실패/근거 없음/DB 실패 → 모두 폴백 동작
4. 환각 방지 테스트 유지: 근거 없으면 `provider.calls == []`

## 규칙

- 노드 팩토리 패턴: `make_*_node(provider, ...)` — 의존성 주입
- 새 분류/경로 규칙은 `route_after_classify`에 반영 + 라우팅 테스트 갱신
- API 변경 시 `backend/schemas.py`와 프론트 `api.js` 동시 갱신
