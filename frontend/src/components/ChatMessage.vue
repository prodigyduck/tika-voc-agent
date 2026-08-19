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
    <div v-if="message.role === 'agent' && message.sources && message.sources.length" class="msg-sources">
      출처: {{ message.sources.join(', ') }}
    </div>
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
.msg-sources { font-size: 11px; color: #6b7280; margin-top: 4px; font-style: italic; }
</style>
