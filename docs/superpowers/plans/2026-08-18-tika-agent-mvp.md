# tika-agent MVP 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** tika(todo 앱) 사용자 VOC를 채팅으로 받아 분류 → 메뉴얼 근거 답변/에스컬레이션 → 이력 저장 → 대시보드 확인까지 동작하는 VOC 에이전트 MVP를 완성한다.

**Architecture:** tpssAgent의 골격(FastAPI + LangGraph + Vue3 + SQLAlchemy)을 재사용하되, LangGraph 그래프는 VOC 전용 조건부 그래프(classify → route → retrieve/answer 또는 escalate → respond → save)로 신규 설계한다. 메뉴얼(`manual/*.md`)이 답변의 유일한 근거 원천이며, 임베딩 없는 간단 검색으로 조회한다.

**Tech Stack:** Python 3.9+ / FastAPI / LangGraph / SQLAlchemy 2.x / PostgreSQL / OpenAI 호환 API / Vue 3 + Vite / pytest + Vitest

**Spec:** `docs/superpowers/specs/2026-08-18-tika-agent-design.md`

## Global Constraints

- 모든 주석·프롬프트·UI 문구·문서는 **한국어**
- Python 3.9 호환 문법 (`X | None` 대신 `Optional[X]`, `list[X]` 대신 `List[X]`)
- 분류 유형 고정 6종: `사용법문의`, `버그제보`, `기능요청`, `불만`, `칭찬`, `기타`
- 우선순위 고정 3단: `low`, `medium`, `high`
- 에스컬레이션 상태 고정: `open`, `resolved`
- 메뉴얼 검색 결과는 항상 **상위 3개** 청크
- 출처 표기 포맷: `{파일명(.md 제외)}#{섹션제목}` (예: `03-ui-guide#할 일 삭제하기`)
- 로그 파일 생성 금지 — `print`/콘솔 로깅만 (tpssAgent의 `*.log` 난립 금지)
- mock 데이터 금지 — 단, 테스트 더블(`FakeProvider`, 테스트 DB)은 허용
- 임베딩/벡터 DB·외부 알림·인증·다중 턴 대화는 MVP 범위 밖
- LLM은 반드시 `backend/llm/base.py`의 `LLMProvider` ABC 뒤에서만 호출
- 그래프 노드는 `backend/nodes/`에 파일당 하나
- 프론트는 Vue3 Composition API(`<script setup>`)만 사용
- 커밋 메시지: conventional commits (`feat:`, `docs:`, `test:`, `chore:` 등), 한국어 제목, 끝에 `Co-Authored-By: Claude <noreply@anthropic.com>`
- 작업 디렉터리: `/Users/prodigyduck/git/tika-agent` (이미 git 저장소, main 브랜치)
- 참조 프로젝트(읽기 전용): `~/git/tpssAgent`(골격), `~/git/todoapp-vue-spring`(tika 앱)

---

### Task 1: 프로젝트 기반 — 설정·DB·모델

**Files:**
- Create: `.gitignore`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.env.example`, `docker-compose.yml`
- Create: `backend/__init__.py`(빈 파일), `backend/config.py`, `backend/constants.py`, `backend/database.py`, `backend/models.py`
- Create: `tests/__init__.py`(빈 파일), `tests/conftest.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces:
  - `settings` (backend/config.py): `.database_url: str`, `.llm_provider: str`, `.llm_base_url: str`, `.llm_api_key: str`, `.llm_model: str`
  - `CATEGORIES: List[str]`, `PRIORITIES: List[str]`, `ESCALATION_STATUSES: List[str]` (backend/constants.py)
  - `Base`, `engine`, `SessionLocal`, `init_database()`, `get_db_context()` (backend/database.py)
  - `VocRecord` (backend/models.py) — 컬럼: id, session_id, voc_text, category, priority, answer, answer_sources, escalated, escalation_reason, escalation_status, created_at, resolved_at
  - pytest fixtures `db_session`, `db_session_factory` (tests/conftest.py)

- [ ] **Step 1: 파이썬 가상환경 및 프로젝트 파일 생성**

```bash
cd /Users/prodigyduck/git/tika-agent
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
venv/
.env
.pytest_cache/
htmlcov/
.coverage
node_modules/
dist/
*.log
```

`requirements.txt`:
```
fastapi>=0.110,<1.0
uvicorn[standard]>=0.29
langgraph>=0.2,<0.4
sqlalchemy>=2.0,<3.0
psycopg2-binary>=2.9
openai>=1.30,<2.0
python-dotenv>=1.0
pydantic>=2.6,<3.0
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8.0
pytest-cov>=5.0
httpx>=0.27
```

`pytest.ini`:
```
[pytest]
testpaths = tests
addopts = -q
```

`.env.example`:
```
# 데이터베이스 (docker-compose up -d postgres 실행 시 기본값과 일치)
DATABASE_URL=postgresql://tika:tika@localhost:5432/tika_agent

# LLM — OpenAI 호환 API (LLM_BASE_URL을 바꾸면 다른 호환 서비스로 교체)
LLM_PROVIDER=openai_compat
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=
LLM_MODEL=gpt-4o-mini
```

`docker-compose.yml`:
```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: tika
      POSTGRES_PASSWORD: tika
      POSTGRES_DB: tika_agent
    ports:
      - "5432:5432"
    volumes:
      - tika_pgdata:/var/lib/postgresql/data
volumes:
  tika_pgdata:
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/conftest.py` — 백엔드 import보다 먼저 환경변수 세팅(필수 순서):
```python
import os

# 백엔드 임포트 전에 테스트 환경 변수 설정 — DB를 SQLite 인메모리로 강제
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["LLM_API_KEY"] = "test-key"

import pytest

from backend.database import Base, SessionLocal, engine


@pytest.fixture()
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def db_session_factory():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal
```

`tests/test_database.py`:
```python
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
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

```bash
pip install -r requirements-dev.txt
pytest tests/test_database.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backend'` (또는 config/constants/models 없음)

- [ ] **Step 4: 최소 구현**

`backend/__init__.py`와 `tests/__init__.py`는 빈 파일로 생성.

`backend/config.py`:
```python
"""tika-agent 설정 — .env 기반 (스펙 §6.3)."""
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """환경 변수를 읽어 보관. 테스트에서는 속성을 직접 덮어쓸 수 있다."""

    def __init__(self) -> None:
        self.database_url: str = os.getenv(
            "DATABASE_URL", "postgresql://tika:tika@localhost:5432/tika_agent"
        )
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "openai_compat")
        self.llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.llm_api_key: str = os.getenv("LLM_API_KEY", "")
        self.llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")


settings = Settings()
```

`backend/constants.py`:
```python
"""도메인 상수 — 분류 체계 (스펙 §4.2)."""

CATEGORIES = ["사용법문의", "버그제보", "기능요청", "불만", "칭찬", "기타"]
PRIORITIES = ["low", "medium", "high"]
ESCALATION_STATUSES = ["open", "resolved"]
```

`backend/database.py`:
```python
"""SQLAlchemy 엔진/세션 — 테스트는 SQLite 인메모리로 대체 가능."""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import settings

Base = declarative_base()


def _create_engine(url: str):
    if url.startswith("sqlite"):
        # 인메모리 SQLite는 커넥션 공유가 필요 (스레드 간 사용)
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url, pool_pre_ping=True)


engine = _create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_database() -> None:
    """모든 테이블 생성. 모델 임포트로 메타데이터 등록을 보장한다."""
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db_context():
    """커밋/롤백/종료를 책임지는 세션 컨텍스트."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

`backend/models.py`:
```python
"""VOC 이력 ORM 모델 (스펙 §4.4)."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text

from backend.database import Base


class VocRecord(Base):
    __tablename__ = "voc_records"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), index=True, nullable=False)
    voc_text = Column(Text, nullable=False)
    category = Column(String(20), nullable=False, default="기타")
    priority = Column(String(10), nullable=False, default="medium")
    answer = Column(Text, nullable=True)
    answer_sources = Column(JSON, nullable=True)  # List[str] — 에스컬레이션 경로는 null
    escalated = Column(Boolean, nullable=False, default=False)
    escalation_reason = Column(String(200), nullable=True)
    escalation_status = Column(String(10), nullable=False, default="open")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)
```
(List, Optional import는 향후 확장용 — 3.9 경고 방지 필요 없으면 생략 가능하나 일관성을 위해 유지하지 않는다. 실제 파일에서는 `from typing import List, Optional` 줄을 **쓰지 않는다** — 미사용 import 방지.)

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_database.py -v
```
Expected: PASS 3건

- [ ] **Step 6: 커밋**

```bash
git add .gitignore requirements.txt requirements-dev.txt pytest.ini .env.example docker-compose.yml backend/ tests/
git commit -m "chore: 프로젝트 기반 — 설정, DB 엔진, VocRecord 모델

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: LLM 교체 가능 추상화

**Files:**
- Create: `backend/llm/__init__.py`, `backend/llm/base.py`, `backend/llm/openai_compat.py`, `backend/llm/factory.py`
- Create: `tests/fakes.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `settings` (Task 1)
- Produces:
  - `LLMProvider` (ABC): `.name: str` 프로퍼티, `.generate(prompt: str, **kwargs) -> str`
  - `OpenAICompatProvider(base_url: str, api_key: str, model: str, client: Optional[object] = None)` — client는 테스트 주입용
  - `get_llm_provider(settings) -> Optional[LLMProvider]` — 미설정 시 `None`
  - `FakeProvider(responses: List[str])` (tests/fakes.py) — `generate` 호출마다 responses를 순서대로 소진, 소진 시 `RuntimeError`. `.calls: List[str]`로 프롬프트 기록

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_llm.py`:
```python
from backend.config import Settings
from backend.llm.factory import get_llm_provider


class _FakeClient:
    """openai client 대역 — chat.completions.create 호출 기록."""

    def __init__(self, reply: str):
        self._reply = reply
        self.calls = []

    @property
    def chat(self):
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)

                class _Msg:
                    content = outer._reply

                class _Choice:
                    message = _Msg()

                class _Resp:
                    choices = [_Choice()]

                return _Resp()

        class _Chat:
            completions = _Completions()

        return _Chat()


def test_openai_compat_generate가_클라이언트를_호출한다():
    from backend.llm.openai_compat import OpenAICompatProvider

    client = _FakeClient("안녕하세요")
    provider = OpenAICompatProvider(base_url="http://x", api_key="k", model="m", client=client)

    assert provider.generate("질문") == "안녕하세요"
    assert provider.name == "openai_compat"
    assert client.calls[0]["model"] == "m"
    assert client.calls[0]["messages"][0]["content"] == "질문"


def test_factory_api_key_있으면_provider_생성():
    s = Settings()
    s.llm_provider = "openai_compat"
    s.llm_api_key = "k"
    s.llm_base_url = "http://x"
    s.llm_model = "m"
    provider = get_llm_provider(s)
    assert provider is not None
    assert provider.name == "openai_compat"


def test_factory_api_key_없으면_None():
    s = Settings()
    s.llm_provider = "openai_compat"
    s.llm_api_key = ""
    assert get_llm_provider(s) is None


def test_fake_provider_순서대로_반환():
    from tests.fakes import FakeProvider

    provider = FakeProvider(["a", "b"])
    assert provider.generate("x") == "a"
    assert provider.generate("y") == "b"
    assert provider.calls == ["x", "y"]
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_llm.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.llm'`

- [ ] **Step 3: 최소 구현**

`backend/llm/base.py` (tpssAgent `backend/llm/base.py`와 동일한 ABC):
```python
"""LLM Provider 추상 베이스 — provider 교체 가능 추상화 (스펙 §6.3).

모든 LLM provider는 이 인터페이스를 구현해야 한다.
"""
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """LLM provider 추상 인터페이스."""

    @property
    @abstractmethod
    def name(self) -> str:
        """provider 이름 (예: 'openai_compat')"""
        raise NotImplementedError

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """프롬프트를 받아 LLM 응답을 생성 (동기).

        Args:
            prompt: 입력 프롬프트
            **kwargs: provider별 추가 옵션 (temperature 등)
        Returns:
            생성된 텍스트 응답
        """
        raise NotImplementedError
```

`backend/llm/openai_compat.py`:
```python
"""OpenAI 호환 API 기본 구현 — LLM_BASE_URL/LLM_MODEL로 교체 (스펙 §6.3)."""
from typing import Optional

from backend.llm.base import LLMProvider


class OpenAICompatProvider(LLMProvider):
    """OpenAI 호환 chat.completions 호출 provider."""

    def __init__(self, base_url: str, api_key: str, model: str, client: Optional[object] = None):
        if client is None:
            from openai import OpenAI

            client = OpenAI(base_url=base_url, api_key=api_key)
        self._client = client
        self._model = model

    @property
    def name(self) -> str:
        return "openai_compat"

    def generate(self, prompt: str, **kwargs) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.2),
        )
        return response.choices[0].message.content
```

`backend/llm/factory.py`:
```python
"""설정 기반 provider 생성 — 미설정 시 None 반환 (스펙 §4.5 우아한 열화)."""
from typing import Optional

from backend.config import Settings
from backend.llm.base import LLMProvider


def get_llm_provider(settings: Settings) -> Optional[LLMProvider]:
    if settings.llm_provider == "openai_compat" and settings.llm_api_key:
        from backend.llm.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    return None
```

`backend/llm/__init__.py`:
```python
from backend.llm.base import LLMProvider
from backend.llm.factory import get_llm_provider

__all__ = ["LLMProvider", "get_llm_provider"]
```

`tests/fakes.py`:
```python
"""테스트용 LLM 더블 — LLM 없이 그래프 전 경로 테스트 (스펙 §8)."""
from typing import List

from backend.llm.base import LLMProvider


class FakeProvider(LLMProvider):
    """예약된 응답을 순서대로 반환. 소진되면 예외 발생."""

    def __init__(self, responses: List[str]):
        self.responses = list(responses)
        self.calls: List[str] = []

    @property
    def name(self) -> str:
        return "fake"

    def generate(self, prompt: str, **kwargs) -> str:
        self.calls.append(prompt)
        if not self.responses:
            raise RuntimeError("FakeProvider: 예약된 응답이 없음")
        return self.responses.pop(0)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_llm.py -v
```
Expected: PASS 4건

- [ ] **Step 5: 커밋**

```bash
git add backend/llm/ tests/fakes.py tests/test_llm.py
git commit -m "feat: LLM 교체 가능 추상화 — LLMProvider ABC와 OpenAI 호환 구현

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 3: tika 사용자 메뉴얼 작성 + 구조 린트

**Files:**
- Create: `manual/index.md`, `manual/01-getting-started.md`, `manual/02-managing-todos.md`, `manual/03-ui-guide.md`, `manual/04-troubleshooting.md`, `manual/05-faq.md`
- Create: `scripts/lint_manual.py`
- Test: `tests/test_manual_lint.py`

**Interfaces:**
- Consumes: 없음
- Produces: `manual/` 폴더의 6개 마크다운 — `##` 섹션이 곧 검색 단위(스펙 §5.2). `scripts/lint_manual.py`의 `lint() -> int` (0=통과). Task 4의 `load_manual()`이 이 파일들을 소비

**메뉴얼 내용 근거** (tika = `~/git/todoapp-vue-spring` 실제 코드):
- `TodoController.java`: CRUD + `/myday`, `/important`, `/list/{listName}`, `PATCH toggle/important/myday`, `DELETE /completed`, `POST /email`
- `Todo.java` 엔티티: title, notes, completed, important, myDay, listName
- `TodoList.vue`: 사이드바(오늘/중요/전체 + 개수 배지), 검색, 인라인 추가, 원형 체크박스, 완료 항목 아코디언, 상세 패널(제목/메모/오늘/중요 토글), 이메일 다이얼로그(주소 유효성 검사), 스낵바
- `application.properties`(H2 인메모리): 서버 재시작 시 데이터 초기화 — troubleshooting 핵심 소재

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_manual_lint.py`:
```python
import subprocess
import sys


def test_메뉴얼_린트_통과():
    result = subprocess.run(
        [sys.executable, "scripts/lint_manual.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "메뉴얼 린트 실패:\n" + result.stdout + result.stderr
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_manual_lint.py -v
```
Expected: FAIL — `lint` 실패 출력(메뉴얼 파일 부족). 스크립트가 없으면 `No such file` stderr 포함

- [ ] **Step 3: 린트 스크립트 구현**

`scripts/lint_manual.py`:
```python
"""메뉴얼 구조 린트 — 스펙 §5.2 규칙 검증.

