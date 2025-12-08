import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface GenerationTask {
  id: string
  type: 'character' | 'scene' | 'prop' | 'frame' | 'video'
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
}

interface GenerationState {
  // 生成设置 - 会持久化
  characterGroupCount: number
  sceneGroupCount: number
  propGroupCount: number
  styleGroupCount: number
  frameGroupCount: number
  videoGroupCount: number
  
  // 风格参考设置 - 全局开关
  characterUseStyle: boolean
  characterSelectedStyleId: string | null
  sceneUseStyle: boolean
  sceneSelectedStyleId: string | null
  propUseStyle: boolean
  propSelectedStyleId: string | null
  
  // 生成状态 - 不持久化
  isGenerating: boolean
  batchTasks: GenerationTask[]
  currentTaskIndex: number
  shouldStop: boolean
  
  // 正在生成的项目ID集合（防止重复生成）
  generatingItems: Set<string>
  
  // Actions
  setCharacterGroupCount: (count: number) => void
  setSceneGroupCount: (count: number) => void
  setPropGroupCount: (count: number) => void
  setStyleGroupCount: (count: number) => void
  setFrameGroupCount: (count: number) => void
  setVideoGroupCount: (count: number) => void
  
  // 风格参考设置 actions
  setCharacterUseStyle: (use: boolean) => void
  setCharacterSelectedStyleId: (id: string | null) => void
  setSceneUseStyle: (use: boolean) => void
  setSceneSelectedStyleId: (id: string | null) => void
  setPropUseStyle: (use: boolean) => void
  setPropSelectedStyleId: (id: string | null) => void
  
  startBatchGeneration: (tasks: Omit<GenerationTask, 'status'>[]) => void
  updateTaskStatus: (taskId: string, status: GenerationTask['status']) => void
  setCurrentTaskIndex: (index: number) => void
  stopGeneration: () => void
  resetGeneration: () => void
  
  addGeneratingItem: (itemId: string) => void
  removeGeneratingItem: (itemId: string) => void
  isItemGenerating: (itemId: string) => boolean
}

export const useGenerationStore = create<GenerationState>()(
  persist(
    (set, get) => ({
      // 默认设置
      characterGroupCount: 3,
      sceneGroupCount: 3,
      propGroupCount: 3,
      styleGroupCount: 3,
      frameGroupCount: 3,
      videoGroupCount: 3,
      
      // 风格参考设置
      characterUseStyle: false,
      characterSelectedStyleId: null,
      sceneUseStyle: false,
      sceneSelectedStyleId: null,
      propUseStyle: false,
      propSelectedStyleId: null,
      
      // 运行时状态
      isGenerating: false,
      batchTasks: [],
      currentTaskIndex: 0,
      shouldStop: false,
      generatingItems: new Set(),
      
      setCharacterGroupCount: (count) => set({ characterGroupCount: count }),
      setSceneGroupCount: (count) => set({ sceneGroupCount: count }),
      setPropGroupCount: (count) => set({ propGroupCount: count }),
      setStyleGroupCount: (count) => set({ styleGroupCount: count }),
      setFrameGroupCount: (count) => set({ frameGroupCount: count }),
      setVideoGroupCount: (count) => set({ videoGroupCount: count }),
      
      setCharacterUseStyle: (use) => set({ characterUseStyle: use }),
      setCharacterSelectedStyleId: (id) => set({ characterSelectedStyleId: id }),
      setSceneUseStyle: (use) => set({ sceneUseStyle: use }),
      setSceneSelectedStyleId: (id) => set({ sceneSelectedStyleId: id }),
      setPropUseStyle: (use) => set({ propUseStyle: use }),
      setPropSelectedStyleId: (id) => set({ propSelectedStyleId: id }),
      
      startBatchGeneration: (tasks) => set({
        isGenerating: true,
        shouldStop: false,
        batchTasks: tasks.map(t => ({ ...t, status: 'pending' as const })),
        currentTaskIndex: 0,
      }),
      
      updateTaskStatus: (taskId, status) => set((state) => ({
        batchTasks: state.batchTasks.map(t => 
          t.id === taskId ? { ...t, status } : t
        ),
      })),
      
      setCurrentTaskIndex: (index) => set({ currentTaskIndex: index }),
      
      stopGeneration: () => set({ shouldStop: true }),
      
      resetGeneration: () => set({
        isGenerating: false,
        batchTasks: [],
        currentTaskIndex: 0,
        shouldStop: false,
      }),
      
      addGeneratingItem: (itemId) => set((state) => {
        const newSet = new Set(state.generatingItems)
        newSet.add(itemId)
        return { generatingItems: newSet }
      }),
      
      removeGeneratingItem: (itemId) => set((state) => {
        const newSet = new Set(state.generatingItems)
        newSet.delete(itemId)
        return { generatingItems: newSet }
      }),
      
      isItemGenerating: (itemId) => get().generatingItems.has(itemId),
    }),
    {
      name: 'generation-settings',
      // 只持久化设置，不持久化运行时状态
      partialize: (state) => ({
        characterGroupCount: state.characterGroupCount,
        sceneGroupCount: state.sceneGroupCount,
        propGroupCount: state.propGroupCount,
        styleGroupCount: state.styleGroupCount,
        frameGroupCount: state.frameGroupCount,
        videoGroupCount: state.videoGroupCount,
        characterUseStyle: state.characterUseStyle,
        characterSelectedStyleId: state.characterSelectedStyleId,
        sceneUseStyle: state.sceneUseStyle,
        sceneSelectedStyleId: state.sceneSelectedStyleId,
        propUseStyle: state.propUseStyle,
        propSelectedStyleId: state.propSelectedStyleId,
      }),
    }
  )
)

