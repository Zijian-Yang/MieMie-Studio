import { Space, theme } from 'antd'
import type { HelpContent } from '../../services/api'
import HoverInfoPopover from '../../components/Help/HoverInfoPopover'

interface VideoFieldLabelProps {
  label: string
  help?: HelpContent | string
  required?: boolean
}

const VideoFieldLabel = ({ label, help, required }: VideoFieldLabelProps) => {
  const { token } = theme.useToken()

  return (
    <Space size={4}>
      <span>{label}</span>
      {required && <span style={{ color: token.colorError }}>*</span>}
      <HoverInfoPopover title={label} help={help} />
    </Space>
  )
}

export default VideoFieldLabel
