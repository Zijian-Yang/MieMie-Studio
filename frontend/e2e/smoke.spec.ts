import { expect, test, chromium, type Page } from '@playwright/test'
import { resolveChromiumExecutablePath } from './playwrightChromium.js'

const BASE_URL = 'http://127.0.0.1:4173'
const CHROMIUM_EXECUTABLE_PATH = resolveChromiumExecutablePath()

const AUTH_STATE = {
  token: 'playwright-token',
  user: {
    id: 'user-1',
    username: 'playwright',
    display_name: 'Playwright User',
    created_at: '2026-04-23T00:00:00',
  },
  isAuthenticated: true,
}

async function withPage(run: (page: Page) => Promise<void>) {
  let browser: Awaited<ReturnType<typeof chromium.launch>> | null = null
  try {
    browser = await chromium.launch({
      headless: true,
      ...(CHROMIUM_EXECUTABLE_PATH ? { executablePath: CHROMIUM_EXECUTABLE_PATH } : {}),
    })
  } catch (error) {
    test.skip(true, `当前环境无法启动 Playwright Chromium: ${String(error)}`)
    return
  }

  try {
    const page = await browser.newPage({ baseURL: BASE_URL })
    await run(page)
  } finally {
    await browser.close()
  }
}

async function seedAuth(page: Page) {
  await page.addInitScript((authState) => {
    window.localStorage.setItem('auth-storage', JSON.stringify({
      state: authState,
      version: 0,
    }))
  }, AUTH_STATE)
}

function createVideoStudioSmokeTask() {
  return {
    id: 'video-task-1',
    project_id: 'project-1',
    name: 'Smoke 视频任务',
    task_type: 'image_to_video',
    task_kind: 'image_to_video',
    provider: 'wan',
    key_profile: 'test',
    model_id: 'wan2.5-i2v-preview',
    input_assets: {
      first_frame: ['https://assets.example.com/first-frame.png'],
      audio: [],
    },
    normalized_params: {
      resolution: '720P',
      duration: 5,
      prompt_extend: true,
      watermark: false,
    },
    provider_payload_snapshot: {
      model: 'wan2.5-i2v-preview',
      prompt: '镜头缓慢推进',
    },
    provider_result_meta: {
      request_id: 'req-smoke-1',
    },
    mode: 'first_frame',
    first_frame_url: 'https://assets.example.com/first-frame.png',
    prompt: '镜头缓慢推进',
    negative_prompt: '',
    model: 'wan2.5-i2v-preview',
    duration: 5,
    watermark: false,
    auto_audio: false,
    resolution: '720P',
    prompt_extend: true,
    group_count: 1,
    video_urls: ['https://assets.example.com/result.mp4'],
    thumbnail_url: 'https://assets.example.com/first-frame.png',
    video_markers: {
      'https://assets.example.com/result.mp4': ['star'],
    },
    task_ids: ['dashscope-task-1'],
    request_ids: ['req-smoke-1'],
    status: 'succeeded',
    created_at: '2026-04-23T00:00:00',
    updated_at: '2026-04-23T00:01:00',
  }
}

function createVideoStudioCreatedTask(payload: Record<string, any> = {}) {
  return {
    id: 'video-task-created',
    project_id: payload.project_id || 'project-1',
    name: payload.name || 'Smoke 创建任务',
    task_type: payload.task_type || 'text_to_video',
    task_kind: payload.task_kind || 'text_to_video',
    provider: payload.provider || 'wan',
    key_profile: 'test',
    model_id: payload.model_id || payload.model || 'wan2.6-t2v',
    input_assets: payload.input_assets || {},
    normalized_params: payload.normalized_params || {
      resolution: '720P',
      duration: 5,
      prompt_extend: true,
      watermark: false,
    },
    provider_payload_snapshot: null,
    provider_result_meta: {},
    mode: 'first_frame',
    prompt: payload.prompt || 'Smoke 创建流程提示词',
    negative_prompt: payload.negative_prompt || '',
    model: payload.model || payload.model_id || 'wan2.6-t2v',
    duration: payload.normalized_params?.duration || 5,
    watermark: payload.normalized_params?.watermark || false,
    auto_audio: false,
    resolution: payload.normalized_params?.resolution || '720P',
    prompt_extend: payload.normalized_params?.prompt_extend ?? true,
    t2v_prompt_extend: payload.normalized_params?.prompt_extend ?? true,
    group_count: payload.group_count || 1,
    video_urls: [],
    video_markers: {},
    task_ids: [],
    request_ids: [],
    status: 'pending',
    created_at: '2026-04-23T00:02:00',
    updated_at: '2026-04-23T00:02:00',
  }
}