규칙:
1. manual/ 에 index.md + 문서 5종(01~05) 존재
2. 문서별 `##` 섹션 1개 이상, 섹션 제목 중복 금지
3. 04-troubleshooting.md의 모든 섹션은 **증상**/**원인**/**해결** 3단 구조
4. index.md가 모든 문서 파일명을 언급
"""
import re
import sys
from pathlib import Path

MANUAL_DIR = Path(__file__).parent.parent / "manual"
EXPECTED_FILES = [
    "01-getting-started.md",
    "02-managing-todos.md",
    "03-ui-guide.md",
    "04-troubleshooting.md",
    "05-faq.md",
]


def sections_of(path: Path):
    text = path.read_text(encoding="utf-8")
    titles = re.findall(r"^## (.+)$", text, re.MULTILINE)
    return text, titles


def lint() -> int:
    errors = []
    if not MANUAL_DIR.is_dir():
        print(f"[린트 실패] {MANUAL_DIR} 가 없습니다")
        return 1

    index_path = MANUAL_DIR / "index.md"
    index_text = index_path.read_text(encoding="utf-8") if index_path.exists() else ""

    for name in EXPECTED_FILES:
        path = MANUAL_DIR / name
        if not path.exists():
            errors.append(f"{name}: 파일이 없습니다")
            continue
        text, titles = sections_of(path)
        if not titles:
            errors.append(f"{name}: `##` 섹션이 없습니다")
        if len(titles) != len(set(titles)):
            errors.append(f"{name}: 섹션 제목이 중복됩니다")
        if name == "04-troubleshooting.md":
            for title in titles:
                section = text.split(f"## {title}", 1)[1]
                section = section.split("\n## ", 1)[0]
                for label in ("**증상**", "**원인**", "**해결**"):
                    if label not in section:
                        errors.append(f"{name}#{title}: {label} 누락 — 3단 구조 위반")
        if path.stem not in index_text:
            errors.append(f"index.md 가 {name} 을 언급하지 않습니다")

    for error in errors:
        print(f"[린트 실패] {error}")
    if not errors:
        print("메뉴얼 린트 통과")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(lint())
```

- [ ] **Step 4: 메뉴얼 6종 작성**

`manual/01-getting-started.md`:
```markdown
# tika 시작하기

tika에 오신 것을 환영합니다. tika는 Things 3에서 영감을 받은 간결한 할 일 관리 앱입니다.

## tika란 무엇인가요
tika는 할 일을 만들고, 완료 표시하고, 정리하는 데 필요한 기능만 담은 할 일 관리 앱입니다.
복잡한 설정 없이 실행하자마자 바로 사용할 수 있습니다.

## 화면 구성
tika 화면은 두 영역으로 구성됩니다.
- 왼쪽 사이드바: 오늘, 중요, 전체 목록으로 이동하는 메뉴
- 오른쪽 목록 영역: 할 일 목록과 새 할 일 입력란, 상단 검색창

## 첫 할 일 추가하기
목록 영역 상단의 새 할 일 입력란에 할 일 제목을 입력하고 Enter 키를 누릅니다.
입력한 할 일이 목록에 바로 나타납니다.

## 할 일 완료하기
할 일 항목 왼쪽의 원형 체크박스를 클릭하면 완료 표시가 됩니다.
완료된 항목은 취소선과 함께 목록 아래쪽 "완료됨" 영역으로 이동합니다.
```

`manual/02-managing-todos.md`:
```markdown
# 할 일 관리

생성, 수정, 삭제, 완료 등 할 일 관리 방법을 안내합니다.

## 할 일 추가하기
목록 영역 상단의 새 할 일 입력란에 제목을 입력하고 Enter 키를 누릅니다.
입력 즉시 목록에 반영됩니다.

## 할 일 내용 수정하기
수정할 할 일을 클릭하면 오른쪽에 상세 패널이 열립니다.
상세 패널에서 제목과 메모를 수정하면 자동으로 저장됩니다.

## 메모 추가하기
할 일 상세 패널의 메모 입력란에 내용을 입력합니다.
메모는 할 일에 대한 상세 설명, 링크, 관련 정보를 적는 공간입니다.

## 할 일 삭제하기
목록에서 할 일 항목에 마우스를 올리면 나타나는 삭제 버튼을 누릅니다.
삭제된 할 일은 복구할 수 없으므로 신중하게 눌러 주세요.

## 완료 표시하고 되돌리기
원형 체크박스를 클릭하면 완료, 다시 클릭하면 미완료로 되돌아갑니다.
완료된 항목은 목록 아래 "완료됨" 영역에 모여 표시됩니다.

## 오늘(My Day)에 추가하기
할 일 상세 패널에서 오늘 표시를 켜면 오늘 목록에 나타납니다.
오늘 목록은 사이드바의 오늘 항목에서 확인할 수 있습니다.

## 중요로 표시하기
할 일 상세 패널에서 중요 표시를 켜면 별 표시가 붙습니다.
사이드바의 중요 항목에서 중요 표시한 할 일만 모아 볼 수 있습니다.

## 할 일 검색하기
화면 상단의 검색창에 단어를 입력하면 제목과 메모에서 해당 단어를 찾아 목록을 걸러 줍니다.
대소문자는 구분하지 않습니다.

## 할 일 목록을 이메일로 보내기
상단의 이메일 버튼을 누르고 받을 주소를 입력하면 현재 할 일 목록을 이메일로 보낼 수 있습니다.
형식에 맞는 이메일 주소를 입력해야 전송됩니다.
```

`manual/03-ui-guide.md`:
```markdown
# 화면 구성 가이드

tika 화면의 구성 요소와 조작 방법을 안내합니다.

## 기본 화면 구성
왼쪽에 사이드바, 오른쪽에 할 일 목록이 표시됩니다.
목록 위에는 검색창과 새 할 일 입력란이 있습니다.

## 사이드바 메뉴
사이드바에는 세 가지 메뉴가 있습니다.
- 오늘: 오늘 표시한 할 일 (태양 아이콘)
- 중요: 중요 표시한 할 일 (별 아이콘)
- 전체: 모든 할 일 (클립보드 아이콘)
각 메뉴 오른쪽에는 해당 할 일 개수가 표시됩니다.

## 완료된 할 일 보기
완료한 할 일은 목록 아래쪽 "완료됨" 영역에 접혀 있습니다.
완료됨 영역을 클릭해 펼치면 취소선이 그어진 완료 항목들을 확인할 수 있습니다.

## 상세 패널
할 일을 클릭하면 오른쪽에서 상세 패널이 열립니다.
제목과 메모를 편집하고, 오늘 표시와 중요 표시를 켜고 끌 수 있습니다.

## 알림 메시지
작업 결과(저장, 삭제, 이메일 전송 등)는 화면 아래에 잠깐 나타나는 알림 메시지로 확인할 수 있습니다.
```

`manual/04-troubleshooting.md`:
```markdown
# 문제 해결

자주 보고되는 문제의 증상, 원인, 해결 방법을 안내합니다.

## 할 일이 저장되지 않아요
**증상**: 새 할 일을 입력했는데 목록에 나타나지 않거나 곧 사라집니다.
**원인**: tika 서버가 실행 중이 아니거나 연결이 불안정할 수 있습니다. 또는 페이지가 오래된 상태일 수 있습니다.
**해결**: 1. 페이지를 새로고침하세요. 2. 그래도 같은 증상이면 tika 서버가 중단된 것이므로 잠시 후 다시 시도하세요. 3. 지속되면 버그로 접수해 주세요.

## 입력한 할 일이 사라졌어요
**증상**: 이전에 추가했던 할 일이 목록에 보이지 않습니다.
**원인**: tika 현재 버전은 메모리 기반 데이터베이스를 사용해 앱/서버가 재시작되면 데이터가 초기화됩니다.
**해결**: 할 일을 다시 추가해 주세요. 영구 저장이 꼭 필요하다면 기능 요청으로 접수해 주세요.

## 완료한 할 일이 목록에서 안 보여요
**증상**: 완료 표시를 했는데 항목이 사라진 것처럼 보입니다.
**원인**: 완료된 항목은 목록 아래 "완료됨" 영역에 접혀 있습니다. 삭제된 것이 아닙니다.
**해결**: 목록 아래쪽의 완료됨 영역을 클릭해 펼치세요. 완료를 되돌리려면 체크박스를 다시 클릭하세요.

## 검색해도 할 일이 안 나와요
**증상**: 분명히 추가한 할 일이 검색되지 않습니다.
**원인**: 검색은 제목과 메모만 대상으로 하며 대소문자는 구분하지 않지만, 띄어쓰기나 오타가 다르면 걸리지 않습니다.
**해결**: 1. 더 짧은 단어로 검색해 보세요. 2. 메모가 아닌 제목에 있는 단어로 검색해 보세요. 3. 전체 목록에서 직접 확인해 보세요.

## 이메일이 오지 않아요
**증상**: 할 일 목록을 이메일로 보냈는데 메일이 도착하지 않습니다.
**원인**: 받는 주소가 올바른지, 스팸함으로 분류되지 않았는지 확인이 필요합니다. 형식에 맞지 않는 주소는 전송 자체가 안 됩니다.
**해결**: 1. 이메일 주소를 다시 확인하고 재전송하세요. 2. 스팸함을 확인하세요. 3. 반복되면 버그로 접수해 주세요.

## 오늘 표시가 자동으로 안 풀려요
**증상**: 어제 오늘 표시한 할 일이 다음 날에도 오늘 목록에 남아 있습니다.
**원인**: tika의 오늘 표시는 자동 만료 기능이 없어 수동으로 해제해야 합니다.
**해결**: 해당 할 일의 상세 패널에서 오늘 표시를 꺼 주세요. 자동 해제를 원하시면 기능 요청으로 접수해 주세요.
```

`manual/05-faq.md`:
```markdown
# 자주 묻는 질문

tika에 대해 자주 묻는 질문과 답변입니다.

## 데이터는 어디에 저장되나요
현재 버전은 메모리 기반 데이터베이스를 사용합니다. 앱이나 서버가 재시작되면 데이터가 초기화될 수 있습니다. 영구 저장 기능은 준비 중입니다.

## 여러 기기에서 동기화되나요
현재 버전은 기기 간 동기화를 지원하지 않습니다. 동기화가 필요하다면 기능 요청으로 알려주세요.

## 완료 표시를 취소할 수 있나요
네, 가능합니다. 완료된 항목의 체크박스를 다시 클릭하면 미완료로 되돌아갑니다.

## 다른 사람과 목록을 공유할 수 있나요
이메일로 할 일 목록을 보낼 수 있습니다. 상단의 이메일 버튼을 사용하세요.

## 모바일에서 쓸 수 있나요
tika는 반응형 화면을 제공해 모바일 브라우저에서도 사용할 수 있습니다.
```

`manual/index.md`:
```markdown
# tika 사용자 메뉴얼 색인

tika 사용자 메뉴얼의 전체 문서 목록입니다. 각 섹션은 자기완결적으로 작성되어 있어 필요한 항목만 읽어도 됩니다.

## 문서 목록
- [01-getting-started](01-getting-started.md) — tika 소개, 화면 구성, 첫 할 일 추가, 완료하기
- [02-managing-todos](02-managing-todos.md) — 추가, 수정, 메모, 삭제, 완료, 오늘/중요 표시, 검색, 이메일 전송
- [03-ui-guide](03-ui-guide.md) — 기본 화면, 사이드바, 완료 항목 영역, 상세 패널, 알림 메시지
- [04-troubleshooting](04-troubleshooting.md) — 저장 안 됨, 데이터 사라짐, 완료 항목 안 보임, 검색 안 됨, 이메일 미수신, 오늘 표시 잔류
- [05-faq](05-faq.md) — 저장 방식, 동기화, 완료 취소, 목록 공유, 모바일
```

- [ ] **Step 5: 린트 실행 — 통과 확인**

```bash
python scripts/lint_manual.py
pytest tests/test_manual_lint.py -v
```
Expected: `메뉴얼 린트 통과` 출력, 테스트 PASS

- [ ] **Step 6: 커밋**

```bash
git add manual/ scripts/lint_manual.py tests/test_manual_lint.py
git commit -m "docs: tika 사용자 메뉴얼 5종 + 색인과 구조 린트 스크립트

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: 메뉴얼 간단 검색 (임베딩 없음)

**Files:**
- Create: `backend/manual_retrieval.py`
- Test: `tests/test_manual_retrieval.py`

**Interfaces:**
- Consumes: `manual/*.md` (Task 3), `CATEGORIES` (Task 1)
- Produces:
  - `ManualChunk` dataclass: `.file: str`(예: "03-ui-guide"), `.section: str`(예: "할 일 삭제하기"), `.content: str`, `.source: str` 프로퍼티 → `"03-ui-guide#할 일 삭제하기"`
  - `load_manual(manual_dir: Path = MANUAL_DIR) -> List[ManualChunk]` — `##` 단위 분해, index.md 제외
  - `search(chunks, voc_text: str, category: Optional[str] = None, top_k: int = 3) -> List[ManualChunk]` — 점수 = 제목 토큰 매칭(+3) + 본문 출현 수(+1/회) + 분류 유형별 파일 접두사 보너스(+2)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_manual_retrieval.py`:
```python
from backend.manual_retrieval import load_manual, search


def test_메뉴얼_로드_섹션_분해():
    chunks = load_manual()
    assert len(chunks) >= 15  # 5개 문서의 전체 섹션 수
    first = chunks[0]
    assert first.file == "01-getting-started"
    assert first.source == f"01-getting-started#{first.section}"
    assert first.content  # 내용이 비어 있지 않음


def test_저장_문의가_문제해결_섹션을_찾는다():
    chunks = load_manual()
    results = search(chunks, "할 일이 저장되지 않아요", category="사용법문의")
    assert any("저장되지" in c.section for c in results)


def test_사용법_문의는_가이드_문서_우선():
    chunks = load_manual()
    results = search(chunks, "완료한 할 일이 목록에서 안 보여요", category="사용법문의")
    assert results
    assert results[0].file.startswith(("01", "02", "03"))


def test_불만은_문제해결_문서_우선():
    chunks = load_manual()
    results = search(chunks, "이메일이 오지 않아요", category="불만")
    assert results
    assert results[0].file.startswith(("04", "05"))


def test_관련_없는_질문은_빈_결과():
    chunks = load_manual()
    assert search(chunks, "zzz qq", category="사용법문의") == []


def test_상위_3개만_반환():
    chunks = load_manual()
    results = search(chunks, "할 일 추가 완료 삭제 저장 검색 이메일 메모", category="사용법문의")
    assert 0 < len(results) <= 3
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_manual_retrieval.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.manual_retrieval'`

- [ ] **Step 3: 최소 구현**

`backend/manual_retrieval.py`:
```python
"""메뉴얼 로드 + 간단 검색 (임베딩 없음) — 스펙 §5.3.

