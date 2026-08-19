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
