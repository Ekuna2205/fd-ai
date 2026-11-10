import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useCamera } from './useCamera'

const setMedia = (value: unknown) => Object.defineProperty(navigator, 'mediaDevices', { value, configurable: true })
afterEach(() => setMedia(undefined))

describe('useCamera', () => {
  it('explains a denied permission', async () => {
    setMedia({ getUserMedia: vi.fn().mockRejectedValue(new DOMException('no', 'NotAllowedError')) })
    const { result } = renderHook(() => useCamera())
    await act(() => result.current.start())
    expect(result.current.status).toBe('error')
    expect(result.current.error).toMatch(/permission was denied/i)
  })

  it('explains a missing camera and a busy camera', async () => {
    const gum = vi.fn().mockRejectedValueOnce(new DOMException('', 'NotFoundError')).mockRejectedValueOnce(new DOMException('', 'NotReadableError'))
    setMedia({ getUserMedia: gum })
    const { result } = renderHook(() => useCamera())
    await act(() => result.current.start())
    expect(result.current.error).toMatch(/No camera was found/)
    await act(() => result.current.start())
    expect(result.current.error).toMatch(/in use by another application/)
  })

  it('requires a secure context', async () => {
    setMedia(undefined)
    const { result } = renderHook(() => useCamera())
    await act(() => result.current.start())
    expect(result.current.error).toMatch(/HTTPS or localhost/)
  })

  it('starts, lists cameras, and releases every track on stop and on unmount', async () => {
    const track = { stop: vi.fn(), getSettings: () => ({ deviceId: 'cam1', width: 1280, height: 720 }) }
    const stream = { getTracks: () => [track], getVideoTracks: () => [track] }
    setMedia({
      getUserMedia: vi.fn().mockResolvedValue(stream),
      enumerateDevices: vi.fn().mockResolvedValue([{ kind: 'videoinput', deviceId: 'cam1' }, { kind: 'audioinput', deviceId: 'mic' }]),
    })
    const { result, unmount } = renderHook(() => useCamera())
    await act(() => result.current.start())
    expect(result.current.status).toBe('active')
    expect(result.current.devices).toHaveLength(1) // audio inputs are ignored
    expect(result.current.aspect).toBeCloseTo(16 / 9)
    act(() => result.current.stop())
    expect(track.stop).toHaveBeenCalledTimes(1)
    expect(result.current.status).toBe('idle')
    await act(() => result.current.start())
    unmount()
    expect(track.stop).toHaveBeenCalledTimes(2)
  })
})
