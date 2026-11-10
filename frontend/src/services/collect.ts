import { api } from '@/services/api'
import type { CollectFrame, CollectInfo, CollectLabel, CollectResult } from '@/types/collect'

/** Public collection-link API: no account needed; the link token is the only credential. */
export const getCollectInfo = (token: string) => api.get<CollectInfo>(`/collect/${token}`).then((r) => r.data)

export const sendCollectFrame = (token: string, jpeg: Blob) => {
  const form = new FormData()
  form.append('image', jpeg, 'frame.jpg')
  return api.post<CollectFrame>(`/collect/${token}/frame`, form, { timeout: 8000 }).then((r) => r.data)
}

export function submitCollect(token: string, video: Blob, label: CollectLabel, participant: string, attackType: string | null,
  onProgress?: (pct: number) => void) {
  const form = new FormData()
  form.append('video', video, video.type.includes('mp4') ? 'recording.mp4' : 'recording.webm')
  form.append('label', label)
  form.append('consent', 'true')
  form.append('participant', participant)
  if (attackType) form.append('attack_type', attackType)
  return api.post<CollectResult>(`/collect/${token}`, form, {
    timeout: 120_000,
    onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
  }).then((r) => r.data)
}

export const setCollection = (datasetId: string, enabled: boolean, rotate = false) =>
  api.put(`/datasets/${datasetId}/collect`, { enabled, rotate }).then((r) => r.data)
