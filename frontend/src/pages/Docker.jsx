import { useChannel } from '../hooks/useChannel'
import { useWs } from '../hooks/useWebSocket'
import { useToast } from '../components/Toast'
import { CardSkeleton } from '../components/Skeleton'
import { fmtBytes } from '../utils/format'

export default function Docker() {
  const { data, loading } = useChannel('docker')
  const ws = useWs()
  const toast = useToast()

  const doAction = async (id, action) => {
    toast(`${action}ing container…`, 'info')
    const r = await ws.action('docker', action, { container_id: id })
    toast(r.message || r.data?.message || 'Done', r.success || r.data?.success ? 'success' : 'error')
  }

  if (loading) return <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{[...Array(4)].map((_,i) => <CardSkeleton key={i} />)}</div>

  if (!data?.daemon_running) return (
    <div className="glass p-10 text-center">
      <p className="text-txt-muted text-lg mb-2">Docker not available</p>
      <p className="text-txt-muted text-sm">Docker daemon is not running or not installed</p>
      <button onClick={() => ws.action('docker', 'start_daemon', {})} className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-sm bg-primary text-white border-none cursor-pointer hover:brightness-110 transition-all active:scale-95">
        ▶ Start Docker
      </button>
    </div>
  )

  const containers = data?.containers || []

  return (
    <div>
      <div className="flex items-center gap-3 mb-4 text-sm">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-success-muted text-success">
          {containers.filter(c => c.state === 'running').length} Running
        </span>
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-bg-elevated text-txt-muted">
          {containers.filter(c => c.state !== 'running').length} Stopped
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {containers.map(c => {
          const running = c.state === 'running'
          const statusColor = running ? 'border-l-success' : c.state === 'exited' ? 'border-l-txt-muted' : 'border-l-danger'
          return (
            <div key={c.id} className={`glass border-l-[3px] ${statusColor}`}>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="font-semibold text-sm">{c.name}</div>
                  <div className="text-[0.6875rem] text-txt-muted">{c.image}</div>
                </div>
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full
                  ${running ? 'bg-success-muted text-success' : 'bg-bg-elevated text-txt-muted'}`}>
                  <span className={`sdot ${running ? 'bg-success sdot-pulse' : 'bg-txt-muted'}`} /> {c.state}
                </span>
              </div>

              {running && c.stats && (
                <div className="grid grid-cols-2 gap-3 mb-3 text-xs">
                  <div>
                    <div className="text-txt-muted mb-1">CPU</div>
                    <div className="w-full h-1 bg-bg-elevated rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-[width] duration-600"
                        style={{ width: `${Math.min(c.stats.cpu_percent || 0, 100)}%` }} />
                    </div>
                    <div className="tabular-nums mt-1">{(c.stats.cpu_percent || 0).toFixed(1)}%</div>
                  </div>
                  <div>
                    <div className="text-txt-muted mb-1">Memory</div>
                    <div className="w-full h-1 bg-bg-elevated rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-[width] duration-600"
                        style={{ width: `${Math.min(c.stats.memory_percent || 0, 100)}%` }} />
                    </div>
                    <div className="tabular-nums mt-1">{fmtBytes(c.stats.memory_usage)}</div>
                  </div>
                </div>
              )}

              <div className="flex gap-1.5 mt-2">
                {running ? (
                  <>
                    <button onClick={() => doAction(c.id, 'stop')} className="inline-flex items-center gap-1 px-2.5 py-1 text-[0.6875rem] font-semibold rounded-sm border border-border bg-transparent text-txt-secondary cursor-pointer hover:bg-bg-hover transition active:scale-95">⏹ Stop</button>
                    <button onClick={() => doAction(c.id, 'restart')} className="inline-flex items-center gap-1 px-2.5 py-1 text-[0.6875rem] font-semibold rounded-sm bg-primary/15 text-primary border-none cursor-pointer hover:bg-primary/25 transition active:scale-95">🔄 Restart</button>
                  </>
                ) : (
                  <>
                    <button onClick={() => doAction(c.id, 'start')} className="inline-flex items-center gap-1 px-2.5 py-1 text-[0.6875rem] font-semibold rounded-sm bg-success/15 text-success border-none cursor-pointer hover:bg-success/25 transition active:scale-95">▶ Start</button>
                    <button onClick={() => doAction(c.id, 'remove')} className="inline-flex items-center gap-1 px-2.5 py-1 text-[0.6875rem] font-semibold rounded-sm bg-danger/15 text-danger border-none cursor-pointer hover:bg-danger/25 transition active:scale-95">🗑 Remove</button>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