function createProjectSmokeProject() {
  return {
    id: 'project-1',
    name: 'Playwright 项目',
    description: '用于 smoke 测试',
    script: {
      shots: [
        { id: 'shot-1', content: '第一镜' },
        { id: 'shot-2', content: '第二镜' },
      ],
    },
    character_ids: ['character-1', 'character-2'],
    scene_ids: [],
    prop_ids: [],
    created_at: '2026-04-23T00:00:00',
    updated_at: '2026-04-23T00:00:00',
  }
}

function createVideoStudioCapabilities() {
  return {
    task_kinds: [
      {
        id: 'text_to_video',
        label: '文生视频',
        description: '通过提示词生成视频。',
        legacy_task_types: ['text_to_video'],
        model_ids: ['wan2.6-t2v'],
        default_model_id: 'wan2.6-t2v',
      },
    ],
    models: {
      'wan2.6-t2v': {
        id: 'wan2.6-t2v',
        name: 'Wan 文生视频',
        provider: 'wan',
        type: 'video',
        description: 'Smoke 测试模型',
        capabilities: {
          max_concurrent: 2,
        },
        supported_task_kinds: ['text_to_video'],
        task_profiles: {
          text_to_video: {
            task_kind: 'text_to_video',
            label: '文生视频',
            description: '通过提示词生成视频。',
            input_roles: [],
            parameters: [],
            supported_narrative_modes: ['single'],
            default_values: {
              resolution: '720P',
              duration: 5,
              prompt_extend: true,
              watermark: false,
            },
          },
        },
      },
    },
    legacy_task_kind_map: {
      text_to_video: 'text_to_video',
    },
  }
}

function createReferenceVideoStudioCapabilities() {
  return {
    task_kinds: [
      {
        id: 'reference_to_video',
        label: '参考生视频',
        description: '通过参考素材和提示词生成视频。',
        legacy_task_types: ['reference_to_video'],
        model_ids: ['wan2.7-r2v'],
        default_model_id: 'wan2.7-r2v',
      },
    ],
    models: {
      'wan2.7-r2v': {
        id: 'wan2.7-r2v',
        name: 'Wan 参考生视频',
        provider: 'wan',
        type: 'video',
        description: 'Smoke 参考素材模型',
        capabilities: {
          max_concurrent: 2,
        },
        supported_task_kinds: ['reference_to_video'],
        task_profiles: {
          reference_to_video: {
            task_kind: 'reference_to_video',
            label: '参考生视频',
            description: '通过参考素材和提示词生成视频。',
            input_roles: [],
            parameters: [],
            supported_narrative_modes: ['single'],
            default_values: {
              resolution: '720P',
              duration: 5,
              prompt_extend: true,
              watermark: false,
            },
            ui_hints: {
              max_reference_images: 1,
              max_reference_videos: 0,
              max_reference_total: 1,
            },
          },
        },
      },
    },
    legacy_task_kind_map: {
      reference_to_video: 'reference_to_video',
    },
  }
}

