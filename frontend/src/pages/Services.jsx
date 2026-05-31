import { useState } from 'react'
import { useChannel } from '../hooks/useChannel'
import { useWs } from '../hooks/useWebSocket'
import { useToast } from '../components/Toast'
import { TableSkeleton } from '../components/Skeleton'
import { fmtBytes } from '../utils/format'

const CAT_LABELS = {
  databases: '🗄️ Databases',
  web_servers: '🌐 Web Servers',
  docker: '🐳 Docker',
  audio: '🔊 Audio',
  network: '📡 Network',
  custom: '⚙️ Custom',
  other_active: '✅ Other Active',
  inactive: '💤 Inactive',
}

export default function Services() {
  const { data, loading } = useChannel('services')
  const ws = useWs()
  const toast = useToast()
  const [showInactive, setShowInactive] = useState(false)
  const [filter, setFilter] = useState('')

  const doAction = async (name, action) => {
    toast(`${action}ing ${name}…`, 'info')
    const r = await ws.action('service', action, { service: name })
    toast(r.message || r.data?.message || 'Done', r.success || r.data?.success ? 'success' : 'error')
  }

  if (loading) return <TableSkeleton rows={10} cols={4} />

  const cats = data?.categories || {}
  const summary = data?.summary || {}
  const q = filter.toLowerCase()

  const filterSvcs = (list) => q ? list.filter(s => s.name.toLowerCase().includes(q) || (s.description||'').toLowerCase().includes(q)) : list

  return (
    <div>
      {/* Summary */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-success-muted text-success">
          <span className="sdot bg-success sdot-pulse" /> {summary.active || 0} Active
        </span>
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-bg-elevated text-txt-muted">
          {summary.inactive || 0} Inactive
        </span>
        {summary.failed > 0 && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-danger-muted text-danger">
            <span className="sdot bg-danger sdot-pulse" /> {summary.failed} Failed
          </span>
        )}
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-info-muted text-info">
          {summary.total || 0} Total
        </span>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="flex-1 min-w-[200px] flex items-center gap-2 py-[7px] px-3.5 bg-bg-surface border border-border rounded-sm focus-within:border-primary transition-colors">
          <span className="text-txt-muted text-sm">🔍</span>
          <input className="flex-1 bg-transparent border-none text-txt text-xs outline-none placeholder:text-txt-muted font-sans"
            placeholder="Filter services…" value={filter} onChange={e => setFilter(e.target.value)} />
        </div>
        <button onClick={() => setShowInactive(!showInactive)}
          className={`inline-flex items-center gap-2 px-3 py-[7px] text-[0.6875rem] font-semibold rounded-sm border cursor-pointer transition-all active:scale-95
            ${showInactive ? 'bg-primary text-white border-primary' : 'bg-transparent text-txt-secondary border-border hover:bg-bg-hover'}`}>
          💤 Show Inactive ({(cats.inactive || []).length})
        </button>
      </div>

      {/* Categories */}
      {Object.entries(CAT_LABELS).map(([key, label]) => {
        if (key === 'inactive' && !showInactive) return null
        const svcs = filterSvcs(cats[key] || [])
        if (svcs.length === 0) return null
        return (
          <div key={key} className="glass p-0 overflow-hidden mb-4">
            <div className="text-xs font-semibold text-txt-muted uppercase tracking-wider py-2 px-4 bg-bg-surface">
              {label}
            </div>
            {svcs.map(s => (
              <ServiceRow key={s.name} s={s} onAction={doAction} />
            ))}
          </div>
        )
      })}
    </div>
  )
}

function ServiceRow({ s, onAction }) {
  const badge = s.active === 'active' ? 'bg-success-muted text-success'
    : s.active === 'failed' ? 'bg-danger-muted text-danger'
    : 'bg-bg-elevated text-txt-muted'
  const dotColor = s.active === 'active' ? 'bg-success' : s.active === 'failed' ? 'bg-danger' : 'bg-txt-muted'

  return (
    <div className={`flex items-center gap-3 py-2.5 px-4 border-b border-border last:border-b-0 transition-colors hover:bg-bg-hover ${s.active === 'failed' ? 'bg-danger-muted' : ''}`}>
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full min-w-[90px] ${badge}`}>
        <span className={`sdot ${dotColor} ${s.active !== 'inactive' ? 'sdot-pulse' : ''}`} />
        {s.active}/{s.sub}
      </span>
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-[0.8125rem]">{s.name}</div>
        <div className="text-[0.6875rem] text-txt-muted truncate">{s.description}</div>
      </div>
      {s.pid > 0 && <span className="text-[0.6875rem] text-txt-muted">PID {s.pid}</span>}
      {s.memory > 0 && <span className="text-[0.6875rem] text-txt-muted">{fmtBytes(s.memory)}</span>}
      <div className="flex gap-1.5">
        <button onClick={() => onAction(s.name, 'restart')} title="Restart"
          className="inline-flex items-center gap-1 px-2.5 py-1 text-[0.6875rem] font-semibold rounded-sm bg-primary/15 text-primary border-none cursor-pointer hover:bg-primary/25 transition-colors active:scale-95">
          🔄
        </button>
        {s.active === 'active' ? (
          <button onClick={() => onAction(s.name, 'stop')} title="Stop"
            className="inline-flex items-center justify-center w-7 h-7 rounded-sm border border-border text-txt-secondary bg-transparent text-xs cursor-pointer hover:bg-bg-hover transition-colors active:scale-90">
            ⏹
          </button>
        ) : (
          <button onClick={() => onAction(s.name, 'start')} title="Start"
            className="inline-flex items-center justify-center w-7 h-7 rounded-sm border border-border text-success bg-transparent text-xs cursor-pointer hover:bg-success-muted transition-colors active:scale-90">
            ▶
          </button>
        )}
      </div>
    </div>
  )
}
