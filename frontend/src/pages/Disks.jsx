import { useChannel } from '../hooks/useChannel'
import { CardSkeleton } from '../components/Skeleton'

export default function Disks() {
  const { data, loading } = useChannel('disks')

  if (loading) return <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{[...Array(3)].map((_,i) => <CardSkeleton key={i} />)}</div>

  if (!data) return <div className="glass p-10 text-center"><p className="text-txt-muted">No disk data available</p></div>

  const disks = Array.isArray(data.disks) ? data.disks : []
  const summary = data.summary || {}

  const healthColor = (h) => h === 'PASSED' ? 'text-success' : h === 'FAILED' ? 'text-danger' : 'text-warning'
  const healthBg = (h) => h === 'PASSED' ? 'bg-success/10 border-success/20' : h === 'FAILED' ? 'bg-danger/10 border-danger/20' : 'bg-warning/10 border-warning/20'
  const healthIcon = (h) => h === 'PASSED' ? '✅' : h === 'FAILED' ? '❌' : '⚠️'

  return (
    <div>
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard icon="💽" label="Total Disks" value={String(summary.total || 0)} />
        <StatCard icon="✅" label="Healthy" value={String(summary.healthy || 0)} color="text-success" />
        <StatCard icon="⚠️" label="Warnings" value={String(summary.warnings || 0)} color="text-warning" />
        <StatCard icon="❌" label="Failed" value={String(summary.failed || 0)} color="text-danger" />
      </div>

      {!data.smartctl_available && (
        <div className="glass p-4 mb-4 border border-warning/30 bg-warning/5">
          <div className="text-sm font-semibold text-warning mb-1">⚠️ smartmontools not installed</div>
          <div className="text-xs text-txt-muted">
            Install <code className="bg-bg-surface px-1.5 py-0.5 rounded text-xs">smartmontools</code> for full disk health monitoring:&nbsp;
            <code className="bg-bg-surface px-1.5 py-0.5 rounded text-xs">sudo pacman -S smartmontools</code> or&nbsp;
            <code className="bg-bg-surface px-1.5 py-0.5 rounded text-xs">sudo apt install smartmontools</code>
          </div>
        </div>
      )}

      {/* Disk Cards */}
      {disks.map((disk, idx) => (
        <DiskCard key={idx} disk={disk} healthColor={healthColor} healthBg={healthBg} healthIcon={healthIcon} />
      ))}

      {disks.length === 0 && (
        <div className="glass p-10 text-center">
          <p className="text-txt-muted">No disks detected</p>
        </div>
      )}
    </div>
  )
}

function StatCard({ icon, label, value, color = 'text-txt' }) {
  return (
    <div className="glass p-4 text-center">
      <div className="text-lg mb-1">{icon}</div>
      <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">{label}</div>
      <div className={`font-bold text-xl mt-1 ${color}`}>{value}</div>
    </div>
  )
}

