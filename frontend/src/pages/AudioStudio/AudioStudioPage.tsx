import { useParams } from 'react-router-dom'
import { Card, Empty, Space } from 'antd'
import { AudioOutlined } from '@ant-design/icons'
import { useProjectStore } from '../../stores/projectStore'
import { useEffect } from 'react'

const AudioStudioPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { fetchProject } = useProjectStore()

  useEffect(() => {
    if (projectId) {
      fetchProject(projectId)
    }
  }, [projectId, fetchProject])

  return (
    <div style={{ padding: 24 }}>
      <Card
        title={
          <Space>
            <AudioOutlined />
            音频工作室
          </Space>
        }
        style={{ background: '#1a1a1a', borderColor: '#333' }}
      >
        <Empty
          description={
            <div>
              <div>功能开发中</div>
              <div style={{ color: '#888', marginTop: 8 }}>
                音频工作室将支持语音合成、音频编辑等功能
              </div>
            </div>
          }
        />
      </Card>
    </div>
  )
}

export default AudioStudioPage

