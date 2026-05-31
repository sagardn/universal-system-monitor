import { useChannel } from '../hooks/useChannel'
import { CardSkeleton } from '../components/Skeleton'

function fmtNs(ns) {
  const s = ns / 1e9
  if (s > 3600) return `${(s/3600).toFixed(1)}h`
  if (s > 60) return `${(s/60).toFixed(1)}m`
  return `${s.toFixed(1)}s`
}

export default function Scheduler() {
  const { data, loading } = useChannel('scheduler')

  if (loading) return <div className="grid grid-cols-1 md:grid-cols-3 gap-4">{[...Array(3)].map((_,i) => <CardSkeleton key={i} />)}</div>

  const scheduler = data?.scheduler || 'unknown'
  const cpus = data?.per_cpu || []
  const features = data?.features || []
  const schedExt = data?.sched_ext || {}

  return (
    <div>
      {/* Active Scheduler */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="glass p-5">
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">Active Scheduler</div>
          <div className="text-xl font-bold mt-2 text-primary">{scheduler}</div>
        </div>
        <div className="glass p-5">
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">Kernel</div>
          <div className="text-xl font-bold mt-2">{data?.kernel || '—'}</div>
          <div className="text-xs text-txt-muted mt-1">{data?.variant || ''}</div>
        </div>
        <div className="glass p-5">
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">sched-ext</div>
          <div className={`text-xl font-bold mt-2 ${schedExt.available ? 'text-success' : 'text-txt-muted'}`}>
            {schedExt.available ? '✓ Available' : 'Not available'}
          </div>
          {schedExt.active && <div className="text-xs text-primary mt-1">{schedExt.active}</div>}
        </div>
        <div className="glass p-5">
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">Total CPUs</div>
          <div className="text-xl font-bold mt-2">{cpus.length || '—'}</div>
        </div>
      </div>

      {/* Features */}
      {features.length > 0 && (
        <div className="flex gap-2 mb-6 flex-wrap">
          {features.map((f, i) => (
            <span key={i} className="inline-flex items-center px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-primary-muted text-primary">
              {f}
            </span>
          ))}
        </div>
      )}

      {/* Per CPU */}
      {cpus.length > 0 && (
        <div className="glass p-0 overflow-hidden">
          <div className="text-xs font-semibold text-txt-muted uppercase tracking-wider py-2 px-4 bg-bg-surface">
            Per-CPU Scheduler Stats
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border">
            {cpus.map((cpu, i) => (
              <div key={i} className="bg-bg-base p-3 text-xs">
                <div className="font-semibold text-primary mb-1">CPU {cpu.cpu ?? i}</div>
                <div className="flex justify-between text-txt-muted">
                  <span>Run time</span>
                  <span className="tabular-nums">{fmtNs(cpu.running_ns || 0)}</span>
                </div>
                <div className="flex justify-between text-txt-muted">
                  <span>Wait time</span>
                  <span className="tabular-nums">{fmtNs(cpu.waiting_ns || 0)}</span>
                </div>
                <div className="flex justify-between text-txt-muted">
                  <span>Slices</span>
                  <span className="tabular-nums">{(cpu.timeslices || 0).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
