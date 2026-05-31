import { useState, useMemo } from 'react'
import { useChannel } from '../hooks/useChannel'
import { useWs } from '../hooks/useWebSocket'
import { useToast } from '../components/Toast'
import Modal from '../components/Modal'
import { TableSkeleton } from '../components/Skeleton'
import { fmtBytes, gaugeColor } from '../utils/format'

export default function Processes() {
  const { data, loading } = useChannel('processes')
  const ws = useWs()
  const toast = useToast()
  const [filter, setFilter] = useState('')
  const [sortCol, setSortCol] = useState('cpu_percent')
  const [sortAsc, setSortAsc] = useState(false)
  const [showZombies, setShowZombies] = useState(false)
  const [selected, setSelected] = useState(null)
  const [killModal, setKillModal] = useState(null)

  const procs = data?.processes || []
  const summary = data?.summary || {}

  const sorted = useMemo(() => {
    let list = procs
    if (filter) {
      const q = filter.toLowerCase()
      list = list.filter(p => p.name.toLowerCase().includes(q) || String(p.pid).includes(q) || (p.username||'').toLowerCase().includes(q))
    }
    if (showZombies) list = list.filter(p => p.is_zombie)
    return [...list].sort((a, b) => {
      let va = a[sortCol], vb = b[sortCol]
      if (typeof va === 'string') { va = va.toLowerCase(); vb = (vb||'').toLowerCase() }
      return sortAsc ? (va < vb ? -1 : 1) : (va > vb ? -1 : 1)
    }).slice(0, 300)
  }, [procs, filter, sortCol, sortAsc, showZombies])

  const doSort = (col) => {
    if (sortCol === col) setSortAsc(!sortAsc)
    else { setSortCol(col); setSortAsc(false) }
  }

  const doKill = async (pid, name, sig) => {
    setKillModal(null)
    const r = await ws.action('process', sig === 'SIGKILL' ? 'force_kill' : 'kill', { pid, signal: sig })
    toast(r.message || r.data?.message || 'Done', r.success || r.data?.success ? 'success' : 'error')
  }

  const openKill = (p, sig) => {
    if (p.safety === 'critical') {
      toast(`⛔ ${p.name} is a system-critical process. Killing it would crash your system.`, 'error')
      return
    }
    setKillModal({ pid: p.pid, name: p.name, sig, safety: p.safety })
  }

  if (loading) return <TableSkeleton rows={12} cols={7} />

  const TH = ({ col, children, w }) => (
    <th className={sortCol === col ? 'sorted' : ''} style={{ width: w }} onClick={() => doSort(col)}>
      {children} {sortCol === col && <span className="ml-1">{sortAsc ? '▲' : '▼'}</span>}
    </th>
  )

  return (
    <div>
      {/* Toolbar */}
      <div className="flex items-center gap-3 mb-3.5 flex-wrap">
        <div className="flex-1 min-w-[200px] flex items-center gap-2 py-[7px] px-3.5 bg-bg-surface border border-border rounded-sm focus-within:border-primary transition-colors">
          <span className="text-txt-muted text-sm">🔍</span>
          <input className="flex-1 bg-transparent border-none text-txt text-xs outline-none placeholder:text-txt-muted font-sans"
            placeholder="Search processes…" value={filter} onChange={e => setFilter(e.target.value)} />
        </div>
        <button onClick={() => setShowZombies(!showZombies)}
          className={`inline-flex items-center gap-2 px-3 py-[7px] text-[0.6875rem] font-semibold rounded-sm border cursor-pointer transition-all active:scale-95
            ${showZombies ? 'bg-danger text-white border-danger' : 'bg-transparent text-txt-secondary border-border hover:bg-bg-hover'}`}>
          🧟 Zombies
        </button>
        <span className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">
          {summary.total || 0} total · {summary.running || 0} running · {summary.zombie || 0} zombie · {summary.leak_count || 0} leaks
        </span>
      </div>

      {/* Table */}
      <div className="glass p-0 overflow-hidden">
        <div className="max-h-[calc(100vh-240px)] overflow-y-auto">
          <table className="dtable">
            <thead>
              <tr>
                <TH col="pid" w="70px">PID</TH>
                <TH col="name">Name</TH>
                <TH col="username" w="80px">User</TH>
                <TH col="cpu_percent" w="75px">CPU%</TH>
                <TH col="memory_percent" w="75px">RAM%</TH>
                <TH col="rss" w="85px">RSS</TH>
                <TH col="status" w="90px">Status</TH>
                <th style={{ width: 110 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(p => (
                <tr key={p.pid} className={`${selected === p.pid ? 'selected' : ''} ${p.is_zombie ? 'bg-danger-muted' : ''}`}
                  onClick={() => setSelected(selected === p.pid ? null : p.pid)}>
                  <td className="tabular-nums">{p.pid}</td>
                  <td>
                    <span className="inline-flex items-center gap-1.5">
                      {p.has_icon
                        ? <img className="w-5 h-5 rounded object-contain" src={`/api/icons/${encodeURIComponent(p.name)}`} alt="" />
                        : <span className="w-5 h-5 rounded bg-bg-elevated inline-flex items-center justify-center text-[10px] text-txt-muted">◆</span>}
                      <span className="truncate max-w-[200px]">{p.name}</span>
                      {p.memory_leak && <span className="text-warning text-xs" title="Possible memory leak">⚠️</span>}
                      {p.safety === 'critical' && <span className="text-[0.6rem] px-1.5 py-0.5 bg-danger-muted text-danger rounded-full font-semibold">SYS</span>}
                      {p.safety === 'warn' && <span className="text-[0.6rem] px-1.5 py-0.5 bg-warning-muted text-warning rounded-full font-semibold">⚠</span>}
                    </span>
                  </td>
                  <td className="text-txt-muted">{p.username}</td>
                  <td style={{ color: gaugeColor(p.cpu_percent) }} className="tabular-nums font-medium">{p.cpu_percent.toFixed(1)}</td>
                  <td style={{ color: gaugeColor(p.memory_percent) }} className="tabular-nums font-medium">{p.memory_percent.toFixed(1)}</td>
                  <td className="tabular-nums">{fmtBytes(p.rss)}</td>
                  <td>
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full
                      ${p.is_zombie ? 'bg-danger-muted text-danger' : p.status === 'running' ? 'bg-success-muted text-success' : 'bg-bg-elevated text-txt-muted'}`}>
                      <span className={`sdot ${p.is_zombie ? 'bg-danger sdot-pulse' : p.status === 'running' ? 'bg-success sdot-pulse' : 'bg-txt-muted'}`} />
                      {p.status}
                    </span>
                  </td>
                  <td onClick={e => e.stopPropagation()}>
                    <div className="flex gap-1.5">
                      <button onClick={() => openKill(p, 'SIGTERM')} title={p.safety === 'critical' ? 'System process — cannot kill' : 'End Task'}
                        disabled={p.safety === 'critical'}
                        className={`inline-flex items-center justify-center w-7 h-7 rounded-sm border text-xs cursor-pointer transition-all active:scale-90
                          ${p.safety === 'critical' ? 'opacity-30 cursor-not-allowed border-border text-txt-muted bg-transparent' : 'border-border text-txt-secondary bg-transparent hover:bg-bg-hover hover:text-txt'}`}>
                        ✕
                      </button>
                      <button onClick={() => openKill(p, 'SIGKILL')} title={p.safety === 'critical' ? 'System process' : 'Force Kill'}
                        disabled={p.safety === 'critical'}
                        className={`inline-flex items-center justify-center w-7 h-7 rounded-sm border text-xs cursor-pointer transition-all active:scale-90
                          ${p.safety === 'critical' ? 'opacity-30 cursor-not-allowed border-border text-txt-muted bg-transparent' : 'border-border text-danger bg-transparent hover:bg-danger-muted'}`}>
                        ⚡
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Kill Modal */}
      {killModal && (
        <Modal open={true} onClose={() => setKillModal(null)}
          title={killModal.sig === 'SIGKILL' ? '⚡ Force Kill Process' : '✕ End Process'}
          confirmText={killModal.sig === 'SIGKILL' ? 'Force Kill' : 'End Task'}
          danger={killModal.sig === 'SIGKILL'}
          onConfirm={() => doKill(killModal.pid, killModal.name, killModal.sig)}>
          <p className="mb-2">Send <strong>{killModal.sig}</strong> to <strong>{killModal.name}</strong> (PID {killModal.pid})?</p>
          {killModal.safety === 'warn' && (
            <p className="text-warning text-sm bg-warning-muted p-3 rounded-md">
              ⚠️ This is a system service. Killing it may affect desktop functionality.
            </p>
          )}
          {killModal.sig === 'SIGKILL' && (
            <p className="text-danger text-sm mt-2">This will immediately terminate the process without cleanup.</p>
          )}
        </Modal>
      )}
    </div>
  )
}
