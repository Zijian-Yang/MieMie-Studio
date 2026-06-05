import { Spin, theme } from 'antd'

export interface VideoStudioPreviewPayload {
  canonical_request: Record<string, any>
  provider_payload: Record<string, any> | null
  validation_warnings: string[]
}

interface DeveloperPreviewPanelProps {
  isEditMode: boolean
  taskId?: string
  previewLoading: boolean
  previewPayload: VideoStudioPreviewPayload | null
}

const DeveloperPreviewPanel = ({
  isEditMode,
  taskId,
  previewLoading,
  previewPayload,
}: DeveloperPreviewPanelProps) => {
  const { token } = theme.useToken()

  return (
    <div>
      <div style={{ marginBottom: 8, fontWeight: 500 }}>提交状态</div>
      <div style={{ marginBottom: 12, color: token.colorTextSecondary }}>
        {isEditMode && taskId ? `任务 ID: ${taskId}` : '尚未提交'}
      </div>
      {previewLoading ? (
        <Spin size="small" />
      ) : (
        <>
          {previewPayload?.validation_warnings?.length ? (
            <div style={{ marginBottom: 12, padding: 10, borderRadius: 8, background: token.colorWarningBg }}>
              {previewPayload.validation_warnings.map((warning, index) => (
                <div key={index} style={{ color: token.colorWarningText, fontSize: 12 }}>{warning}</div>
              ))}
            </div>
          ) : null}
          <div style={{ marginBottom: 8, fontWeight: 500 }}>Canonical 请求体</div>
          <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, padding: 12, borderRadius: 8, background: token.colorBgLayout, marginBottom: 12 }}>
            {JSON.stringify(previewPayload?.canonical_request || {}, null, 2)}
          </pre>
          <div style={{ marginBottom: 8, fontWeight: 500 }}>厂商请求体</div>
          <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, padding: 12, borderRadius: 8, background: token.colorBgLayout }}>
            {JSON.stringify(previewPayload?.provider_payload || {}, null, 2)}
          </pre>
        </>
      )}
    </div>
  )
}

export default DeveloperPreviewPanel
