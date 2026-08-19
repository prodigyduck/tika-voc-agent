<script setup>
import { nextTick, ref } from 'vue'
import { chat, getSessionId } from '../services/api'
import ChatMessage from '../components/ChatMessage.vue'

// 프리셋 질문 칩 (스펙 §6.2)
const PRESETS = [
  '완료한 할 일이 목록에서 안 보여요',
  '할 일을 삭제하려면 어떻게 하나요?',
  '입력한 할 일이 사라졌어요',
  '이메일로 목록을 보내고 싶어요',
]

const messages = ref([])
const input = ref('')
const waiting = ref(false)
const error = ref('')
const listEl = ref(null)

async function send(text) {
  const vocText = (text ?? input.value).trim()
  if (!vocText || waiting.value) return
  input.value = ''
  error.value = ''
  messages.value.push({ role: 'user', content: vocText })
  waiting.value = true
  try {
    const data = await chat(vocText, getSessionId())
    messages.value.push({
      role: 'agent',
      content: data.response,
      category: data.category,
      escalated: data.escalated,
      sources: data.sources,
    })
  } catch (e) {
    error.value = `에이전트에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요. (${e.message})`
  } finally {
    waiting.value = false
    await nextTick()
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
  }
}
</script>

<template>
  <section class="chat">
    <div class="message-list" ref="listEl">
      <div v-if="messages.length === 0" class="empty">
        <h2>tika VOC 에이전트</h2>
        <p>tika 사용 중 불편하거나 궁금한 점을 입력해 주세요.</p>
      </div>
      <ChatMessage v-for="(m, i) in messages" :key="i" :message="m" />
      <div v-if="waiting" class="message agent">
        <div class="bubble typing">답변 작성 중...</div>
      </div>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="presets">
      <button v-for="p in PRESETS" :key="p" :disabled="waiting" @click="send(p)">
        {{ p }}
      </button>
    </div>
    <form class="input-row" @submit.prevent="send()">
      <input
        v-model="input"
        placeholder="예: 할 일이 저장되지 않아요"
        :disabled="waiting"
      />
      <button type="submit" :disabled="waiting || !input.trim()">보내기</button>
    </form>
  </section>
</template>

<style scoped>
.chat { display: flex; flex-direction: column; height: calc(100vh - 140px); }
.message-list { flex: 1; overflow-y: auto; padding: 12px 4px; }
.empty { text-align: center; color: #6b7280; margin-top: 80px; }
.typing { color: #6b7280; }
.error { color: #dc2626; font-size: 14px; margin: 4px 0; }
.presets { display: flex; flex-wrap: wrap; gap: 8px; padding: 8px 0; }
.presets button { border: 1px solid #d1d5db; background: #fff; border-radius: 16px; padding: 6px 12px; font-size: 13px; cursor: pointer; }
.presets button:hover { border-color: #2563eb; color: #2563eb; }
.input-row { display: flex; gap: 8px; }
.input-row input { flex: 1; padding: 12px 14px; border: 1px solid #d1d5db; border-radius: 10px; font-size: 15px; }
.input-row button { padding: 12px 20px; border: none; background: #2563eb; color: #fff; border-radius: 10px; font-size: 15px; cursor: pointer; }
.input-row button:disabled { background: #93c5fd; cursor: not-allowed; }
</style>