function createVideoEditLocalCapabilities() {
  return {
    task_kinds: [
      {
        id: 'video_edit_local',
        label: '局部编辑',
        description: '选择源视频并绘制 Mask 后局部编辑视频。',
        legacy_task_types: ['video_edit'],
        model_ids: ['wan2.5-video-edit-local'],
        default_model_id: 'wan2.5-video-edit-local',
      },
    ],
    models: {
      'wan2.5-video-edit-local': {
        id: 'wan2.5-video-edit-local',
        name: 'Wan 局部编辑',
        provider: 'wan',
        type: 'video',
        description: 'Smoke 局部编辑模型',
        capabilities: {
          max_concurrent: 1,
        },
        supported_task_kinds: ['video_edit_local'],
        task_profiles: {
          video_edit_local: {
            task_kind: 'video_edit_local',
            label: '局部编辑',
            description: '选择源视频并绘制 Mask 后局部编辑视频。',
            input_roles: ['source_video'],
            parameters: [],
            supported_narrative_modes: ['single'],
            default_values: {
              resolution: '720P',
              duration: 5,
            },
          },
        },
      },
    },
    legacy_task_kind_map: {
      video_edit: 'video_edit_local',
    },
  }
}

async function mockProjectApis(
  page: Page,
  options: {
    videoStudioTasks?: any[]
    videoStudioCapabilities?: any
    galleryImages?: any[]
    audioItems?: any[]
    videoLibraryItems?: any[]
    onVideoStudioCreate?: (payload: Record<string, any>) => void
  } = {},
) {
  const videoStudioTasks = options.videoStudioTasks ?? []
  const videoStudioCapabilities = options.videoStudioCapabilities ?? createVideoStudioCapabilities()
  const galleryImages = options.galleryImages ?? []
  const audioItems = options.audioItems ?? []
  const videoLibraryItems = options.videoLibraryItems ?? []
  const smokeProject = createProjectSmokeProject()

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname

    if (path === '/api/projects') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          projects: [smokeProject],
          total: 1,
        }),
      })
      return
    }

    if (path === '/api/projects/project-1') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(smokeProject),
      })
      return
    }

    if (path === '/api/settings') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          api_key_masked: '',
          is_api_key_set: false,
          test_api_key_masked: '',
          is_test_api_key_set: false,
          production_api_key_masked: '',
          is_production_api_key_set: false,
          wan_key_profile: 'test',
          kling_key_profile: 'test',
          vidu_key_profile: 'test',
          video_task_notifications_enabled: false,
          image_task_notifications_enabled: false,
          api_region: 'cn-beijing',
          base_url: 'https://dashscope.aliyuncs.com/api/v1',
          llm: {},
          image: {},
          image_edit: {},
          video: {
            model: 'wan2.5-i2v-preview',
            resolution: '720P',
            duration: 5,
            prompt_extend: true,
            watermark: false,
            audio: false,
          },
          text_to_video: {},
          ref_video: {},
          oss: {
            enabled: false,
            access_key_id_masked: '',
            access_key_secret_masked: '',
            is_configured: false,
            bucket_name: '',
            endpoint: '',
            prefix: '',
          },
          available_regions: {},
          available_llm_models: {},
          available_image_models: {},
          available_image_edit_models: {},
          available_video_models: {},
          available_text_to_video_models: {},
          available_ref_video_models: {},
          available_keyframe_to_video_models: {},
          available_video_repainting_models: {},
          available_video_edit_models: {},
        }),
      })
      return
    }

    if (path === '/api/videos') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ videos: [] }) })
      return
    }

    if (path === '/api/frames') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ frames: [] }) })
      return
    }

    if (path === '/api/video-studio/capabilities') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(videoStudioCapabilities),
      })
      return
    }

    if (path === '/api/video-studio/preview-payload') {
      const payload = route.request().postDataJSON() as Record<string, any>
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          canonical_request: payload,
          provider_payload: {
            model: payload.model || payload.model_id,
            prompt: payload.prompt,
          },
          validation_warnings: [],
        }),
      })
      return
    }

    if (path === '/api/video-studio/prepare-source-video') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          preview_image_data_url: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
          preview_image_url: 'https://assets.example.com/source-preview.png',
          metadata: {
            width: 320,
            height: 180,
            fps: 24,
            duration: 4,
            frame_count: 96,
            file_size: 1024,
            format: 'mp4',
            warnings: [],
          },
          warnings: [],
        }),
      })
      return
    }

    if (path === '/api/video-studio' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON() as Record<string, any>
      options.onVideoStudioCreate?.(payload)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ task: createVideoStudioCreatedTask(payload) }),
      })
      return
    }

    if (path === '/api/video-studio') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ tasks: videoStudioTasks }) })
      return
    }

    if (path === '/api/gallery') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ images: galleryImages }) })
      return
    }

    if (path === '/api/audio') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ audios: audioItems }) })
      return
    }

    if (path === '/api/video-library') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ videos: videoLibraryItems }) })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({}),
    })
  })
}

