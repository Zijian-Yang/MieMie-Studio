import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { Buffer } from 'node:buffer'
import ts from 'typescript'

const sourceUrl = new URL('../src/pages/VideoStudio/capabilityLimits.ts', import.meta.url)
const source = await readFile(sourceUrl, 'utf8')
const transpiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2020,
    target: ts.ScriptTarget.ES2020,
  },
})
const moduleUrl = `data:text/javascript;base64,${Buffer.from(transpiled.outputText).toString('base64')}`
const { resolveReferenceCollectionLimits } = await import(moduleUrl)

assert.deepEqual(
  resolveReferenceCollectionLimits('reference_to_video', {
    ui_hints: {
      max_reference_images: 9,
      max_reference_videos: 0,
      max_reference_total: 9,
    },
  }),
  {
    maxReferenceImages: 9,
    maxReferenceVideos: 0,
    maxReferenceTotal: 9,
  },
)

assert.deepEqual(
  resolveReferenceCollectionLimits('reference_to_video', { ui_hints: {} }),
  {
    maxReferenceImages: 1,
    maxReferenceVideos: 5,
    maxReferenceTotal: 5,
  },
)

assert.deepEqual(
  resolveReferenceCollectionLimits('video_edit_global', {
    ui_hints: {
      max_reference_images: 0,
      max_reference_videos: 0,
      max_reference_total: 0,
    },
  }),
  {
    maxReferenceImages: 0,
    maxReferenceVideos: 0,
    maxReferenceTotal: 0,
  },
)
