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

async function mockProjectApis(page: Page) {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname

    if (path === '/api/projects/project-1') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'project-1',
          name: 'Playwright 项目',
          description: '用于 smoke 测试',
          script: { shots: [] },
          character_ids: [],
          scene_ids: [],
          prop_ids: [],
          created_at: '2026-04-23T00:00:00',
          updated_at: '2026-04-23T00:00:00',
        }),
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

    if (path === '/api/video-studio') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ tasks: [] }) })
      return
    }

    if (path === '/api/gallery') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ images: [] }) })
      return
    }

    if (path === '/api/audio') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ audios: [] }) })
      return
    }

    if (path === '/api/video-library') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ videos: [] }) })
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
