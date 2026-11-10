import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as face from '@/services/face'
import { useLiveDetection } from './useLiveDetection'

vi.mock('./useCamera', () => ({ frameToBlob: vi.fn().mockResolvedValue(new Blob(['x'])) }))
vi.mock('@/services/face', () => ({ detectFrame: vi.fn() }))

const video = { readyState: 4, videoWidth: 640, videoHeight: 480 } as HTMLVideoElement
const ref = { current: video }
const result = { face_count: 1, faces: [], guidance: ['ok'], quality: null, image: { width: 1, height: 1 }, detector: { name: 'd', landmarks: true }, processing_ms: 5 }

beforeEach(() => vi.useFakeTimers())
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks() })

describe('useLiveDetection', () => {
  it('never has more than one request in flight and throttles the rate', async () => {
    let inFlight = 0, maxInFlight = 0
    vi.mocked(face.detectFrame).mockImplementation(async () => {
      maxInFlight = Math.max(maxInFlight, ++inFlight)
      await new Promise((r) => setTimeout(r, 400)) // slower than the 250 ms interval
      inFlight--
      return result as never
    })
    const { result: hook } = renderHook(() => useLiveDetection(ref, true))
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(maxInFlight).toBe(1)
    expect(vi.mocked(face.detectFrame).mock.calls.length).toBeLessThanOrEqual(8) // ~3000/400, not 3000/250
    expect(hook.current.detection?.face_count).toBe(1)
  })

  it('stops requesting when deactivated or unmounted', async () => {
    vi.mocked(face.detectFrame).mockResolvedValue(result as never)
    const { unmount } = renderHook(() => useLiveDetection(ref, true))
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    unmount()
    const calls = vi.mocked(face.detectFrame).mock.calls.length
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(vi.mocked(face.detectFrame).mock.calls.length).toBe(calls)
  })

  it('halts after repeated failures instead of hammering the server', async () => {
    vi.mocked(face.detectFrame).mockRejectedValue(new Error('boom'))
    const { result: hook } = renderHook(() => useLiveDetection(ref, true))
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000) })
    expect(hook.current.halted).toBe(true)
    expect(vi.mocked(face.detectFrame)).toHaveBeenCalledTimes(5)
  })

  it('skips frames while the tab is hidden', async () => {
    vi.mocked(face.detectFrame).mockResolvedValue(result as never)
    Object.defineProperty(document, 'hidden', { value: true, configurable: true })
    renderHook(() => useLiveDetection(ref, true))
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(face.detectFrame).not.toHaveBeenCalled()
    Object.defineProperty(document, 'hidden', { value: false, configurable: true })
  })
})
