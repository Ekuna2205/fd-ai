/**
 * Minimal i18n: the English text IS the key. `t('Sign in')` returns the Mongolian translation when the language is
 * Mongolian and a translation exists, else the English text. Placeholders: t('Hello {name}', { name }).
 * A test (i18n/coverage.test.ts) fails when a t('...') literal in the source has no Mongolian entry.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { mn } from './mn'

export type Lang = 'en' | 'mn'
export const LANGS: { code: Lang; label: string; short: string }[] = [
  { code: 'mn', label: 'Монгол', short: 'МН' },
  { code: 'en', label: 'English', short: 'EN' },
]
const KEY = 'faceguard.lang'
type Vars = Record<string, string | number | null | undefined>

function initial(): Lang {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'en' || saved === 'mn') return saved
  } catch { /* storage unavailable */ }
  return typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('mn') ? 'mn' : 'en'
}

let current: Lang = initial()
/** True when the person chose a language before (the choice wins over page defaults). */
export function hasSavedLang(): boolean {
  try { return localStorage.getItem(KEY) != null } catch { return false }
}
/** For code outside React (API client, formatters). Components should use useT() so they re-render on change. */
export const getLang = () => current
export const locale = (lang: Lang = current) => (lang === 'mn' ? 'mn-MN' : 'en-GB')

export function translate(text: string, vars?: Vars, lang: Lang = current): string {
  let out = lang === 'mn' ? (mn[text] ?? text) : text
  if (vars) out = out.replace(/\{(\w+)\}/g, (m: string, k: string) => (k in vars ? String(vars[k] ?? '') : m))
  return out
}

/** Translates a message produced by the API when it matches a known English sentence (exact, or a known pattern). */
export function translateServer(text: string | null | undefined, lang: Lang = current): string {
  if (!text) return text ?? ''
  if (lang !== 'mn') return text
  if (mn[text]) return mn[text]
  for (const [re, tpl] of SERVER_PATTERNS) {
    const m = text.match(re)
    if (m) return tpl.replace(/\$(\d)/g, (_, i: string) => m[Number(i)] ?? '')
  }
  return text
}
// API sentences that carry numbers. Most API text is translated on the server (Accept-Language); these are fallbacks.
const SERVER_PATTERNS: [RegExp, string][] = [
  [/^Request failed \((\d+)\)\.$/, 'Хүсэлт амжилтгүй боллоо ($1).'],
  [/^Too many requests\. Try again in (\d+) seconds?\.$/, 'Хэт олон хүсэлт илгээлээ. $1 секундын дараа дахин оролдоно уу.'],
]

type Ctx = { lang: Lang; setLang: (l: Lang, remember?: boolean) => void; t: (text: string, vars?: Vars) => string }
const LangContext = createContext<Ctx | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(current)
  // Only an explicit choice is remembered, so pages can still pick a default (hasSavedLang) for first-time visitors.
  const setLang = useCallback((l: Lang, remember = true) => {
    current = l
    setLangState(l)
    if (remember) try { localStorage.setItem(KEY, l) } catch { /* ignore */ }
  }, [])
  useEffect(() => {
    current = lang
    document.documentElement.lang = lang
  }, [lang])
  const t = useCallback((text: string, vars?: Vars) => translate(text, vars, lang), [lang])
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t])
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>
}

/** Works without a provider (unit tests render components bare): falls back to English-or-current, no switching. */
export function useT(): Ctx {
  const ctx = useContext(LangContext)
  return ctx ?? { lang: current, setLang: (l) => { current = l }, t: (text, vars) => translate(text, vars) }
}
