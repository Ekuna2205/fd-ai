import { api } from './api'
import type { ModelDetail, ModelInfo } from '@/types/models'

export const listModels = () => api.get<ModelInfo[]>('/models').then((r) => r.data)
export const getModel = (id: string) => api.get<ModelDetail>(`/models/${id}`).then((r) => r.data)
export const activateModel = (id: string) => api.post<ModelInfo>(`/models/${id}/activate`).then((r) => r.data)
export const deactivateModel = (id: string) => api.post<ModelInfo>(`/models/${id}/deactivate`).then((r) => r.data)

export interface RegisterModelInput {
  name: string; version: string; architecture: string; description: string; input_crop: 'full' | 'face'
  onnx: File; test_metrics: File; split_report: File
}

/** Uploads the three files a training run produces. The server validates them with ONNX Runtime; never activates. */
export const registerModel = (m: RegisterModelInput, onProgress?: (pct: number) => void) => {
  const form = new FormData()
  for (const k of ['name', 'version', 'architecture', 'description', 'input_crop'] as const) form.append(k, m[k])
  form.append('onnx', m.onnx)
  form.append('test_metrics', m.test_metrics)
  form.append('split_report', m.split_report)
  return api.post<ModelInfo>('/models', form, {
    timeout: 300_000,
    onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
  }).then((r) => r.data)
}
export const deleteModel = (id: string) => api.delete(`/models/${id}`).then(() => undefined)
