import { useState } from 'react'
import { useChannel } from '../hooks/useChannel'
import { useWs } from '../hooks/useWebSocket'

export default function CronJobs() {
  const data = useChannel('cron')
  const ws = useWs()
  const [busy, setBusy] = useState({})
  const [showAdd, setShowAdd] = useState(false)
  const [newSchedule, setNewSchedule] = useState('0 * * * *')
  const [newCommand, setNewCommand] = useState('')

  const toggle = async (job) => {
    setBusy(b => ({ ...b, [job.id]: true }))
    await ws.action('cron', 'toggle', { raw: job.raw, enable: !job.enabled })
    setBusy(b => ({ ...b, [job.id]: false }))
  }

  const remove = async (job) => {
    if (!confirm(`Delete this cron job?\n${job.raw}`)) return
    setBusy(b => ({ ...b, [job.id]: true }))
    await ws.action('cron', 'delete', { raw: job.raw })
    setBusy(b => ({ ...b, [job.id]: false }))
  }

  const addJob = async () => {
    if (!newSchedule.trim() || !newCommand.trim()) return
    const r = await ws.action('cron', 'add', { schedule: newSchedule, command: newCommand })
    if (r?.success) {
      setNewSchedule('0 * * * *')
      setNewCommand('')
      setShowAdd(false)
    }
  }

  const jobs = data?.jobs || []
  const userJobs = jobs.filter(j => j.user)
  const systemJobs = jobs.filter(j => !j.user)

  const presets = [
    { label: 'Every minute', value: '* * * * *' },
    { label: 'Every 5 min', value: '*/5 * * * *' },
    { label: 'Every hour', value: '0 * * * *' },
    { label: 'Every day at midnight', value: '0 0 * * *' },
    { label: 'Every Monday', value: '0 0 * * 1' },
    { label: 'Every month', value: '0 0 1 * *' },
  ]

  const JobRow = ({ job }) => (
    <div className={`flex items-center gap-3 p-3 rounded-lg transition-colors ${
      job.enabled ? 'bg-bg-surface' : 'bg-bg-surface/50 opacity-60'
    }`}>
      <span className="text-lg">{job.enabled ? '⏰' : '⏸️'}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <code className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded font-mono">
            {job.schedule}
          </code>
          <span className="text-xs text-txt-muted">{job.schedule_human}</span>
        </div>
        <p className="text-sm font-mono mt-1 truncate">{job.command}</p>
      </div>
      {job.user && (
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => toggle(job)}
            disabled={busy[job.id]}
            className={`relative w-10 h-5 rounded-full transition-colors duration-200 ${
              job.enabled ? 'bg-success' : 'bg-bg-elevated'
            } ${busy[job.id] ? 'opacity-50' : ''}`}
          >
            <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${
              job.enabled ? 'translate-x-5' : 'translate-x-0.5'
            }`} />
          </button>
          <button
            onClick={() => remove(job)}
            disabled={busy[job.id]}
            className="text-danger/60 hover:text-danger text-xs px-1"
            title="Delete"
          >
            ✕
          </button>
        </div>
      )}
      {!job.user && (
        <span className="text-[0.6rem] bg-warning/20 text-warning px-1.5 py-0.5 rounded-full font-medium shrink-0">
          {job.source}
        </span>
      )}
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold">⏰ Cron Jobs</h2>
          <p className="text-xs text-txt-muted mt-1">
            {data ? `${data.user_count} user · ${data.system_count} system` : 'Loading...'}
          </p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="px-4 py-2 rounded-lg font-semibold text-sm bg-primary text-white hover:brightness-110 transition-all"
        >
          {showAdd ? '✕ Cancel' : '＋ Add Job'}
        </button>
      </div>

      {/* Add Form */}
      {showAdd && (
        <div className="glass p-5 space-y-4">
          <h3 className="text-sm font-semibold">New Cron Job</h3>

          {/* Schedule Presets */}
          <div className="flex flex-wrap gap-1.5">
            {presets.map(p => (
              <button
                key={p.value}
                onClick={() => setNewSchedule(p.value)}
                className={`text-xs px-2.5 py-1 rounded-lg transition-colors ${
                  newSchedule === p.value
                    ? 'bg-primary text-white'
                    : 'bg-bg-elevated hover:bg-bg-surface text-txt-muted'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Schedule Input */}
          <div>
            <label className="text-xs text-txt-muted mb-1 block">Schedule (cron syntax)</label>
            <input
              type="text"
              value={newSchedule}
              onChange={e => setNewSchedule(e.target.value)}
              placeholder="* * * * *"
              className="w-full bg-bg-elevated rounded-lg px-3 py-2 text-sm font-mono outline-none focus:ring-2 ring-primary/50"
            />
            <p className="text-[0.6rem] text-txt-muted mt-1 font-mono">minute hour day-of-month month day-of-week</p>
          </div>

          {/* Command Input */}
          <div>
            <label className="text-xs text-txt-muted mb-1 block">Command</label>
            <input
              type="text"
              value={newCommand}
              onChange={e => setNewCommand(e.target.value)}
              placeholder="/usr/bin/my-script.sh"
              className="w-full bg-bg-elevated rounded-lg px-3 py-2 text-sm font-mono outline-none focus:ring-2 ring-primary/50"
            />
          </div>

          <button
            onClick={addJob}
            disabled={!newSchedule.trim() || !newCommand.trim()}
            className="px-4 py-2 rounded-lg font-semibold text-sm bg-success text-white hover:brightness-110 disabled:opacity-50 transition-all"
          >
            ✓ Add Cron Job
          </button>
        </div>
      )}

      {/* User Jobs */}
      {userJobs.length > 0 && (
        <div className="glass p-5">
          <h3 className="text-sm font-semibold mb-3">👤 Your Cron Jobs</h3>
          <div className="space-y-2">
            {userJobs.map(job => <JobRow key={job.id} job={job} />)}
          </div>
        </div>
      )}

      {/* System Jobs */}
      {systemJobs.length > 0 && (
        <div className="glass p-5">
          <h3 className="text-sm font-semibold mb-3">🔒 System Cron Jobs</h3>
          <div className="space-y-2">
            {systemJobs.map(job => <JobRow key={job.id} job={job} />)}
          </div>
        </div>
      )}

      {/* Empty State */}
      {data && jobs.length === 0 && !showAdd && (
        <div className="glass p-12 text-center">
          <span className="text-5xl">⏰</span>
          <p className="text-sm text-txt-muted mt-3">No cron jobs found</p>
          <p className="text-xs text-txt-muted mt-1">Click "Add Job" to create one</p>
        </div>
      )}
    </div>
  )
}
