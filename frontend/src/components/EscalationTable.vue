<script setup>
defineProps({
  vocs: { type: Array, default: () => [] },
})
const emit = defineEmits(['toggle'])
</script>

<template>
  <div>
    <table class="escalation-table" v-if="vocs.length">
      <thead>
        <tr>
          <th>ID</th><th>VOC</th><th>유형</th><th>사유</th><th>상태</th><th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="v in vocs" :key="v.id" :class="{ open: v.escalation_status === 'open' }">
          <td>{{ v.id }}</td>
          <td class="voc-text">{{ v.voc_text }}</td>
          <td>{{ v.category }}</td>
          <td class="voc-text">{{ v.escalation_reason || '-' }}</td>
          <td>
            <span class="status" :class="v.escalation_status">{{ v.escalation_status }}</span>
          </td>
          <td>
            <button @click="emit('toggle', v)">
              {{ v.escalation_status === 'open' ? '해결 완료' : '다시 열기' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">에스컬레이션된 VOC가 없습니다.</p>
  </div>
</template>

<style scoped>
.escalation-table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; font-size: 14px; }
th, td { padding: 8px 10px; border-bottom: 1px solid #f3f4f6; text-align: left; }
th { background: #f9fafb; font-size: 13px; color: #6b7280; }
.voc-text { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
tr.open { background: #fffbeb; }
.status { padding: 2px 8px; border-radius: 10px; font-size: 12px; }
.status.open { background: #fef3c7; color: #b45309; }
.status.resolved { background: #dcfce7; color: #15803d; }
button { border: 1px solid #d1d5db; background: #fff; border-radius: 8px; padding: 4px 10px; cursor: pointer; font-size: 13px; }
.empty { color: #6b7280; text-align: center; padding: 24px; }
</style>
