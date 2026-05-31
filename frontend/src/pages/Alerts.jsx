import { useState, useEffect } from 'react'
import { useWs } from '../hooks/useWebSocket'
import { CardSkeleton } from '../components/Skeleton'

function fmtTimeAgo(ts) {
  if (!ts) return '—'
  const secs = Math.floor(Date.now() / 1000 - ts)
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`
  return `${Math.floor(secs / 86400)}d ago`
}

export default function Alerts() {
  const ws = useWs()
  const [history, setHistory] = useState(null)
  const [liveAlerts, setLiveAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  // Fetch alert history on mount
  useEffect(() => {
    if (!ws) return
    ws.action('alert', 'get_history', {}).then(r => {
      if (r?.data) setHistory(r.data)
      setLoading(false)
    }).catch(() => setLoading(false))

    // Listen for live alerts
    const off = ws.on('alert', (alertData) => {
      setLiveAlerts(prev => [alertData, ...prev].slice(0, 50))
    })
    return off
  }, [ws])

  if (loading) return <div className="grid grid-cols-1 gap-4">{[...Array(3)].map((_,i) => <CardSkeleton key={i} />)}</div>

  const all = [...liveAlerts, ...(history || [])]
  // Deduplicate by rule+timestamp
  const seen = new Set()
  const deduped = all.filter(a => {
    const key = `${a.rule}:${a.timestamp}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })

  // Split into active (last 5 minutes) and history
  const now = Date.now() / 1000
  const active = deduped.filter(a => now - a.timestamp < 300)
  const past = deduped.filter(a => now - a.timestamp >= 300)

  return (
    <div>
      {/* Active */}
      {active.length > 0 ? (
        <div className="mb-6">
          <div className="text-sm font-semibold mb-3">🔴 Active Alerts ({active.length})</div>
          <div className="grid grid-cols-1 gap-3">
            {active.map((a, i) => (
              <div key={i} className={`glass p-4 border-l-[3px] ${a.severity === 'critical' ? 'border-l-danger' : a.severity === 'warning' ? 'border-l-warning' : 'border-l-info'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`inline-flex items-center px-2 py-0.5 text-[0.6875rem] font-semibold rounded-full
                      ${a.severity === 'critical' ? 'bg-danger-muted text-danger' : a.severity === 'warning' ? 'bg-warning-muted text-warning' : 'bg-info-muted text-info'}`}>
                      {a.severity}
                    </span>
                    <span className="font-semibold text-sm">{a.rule}</span>
                  </div>
                  <span className="text-xs text-txt-muted">{fmtTimeAgo(a.timestamp)}</span>
                </div>
                <p className="text-txt-secondary text-sm mt-2">{a.message}</p>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="glass p-8 text-center mb-6">
          <div className="text-4xl mb-3">✅</div>
          <div className="text-txt-secondary text-sm">No active alerts — system is healthy</div>
        </div>
      )}

      {/* History */}
      {past.length > 0 && (
        <div>
          <div className="text-sm font-semibold mb-3">📋 Alert History ({past.length})</div>
          <div className="glass p-0 overflow-hidden">
            <div className="max-h-[400px] overflow-y-auto">
              {past.map((a, i) => (
                <div key={i} className="flex items-center gap-3 py-2 px-4 border-b border-border last:border-0 text-xs">
                  <span className={`inline-flex items-center px-2 py-0.5 text-[0.6875rem] font-semibold rounded-full shrink-0
                    ${a.severity === 'critical' ? 'bg-danger-muted text-danger' : a.severity === 'warning' ? 'bg-warning-muted text-warning' : 'bg-info-muted text-info'}`}>
                    {a.severity}
                  </span>
                  <span className="font-semibold shrink-0">{a.rule}</span>
                  <span className="text-txt-muted flex-1 truncate">{a.message}</span>
                  <span className="text-txt-muted shrink-0">{fmtTimeAgo(a.timestamp)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {deduped.length === 0 && (
        <div className="glass p-8 text-center">
          <div className="text-4xl mb-3">📭</div>
          <div className="text-txt-secondary text-sm">No alert history yet</div>
        </div>
      )}
    </div>
  )
}
