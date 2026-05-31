import { useState, useRef, useEffect } from 'react'
import { useChannel } from '../hooks/useChannel'
import { useWs } from '../hooks/useWebSocket'
import { useToast } from '../components/Toast'
import { CardSkeleton } from '../components/Skeleton'

export default function Network() {
  const { data, loading } = useChannel('network')
  const ws = useWs()
  const toast = useToast()
  const [wifiScanning, setWifiScanning] = useState(false)
  const [wifiNetworks, setWifiNetworks] = useState(null)
  const [wifiPassword, setWifiPassword] = useState('')
  const [connectingSsid, setConnectingSsid] = useState(null)
  // Optimistic overrides — flip UI instantly, clear after collector confirms
  const [overrides, setOverrides] = useState({})
  const overrideTimers = useRef({})

  // Clear overrides when real data arrives (collector updates every 2s)
  useEffect(() => {
    if (data?.services) {
      // After real data arrives, clear any overrides older than 1s
      const now = Date.now()
      setOverrides(prev => {
        const next = { ...prev }
        for (const key of Object.keys(next)) {
          if (now - next[key].ts > 1000) delete next[key]
        }
        return next
      })
    }
  }, [data?.services])

  if (loading) return <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{[...Array(4)].map((_,i) => <CardSkeleton key={i} />)}</div>

  if (!data) return <div className="glass p-10 text-center"><p className="text-txt-muted">No network data available</p></div>

  const ifaces = Array.isArray(data.interfaces) ? data.interfaces : []
  const conns = Array.isArray(data.connections) ? data.connections : []
  const totalConns = typeof data.total_connections === 'number' ? data.total_connections : conns.length
  const stateSummary = (data.state_summary && typeof data.state_summary === 'object' && !Array.isArray(data.state_summary)) ? data.state_summary : {}
  const services = (data.services && typeof data.services === 'object') ? data.services : {}

  // Action with optimistic UI update
  const doToggle = async (key, action, params = {}, activeField = 'connected') => {
    // Optimistically flip the state
    const currentVal = (services[key] || {})[activeField]
    setOverrides(prev => ({ ...prev, [key]: { [activeField]: !currentVal, ts: Date.now() } }))

    const r = await ws.action('network', action, params)
    toast(r.message || r.data?.message || 'Done', r.success || r.data?.success ? 'success' : 'error')

    // If failed, revert override
    if (!r.success && !r.data?.success) {
      setOverrides(prev => { const n = { ...prev }; delete n[key]; return n })
    }
    return r
  }

  const doAction = async (action, params = {}) => {
    const r = await ws.action('network', action, params)
    toast(r.message || r.data?.message || 'Done', r.success || r.data?.success ? 'success' : 'error')
    return r
  }

  const scanWifi = async () => {
    setWifiScanning(true)
    toast('Scanning WiFi networks…', 'info', 4000)
    const r = await ws.action('network', 'wifi_scan', {})
    setWifiScanning(false)
    if (r.data?.networks) {
      setWifiNetworks(r.data.networks)
    }
  }

  const connectWifi = async (ssid) => {
    setConnectingSsid(ssid)
    toast(`Connecting to ${ssid}…`, 'info', 10000)
    const r = await doAction('wifi_connect', { ssid, password: wifiPassword })
    setConnectingSsid(null)
    setWifiPassword('')
    if (r.success || r.data?.success) setWifiNetworks(null)
  }

  // Merge real data with optimistic overrides
  const getService = (key, defaults = {}) => {
    const real = services[key] || defaults
    const override = overrides[key]
    return override ? { ...real, ...override } : real
  }

  const ts = getService('tailscale', { connected: false })
  const wifi = getService('wifi', { connected: false })
  const bt = getService('bluetooth', { powered: false })
  const fw = getService('firewall', { active: false })
  const dns = services.dns || {}

  return (
    <div>
      {/* ─── Network Services ─────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">

        {/* Tailscale */}
        {ts.available !== undefined && (
          <ServiceCard
            icon="🔗" name="Tailscale VPN"
            active={ts.connected}
            statusText={ts.connected ? `${String(ts.ip || '')}` : 'Disconnected'}
            onToggle={() => doToggle('tailscale', ts.connected ? 'tailscale_down' : 'tailscale_up')}
          >
            {ts.connected && (
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-txt-muted">
                <div><span className="text-txt-muted">Host:</span> <span className="text-txt font-medium">{String(ts.hostname || '')}</span></div>
                <div><span className="text-txt-muted">Net:</span> <span className="text-txt font-medium">{String(ts.tailnet || '')}</span></div>
                <div><span className="text-txt-muted">Peers:</span> <span className="text-success font-medium">{String(ts.peers_online || 0)}</span>/{String(ts.peers_total || 0)}</div>
              </div>
            )}
          </ServiceCard>
        )}

        {/* WiFi */}
        {wifi.available && (
          <ServiceCard
            icon="📶" name="WiFi"
            active={wifi.connected}
            statusText={wifi.connected ? `${String(wifi.ssid || '')} (${String(wifi.signal || 0)}%)` : 'Disconnected'}
            onToggle={() => wifi.connected ? doToggle('wifi', 'wifi_disconnect', { device: wifi.device || 'wlan0' }) : scanWifi()}
            toggleLabel={wifi.connected ? 'Disconnect' : 'Scan'}
          >
            {wifi.connected && wifi.security && (
              <div className="mt-1 text-xs text-txt-muted">🔒 {String(wifi.security)}</div>
            )}
            {!wifi.connected && (
              <button onClick={scanWifi} disabled={wifiScanning}
                className="mt-2 inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-sm bg-primary/15 text-primary border-none cursor-pointer hover:bg-primary/25 transition active:scale-95 disabled:opacity-50">
                {wifiScanning ? '⏳ Scanning…' : '📡 Scan Networks'}
              </button>
            )}
          </ServiceCard>
        )}

        {/* Bluetooth */}
        {bt.available && (
          <ServiceCard
            icon="🔵" name="Bluetooth"
            active={bt.powered}
            statusText={bt.powered ? String(bt.name || 'On') : 'Off'}
            onToggle={() => doToggle('bluetooth', 'bluetooth_toggle', { enable: !bt.powered }, 'powered')}
          />
        )}

        {/* Firewall */}
        {fw.available !== undefined && (
          <ServiceCard
            icon="🛡️" name="Firewall (UFW)"
            active={fw.active}
            statusText={fw.active ? `Active · ${String(fw.rules || 0)} rules` : 'Inactive'}
            onToggle={() => doToggle('firewall', 'firewall_toggle', { enable: !fw.active }, 'active')}
          />
        )}

        {/* DNS */}
        {dns.available && (
          <div className="glass p-5">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-lg">🌐</span>
                <span className="font-semibold text-sm">DNS</span>
              </div>
              <button onClick={() => doAction('dns_flush')}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-sm bg-primary/15 text-primary border-none cursor-pointer hover:bg-primary/25 transition active:scale-95">
                🗑 Flush Cache
              </button>
            </div>
            <div className="flex gap-2 flex-wrap">
              {(dns.servers || []).map((s, i) => (
                <span key={i} className="inline-flex items-center px-2 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-bg-elevated text-txt-muted tabular-nums">
                  {String(s)}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ─── WiFi Network Scanner ─────────────────────────────── */}
      {wifiNetworks && (
        <div className="glass p-0 overflow-hidden mb-6">
          <div className="flex items-center justify-between py-2 px-4 bg-bg-surface">
            <span className="text-xs font-semibold text-txt-muted uppercase tracking-wider">Available Networks ({wifiNetworks.length})</span>
            <button onClick={() => setWifiNetworks(null)}
              className="text-xs text-txt-muted hover:text-txt cursor-pointer bg-transparent border-none">✕ Close</button>
          </div>
          <div className="max-h-[300px] overflow-y-auto">
            {wifiNetworks.map(n => (
              <div key={n.ssid} className={`flex items-center gap-3 py-2.5 px-4 border-b border-border last:border-b-0 hover:bg-bg-hover transition ${n.in_use ? 'bg-success-muted/20' : ''}`}>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm flex items-center gap-2">
                    {String(n.ssid)}
                    {n.in_use && <span className="inline-flex items-center px-1.5 py-0.5 text-[0.6rem] font-semibold rounded-full bg-success-muted text-success">Connected</span>}
                  </div>
                  <div className="text-xs text-txt-muted flex items-center gap-3 mt-0.5">
                    <span>{String(n.signal)}% signal</span>
                    {n.security && <span>🔒 {String(n.security)}</span>}
                  </div>
                </div>
                <SignalBar signal={n.signal} />
                {!n.in_use && (
                  <div className="flex items-center gap-2">
                    {n.security && n.security !== '--' && n.security !== '' && (
                      <input
                        type="password" placeholder="Password"
                        className="w-28 px-2 py-1 text-xs bg-bg-surface border border-border rounded-sm text-txt outline-none focus:border-primary font-sans"
                        value={connectingSsid === n.ssid ? wifiPassword : ''}
                        onChange={e => { setConnectingSsid(n.ssid); setWifiPassword(e.target.value) }}
                      />
                    )}
                    <button onClick={() => connectWifi(n.ssid)} disabled={connectingSsid === n.ssid}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-sm bg-primary text-white border-none cursor-pointer hover:brightness-110 transition active:scale-95 disabled:opacity-50">
                      {connectingSsid === n.ssid ? '⏳' : '▶'} Connect
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ─── Connection Summary ─────────────────────────────── */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-primary-muted text-primary">
          {String(totalConns)} Total Connections
        </span>
        {Object.entries(stateSummary).map(([state, count]) => (
          <span key={state} className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full
            ${state === 'ESTABLISHED' ? 'bg-success-muted text-success' : state === 'LISTEN' ? 'bg-info-muted text-info' : 'bg-bg-elevated text-txt-muted'}`}>
            {String(count)} {String(state)}
          </span>
        ))}
      </div>

      {/* ─── Interfaces ────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {ifaces.filter(i => i.name !== 'lo').map(iface => (
          <div key={String(iface.name)} className="glass p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">{iface.type === 'wifi' ? '📶' : iface.type === 'docker' ? '🐳' : iface.type === 'vpn' ? '🔒' : '🔌'}</span>
                <div className="font-semibold text-sm">{String(iface.name)}</div>
              </div>
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full
                ${iface.is_up ? 'bg-success-muted text-success' : 'bg-bg-elevated text-txt-muted'}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${iface.is_up ? 'bg-success' : 'bg-txt-muted'}`} />
                {iface.is_up ? 'Up' : 'Down'}
              </span>
            </div>

            {Array.isArray(iface.addresses) && iface.addresses.map((a, i) => (
              <div key={i} className="text-xs text-txt-secondary mb-0.5">
                <span className="text-txt-muted">{String(a.family || '')}:</span> {String(a.address || '')}
                {a.netmask && <span className="text-txt-muted ml-1">/{String(a.netmask)}</span>}
              </div>
            ))}

            <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
              {iface.speed > 0 && (
                <div>
                  <div className="text-txt-muted">Link Speed</div>
                  <div className="font-semibold">{String(iface.speed)} Mbps</div>
                </div>
              )}
              <div>
                <div className="text-txt-muted">MTU</div>
                <div className="font-semibold">{String(iface.mtu || 0)}</div>
              </div>
              <div>
                <div className="text-txt-muted">Type</div>
                <div className="font-semibold capitalize">{String(iface.type || 'unknown')}</div>
              </div>
              {iface.wifi_signal && typeof iface.wifi_signal === 'object' && (
                <div>
                  <div className="text-txt-muted">WiFi Signal</div>
                  <div className="font-semibold">{String(iface.wifi_signal.signal_dbm || 0)} dBm ({String(iface.wifi_signal.quality_percent || 0)}%)</div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* ─── Connections Table ──────────────────────────────── */}
      {conns.length > 0 && (
        <div className="glass p-0 overflow-hidden">
          <div className="text-xs font-semibold text-txt-muted uppercase tracking-wider py-2 px-4 bg-bg-surface">
            Active Connections ({String(conns.length)})
          </div>
          <div className="max-h-[400px] overflow-y-auto">
            <table className="dtable">
              <thead>
                <tr>
                  <th>Process</th>
                  <th>PID</th>
                  <th>Proto</th>
                  <th>Local</th>
                  <th>Remote</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
                {conns.slice(0, 200).map((c, i) => (
                  <tr key={i}>
                    <td className="font-medium">{String(c.process || '—')}</td>
                    <td className="tabular-nums text-txt-muted">{String(c.pid || '—')}</td>
                    <td>{String(c.type || '')}/{String(c.family || '')}</td>
                    <td className="text-txt-muted tabular-nums">{String(c.local || '—')}</td>
                    <td className="text-txt-muted tabular-nums">{String(c.remote || '—')}</td>
                    <td>
                      <span className={`inline-flex items-center px-2 py-0.5 text-[0.6875rem] font-semibold rounded-full
                        ${c.state === 'ESTABLISHED' ? 'bg-success-muted text-success'
                          : c.state === 'LISTEN' ? 'bg-primary-muted text-primary'
                          : c.state === 'TIME_WAIT' ? 'bg-warning-muted text-warning'
                          : 'bg-bg-elevated text-txt-muted'}`}>
                        {String(c.state || 'NONE')}
                      </span>
                    </td>
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


// ─── Reusable Components ──────────────────────────────────────────────────────

function ServiceCard({ icon, name, active, statusText, onToggle, toggleLabel, children }) {
  return (
    <div className="glass p-5">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <span className="font-semibold text-sm">{name}</span>
        </div>
        <button onClick={onToggle}
          className={`relative inline-flex h-6 w-11 items-center rounded-full cursor-pointer transition-colors duration-200 border-none
            ${active ? 'bg-success' : 'bg-bg-elevated'}`}>
          <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform duration-200
            ${active ? 'translate-x-6' : 'translate-x-1'}`} />
        </button>
      </div>
      <div className="flex items-center gap-2">
        <span className={`w-1.5 h-1.5 rounded-full ${active ? 'bg-success' : 'bg-txt-muted'}`} />
        <span className={`text-xs ${active ? 'text-success' : 'text-txt-muted'}`}>{statusText}</span>
      </div>
      {children}
    </div>
  )
}

function SignalBar({ signal }) {
  const bars = signal > 75 ? 4 : signal > 50 ? 3 : signal > 25 ? 2 : 1
  return (
    <div className="flex items-end gap-0.5 h-4">
      {[1, 2, 3, 4].map(i => (
        <div key={i} className={`w-1 rounded-full transition-colors ${i <= bars ? 'bg-success' : 'bg-bg-elevated'}`}
          style={{ height: `${i * 25}%` }} />
      ))}
    </div>
  )
}
