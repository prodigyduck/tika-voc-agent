# tika-agent 설계 문서

- **날짜**: 2026-08-18
- **상태**: 승인됨 (브레인스토밍 5섹션 발표 완료)
- **참조 프로젝트**: `~/git/tpssAgent` (골격/하네스 패턴), `~/git/todoapp-vue-spring` (tika 앱), `~/git/vocClaasifier` (VOC 분류 사례)

---

## 1. 개요

**tika-agent**는 todo 앱 **tika**(`todoapp-vue-spring`, Vue3 + Spring Boot, Things 3 스타일)의 사용자 VOC(Voice of Customer)를 처리하는 LLM 에이전트 시스템이다.

사용자가 채팅창에 입력한 VOC를 받아 **분류 → 메뉴얼 기반 답변 또는 에스컬레이션 → 이력 저장**의 전체 파이프라인을 수행하고, 담당자는 대시보드에서 통계와 에스컬레이션을 관리한다.

### 목표

1. VOC 채팅 입력 → 자동 분류(6유형) → 메뉴얼 근거 답변 or 사람 에스컬레이션
2. tika 실제 코드 기반의 **사용자 메뉴얼** 작성 (에이전트 답변의 근거 원천)
3. tpssAgent 스타일 **개발 하네스**(.claude/agents + skills)로 계획·구현·검증 구동
4. MVP 완료 기준: **전체 흐름 동작** (챗 → 처리 → 대시보드 확인)

### 핵심 원칙

- **환각 방지**: 메뉴얼에 근거 없는 답변을 하지 않는다. 근거가 없으면 정직하게 안내하고 에스컬레이션한다.
- **우아한 열화**: LLM/검색/저장 어느 단계가 실패해도 사용자는 정상 흐름의 응답을 받는다.
- **YAGNI**: 임베딩 RAG, 인증, 외부 알림은 MVP 범위 밖. 단, 교체 가능한 인터페이스 뒤에 숨긴다.

---

## 2. 확정된 결정 사항

| 항목 | 결정 | 비고 |
|------|------|------|
| 대상 앱 | tika = `todoapp-vue-spring` | Vue3 + Spring Boot |
| VOC 입력 | tpssAgent 스타일 채팅 UI | `POST /api/chat` |
| 처리 범위 | 전체 파이프라인 (분류+답변+에스컬레이션+요약) | LangGraph 조건부 그래프 |
| 메뉴얼 | tika 코드 기반 직접 작성 (마크다운 5종) | `manual/` 폴더, RAG 소스 |
| 하네스 | tpssAgent 스타일 | agents 4 + skills 4 |
| 스택 | FastAPI + LangGraph + Vue3 + Vite | tpssAgent 골격 재사용 |
| LLM | **교체 가능 추상화** | OpenAI 호환 기본, `.env`로 base_url/model 지정 |
| RAG 방식 | 간단 검색 (임베딩 없음) | `search()` 인터페이스로 벡터 교체 여지 |
| 에스컬레이션 알림 | 대시보드 플래그 | 외부 채널 연동은 MVP 밖 |
| 저장 | PostgreSQL + SQLAlchemy | tpssAgent 동일 패턴 |
| MVP 기준 | 전체 흐름 동작 | 챗 → 분류/답변/에스컬레이션 → 대시보드 |

### 접근 방식 (하이브리드)

tpssAgent의 **골격만** 재사용하고(FastAPI 구조, SQLAlchemy 패턴, LLMProvider ABC, Vue3 챗 UI 패턴, 하네스 관례), **에이전트 그래프는 VOC 전용 조건부 그래프**로 신규 설계한다. 안티패턴 2종(순차 고정 파이프라인 강제, mock 데이터 남용)은 배제한다.

---

## 3. 전체 아키텍처 & 폴더 구조

