import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { Buffer } from 'node:buffer'
import ts from 'typescript'

const sourceUrl = new URL('../src/pages/VideoStudio/taskCardLayout.ts', import.meta.url)
const source = await readFile(sourceUrl, 'utf8')
const transpiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2020,
    target: ts.ScriptTarget.ES2020,
  },
})
const moduleUrl = `data:text/javascript;base64,${Buffer.from(transpiled.outputText).toString('base64')}`
const {
  TASK_CARD_META_ROW_STYLE,
  TASK_CARD_TAGS_STYLE,
  TASK_CARD_PROGRESS_STYLE,
} = await import(moduleUrl)

assert.equal(TASK_CARD_META_ROW_STYLE.flexWrap, 'wrap')
assert.equal(TASK_CARD_META_ROW_STYLE.width, '100%')
assert.equal(TASK_CARD_TAGS_STYLE.flexWrap, 'wrap')
assert.equal(TASK_CARD_TAGS_STYLE.minWidth, 0)
assert.equal(TASK_CARD_PROGRESS_STYLE.flex, '0 0 auto')
assert.equal(TASK_CARD_PROGRESS_STYLE.marginLeft, 'auto')
