"""VOC 이력 ORM 모델 (스펙 §4.4)."""
from datetime import datetime

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
