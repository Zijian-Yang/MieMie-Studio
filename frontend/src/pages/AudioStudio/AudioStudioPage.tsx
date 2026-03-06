import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import {
  Card, Tabs, Button, Form, Input, Select, Slider, InputNumber, Switch,
  List, Tag, Space, Empty, message, Popconfirm, Spin, Typography, Alert,
} from 'antd'
import {
  AudioOutlined, SoundOutlined, ScissorOutlined, ExperimentOutlined,
  PlayCircleOutlined, PauseCircleOutlined, DeleteOutlined, SaveOutlined, ReloadOutlined,
  StarOutlined, StarFilled, FlagOutlined, FlagFilled, CheckOutlined, CloseOutlined,
} from '@ant-design/icons'
import {
  audioStudioApi, audioApi,
  AudioStudioTask, VoiceProfile, AudioItem,
} from '../../services/api'
import { useProjectStore } from '../../stores/projectStore'

const { TextArea } = Input
const { Text } = Typography

// cosyvoice-v3-flash 系统音色
const SYSTEM_VOICES = [
  { group: '社交陪伴', voices: [
    { id: 'longanyang', name: '龙安阳', desc: '阳光青年男性', lang: '中英', instruct: true },
    { id: 'longanhuan', name: '龙安欢', desc: '活力欢快女性', lang: '中英', instruct: true },
    { id: 'longantai_v3', name: '龙安台', desc: '甜美台湾女性', lang: '中英' },
    { id: 'longhua_v3', name: '龙华', desc: '活力甜美女性', lang: '中英' },
    { id: 'longcheng_v3', name: '龙诚', desc: '沉稳青年男性', lang: '中英' },
    { id: 'longze_v3', name: '龙泽', desc: '温暖活力男性', lang: '中英' },
    { id: 'longzhe_v3', name: '龙哲', desc: '沉着温厚男性', lang: '中英' },
    { id: 'longyan_v3', name: '龙燕', desc: '温柔淑雅女性', lang: '中英' },
    { id: 'longxing_v3', name: '龙星', desc: '邻家温柔女性', lang: '中英' },
    { id: 'longtian_v3', name: '龙天', desc: '磁性理性男性', lang: '中英' },
    { id: 'longwan_v3', name: '龙婉', desc: '细腻温婉女性', lang: '中英' },
    { id: 'longqiang_v3', name: '龙强', desc: '阳刚男性', lang: '中英' },
    { id: 'longfeifei_v3', name: '龙菲菲', desc: '知性女性', lang: '中英' },
    { id: 'longhao_v3', name: '龙浩', desc: '阳光男性', lang: '中英' },
    { id: 'longanrou_v3', name: '龙安柔', desc: '温柔女性', lang: '中英' },
    { id: 'longhan_v3', name: '龙翰', desc: '稳重男性', lang: '中英' },
    { id: 'longanzhi_v3', name: '龙安芝', desc: '知性女性', lang: '中英' },
    { id: 'longanling_v3', name: '龙安玲', desc: '清脆女性', lang: '中英' },
    { id: 'longanya_v3', name: '龙安雅', desc: '优雅女性', lang: '中英' },
    { id: 'longanqin_v3', name: '龙安芹', desc: '亲切女性', lang: '中英' },
  ]},
  { group: '儿童', voices: [
    { id: 'longhuhu_v3', name: '龙虎虎', desc: '天真活泼女孩', lang: '中英', instruct: true },
    { id: 'longpaopao_v3', name: '龙泡泡', desc: '气泡音', lang: '中英' },
    { id: 'longjielidou_v3', name: '龙杰力豆', desc: '阳光调皮男孩', lang: '中英' },
    { id: 'longxian_v3', name: '龙仙', desc: '豪爽可爱女孩', lang: '中英' },
    { id: 'longling_v3', name: '龙灵', desc: '童真呆萌女孩', lang: '中英' },
    { id: 'longshanshan_v3', name: '龙珊珊', desc: '戏剧童声', lang: '中英' },
    { id: 'longniuniu_v3', name: '龙牛牛', desc: '阳光男孩', lang: '中英' },
  ]},
  { group: '方言', voices: [
    { id: 'longjiaxin_v3', name: '龙家欣', desc: '优雅粤语女性', lang: '粤语 英' },
    { id: 'longjiayi_v3', name: '龙家怡', desc: '知性粤语女性', lang: '粤语 英' },
    { id: 'longanyue_v3', name: '龙安粤', desc: '活力粤语男性', lang: '粤语 英' },
    { id: 'longlaotie_v3', name: '龙老铁', desc: '豪爽东北男性', lang: '东北话 英' },
    { id: 'longshange_v3', name: '龙山哥', desc: '地道陕北男性', lang: '陕西话 英' },
    { id: 'longanmin_v3', name: '龙安闽', desc: '清纯闽南少女', lang: '闽南话 英' },
  ]},
  { group: '海外', voices: [
    { id: 'loongkyong_v3', name: 'Kyong', desc: '韩语女性', lang: '韩语' },
    { id: 'loongriko_v3', name: 'Riko', desc: '日语动漫少女', lang: '日语' },
    { id: 'loongtomoka_v3', name: 'Tomoka', desc: '日语女性', lang: '日语' },
  ]},
  { group: '语音助手', voices: [
    { id: 'longxiaochun_v3', name: '龙小春', desc: '知性积极女性', lang: '中英' },
    { id: 'longxiaoxia_v3', name: '龙小夏', desc: '沉稳权威女性', lang: '中英' },
    { id: 'longyumi_v3', name: 'YUMI', desc: '严肃年轻女性', lang: '中英' },
    { id: 'longanyun_v3', name: '龙安云', desc: '温厚居家男性', lang: '中英' },
    { id: 'longanwen_v3', name: '龙安文', desc: '优雅知性女性', lang: '中英' },
    { id: 'longanli_v3', name: '龙安莉', desc: '干练沉稳女性', lang: '中英' },
    { id: 'longanlang_v3', name: '龙安朗', desc: '清爽干练男性', lang: '中英' },
    { id: 'longyingmu_v3', name: '龙颖慕', desc: '优雅知性女性', lang: '中英' },
  ]},
  { group: '客服', voices: [
    { id: 'longyingxiao_v3', name: '龙颖笑', desc: '甜美销售女性', lang: '中英' },
    { id: 'longyingxun_v3', name: '龙颖迅', desc: '青涩年轻男性', lang: '中英' },
    { id: 'longyingjing_v3', name: '龙颖静', desc: '低调沉稳女性', lang: '中英' },
    { id: 'longyingling_v3', name: '龙颖灵', desc: '温柔共情女性', lang: '中英' },
    { id: 'longyingtao_v3', name: '龙颖桃', desc: '温和沉稳女性', lang: '中英' },
  ]},
  { group: '其他', voices: [
    { id: 'longfei_v3', name: '龙飞', desc: '激情磁性男性', lang: '中英' },
    { id: 'longmiao_v3', name: '龙淼', desc: '温柔女性', lang: '中英' },
    { id: 'longsanshu_v3', name: '龙三叔', desc: '成熟男性', lang: '中英' },
    { id: 'longyuan_v3', name: '龙远', desc: '沉稳男性', lang: '中英' },
    { id: 'longyue_v3', name: '龙月', desc: '柔美女性', lang: '中英' },
    { id: 'longxiu_v3', name: '龙秀', desc: '温婉女性', lang: '中英' },
    { id: 'longnan_v3', name: '龙楠', desc: '稳重男性', lang: '中英' },
    { id: 'longwanjun_v3', name: '龙万君', desc: '沉稳女性', lang: '中英' },
    { id: 'longyichen_v3', name: '龙逸辰', desc: '阳光男性', lang: '中英' },
    { id: 'longlaobo_v3', name: '龙老伯', desc: '年长男性', lang: '中英' },
    { id: 'longlaoyi_v3', name: '龙老姨', desc: '年长女性', lang: '中英' },
    { id: 'longjiqi_v3', name: '龙吉七', desc: '中年男性', lang: '中英' },
    { id: 'longhouge_v3', name: '龙猴哥', desc: '特色男性', lang: '中英' },
    { id: 'longdaiyu_v3', name: '龙黛玉', desc: '古典女性', lang: '中英' },
    { id: 'longanran_v3', name: '龙安然', desc: '温和女性', lang: '中英' },
    { id: 'longanxuan_v3', name: '龙安萱', desc: '甜美女性', lang: '中英' },
    { id: 'longshuo_v3', name: '龙硕', desc: '有力男性', lang: '中英' },
    { id: 'longshu_v3', name: '龙舒', desc: '知性女性', lang: '中英' },
    { id: 'loongbella_v3', name: 'Bella 3.0', desc: '英语女性', lang: '英语' },
  ]},
]