검색 단위는 `##` 섹션이다 (스펙 §5.2 구조 규칙).
나중에 벡터 검색으로 교체할 때는 search() 시그니처를 유지한 구현체를 추가한다.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MANUAL_DIR = Path(__file__).parent.parent / "manual"

# 분류 유형별 우선 문서 접두사 (스펙 §5.3 — 버그제보는 에스컬레이션 경로라 검색하지 않음)
CATEGORY_FILE_WEIGHTS: Dict[str, Tuple[str, ...]] = {
    "사용법문의": ("01", "02", "03"),
    "칭찬": ("01", "02", "03"),
    "불만": ("04", "05"),
}


@dataclass
class ManualChunk:
    file: str      # 예: "03-ui-guide" (.md 제외)
    section: str   # 예: "할 일 삭제하기"
    content: str

    @property
    def source(self) -> str:
        return f"{self.file}#{self.section}"


def _tokenize(text: str) -> List[str]:
    """2글자 이상의 한글/영문/숫자 덩어리를 토큰으로 추출."""
    return re.findall(r"[가-힣A-Za-z0-9]{2,}", text)


def load_manual(manual_dir: Path = MANUAL_DIR) -> List[ManualChunk]:
    """manual/*.md 를 읽어 `##` 단위 청크로 분해. index.md는 제외."""
    chunks: List[ManualChunk] = []
    for path in sorted(manual_dir.glob("*.md")):
        if path.name == "index.md":
            continue
        text = path.read_text(encoding="utf-8")
        parts = re.split(r"^## ", text, flags=re.MULTILINE)
        for part in parts[1:]:  # parts[0]은 # 헤더 영역 — 스킵
            lines = part.strip().splitlines()
            if not lines:
                continue
            chunks.append(
                ManualChunk(file=path.stem, section=lines[0].strip(), content="\n".join(lines))
            )
    return chunks


def _score(chunk: ManualChunk, tokens: List[str], preferred: Tuple[str, ...]) -> int:
    score = 0
    for token in tokens:
        if token in chunk.section:
            score += 3  # 제목 매칭 고가중 (스펙 §5.3)
        score += chunk.content.count(token)
    if chunk.file.startswith(preferred):
        score += 2  # 분류 유형별 문서 보너스
    return score


def search(
    chunks: List[ManualChunk],
    voc_text: str,
    category: Optional[str] = None,
    top_k: int = 3,
) -> List[ManualChunk]:
    """VOC 텍스트와 분류 유형으로 상위 청크 검색. 점수 0 이하는 제외."""
    tokens = _tokenize(voc_text)
    if not tokens:
        return []
    preferred = CATEGORY_FILE_WEIGHTS.get(category or "", ())
    scored = [
        (i, _score(chunk, tokens, preferred))
        for i, chunk in enumerate(chunks)
    ]
    scored = [(i, s) for i, s in scored if s > 0]
    scored.sort(key=lambda pair: (-pair[1], pair[0]))
    return [chunks[i] for i, _ in scored[:top_k]]
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_manual_retrieval.py -v
```
Expected: PASS 6건. `test_불만은_문제해결_문서_우선`이 실패하면 가중치/토큰 점검 (04 문서 제목 "이메일이 오지 않아요"가 VOC 토큰과 정확히 매칭되어야 함)

- [ ] **Step 5: 커밋**

```bash
git add backend/manual_retrieval.py tests/test_manual_retrieval.py
git commit -m "feat: 메뉴얼 간단 검색 — 토큰 매칭 + 분류별 문서 가중치

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 5: AgentState + classify 노드

**Files:**
- Create: `backend/state.py`, `backend/nodes/__init__.py`(빈 파일), `backend/nodes/classify.py`
- Test: `tests/test_classify.py`

**Interfaces:**
- Consumes: `CATEGORIES`, `PRIORITIES` (Task 1), `LLMProvider` (Task 2), `FakeProvider` (Task 2)
- Produces:
  - `AgentState` (TypedDict, total=False) — 필드: voc_text, session_id, category, priority, manual_chunks(List[dict]), answer, answer_sources(List[str]), escalated, escalation_reason, escalation_message, response, voc_id, error
  - `parse_classification(text: str) -> Dict[str, str]` — `{"category", "priority"}`, 실패 시 `{"category": "기타", "priority": "medium"}`
  - `make_classify_node(provider: Optional[LLMProvider])` — 호출 가능한 노드 팩토리

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_classify.py`:
```python
from backend.nodes.classify import (
    FALLBACK_CLASSIFICATION,
    make_classify_node,
    parse_classification,
)
from tests.fakes import FakeProvider


def test_정상_JSON_파싱():
    result = parse_classification('{"category": "버그제보", "priority": "high"}')
    assert result == {"category": "버그제보", "priority": "high"}


def test_JSON_앞뒤_설명_허용():
    result = parse_classification(
        '분류 결과입니다\n{"category": "칭찬", "priority": "low"}\n감사합니다'
    )
    assert result["category"] == "칭찬"


def test_잘못된_유형은_폴백():
    result = parse_classification('{"category": "문의", "priority": "low"}')
    assert result == dict(FALLBACK_CLASSIFICATION)


def test_파싱_불가_출력은_폴백():
    assert parse_classification("죄송합니다 무슨 뜻인지 모르겠어요") == dict(FALLBACK_CLASSIFICATION)


def test_노드_정상_동작():
    provider = FakeProvider(['{"category": "사용법문의", "priority": "low"}'])
    node = make_classify_node(provider)
    result = node({"voc_text": "완료는 어떻게 하나요?"})
    assert result == {"category": "사용법문의", "priority": "low"}
    assert "사용법문의" in provider.calls[0]  # 프롬프트에 분류 기준 포함 확인


def test_노드_LLM_실패시_폴백과_에러기록():
    provider = FakeProvider([])  # 응답 없음 → 예외
    node = make_classify_node(provider)
    result = node({"voc_text": "불만 있어요"})
    assert result["category"] == "기타"
    assert result["priority"] == "medium"
    assert "error" in result


def test_노드_provider_None_폴백():
    node = make_classify_node(None)
    result = node({"voc_text": "x"})
    assert result["category"] == "기타"
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_classify.py -v
```
Expected: FAIL — `No module named 'backend.state'` / `'backend.nodes'`

- [ ] **Step 3: 최소 구현**

`backend/state.py`:
```python
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
```

`backend/nodes/classify.py`:
```python
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
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_classify.py -v
```
Expected: PASS 7건

- [ ] **Step 5: 커밋**

```bash
git add backend/state.py backend/nodes/ tests/test_classify.py
git commit -m "feat: AgentState 정의와 VOC 분류 노드 (JSON 파싱 + 폴백)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: retrieve 노드 + answer 노드 (환각 방지)

**Files:**
- Create: `backend/nodes/retrieve.py`, `backend/nodes/answer.py`
- Test: `tests/test_answer_node.py`

**Interfaces:**
- Consumes: `load_manual`, `search`, `ManualChunk` (Task 4), `LLMProvider`/`FakeProvider` (Task 2)
- Produces:
  - `make_retrieve_node(chunks: Optional[List[ManualChunk]] = None)` — state에 `manual_chunks: List[dict]` 저장
  - `make_answer_node(provider: Optional[LLMProvider])` — state에 `answer`, `answer_sources`, `escalated`, `escalation_reason` 저장
  - `NO_MANUAL_ANSWER`, `FALLBACK_ANSWER` 상수 (answer.py)
  - `build_answer_prompt(voc_text: str, chunks: List[dict]) -> str`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_answer_node.py`:
```python
from backend.nodes.answer import (
    FALLBACK_ANSWER,
    NO_MANUAL_ANSWER,
    build_answer_prompt,
    make_answer_node,
)
from backend.nodes.retrieve import make_retrieve_node
from tests.fakes import FakeProvider

CHUNKS = [
    {
        "file": "03-ui-guide",
        "section": "할 일 삭제하기",
        "content": "## 할 일 삭제하기\n항목에 마우스를 올려 삭제 버튼을 누릅니다.",
    }
]


def test_근거_있으면_답변_생성():
    provider = FakeProvider(["삭제 버튼을 누르세요.\n📖 출처: 03-ui-guide#할 일 삭제하기"])
    node = make_answer_node(provider)
    result = node({"voc_text": "삭제 어떻게 해요?", "manual_chunks": CHUNKS})
    assert result["escalated"] is False
    assert result["answer_sources"] == ["03-ui-guide#할 일 삭제하기"]
    assert "📖 출처" in result["answer"]


def test_근거_없으면_답변_금지_에스컬레이션():
    """환각 방지 핵심 테스트 (스펙 §4.5) — 근거 없으면 LLM을 호출조차 하지 않는다."""
    provider = FakeProvider(["지어낸 답변"])
    node = make_answer_node(provider)
    result = node({"voc_text": "테마 색을 분홍색으로 바꾸고 싶어요", "manual_chunks": []})
    assert result["answer"] == NO_MANUAL_ANSWER
    assert result["escalated"] is True
    assert result["answer_sources"] == []
    assert provider.calls == []  # LLM 미호출 확인


def test_LLM_실패시_폴백_답변():
    provider = FakeProvider([])  # 응답 없음 → 예외
    node = make_answer_node(provider)
    result = node({"voc_text": "x", "manual_chunks": CHUNKS})
    assert result["answer"] == FALLBACK_ANSWER
    assert result["escalated"] is True


def test_provider_None이면_폴백_답변():
    node = make_answer_node(None)
    result = node({"voc_text": "x", "manual_chunks": CHUNKS})
    assert result["answer"] == FALLBACK_ANSWER
    assert result["escalated"] is True


def test_프롬프트에_근거와_VOC_포함():
    prompt = build_answer_prompt("삭제 어떻게 해요?", CHUNKS)
    assert "삭제 어떻게 해요?" in prompt
    assert "할 일 삭제하기" in prompt
    assert "지어내" in prompt  # 환각 금지 지시 포함


def test_retrieve_노드_실제_메뉴얼_검색():
    node = make_retrieve_node()
    result = node({"voc_text": "할 일이 저장되지 않아요", "category": "사용법문의"})
    assert len(result["manual_chunks"]) >= 1
    first = result["manual_chunks"][0]
    assert set(first.keys()) == {"file", "section", "content"}
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_answer_node.py -v
```
Expected: FAIL — `No module named 'backend.nodes.retrieve'`

- [ ] **Step 3: 최소 구현**

`backend/nodes/retrieve.py`:
```python
"""메뉴얼 검색 노드 — manual_retrieval.search 래핑 (스펙 §4.1)."""
from typing import Any, Dict, List, Optional

from backend.manual_retrieval import ManualChunk, load_manual, search


def make_retrieve_node(chunks: Optional[List[ManualChunk]] = None):
    manual_chunks = chunks if chunks is not None else load_manual()

    def retrieve_node(state: Dict[str, Any]) -> Dict[str, Any]:
        results = search(
            manual_chunks,
            state["voc_text"],
            category=state.get("category"),
            top_k=3,
        )
        return {
            "manual_chunks": [
                {"file": c.file, "section": c.section, "content": c.content}
                for c in results
            ]
        }

    return retrieve_node
```

`backend/nodes/answer.py`:
```python
"""메뉴얼 근거 답변 노드 — 환각 방지 핵심 (스펙 §4.5, §5.4).

근거(청크)가 없으면 LLM을 호출하지 않고 정직하게 안내한 뒤 에스컬레이션한다.
"""
from typing import Any, Dict, List, Optional

from backend.llm.base import LLMProvider

