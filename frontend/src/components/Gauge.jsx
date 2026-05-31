import { useMemo } from 'react'
import { gaugeColor } from '../utils/format'

export default function Gauge({ size = 120, percent = 0, label = '', sub = '' }) {
  const r = (size - 12) / 2
  const circumference = 2 * Math.PI * r
  const offset = circumference * (1 - Math.min(percent, 100) / 100)
  const color = gaugeColor(percent)

  return (
    <div className="flex flex-col items-center gap-2">
      <svg className="gauge-svg" width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)' }}>
        <circle className="gauge-track" cx={size/2} cy={size/2} r={r} />
        <circle className="gauge-fill" cx={size/2} cy={size/2} r={r} stroke={color}
          strokeDasharray={circumference} strokeDashoffset={offset} />
        <text className="gauge-text" x={size/2} y={size/2}
          transform={`rotate(90 ${size/2} ${size/2})`} fontSize={size * 0.22}>
          {Math.round(percent)}%
        </text>
      </svg>
      {label && <span className="text-xs font-medium text-txt-secondary">{label}</span>}
      {sub && <span className="text-[0.6875rem] text-txt-muted">{sub}</span>}
    </div>
  )
}