function DiskCard({ disk, healthColor, healthBg, healthIcon }) {
  const lifespan = disk.lifespan_percent
  const lifespanColor = lifespan > 80 ? 'text-success' : lifespan > 50 ? 'text-warning' : lifespan > 20 ? 'text-danger' : 'text-danger'
  const lifespanBarColor = lifespan > 80 ? 'bg-success' : lifespan > 50 ? 'bg-warning' : 'bg-danger'

  return (
    <div className={`glass p-5 mb-4 border ${healthBg(disk.health)}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{disk.type === 'NVMe' ? '⚡' : disk.is_ssd ? '💾' : '💿'}</span>
          <div>
            <div className="font-semibold text-sm">{String(disk.model || disk.name)}</div>
            <div className="text-xs text-txt-muted">
              {String(disk.device)} · {String(disk.type)} · {disk.capacity_gb ? `${String(disk.capacity_gb)} GB` : ''}
              {disk.interface ? ` · ${String(disk.interface)}` : ''}
            </div>
          </div>
        </div>
        <div className={`flex items-center gap-1.5 text-sm font-bold ${healthColor(disk.health)}`}>
          {healthIcon(disk.health)} {String(disk.health)}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {disk.temperature > 0 && (
          <div className="bg-bg-surface rounded-lg p-3 text-center">
            <div className="text-xs text-txt-muted">Temperature</div>
            <div className={`font-bold text-base tabular-nums ${disk.temperature > 55 ? 'text-danger' : disk.temperature > 40 ? 'text-warning' : 'text-success'}`}>
              {String(disk.temperature)}°C
            </div>
          </div>
        )}
        {disk.power_on_hours > 0 && (
          <div className="bg-bg-surface rounded-lg p-3 text-center">
            <div className="text-xs text-txt-muted">Power On</div>
            <div className="font-bold text-base tabular-nums text-txt">
              {disk.power_on_days > 365 ? `${String(Math.round(disk.power_on_days / 365 * 10) / 10)} yr` : `${String(Math.round(disk.power_on_days))} days`}
            </div>
          </div>
        )}
        {lifespan != null && (
          <div className="bg-bg-surface rounded-lg p-3 text-center">
            <div className="text-xs text-txt-muted">Lifespan</div>
            <div className={`font-bold text-base tabular-nums ${lifespanColor}`}>
              {String(lifespan)}%
            </div>
          </div>
        )}
        {disk.serial && (
          <div className="bg-bg-surface rounded-lg p-3 text-center">
            <div className="text-xs text-txt-muted">Serial</div>
            <div className="font-mono text-xs text-txt mt-1 truncate">{String(disk.serial)}</div>
          </div>
        )}
      </div>

      {/* Lifespan Bar */}
      {lifespan != null && (
        <div className="mb-4">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-txt-muted">Drive Lifespan Remaining</span>
            <span className={`font-bold ${lifespanColor}`}>{String(lifespan)}%</span>
          </div>
          <div className="h-2 bg-bg-elevated rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${lifespanBarColor}`}
              style={{ width: `${lifespan}%` }}
            />
          </div>
        </div>
      )}

      {/* NVMe Extra */}
      {disk.nvme && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div className="bg-bg-surface rounded-lg p-2.5 text-center">
            <div className="text-[0.625rem] text-txt-muted">Written</div>
            <div className="font-bold text-xs tabular-nums">{String(disk.nvme.data_written_tb)} TB</div>
          </div>
          <div className="bg-bg-surface rounded-lg p-2.5 text-center">
            <div className="text-[0.625rem] text-txt-muted">Read</div>
            <div className="font-bold text-xs tabular-nums">{String(disk.nvme.data_read_tb)} TB</div>
          </div>
          <div className="bg-bg-surface rounded-lg p-2.5 text-center">
            <div className="text-[0.625rem] text-txt-muted">Spare</div>
            <div className="font-bold text-xs tabular-nums">{String(disk.nvme.available_spare)}%</div>
          </div>
          <div className="bg-bg-surface rounded-lg p-2.5 text-center">
            <div className="text-[0.625rem] text-txt-muted">Wear</div>
            <div className="font-bold text-xs tabular-nums">{String(disk.nvme.percentage_used)}%</div>
          </div>
        </div>
      )}

      {/* SMART Attributes Table */}
      {disk.attributes && disk.attributes.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-xs text-primary font-semibold hover:text-primary/80 transition select-none">
            📋 SMART Attributes ({String(disk.attributes.length)})
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-txt-muted border-b border-border">
                  <th className="text-left py-1.5 px-2">ID</th>
                  <th className="text-left py-1.5 px-2">Attribute</th>
                  <th className="text-right py-1.5 px-2">Value</th>
                  <th className="text-right py-1.5 px-2">Worst</th>
                  <th className="text-right py-1.5 px-2">Thresh</th>
                  <th className="text-left py-1.5 px-2">Raw</th>
                </tr>
              </thead>
              <tbody>
                {disk.attributes.map((a, i) => (
                  <tr key={i} className="border-b border-border/50 hover:bg-bg-surface/50 transition">
                    <td className="py-1.5 px-2 tabular-nums text-txt-muted">{String(a.id)}</td>
                    <td className="py-1.5 px-2">{String(a.name)}</td>
                    <td className={`py-1.5 px-2 text-right font-bold tabular-nums ${a.value <= a.thresh && a.thresh > 0 ? 'text-danger' : ''}`}>
                      {String(a.value)}
                    </td>
                    <td className="py-1.5 px-2 text-right tabular-nums text-txt-muted">{String(a.worst)}</td>
                    <td className="py-1.5 px-2 text-right tabular-nums text-txt-muted">{String(a.thresh)}</td>
                    <td className="py-1.5 px-2 font-mono text-txt-muted truncate max-w-[120px]">{String(a.raw_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  )
}