NO_MANUAL_ANSWER = (
    "죄송합니다. 현재 tika 메뉴얼에서 이 문의에 대한 내용을 찾지 못했습니다.\n"
    "담당자에게 전달하여 확인 후 안내드리겠습니다."
)

FALLBACK_ANSWER = "죄송합니다. 지금은 답변을 생성하지 못했습니다. 담당자에게 전달하겠습니다."

ANSWER_PROMPT = """당신은 todo 앱 'tika'의 고객 지원 담당자입니다.

아래 [메뉴얼 근거]에 있는 내용만 사용해서 사용자 VOC에 답변하세요.
- 근거에 없는 내용을 절대 지어내지 마세요.
- 근거가 일부만 있으면 있는 내용만 안내하세요.
- 친절하고 간결한 한국어로 작성하고, 절차가 있으면 번호 목록을 사용하세요.

[사용자 VOC]
{voc_text}

[메뉴얼 근거]
{chunks_text}

답변 마지막 줄에 아래 형식으로 출처를 모두 나열하세요.
📖 출처: 파일명#섹션제목"""


def build_answer_prompt(voc_text: str, chunks: List[dict]) -> str:
    chunks_text = "\n\n".join(
        f"### {c['section']} ({c['file']})\n{c['content']}" for c in chunks
    )
    return ANSWER_PROMPT.format(voc_text=voc_text, chunks_text=chunks_text)


def _sources_of(chunks: List[dict]) -> List[str]:
    return [f"{c['file']}#{c['section']}" for c in chunks]


def make_answer_node(provider: Optional[LLMProvider]):
    def answer_node(state: Dict[str, Any]) -> Dict[str, Any]:
        chunks = state.get("manual_chunks") or []
        voc_text = state["voc_text"]

        if not chunks:
            # 환각 방지 — 근거 없으면 답변 생성 금지 (스펙 §4.5)
            return {
                "answer": NO_MANUAL_ANSWER,
                "answer_sources": [],
                "escalated": True,
                "escalation_reason": "메뉴얼에 근거 없는 문의",
            }

        if provider is not None:
            try:
                answer = provider.generate(
                    build_answer_prompt(voc_text, chunks), temperature=0.2
                )
                return {
                    "answer": answer,
                    "answer_sources": _sources_of(chunks),
                    "escalated": False,
                }
            except Exception as exc:  # 우아한 열화
                print(f"[answer] LLM 호출 실패, 폴백 응답 사용: {exc}")
                escalation_reason = f"답변 생성 실패: {exc}"
            else:
                escalation_reason = ""
        else:
            escalation_reason = "LLM provider 미설정"

        return {
            "answer": FALLBACK_ANSWER,
            "answer_sources": _sources_of(chunks),
            "escalated": True,
            "escalation_reason": escalation_reason,
        }

    return answer_node
```
주의: `try/except/else` 구조 대신 아래처럼 직관적으로 작성해도 된다 (동일 동작):
```python
        if provider is None:
            return {
                "answer": FALLBACK_ANSWER,
                "answer_sources": _sources_of(chunks),
                "escalated": True,
                "escalation_reason": "LLM provider 미설정",
            }
        try:
            answer = provider.generate(
                build_answer_prompt(voc_text, chunks), temperature=0.2
            )
        except Exception as exc:
            print(f"[answer] LLM 호출 실패, 폴백 응답 사용: {exc}")
            return {
                "answer": FALLBACK_ANSWER,
                "answer_sources": _sources_of(chunks),
                "escalated": True,
                "escalation_reason": f"답변 생성 실패: {exc}",
            }
        return {
            "answer": answer,
            "answer_sources": _sources_of(chunks),
            "escalated": False,
        }
```
**두 번째 버전(초기 return 스타일)을 사용한다.** 첫 버전은 참고용으로만 남긴다.

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_answer_node.py -v
```
Expected: PASS 6건

- [ ] **Step 5: 커밋**

```bash
git add backend/nodes/retrieve.py backend/nodes/answer.py tests/test_answer_node.py
git commit -m "feat: 메뉴얼 검색·답변 노드 — 근거 없으면 에스컬레이션 (환각 방지)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 7: escalate + respond + save 노드

**Files:**
- Create: `backend/nodes/escalate.py`, `backend/nodes/respond.py`, `backend/nodes/save.py`
- Test: `tests/test_escalate_respond_save.py`

**Interfaces:**
- Consumes: `LLMProvider`/`FakeProvider` (Task 2), `VocRecord` (Task 1), `db_session_factory` fixture (Task 1)
- Produces:
  - `make_escalate_node(provider: Optional[LLMProvider])` — state에 `escalated=True`, `escalation_reason`, `escalation_message` 저장
  - `ESCALATION_MESSAGES: Dict[str, str]`, `DEFAULT_ESCALATION_MESSAGE` (escalate.py)
  - `make_respond_node()` — state에 `response`(최종 마크다운) 저장
  - `make_save_node(session_factory: Callable)` — state에 `voc_id` 저장, 실패 시 `voc_id=None` + error (응답은 계속 반환)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_escalate_respond_save.py`:
```python
from backend.models import VocRecord
from backend.nodes.escalate import ESCALATION_MESSAGES, make_escalate_node
from backend.nodes.respond import make_respond_node
from backend.nodes.save import make_save_node
from tests.fakes import FakeProvider


def test_escalate_정적_문구_provider없음():
    node = make_escalate_node(None)
    result = node({"voc_text": "앱이 꺼져요", "category": "버그제보"})
    assert result["escalated"] is True
    assert result["escalation_message"] == ESCALATION_MESSAGES["버그제보"]
    assert "버그제보" in result["escalation_reason"]


def test_escalate_LLM_문구_생성():
    provider = FakeProvider(["접수했습니다. 빠르게 확인하겠습니다."])
    node = make_escalate_node(provider)
    result = node({"voc_text": "버그", "category": "버그제보"})
    assert result["escalation_message"] == "접수했습니다. 빠르게 확인하겠습니다."


def test_escalate_LLM_실패시_정적_폴백():
    provider = FakeProvider([])  # 응답 없음 → 예외
    node = make_escalate_node(provider)
    result = node({"voc_text": "버그", "category": "버그제보"})
    assert result["escalation_message"] == ESCALATION_MESSAGES["버그제보"]


def test_respond_답변_있으면_답변_그대로():
    node = make_respond_node()
    result = node({
        "answer": "이렇게 하세요\n📖 출처: 03-ui-guide#할 일 삭제하기",
        "answer_sources": ["03-ui-guide#할 일 삭제하기"],
    })
    assert result["response"].startswith("이렇게 하세요")


def test_respond_출처_누락시_덧붙임():
    node = make_respond_node()
    result = node({"answer": "이렇게 하세요", "answer_sources": ["03-ui-guide#할 일 삭제하기"]})
    assert "03-ui-guide#할 일 삭제하기" in result["response"]


def test_respond_에스컬레이션만_있으면_안내문구():
    node = make_respond_node()
    result = node({"escalated": True, "escalation_message": "전달했습니다"})
    assert result["response"] == "전달했습니다"


def test_respond_아무것도_없으면_기본_안내():
    node = make_respond_node()
    result = node({})
    assert result["response"]  # 빈 문자열 아님


def test_save_노드_저장(db_session_factory):
    node = make_save_node(db_session_factory)
    result = node({
        "voc_text": "불만 있어요",
        "session_id": "s1",
        "category": "불만",
        "priority": "low",
        "escalated": True,
    })
    assert isinstance(result["voc_id"], int)

    db = db_session_factory()
    record = db.query(VocRecord).first()
    db.close()
    assert record.escalated is True
    assert record.escalation_status == "open"


def test_save_노드_답변_경로_저장(db_session_factory):
    node = make_save_node(db_session_factory)
    result = node({
        "voc_text": "완료 어떻게 해요?",
        "session_id": "s2",
        "category": "사용법문의",
        "priority": "low",
        "answer": "체크박스를 누르세요",
        "answer_sources": ["03-ui-guide#완료된 할 일 보기"],
        "escalated": False,
    })
    assert isinstance(result["voc_id"], int)

    db = db_session_factory()
    record = db.query(VocRecord).filter_by(session_id="s2").first()
    db.close()
    assert record.answer == "체크박스를 누르세요"
    assert record.escalated is False


def test_save_실패해도_폭발하지_않음():
    def broken_factory():
        raise RuntimeError("db down")

    node = make_save_node(broken_factory)
    result = node({"voc_text": "x"})
    assert result["voc_id"] is None
    assert "error" in result
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_escalate_respond_save.py -v
```
Expected: FAIL — `No module named 'backend.nodes.escalate'`

- [ ] **Step 3: 최소 구현**

`backend/nodes/escalate.py`:
```python
"""에스컬레이션 노드 — 접수 안내 문구 생성 + 플래그 (스펙 §4.1).

LLM 문구 생성에 실패해도 정적 문구로 응답한다 (스펙 §4.5).
"""
from typing import Any, Dict, Optional

from backend.llm.base import LLMProvider

ESCALATION_MESSAGES = {
    "버그제보": "버그 제보를 알려주셔서 감사합니다. 담당자에게 전달했으며 확인 후 조치하겠습니다.",
    "기능요청": "소중한 기능 요청 감사합니다. 제품팀에 전달하여 검토하겠습니다.",
    "불만": "불편을 드려 죄송합니다. 담당자가 내용을 확인하여 빠르게 답변드리겠습니다.",
    "기타": "문의 내용을 담당자에게 전달했습니다. 확인 후 안내드리겠습니다.",
}
DEFAULT_ESCALATION_MESSAGE = "문의 내용을 담당자에게 전달했습니다. 확인 후 안내드리겠습니다."

ESCALATE_PROMPT = """당신은 todo 앱 'tika'의 고객 지원 담당자입니다.
아래 VOC는 사람이 확인해야 하는 {category} 유형입니다.
사용자에게 전달할 접수 완료 안내 문구를 2~3문장의 친절한 한국어로 작성하세요.
해결 방법이나 일정을 지어내지 말고, 접수되었음과 검토하겠다는 점만 안내하세요.

[VOC]
{voc_text}"""


def make_escalate_node(provider: Optional[LLMProvider]):
    def escalate_node(state: Dict[str, Any]) -> Dict[str, Any]:
        category = state.get("category", "기타")
        reason = state.get("escalation_reason") or f"{category} 유형은 사람 확인이 필요합니다"
        message = ESCALATION_MESSAGES.get(category, DEFAULT_ESCALATION_MESSAGE)
        if provider is not None:
            try:
                message = provider.generate(
                    ESCALATE_PROMPT.format(category=category, voc_text=state["voc_text"]),
                    temperature=0.3,
                )
            except Exception as exc:
                print(f"[escalate] LLM 호출 실패, 정적 문구 사용: {exc}")
        return {"escalated": True, "escalation_reason": reason, "escalation_message": message}

    return escalate_node
```

`backend/nodes/respond.py`:
```python
"""최종 응답 조립 노드 (스펙 §4.1).

우선순위: answer(출처 포함) > escalation_message > 기본 안내.
answer에 출처가 없으면 안전장치로 덧붙인다.
"""
from typing import Any, Dict

from backend.nodes.escalate import DEFAULT_ESCALATION_MESSAGE


def make_respond_node():
    def respond_node(state: Dict[str, Any]) -> Dict[str, Any]:
        answer = state.get("answer")
        if answer:
            sources = state.get("answer_sources") or []
            if sources and not any(s in answer for s in sources):
                answer = answer + "\n\n📖 출처: " + ", ".join(sources)
            return {"response": answer}
        return {"response": state.get("escalation_message") or DEFAULT_ESCALATION_MESSAGE}

    return respond_node
```

`backend/nodes/save.py`:
```python
"""VOC 이력 저장 노드 — 저장 실패해도 응답을 막지 않는다 (스펙 §4.5)."""
from typing import Any, Callable, Dict

from backend.models import VocRecord


def make_save_node(session_factory: Callable):
    def save_node(state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            db = session_factory()
            try:
                record = VocRecord(
                    session_id=state.get("session_id") or "anonymous",
                    voc_text=state["voc_text"],
                    category=state.get("category", "기타"),
                    priority=state.get("priority", "medium"),
                    answer=state.get("answer"),
                    answer_sources=state.get("answer_sources") or [],
                    escalated=bool(state.get("escalated")),
                    escalation_reason=state.get("escalation_reason"),
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                return {"voc_id": record.id}
            finally:
                db.close()
        except Exception as exc:
            print(f"[save] DB 저장 실패 (응답은 계속 반환): {exc}")
            return {"voc_id": None, "error": f"save 실패: {exc}"}

    return save_node
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_escalate_respond_save.py -v
```
Expected: PASS 10건

- [ ] **Step 5: 커밋**

```bash
git add backend/nodes/escalate.py backend/nodes/respond.py backend/nodes/save.py tests/test_escalate_respond_save.py
git commit -m "feat: 에스컬레이션·응답 조립·이력 저장 노드

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: LangGraph 그래프 조립

**Files:**
- Create: `backend/agent.py`
- Test: `tests/test_agent_graph.py`

**Interfaces:**
- Consumes: `AgentState` (Task 5), `make_*_node` 팩토리 6종 (Task 5~7), `load_manual` (Task 4), `db_session_factory` fixture (Task 1)
- Produces:
  - `route_after_classify(state: Dict[str, Any]) -> str` — `"retrieve"` 또는 `"escalate"` 반환
  - `build_graph(provider, manual_chunks=None, session_factory=None)` — 컴파일된 LangGraph 반환
  - `run_tika_agent(voc_text: str, session_id: str, provider=None, session_factory=None) -> Dict[str, Any]` — 최종 state 반환 (Task 9의 API가 사용)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_agent_graph.py`:
