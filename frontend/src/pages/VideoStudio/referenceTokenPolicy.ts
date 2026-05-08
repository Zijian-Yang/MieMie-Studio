import type {
  VideoReferenceTokenPolicy,
  VideoReferenceTokenRole,
  VideoReferenceTokenTemplate,
} from '../../services/api'

export interface ReferenceTokenOption {
  key: string
  label: string
  token: string
}

export interface ReferenceTokenBuildInput {
  role: VideoReferenceTokenRole
  roleIndex: number
  roleCounts: Partial<Record<VideoReferenceTokenRole, number>>
  policy?: VideoReferenceTokenPolicy | null
}

export interface PromptTokenInsertion {
  value: string
  cursor: number
}

const DEFAULT_TEMPLATES: Record<VideoReferenceTokenRole, VideoReferenceTokenTemplate> = {
  reference_image: { template: '图{index}' },
  reference_video: { template: '视频{index}' },
}

const DEFAULT_REFERENCE_ORDER: VideoReferenceTokenRole[] = ['reference_image', 'reference_video']

function clampIndex(index: number, max: number) {
  if (!Number.isFinite(index)) return max
  return Math.min(Math.max(index, 0), max)
}

function formatTemplate(template: string, index: number) {
  return template.replace(/\{index\}/g, String(index))
}

function getTokenTemplate(
  policy: VideoReferenceTokenPolicy | null | undefined,
  role: VideoReferenceTokenRole,
) {
  return policy?.tokens?.[role] || DEFAULT_TEMPLATES[role]
}

function getReferenceTokenIndex(input: ReferenceTokenBuildInput) {
  const policy = input.policy
  const indexBase = typeof policy?.index_base === 'number' ? policy.index_base : 1
  const roleIndex = Math.max(0, input.roleIndex)

  if (policy?.numbering_scope === 'combined') {
    const order = policy.reference_order?.length ? policy.reference_order : DEFAULT_REFERENCE_ORDER
    let precedingCount = 0
    for (const role of order) {
      if (role === input.role) break
      precedingCount += Math.max(0, input.roleCounts[role] || 0)
    }
    return indexBase + precedingCount + roleIndex
  }

  return indexBase + roleIndex
}

export function buildReferenceTokenOptions(input: ReferenceTokenBuildInput): ReferenceTokenOption[] {
  const index = getReferenceTokenIndex(input)
  const template = getTokenTemplate(input.policy, input.role)
  const token = formatTemplate(template.template, index)
  const options: ReferenceTokenOption[] = [
    {
      key: 'default',
      label: token,
      token,
    },
  ]

  for (const variant of template.variants || []) {
    options.push({
      key: variant.key,
      label: formatTemplate(variant.label, index),
      token: formatTemplate(variant.template, index),
    })
  }

  return options
}

export function insertReferenceTokenAtSelection(
  text: string,
  token: string,
  selectionStart?: number,
  selectionEnd?: number,
): PromptTokenInsertion {
  const value = text || ''
  if (typeof selectionStart === 'number') {
    const start = clampIndex(selectionStart, value.length)
    const end = clampIndex(typeof selectionEnd === 'number' ? selectionEnd : selectionStart, value.length)
    const from = Math.min(start, end)
    const to = Math.max(start, end)
    const nextValue = `${value.slice(0, from)}${token}${value.slice(to)}`
    return {
      value: nextValue,
      cursor: from + token.length,
    }
  }

  const prefix = value.trimEnd()
  const nextValue = prefix ? `${prefix} ${token}` : token
  return {
    value: nextValue,
    cursor: nextValue.length,
  }
}
