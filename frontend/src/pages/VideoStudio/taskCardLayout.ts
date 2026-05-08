import type { CSSProperties } from 'react'

export const TASK_CARD_META_ROW_STYLE: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  flexWrap: 'wrap',
  width: '100%',
  columnGap: 8,
  rowGap: 6,
}

export const TASK_CARD_TAGS_STYLE: CSSProperties = {
  display: 'flex',
  flex: '1 1 180px',
  flexWrap: 'wrap',
  minWidth: 0,
}

export const TASK_CARD_PROGRESS_STYLE: CSSProperties = {
  flex: '0 0 auto',
  marginLeft: 'auto',
  fontSize: 12,
  whiteSpace: 'nowrap',
}