const AUDIO_FORMATS = [
  { value: 'mp3_22050hz_mono_256kbps', label: 'MP3 22.05kHz' },
  { value: 'mp3_16000hz_mono_128kbps', label: 'MP3 16kHz' },
  { value: 'mp3_24000hz_mono_256kbps', label: 'MP3 24kHz' },
  { value: 'mp3_44100hz_mono_256kbps', label: 'MP3 44.1kHz' },
  { value: 'mp3_48000hz_mono_256kbps', label: 'MP3 48kHz' },
  { value: 'wav_16000hz_mono_16bit', label: 'WAV 16kHz' },
  { value: 'wav_22050hz_mono_16bit', label: 'WAV 22.05kHz' },
  { value: 'wav_24000hz_mono_16bit', label: 'WAV 24kHz' },
  { value: 'wav_44100hz_mono_16bit', label: 'WAV 44.1kHz' },
  { value: 'wav_48000hz_mono_16bit', label: 'WAV 48kHz' },
  { value: 'pcm_16000hz_mono_16bit', label: 'PCM 16kHz' },
  { value: 'pcm_22050hz_mono_16bit', label: 'PCM 22.05kHz' },
  { value: 'pcm_24000hz_mono_16bit', label: 'PCM 24kHz' },
]

const LANGUAGE_OPTIONS = [
  { value: 'zh', label: '中文' },
  { value: 'en', label: '英文' },
  { value: 'fr', label: '法语' },
  { value: 'de', label: '德语' },
  { value: 'ja', label: '日语' },
  { value: 'ko', label: '韩语' },
  { value: 'ru', label: '俄语' },
]

