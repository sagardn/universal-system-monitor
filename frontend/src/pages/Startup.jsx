import { useState } from 'react'
import { useChannel } from '../hooks/useChannel'
import { useWs } from '../hooks/useWebSocket'

export default function Startup() {
  const data = useChannel('startup')
  const ws = useWs()
  const [busy, setBusy] = useState({})

  const toggle = async (filename, enable) => {
    setBusy(b => ({ ...b, [filename]: true }))
    await ws.action('startup', 'toggle', { filename, enable })
    setBusy(b => ({ ...b, [filename]: false }))
  }

  const remove = async (filename) => {
    if (!confirm(`Delete ${filename} from autostart?`)) return
    setBusy(b => ({ ...b, [filename]: true }))
    await ws.action('startup', 'delete', { filename })
    setBusy(b => ({ ...b, [filename]: false }))
  }

  const apps = data?.apps || []
  const desktopApps = apps.filter(a => a.type === 'desktop')
  const systemdApps = apps.filter(a => a.type === 'systemd')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold">🚀 Startup Applications</h2>
          <p className="text-xs text-txt-muted mt-1">
            {data ? `${data.enabled_count} enabled / ${data.count} total` : 'Loading...'}
          </p>
        </div>
      </div>

      {/* Desktop Autostart */}
      {desktopApps.length > 0 && (
        <div className="glass p-5">
          <h3 className="text-sm font-semibold mb-3">📁 Desktop Autostart</h3>
          <div className="space-y-2">
            {desktopApps.map(app => (
              <div key={app.filename}
                className={`flex items-center gap-3 p-3 rounded-lg transition-colors ${
                  app.enabled ? 'bg-bg-surface' : 'bg-bg-surface/50 opacity-60'
                }`}
              >
                <span className="text-lg">{app.icon ? '🔧' : '📄'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate">{app.name}</span>
                    {!app.user && (
                      <span className="text-[0.6rem] bg-info/20 text-info px-1.5 py-0.5 rounded-full font-medium">SYSTEM</span>
                    )}
                  </div>
                  {app.comment && <p className="text-xs text-txt-muted truncate">{app.comment}</p>}
                  {app.exec && <p className="text-[0.65rem] text-txt-muted font-mono truncate">{app.exec}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => toggle(app.filename, !app.enabled)}
                    disabled={busy[app.filename]}
                    className={`relative w-10 h-5 rounded-full transition-colors duration-200 ${
                      app.enabled ? 'bg-success' : 'bg-bg-elevated'
                    } ${busy[app.filename] ? 'opacity-50' : ''}`}
                  >
                    <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${
                      app.enabled ? 'translate-x-5' : 'translate-x-0.5'
                    }`} />
                  </button>
                  {app.user && (
                    <button
                      onClick={() => remove(app.filename)}
                      disabled={busy[app.filename]}
                      className="text-danger/60 hover:text-danger text-xs px-1"
                      title="Remove"
                    >
                      ✕
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Systemd User Services */}
      {systemdApps.length > 0 && (
        <div className="glass p-5">
          <h3 className="text-sm font-semibold mb-3">⚙️ Systemd User Services</h3>
          <div className="space-y-2">
            {systemdApps.map(app => (
              <div key={app.filename}
                className="flex items-center gap-3 p-3 rounded-lg bg-bg-surface"
              >
                <span className="text-lg">🔩</span>
                <div className="flex-1 min-w-0">
                  <span className="font-medium text-sm">{app.name}</span>
                  <span className="text-xs text-txt-muted ml-2">{app.filename}</span>
                </div>
                <span className="text-xs bg-success/20 text-success px-2 py-0.5 rounded-full font-medium">enabled</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {data && apps.length === 0 && (
        <div className="glass p-12 text-center">
          <span className="text-5xl">🚀</span>
          <p className="text-sm text-txt-muted mt-3">No startup applications found</p>
          <p className="text-xs text-txt-muted mt-1">Add .desktop files to ~/.config/autostart/</p>
        </div>
      )}
    </div>
  )
}