```
tika-agent/
├── CLAUDE.md                  # 프로젝트 가이드 (tpssAgent CLAUDE.md 스타일)
├── README.md
├── .env.example               # LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, DATABASE_URL
├── docker-compose.yml         # PostgreSQL만 (앱은 로컬 실행)
├── requirements.txt
│
├── manual/                    # tika 사용자 메뉴얼 (RAG 소스)
│   ├── index.md               # 전체 색인 (섹션 목록 + 요약)
│   ├── 01-getting-started.md  # 시작하기
│   ├── 02-managing-todos.md   # 할 일 관리
│   ├── 03-ui-guide.md         # 화면 구성/조작법
│   ├── 04-troubleshooting.md  # 문제 해결 (증상→원인→해결)
│   └── 05-faq.md              # FAQ
│
├── backend/
│   ├── main.py                # FastAPI 앱 + 라우팅
│   ├── config.py              # .env 설정 로드
│   ├── database.py            # SQLAlchemy 엔진/세션
│   ├── models.py              # VocRecord ORM
│   ├── schemas.py             # Pydantic 요청/응답
│   ├── agent.py               # LangGraph 그래프 정의 (노드 연결만)
│   ├── state.py               # AgentState TypedDict
│   ├── nodes/                 # 그래프 노드 (파일당 하나)
│   │   ├── classify.py
│   │   ├── retrieve.py
│   │   ├── answer.py
│   │   ├── escalate.py
│   │   ├── respond.py
│   │   └── save.py
│   ├── manual_retrieval.py    # 메뉴얼 로드 + 간단 검색
│   └── llm/                   # tpssAgent 패턴 재사용
│       ├── base.py            # LLMProvider ABC
│       ├── openai_compat.py   # OpenAI 호환 기본 구현 (실제 호출)
│       └── factory.py         # .env 기반 provider 생성
│
├── frontend/                  # Vue3 + Vite
│   └── src/
│       ├── views/             # ChatView, DashboardView
│       ├── components/        # 챗 버블, 통계 카드/차트, 에스컬레이션 목록
│       └── services/api.js
│
├── tests/                     # pytest
│
└── .claude/                   # 개발 하네스
    ├── agents/                # manual-writer, backend-engineer, frontend-engineer, qa-engineer
    └── skills/                # tika-orchestrator, manual-authoring, voc-pipeline, dashboard-ui
```

### tpssAgent와 의도적으로 다른 점

1. **노드를 `nodes/` 패키지로 분리** — tpssAgent는 `agent.py`에 노드가 몰려 있음. VOC 그래프는 조건부 분기가 있어 파일 분리가 유지보수에 유리.
2. **로그 파일을 남기지 않음** — tpssAgent의 `backend_*.log` 난립은 교훈. 콘솔 출력만.
3. **mock 데이터 없음** — 메뉴얼이 곧 데이터. mock RAG/mock DB 불필요.
4. **기본 LLM 구현이 실제 호출** — tpssAgent는 내부 LLM mock이 기본. tika-agent는 OpenAI 호환 실구현이 기본.

### 데이터 흐름

```
[챗 입력] → POST /api/chat → LangGraph 그래프 실행
  → classify → (route) → retrieve → answer   (답변 경로)
  → classify → (route) → escalate            (에스컬레이션 경로)
  → respond → save(PostgreSQL) → [응답 반환]

[대시보드] → GET /api/vocs, GET /api/stats → 목록/통계/상태 토글
```

---

## 4. 에이전트 그래프 & 데이터 모델

### 4.1 LangGraph 그래프

```
START
  ↓
classify ── VOC를 6개 유형으로 분류 + 우선순위 판정
  ↓
route (conditional edge)
  ├─ [답변 경로] 사용법문의 / 칭찬 / 경미한 불만(low)
  │     ↓
  │   retrieve ── 메뉴얼 간단 검색 (상위 3 청크)
  │     ↓
  │   answer ── 근거 답변 생성 + 출처 표기
  │
  └─ [에스컬레이션 경로] 버그제보 / 기능요청 / 중대 불만(high,medium) / 기타
        ↓
      escalate ── 접수 안내 문구 + 플래그
  ↓
respond ── 최종 마크다운 응답 조립
  ↓
save ── VOC 이력 DB 저장
  ↓
END
```

### 4.2 분류 체계

| 유형 | 라우팅 | 우선순위 |
|------|--------|---------|
| 사용법문의 | 답변 경로 | low~medium |
| 버그제보 | 에스컬레이션 | high |
| 기능요청 | 에스컬레이션 | medium |
| 불만 | 우선순위로 분기 | low→답변 / medium·high→에스컬레이션 |
| 칭찬 | 답변 경로 | low |
| 기타 | 에스컬레이션 | medium |

