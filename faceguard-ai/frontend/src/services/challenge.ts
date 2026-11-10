import { api } from './api'
import type { Challenge, ChallengeResult } from '@/types/challenge'

export const newChallenge = () => api.post<Challenge>('/face/challenge').then((r) => r.data)
export const submitChallenge = (token: string, video: Blob, filename: string, onProgress?: (pct: number) => void) => {
  const f = new FormData()
  f.append('token', token)
  f.append('consent', 'true')
  f.append('video', video, filename)
  return api.post<ChallengeResult>('/face/challenge/verify', f, {
    timeout: 180_000, onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
  }).then((r) => r.data)
}
