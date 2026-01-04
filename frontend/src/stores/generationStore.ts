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
  
  // 文生图模型设置（用于角色、场景、道具生成）
  t2iModel: string | null  // null 表示使用系统默认 (wan2.6-t2i)
  t2iWidth: number | null  // 图片宽度，null 表示使用系统默认
  t2iHeight: number | null  // 图片高度，null 表示使用系统默认
  t2iPromptExtend: boolean | null
  t2iWatermark: boolean | null
  t2iSeed: number | null
  
  // 视频生成设置（页面级覆盖，优先于系统设置）
  videoModel: string | null  // null 表示使用系统默认
  videoResolution: string | null  // 分辨率
  videoDuration: number | null   // 时长（秒）
  videoPromptExtend: boolean | null
  videoWatermark: boolean | null
  videoSeed: number | null
  videoAudio: boolean | null  // 是否自动生成音频
  videoShotType: string | null  // 镜头类型（single/multi，仅wan2.6支持）
  
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
  
  // 文生图模型设置 actions
  setT2iModel: (model: string | null) => void
  setT2iWidth: (width: number | null) => void
  setT2iHeight: (height: number | null) => void
  setT2iPromptExtend: (value: boolean | null) => void
  setT2iWatermark: (value: boolean | null) => void
  setT2iSeed: (seed: number | null) => void
  resetT2iSettings: () => void
  
  // 视频生成设置 actions
  setVideoModel: (model: string | null) => void
  setVideoResolution: (resolution: string | null) => void
  setVideoDuration: (duration: number | null) => void
  setVideoPromptExtend: (value: boolean | null) => void
  setVideoWatermark: (value: boolean | null) => void
  setVideoSeed: (seed: number | null) => void
  setVideoAudio: (audio: boolean | null) => void
  setVideoShotType: (shotType: string | null) => void
  resetVideoSettings: () => void
  
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
  setStopGeneration: (stop: boolean) => void
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
      videoGroupCount: 1,
      
      // 文生图模型设置（默认使用系统设置）
      t2iModel: null,
      t2iWidth: null,
      t2iHeight: null,
      t2iPromptExtend: null,
      t2iWatermark: null,
      t2iSeed: null,
      
      // 视频生成设置（页面级覆盖）
      videoModel: null,
      videoResolution: null,
      videoDuration: null,
      videoPromptExtend: null,
      videoWatermark: null,
      videoSeed: null,
      videoAudio: null,
      videoShotType: null,
      
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
      
      // 文生图模型设置 actions
      setT2iModel: (model) => set({ t2iModel: model }),
      setT2iWidth: (width) => set({ t2iWidth: width }),
      setT2iHeight: (height) => set({ t2iHeight: height }),
      setT2iPromptExtend: (value) => set({ t2iPromptExtend: value }),
      setT2iWatermark: (value) => set({ t2iWatermark: value }),
      setT2iSeed: (seed) => set({ t2iSeed: seed }),
      resetT2iSettings: () => set({
        t2iModel: null,
        t2iWidth: null,
        t2iHeight: null,
        t2iPromptExtend: null,
        t2iWatermark: null,
        t2iSeed: null,
      }),
      
      // 视频生成设置 actions
      setVideoModel: (model) => set({ videoModel: model }),
      setVideoResolution: (resolution) => set({ videoResolution: resolution }),
      setVideoDuration: (duration) => set({ videoDuration: duration }),
      setVideoPromptExtend: (value) => set({ videoPromptExtend: value }),
      setVideoWatermark: (value) => set({ videoWatermark: value }),
      setVideoSeed: (seed) => set({ videoSeed: seed }),
      setVideoAudio: (audio) => set({ videoAudio: audio }),
      setVideoShotType: (shotType) => set({ videoShotType: shotType }),
      resetVideoSettings: () => set({
        videoModel: null,
        videoResolution: null,
        videoDuration: null,
        videoPromptExtend: null,
        videoWatermark: null,
        videoSeed: null,
        videoAudio: null,
        videoShotType: null,
      }),
      
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
      
      setStopGeneration: (stop) => set({ shouldStop: stop }),
      
      resetGeneration: () => set({
        isGenerating: false,
        batchTasks: [],
        currentTaskIndex: 0,
        shouldStop: false,
        generatingItems: new Set(),  // 同时清空正在生成的项目
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
        // 文生图模型设置
        t2iModel: state.t2iModel,
        t2iWidth: state.t2iWidth,
        t2iHeight: state.t2iHeight,
        t2iPromptExtend: state.t2iPromptExtend,
        t2iWatermark: state.t2iWatermark,
        t2iSeed: state.t2iSeed,
        // 视频生成设置
        videoModel: state.videoModel,
        videoResolution: state.videoResolution,
        videoDuration: state.videoDuration,
        videoPromptExtend: state.videoPromptExtend,
        videoWatermark: state.videoWatermark,
        videoSeed: state.videoSeed,
        videoAudio: state.videoAudio,
        videoShotType: state.videoShotType,
        // 风格设置
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

