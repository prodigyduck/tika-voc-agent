"""tika-agent 설정 — .env 기반 (스펙 §6.3)."""
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """환경 변수를 읽어 보관. 테스트에서는 속성을 직접 덮어쓸 수 있다."""

    def __init__(self) -> None:
        self.database_url: str = os.getenv(
            "DATABASE_URL", "postgresql://doit:doit@localhost:5432/doit_agent"
        )
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "openai_compat")
        self.llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.llm_api_key: str = os.getenv("LLM_API_KEY", "")
        self.llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.judge_enabled: bool = os.getenv("JUDGE_ENABLED", "true").lower() in ("1", "true", "yes")
        # 빈 값이면 기존 LLM 프로바이더(모델)를 그대로 채점에 재사용한다
        self.judge_model: str = os.getenv("JUDGE_MODEL", "")


settings = Settings()
