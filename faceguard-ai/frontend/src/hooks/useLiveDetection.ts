import axios from 'axios'
import { useEffect, useState, type RefObject } from 'react'
import { errorMessage } from '@/services/api'
import { detectFrame } from '@/services/face'
import type { DetectionResult } from '@/types/face'
import { frameToBlob } from './useCamera'

const INTERVAL_MS = 250 // at most ~4 analysed frames per second, never more than one request in flight
const MAX_FAILURES = 5

/**
 * Efficient frame loop: sequential (a new frame is only sent after the previous answer),
 * throttled, paused while the tab is hidden, downscaled to 480 px, and aborted on stop/unmount.
 */
export function useLiveDetection(videoRef: RefObject<HTMLVideoElement | null>, active: boolean) {
  const [detection, setDetection] = useState<DetectionResult | null>(null)
  const [latencyMs, setLatencyMs] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [halted, setHalted] = useState(false)
  const [restartKey, setRestartKey] = useState(0)

  useEffect(() => {
    if (!active) { setDetection(null); setLatencyMs(null); setError(null); setHalted(false); return }
    let stopped = false
    let timer: number | undefined
    let failures = 0
    const ctrl = new AbortController()

    const tick = async () => {
      const started = performance.now()
      let delay = INTERVAL_MS
      const video = videoRef.current
      if (video && video.readyState >= 2 && video.videoWidth > 0 && !document.hidden) {
        try {
          const result = await detectFrame(await frameToBlob(video, 480, 0.7), ctrl.signal)
          if (stopped) return
          setDetection(result); setError(null); failures = 0
          setLatencyMs(Math.round(performance.now() - started))
        } catch (e) {
          if (stopped || axios.isCancel(e)) return
          failures += 1
          setError(errorMessage(e))
          delay = axios.isAxiosError(e) && e.response?.status === 429 ? 2000 : 1000
          if (failures >= MAX_FAILURES) { setHalted(true); return }
        }
      }
      if (!stopped) timer = window.setTimeout(tick, Math.max(0, delay - (performance.now() - started)))
    }
    void tick()
    return () => { stopped = true; ctrl.abort(); window.clearTimeout(timer) }
  }, [active, videoRef, restartKey])

  return { detection, latencyMs, error, halted, restart: () => { setHalted(false); setError(null); setRestartKey((k) => k + 1) } }
}
