import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { Buffer } from 'node:buffer'
import ts from 'typescript'

const sourceUrl = new URL('../src/pages/VideoStudio/referenceTokenPolicy.ts', import.meta.url)
const source = await readFile(sourceUrl, 'utf8')
const transpiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2020,
    target: ts.ScriptTarget.ES2020,
  },
})
const moduleUrl = `data:text/javascript;base64,${Buffer.from(transpiled.outputText).toString('base64')}`
const {
  buildReferenceTokenOptions,
  insertReferenceTokenAtSelection,
} = await import(moduleUrl)

assert.deepEqual(
  buildReferenceTokenOptions({
    role: 'reference_image',
    roleIndex: 0,
    roleCounts: { reference_image: 2, reference_video: 1 },
  }),
  [{ key: 'default', label: '图1', token: '图1' }],
)

assert.deepEqual(
  buildReferenceTokenOptions({
    role: 'reference_video',
    roleIndex: 1,
    roleCounts: { reference_image: 2, reference_video: 2 },
  }),
  [{ key: 'default', label: '视频2', token: '视频2' }],
)

assert.deepEqual(
  buildReferenceTokenOptions({
    role: 'reference_image',
    roleIndex: 2,
    roleCounts: { reference_image: 3, reference_video: 0 },
    policy: {
      mode: 'media_reference_tokens',
      index_base: 1,
      numbering_scope: 'by_type',
      tokens: {
        reference_image: { template: '[Image {index}]' },
      },
    },
  }),
  [{ key: 'default', label: '[Image 3]', token: '[Image 3]' }],
)

assert.deepEqual(
  buildReferenceTokenOptions({
    role: 'reference_video',
    roleIndex: 0,
    roleCounts: { reference_image: 2, reference_video: 1 },
    policy: {
      mode: 'media_reference_tokens',
      index_base: 1,
      numbering_scope: 'by_type',
      tokens: {
        reference_image: {
          template: '图{index}',
          variants: [{ key: 'en', label: 'Image {index}', template: 'Image {index}' }],
        },
        reference_video: {
          template: '视频{index}',
          variants: [{ key: 'en', label: 'Video {index}', template: 'Video {index}' }],
        },
      },
    },
  }),
  [
    { key: 'default', label: '视频1', token: '视频1' },
    { key: 'en', label: 'Video 1', token: 'Video 1' },
  ],
)

assert.deepEqual(
  buildReferenceTokenOptions({
    role: 'reference_image',
    roleIndex: 0,
    roleCounts: { reference_image: 2, reference_video: 1 },
    policy: {
      mode: 'media_reference_tokens',
      index_base: 1,
      numbering_scope: 'combined',
      reference_order: ['reference_video', 'reference_image'],
      tokens: {
        reference_image: { template: 'character{index}' },
        reference_video: { template: 'character{index}' },
      },
    },
  }),
  [{ key: 'default', label: 'character2', token: 'character2' }],
)

assert.deepEqual(
  buildReferenceTokenOptions({
    role: 'reference_image',
    roleIndex: 1,
    roleCounts: { reference_image: 2, reference_video: 0 },
    policy: {
      mode: 'media_reference_tokens',
      index_base: 1,
      numbering_scope: 'by_type',
      tokens: {
        reference_image: { template: '<<<image_{index}>>>' },
      },
    },
  }),
  [{ key: 'default', label: '<<<image_2>>>', token: '<<<image_2>>>' }],
)

assert.deepEqual(
  insertReferenceTokenAtSelection('让角色奔跑', '图1', 1, 3),
  { value: '让图1奔跑', cursor: 3 },
)

assert.deepEqual(
  insertReferenceTokenAtSelection('让角色奔跑', '[Image 1]'),
  { value: '让角色奔跑 [Image 1]', cursor: 15 },
)
