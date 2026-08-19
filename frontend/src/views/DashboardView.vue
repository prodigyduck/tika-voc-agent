<script setup>
import { onMounted, ref } from 'vue'
import { getStats, getVocs, patchVocStatus } from '../services/api'
import EscalationTable from '../components/EscalationTable.vue'
import StatsCards from '../components/StatsCards.vue'

const CATEGORIES = ['사용법문의', '버그제보', '기능요청', '불만', '칭찬', '기타']

const STATUS_LABELS = {
  open: '미해결',
  resolved: '해결',
}

const PRIORITY_LABELS = {
  low: '낮음',
  medium: '보통',
  high: '높음',
}

const stats = ref(null)
const vocs = ref([])
const error = ref('')
const loading = ref(false)
const filterCategory = ref('')
const onlyEscalated = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = {}
    if (filterCategory.value) params.category = filterCategory.value
    if (onlyEscalated.value) params.escalated = true
    const [s, v] = await Promise.all([getStats(), getVocs(params)])
    stats.value = s
    vocs.value = v
  } catch (e) {
    error.value = `대시보드를 불러올 수 없습니다. 백엔드가 실행 중인지 확인하세요. (${e.message})`
  } finally {
    loading.value = false
  }
}

async function toggleStatus(voc) {
  const next = voc.escalation_status === 'open' ? 'resolved' : 'open'
  try {
    await patchVocStatus(voc.id, next)
    await load()
  } catch (e) {
    error.value = `상태 변경 실패: ${e.message}`
  }
}

function barWidth(count) {
  const values = Object.values(stats.value?.by_category || {})
  const max = Math.max(1, ...values)
  return Math.round((count / max) * 100) + '%'
}

// 백엔드가 타임존 없는 UTC로 저장하므로 오프셋이 없으면 UTC로 파싱한다
function formatTime(value) {
  const hasZone = /Z$|[+-]\d{2}:?\d{2}$/.test(value)
  return new Date(hasZone ? value : value + 'Z').toLocaleString('ko-KR')
}

onMounted(load)
</script>

<template>
  <section class="dashboard">
    <h1>VOC 대시보드</h1>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="loading">불러오는 중...</p>

    <StatsCards :stats="stats" />

    <div class="chart" v-if="stats">
      <h3>유형별 분포</h3>
      <div v-for="(count, cat) in stats.by_category" :key="cat" class="bar-row">
        <span class="bar-label">{{ cat }}</span>
        <div class="bar-track">
          <div class="bar" :style="{ width: barWidth(count) }"></div>
        </div>
        <span class="bar-count">{{ count }}</span>
      </div>
    </div>

    <h3>에스컬레이션</h3>
    <EscalationTable :vocs="vocs.filter((v) => v.escalated)" @toggle="toggleStatus" />

    <div class="filters">
      <h3>VOC 이력</h3>
      <select v-model="filterCategory" @change="load">
        <option value="">전체 유형</option>
        <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
      </select>
      <label>
        <input type="checkbox" v-model="onlyEscalated" @change="load" />
        에스컬레이션만
      </label>
    </div>
    <table class="voc-table" v-if="vocs.length">
      <thead>
        <tr><th>ID</th><th>VOC</th><th>유형</th><th>우선순위</th><th>에스컬레이션</th><th>등록</th></tr>
      </thead>
      <tbody>
        <tr v-for="v in vocs" :key="v.id">
          <td>{{ v.id }}</td>
          <td class="voc-text">{{ v.voc_text }}</td>
          <td>{{ v.category }}</td>
          <td>{{ PRIORITY_LABELS[v.priority] }}</td>
          <td>{{ v.escalated ? '예' : '아니오' }}</td>
          <td>{{ formatTime(v.created_at) }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">해당 조건의 VOC가 없습니다.</p>
  </section>
</template>

<style scoped>
h1 { font-size: 22px; margin: 8px 0; }
h3 { margin: 16px 0 8px; font-size: 15px; }
.error { color: #dc2626; }
.loading { color: #6b7280; }
.chart { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px 16px; }
.bar-row { display: flex; align-items: center; gap: 10px; margin: 6px 0; }
.bar-label { width: 80px; font-size: 13px; text-align: right; }
.bar-track { flex: 1; background: #f3f4f6; border-radius: 6px; height: 14px; }
.bar { background: #2563eb; border-radius: 6px; height: 14px; }
.bar-count { width: 32px; font-size: 13px; }
.filters { display: flex; align-items: center; gap: 12px; }
.filters select { padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 8px; }
.voc-table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; font-size: 14px; }
.voc-table th, .voc-table td { padding: 8px 10px; border-bottom: 1px solid #f3f4f6; text-align: left; }
.voc-table th { background: #f9fafb; font-size: 13px; color: #6b7280; }
.empty { color: #6b7280; text-align: center; padding: 24px; }
</style>
