/// <reference types="node" />
/** Every t('...') / translate('...') literal in the source must have a Mongolian entry, and placeholders must match. */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { mn } from './mn'

const SRC = join(__dirname, '..')
function files(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f)
    if (statSync(p).isDirectory()) return f === 'i18n' ? [] : files(p)
    return /\.(ts|tsx)$/.test(f) && !/\.test\.tsx?$/.test(f) ? [p] : []
  })
}
const CALL = /\b(?:t|translate)\(\s*(['"])((?:\\.|(?!\1).)*)\1/g

function keys(): Map<string, string> {
  const out = new Map<string, string>()
  for (const f of files(SRC)) {
    for (const m of readFileSync(f, 'utf8').matchAll(CALL)) out.set(m[2].replace(/\\(['"\\])/g, '$1'), f.replace(SRC, ''))
  }
  return out
}
const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()

describe('Mongolian translations', () => {
  it('cover every translated literal', () => {
    const missing = [...keys()].filter(([k]) => !(k in mn)).map(([k, f]) => `${f}: ${k}`)
    expect(missing).toEqual([])
  })
  it('keep the same placeholders', () => {
    const bad = Object.entries(mn).filter(([en, tr]) => placeholders(en).join() !== placeholders(tr).join()).map(([en]) => en)
    expect(bad).toEqual([])
  })
})