```python
from backend.agent import route_after_classify, run_tika_agent
from tests.fakes import FakeProvider

CLASSIFY_HOWTO = '{"category": "사용법문의", "priority": "low"}'
CLASSIFY_BUG = '{"category": "버그제보", "priority": "high"}'


def test_route_규칙():
    assert route_after_classify({"category": "사용법문의"}) == "retrieve"
    assert route_after_classify({"category": "칭찬"}) == "retrieve"
    assert route_after_classify({"category": "불만", "priority": "low"}) == "retrieve"
    assert route_after_classify({"category": "불만", "priority": "high"}) == "escalate"
    assert route_after_classify({"category": "불만", "priority": "medium"}) == "escalate"
    assert route_after_classify({"category": "버그제보"}) == "escalate"
    assert route_after_classify({"category": "기능요청"}) == "escalate"
    assert route_after_classify({"category": "기타"}) == "escalate"


def test_전체_그래프_답변_경로(db_session_factory):
    provider = FakeProvider([
        CLASSIFY_HOWTO,
        "완료된 항목은 목록 아래 완료됨 영역에 있습니다.\n📖 출처: 03-ui-guide#완료된 할 일 보기",
    ])
    result = run_tika_agent(
        "완료한 할 일이 목록에서 안 보여요",
        "s1",
        provider=provider,
        session_factory=db_session_factory,
    )
    assert result["category"] == "사용법문의"
    assert result["escalated"] is False
    assert isinstance(result["voc_id"], int)
    assert "📖 출처" in result["response"]
    assert result["answer_sources"]


def test_전체_그래프_에스컬레이션_경로(db_session_factory):
    provider = FakeProvider([
        CLASSIFY_BUG,
        "접수했습니다. 담당자가 확인할 것입니다.",
    ])
    result = run_tika_agent(
        "앱을 켜면 바로 꺼집니다",
        "s2",
        provider=provider,
        session_factory=db_session_factory,
    )
    assert result["escalated"] is True
    assert result["voc_id"] is not None
    assert "접수했습니다" in result["response"]


def test_그래프_LLM_전체_실패시에도_폴백_응답(db_session_factory):
    provider = FakeProvider([])  # 모든 generate가 실패
    result = run_tika_agent(
        "이상해요",
        "s3",
        provider=provider,
        session_factory=db_session_factory,
    )
    assert result["category"] == "기타"  # classify 폴백
    assert result["escalated"] is True   # 기타 → escalate 경로
    assert result["response"]            # 응답은 존재
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_agent_graph.py -v
```
Expected: FAIL — `No module named 'backend.agent'`

- [ ] **Step 3: 최소 구현**

`backend/agent.py`:
```python
"""tika-agent LangGraph 그래프 — VOC 조건부 파이프라인 (스펙 §4.1).

classify → (route) → retrieve → answer → respond → save → END
                └────→ escalate ──↗
"""
from typing import Any, Callable, Dict, List, Optional

from langgraph.graph import END, START, StateGraph

from backend.llm.base import LLMProvider
from backend.manual_retrieval import ManualChunk, load_manual
from backend.nodes.answer import make_answer_node
from backend.nodes.classify import make_classify_node
from backend.nodes.escalate import make_escalate_node
from backend.nodes.respond import make_respond_node
from backend.nodes.retrieve import make_retrieve_node
from backend.nodes.save import make_save_node
from backend.state import AgentState


def route_after_classify(state: Dict[str, Any]) -> str:
    """분류 결과에 따른 경로 결정 (스펙 §4.2)."""
    category = state.get("category")
    priority = state.get("priority")
    if category in ("사용법문의", "칭찬"):
        return "retrieve"
    if category == "불만" and priority == "low":
        return "retrieve"
    return "escalate"


def build_graph(
    provider: Optional[LLMProvider],
    manual_chunks: Optional[List[ManualChunk]] = None,
    session_factory: Optional[Callable] = None,
):
    chunks = manual_chunks if manual_chunks is not None else load_manual()
    builder = StateGraph(AgentState)

    builder.add_node("classify", make_classify_node(provider))
    builder.add_node("retrieve", make_retrieve_node(chunks))
    builder.add_node("answer", make_answer_node(provider))
    builder.add_node("escalate", make_escalate_node(provider))
    builder.add_node("respond", make_respond_node())
    builder.add_node("save", make_save_node(session_factory))

    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        route_after_classify,
        {"retrieve": "retrieve", "escalate": "escalate"},
    )
    builder.add_edge("retrieve", "answer")
    builder.add_edge("answer", "respond")
    builder.add_edge("escalate", "respond")
    builder.add_edge("respond", "save")
    builder.add_edge("save", END)

    return builder.compile()


def run_tika_agent(
    voc_text: str,
    session_id: str,
    provider: Optional[LLMProvider] = None,
    session_factory: Optional[Callable] = None,
) -> Dict[str, Any]:
    """VOC 하나를 그래프로 처리하고 최종 state를 반환."""
    graph = build_graph(provider=provider, session_factory=session_factory)
    initial_state: AgentState = {"voc_text": voc_text, "session_id": session_id}
    return graph.invoke(initial_state)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_agent_graph.py -v
pytest -q  # 전체 회귀
```
Expected: 그래프 테스트 4건 PASS + 기존 전체 PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/agent.py tests/test_agent_graph.py
git commit -m "feat: LangGraph 조건부 그래프 조립 — 답변/에스컬레이션 경로 분기

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 9: FastAPI 앱 + API 전체

**Files:**
- Create: `backend/schemas.py`, `backend/main.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `run_tika_agent` (Task 8), `get_llm_provider` (Task 2), `VocRecord`/`SessionLocal`/`init_database` (Task 1), `ESCALATION_STATUSES` (Task 1), `settings` (Task 1)
- Produces:
  - `create_app(provider=None, session_factory=None) -> FastAPI` — 테스트 주입용 앱 팩토리 (module-level `app = create_app()` 포함)
  - 엔드포인트: `POST /api/chat`, `GET /api/vocs`, `GET /api/vocs/{id}`, `PATCH /api/vocs/{id}/status`, `GET /api/stats`, `GET /health` (스펙 §6.1)
  - Pydantic 모델: `ChatRequest{voc_text, session_id}`, `ChatResponse{response, category, priority, escalated, sources, voc_id, session_id}`, `VocOut`, `VocStatusUpdate{status}`, `StatsResponse{total, by_category, escalated_open, by_day}`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_api.py`:
```python
from fastapi.testclient import TestClient

from backend.main import create_app
from tests.fakes import FakeProvider

CLASSIFY_HOWTO = '{"category": "사용법문의", "priority": "low"}'
CLASSIFY_BUG = '{"category": "버그제보", "priority": "high"}'


def make_provider(responses):
    return FakeProvider(responses)


def test_chat_정상_답변_경로():
    app = create_app(provider=make_provider([
        CLASSIFY_HOWTO,
        "완료됨 영역을 펼쳐 보세요.\n📖 출처: 03-ui-guide#완료된 할 일 보기",
    ]))
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


def test_chat_에스컬레이션_경로():
    app = create_app(provider=make_provider([CLASSIFY_BUG, "접수했습니다."]))
    client = TestClient(app)

    resp = client.post("/api/chat", json={"voc_text": "앱이 꺼져요", "session_id": "s2"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["escalated"] is True


def test_chat_빈_텍스트_422():
    app = create_app(provider=make_provider([]))
    client = TestClient(app)
    resp = client.post("/api/chat", json={"voc_text": "", "session_id": "s"})
    assert resp.status_code == 422


def test_llm_미설정시_503(monkeypatch):
    from backend import config

    monkeypatch.setattr(config.settings, "llm_api_key", "")
    app = create_app(provider=None)
    client = TestClient(app)
    resp = client.post("/api/chat", json={"voc_text": "안녕", "session_id": "s"})
    assert resp.status_code == 503
    assert "LLM_API_KEY" in resp.json()["detail"]


def test_vocs_목록_필터():
    provider = make_provider([
        CLASSIFY_HOWTO,
        "답변입니다.\n📖 출처: 03-ui-guide#완료된 할 일 보기",
        CLASSIFY_BUG,
        "접수했습니다.",
    ])
    app = create_app(provider=provider)
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


def test_voc_단건_조회_404():
    app = create_app(provider=make_provider([]))
    client = TestClient(app)
    resp = client.get("/api/vocs/9999")
    assert resp.status_code == 404


def test_status_토글():
    app = create_app(provider=make_provider([CLASSIFY_BUG, "접수했습니다."]))
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


def test_stats():
    provider = make_provider([
        CLASSIFY_HOWTO,
        "답변입니다.\n📖 출처: 03-ui-guide#완료된 할 일 보기",
        CLASSIFY_BUG,
        "접수했습니다.",
    ])
    app = create_app(provider=provider)
    client = TestClient(app)
    client.post("/api/chat", json={"voc_text": "완료 안 보여요", "session_id": "a"})
    client.post("/api/chat", json={"voc_text": "꺼져요", "session_id": "b"})

    stats = client.get("/api/stats").json()
    assert stats["total"] == 2
    assert stats["by_category"]["사용법문의"] == 1
    assert stats["by_category"]["버그제보"] == 1
    assert stats["escalated_open"] == 1
    assert len(stats["by_day"]) == 7


def test_health():
    app = create_app(provider=make_provider([]))
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_api.py -v
```
Expected: FAIL — `No module named 'backend.schemas'` / `'backend.main'`

- [ ] **Step 3: 최소 구현**

`backend/schemas.py`:
```python
"""API 요청/응답 스키마 (스펙 §6.1)."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    voc_text: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default="anonymous", max_length=64)


class ChatResponse(BaseModel):
    response: str
    category: str
    priority: str
    escalated: bool
    sources: List[str] = []
    voc_id: Optional[int] = None
    session_id: str


class VocOut(BaseModel):
    id: int
    session_id: str
    voc_text: str
    category: str
    priority: str
    answer: Optional[str] = None
    answer_sources: Optional[List[str]] = None
    escalated: bool
    escalation_reason: Optional[str] = None
    escalation_status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # ORM 객체 직접 변환


class VocStatusUpdate(BaseModel):
    status: str  # open | resolved


class StatsResponse(BaseModel):
    total: int
    by_category: dict
    escalated_open: int
    by_day: List[dict]  # 최근 7일 [{"date": "2026-08-18", "count": 3}]
```

`backend/main.py`:
```python
"""tika-agent FastAPI 애플리케이션 (스펙 §6.1)."""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.agent import run_tika_agent
from backend.config import settings
from backend.constants import ESCALATION_STATUSES
from backend.database import SessionLocal, init_database
from backend.llm import get_llm_provider
from backend.models import VocRecord
from backend.schemas import (
    ChatRequest,
    ChatResponse,
    StatsResponse,
    VocOut,
    VocStatusUpdate,
)


def create_app(provider=None, session_factory=None) -> FastAPI:
    """앱 팩토리 — 테스트에서 provider/session_factory를 주입한다."""
    app = FastAPI(title="tika-agent API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 개발 모드 전체 허용 (tpssAgent와 동일)
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    init_database()
    app.state.provider = provider
    app.state.session_factory = session_factory or SessionLocal

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(request: ChatRequest):
        provider = app.state.provider or get_llm_provider(settings)
        app.state.provider = provider
        if provider is None:
            raise HTTPException(
                status_code=503,
                detail="LLM이 설정되지 않았습니다. .env의 LLM_API_KEY를 확인하세요.",
            )
        result = run_tika_agent(
            voc_text=request.voc_text,
            session_id=request.session_id,
            provider=provider,
            session_factory=app.state.session_factory,
        )
        return ChatResponse(
            response=result.get("response", ""),
            category=result.get("category", "기타"),
            priority=result.get("priority", "medium"),
            escalated=bool(result.get("escalated")),
            sources=result.get("answer_sources") or [],
            voc_id=result.get("voc_id"),
            session_id=request.session_id,
        )

    @app.get("/api/vocs", response_model=List[VocOut])
    def list_vocs(
        category: Optional[str] = None,
        escalated: Optional[bool] = None,
        status: Optional[str] = None,
        limit: int = Query(default=100, le=500),
    ):
        db = app.state.session_factory()
        try:
            query = db.query(VocRecord).order_by(VocRecord.created_at.desc())
            if category:
                query = query.filter(VocRecord.category == category)
            if escalated is not None:
                query = query.filter(VocRecord.escalated == escalated)
            if status:
                query = query.filter(VocRecord.escalation_status == status)
            return query.limit(limit).all()
        finally:
            db.close()

    @app.get("/api/vocs/{voc_id}", response_model=VocOut)
    def get_voc(voc_id: int):
        db = app.state.session_factory()
        try:
            record = db.query(VocRecord).filter(VocRecord.id == voc_id).first()
            if record is None:
                raise HTTPException(status_code=404, detail="VOC를 찾을 수 없습니다")
            return record
        finally:
            db.close()

    @app.patch("/api/vocs/{voc_id}/status", response_model=VocOut)
    def update_status(voc_id: int, payload: VocStatusUpdate):
        if payload.status not in ESCALATION_STATUSES:
            raise HTTPException(status_code=422, detail="status는 open 또는 resolved여야 합니다")
        db = app.state.session_factory()
        try:
            record = db.query(VocRecord).filter(VocRecord.id == voc_id).first()
            if record is None:
                raise HTTPException(status_code=404, detail="VOC를 찾을 수 없습니다")
            record.escalation_status = payload.status
            record.resolved_at = datetime.utcnow() if payload.status == "resolved" else None
            db.commit()
            db.refresh(record)
            return record
        finally:
            db.close()

    @app.get("/api/stats", response_model=StatsResponse)
    def stats():
        db = app.state.session_factory()
        try:
            records = db.query(VocRecord).all()
            by_category: dict = {}
            for r in records:
                by_category[r.category] = by_category.get(r.category, 0) + 1
            escalated_open = sum(
                1 for r in records if r.escalated and r.escalation_status == "open"
            )
            by_day: dict = {}
            today = datetime.utcnow().date()
            for offset in range(6, -1, -1):
                by_day[(today - timedelta(days=offset)).isoformat()] = 0
            for r in records:
                key = r.created_at.date().isoformat()
                if key in by_day:
                    by_day[key] += 1
            return StatsResponse(
                total=len(records),
                by_category=by_category,
                escalated_open=escalated_open,
                by_day=[{"date": d, "count": c} for d, c in by_day.items()],
            )
        finally:
            db.close()

    @app.get("/health")
    def health():
        provider_ready = app.state.provider is not None or get_llm_provider(settings) is not None
        return {"status": "ok", "llm_configured": provider_ready}

    return app


app = create_app()
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_api.py -v
pytest -q  # 전체 회귀
```
Expected: API 테스트 9건 PASS + 전체 PASS

- [ ] **Step 5: 서버 기동 스모크 테스트 (수동)**

