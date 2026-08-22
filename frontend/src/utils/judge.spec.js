import { describe, expect, it } from 'vitest'
import { causeClass, formatAvg, formatScore } from './judge'

describe('formatScore', () => {
  it('채점된 건은 "합계/15" 형식', () => {
    expect(formatScore({ judge_total: 12 })).toBe('12/15')
  })
  it('미채점은 대시', () => {
    expect(formatScore({ judge_total: null })).toBe('—')
    expect(formatScore({})).toBe('—')
  })
})

describe('formatAvg', () => {
  it('평균은 "값/15"', () => {
    expect(formatAvg(11.0)).toBe('11/15')
  })
  it('null은 대시', () => {
    expect(formatAvg(null)).toBe('—')
  })
})

describe('causeClass', () => {
  it('재료부족/과정오류만 태그 클래스', () => {
    expect(causeClass('재료부족')).toBe('tag gap')
    expect(causeClass('과정오류')).toBe('tag error')
    expect(causeClass('해당없음')).toBe('')
    expect(causeClass(null)).toBe('')
  })
})
