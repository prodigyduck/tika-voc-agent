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
