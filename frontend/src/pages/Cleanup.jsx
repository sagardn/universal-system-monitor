import { useState } from 'react'
import { useChannel } from '../hooks/useChannel'
import { useWs } from '../hooks/useWebSocket'
import { useToast } from '../components/Toast'

function fmtSize(bytes) {
  if (!bytes || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

export default function Cleanup() {
  const { data } = useChannel('cleanup')
  const ws = useWs()
  const toast = useToast()
  const [busy, setBusy] = useState({})
  const [selected, setSelected] = useState(new Set())

  const categories = data?.categories || []
  const orphans = data?.orphan_packages || []

  const clean = async (action, label) => {
    setBusy(b => ({ ...b, [action]: true }))
    toast(`Cleaning ${label}…`, 'info')
    const r = await ws.action('cleanup', action, {})
    toast(r?.message || 'Done', r?.success ? 'success' : 'error')
    setBusy(b => ({ ...b, [action]: false }))
  }

  const toggleSelect = (id) => {
    setSelected(s => {
      const next = new Set(s)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const selectAll = () => {
    if (selected.size === categories.filter(c => c.safe).length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(categories.filter(c => c.safe).map(c => c.id)))
    }
  }

  const cleanSelected = async () => {
    for (const cat of categories) {
      if (selected.has(cat.id)) {
        await clean(cat.action, cat.name)
      }
    }
    setSelected(new Set())
  }

  const selectedSize = categories
    .filter(c => selected.has(c.id))
    .reduce((sum, c) => sum + c.size, 0)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-bold">🧹 System Cleanup</h2>
          <p className="text-xs text-txt-muted mt-1">
            {data ? `${fmtSize(data.total_size)} reclaimable space found` : 'Scanning...'}
          </p>
        </div>
        <div className="flex gap-2">
          {selected.size > 0 && (
            <button
              onClick={cleanSelected}
              className="px-4 py-2 rounded-lg font-semibold text-sm bg-danger text-white hover:brightness-110 transition-all flex items-center gap-2"
            >
              🗑️ Clean Selected ({fmtSize(selectedSize)})
            </button>
          )}
          <button
            onClick={selectAll}
            className="px-4 py-2 rounded-lg font-semibold text-sm bg-bg-elevated hover:bg-bg-surface transition-all"
          >
            {selected.size === categories.filter(c => c.safe).length ? 'Deselect All' : 'Select All Safe'}
          </button>
        </div>
      </div>

      {/* Size Overview */}
      {data && (
        <div className="glass p-5">
          <div className="flex items-center gap-4 mb-3">
            <span className="text-3xl font-extrabold text-warning">{fmtSize(data.total_size)}</span>
            <span className="text-sm text-txt-muted">total junk found</span>
          </div>
          <div className="flex gap-1 h-3 rounded-full overflow-hidden bg-bg-elevated">
            {categories.map(cat => (
              <div
                key={cat.id}
                className="h-full transition-all duration-500"
                style={{
                  width: `${Math.max((cat.size / (data.total_size || 1)) * 100, 2)}%`,
                  backgroundColor: cat.safe ? 'var(--success)' : 'var(--warning)',
                  opacity: selected.has(cat.id) ? 1 : 0.4,
                }}
                title={`${cat.name}: ${fmtSize(cat.size)}`}
              />
            ))}
          </div>
        </div>
      )}

      {/* Categories */}
      <div className="space-y-2">
        {categories.map(cat => (
          <div
            key={cat.id}
            className={`glass p-4 flex items-center gap-4 transition-all cursor-pointer hover:border-primary/30 ${
              selected.has(cat.id) ? 'border-primary/50 bg-primary/5' : ''
            }`}
            onClick={() => cat.safe && toggleSelect(cat.id)}
          >
            {/* Checkbox */}
            <div className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${
              selected.has(cat.id) ? 'bg-primary border-primary' : 'border-border'
            } ${!cat.safe ? 'opacity-30' : ''}`}>
              {selected.has(cat.id) && <span className="text-white text-xs">✓</span>}
            </div>

            {/* Icon */}
            <span className="text-2xl shrink-0">{cat.icon}</span>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-sm">{cat.name}</span>
                {!cat.safe && (
                  <span className="text-[0.6rem] bg-warning/20 text-warning px-1.5 py-0.5 rounded-full font-medium">
                    CAUTION
                  </span>
                )}
              </div>
              <p className="text-xs text-txt-muted font-mono truncate">{cat.path}</p>
            </div>

            {/* Size */}
            <div className="text-right shrink-0">
              <div className="font-bold text-sm tabular-nums">{fmtSize(cat.size)}</div>
              {cat.files > 0 && (
                <div className="text-xs text-txt-muted">{cat.files.toLocaleString()} files</div>
              )}
            </div>

            {/* Action */}
            <button
              onClick={(e) => { e.stopPropagation(); clean(cat.action, cat.name) }}
              disabled={busy[cat.action]}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 ${
                busy[cat.action]
                  ? 'bg-bg-elevated text-txt-muted'
                  : 'bg-danger/10 text-danger hover:bg-danger hover:text-white'
              }`}
            >
              {busy[cat.action] ? '⏳' : '🧹 Clean'}
            </button>
          </div>
        ))}
      </div>

      {/* Orphan Packages */}
      {orphans.length > 0 && (
        <div className="glass p-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-semibold">📦 Orphan Packages</h3>
              <p className="text-xs text-txt-muted">{orphans.length} packages no longer needed</p>
            </div>
            <button
              onClick={() => clean('clean_orphans', 'orphan packages')}
              disabled={busy.clean_orphans}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-danger/10 text-danger hover:bg-danger hover:text-white transition-all"
            >
              {busy.clean_orphans ? '⏳ Removing...' : '🧹 Remove All'}
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {orphans.slice(0, 30).map(pkg => (
              <span key={pkg} className="text-xs bg-bg-elevated px-2 py-0.5 rounded font-mono">
                {pkg}
              </span>
            ))}
            {orphans.length > 30 && (
              <span className="text-xs text-txt-muted px-2 py-0.5">+{orphans.length - 30} more</span>
            )}
          </div>
        </div>
      )}

      {/* Empty State */}
      {data && categories.length === 0 && orphans.length === 0 && (
        <div className="glass p-12 text-center">
          <span className="text-5xl">✨</span>
          <p className="text-sm text-txt-muted mt-3">Your system is clean!</p>
          <p className="text-xs text-txt-muted mt-1">No junk files found</p>
        </div>
      )}
    </div>
  )
}
