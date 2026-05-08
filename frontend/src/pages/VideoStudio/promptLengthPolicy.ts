import type { VideoPromptLengthPolicy } from '../../services/api'

export const HAPPYHORSE_PROMPT_LENGTH_POLICY: VideoPromptLengthPolicy = {
  mode: 'cjk_weighted',
  max_units: 5000,
  cjk_unit: 2,
  non_cjk_unit: 1,
  cjk_equivalent_limit: 2500,
  non_cjk_equivalent_limit: 5000,
}

function isCjkUnifiedIdeograph(char: string) {
  const codePoint = char.codePointAt(0) || 0
  return (
    (codePoint >= 0x3400 && codePoint <= 0x4dbf) ||
    (codePoint >= 0x4e00 && codePoint <= 0x9fff) ||
    (codePoint >= 0xf900 && codePoint <= 0xfaff) ||
    (codePoint >= 0x20000 && codePoint <= 0x2a6df) ||
    (codePoint >= 0x2a700 && codePoint <= 0x2b73f) ||
    (codePoint >= 0x2b740 && codePoint <= 0x2b81f) ||
    (codePoint >= 0x2b820 && codePoint <= 0x2ceaf) ||
    (codePoint >= 0x2ceb0 && codePoint <= 0x2ebef) ||
    (codePoint >= 0x30000 && codePoint <= 0x3134f)
  )
}

export function countPromptLengthUnits(text: string, policy?: VideoPromptLengthPolicy) {
  if (policy?.mode !== 'cjk_weighted') {
    return Array.from(text || '').length
  }

  const cjkUnit = policy.cjk_unit ?? 2
  const nonCjkUnit = policy.non_cjk_unit ?? 1
  return Array.from(text || '').reduce((total, char) => (
    total + (isCjkUnifiedIdeograph(char) ? cjkUnit : nonCjkUnit)
  ), 0)
}

export function formatPromptLengthLimit(policy?: VideoPromptLengthPolicy) {
  if (!policy?.max_units) return ''
  if (policy.mode === 'cjk_weighted') {
    return `${policy.cjk_equivalent_limit || 2500} 个中文字符或 ${policy.non_cjk_equivalent_limit || policy.max_units} 个非中文字符`
  }
  return `${policy.max_units} 个字符`
}

export function getPromptLengthError(text: string, policy?: VideoPromptLengthPolicy) {
  if (!policy?.max_units) return null
  const units = countPromptLengthUnits(text, policy)
  if (units <= policy.max_units) return null
  return `提示词长度不能超过${formatPromptLengthLimit(policy)}`
}
