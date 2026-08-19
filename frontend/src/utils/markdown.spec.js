import { describe, expect, it } from 'vitest'
import { renderMarkdown } from './markdown'

describe('renderMarkdown', () => {
  it('볼드를 strong으로 변환', () => {
    expect(renderMarkdown('**증상**: 안 보여요')).toContain('<strong>증상</strong>')
  })

  it('번호 목록을 ul/li로 변환', () => {
    const html = renderMarkdown('1. 새로고침\n2. 재시작')
    expect(html).toContain('<ul>')
    expect(html).toContain('<li>새로고침</li>')
    expect(html).toContain('<li>재시작</li>')
  })

  it('하이픈 목록을 ul/li로 변환', () => {
    const html = renderMarkdown('- 첫째\n- 둘째')
    expect(html).toContain('<li>첫째</li>')
  })

  it('h3 제목 변환', () => {
    expect(renderMarkdown('### 접수 안내')).toContain('<h3>접수 안내</h3>')
  })

  it('HTML을 이스케이프해 XSS 방지', () => {
    expect(renderMarkdown('<script>alert(1)</script>')).not.toContain('<script>')
  })

  it('빈 입력은 빈 문자열', () => {
    expect(renderMarkdown('')).toBe('')
  })
})
