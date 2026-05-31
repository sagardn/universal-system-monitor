import { useChannel } from '../hooks/useChannel'
import { CardSkeleton } from '../components/Skeleton'

export default function Thermal() {
  const { data, loading } = useChannel('thermal')

  if (loading) return <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{[...Array(4)].map((_,i) => <CardSkeleton key={i} />)}</div>

  if (!data) return <div className="glass p-10 text-center"><p className="text-txt-muted">No thermal data available</p></div>

  const cpuTemp = data.cpu_temp || 0
  const gpuTemp = data.gpu_temp || 0
  const maxTemp = data.max_temp || 0
  const sensors = Array.isArray(data.sensors) ? data.sensors : []
  const fans = Array.isArray(data.fans) ? data.fans : []
  const zones = Array.isArray(data.thermal_zones) ? data.thermal_zones : []

  const tempColor = (t) => t > 85 ? 'text-danger' : t > 65 ? 'text-warning' : 'text-success'
  const tempBarColor = (t) => t > 85 ? 'bg-danger' : t > 65 ? 'bg-warning' : 'bg-success'

  return (
    <div>
      {/* Key Temperatures */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <TempCard label="CPU" temp={cpuTemp} icon="🔥" />
        <TempCard label="GPU" temp={gpuTemp} icon="🎮" />
        <TempCard label="Hottest" temp={maxTemp} icon="🌡️" />
        <div className="glass p-5 text-center">
          <div className="text-lg mb-1">💨</div>
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">Fans</div>
          <div className="font-bold text-base mt-1">{String(fans.length)}</div>
          <div className="text-xs text-txt-muted mt-0.5">
            {fans.filter(f => f.rpm > 0).length} active
          </div>
        </div>
      </div>

      {/* Sensor Details */}
      {sensors.map(sensor => (
        <div key={sensor.name} className="glass p-5 mb-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">📟</span>
            <span className="font-semibold text-sm capitalize">{String(sensor.name)}</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {(sensor.temps || []).map((t, i) => (
              <div key={i} className="bg-bg-surface rounded-lg p-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs text-txt-muted">{String(t.label)}</span>
                  <span className={`text-sm font-bold tabular-nums ${tempColor(t.value)}`}>
                    {String(t.value)}°C
                  </span>
                </div>
                <div className="h-1.5 bg-bg-elevated rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${tempBarColor(t.value)}`}
                    style={{ width: `${Math.min(100, (t.value / (t.critical || t.max || 100)) * 100)}%` }}
                  />
                </div>
                {t.critical && (
                  <div className="text-[0.625rem] text-txt-muted mt-1 tabular-nums">
                    Critical: {String(t.critical)}°C
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Inline fans for this sensor */}
          {sensor.fans && sensor.fans.length > 0 && (
            <div className="mt-3 flex gap-3 flex-wrap">
              {sensor.fans.map((f, i) => (
                <div key={i} className="inline-flex items-center gap-2 bg-bg-surface rounded-lg px-3 py-2 text-xs">
                  <span>💨</span>
                  <span className="text-txt-muted">{String(f.label)}</span>
                  <span className="font-bold tabular-nums">{String(f.rpm)} RPM</span>
                  {f.percent != null && (
                    <span className="text-txt-muted">({String(f.percent)}%)</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {/* Fan Overview */}
      {fans.length > 0 && (
        <div className="glass p-5 mb-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">💨</span>
            <span className="font-semibold text-sm">Fan Speeds</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {fans.map((f, i) => (
              <div key={i} className="bg-bg-surface rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-txt-muted">{String(f.device)} — {String(f.label)}</span>
                  <span className="text-sm font-bold tabular-nums">
                    {f.rpm > 0 ? `${String(f.rpm)} RPM` : <span className="text-txt-muted">Stopped</span>}
                  </span>
                </div>
                {f.percent != null && (
                  <div className="h-1.5 bg-bg-elevated rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-info transition-all duration-500"
                      style={{ width: `${f.percent}%` }}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Thermal Zones */}
      {zones.length > 0 && (
        <div className="glass p-5">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">🗺️</span>
            <span className="font-semibold text-sm">Thermal Zones</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {zones.map((z, i) => (
              <div key={i} className="bg-bg-surface rounded-lg p-3 text-center">
                <div className="text-xs text-txt-muted mb-1">{String(z.name)}</div>
                <div className={`text-lg font-bold tabular-nums ${tempColor(z.temp)}`}>
                  {String(z.temp)}°C
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function TempCard({ label, temp, icon }) {
  const color = temp > 85 ? 'text-danger' : temp > 65 ? 'text-warning' : 'text-success'
  return (
    <div className="glass p-5 text-center">
      <div className="text-lg mb-1">{icon}</div>
      <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">{label}</div>
      <div className={`font-bold text-2xl mt-1 tabular-nums ${color}`}>
        {temp > 0 ? `${String(temp)}°` : '—'}
      </div>
      <div className="text-xs text-txt-muted mt-0.5">°C</div>
    </div>
  )
}
