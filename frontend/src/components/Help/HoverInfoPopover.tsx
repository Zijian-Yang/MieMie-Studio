import { Popover, Space, Typography, theme } from 'antd'
import { QuestionCircleOutlined } from '@ant-design/icons'
import type { ReactNode } from 'react'
import type { HelpContent } from '../../services/api'

const { Text } = Typography

interface HoverInfoPopoverProps {
  title: string
  help?: HelpContent | string | null
  icon?: ReactNode
}

function renderList(items?: string[]) {
  if (!items?.length) return null
  return (
    <div style={{ marginTop: 6 }}>
      {items.map((item, index) => (
        <div key={`${item}-${index}`} style={{ display: 'flex', gap: 6, alignItems: 'flex-start', marginBottom: 4 }}>
          <span style={{ lineHeight: '20px' }}>•</span>
          <span style={{ lineHeight: '20px' }}>{item}</span>
        </div>
      ))}
    </div>
  )
}

function normalizeHelp(help?: HelpContent | string | null) {
  if (!help) return null
  if (typeof help === 'string') {
    return { summary: help }
  }
  return help
}

const HoverInfoPopover = ({ title, help, icon }: HoverInfoPopoverProps) => {
  const { token } = theme.useToken()
  const normalizedHelp = normalizeHelp(help)

  if (!normalizedHelp) return null

  const sections = [
    normalizedHelp.summary ? { label: '概览', content: normalizedHelp.summary } : null,
    normalizedHelp.meaning ? { label: '含义', content: normalizedHelp.meaning } : null,
    normalizedHelp.limits?.length ? { label: '限制', list: normalizedHelp.limits } : null,
    normalizedHelp.how_to_choose?.length ? { label: '怎么选', list: normalizedHelp.how_to_choose } : null,
    normalizedHelp.examples?.length ? { label: '示例', list: normalizedHelp.examples } : null,
    normalizedHelp.notes?.length ? { label: '补充说明', list: normalizedHelp.notes } : null,
  ].filter(Boolean) as Array<{ label: string; content?: string; list?: string[] }>

  if (sections.length === 0) return null

  return (
    <Popover
      trigger="hover"
      placement="topLeft"
      overlayStyle={{ maxWidth: 420 }}
      content={
        <div style={{ maxWidth: 380 }}>
          {sections.map((section, index) => (
            <div key={section.label} style={{ marginBottom: index === sections.length - 1 ? 0 : 10 }}>
              <Text strong style={{ color: token.colorText }}>
                {section.label}
              </Text>
              {section.content && (
                <div style={{ marginTop: 4, lineHeight: '20px', color: token.colorTextSecondary }}>
                  {section.content}
                </div>
              )}
              {section.list && (
                <div style={{ color: token.colorTextSecondary }}>
                  {renderList(section.list)}
                </div>
              )}
            </div>
          ))}
        </div>
      }
      title={<Space size={6}><QuestionCircleOutlined />{title}</Space>}
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          color: token.colorTextSecondary,
          cursor: 'help',
        }}
      >
        {icon || <QuestionCircleOutlined />}
      </span>
    </Popover>
  )
}

export default HoverInfoPopover