- classify 노드는 LLM에 유형+우선순위를 **구조화 출력**(JSON)으로 요청한다.
- 분류 실패(LLM 에러, 출력 파싱 실패) → `기타 + medium` 폴백 → 에스컬레이션 경로. 사용자는 에러를 보지 않는다.

### 4.3 AgentState (`state.py`)

tpssAgent 패턴 — 파이프라인 진행에 따라 점진적 채움, 모든 필드 선택(`total=False`):

```python
class AgentState(TypedDict, total=False):
    voc_text: str          # 입력: 원본 VOC
    session_id: str        # 입력: 대화 세션
    category: str          # classify 결과 (6유형)
    priority: str          # classify 결과 (low/medium/high)
    manual_chunks: list    # retrieve 결과 [{file, section, content}]
    answer: str            # answer 결과 (마크다운)
    answer_sources: list   # 출처 ["03-ui-guide#할-일-삭제하기"]
    escalated: bool        # escalate 결과
    escalation_reason: str # 에스컬레이션 사유
    response: str          # respond 결과 (최종 마크다운)
    voc_id: int            # save 결과 (저장된 레코드 ID)
    error: str             # 파이프라인 에러 (있으면)
```

### 4.4 DB 모델 (`models.py`)

단일 테이블. MVP는 사용자/인증 없음(대시보드 열린 접근 가정).

```python
class VocRecord(Base):
    __tablename__ = "voc_records"
    id: int (PK)
    session_id: str (인덱스)
    voc_text: Text
    category: str          # 6유형
    priority: str          # low/medium/high
    answer: Text | null    # 생성된 답변 (에스컬레이션 경로는 null)
    answer_sources: JSON | null
    escalated: bool (기본 false)
    escalation_reason: str | null
    escalation_status: str # open / resolved (담당자가 대시보드에서 변경)
    created_at: datetime (기본 now)
    resolved_at: datetime | null
```

### 4.5 에러 처리 (우아한 열화)

| 실패 지점 | 동작 |
|-----------|------|
| LLM 호출 실패(classify) | `기타 + medium` 폴백 → 에스컬레이션 경로. `error` 필드 기록 |
| 메뉴얼 검색 결과 없음 | answer가 지어내지 않음. "메뉴얼에 해당 내용이 없다" 안내 + 자동 에스컬레이션 |
| LLM 호출 실패(answer/escalate) | 정적 폴백 문구로 응답(접수 완료 안내) + 에스컬레이션 |
| save(DB) 실패 | 응답 반환은 그대로, 에러만 로깅. `voc_id` 없음 |

---

## 5. 메뉴얼 설계

### 5.1 문서 5종 (모두 tika 실제 코드 기반)

| 파일 | 내용 | 코드 근거 |
|------|------|-----------|
| `01-getting-started.md` | tika 소개, 접속, 첫 할 일 만들기 | README, `TodoController` |
| `02-managing-todos.md` | 생성 / 인라인 수정 / 삭제 / 완료 토글 | `TodoController`, `TodoService` CRUD |
| `03-ui-guide.md` | Inbox 화면, 원형 체크박스, "+ New To-Do", hover 수정·삭제 버튼, 완료 항목 취소선 | `TodoList.vue` |
| `04-troubleshooting.md` | 증상 → 원인 → 해결 구조의 문제 해결 문서 | 코드 기반 추론 + 일반적 증상 |
| `05-faq.md` | 자주 묻는 질문 | 전체 문서 통합 |

독자는 **tika 일반 사용자**. 언어는 한국어.

### 5.2 구조 규칙 — 검색 단위 = `##` 섹션

문서 구조가 곧 시스템 사양이다.

- 각 `##` 섹션은 **자기완결적**: 제목만 봐도 내용 파악 가능, 다른 섹션 의존 금지
- `04-troubleshooting.md`의 섹션은 **증상/원인/해결** 3단 구조 고정
- `index.md`에 전체 섹션 목록 + 한 줄 요약 유지 (사람용 색인 + retrieve 참조)

```markdown
## 할 일이 저장되지 않아요
**증상**: 저장을 눌러도 목록에 나타나지 않는다
**원인**: ...
**해결**: 1. ... 2. ...
```