const INSTRUCT_EMOTIONS = [
  { value: 'neutral', label: '中性 (neutral)' },
  { value: 'happy', label: '开心 (happy)' },
  { value: 'sad', label: '悲伤 (sad)' },
  { value: 'angry', label: '愤怒 (angry)' },
  { value: 'fearful', label: '恐惧 (fearful)' },
  { value: 'surprised', label: '惊讶 (surprised)' },
  { value: 'disgusted', label: '厌恶 (disgusted)' },
]

interface VoiceInstructConfig {
  scenes: { value: string; label: string }[]
  roles: { value: string; label: string }[]
  identities: { value: string; label: string }[]
  roleFormat: 'current' | 'default'
}

const VOICE_INSTRUCT_CONFIG: Record<string, VoiceInstructConfig> = {
  longanyang: {
    scenes: [
      { value: '闲聊互动', label: '闲聊互动' },
      { value: '新闻播报', label: '新闻播报' },
      { value: '广告促销', label: '广告促销' },
      { value: '比赛解说', label: '比赛解说' },
      { value: '一些儿童内容解说', label: '儿童内容解说' },
      { value: '语音导航', label: '语音导航' },
      { value: '脱口秀表演', label: '脱口秀表演' },
    ],
    roles: [{ value: '一个旁白', label: '旁白' }],
    identities: [{ value: '故事机', label: '故事机' }],
    roleFormat: 'current',
  },
  longanhuan: {
    scenes: [
      { value: '闲聊对话', label: '闲聊对话' },
      { value: '比赛解说', label: '比赛解说' },
      { value: '深夜电台广播', label: '深夜电台广播' },
      { value: '剧情解说', label: '剧情解说' },
      { value: '诗歌朗诵', label: '诗歌朗诵' },
      { value: '科普知识推广', label: '科普知识推广' },
      { value: '产品推广', label: '产品推广' },
      { value: '脱口秀表演', label: '脱口秀表演' },
    ],
    roles: [{ value: '温和客服', label: '温和客服' }],
    identities: [],
    roleFormat: 'default',
  },
  longhuhu_v3: {
    scenes: [
      { value: '自由对话', label: '自由对话' },
      { value: '广告促销', label: '广告促销' },
    ],
    roles: [
      { value: '傲娇公主', label: '傲娇公主' },
      { value: '元气少女', label: '元气少女' },
      { value: '可爱孩童', label: '可爱孩童' },
      { value: '机器人', label: '机器人' },
      { value: '小猪佩奇', label: '小猪佩奇' },
    ],
    identities: [
      { value: '故事机', label: '故事机' },
      { value: '儿童玩具', label: '儿童玩具' },
    ],
    roleFormat: 'default',
  },
}

const ALL_SYSTEM_VOICE_IDS = new Set(
  SYSTEM_VOICES.flatMap(g => g.voices.map(v => v.id))
)
const INSTRUCT_VOICE_IDS = new Set(
  SYSTEM_VOICES.flatMap(g => g.voices.filter(v => v.instruct).map(v => v.id))
)

const SYSTEM_VOICE_NAME_MAP: Record<string, string> = Object.fromEntries(
  SYSTEM_VOICES.flatMap(g => g.voices.map(v => [v.id, `${v.name}（${v.desc}）`]))
)

const FORMAT_LABEL_MAP: Record<string, string> = Object.fromEntries(
  AUDIO_FORMATS.map(f => [f.value, f.label])
)

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return m > 0 ? `${m}分${s}秒` : `${s}秒`
}

type VoiceType = 'system_instruct' | 'system_plain' | 'custom'

function getVoiceType(voiceId: string | undefined): VoiceType {
  if (!voiceId) return 'system_plain'
  if (INSTRUCT_VOICE_IDS.has(voiceId)) return 'system_instruct'
  if (ALL_SYSTEM_VOICE_IDS.has(voiceId)) return 'system_plain'
  return 'custom'
}

function buildInstruction(
  voiceId: string | undefined,
  voiceType: VoiceType,
  emotion?: string,
  scene?: string,
  role?: string,
  identity?: string,
  freeText?: string,
): string | null {
  if (voiceType === 'custom') return freeText || null
  if (voiceType === 'system_plain') return null
  if (!emotion) return null
  const config = voiceId ? VOICE_INSTRUCT_CONFIG[voiceId] : undefined
  if (scene) return `你正在进行${scene}，你说话的情感是${emotion}。`
  if (role) {
    if (config?.roleFormat === 'current') {
      return `你现在说话的角色是${role}，你说话的情感是${emotion}。`
    }
    return `你说话的角色是${role}，你说话的情感是${emotion}。`
  }
  if (identity) return `你正在以一个${identity}的身份说话，你说话的情感是${emotion}。`
  return `你说话的情感是${emotion}。`
}