```bash
docker compose up -d postgres
cp .env.example .env   # LLM_API_KEY 실제 키 입력
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
# 다른 터미널에서:
curl -s http://localhost:8000/health
```
Expected: `{"status":"ok","llm_configured":true}` — 실패 시 `.env`/postgres 상태 점검

- [ ] **Step 6: 커밋**

```bash
git add backend/schemas.py backend/main.py tests/test_api.py
git commit -m "feat: FastAPI 앱 — chat/VOC 목록/상태 토글/통계/헬스 API

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 10: 프론트엔드 — 챗 뷰

**Files:**
- Create: `frontend/` (Vite scaffold), `frontend/src/services/api.js`, `frontend/src/utils/markdown.js`, `frontend/src/utils/markdown.spec.js`, `frontend/src/views/ChatView.vue`, `frontend/src/components/ChatMessage.vue`, `frontend/src/router/index.js`
- Modify: `frontend/src/App.vue`(스캐폴드 기본 교체), `frontend/src/main.js`, `frontend/package.json`(스크립트)
- Delete: 스크롤드 기본 파일(`frontend/src/components/HelloWorld.vue`, `frontend/src/style.css` 등 scaffold 부산물)

**Interfaces:**
- Consumes: `POST /api/chat` 응답 (Task 9) — `{response, category, priority, escalated, sources, voc_id, session_id}`
- Produces:
  - `chat(vocText: string, sessionId: string)`, `getVocs(params)`, `patchVocStatus(id, status)`, `getStats()`, `getSessionId()` (services/api.js) — Task 11이 사용
  - `renderMarkdown(md: string) -> string` (utils/markdown.js) — HTML 이스케이프 포함
  - 라우트 `/` (ChatView), `/dashboard` (Task 11이 추가)

- [ ] **Step 1: Vite 스캐폴드 + 의존성**

```bash
cd /Users/prodigyduck/git/tika-agent
npm create vite@latest frontend -- --template vue
cd frontend
npm install
npm install vue-router@4
npm install -D vitest
cd ..
```

scaffold 부산물 정리: `frontend/src/components/HelloWorld.vue`, `frontend/src/style.css`, `frontend/src/assets/vue.svg` 삭제.

`frontend/package.json` scripts에 추가:
```json
"test": "vitest run"
```

- [ ] **Step 2: 실패하는 테스트 작성 (마크다운 파서)**

`frontend/src/utils/markdown.spec.js`:
```javascript
import { describe, expect, it } from 'vitest'
import { renderMarkdown } from './markdown'

describe('renderMarkdown', () => {
  it('볼드를 strong으로 변환', () => {
    expect(renderMarkdown('**증상**: 안 보여요')).toContain('<strong>증상</strong>')
  })

  it('번호 목록을 ul/li로 변환', () => {
    const html = renderMarkdown('1. 새로고침\n2. 재시작')
    expect(html).toContain('<ul>')
    expect(html).toContain('<li>새로고침</li>')
    expect(html).toContain('<li>재시작</li>')
  })

  it('하이픈 목록을 ul/li로 변환', () => {
    const html = renderMarkdown('- 첫째\n- 둘째')
    expect(html).toContain('<li>첫째</li>')
  })

  it('h3 제목 변환', () => {
    expect(renderMarkdown('### 접수 안내')).toContain('<h3>접수 안내</h3>')
  })

  it('HTML을 이스케이프해 XSS 방지', () => {
    expect(renderMarkdown('<script>alert(1)</script>')).not.toContain('<script>')
  })

  it('빈 입력은 빈 문자열', () => {
    expect(renderMarkdown('')).toBe('')
  })
})
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

```bash
cd frontend && npm test
```
Expected: FAIL — `Cannot find module './markdown'`

- [ ] **Step 4: 구현 — api.js / markdown.js / 라우터 / 뷰**

`frontend/src/services/api.js`:
```javascript
// tika-agent 백엔드 API 클라이언트
const BASE_URL = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `요청 실패 (${res.status})`)
  }
  return res.json()
}

export function chat(vocText, sessionId) {
  return request('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ voc_text: vocText, session_id: sessionId }),
  })
}

export function getVocs(params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== '' && v !== undefined && v !== null)
  ).toString()
  return request(`/api/vocs${qs ? '?' + qs : ''}`)
}

export function patchVocStatus(id, status) {
  return request(`/api/vocs/${id}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
}

export function getStats() {
  return request('/api/stats')
}

export function getSessionId() {
  let id = sessionStorage.getItem('tika_session_id')
  if (!id) {
    id = 's-' + Math.random().toString(36).slice(2, 10)
    sessionStorage.setItem('tika_session_id', id)
  }
  return id
}
```

`frontend/src/utils/markdown.js`:
```javascript
// 간단 마크다운 렌더러 — tpssAgent 커스텀 파서의 축소판 (스펙 §6.2)
function escapeHtml(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function inline(text) {
  return text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
}

export function renderMarkdown(md) {
  if (!md) return ''
  const lines = escapeHtml(md).split('\n')
  const out = []
  let inList = false
  const closeList = () => {
    if (inList) {
      out.push('</ul>')
      inList = false
    }
  }
  for (const line of lines) {
    const trimmed = line.trim()
    if (/^###\s+/.test(trimmed)) {
      closeList()
      out.push(`<h3>${inline(trimmed.replace(/^###\s+/, ''))}</h3>`)
    } else if (/^[-*]\s+/.test(trimmed) || /^\d+\.\s+/.test(trimmed)) {
      if (!inList) {
        out.push('<ul>')
        inList = true
      }
      const item = trimmed.replace(/^[-*]\s+/, '').replace(/^\d+\.\s+/, '')
      out.push(`<li>${inline(item)}</li>`)
    } else if (trimmed === '') {
      closeList()
    } else {
      closeList()
      out.push(`<p>${inline(trimmed)}</p>`)
    }
  }
  closeList()
  return out.join('')
}
```

`frontend/src/router/index.js`:
```javascript
import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: '/', name: 'chat', component: ChatView }],
})

export default router
```

`frontend/src/main.js`:
```javascript
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './assets/main.css'

createApp(App).use(router).mount('#app')
```
(`frontend/src/assets/main.css`는 기존 `style.css`를 이 이름으로 교체)

`frontend/src/App.vue`:
```vue
<script setup>
</script>

<template>
  <div class="app">
    <nav class="nav">
      <span class="brand">tika-agent</span>
      <div class="links">
        <RouterLink to="/">VOC 챗</RouterLink>
        <RouterLink to="/dashboard">대시보드</RouterLink>
      </div>
    </nav>
    <RouterView />
  </div>