### 5.3 간단 검색 (`manual_retrieval.py`)

```
search(voc_text: str, category: str) -> list[ManualChunk]
```

1. 시작 시 `manual/*.md` 로드 → `##` 단위 청크 분해 → 메모리 캐시
2. 점수 = 제목 키워드 매칭(고가중) + 본문 키워드 출현 빈도
3. 분류 유형별 파일 가중치: 사용법문의·칭찬 → `01~03` 우선 / 불만 → `04~05` 우선 (버그제보는 에스컬레이션 경로라 검색하지 않음)
4. 상위 3개 청크 + 출처 메타데이터(`파일명#섹션제목`) 반환

임베딩 없이 시작하되 `search()` 인터페이스 뒤에 숨겨 벡터 검색 구현체로 교체 가능(전략 패턴).

### 5.4 답변 출처 표기

answer 노드는 답변 말미에 항상 출처를 붙인다:

> 할 일을 지우려면 항목에 마우스를 올린 뒤 오른쪽 삭제 버튼을 누르세요.
> 📖 출처: 03-ui-guide#할-일-삭제하기

---

## 6. API & 프론트엔드

### 6.1 API

| Method | Endpoint | 설명 |
|--------|----------|------|
| `POST` | `/api/chat` | VOC 처리 `{voc_text, session_id}` → 그래프 실행 결과 |
| `GET` | `/api/vocs` | VOC 목록. `?category=&escalated=&status=` 필터 |
| `GET` | `/api/vocs/{id}` | 단건 상세 |
| `PATCH` | `/api/vocs/{id}/status` | 에스컬레이션 상태 변경(`open`↔`resolved`). 담당자 액션 |
| `GET` | `/api/stats` | 유형별 분포, 에스컬레이션 현황, 일별 추이 |
| `GET` | `/health` | 헬스체크 (DB + LLM 설정 상태) |

`POST /api/chat` 응답:

```json
{
  "response": "할 일을 지우려면 ...\n📖 출처: 03-ui-guide#할-일-삭제하기",
  "category": "사용법문의",
  "priority": "low",
  "escalated": false,
  "sources": ["03-ui-guide#할-일-삭제하기"],
  "voc_id": 42,
  "session_id": "abc123"
}
```

에러: LLM 미설정 → `503` + 설정 안내. 그래프 내부 에러는 우아한 열화로 기본 응답(§4.5). 개발 모드 CORS 전체 허용(tpssAgent 동일).

### 6.2 프론트엔드 (Vue3 + Vite)

**ChatView (`/`)** — tpssAgent 챗 UI 패턴
- 챗 버블 + 타이핑 인디케이터 + 프리셋 질문 칩 (예: "할 일이 저장되지 않아요")
- 답변에 분류 배지(유형별 색상) + 출처 링크 + 에스컬레이션 ⚠️ 표시
- tpssAgent 커스텀 마크다운 파서(테이블/리스트/볼드) 재사용
- 백엔드 미가동 시 폴백 UI

**DashboardView (`/dashboard`)**
- 통계 카드: 총 VOC / 유형별 분포 / 미해결 에스컬레이션 수
- 유형별 분포 차트 (tpssAgent `charts/BaseChart.vue` 패턴 재사용)
- 에스컬레이션 목록 테이블 — 상태 토글 버튼(`open`→`resolved`)
- VOC 이력 목록 — 유형/상태 필터

상단 네비로 두 뷰 전환.

### 6.3 LLM 교체 가능 추상화

