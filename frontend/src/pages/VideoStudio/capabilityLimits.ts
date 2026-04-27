import type { VideoTaskKind, VideoTaskProfile } from '../../services/api'

export interface ReferenceCollectionLimits {
  maxReferenceImages: number
  maxReferenceVideos: number
  maxReferenceTotal: number
}

function finiteNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

export function resolveReferenceCollectionLimits(
  taskKind: VideoTaskKind,
  currentProfile?: Pick<VideoTaskProfile, 'ui_hints'> | null,
): ReferenceCollectionLimits {
  const uiHints = currentProfile?.ui_hints || {}

  return {
    maxReferenceImages: finiteNumber(uiHints.max_reference_images) ?? (taskKind === 'video_edit_global' ? 4 : 1),
    maxReferenceVideos: finiteNumber(uiHints.max_reference_videos) ?? (taskKind === 'reference_to_video' ? 5 : 0),
    maxReferenceTotal: finiteNumber(uiHints.max_reference_total) ?? 5,
  }
}
