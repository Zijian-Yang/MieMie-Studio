import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// 版本信息
export interface ScriptVersion {
  id: string
  name: string
  description: string
  content: string
  originalContent: string
  modelUsed?: string
  promptUsed?: string
  createdAt: string
}

export interface PromptVersion {
  id: string
  name: string
  description: string
  prompt: string
  createdAt: string
}

// 列信息
export interface Column {
  id: number
  model: string
  content: string
  isGenerating: boolean
  selected: boolean
}

// 项目的脚本状态
interface ProjectScriptState {
  originalContent: string
  aiEditorEnabled: boolean
  columns: Column[]
  customPrompt: string
  scriptVersions: ScriptVersion[]
  promptVersions: PromptVersion[]
  selectedScriptVersionId: string | null
}

interface ScriptState {
  // 每个项目的状态，key 为 projectId
  projectStates: Record<string, ProjectScriptState>
  
  // Actions
  getProjectState: (projectId: string) => ProjectScriptState
  setOriginalContent: (projectId: string, content: string) => void
  setAiEditorEnabled: (projectId: string, enabled: boolean) => void
  setColumns: (projectId: string, columns: Column[]) => void
  updateColumn: (projectId: string, columnId: number, updates: Partial<Column>) => void
  addColumn: (projectId: string, column: Column) => void
  removeColumn: (projectId: string, columnId: number) => void
  setCustomPrompt: (projectId: string, prompt: string) => void
  
  // 版本管理
  addScriptVersion: (projectId: string, version: ScriptVersion) => void
  setSelectedScriptVersion: (projectId: string, versionId: string | null) => void
  addPromptVersion: (projectId: string, version: PromptVersion) => void
  
  // 重置项目状态
  resetProjectState: (projectId: string) => void
}

const defaultProjectState: ProjectScriptState = {
  originalContent: '',
  aiEditorEnabled: false,
  columns: [{ id: 1, model: 'qwen3-max', content: '', isGenerating: false, selected: true }],
  customPrompt: '',
  scriptVersions: [],
  promptVersions: [],
  selectedScriptVersionId: null,
}

export const useScriptStore = create<ScriptState>()(
  persist(
    (set, get) => ({
      projectStates: {},

      getProjectState: (projectId: string) => {
        const state = get().projectStates[projectId]
        if (state) return state
        return { ...defaultProjectState }
      },

      setOriginalContent: (projectId: string, content: string) => {
        set((state) => ({
          projectStates: {
            ...state.projectStates,
            [projectId]: {
              ...get().getProjectState(projectId),
              originalContent: content,
            },
          },
        }))
      },

      setAiEditorEnabled: (projectId: string, enabled: boolean) => {
        set((state) => ({
          projectStates: {
            ...state.projectStates,
            [projectId]: {
              ...get().getProjectState(projectId),
              aiEditorEnabled: enabled,
            },
          },
        }))
      },

      setColumns: (projectId: string, columns: Column[]) => {
        set((state) => ({
          projectStates: {
            ...state.projectStates,
            [projectId]: {
              ...get().getProjectState(projectId),
              columns,
            },
          },
        }))
      },

      updateColumn: (projectId: string, columnId: number, updates: Partial<Column>) => {
        const currentState = get().getProjectState(projectId)
        const newColumns = currentState.columns.map(c =>
          c.id === columnId ? { ...c, ...updates } : c
        )
        set((state) => ({
          projectStates: {
            ...state.projectStates,
            [projectId]: {
              ...currentState,
              columns: newColumns,
            },
          },
        }))
      },

      addColumn: (projectId: string, column: Column) => {
        const currentState = get().getProjectState(projectId)
        set((state) => ({
          projectStates: {
            ...state.projectStates,
            [projectId]: {
              ...currentState,
              columns: [...currentState.columns, column],
            },
          },
        }))
      },

      removeColumn: (projectId: string, columnId: number) => {
        const currentState = get().getProjectState(projectId)
        let newColumns = currentState.columns.filter(c => c.id !== columnId)
        // 如果删除的是选中的，选中第一个
        const wasSelected = currentState.columns.find(c => c.id === columnId)?.selected
        if (wasSelected && newColumns.length > 0) {
          newColumns = newColumns.map((c, i) => ({ ...c, selected: i === 0 }))
        }
        set((state) => ({
          projectStates: {
            ...state.projectStates,
            [projectId]: {
              ...currentState,
              columns: newColumns,
            },
          },
        }))
      },

      setCustomPrompt: (projectId: string, prompt: string) => {
        set((state) => ({
          projectStates: {
            ...state.projectStates,
            [projectId]: {
              ...get().getProjectState(projectId),
              customPrompt: prompt,
            },
          },
        }))
      },

      addScriptVersion: (projectId: string, version: ScriptVersion) => {
        const currentState = get().getProjectState(projectId)
        set((state) => ({
          projectStates: {
            ...state.projectStates,
            [projectId]: {
              ...currentState,
              scriptVersions: [version, ...currentState.scriptVersions],
            },
          },
        }))
      },

      setSelectedScriptVersion: (projectId: string, versionId: string | null) => {
        const currentState = get().getProjectState(projectId)
        set((state) => ({
          projectStates: {
            ...state.projectStates,
            [projectId]: {
              ...currentState,
              selectedScriptVersionId: versionId,
            },
          },
        }))
      },

      addPromptVersion: (projectId: string, version: PromptVersion) => {
        const currentState = get().getProjectState(projectId)
        set((state) => ({
          projectStates: {
            ...state.projectStates,
            [projectId]: {
              ...currentState,
              promptVersions: [version, ...currentState.promptVersions],
            },
          },
        }))
      },

      resetProjectState: (projectId: string) => {
        set((state) => ({
          projectStates: {
            ...state.projectStates,
            [projectId]: { ...defaultProjectState },
          },
        }))
      },
    }),
    {
      name: 'script-storage',
      partialize: (state) => ({
        projectStates: Object.fromEntries(
          Object.entries(state.projectStates).map(([key, value]) => [
            key,
            {
              ...value,
              // 不持久化生成中状态
              columns: value.columns.map(c => ({ ...c, isGenerating: false })),
            },
          ])
        ),
      }),
    }
  )
)

