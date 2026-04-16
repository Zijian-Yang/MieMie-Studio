export type Wan27TaskKind = 'text_to_image' | 'image_edit' | 'interactive_edit' | 'sequential_generation'

export type ImageQualityLevel = 'low' | 'medium' | 'high'

export interface ImageSizeTemplate {
  ratio: string
  orientation: string
  width: number
  height: number
  label: string
}

export interface ImageQualityTemplateGroup {
  ratio: string
  orientation: string
  options: Array<ImageSizeTemplate & { quality: ImageQualityLevel; qualityLabel: string }>
}

export interface ImageSizeLimits {
  minTotalPixels: number
  maxTotalPixels: number
  minRatio: number
  maxRatio: number
}

export const WAN27_MIN_TOTAL_PIXELS = 768 * 768
export const WAN27_PRO_MAX_TOTAL_PIXELS = 4096 * 4096
export const WAN27_STANDARD_MAX_TOTAL_PIXELS = 2048 * 2048
export const WAN27_MIN_RATIO = 1 / 8
export const WAN27_MAX_RATIO = 8

const IMAGE_TEMPLATE_RATIOS: Array<{ ratio: string; orientation: string; value: number }> = [
  { ratio: '1:1', orientation: '方图', value: 1 },
  { ratio: '4:3', orientation: '横版', value: 4 / 3 },
  { ratio: '3:4', orientation: '竖版', value: 3 / 4 },
  { ratio: '16:9', orientation: '横版', value: 16 / 9 },
  { ratio: '9:16', orientation: '竖版', value: 9 / 16 },
  { ratio: '21:9', orientation: '横版', value: 21 / 9 },
]

const IMAGE_QUALITY_LEVELS: Array<{ value: ImageQualityLevel; label: string; scale: number }> = [
  { value: 'low', label: '小尺寸', scale: 0.6 },
  { value: 'medium', label: '标准', scale: 0.8 },
  { value: 'high', label: '最大像素', scale: 1 },
]

export const getWan27CustomSizeLimits = (
  modelId: string,
  taskKind: Wan27TaskKind,
  referenceCount: number,
): ImageSizeLimits => ({
  minTotalPixels: WAN27_MIN_TOTAL_PIXELS,
  maxTotalPixels: modelId === 'wan2.7-image-pro' && taskKind === 'text_to_image' && referenceCount === 0
    ? WAN27_PRO_MAX_TOTAL_PIXELS
    : WAN27_STANDARD_MAX_TOTAL_PIXELS,
  minRatio: WAN27_MIN_RATIO,
  maxRatio: WAN27_MAX_RATIO,
})

export const buildWan27SizeTemplates = (limits: ImageSizeLimits | null): ImageSizeTemplate[] => {
  if (!limits) return []
  return IMAGE_TEMPLATE_RATIOS
    .filter((item) => item.value >= limits.minRatio && item.value <= limits.maxRatio)
    .map((item) => {
      let width = Math.max(1, Math.floor(Math.sqrt(limits.maxTotalPixels * item.value)))
      let height = Math.max(1, Math.floor(Math.sqrt(limits.maxTotalPixels / item.value)))
      while (width * height > limits.maxTotalPixels && width > 1 && height > 1) {
        width -= 1
        height -= 1
      }
      return {
        ratio: item.ratio,
        orientation: item.orientation,
        width,
        height,
        label: `${item.ratio} ${item.orientation} ${width}×${height}`,
      }
    })
    .filter((item) => item.width * item.height >= limits.minTotalPixels)
}

export const buildWan27QualityTemplateGroups = (limits: ImageSizeLimits | null): ImageQualityTemplateGroup[] => {
  const maxTemplates = buildWan27SizeTemplates(limits)
  return maxTemplates.map((template) => {
    const options: Array<ImageSizeTemplate & { quality: ImageQualityLevel; qualityLabel: string }> = []
    for (const level of IMAGE_QUALITY_LEVELS) {
      const width = Math.max(1, Math.floor(template.width * level.scale))
      const height = Math.max(1, Math.floor(template.height * level.scale))
      const pixels = width * height
      if (!limits || pixels < limits.minTotalPixels || pixels > limits.maxTotalPixels) {
        continue
      }
      const key = `${width}x${height}`
      if (options.some((item) => `${item.width}x${item.height}` === key)) {
        continue
      }
      options.push({
        ratio: template.ratio,
        orientation: template.orientation,
        width,
        height,
        label: `${template.ratio} ${template.orientation} · ${level.label} ${width}×${height}`,
        quality: level.value,
        qualityLabel: level.label,
      })
    }
    if (!options.length) {
      options.push({
        ratio: template.ratio,
        orientation: template.orientation,
        width: template.width,
        height: template.height,
        label: `${template.ratio} ${template.orientation} · 最大像素 ${template.width}×${template.height}`,
        quality: 'high',
        qualityLabel: '最大像素',
      })
    }
    return {
      ratio: template.ratio,
      orientation: template.orientation,
      options,
    }
  })
}

export const matchWan27QualityTemplate = (
  groups: ImageQualityTemplateGroup[],
  width?: number | null,
  height?: number | null,
): { ratio: string; quality: ImageQualityLevel } | null => {
  if (!width || !height) return null
  let bestRatio: string | null = null
  let bestQuality: ImageQualityLevel | null = null
  let bestScore = Number.POSITIVE_INFINITY
  for (const group of groups) {
    for (const option of group.options) {
      const score = Math.abs(option.width - width) + Math.abs(option.height - height)
      if (score < bestScore) {
        bestScore = score
        bestRatio = group.ratio
        bestQuality = option.quality
      }
    }
  }
  if (bestRatio === null || bestQuality === null) return null
  return {
    ratio: bestRatio,
    quality: bestQuality,
  }
}
