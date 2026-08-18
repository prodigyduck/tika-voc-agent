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
    # 분류 유형별 문서 보너스는 토큰 매칭이 있을 때만 적용
    if score > 0 and chunk.file.startswith(preferred):
        score += 16
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
