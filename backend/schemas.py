"""API 요청/응답 스키마 (스펙 §6.1)."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


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

    model_config = ConfigDict(from_attributes=True)  # ORM 객체 직접 변환


class VocStatusUpdate(BaseModel):
    status: str  # open | resolved


class StatsResponse(BaseModel):
    total: int
    by_category: dict
    escalated_open: int
    by_day: List[dict]  # 최근 7일 [{"date": "2026-08-18", "count": 3}]
