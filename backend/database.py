"""SQLAlchemy 엔진/세션 — 테스트는 SQLite 인메모리로 대체 가능."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import settings

Base = declarative_base()


def _create_engine(url: str):
    if url.endswith(":memory:") or url == "sqlite://":
        # 인메모리 SQLite는 커넥션 공유가 필요 (스레드 간 사용)
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    if url.startswith("sqlite"):
        # 파일 SQLite — 커넥션 풀로 요청마다 독립 커넥션 사용.
        # StaticPool 단일 커넥션을 스레드가 동시에 쓰면 sqlite3 C 레벨 크래시(SIGSEGV) 발생.
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


engine = _create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_database() -> None:
    """모든 테이블 생성. 모델 임포트로 메타데이터 등록을 보장한다."""
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