const AudioStudioPage = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { fetchProject } = useProjectStore()

  const [tasks, setTasks] = useState<AudioStudioTask[]>([])
  const [voices, setVoices] = useState<VoiceProfile[]>([])
  const [audioItems, setAudioItems] = useState<AudioItem[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [activeTab, setActiveTab] = useState('tts')
  const pollingRef = useRef<Set<string>>(new Set())
  const isMountedRef = useRef(true)

  const [playingId, setPlayingId] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const handlePlayPause = useCallback((taskId: string, url: string) => {
    if (playingId === taskId && audioRef.current) {
      audioRef.current.pause()
      setPlayingId(null)
      return
    }
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    const audio = new Audio(url)
    audio.onended = () => { setPlayingId(null); audioRef.current = null }
    audio.onerror = () => { setPlayingId(null); audioRef.current = null }
    audio.play()
    audioRef.current = audio
    setPlayingId(taskId)
  }, [playingId])

  const getVoiceDisplayName = useCallback((voiceId: string) => {
    if (SYSTEM_VOICE_NAME_MAP[voiceId]) return SYSTEM_VOICE_NAME_MAP[voiceId]
    const matched = voices.find(v => v.voice_id === voiceId)
    return matched ? `${matched.name}（${matched.source === 'clone' ? '复刻' : '设计'}）` : voiceId
  }, [voices])

  const [ttsForm] = Form.useForm()
  const [cloneForm] = Form.useForm()
  const [designForm] = Form.useForm()

  useEffect(() => {
    isMountedRef.current = true
    if (projectId) {
      fetchProject(projectId)
      loadData()
    }
    return () => {
      isMountedRef.current = false
      pollingRef.current.clear()
      if (audioRef.current) { audioRef.current.pause(); audioRef.current = null }
    }
  }, [projectId])

  const loadData = useCallback(async () => {
    if (!projectId) return
    setLoading(true)
    try {
      const [tasksRes, voicesRes, audioRes] = await Promise.all([
        audioStudioApi.list(projectId),
        audioStudioApi.listVoices(projectId),
        audioApi.list(projectId),
      ])
      setTasks(tasksRes.tasks)
      setVoices(voicesRes.voices)
      setAudioItems(audioRes.audios)

      tasksRes.tasks.forEach((t: AudioStudioTask) => {
        if (t.status === 'processing') startPolling(t.id)
      })
    } catch {
      message.error('加载数据失败')
    } finally {
      setLoading(false)
    }
  }, [projectId])

  const startPolling = (taskId: string) => {
    if (pollingRef.current.has(taskId)) return
    pollingRef.current.add(taskId)
    const poll = async () => {
      if (!isMountedRef.current || !pollingRef.current.has(taskId)) return
      try {
        const res = await audioStudioApi.get(taskId)
        const updated = res.task
        if (!isMountedRef.current) return
        setTasks(prev => prev.map(t => t.id === taskId ? updated : t))
        if (updated.status === 'succeeded' || updated.status === 'failed') {
          pollingRef.current.delete(taskId)
          if (updated.status === 'succeeded') {
            message.success(`任务"${updated.name}"完成`)
            if (updated.task_type !== 'tts') loadData()
          } else {
            message.error(`任务"${updated.name}"失败: ${updated.error_message || '未知错误'}`)
          }
          return
        }
      } catch { /* ignore */ }
      setTimeout(poll, 3000)
    }
    setTimeout(poll, 2000)
  }

  const selectedVoice = Form.useWatch('voice', ttsForm)
  const voiceType = useMemo(() => getVoiceType(selectedVoice), [selectedVoice])
  const voiceInstructCfg = useMemo(() => selectedVoice ? VOICE_INSTRUCT_CONFIG[selectedVoice] : undefined, [selectedVoice])
  const prevVoiceRef = useRef<string | undefined>()
  useEffect(() => {
    if (prevVoiceRef.current !== undefined && prevVoiceRef.current !== selectedVoice) {
      ttsForm.setFieldsValue({ instruct_emotion: undefined, instruct_scene: undefined, instruct_role: undefined, instruct_identity: undefined })
    }
    prevVoiceRef.current = selectedVoice
  }, [selectedVoice, ttsForm])

  // ─── TTS ─────────────────────
  const handleTTS = async () => {
    if (!projectId) return
    try {
      const values = await ttsForm.validateFields()
      setSubmitting(true)
      const instruction = buildInstruction(
        selectedVoice,
        voiceType,
        values.instruct_emotion,
        values.instruct_scene,
        values.instruct_role,
        values.instruct_identity,
        values.instruction,
      )
      const res = await audioStudioApi.createTTS({
        project_id: projectId,
        name: values.name || '',
        text: values.text,
        voice: values.voice,
        format: values.format || 'mp3_22050hz_mono_256kbps',
        volume: values.volume ?? 50,
        speech_rate: values.speech_rate ?? 1.0,
        pitch_rate: values.pitch_rate ?? 1.0,
        seed: values.seed || null,
        language_hints: values.language_hints || null,
        instruction,
        enable_ssml: values.enable_ssml || false,
      })
      setTasks(prev => [res.task, ...prev])
      startPolling(res.task.id)
      message.success('TTS 任务已提交')
    } catch (e: any) {
      if (e.errorFields) return
      message.error(e.message || '提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  // ─── Voice Clone ─────────────
  const handleVoiceClone = async () => {
    if (!projectId) return
    try {
      const values = await cloneForm.validateFields()
      setSubmitting(true)
      const res = await audioStudioApi.createVoiceClone({
        project_id: projectId,
        name: values.name || '',
        audio_url: values.audio_url,
        prefix: values.prefix,
        language_hints: values.language_hints || null,
      })
      setTasks(prev => [res.task, ...prev])
      startPolling(res.task.id)
      message.success('声音复刻任务已提交')
    } catch (e: any) {
      if (e.errorFields) return
      message.error(e.message || '提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  // ─── Voice Design ────────────
  const handleVoiceDesign = async () => {
    if (!projectId) return
    try {
      const values = await designForm.validateFields()
      setSubmitting(true)
      const res = await audioStudioApi.createVoiceDesign({
        project_id: projectId,
        name: values.name || '',
        voice_prompt: values.voice_prompt,
        preview_text: values.preview_text,
        prefix: values.prefix,
        sample_rate: values.sample_rate || 24000,
        response_format: values.response_format || 'wav',
      })
      setTasks(prev => [res.task, ...prev])
      startPolling(res.task.id)
      message.success('声音设计任务已提交')
    } catch (e: any) {
      if (e.errorFields) return
      message.error(e.message || '提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleSaveToLibrary = async (taskId: string) => {
    try {
      await audioStudioApi.saveToLibrary(taskId)
      setTasks(prev => prev.map(t => t.id === taskId ? { ...t, saved_to_library: true } : t))
      message.success('已保存到音频库')
    } catch {
      message.error('保存失败')
    }
  }

  const handleDeleteTask = async (taskId: string) => {
    try {
      await audioStudioApi.delete(taskId)
      setTasks(prev => prev.filter(t => t.id !== taskId))
      pollingRef.current.delete(taskId)
    } catch {
      message.error('删除失败')
    }
  }

  const handleToggleAudioMarker = async (taskId: string, markerKey: string) => {
    const task = tasks.find(t => t.id === taskId)
    if (!task) return
    const currentMarkers = task.markers || []
    const newMarkers = currentMarkers.includes(markerKey)
      ? currentMarkers.filter(m => m !== markerKey)
      : [...currentMarkers, markerKey]
    try {
      await audioStudioApi.updateMarkers(taskId, newMarkers)
      setTasks(prev => prev.map(t => t.id === taskId ? { ...t, markers: newMarkers } : t))
    } catch {
      message.error('标记更新失败')
    }
  }

  const handleDeleteVoice = async (profileId: string) => {
    try {
      await audioStudioApi.deleteVoice(profileId)
      setVoices(prev => prev.filter(v => v.id !== profileId))
      message.success('音色已删除')
    } catch {
      message.error('删除失败')
    }
  }

  // ─── Voice Select Options ────
  const voiceOptions = [
    ...SYSTEM_VOICES.map(group => ({
      label: `系统音色 - ${group.group}`,
      options: group.voices.map(v => ({
        value: v.id,
        label: `${v.name} (${v.desc})${v.instruct ? ' [支持Instruct]' : ''}`,
      })),
    })),
    ...(voices.filter(v => v.status === 'ok').length > 0 ? [{
      label: '我的自定义音色',
      options: voices.filter(v => v.status === 'ok').map(v => ({
        value: v.voice_id,
        label: `${v.name} (${v.source === 'clone' ? '复刻' : '设计'})`,
      })),
    }] : []),
  ]

  // ─── Audio Library Select (for clone) ────
  const audioUrlOptions = audioItems.map(a => ({
    value: a.url,
    label: a.name || a.id,
  }))

  const statusTag = (status: string) => {
    const map: Record<string, { color: string; text: string }> = {
      pending: { color: 'default', text: '等待中' },
      processing: { color: 'processing', text: '处理中' },
      succeeded: { color: 'success', text: '成功' },
      failed: { color: 'error', text: '失败' },
    }
    const s = map[status] || { color: 'default', text: status }
    return <Tag color={s.color}>{s.text}</Tag>
  }

  const taskTypeLabel = (type: string) => {
    const map: Record<string, string> = { tts: '文本转语音', voice_clone: '声音复刻', voice_design: '声音设计' }
    return map[type] || type
  }

  // ─── Render ──────────────────
  return (
    <div style={{ padding: 24 }}>
      <Card
        title={<Space><AudioOutlined /> 音频工作室</Space>}
        extra={<Button icon={<ReloadOutlined />} onClick={loadData}>刷新</Button>}
      >
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
          {
            key: 'tts',
            label: <span><SoundOutlined /> 文本转语音</span>,
            children: (
              <Form form={ttsForm} layout="vertical" initialValues={{ format: 'mp3_22050hz_mono_256kbps', volume: 50, speech_rate: 1.0, pitch_rate: 1.0 }}>
                <Form.Item name="name" label="任务名称">
                  <Input placeholder="可选，留空自动生成" />
                </Form.Item>
                <Form.Item name="text" label="合成文本" rules={[{ required: true, message: '请输入文本' }]}>
                  <TextArea rows={4} placeholder="输入要合成的文本内容..." showCount maxLength={20000} />
                </Form.Item>
                <Form.Item name="voice" label="音色" rules={[{ required: true, message: '请选择音色' }]}>
                  <Select
                    showSearch
                    optionFilterProp="label"
                    placeholder="搜索或选择音色"
                    options={voiceOptions}
                    style={{ width: '100%' }}
                  />
                </Form.Item>
                <Form.Item name="format" label="音频格式">
                  <Select options={AUDIO_FORMATS} />
                </Form.Item>
                <Form.Item name="volume" label={`音量`}>
                  <Slider min={0} max={100} marks={{ 0: '0', 50: '50', 100: '100' }} />
                </Form.Item>
                <Form.Item name="speech_rate" label={`语速`}>
                  <Slider min={0.5} max={2.0} step={0.1} marks={{ 0.5: '0.5x', 1.0: '1.0x', 2.0: '2.0x' }} />
                </Form.Item>
                <Form.Item name="pitch_rate" label={`音高`}>
                  <Slider min={0.5} max={2.0} step={0.1} marks={{ 0.5: '0.5x', 1.0: '1.0x', 2.0: '2.0x' }} />
                </Form.Item>
                <Form.Item name="seed" label="随机种子">
                  <InputNumber min={0} max={65535} placeholder="可选，0~65535" style={{ width: '100%' }} />
                </Form.Item>
                <Form.Item name="language_hints" label="语言提示">
                  <Select allowClear placeholder="可选" options={LANGUAGE_OPTIONS} />
                </Form.Item>
                {voiceType === 'system_instruct' && voiceInstructCfg && (
                  <>
                    <Form.Item name="instruct_emotion" label="情感指令" extra="选择情感后自动生成 Instruct 指令，下方场景/角色/身份可三选一">
                      <Select allowClear placeholder="可选 — 不选则不使用指令" options={INSTRUCT_EMOTIONS} />
                    </Form.Item>
                    {voiceInstructCfg.scenes.length > 0 && (
                      <Form.Item name="instruct_scene" label="场景（可选）"
                        extra={`支持：${voiceInstructCfg.scenes.map(s => s.value).join('、')}`}>
                        <Select allowClear placeholder="与角色、身份互斥" options={voiceInstructCfg.scenes}
                          onChange={() => { ttsForm.setFieldValue('instruct_role', undefined); ttsForm.setFieldValue('instruct_identity', undefined) }} />
                      </Form.Item>
                    )}
                    {voiceInstructCfg.roles.length > 0 && (
                      <Form.Item name="instruct_role" label="角色（可选）"
                        extra={`支持：${voiceInstructCfg.roles.map(r => r.value).join('、')}`}>
                        <Select allowClear placeholder="与场景、身份互斥" options={voiceInstructCfg.roles}
                          onChange={() => { ttsForm.setFieldValue('instruct_scene', undefined); ttsForm.setFieldValue('instruct_identity', undefined) }} />
                      </Form.Item>
                    )}
                    {voiceInstructCfg.identities.length > 0 && (
                      <Form.Item name="instruct_identity" label="身份（可选）"
                        extra={`支持：${voiceInstructCfg.identities.map(i => i.value).join('、')}`}>
                        <Select allowClear placeholder="与场景、角色互斥" options={voiceInstructCfg.identities}
                          onChange={() => { ttsForm.setFieldValue('instruct_scene', undefined); ttsForm.setFieldValue('instruct_role', undefined) }} />
                      </Form.Item>
                    )}
                  </>
                )}
                {voiceType === 'system_plain' && selectedVoice && (
                  <Alert type="info" showIcon message="当前系统音色不支持 Instruct 指令" style={{ marginBottom: 16 }} />
                )}
                {voiceType === 'custom' && (
                  <Form.Item name="instruction" label="指令（Instruct）" extra="复刻/设计音色支持任意自然语言指令控制语音效果">
                    <TextArea rows={2} placeholder="如：请用非常开心地语气说话。" maxLength={100} />
                  </Form.Item>
                )}
                <Form.Item name="enable_ssml" label="启用 SSML" valuePropName="checked">
                  <Switch />
                </Form.Item>
                <Button type="primary" icon={<SoundOutlined />} onClick={handleTTS} loading={submitting} block size="large">
                  开始合成
                </Button>
              </Form>
            ),
          },
          {
            key: 'voice_clone',
            label: <span><ScissorOutlined /> 声音复刻</span>,
            children: (
              <Form form={cloneForm} layout="vertical">
                <Form.Item name="name" label="音色名称">
                  <Input placeholder="给复刻的音色起个名字" />
                </Form.Item>
                <Form.Item name="audio_url" label="音频样本" rules={[{ required: true, message: '请选择音频' }]}
                  extra="从音频库选择 10~20 秒清晰人声音频，无背景噪音效果最佳">
                  {audioUrlOptions.length > 0 ? (
                    <Select
                      showSearch
                      optionFilterProp="label"
                      placeholder="从音频库选择"
                      options={audioUrlOptions}
                    />
                  ) : (
                    <div>
                      <Input placeholder="输入音频 URL 或先到音频库上传" />
                      <Text type="secondary" style={{ fontSize: 12 }}>音频库暂无音频，请先到音频库上传</Text>
                    </div>
                  )}
                </Form.Item>
                <Form.Item name="prefix" label="音色前缀" rules={[
                  { required: true, message: '请输入前缀' },
                  { pattern: /^[a-z0-9]{1,10}$/, message: '仅小写字母和数字，不超过10位' },
                ]} extra="仅小写字母和数字，不超过10位。生成格式: cosyvoice-v3-flash-{prefix}-xxxx">
                  <Input placeholder="如 myvoice" maxLength={10} />
                </Form.Item>
                <Form.Item name="language_hints" label="音频语言提示">
                  <Select allowClear placeholder="可选，辅助识别音频语种" options={LANGUAGE_OPTIONS} />
                </Form.Item>
                <Button type="primary" icon={<ScissorOutlined />} onClick={handleVoiceClone} loading={submitting} block size="large">
                  开始复刻
                </Button>
              </Form>
            ),
          },
          {
            key: 'voice_design',
            label: <span><ExperimentOutlined /> 声音设计</span>,
            children: (
              <Form form={designForm} layout="vertical" initialValues={{ sample_rate: 24000, response_format: 'wav' }}>
                <Form.Item name="name" label="音色名称">
                  <Input placeholder="给设计的音色起个名字" />
                </Form.Item>
                <Form.Item name="voice_prompt" label="声音描述" rules={[{ required: true, message: '请输入声音描述' }]}
                  extra="详细描述期望的音色特征，如年龄、性别、情感、语速等">
                  <TextArea rows={3} placeholder="如：沉稳的中年男性播音员，音色低沉浑厚，富有磁性，语速平稳" maxLength={500} showCount />
                </Form.Item>
                <Form.Item name="preview_text" label="试听文本" rules={[{ required: true, message: '请输入试听文本' }]}
                  extra="用于生成预览音频的文本">
                  <TextArea rows={2} placeholder="如：各位听众朋友，大家好，欢迎收听晚间新闻。" maxLength={200} showCount />
                </Form.Item>
                <Form.Item name="prefix" label="音色前缀" rules={[
                  { required: true, message: '请输入前缀' },
                  { pattern: /^[a-z0-9]{1,10}$/, message: '仅小写字母和数字，不超过10位' },
                ]}>
                  <Input placeholder="如 announcer" maxLength={10} />
                </Form.Item>
                <Form.Item name="sample_rate" label="预览采样率">
                  <Select options={[
                    { value: 16000, label: '16000 Hz' },
                    { value: 24000, label: '24000 Hz' },
                    { value: 48000, label: '48000 Hz' },
                  ]} />
                </Form.Item>
                <Form.Item name="response_format" label="预览格式">
                  <Select options={[
                    { value: 'wav', label: 'WAV' },
                    { value: 'mp3', label: 'MP3' },
                    { value: 'pcm', label: 'PCM' },
                  ]} />
                </Form.Item>
                <Button type="primary" icon={<ExperimentOutlined />} onClick={handleVoiceDesign} loading={submitting} block size="large">
                  开始设计
                </Button>
              </Form>
            ),
          },
          {
            key: 'my_voices',
            label: <span><AudioOutlined /> 我的音色 ({voices.length})</span>,
            children: (
              <>
                {voices.length === 0 ? (
                  <Empty description="暂无自定义音色，可通过声音复刻或声音设计创建" />
                ) : (
                  <List
                    dataSource={voices}
                    renderItem={(v) => (
                      <List.Item
                        actions={[
                          v.preview_audio_url && (
                            <Button
                              size="small"
                              icon={playingId === `voice-${v.id}` ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                              onClick={() => handlePlayPause(`voice-${v.id}`, v.preview_audio_url!)}
                            >
                              {playingId === `voice-${v.id}` ? '暂停' : '试听'}
                            </Button>
                          ),
                          <Popconfirm title="确定删除该音色？删除后不可恢复。" onConfirm={() => handleDeleteVoice(v.id)}>
                            <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                          </Popconfirm>,
                        ].filter(Boolean)}
                      >
                        <List.Item.Meta
                          title={<Space>{v.name} <Tag color={v.status === 'ok' ? 'success' : v.status === 'deploying' ? 'processing' : 'error'}>{v.status === 'ok' ? '可用' : v.status === 'deploying' ? '审核中' : '不可用'}</Tag></Space>}
                          description={
                            <Space direction="vertical" size={0}>
                              <Text type="secondary">来源: {v.source === 'clone' ? '声音复刻' : '声音设计'} | 模型: {v.target_model}</Text>
                              <Text type="secondary" copyable={{ text: v.voice_id }}>ID: {v.voice_id}</Text>
                              {v.voice_prompt && <Text type="secondary">描述: {v.voice_prompt}</Text>}
                            </Space>
                          }
                        />
                      </List.Item>
                    )}
                  />
                )}
              </>
            ),
          },
          {
            key: 'task_history',
            label: <span><SoundOutlined /> 任务历史 ({tasks.length})</span>,
            children: (
              <>
                {loading ? (
                  <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
                ) : tasks.length === 0 ? (
                  <Empty description="暂无任务" />
                ) : (
                  <List
                    dataSource={tasks}
                    renderItem={(task) => (
                      <List.Item
                        actions={[
                          task.result_audio_url && (
                            <Button
                              size="small"
                              icon={playingId === task.id ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                              onClick={() => handlePlayPause(task.id, task.result_audio_url!)}
                            >
                              {playingId === task.id ? '暂停' : '播放'}
                            </Button>
                          ),
                          task.result_audio_url && !task.saved_to_library && (
                            <Button size="small" icon={<SaveOutlined />} onClick={() => handleSaveToLibrary(task.id)}>
                              存入音频库
                            </Button>
                          ),
                          <Popconfirm title="确定删除？" onConfirm={() => handleDeleteTask(task.id)}>
                            <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                          </Popconfirm>,
                        ].filter(Boolean)}
                      >
                        <List.Item.Meta
                          title={
                            <Space>
                              {task.name || task.id.slice(0, 8)}
                              <Tag>{taskTypeLabel(task.task_type)}</Tag>
                              {statusTag(task.status)}
                              {task.saved_to_library && <Tag color="blue">已存库</Tag>}
                              <span style={{ display: 'inline-flex', gap: 2, marginLeft: 4 }}>
                                {([
                                  { key: 'star', icon: <StarOutlined />, activeIcon: <StarFilled />, color: '#faad14' },
                                  { key: 'flag', icon: <FlagOutlined />, activeIcon: <FlagFilled />, color: '#ff4d4f' },
                                  { key: 'check', icon: <CheckOutlined />, activeIcon: <CheckOutlined />, color: '#52c41a' },
                                  { key: 'cross', icon: <CloseOutlined />, activeIcon: <CloseOutlined />, color: '#ff4d4f' },
                                ] as const).map(marker => {
                                  const active = (task.markers || []).includes(marker.key)
                                  return (
                                    <Button
                                      key={marker.key}
                                      type="text"
                                      size="small"
                                      icon={active ? marker.activeIcon : marker.icon}
                                      style={{
                                        color: active ? marker.color : '#d9d9d9',
                                        fontSize: 13,
                                        padding: '1px 4px',
                                        height: 22,
                                        minWidth: 22,
                                      }}
                                      onClick={(e) => { e.stopPropagation(); handleToggleAudioMarker(task.id, marker.key) }}
                                    />
                                  )
                                })}
                              </span>
                            </Space>
                          }
                          description={
                            <Space direction="vertical" size={4}>
                              {task.task_type === 'tts' && <Text type="secondary">文本: {task.text?.slice(0, 80)}{(task.text?.length || 0) > 80 ? '...' : ''}</Text>}
                              {task.task_type === 'voice_clone' && <Text type="secondary">前缀: {task.prefix}</Text>}
                              {task.task_type === 'voice_design' && <Text type="secondary">描述: {task.voice_prompt?.slice(0, 60)}</Text>}
                              <Space size={[4, 4]} wrap>
                                {task.task_type === 'tts' && task.voice && (
                                  <Tag color="blue">{getVoiceDisplayName(task.voice)}</Tag>
                                )}
                                {task.task_type === 'tts' && task.format && (
                                  <Tag>{FORMAT_LABEL_MAP[task.format] || task.format}</Tag>
                                )}
                                {task.task_type === 'tts' && task.speech_rate !== undefined && task.speech_rate !== 1.0 && (
                                  <Tag>语速 {task.speech_rate}x</Tag>
                                )}
                                {task.task_type === 'tts' && task.pitch_rate !== undefined && task.pitch_rate !== 1.0 && (
                                  <Tag>音高 {task.pitch_rate}x</Tag>
                                )}
                                {task.task_type === 'tts' && task.volume !== undefined && task.volume !== 50 && (
                                  <Tag>音量 {task.volume}</Tag>
                                )}
                                {task.task_type === 'tts' && task.enable_ssml && (
                                  <Tag color="purple">SSML</Tag>
                                )}
                                {task.audio_duration != null && (
                                  <Tag color="cyan">{formatDuration(task.audio_duration)}</Tag>
                                )}
                              </Space>
                              {task.result_voice_id && <Text type="secondary" copyable={{ text: task.result_voice_id }}>音色ID: {task.result_voice_id}</Text>}
                              {task.error_message && <Text type="danger">{task.error_message}</Text>}
                              <Text type="secondary" style={{ fontSize: 12 }}>{new Date(task.created_at).toLocaleString()}</Text>
                              {task.request_id && (
                                <Text type="secondary" style={{ fontSize: 11, fontFamily: 'monospace' }}>
                                  Request ID: {task.request_id}
                                </Text>
                              )}
                            </Space>
                          }
                        />
                      </List.Item>
                    )}
                  />
                )}
              </>
            ),
          },
        ]} />
      </Card>
    </div>
  )
}

export default AudioStudioPage
