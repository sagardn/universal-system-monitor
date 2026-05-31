import { useChannel } from '../hooks/useChannel'
import { useWs } from '../hooks/useWebSocket'
import { useToast } from '../components/Toast'
import Modal from '../components/Modal'
import { TableSkeleton } from '../components/Skeleton'
import { useState } from 'react'

export default function Snapshots() {
  const { data, loading } = useChannel('snapshots')
  const ws = useWs()
  const toast = useToast()
  const [restoreModal, setRestoreModal] = useState(null)

  const doCreate = async () => {
    toast('Creating snapshot…', 'info')
    const r = await ws.action('snapshot', 'create', { description: 'Manual snapshot from USM' })
    toast(r.message || r.data?.message || 'Done', r.success || r.data?.success ? 'success' : 'error')
  }

  const doDelete = async (num) => {
    const r = await ws.action('snapshot', 'delete', { number: num })
    toast(r.message || r.data?.message || 'Done', r.success || r.data?.success ? 'success' : 'error')
  }

  const doRestore = async (num) => {
    setRestoreModal(null)
    toast('Restoring snapshot… A reboot may be required.', 'warning', 10000)
    const r = await ws.action('snapshot', 'restore', { number: num })
    toast(r.message || r.data?.message || 'Done', r.success || r.data?.success ? 'success' : 'error')
  }

  if (loading) return <TableSkeleton rows={6} cols={4} />

  if (!data?.available) return (
    <div className="glass p-10 text-center">
      <p className="text-txt-muted text-lg">BTRFS / Snapper not available</p>
      <p className="text-txt-muted text-sm mt-2">Requires BTRFS filesystem with snapper configured</p>
    </div>
  )

  const snapshots = data?.snapshots || []

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <button onClick={doCreate}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-sm bg-gradient-to-r from-primary to-accent text-white border-none cursor-pointer hover:brightness-110 shadow-[0_0_24px_var(--color-primary-glow)] transition-all active:scale-95">
          📸 Create Snapshot
        </button>
        <span className="text-xs text-txt-muted">{snapshots.length} snapshots</span>
        {data?.has_snapper && (
          <span className="inline-flex items-center px-2 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-primary-muted text-primary">
            snapper
          </span>
        )}
      </div>

      <div className="glass p-0 overflow-hidden">
        <table className="dtable">
          <thead><tr><th>#</th><th>Type</th><th>Date</th><th>Description</th><th>Actions</th></tr></thead>
          <tbody>
            {snapshots.map(s => (
              <tr key={s.number ?? s.id ?? s.path}>
                <td className="tabular-nums font-semibold">{s.number ?? s.id ?? '—'}</td>
                <td>
                  <span className={`inline-flex items-center px-2 py-0.5 text-[0.6875rem] font-semibold rounded-full
                    ${s.type === 'pre' ? 'bg-primary-muted text-primary' : s.type === 'post' ? 'bg-success-muted text-success' : 'bg-bg-elevated text-txt-muted'}`}>
                    {s.type || 'snapshot'}
                  </span>
                </td>
                <td className="text-txt-muted">{s.date || '—'}</td>
                <td className="text-txt-muted truncate max-w-[300px]">{s.description || s.path || '—'}</td>
                <td>
                  <div className="flex gap-1.5">
                    <button onClick={() => setRestoreModal(s)}
                      className="inline-flex items-center gap-1 px-2 py-1 text-[0.6875rem] font-semibold rounded-sm bg-warning/15 text-warning border-none cursor-pointer hover:bg-warning/25 transition active:scale-95">
                      ↩ Restore
                    </button>
                    <button onClick={() => doDelete(s.number ?? s.id)}
                      className="inline-flex items-center justify-center w-7 h-7 rounded-sm border border-border text-danger bg-transparent text-xs cursor-pointer hover:bg-danger-muted transition active:scale-90">
                      🗑
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {restoreModal && (
        <Modal open={true} onClose={() => setRestoreModal(null)} title="⚠️ Restore Snapshot"
          confirmText="Restore" danger onConfirm={() => doRestore(restoreModal.number ?? restoreModal.id)}>
          <p>Restore snapshot <strong>#{restoreModal.number ?? restoreModal.id}</strong>?</p>
          <p className="text-warning text-sm mt-2 bg-warning-muted p-3 rounded-md">
            This will revert your system to this snapshot. A reboot will be required.
          </p>
        </Modal>
      )}
    </div>
  )
}