test('登录页可以正常渲染', async () => {
  await withPage(async (page) => {
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: 'MieMie Studio' })).toBeVisible()
    await expect(page.getByRole('button', { name: '登录' })).toBeVisible()
  })
})

test('未登录访问受保护路由会跳转到登录页', async () => {
  await withPage(async (page) => {
    await page.goto('/projects')
    await expect(page).toHaveURL(/\/login$/)
  })
})

test('项目列表可渲染已有项目', async () => {
  await withPage(async (page) => {
    await seedAuth(page)
    await mockProjectApis(page)
    await page.goto('/projects')

    await expect(page.getByRole('heading', { name: '项目列表' })).toBeVisible()
    await expect(page.getByRole('button', { name: '新建项目' })).toBeVisible()
    await expect(page.getByText('Playwright 项目')).toBeVisible()
    await expect(page.getByText('用于 smoke 测试')).toBeVisible()
    await expect(page.getByText('分镜数：2')).toBeVisible()
    await expect(page.getByText('角色数：2')).toBeVisible()
    await expect(page.getByRole('button', { name: '打开' })).toBeVisible()
    await expect(page.getByRole('button', { name: '删除' })).toBeVisible()
  })
})

test('旧版视频页展示迁退提示', async () => {
  await withPage(async (page) => {
    await seedAuth(page)
    await mockProjectApis(page)
    await page.goto('/project/project-1/videos')
    await expect(page.getByText('旧版视频生成页已进入迁退阶段')).toBeVisible()
    await expect(page.getByRole('button', { name: '前往视频工作室' })).toBeVisible()
  })
})

test('视频工作室空态可渲染', async () => {
  await withPage(async (page) => {
    await seedAuth(page)
    await mockProjectApis(page)
    await page.goto('/project/project-1/video-studio')
    await expect(page.getByText('暂无任务')).toBeVisible()
  })
})

test('视频工作室文生视频创建流程可提交', async () => {
  await withPage(async (page) => {
    await seedAuth(page)
    await mockProjectApis(page)
    await page.goto('/project/project-1/video-studio')

    await page.getByRole('button', { name: '新建任务' }).click()
    await expect(page.getByText('新建视频任务')).toBeVisible()
    await expect(page.getByRole('tab', { name: '文生视频' })).toBeVisible()

    await page.getByPlaceholder('留空自动生成').fill('Smoke 创建任务')
    await page.getByPlaceholder('描述想要生成的视频内容').fill('Smoke 创建流程提示词')
    await page.getByRole('button', { name: '创建任务' }).click()

    await expect(page.getByText('任务已创建')).toBeVisible()
    await expect(page.getByText('Smoke 创建任务')).toBeVisible()
    await expect(page.getByText('文生视频').first()).toBeVisible()
    await expect(page.getByText('WAN').first()).toBeVisible()
    await expect(page.getByText('等待中').first()).toBeVisible()
    await expect(page.getByText('0/1')).toBeVisible()
  })
})

