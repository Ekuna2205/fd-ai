import { useEffect, useRef } from 'react'
import type { DetectionResult } from '@/types/face'

// iBUG 68-point groups: [start, end, closed]
const GROUPS: [number, number, boolean][] = [
  [0, 16, false], [17, 21, false], [22, 26, false], [27, 30, false], [31, 35, false],
  [36, 41, true], [42, 47, true], [48, 59, true], [60, 67, true],
]

/** Draws boxes and landmarks for the latest detection. Coordinates are normalised, so any display size works. */
export function FaceOverlay({ detection }: { detection: DetectionResult | null }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const dpr = window.devicePixelRatio || 1
    const cw = canvas.clientWidth, ch = canvas.clientHeight
    canvas.width = Math.round(cw * dpr); canvas.height = Math.round(ch * dpr)
    const ctx = canvas.getContext('2d')!
    ctx.scale(dpr, dpr)
    ctx.clearRect(0, 0, cw, ch)
    if (!detection) return

    const color = detection.face_count > 1 ? '#EF4444' : detection.quality?.ready ? '#10B981' : '#F59E0B'
    for (const face of detection.faces) {
      const x = face.box.x * cw, y = face.box.y * ch, w = face.box.w * cw, h = face.box.h * ch
      const len = Math.min(w, h) * 0.22
      ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.lineCap = 'round'
      ctx.beginPath()
      for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]] as const) {
        ctx.moveTo(cx + dx * len, cy); ctx.lineTo(cx, cy); ctx.lineTo(cx, cy + dy * len)
      }
      ctx.stroke()
      if (face.landmarks && face.landmarks.length === 68) {
        ctx.strokeStyle = 'rgba(34,211,238,0.55)'; ctx.lineWidth = 1.25
        for (const [a, b, closed] of GROUPS) {
          ctx.beginPath()
          for (let i = a; i <= b; i++) {
            const [px, py] = face.landmarks[i]
            i === a ? ctx.moveTo(px * cw, py * ch) : ctx.lineTo(px * cw, py * ch)
          }
          if (closed) ctx.closePath()
          ctx.stroke()
        }
      }
    }
  }, [detection])

  return <canvas ref={ref} className="pointer-events-none absolute inset-0 size-full" aria-hidden />
}
