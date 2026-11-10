import { api } from './api'
import type { Capabilities, DetectionResult, VerificationResult } from '@/types/face'

function form(field: 'image' | 'file', blob: Blob, name: string) {
  const f = new FormData()
  f.append(field, blob, name)
  f.append('consent', 'true') // callers only reach here after the user has explicitly consented
  return f
}

export const getCapabilities = () => api.get<Capabilities>('/face/capabilities').then((r) => r.data)

export const detectFrame = (frame: Blob, signal?: AbortSignal) =>
  api.post<DetectionResult>('/face/detect', form('image', frame, 'frame.jpg'), { signal }).then((r) => r.data)

export const verifyFrame = (frame: Blob) =>
  api.post<VerificationResult>('/face/verify', form('image', frame, 'frame.jpg')).then((r) => r.data)

export const uploadMedia = (file: File, kind: 'image' | 'video', onProgress?: (pct: number) => void) =>
  api.post<VerificationResult>(`/uploads/${kind}`, form('file', file, file.name), {
    timeout: 180_000,
    onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
  }).then((r) => r.data)

export const getVerification = (id: string) => api.get<VerificationResult>(`/verifications/${id}`).then((r) => r.data)
