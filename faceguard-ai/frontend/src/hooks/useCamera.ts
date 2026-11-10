import { useCallback, useEffect, useRef, useState } from 'react'
import { translate } from '@/i18n'

export type CameraStatus = 'idle' | 'starting' | 'active' | 'error'

function describe(err: unknown): string {
  const name = err instanceof DOMException ? err.name : ''
  switch (name) {
    case 'NotAllowedError': return translate('Camera permission was denied. Allow camera access in your browser settings, then try again.')
    case 'NotFoundError': return translate('No camera was found on this device.')
    case 'NotReadableError': return translate('The camera is in use by another application. Close it and try again.')
    case 'OverconstrainedError': return translate('The selected camera is not available. Try another one.')
    default: return translate('The camera could not be started.')
  }
}

/** `size`: preferred capture size. Smaller video means faster, lighter processing on small servers. */
export function useCamera(size: { width: number; height: number } = { width: 1280, height: 720 }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [status, setStatus] = useState<CameraStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([])
  const [deviceId, setDeviceId] = useState<string | undefined>()
  const [aspect, setAspect] = useState(4 / 3)

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setStatus('idle')
  }, [])

  const start = useCallback(async (wanted?: string) => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus('error'); setError('Camera access needs a secure connection (HTTPS or localhost).'); return
    }
    streamRef.current?.getTracks().forEach((t) => t.stop())
    setStatus('starting'); setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: wanted ? { deviceId: { exact: wanted }, width: { ideal: size.width }, height: { ideal: size.height } }
          : { facingMode: 'user', width: { ideal: size.width }, height: { ideal: size.height } },
      })
      streamRef.current = stream
      const settings = stream.getVideoTracks()[0]?.getSettings()
      setDeviceId(settings?.deviceId ?? wanted)
      if (settings?.width && settings?.height) setAspect(settings.width / settings.height)
      const video = videoRef.current
      if (video) { video.srcObject = stream; await video.play().catch(() => undefined) }
      // Device labels are only available after permission has been granted.
      setDevices((await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput'))
      setStatus('active')
    } catch (e) {
      setStatus('error'); setError(describe(e))
    }
  }, [size.width, size.height])

  const switchCamera = useCallback(() => {
    if (devices.length < 2) return
    const i = devices.findIndex((d) => d.deviceId === deviceId)
    void start(devices[(i + 1) % devices.length].deviceId)
  }, [devices, deviceId, start])

  useEffect(() => () => { streamRef.current?.getTracks().forEach((t) => t.stop()) }, []) // release the camera on unmount

  return { videoRef, status, error, devices, deviceId, aspect, start, stop, switchCamera }
}

/** Downscaled JPEG of the current video frame. Smaller frames keep detection fast and bandwidth low. */
export function frameToBlob(video: HTMLVideoElement, maxWidth: number, quality: number): Promise<Blob> {
  const scale = Math.min(1, maxWidth / video.videoWidth)
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(video.videoWidth * scale)
  canvas.height = Math.round(video.videoHeight * scale)
  canvas.getContext('2d')!.drawImage(video, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Could not capture a frame.'))), 'image/jpeg', quality))
}