test('视频工作室参考素材创建流程可提交', async () => {
  await withPage(async (page) => {
    let createdPayload: Record<string, any> | null = null
    await seedAuth(page)
    await mockProjectApis(page, {
      videoStudioCapabilities: createReferenceVideoStudioCapabilities(),
      galleryImages: [
        {
          id: 'gallery-reference-1',
          name: 'Smoke 参考图',
          url: 'https://assets.example.com/reference-image.png',
          created_at: '2026-04-23T00:00:00',
        },
      ],
      onVideoStudioCreate: (payload) => {
        createdPayload = payload
      },
    })
    await page.goto('/project/project-1/video-studio')

    await page.getByRole('button', { name: '新建任务' }).click()
    await expect(page.getByText('新建视频任务')).toBeVisible()
    await expect(page.getByRole('tab', { name: '参考生视频' })).toBeVisible()

    await page.locator('.ant-select-selector').filter({ hasText: '从图库添加参考图' }).click()
    await page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').getByText('Smoke 参考图').click()
    await expect(page.getByText('已选参考素材')).toBeVisible()

    await page.getByPlaceholder('描述想要生成的视频内容').fill('Smoke 参考素材提示词')
    await page.getByRole('button', { name: '创建任务' }).click()

    await expect(page.getByText('任务已创建')).toBeVisible()
    await expect.poll(() => createdPayload?.input_assets?.reference_media?.[0]?.url).toBe('https://assets.example.com/reference-image.png')
    await expect.poll(() => createdPayload?.input_assets?.reference_media?.[0]?.type).toBe('reference_image')
  })
})

test('视频工作室局部编辑源视频选择后显示 Mask 面板', async () => {
  await withPage(async (page) => {
    await seedAuth(page)
    await mockProjectApis(page, {
      videoStudioCapabilities: createVideoEditLocalCapabilities(),
      videoLibraryItems: [
        {
          id: 'video-source-1',
          name: 'Smoke 源视频',
          url: 'https://assets.example.com/source-video.mp4',
          created_at: '2026-04-23T00:00:00',
        },
      ],
    })
    await page.goto('/project/project-1/video-studio')

    await page.getByRole('button', { name: '新建任务' }).click()
    await expect(page.getByText('新建视频任务')).toBeVisible()
    await expect(page.getByRole('tab', { name: '局部编辑' })).toBeVisible()

    await page.locator('.ant-select-selector').filter({ hasText: '从视频库选择视频' }).click()
    await page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').getByText('Smoke 源视频').click()

    await expect(page.getByText('320 × 180 · 24.00 FPS · 4.00 秒')).toBeVisible()
    await expect(page.getByText('局部编辑 Mask')).toBeVisible()
    await expect(page.getByPlaceholder('描述需要替换或新增的局部内容')).toBeVisible()
  })
})

test('视频工作室任务列表和详情弹窗可渲染', async () => {
  await withPage(async (page) => {
    await seedAuth(page)
    await mockProjectApis(page, { videoStudioTasks: [createVideoStudioSmokeTask()] })
    await page.goto('/project/project-1/video-studio')

    await expect(page.getByText('Smoke 视频任务')).toBeVisible()
    await expect(page.getByText('图生视频').first()).toBeVisible()
    await expect(page.getByText('WAN').first()).toBeVisible()
    await expect(page.getByText('已完成').first()).toBeVisible()
    await expect(page.getByText('1/1')).toBeVisible()

    await page.getByRole('button', { name: '查看' }).click()
    await expect(page.getByText('输入素材')).toBeVisible()
    await expect(page.getByText('关键参数')).toBeVisible()
    await expect(page.getByText('生成结果')).toBeVisible()
    await expect(page.getByText('提示词')).toBeVisible()
    await expect(page.getByText('镜头缓慢推进')).toBeVisible()
    await expect(page.getByRole('button', { name: '编辑' })).toBeVisible()
    await expect(page.getByRole('button', { name: '重新生成' })).toBeVisible()
    await expect(page.getByRole('button', { name: '保存到视频库' })).toBeVisible()
    await expect(page.getByRole('button', { name: '保存尾帧' })).toBeVisible()
    await expect(page.getByText('开发者模式')).toBeVisible()
  })
})