</template>
```
(Task 11 전까지 `/dashboard` 링크는 404 — 순서 문제 없음, 링크만 미리 배치)

`frontend/src/assets/main.css`:
```css
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f6f8; color: #1f2937; }
#app { min-height: 100vh; }
.app { max-width: 860px; margin: 0 auto; padding: 0 16px 48px; }
.nav { display: flex; justify-content: space-between; align-items: center; padding: 16px 4px; }
.brand { font-weight: 700; font-size: 18px; }
.links a { margin-left: 16px; text-decoration: none; color: #2563eb; }
.links a.router-link-active { font-weight: 700; text-decoration: underline; }
```

`frontend/src/components/ChatMessage.vue`:
```vue
<script setup>
import { renderMarkdown } from '../utils/markdown'

// 분류 유형별 배지 색상 (스펙 §6.2)
const CATEGORY_COLORS = {
  사용법문의: '#2563eb',
  버그제보: '#dc2626',
  기능요청: '#7c3aed',
  불만: '#ea580c',
  칭찬: '#16a34a',
  기타: '#6b7280',
}

defineProps({
  message: { type: Object, required: true },
})
</script>

<template>
  <div class="message" :class="message.role">
    <div v-if="message.role === 'agent'" class="badges">
      <span
        class="badge"
        :style="{ background: CATEGORY_COLORS[message.category] || '#6b7280' }"
      >
        {{ message.category }}
      </span>
      <span v-if="message.escalated" class="badge escalate">⚠ 사람 확인 필요</span>
    </div>
    <div class="bubble" v-html="renderMarkdown(message.content)"></div>
  </div>
</template>

<style scoped>
.message { display: flex; flex-direction: column; margin: 8px 0; }
.message.user { align-items: flex-end; }
.message.agent { align-items: flex-start; }
.bubble { max-width: 78%; padding: 10px 14px; border-radius: 14px; line-height: 1.55; }
.message.user .bubble { background: #2563eb; color: #fff; border-bottom-right-radius: 4px; }
.message.agent .bubble { background: #fff; border: 1px solid #e5e7eb; border-bottom-left-radius: 4px; }
.bubble :deep(h3) { margin: 6px 0 4px; font-size: 15px; }
.bubble :deep(ul) { margin: 4px 0; padding-left: 20px; }
.badges { display: flex; gap: 6px; margin-bottom: 4px; }
.badge { font-size: 12px; color: #fff; padding: 2px 8px; border-radius: 10px; }
.badge.escalate { background: #b45309; }
</style>
```

`frontend/src/views/ChatView.vue`:
```vue
<script setup>
import { nextTick, ref } from 'vue'
import { chat, getSessionId } from '../services/api'
import ChatMessage from '../components/ChatMessage.vue'

// 프리셋 질문 칩 (스펙 §6.2)
const PRESETS = [
  '완료한 할 일이 목록에서 안 보여요',
  '할 일을 삭제하려면 어떻게 하나요?',
  '입력한 할 일이 사라졌어요',
  '이메일로 목록을 보내고 싶어요',
]

const messages = ref([])
const input = ref('')
const waiting = ref(false)
const error = ref('')
const listEl = ref(null)

async function send(text) {
  const vocText = (text ?? input.value).trim()
  if (!vocText || waiting.value) return
  input.value = ''
  error.value = ''
  messages.value.push({ role: 'user', content: vocText })
  waiting.value = true
  try {
    const data = await chat(vocText, getSessionId())
    messages.value.push({
      role: 'agent',
      content: data.response,
      category: data.category,
      escalated: data.escalated,
      sources: data.sources,
    })
  } catch (e) {
    error.value = `에이전트에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요. (${e.message})`
  } finally {
    waiting.value = false
    await nextTick()
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
  }
}
</script>

<template>
  <section class="chat">
    <div class="message-list" ref="listEl">
      <div v-if="messages.length === 0" class="empty">
        <h2>tika VOC 에이전트</h2>
        <p>tika 사용 중 불편하거나 궁금한 점을 입력해 주세요.</p>
      </div>
      <ChatMessage v-for="(m, i) in messages" :key="i" :message="m" />
      <div v-if="waiting" class="message agent">
        <div class="bubble typing">답변 작성 중...</div>
      </div>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="presets">
      <button v-for="p in PRESETS" :key="p" :disabled="waiting" @click="send(p)">
        {{ p }}
      </button>
    </div>
    <form class="input-row" @submit.prevent="send()">
      <input
        v-model="input"
        placeholder="예: 할 일이 저장되지 않아요"
        :disabled="waiting"
      />
      <button type="submit" :disabled="waiting || !input.trim()">보내기</button>
    </form>
  </section>
</template>

<style scoped>
.chat { display: flex; flex-direction: column; height: calc(100vh - 140px); }
.message-list { flex: 1; overflow-y: auto; padding: 12px 4px; }
.empty { text-align: center; color: #6b7280; margin-top: 80px; }
.typing { color: #6b7280; }
.error { color: #dc2626; font-size: 14px; margin: 4px 0; }
.presets { display: flex; flex-wrap: wrap; gap: 8px; padding: 8px 0; }
.presets button { border: 1px solid #d1d5db; background: #fff; border-radius: 16px; padding: 6px 12px; font-size: 13px; cursor: pointer; }
.presets button:hover { border-color: #2563eb; color: #2563eb; }
.input-row { display: flex; gap: 8px; }
.input-row input { flex: 1; padding: 12px 14px; border: 1px solid #d1d5db; border-radius: 10px; font-size: 15px; }
.input-row button { padding: 12px 20px; border: none; background: #2563eb; color: #fff; border-radius: 10px; font-size: 15px; cursor: pointer; }
.input-row button:disabled { background: #93c5fd; cursor: not-allowed; }
</style>
```

- [ ] **Step 5: 테스트 실행 — 통과 확인 + 빌드**

```bash
cd frontend && npm test && npm run build
```
Expected: vitest 6건 PASS, `npm run build` 성공

- [ ] **Step 6: 수동 스모크 (백엔드 기동 상태)**

```bash
cd frontend && npm run dev
```
브라우저 http://localhost:5173 — 프리셋 침 "완료한 할 일이 목록에서 안 보여요" 클릭 → 분류 배지 + 출처 포함 답변 표시 확인

- [ ] **Step 7: 커밋**

```bash
git add frontend/
git commit -m "feat: Vue3 챗 뷰 — 분류 배지, 출처 표기, 프리셋 칩, 마크다운 렌더

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 11: 프론트엔드 — 대시보드 뷰

**Files:**
- Create: `frontend/src/views/DashboardView.vue`, `frontend/src/components/StatsCards.vue`, `frontend/src/components/EscalationTable.vue`
- Modify: `frontend/src/router/index.js` (dashboard 라우트 추가)

**Interfaces:**
- Consumes: `getVocs`, `patchVocStatus`, `getStats` (Task 10 api.js), 응답 형태는 Task 9 스키마(`VocOut`, `StatsResponse`)
- Produces: 라우트 `/dashboard` — 통계 카드, 유형별 분포 바 차트, 에스컬레이션 테이블(상태 토글), VOC 이력 필터

- [ ] **Step 1: 라우트 등록**

`frontend/src/router/index.js` 수정:
```javascript
import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import DashboardView from '../views/DashboardView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'chat', component: ChatView },
    { path: '/dashboard', name: 'dashboard', component: DashboardView },
  ],
})

export default router
```

- [ ] **Step 2: 컴포넌트 구현**

`frontend/src/components/StatsCards.vue`:
```vue
<script setup>
defineProps({
  stats: { type: Object, default: null },
})
</script>

<template>
  <div class="cards" v-if="stats">
    <div class="card">
      <span class="num">{{ stats.total }}</span>
      <span class="label">총 VOC</span>
    </div>
    <div class="card warn">
      <span class="num">{{ stats.escalated_open }}</span>
      <span class="label">미해결 에스컬레이션</span>
    </div>
    <div class="card">
      <span class="num">{{ Object.keys(stats.by_category).length }}</span>
      <span class="label">분류 유형 수</span>
    </div>
  </div>
</template>

<style scoped>
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 12px 0; }
.card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; display: flex; flex-direction: column; }
.card.warn { border-color: #f59e0b; }
.num { font-size: 28px; font-weight: 700; }
.label { font-size: 13px; color: #6b7280; margin-top: 4px; }
</style>
```

`frontend/src/components/EscalationTable.vue`:
```vue
<script setup>
defineProps({
  vocs: { type: Array, default: () => [] },
})
const emit = defineEmits(['toggle'])
</script>

<template>
  <div>
    <table class="escalation-table" v-if="vocs.length">
      <thead>
        <tr>
          <th>ID</th><th>VOC</th><th>유형</th><th>사유</th><th>상태</th><th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="v in vocs" :key="v.id" :class="{ open: v.escalation_status === 'open' }">
          <td>{{ v.id }}</td>
          <td class="voc-text">{{ v.voc_text }}</td>
          <td>{{ v.category }}</td>
          <td class="voc-text">{{ v.escalation_reason || '-' }}</td>
          <td>
            <span class="status" :class="v.escalation_status">{{ v.escalation_status }}</span>
          </td>
          <td>
            <button @click="emit('toggle', v)">
              {{ v.escalation_status === 'open' ? '해결 완료' : '다시 열기' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">에스컬레이션된 VOC가 없습니다.</p>
  </div>
</template>

<style scoped>
.escalation-table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; font-size: 14px; }
th, td { padding: 8px 10px; border-bottom: 1px solid #f3f4f6; text-align: left; }
th { background: #f9fafb; font-size: 13px; color: #6b7280; }
.voc-text { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
tr.open { background: #fffbeb; }
.status { padding: 2px 8px; border-radius: 10px; font-size: 12px; }
.status.open { background: #fef3c7; color: #b45309; }
.status.resolved { background: #dcfce7; color: #15803d; }
button { border: 1px solid #d1d5db; background: #fff; border-radius: 8px; padding: 4px 10px; cursor: pointer; font-size: 13px; }
.empty { color: #6b7280; text-align: center; padding: 24px; }
</style>
```

`frontend/src/views/DashboardView.vue`:
```vue
<script setup>
import { onMounted, ref } from 'vue'
import { getStats, getVocs, patchVocStatus } from '../services/api'
import EscalationTable from '../components/EscalationTable.vue'
import StatsCards from '../components/StatsCards.vue'

const CATEGORIES = ['사용법문의', '버그제보', '기능요청', '불만', '칭찬', '기타']

const stats = ref(null)
const vocs = ref([])
const error = ref('')
const loading = ref(false)
const filterCategory = ref('')
const onlyEscalated = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = {}
    if (filterCategory.value) params.category = filterCategory.value
    if (onlyEscalated.value) params.escalated = true
    const [s, v] = await Promise.all([getStats(), getVocs(params)])
    stats.value = s
    vocs.value = v
  } catch (e) {
    error.value = `대시보드를 불러올 수 없습니다. 백엔드가 실행 중인지 확인하세요. (${e.message})`
  } finally {
    loading.value = false
  }
}

async function toggleStatus(voc) {
  const next = voc.escalation_status === 'open' ? 'resolved' : 'open'
  try {
    await patchVocStatus(voc.id, next)
    await load()
  } catch (e) {
    error.value = `상태 변경 실패: ${e.message}`
  }
}

function barWidth(count) {
  const values = Object.values(stats.value?.by_category || {})
  const max = Math.max(1, ...values)
  return Math.round((count / max) * 100) + '%'
}

onMounted(load)
</script>

<template>
  <section class="dashboard">
    <h1>VOC 대시보드</h1>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="loading">불러오는 중...</p>

    <StatsCards :stats="stats" />

    <div class="chart" v-if="stats">
      <h3>유형별 분포</h3>
      <div v-for="(count, cat) in stats.by_category" :key="cat" class="bar-row">
        <span class="bar-label">{{ cat }}</span>
        <div class="bar-track">
          <div class="bar" :style="{ width: barWidth(count) }"></div>
        </div>
        <span class="bar-count">{{ count }}</span>
      </div>
    </div>

    <h3>에스컬레이션</h3>
    <EscalationTable :vocs="vocs.filter((v) => v.escalated)" @toggle="toggleStatus" />

    <div class="filters">
      <h3>VOC 이력</h3>
      <select v-model="filterCategory" @change="load">
        <option value="">전체 유형</option>
        <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
      </select>
      <label>
        <input type="checkbox" v-model="onlyEscalated" @change="load" />
        에스컬레이션만
      </label>
    </div>
    <table class="voc-table" v-if="vocs.length">
      <thead>
        <tr><th>ID</th><th>VOC</th><th>유형</th><th>우선순위</th><th>에스컬레이션</th><th>등록</th></tr>
      </thead>
      <tbody>
        <tr v-for="v in vocs" :key="v.id">
          <td>{{ v.id }}</td>
          <td class="voc-text">{{ v.voc_text }}</td>
          <td>{{ v.category }}</td>
          <td>{{ v.priority }}</td>
          <td>{{ v.escalated ? '예' : '아니오' }}</td>
          <td>{{ new Date(v.created_at).toLocaleString('ko-KR') }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">해당 조건의 VOC가 없습니다.</p>
  </section>
</template>

<style scoped>
h1 { font-size: 22px; margin: 8px 0; }
h3 { margin: 16px 0 8px; font-size: 15px; }
.error { color: #dc2626; }
.loading { color: #6b7280; }
.chart { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px 16px; }
.bar-row { display: flex; align-items: center; gap: 10px; margin: 6px 0; }
.bar-label { width: 80px; font-size: 13px; text-align: right; }
.bar-track { flex: 1; background: #f3f4f6; border-radius: 6px; height: 14px; }
.bar { background: #2563eb; border-radius: 6px; height: 14px; }
.bar-count { width: 32px; font-size: 13px; }
.filters { display: flex; align-items: center; gap: 12px; }
.filters select { padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 8px; }
.voc-table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; font-size: 14px; }
.voc-table th, .voc-table td { padding: 8px 10px; border-bottom: 1px solid #f3f4f6; text-align: left; }
.voc-table th { background: #f9fafb; font-size: 13px; color: #6b7280; }
.empty { color: #6b7280; text-align: center; padding: 24px; }
</style>
```

- [ ] **Step 3: 테스트 + 빌드**

```bash
cd frontend && npm test && npm run build
```
Expected: 기존 6건 PASS (회귀 없음), 빌드 성공

- [ ] **Step 4: 수동 스모크**

백엔드 기동 상태에서 http://localhost:5173/dashboard — 통계 카드/유형별 분포/에스컬레이션 표시, "해결 완료" 버튼으로 상태 토글 확인

- [ ] **Step 5: 커밋**

```bash
git add frontend/
git commit -m "feat: VOC 대시보드 — 통계 카드, 유형별 분포, 에스컬레이션 상태 토글

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 12: 개발 하네스 — .claude/agents + skills + CLAUDE.md

**Files:**
- Create: `.claude/agents/manual-writer.md`, `.claude/agents/backend-engineer.md`, `.claude/agents/frontend-engineer.md`, `.claude/agents/qa-engineer.md`
- Create: `.claude/skills/tika-orchestrator/SKILL.md`, `.claude/skills/manual-authoring/SKILL.md`, `.claude/skills/voc-pipeline/SKILL.md`, `.claude/skills/dashboard-ui/SKILL.md`
- Create: `CLAUDE.md` (프로젝트 루트)
- Create: `README.md` (프로젝트 루트 — 실행 가이드)

**Interfaces:**
- Consumes: 없음 (문서 태스크)
- Produces: tpssAgent 스타일 하네스 — 이후 기능 추가/개선 요청 시 `tika-orchestrator` 스킬로 구동하는 근거 (스펙 §7)

**참고 형식:** tpssAgent `~/git/tpssAgent/.claude/agents/qa-engineer.md`(frontmatter `name/description/model` + 책임/원칙/산출물), `~/git/tpssAgent/.claude/skills/tpss-phase23-orchestrator/SKILL.md`(frontmatter `name/description`)

- [ ] **Step 1: 에이전트 4종 작성**

`.claude/agents/manual-writer.md`:
```markdown
---
name: manual-writer
description: tika(todoapp-vue-spring) 코드를 분석해 사용자 메뉴얼을 작성·보강하는 에이전트. 메뉴얼 작성/수정 요청 시 사용.
model: sonnet
---

당신은 tika-agent 프로젝트의 **메뉴얼 작성 에이전트**입니다.

## 책임 영역

1. `~/git/todoapp-vue-spring` 소스 코드 분석 (프론트 `frontend/src/`, 백엔드 `backend/src/`)
2. `manual/` 폴더의 사용자 메뉴얼 작성·수정 (5종 + index.md)
3. 코드와 메뉴얼 내용의 일치 검증

## 작업 원칙

- 반드시 `superpowers:manual-authoring` 스킬의 구조 규칙을 따른다
- 모든 내용은 실제 코드에서 근거를 찾아 작성한다 — 추측 금지
- 메뉴얼 수정 후 반드시 `python scripts/lint_manual.py` 를 실행해 통과 확인
- 사용자 언어는 일반인 대상 한국어

## 산출물 규칙

- 검색 단위는 `##` 섹션 — 자기완결적으로 작성
- 문제 해결 문서는 증상/원인/해결 3단 구조 고정
- 코드 기반 사실과 일반적 권장(추정)을 구분해 작성
```

`.claude/agents/backend-engineer.md`:
```markdown
---
name: backend-engineer
description: tika-agent 백엔드(FastAPI + LangGraph) 구현 에이전트. 그래프 노드, API, LLM 추상화 개발 시 사용.
model: sonnet
---

당신은 tika-agent 프로젝트의 **백엔드 구현 에이전트**입니다.

## 책임 영역

1. LangGraph 그래프와 노드 (`backend/agent.py`, `backend/nodes/`)
2. FastAPI API (`backend/main.py`, `backend/schemas.py`)
3. LLM 추상화 (`backend/llm/`), 메뉴얼 검색 (`backend/manual_retrieval.py`)
4. DB 모델 (`backend/models.py`)

## 작업 원칙

- 반드시 `superpowers:voc-pipeline` 스킬의 TDD 체크리스트를 따른다
- LLM 호출은 항상 `LLMProvider` 뒤에서 — 테스트는 `tests/fakes.py`의 `FakeProvider` 사용
- 모든 실패 경로는 우아한 열화(스펙 §4.5) — 사용자에게 에러 대신 폴백 응답
- 로그는 print/콘솔만 — 로그 파일 생성 금지
- 노드는 `backend/nodes/`에 파일당 하나

## 산출물 규칙

- 테스트 통과 + `pytest -q` 전체 회귀 통과 후 커밋
- 커밋은 conventional commits 한국어 제목
```

`.claude/agents/frontend-engineer.md`:
```markdown
---
name: frontend-engineer
description: tika-agent 프론트엔드(Vue3) 구현 에이전트. 챗 뷰, 대시보드 UI 개발 시 사용.
model: sonnet
---

당신은 tika-agent 프로젝트의 **프론트엔드 구현 에이전트**입니다.

## 책임 영역

1. 챗 뷰 (`frontend/src/views/ChatView.vue`, `components/ChatMessage.vue`)
2. 대시보드 (`frontend/src/views/DashboardView.vue`, `components/StatsCards.vue`, `components/EscalationTable.vue`)
3. API 클라이언트 (`frontend/src/services/api.js`), 마크다운 렌더러 (`frontend/src/utils/markdown.js`)

## 작업 원칙

- 반드시 `superpowers:dashboard-ui` 스킬의 구현 지침을 따른다
- Vue3 Composition API(`<script setup>`)만 사용
- 백엔드 미가동 시 폴백 UI 표시 — 빈 화면 금지
- 마크다운 렌더는 `renderMarkdown()` 경유 — v-html에 원문 직접 삽입 금지(XSS)

## 산출물 규칙

- `npm test` (vitest) + `npm run build` 통과 후 커밋
- 스타일은 컴포넌트 scoped CSS로 국소화
```

`.claude/agents/qa-engineer.md`:
```markdown
---
name: qa-engineer
description: tika-agent 품질 게이트 에이전트. 단계 완료 검증, E2E 시나리오 실행, 커밋 승인 판정 시 사용.
model: sonnet
---

당신은 tika-agent 프로젝트의 **QA/품질 게이트 에이전트**입니다.

## 책임 영역

1. 백엔드 테스트 전체 실행 (`pytest -q`) — 실패 시 차단
2. 메뉴얼 린트 (`python scripts/lint_manual.py`) — 실패 시 차단
3. 프론트 테스트/빌드 (`cd frontend && npm test && npm run build`) — 실패 시 차단
4. E2E 시나리오 (`python scripts/e2e_check.py`) — 실제 LLM으로 5개 대표 VOC 검증
5. MVP 기준(스펙 §9) 6개 항목 체크 (`docs/qa/e2e-checklist.md`)

## 품질 게이트 (성공 지표)

- pytest 전체 통과 (FakeProvider 기반 전 경로 커버)
- 환각 방지: 메뉴얼에 근거 없는 VOC → 답변 생성 안 함 + 에스컬레이션
- E2E 시나리오 5개 중 분류/라우팅 기대치 충족
- 프론트 빌드 성공 + 수동 스모크 통과

## 산출물 규칙

- 게이트 통과 시에만 커밋 승인
- 미달 시 차단하고 재현 가능한 실패 내용 보고
- 결과는 `docs/qa/`에 문서화
```

- [ ] **Step 2: 스킬 4종 작성**

`.claude/skills/tika-orchestrator/SKILL.md`:
```markdown
---
name: tika-orchestrator
description: tika-agent 개발을 구동하는 멀티 에이전트 하네스 오케스트레이터. 기능 구현 시작/계속, 단계별 게이트 운영 시 사용.
---

# tika-agent 오케스트레이터

tika-agent 개발 작업을 에이전트에 위임하고 품질 게이트로 진행하는 하네스.

## 언제 사용하는가

- "구현 시작", "다음 단계 진행", "하네스로 진행" 등 명시적 요청
- 기능 추가·개선 요청을 받아 단위 작업으로 분해할 때

## 하네스 구성

- manual-writer → 메뉴얼 작성 (HOW: manual-authoring)
- backend-engineer → 그래프/API (HOW: voc-pipeline)
- frontend-engineer → 챗/대시보드 (HOW: dashboard-ui)
- qa-engineer → 게이트 검증 (모든 단계 완료 시)

## 진행 방식

1. 요청을 아래 의존 순서에 따라 단위 작업으로 분해한다
2. 의존 없는 작업은 병렬 위임한다
3. 각 작업 완료 시 qa-engineer 게이트 (pytest + lint + build) 를 통과해야 커밋
4. 게이트 실패 시 해당 에이전트에게 수정 위임 후 재검증

## 의존 그래프 (스펙 §7.2)

메뉴얼 ↔ LLM 추상화 (병렬 가능) → manual_retrieval → 그래프 → API → 프론트 → E2E
```

`.claude/skills/manual-authoring/SKILL.md`:
```markdown
---
name: manual-authoring
description: tika 사용자 메뉴얼 작성 방법 — 구조 규칙, 코드 근거 수집 절차, 검증 체크리스트.
---

# 메뉴얼 작성 방법

## 구조 규칙 (스펙 §5.2)

1. 검색 단위는 `##` 섹션 — 각 섹션은 자기완결적 (다른 섹션 의존 금지)
2. `04-troubleshooting.md`의 섹션은 **증상**/**원인**/**해결** 3단 구조 고정
3. `index.md`는 모든 문서를 언급
4. 문서: 01-getting-started / 02-managing-todos / 03-ui-guide / 04-troubleshooting / 05-faq

## 코드 근거 수집 절차

1. `~/git/todoapp-vue-spring/frontend/src/views/TodoList.vue` — 화면 구성·조작
2. `backend/src/main/java/com/example/todoapp/controller/TodoController.java` — 기능 목록
3. `entity/Todo.java`, `service/TodoService.java` — 데이터 구조·동작
4. `application.properties` — 저장 방식(H2 인메모리 등) → 문제 해결 문서 소재

## 검증 체크리스트

- [ ] `python scripts/lint_manual.py` 통과
- [ ] 새 섹션이 검색 가능한 키워드를 제목에 포함
- [ ] 코드에 없는 기능을 설명하지 않았는지 확인
```

`.claude/skills/voc-pipeline/SKILL.md`:
```markdown
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
```

`.claude/skills/dashboard-ui/SKILL.md`:
```markdown
---
name: dashboard-ui
description: tika-agent 프론트엔드(챗/대시보드) 구현 방법 — Vue3 패턴, 마크다운 렌더, 폴백 UI 규칙.
---

# 프론트엔드 구현 방법

## 규칙

- Vue3 Composition API(`<script setup>`)만 사용
- 마크다운 표시는 `frontend/src/utils/markdown.js`의 `renderMarkdown()` 경유 — v-html 직접 삽입 금지(XSS)
- 백엔드 오류 시 사용자에게 안내 문구 표시 (빈 화면/무반응 금지)
- 스타일은 scoped CSS

## 분류 배지 색상 (ChatMessage.vue와 일치 유지)

사용법문의 #2563eb / 버그제보 #dc2626 / 기능요청 #7c3aed / 불만 #ea580c / 칭찬 #16a34a / 기타 #6b7280

## 검증

- `cd frontend && npm test && npm run build`
- 수동 스모크: 백엔드 기동 상태에서 챗 전송 → 배지·출처 표시, 대시보드 토글 동작
```

- [ ] **Step 3: CLAUDE.md 작성**

`CLAUDE.md`:
```markdown
# CLAUDE.md

이 파일은 Claude Code가 이 저장소에서 작업할 때의 가이드다.

## 프로젝트 개요

tika-agent는 todo 앱 **tika**(`~/git/todoapp-vue-spring`)의 사용자 VOC를 처리하는 LLM 에이전트다.
채팅으로 받은 VOC를 분류(6유형)하고, 메뉴얼(`manual/`)에 근거한 답변을 생성하거나 사람에게 에스컬레이션하며, 이력을 PostgreSQL에 저장한다.

## 개발 명령

### 백엔드 (FastAPI + LangGraph)
```bash
docker compose up -d postgres          # PostgreSQL 기동
source .venv/bin/activate
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pytest -q                              # 전체 테스트
python scripts/lint_manual.py          # 메뉴얼 구조 린트
```

### 프론트엔드 (Vue3 + Vite)
```bash
cd frontend
npm run dev        # http://localhost:5173
npm test           # vitest
npm run build
```

### E2E
```bash
python scripts/e2e_check.py            # 실제 LLM으로 대표 VOC 5개 검증 (.env 필요)
```

## 핵심 아키텍처

- 그래프: `backend/agent.py` — classify → route(조건부) → retrieve → answer / escalate → respond → save
- 노드: `backend/nodes/` 파일당 하나, `make_*_node(provider)` 팩토리 패턴
- LLM: `backend/llm/` — `LLMProvider` ABC, OpenAI 호환 기본, `.env`로 교체
- 메뉴얼: `manual/*.md` — `##` 섹션이 검색 단위, 임베딩 없는 간단 검색(`backend/manual_retrieval.py`)
- 환각 방지: 근거 없으면 답변 생성 금지 + 에스컬레이션 (핵심 품질 속성)

## VOC 처리 하네스

**트리거:** 기능 구현/개선 요청, 단계별 진행 요청 시 `tika-orchestrator` 스킬 사용.

| 에이전트 (`.claude/agents/`) | 책임 | HOW 스킬 |
|------------------------------|------|----------|
| manual-writer | 메뉴얼 작성 | manual-authoring |
| backend-engineer | 그래프/API | voc-pipeline |
| frontend-engineer | 챗/대시보드 | dashboard-ui |
| qa-engineer | 품질 게이트 | — |

각 단계 완료 시 qa-engineer 게이트 통과 후 커밋.

## 규칙

- 로그 파일 생성 금지 (콘솔만)
- LLM 호출은 반드시 `LLMProvider` 뒤에서
- 주석/프롬프트/UI 문구는 한국어
- 커밋: conventional commits 한국어 제목

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-08-18 | 하네스 초기 구성 (에이전트 4 + 스킬 4) |
```

- [ ] **Step 4: README 작성**

`README.md`:
```markdown
# tika-agent

todo 앱 **tika**의 사용자 VOC(Voice of Customer)를 처리하는 LLM 에이전트.

- 채팅으로 VOC 입력 → 자동 분류(사용법문의/버그제보/기능요청/불만/칭찬/기타)
- 사용법 문의는 메뉴얼(`manual/`)에 근거한 답변 + 출처 표기
- 버그·기능요청·중대 불만은 담당자 에스컬레이션 → 대시보드에서 관리

## 아키텍처

- **백엔드**: FastAPI + LangGraph (조건부 파이프라인) + SQLAlchemy + PostgreSQL
- **LLM**: OpenAI 호환 API (`.env`의 `LLM_BASE_URL`/`LLM_MODEL`로 교체 가능)
- **프론트엔드**: Vue 3 + Vite (챗 뷰 + VOC 대시보드)
- **메뉴얼**: `manual/*.md` — 임베딩 없는 간단 검색, 근거 없으면 답변하지 않음

## 빠른 시작

```bash
# 1. DB 기동
docker compose up -d postgres

# 2. 백엔드
cp .env.example .env        # LLM_API_KEY 입력
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 3. 프론트엔드
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## 테스트

```bash
pytest -q                        # 백엔드 전체 (LLM 불필요 — FakeProvider)
python scripts/lint_manual.py    # 메뉴얼 구조 린트
cd frontend && npm test          # 프론트엔드
python scripts/e2e_check.py      # E2E (실제 LLM, .env 필요)
```

## 관련 문서

- 설계: `docs/superpowers/specs/2026-08-18-tika-agent-design.md`
- 구현 계획: `docs/superpowers/plans/2026-08-18-tika-agent-mvp.md`
- 대상 앱: `~/git/todoapp-vue-spring`
```

- [ ] **Step 5: 검증**

```bash
pytest -q && python scripts/lint_manual.py && (cd frontend && npm test && npm run build)
```
Expected: 전체 통과 (문서 태스크라 회귀 없음 확인이 목적)

- [ ] **Step 6: 커밋**

```bash
git add .claude/ CLAUDE.md README.md
git commit -m "chore: 개발 하네스 — 에이전트 4종·스킬 4종·CLAUDE.md·README

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 13: E2E 검증 스크립트 + QA 체크리스트 (MVP 게이트)

**Files:**
- Create: `scripts/e2e_check.py`, `docs/qa/e2e-checklist.md`
- Test: 수동 검증 (실제 LLM 사용 — 자동 테스트로 만들지 않음)

**Interfaces:**
- Consumes: `run_tika_agent`, `get_llm_provider`, `settings`, `init_database`, `SessionLocal` (기존 태스크)
- Produces: `python scripts/e2e_check.py` — 5개 대표 VOC 실측, 종료 코드 0/1/2. `docs/qa/e2e-checklist.md` — 스펙 §9의 MVP 완료 기준 6개 항목 수동 체크리스트

- [ ] **Step 1: E2E 스크립트 작성**

`scripts/e2e_check.py`:
```python
"""실제 LLM으로 대표 VOC 5개를 처리해 MVP 품질 게이트 검증 (스펙 §8 E2E).

사용법: .env 설정 후 `python scripts/e2e_check.py`
종료 코드: 0 통과 / 1 시나리오 실패 / 2 LLM 미설정
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.agent import run_tika_agent  # noqa: E402
from backend.config import settings  # noqa: E402
from backend.database import SessionLocal, init_database  # noqa: E402
from backend.llm import get_llm_provider  # noqa: E402

# (VOC, 기대 유형(None=무관), 기대 에스컬레이션 여부)
SCENARIOS = [
    ("완료한 할 일이 목록에서 안 보여요. 어디서 확인하나요?", "사용법문의", False),
    ("할 일을 어떻게 삭제하나요?", "사용법문의", False),
    ("앱을 켜면 바로 꺼집니다. 고쳐주세요.", "버그제보", True),
    ("다크 모드도 추가해 주세요.", "기능요청", True),
    ("화면 테마 색을 분홍색으로 바꾸고 싶어요.", None, True),  # 메뉴얼에 없음 → 에스컬레이션
]


def main() -> int:
    provider = get_llm_provider(settings)
    if provider is None:
        print("LLM이 설정되지 않았습니다. .env의 LLM_API_KEY를 확인하세요.")
        return 2

    init_database()
    failures = 0
    for i, (voc, expected_category, expected_escalated) in enumerate(SCENARIOS, 1):
        result = run_tika_agent(
            voc_text=voc,
            session_id=f"e2e-{i}",
            provider=provider,
            session_factory=SessionLocal,
        )
        category = result.get("category")
        escalated = bool(result.get("escalated"))
        ok_category = expected_category is None or category == expected_category
        ok_escalated = escalated == expected_escalated
        status = "PASS" if (ok_category and ok_escalated) else "FAIL"
        if status == "FAIL":
            failures += 1
        print(f"[{status}] VOC {i}: {voc}")
        print(f"       분류={category} (기대={expected_category or '무관'}) "
              f"에스컬레이션={escalated} (기대={expected_escalated})")
        print(f"       응답: {(result.get('response') or '')[:120]}")
        print(f"       출처: {result.get('answer_sources') or []}")
        print()

    print(f"결과: {len(SCENARIOS) - failures}/{len(SCENARIOS)} 통과")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: QA 체크리스트 작성**

`docs/qa/e2e-checklist.md`:
```markdown
# tika-agent E2E 체크리스트 (MVP 게이트)

실행 조건: postgres 기동 + `.env`의 LLM_API_KEY 설정 + 백엔드/프론트 기동.

## 자동 (qa-engineer)

- [ ] `pytest -q` 전체 통과
- [ ] `python scripts/lint_manual.py` 통과
- [ ] `cd frontend && npm test && npm run build` 통과
- [ ] `python scripts/e2e_check.py` 5/5 통과

## 수동 — MVP 완료 기준 (스펙 §9)

1. [ ] 챗에서 "완료한 할 일이 목록에서 안 보여요" 입력 → 사용법문의 배지 + 출처 포함 답변 표시
2. [ ] 챗에서 "앱을 켜면 바로 꺼집니다" 입력 → ⚠ 사람 확인 필요 표시 + 접수 안내 문구
3. [ ] 챗에서 메뉴얼에 없는 요청(예: 테마 색 변경) → 지어내지 않고 "찾지 못했습니다" 안내 + 에스컬레이션
4. [ ] 대시보드(/dashboard)에서 총 VOC·유형별 분포·미해결 에스컬레이션 수 표시
5. [ ] 에스컬레이션 테이블에서 "해결 완료" 클릭 → open→resolved 전환 및 다시 열기 동작
6. [ ] VOC 이력 필터(유형/에스컬레이션만) 동작

## 결과 기록

| 일자 | 버전(커밋) | 자동 게이트 | 수동 6항목 | 판정 |
|------|-----------|-------------|-----------|------|
|      |           |             |           |      |
```

- [ ] **Step 3: 실행 — 전체 게이트**

```bash
pytest -q
python scripts/lint_manual.py
cd frontend && npm test && npm run build && cd ..
python scripts/e2e_check.py
```
Expected: 전부 통과. `e2e_check.py`에서 분류 기대치 미달 시 classify 프롬프트(`backend/nodes/classify.py`) 개선 후 재실행 — 게이트를 낮추지 않는다

- [ ] **Step 4: 체크리스트 수동 확인 후 기록**

브라우저에서 수동 6항목 수행 → `docs/qa/e2e-checklist.md` 결과 표에 기록

- [ ] **Step 5: 커밋**

```bash
git add scripts/e2e_check.py docs/qa/e2e-checklist.md
git commit -m "test: E2E 검증 스크립트와 MVP 게이트 체크리스트

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## 완료 정의

Task 1~13 완료 + `docs/qa/e2e-checklist.md` 전항목 통과 시 MVP 완성 (스펙 §9).

## 향후 확장 (이 계획 범위 밖 — 스펙 §10)

- 벡터 검색 RAG: `manual_retrieval.search()` 인터페이스 유지한 구현체 교체
- 외부 알림(이메일/슬랙/JIRA) 에스컬레이션 연동
- 사용자 인증/권한
- 다중 턴 대화, VOC 일괄 처리/스케줄러

