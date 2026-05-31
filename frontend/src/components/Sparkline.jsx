import { useRef, useEffect } from 'react'

export default function Sparkline({ data = [], color = '#17a2b8', height = 48 }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || data.length < 2) return
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    const w = canvas.clientWidth * dpr
    const h = canvas.clientHeight * dpr
    canvas.width = w
    canvas.height = h

    ctx.clearRect(0, 0, w, h)

    const max = Math.max(...data, 1)
    const min = Math.min(...data, 0)
    const range = max - min || 1
    const step = w / (data.length - 1)

    // Area
    ctx.beginPath()
    ctx.moveTo(0, h)
    data.forEach((v, i) => {
      const x = i * step
      const y = h - ((v - min) / range) * h * 0.88
      ctx.lineTo(x, y)
    })
    ctx.lineTo(w, h)
    ctx.closePath()
    const grad = ctx.createLinearGradient(0, 0, 0, h)
    grad.addColorStop(0, color + '30')
    grad.addColorStop(1, color + '03')
    ctx.fillStyle = grad
    ctx.fill()

    // Line
    ctx.beginPath()
    data.forEach((v, i) => {
      const x = i * step
      const y = h - ((v - min) / range) * h * 0.88
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
    })
    ctx.strokeStyle = color
    ctx.lineWidth = 1.5 * dpr
    ctx.lineJoin = 'round'
    ctx.lineCap = 'round'
    ctx.stroke()

    // Current value dot
    if (data.length > 0) {
      const lastX = (data.length - 1) * step
      const lastY = h - ((data[data.length - 1] - min) / range) * h * 0.88
      ctx.beginPath()
      ctx.arc(lastX, lastY, 3 * dpr, 0, Math.PI * 2)
      ctx.fillStyle = color
      ctx.fill()
    }
  }, [data, color])

  return <canvas ref={canvasRef} className="sparkline-canvas" style={{ height }} />
}
