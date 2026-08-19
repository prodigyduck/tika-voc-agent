<script setup>
defineProps({
  stats: { type: Object, default: null },
})
</script>

<template>
  <div class="cards" v-if="stats">
    <div class="card">
      <span class="num">{{ stats.total }}</span>
      <span class="label">총 VOC</span>
    </div>
    <div class="card warn">
      <span class="num">{{ stats.escalated_open }}</span>
      <span class="label">미해결 에스컬레이션</span>
    </div>
    <div class="card">
      <span class="num">{{ Object.keys(stats.by_category).length }}</span>
      <span class="label">분류 유형 수</span>
    </div>
  </div>
</template>

<style scoped>
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 12px 0; }
.card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; display: flex; flex-direction: column; }
.card.warn { border-color: #f59e0b; }
.num { font-size: 28px; font-weight: 700; }
.label { font-size: 13px; color: #6b7280; margin-top: 4px; }
</style>
