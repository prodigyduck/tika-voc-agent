---
name: dashboard-ui
description: doit-voc-agent 프론트엔드(챗/대시보드) 구현 방법 — Vue3 패턴, 마크다운 렌더, 폴백 UI 규칙.
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
