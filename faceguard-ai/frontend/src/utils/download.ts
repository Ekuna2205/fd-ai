import { api } from '@/services/api'

/** Fetches an authenticated file and hands it to the browser as a download (a plain link would not carry the token). */
export async function downloadFile(path: string, params: Record<string, unknown>, fallbackName: string) {
  const res = await api.get<Blob>(path, { params, responseType: 'blob', timeout: 120_000 })
  const cd = String(res.headers['content-disposition'] ?? '')
  const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? fallbackName
  const url = URL.createObjectURL(res.data)
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
