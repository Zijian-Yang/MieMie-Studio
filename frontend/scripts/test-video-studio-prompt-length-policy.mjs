import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { Buffer } from 'node:buffer'
import ts from 'typescript'

const sourceUrl = new URL('../src/pages/VideoStudio/promptLengthPolicy.ts', import.meta.url)
const source = await readFile(sourceUrl, 'utf8')
const transpiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2020,
    target: ts.ScriptTarget.ES2020,
  },
})
const moduleUrl = `data:text/javascript;base64,${Buffer.from(transpiled.outputText).toString('base64')}`
const {
  HAPPYHORSE_PROMPT_LENGTH_POLICY,
  countPromptLengthUnits,
  getPromptLengthError,
} = await import(moduleUrl)

assert.equal(countPromptLengthUnits('马'.repeat(2500), HAPPYHORSE_PROMPT_LENGTH_POLICY), 5000)
assert.equal(countPromptLengthUnits('a'.repeat(5000), HAPPYHORSE_PROMPT_LENGTH_POLICY), 5000)
assert.equal(countPromptLengthUnits('马'.repeat(2499) + 'ab', HAPPYHORSE_PROMPT_LENGTH_POLICY), 5000)
assert.equal(countPromptLengthUnits('A，🙂马', HAPPYHORSE_PROMPT_LENGTH_POLICY), 5)

assert.equal(getPromptLengthError('马'.repeat(2500), HAPPYHORSE_PROMPT_LENGTH_POLICY), null)
assert.equal(getPromptLengthError('a'.repeat(5000), HAPPYHORSE_PROMPT_LENGTH_POLICY), null)
assert.match(
  getPromptLengthError('马'.repeat(2501), HAPPYHORSE_PROMPT_LENGTH_POLICY) || '',
  /2500 个中文字符或 5000 个非中文字符/,
)
assert.match(
  getPromptLengthError('a'.repeat(5001), HAPPYHORSE_PROMPT_LENGTH_POLICY) || '',
  /2500 个中文字符或 5000 个非中文字符/,
)
assert.match(
  getPromptLengthError('马'.repeat(2499) + 'abc', HAPPYHORSE_PROMPT_LENGTH_POLICY) || '',
  /2500 个中文字符或 5000 个非中文字符/,
)
