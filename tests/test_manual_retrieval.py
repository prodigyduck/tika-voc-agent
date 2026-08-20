from backend.manual_retrieval import load_manual, search


def test_메뉴얼_로드_섹션_분해():
    chunks = load_manual()
    assert len(chunks) >= 15  # 5개 문서의 전체 섹션 수
    first = chunks[0]
    assert first.file == "01-getting-started"
    assert first.source == f"01-getting-started#{first.section}"
    assert first.content  # 내용이 비어 있지 않음


def test_완료_사라짐_문의가_문제해결_섹션을_찾는다():
    chunks = load_manual()
    results = search(chunks, "완료한 티켓이 보드에서 사라졌어요", category="불만")
    assert any("사라졌어요" in c.section for c in results)


def test_사용법_문의는_가이드_문서_우선():
    chunks = load_manual()
    results = search(chunks, "티켓을 어떻게 생성하나요?", category="사용법문의")
    assert results
    assert results[0].file.startswith(("01", "02", "03"))


def test_불만은_문제해결_문서_우선():
    chunks = load_manual()
    results = search(chunks, "티켓이 자꾸 원래 자리로 돌아가요", category="불만")
    assert results
    assert results[0].file.startswith(("04", "05"))


def test_관련_없는_질문은_빈_결과():
    chunks = load_manual()
    assert search(chunks, "zzz qq", category="사용법문의") == []


def test_상위_3개만_반환():
    chunks = load_manual()
    results = search(chunks, "티켓 생성 수정 삭제 완료 이동 검색 필터 칸반", category="사용법문의")
    assert 0 < len(results) <= 3


def test_정확한_제목_매칭은_카테고리_우선순위보다_우선():
    chunks = load_manual()
    results = search(chunks, "완료한 티켓이 보드에서 사라졌어요", category="사용법문의")
    assert results
    # 정확한 제목 매칭(04-troubleshooting)이 카테고리 우선순위보다 우선
    assert results[0].section == "완료한 티켓이 보드에서 사라졌어요"


def test_어형이_달라도_제목을_찾는다():
    chunks = load_manual()
    # "삭제하나요"(질문형)와 "삭제하기"(제목)은 어형만 다른 같은 동사
    results = search(chunks, "티켓을 어떻게 삭제하나요?", category="사용법문의")
    assert results
    assert results[0].section == "티켓 삭제하기"


def test_어형_정규화():
    from backend.manual_retrieval import _normalize_token

    assert _normalize_token("삭제하나요") == _normalize_token("삭제하기") == "삭제"
    assert _normalize_token("생성하나요") == _normalize_token("생성하기") == "생성"
    assert _normalize_token("이동하나요") == _normalize_token("이동하기") == "이동"
