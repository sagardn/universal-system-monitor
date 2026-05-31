import { useChannel } from '../hooks/useChannel'
import { useWs } from '../hooks/useWebSocket'
import { useToast } from '../components/Toast'
import Gauge from '../components/Gauge'
import { GaugeSkeleton, CardSkeleton } from '../components/Skeleton'
import { fmtWatts } from '../utils/format'

function fmtMins(m) {
  if (!m || m <= 0) return '—'
  const h = Math.floor(m / 60)
  return h > 0 ? `${h}h ${m % 60}m` : `${m}m`
}

export default function Battery() {
  const { data, loading } = useChannel('battery')
  const ws = useWs()
  const toast = useToast()

  if (loading) return (
    <div className="grid grid-cols-4 gap-4">
      {[...Array(4)].map((_,i) => <div key={i} className="glass p-5"><GaugeSkeleton /></div>)}
    </div>
  )

  if (!data?.has_battery) return (
    <div className="glass p-10 text-center">
      <p className="text-4xl mb-3">🔌</p>
      <p className="text-txt-muted text-lg">No battery detected</p>
      <p className="text-txt-muted text-sm mt-2">Desktop system — showing power profile only</p>
      {data?.power_profile && (
        <div className="mt-4 inline-flex items-center px-3 py-1.5 text-sm font-semibold rounded-full bg-primary-muted text-primary">
          Profile: {data.power_profile.current}
        </div>
      )}
    </div>
  )

  const isCharging = data.status === 'Charging'
  const isFull = data.status === 'Full'
  const profile = data.power_profile || {}
  const profiles = profile.available || []

  const switchProfile = async (p) => {
    toast(`Switching to ${p}…`, 'info')
    const r = await ws.action('power_profile', 'set', { profile: p })
    toast(r?.message || r?.data?.message || 'Done', r?.success || r?.data?.success ? 'success' : 'error')
  }

  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="glass p-5">
          <Gauge
            percent={data.capacity || 0}
            label="Battery"
            sub={isFull ? '✅ Full' : isCharging ? '⚡ Charging' : '🔋 On Battery'}
          />
        </div>
        <div className="glass p-5">
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">Time Remaining</div>
          <div className="text-2xl font-bold mt-2">{fmtMins(data.time_remaining_mins)}</div>
          <div className="text-xs text-txt-muted mt-1">{isCharging ? 'Until full' : 'Until empty'}</div>
        </div>
        <div className="glass p-5">
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">Health</div>
          <div className={`text-2xl font-bold mt-2 ${data.health_percent >= 80 ? 'text-success' : data.health_percent >= 50 ? 'text-warning' : 'text-danger'}`}>
            {data.health_percent ? `${data.health_percent}%` : '—'}
          </div>
          <div className="text-xs text-txt-muted mt-1">{data.cycle_count ? `${data.cycle_count} cycles` : ''}</div>
        </div>
        <div className="glass p-5">
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">Power Draw</div>
          <div className="text-2xl font-bold mt-2">{fmtWatts(data.power_watts)}</div>
          <div className="text-xs text-txt-muted mt-1">
            {data.energy_now_wh && data.energy_full_wh
              ? `${data.energy_now_wh}Wh / ${data.energy_full_wh}Wh`
              : data.ac_online ? 'AC Connected' : ''}
          </div>
        </div>
      </div>

      {/* Power Profiles */}
      {profiles.length > 0 && (
        <div className="glass p-5">
          <div className="text-sm font-semibold mb-3">Power Profile ({profile.manager || 'Unknown'})</div>
          <div className="flex gap-2 flex-wrap">
            {profiles.map(p => (
              <button key={p} onClick={() => switchProfile(p)}
                className={`px-4 py-2 text-xs font-semibold rounded-sm border transition-all cursor-pointer active:scale-95
                  ${p === profile.current
                    ? 'bg-gradient-to-r from-primary to-accent text-white border-transparent shadow-[0_0_24px_var(--color-primary-glow)]'
                    : 'border-border bg-transparent text-txt-secondary hover:border-primary hover:text-primary'}`}>
                {p === 'power-saver' ? '🔋' : p === 'performance' ? '🚀' : '⚖️'} {p}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
