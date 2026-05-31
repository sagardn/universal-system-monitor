/** USM — Formatting Utilities */

export function fmtBytes(n) {
  if (n == null || isNaN(n)) return '0 B'
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
  let i = 0, v = Math.abs(n)
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`
}

export function fmtBps(n) {
  if (!n) return '0 B/s'
  const units = ['B/s', 'KB/s', 'MB/s', 'GB/s']
  let i = 0, v = Math.abs(n)
  while (v >= 1000 && i < units.length - 1) { v /= 1000; i++ }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`
}

export function fmtPercent(n, d = 1) { return n != null ? `${Number(n).toFixed(d)}%` : '0%' }

export function fmtUptime(s) {
  if (!s || s < 0) return '0s'
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export function fmtTimeAgo(ts) {
  if (!ts) return ''
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export function fmtTemp(c) { return c != null ? `${Math.round(c)}°C` : '' }
export function fmtWatts(w) { return w != null ? `${Number(w).toFixed(1)}W` : '' }

export function fmtMhz(m) {
  if (!m) return ''
  return m >= 1000 ? `${(m / 1000).toFixed(1)} GHz` : `${Math.round(m)} MHz`
}

export function fmtMins(m) {
  if (!m) return '—'
  const h = Math.floor(m / 60), mins = m % 60
  return h > 0 ? `${h}h ${mins}m` : `${mins}m`
}

export function truncate(s, max = 40) { return s?.length > max ? s.slice(0, max) + '…' : s || '' }

/** Color interpolation for gauges */
export function gaugeColor(pct) {
  if (pct < 50) return '#22c55e'
  if (pct < 75) return '#f59e0b'
  return '#ef4444'
}