```bash
# .env
LLM_PROVIDER=openai_compat                  # 기본값 (현재 유일 구현)
LLM_BASE_URL=https://api.openai.com/v1      # 어떤 OpenAI 호환 서비스로든 교체
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

- `llm/base.py`: tpssAgent의 `LLMProvider` ABC 재사용 (`generate(prompt, **kwargs) -> str` + `name`)
- `llm/openai_compat.py`: OpenAI 호환 HTTP 호출 구현 (기본)
- `llm/factory.py`: `.env` 읽어 provider 생성. 미설정 시 `503` 안내
- 새 provider 추가 = ABC 구현체 하나 추가 + `.env` 변경 (tpssAgent와 동일한 확장점)

---

## 7. 개발 하네스

### 7.1 구성 (tpssAgent 패턴: agents = WHO/WHAT, skills = HOW)

**에이전트 (`.claude/agents/`)**

| 에이전트 | 책임 |
|----------|------|
| `manual-writer` | tika 코드 분석 → 메뉴얼 작성. 구조 규칙 준수 |
| `backend-engineer` | LLM 추상화 → 검색 → 그래프 → API 구현 |
| `frontend-engineer` | ChatView + DashboardView 구현 |
| `qa-engineer` | 품질 게이트: 테스트 통과 + 전체 흐름 검증 |

**스킬 (`.claude/skills/`)**

| 스킬 | 내용 |
|------|------|
| `tika-orchestrator` | 오케스트레이션: 단계 순서, 게이트 판정, 병렬화 결정 |
| `manual-authoring` | 메뉴얼 작성 방법 (구조 규칙, 코드 근거 수집, 검증 체크리스트) |
| `voc-pipeline` | LangGraph 노드/그래프 구현 방법 + TDD 체크리스트 |
| `dashboard-ui` | 프론트 구현 방법 (tpssAgent 패턴 재사용 지침) |

### 7.2 구현 순서 (의존 그래프)

```
① 메뉴얼 작성 (manual-writer)      ①' LLM 추상화 (backend-engineer)
        └──────── 병렬 진행 가능 ────────┘
                    ↓
② manual_retrieval (메뉴얼 완성 후)
        ↓
③ LangGraph 그래프 (classify → route → answer/escalate → respond → save)
        ↓
④ API 확정 시점부터 프론트 병렬 착수 가능
        ↓
⑤ 프론트엔드 (ChatView → DashboardView)
        ↓
⑥ qa-engineer 게이트 → E2E 검증 → MVP 완성
```

각 단계 완료 시 qa-engineer 게이트 통과 → 커밋.

### 7.3 CLAUDE.md

tpssAgent 스타일 — 프로젝트 개요, 개발 명령, 아키텍처 요약, **하네스 트리거 규칙**(어떤 요청에 `tika-orchestrator`를 쓰는지), 변경 이력 표.

---

## 8. 테스트 전략

| 계층 | 방법 |
|------|------|
| 단위 (노드) | `FakeProvider`(고정 응답 mock)로 classify/answer/route 전 경로 — LLM 없이 테스트 |
| manual_retrieval | 실제 메뉴얼 파일 대상: 대표 VOC가 의도한 섹션을 찾는지 검증 |
| 환각 방지 | 메뉴얼에 답 없는 VOC → 답변 생성 안 함 + 에스컬레이션 확인 (핵심 품질 속성) |
| API | FastAPI TestClient (chat/vocs/stats/status) |
| 메뉴얼 린트 | 구조 규칙 스크립트 검증: `##` 자기완결성, troubleshooting 3단 구조 |
| E2E | 실제 LLM으로 대표 VOC 5개 이상 처리 → 분류/답변/출처 수동 확인 (qa-engineer 체크리스트) |

커버리지: pytest-cov, 백엔드 위주.

---

## 9. MVP 완료 기준

다음 전체 흐름이 동작하면 MVP 완성:

1. 챗에서 VOC 입력 → 분류 배지와 함께 답변 or 에스컬레이션 안내 표시
2. 사용법문의 VOC → 메뉴얼 근거 답변 + 출처 표기
3. 버그제보 VOC → 에스컬레이션 플래그 저장 + 접수 안내
4. 메뉴얼에 없는 VOC → 지어내지 않고 "없음" 안내 + 에스컬레이션
5. 대시보드에서 VOC 목록/통계 확인, 에스컬레이션 `open`→`resolved` 처리
6. 백엔드 테스트 전체 통과

## 10. 범위 밖 (Out of Scope)

- 임베딩/벡터 검색 RAG (인터페이스만 확보)
- 외부 알림 채널 (이메일/슬랙/JIRA)
- 사용자 인증/권한 (대시보드 열린 접근)
- 다중 턴 대화 (1 VOC = 1 처리, 세션은 이력 추적 식별자로만 사용)
- VOC 대량 일괄 처리/스케줄러
