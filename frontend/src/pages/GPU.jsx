import { useCallback } from 'react'
import { useChannel, useHistory } from '../hooks/useChannel'
import Gauge from '../components/Gauge'
import Sparkline from '../components/Sparkline'
import { GaugeSkeleton, CardSkeleton } from '../components/Skeleton'
import { fmtBytes, fmtTemp, fmtWatts, fmtMhz } from '../utils/format'

export default function GPU() {
  const { data, loading } = useChannel('gpu')
  const gpuSel = useCallback(d => d?.utilization?.gpu, [])
  const tmpSel = useCallback(d => d?.temperature?.current, [])
  const gpuHist = useHistory('gpu', gpuSel)
  const tmpHist = useHistory('gpu', tmpSel)

  if (loading) return (
    <div className="grid grid-cols-4 gap-4">
      {[...Array(4)].map((_,i) => <div key={i} className="glass p-5"><GaugeSkeleton /></div>)}
    </div>
  )
  if (!data?.type || data?.type === 'none' || data?.error) return (
    <div className="glass p-10 text-center">
      <p className="text-txt-muted text-lg mb-2">No GPU detected</p>
      <p className="text-txt-muted text-sm">NVIDIA (nvidia-smi) or AMD (/sys/class/drm) required</p>
      {data?.error && <p className="text-danger text-xs mt-2">{data.error}</p>}
    </div>
  )

  const util = data?.utilization || {}
  const temp = data?.temperature || {}
  const vram = data?.memory || {}
  const vramPct = vram.total > 0 ? (vram.used / vram.total) * 100 : 0
  const clocks = data?.clocks || {}
  const procs = data?.processes || []

  return (
    <div>
      <div className="text-sm text-txt-muted mb-4">{data?.name || 'GPU'} · {data?.driver_version || ''}</div>

      {/* Gauges */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="glass p-5"><Gauge percent={util.gpu || 0} label="Utilization" /></div>
        <div className="glass p-5"><Gauge percent={vramPct} label="VRAM" sub={`${fmtBytes(vram.used)} / ${fmtBytes(vram.total)}`} /></div>
        <div className="glass p-5"><Gauge percent={Math.min((temp.current || 0) / 100 * 100, 100)} label="Temp" sub={fmtTemp(temp.current)} /></div>
        <div className="glass p-5 flex flex-col items-center justify-center gap-1">
          <div className="text-2xl font-bold">{fmtWatts(data?.power?.draw)}</div>
          <div className="text-xs text-txt-muted">Power Draw</div>
          <div className="text-xs text-txt-muted">{fmtMhz(clocks.graphics)} GPU · {fmtMhz(clocks.memory)} MEM</div>
          {data?.throttle_reason && data.throttle_reason !== 'None' && (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-warning-muted text-warning mt-1">
              ⚠ {data.throttle_reason}
            </span>
          )}
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="glass p-5">
          <div className="text-sm font-semibold mb-3">GPU Utilization</div>
          <Sparkline data={gpuHist} color="#17a2b8" height={52} />
        </div>
        <div className="glass p-5">
          <div className="text-sm font-semibold mb-3">Temperature</div>
          <Sparkline data={tmpHist} color="#f59e0b" height={52} />
        </div>
      </div>

      {/* Per-process GPU Usage */}
      {procs.length > 0 && (
        <div className="glass p-0 overflow-hidden">
          <div className="text-xs font-semibold text-txt-muted uppercase tracking-wider py-2 px-4 bg-bg-surface">
            Per-Process GPU Usage ({procs.length} processes)
          </div>
          <div className="max-h-[400px] overflow-y-auto">
            <table className="dtable">
              <thead>
                <tr>
                  <th>PID</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>SM%</th>
                  <th>MEM%</th>
                  <th>VRAM</th>
                </tr>
              </thead>
              <tbody>
                {procs.map(p => (
                  <tr key={p.pid}>
                    <td className="tabular-nums">{p.pid}</td>
                    <td className="font-medium">{p.name || p.pid}</td>
                    <td>
                      <span className={`inline-flex items-center px-2 py-0.5 text-[0.6rem] font-semibold rounded-full
                        ${p.type === 'C+G' ? 'bg-accent-muted text-accent' : p.type === 'C' ? 'bg-primary-muted text-primary' : 'bg-bg-elevated text-txt-muted'}`}>
                        {p.type === 'C+G' ? 'Compute+Graphics' : p.type === 'C' ? 'Compute' : 'Graphics'}
                      </span>
                    </td>
                    <td>
                      {p.sm_percent > 0 ? (
                        <div className="flex items-center gap-2">
                          <div className="w-12 h-1 bg-bg-elevated rounded-full overflow-hidden">
                            <div className="h-full bg-primary rounded-full transition-[width] duration-500"
                              style={{ width: `${Math.min(p.sm_percent, 100)}%` }} />
                          </div>
                          <span className="tabular-nums text-xs">{p.sm_percent}%</span>
                        </div>
                      ) : <span className="text-txt-muted">—</span>}
                    </td>
                    <td>
                      {p.mem_percent > 0 ? (
                        <span className="tabular-nums text-xs">{p.mem_percent}%</span>
                      ) : <span className="text-txt-muted">—</span>}
                    </td>
                    <td className="tabular-nums font-medium">{fmtBytes(p.vram_mib * 1024 * 1024)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
