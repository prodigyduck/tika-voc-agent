// 간단 마크다운 렌더러 — tpssAgent 커스텀 파서의 축소판 (스펙 §6.2)
function escapeHtml(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function inline(text) {
  return text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
}

export function renderMarkdown(md) {
  if (!md) return ''
  const lines = escapeHtml(md).split('\n')
  const out = []
  let inList = false
  const closeList = () => {
    if (inList) {
      out.push('</ul>')
      inList = false
    }
  }
  for (const line of lines) {
    const trimmed = line.trim()
    if (/^###\s+/.test(trimmed)) {
      closeList()
      out.push(`<h3>${inline(trimmed.replace(/^###\s+/, ''))}</h3>`)
    } else if (/^[-*]\s+/.test(trimmed) || /^\d+\.\s+/.test(trimmed)) {
      if (!inList) {
        out.push('<ul>')
        inList = true
      }
      const item = trimmed.replace(/^[-*]\s+/, '').replace(/^\d+\.\s+/, '')
      out.push(`<li>${inline(item)}</li>`)
    } else if (trimmed === '') {
      closeList()
    } else {
      closeList()
      out.push(`<p>${inline(trimmed)}</p>`)
    }
  }
  closeList()
  return out.join('')
}
