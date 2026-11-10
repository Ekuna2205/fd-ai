import { getLang, locale } from '@/i18n'

const pad = (n: number) => String(n).padStart(2, '0')
// Mongolian uses numeric dates (2026.11.10). Not every browser ships Mongolian month names, so format them ourselves.
const mnDate = (d: Date, utc = false) =>
  utc ? `${d.getUTCFullYear()}.${pad(d.getUTCMonth() + 1)}.${pad(d.getUTCDate())}` : `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())}`

export const formatNumber = (n: number) => new Intl.NumberFormat(locale()).format(n)
export const formatPercent = (v: number | null | undefined) =>
  v == null ? '—' : `${(v * 100).toFixed(1)}%`
export const formatDateTime = (iso: string) => {
  const d = new Date(iso)
  if (getLang() === 'mn') return `${mnDate(d)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  return d.toLocaleString(locale(), { dateStyle: 'medium', timeStyle: 'short' })
}
/** A UTC calendar day from the API, short form for chart axes. */
export const formatDay = (iso: string) => {
  const d = new Date(iso.length === 10 ? iso + 'T00:00:00Z' : iso)
  if (getLang() === 'mn') return `${pad(d.getUTCMonth() + 1)}.${pad(d.getUTCDate())}`
  return d.toLocaleDateString(locale(), { day: '2-digit', month: 'short', timeZone: 'UTC' })
}
/** A UTC month bucket, short form for chart axes. */
export const formatMonth = (iso: string) => {
  const d = new Date(iso.length === 10 ? iso + 'T00:00:00Z' : iso)
  if (getLang() === 'mn') return `${d.getUTCFullYear()}.${pad(d.getUTCMonth() + 1)}`
  return d.toLocaleDateString(locale(), { month: 'short', year: '2-digit', timeZone: 'UTC' })
}
export const formatMs = (ms: number | null | undefined) => (ms == null ? '—' : ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`)
