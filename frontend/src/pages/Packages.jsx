import { useChannel } from '../hooks/useChannel'
import { useWs } from '../hooks/useWebSocket'
import { useToast } from '../components/Toast'
import { CardSkeleton } from '../components/Skeleton'

export default function Packages() {
  const { data, loading } = useChannel('packages')
  const ws = useWs()
  const toast = useToast()

  if (loading) return <div className="grid grid-cols-1 md:grid-cols-3 gap-4">{[...Array(3)].map((_,i) => <CardSkeleton key={i} />)}</div>

  const total = data?.installed_count || 0
  const official = data?.official_updates || []
  const aur = data?.aur_updates || []
  const totalUpdates = official.length + aur.length

  const doUpdate = async () => {
    toast('Starting system update…', 'info', 10000)
    const r = await ws.action('package', 'update_system', {})
    toast(r.message || r.data?.message || 'Done', r.success || r.data?.success ? 'success' : 'error')
  }

  return (
    <div>
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="glass p-5">
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">Installed</div>
          <div className="text-2xl font-bold mt-2">{total}</div>
        </div>
        <div className="glass p-5">
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">Official Updates</div>
          <div className={`text-2xl font-bold mt-2 ${official.length > 0 ? 'text-warning' : 'text-success'}`}>{official.length}</div>
        </div>
        <div className="glass p-5">
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">AUR Updates</div>
          <div className={`text-2xl font-bold mt-2 ${aur.length > 0 ? 'text-warning' : 'text-success'}`}>{aur.length}</div>
        </div>
        <div className="glass p-5 flex items-center justify-center">
          <button onClick={doUpdate} disabled={totalUpdates === 0}
            className={`inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-sm border-none cursor-pointer transition-all active:scale-95
              ${totalUpdates > 0 ? 'bg-gradient-to-r from-primary to-accent text-white shadow-[0_0_24px_var(--color-primary-glow)] hover:brightness-110' : 'bg-bg-elevated text-txt-muted cursor-not-allowed'}`}>
            📦 Update System ({totalUpdates})
          </button>
        </div>
      </div>

      {/* Update list */}
      {official.length > 0 && (
        <div className="glass p-0 overflow-hidden mb-4">
          <div className="text-xs font-semibold text-txt-muted uppercase tracking-wider py-2 px-4 bg-bg-surface">
            Official Updates ({official.length})
          </div>
          <div className="max-h-[300px] overflow-y-auto">
            {official.map(u => (
              <div key={u.name} className="flex items-center justify-between py-2 px-4 border-b border-border last:border-0 text-xs">
                <span className="font-semibold">{u.name}</span>
                <span className="text-txt-muted">{u.old_version} → <span className="text-primary">{u.new_version}</span></span>
              </div>
            ))}
          </div>
        </div>
      )}

      {aur.length > 0 && (
        <div className="glass p-0 overflow-hidden">
          <div className="text-xs font-semibold text-txt-muted uppercase tracking-wider py-2 px-4 bg-bg-surface">
            AUR Updates ({aur.length})
          </div>
          <div className="max-h-[300px] overflow-y-auto">
            {aur.map(u => (
              <div key={u.name} className="flex items-center justify-between py-2 px-4 border-b border-border last:border-0 text-xs">
                <span className="font-semibold">{u.name}</span>
                <span className="text-txt-muted">{u.old_version} → <span className="text-accent">{u.new_version}</span></span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
