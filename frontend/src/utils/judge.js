// Phase 2 — 채점 점수·원인 표시 헬퍼 (스펙 2026-08-21 §7)
export function formatScore(voc) {
  return voc?.judge_total == null ? '—' : `${voc.judge_total}/15`
}

export function formatAvg(avg) {
  return avg == null ? '—' : `${avg}/15`
}

export function causeClass(cause) {
  if (cause === '재료부족') return 'tag gap'
  if (cause === '과정오류') return 'tag error'
  return ''
}
