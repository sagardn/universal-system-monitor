import { useCallback } from 'react'
import { useChannel, useHistory } from '../hooks/useChannel'
import Gauge from '../components/Gauge'
import Sparkline from '../components/Sparkline'
import { GaugeSkeleton, CardSkeleton } from '../components/Skeleton'
import { fmtBytes, fmtUptime, fmtTemp, fmtMhz } from '../utils/format'

export default function Overview() {
  const { data: sys, loading } = useChannel('system')
  const { data: gpu } = useChannel('gpu')
  const cpuSel = useCallback(d => d?.cpu?.percent, [])
  const ramSel = useCallback(d => d?.memory?.percent, [])
  const gpuSel = useCallback(d => d?.utilization?.gpu, [])
  const cpuHistory = useHistory('system', cpuSel)
  const ramHistory = useHistory('system', ramSel)
  const gpuHistory = useHistory('gpu', gpuSel)

  if (loading) return (
    <div>
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[...Array(4)].map((_,i) => <div key={i} className="glass p-5"><GaugeSkeleton /></div>)}
      </div>
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[...Array(4)].map((_,i) => <CardSkeleton key={i} />)}
      </div>
    </div>
  )

  const cpu = sys?.cpu?.percent || 0
  const ram = sys?.memory?.percent || 0
  const swap = sys?.swap?.percent || 0
  const gpuPct = gpu?.utilization?.gpu || 0

  const temps = sys?.temperatures || {}
  let cpuTemp = null
  for (const sensors of Object.values(temps)) {
    if (sensors?.[0]) { cpuTemp = sensors[0].current; break }
  }

  return (
    <div>
      {/* Gauges */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="glass p-5">
          <Gauge percent={cpu} label="CPU" sub={fmtMhz(sys?.cpu?.freq_current)} />
        </div>
        <div className="glass p-5">
          <Gauge percent={ram} label="RAM" sub={`${fmtBytes(sys?.memory?.used)} / ${fmtBytes(sys?.memory?.total)}`} />
        </div>
        <div className="glass p-5">
          <Gauge percent={swap} label="Swap" sub={fmtBytes(sys?.swap?.used)} />
        </div>
        <div className="glass p-5">
          <Gauge percent={gpuPct} label="GPU" sub={gpu?.name?.replace('NVIDIA ', '').replace('GeForce ', '') || 'N/A'} />
        </div>
      </div>

      {/* System Info + Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard icon="⏱" iconBg="bg-primary-muted" iconColor="text-primary" label="Uptime" value={fmtUptime(sys?.uptime)} />
        <StatCard icon="🖥" iconBg="bg-info-muted" iconColor="text-info" label="Host" value={sys?.hostname || '—'} small />
        <StatCard icon="🐧" iconBg="bg-success-muted" iconColor="text-success" label="Distro" value={sys?.distro || sys?.os_name || '—'} small />
        <StatCard icon="📊" iconBg="bg-warning-muted" iconColor="text-warning" label="Load Avg"
          value={(sys?.cpu?.load_avg || []).map(v => v.toFixed(2)).join('  ')} small />
      </div>

      {/* System Details Banner */}
      <div className="glass p-4 mb-6 flex items-center gap-6 flex-wrap text-xs">
        <div className="flex items-center gap-1.5">
          <span className="text-txt-muted">CPU:</span>
          <span className="font-semibold">{sys?.cpu_model || '—'}</span>
          <span className="text-txt-muted">({sys?.cpu?.count_physical || 0}C/{sys?.cpu?.count_logical || 0}T)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-txt-muted">RAM:</span>
          <span className="font-semibold">{fmtBytes(sys?.memory?.total)}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-txt-muted">Kernel:</span>
          <span className="font-semibold">{sys?.kernel || '—'}</span>
        </div>
        {sys?.desktop && (
          <div className="flex items-center gap-1.5">
            <span className="text-txt-muted">DE:</span>
            <span className="font-semibold">{sys?.desktop}</span>
          </div>
        )}
        {cpuTemp > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-txt-muted">CPU Temp:</span>
            <span className={`font-semibold ${cpuTemp > 85 ? 'text-danger' : cpuTemp > 65 ? 'text-warning' : 'text-success'}`}>
              {fmtTemp(cpuTemp)}
            </span>
          </div>
        )}
      </div>

      {/* Disk Usage */}
      {sys?.disk?.partitions?.length > 0 && (
        <div className="glass p-5 mb-6">
          <div className="text-sm font-semibold mb-3">💾 Disk Usage</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {sys.disk.partitions.filter(d => !d.mountpoint.startsWith('/boot')).slice(0, 6).map(d => (
              <div key={d.mountpoint} className="bg-bg-surface rounded-lg p-3">
                <div className="flex items-center justify-between mb-1.5 text-xs">
                  <span className="font-medium truncate max-w-[180px]">{d.mountpoint}</span>
                  <span className="text-txt-muted tabular-nums">{fmtBytes(d.used)} / {fmtBytes(d.total)}</span>
                </div>
                <div className="h-1.5 bg-bg-elevated rounded-full overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-500 ${d.percent > 90 ? 'bg-danger' : d.percent > 75 ? 'bg-warning' : 'bg-primary'}`}
                    style={{ width: `${d.percent}%` }} />
                </div>
                <div className="text-[0.625rem] text-txt-muted mt-1 tabular-nums">{d.percent}% · {d.fstype}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sparklines */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SparkCard title="CPU History" data={cpuHistory} color="#17a2b8" />
        <SparkCard title="RAM History" data={ramHistory} color="#22c55e" />
        <SparkCard title="GPU History" data={gpuHistory} color="#f59e0b" />
      </div>
    </div>
  )
}

function StatCard({ icon, iconBg, iconColor, label, value, small }) {
  return (
    <div className="glass flex items-center gap-3.5 p-4">
      <div className={`w-[42px] h-[42px] flex items-center justify-center rounded-sm text-xl shrink-0 ${iconBg} ${iconColor}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">{label}</div>
        <div className={`font-bold tabular-nums ${small ? 'text-xs' : 'text-base'}`}>{value}</div>
      </div>
    </div>
  )
}

function SparkCard({ title, data, color }) {
  return (
    <div className="glass p-5">
      <div className="text-sm font-semibold mb-3">{title}</div>
      <Sparkline data={data} color={color} height={52} />
    </div>
  )
}
