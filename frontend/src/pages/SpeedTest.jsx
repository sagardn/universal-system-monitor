import { useState } from 'react'
import { useWs } from '../hooks/useWebSocket'

export default function SpeedTest() {
  const ws = useWs()
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const runTest = async () => {
    setRunning(true)
    setError('')
    setResult(null)
    try {
      const r = await ws.action('speedtest', 'run', {})
      if (r?.success && r?.data) {
        setResult(r.data)
      } else {
        setError(r?.message || 'Speed test failed')
      }
    } catch (e) {
      setError(e.message || 'Speed test failed')
    }
    setRunning(false)
  }

  const fmtSpeed = (v) => {
    if (!v) return '—'
    if (v >= 1000) return `${(v / 1000).toFixed(1)} Gbps`
    return `${v.toFixed(1)} Mbps`
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold">🌐 Speed Test</h2>
          <p className="text-xs text-txt-muted mt-1">Test your internet connection speed</p>
        </div>
        <button
          onClick={runTest}
          disabled={running}
          className="px-5 py-2.5 rounded-lg font-semibold text-sm transition-all duration-200 bg-primary text-white hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {running ? (
            <>
              <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Testing...
            </>
          ) : (
            '▶ Run Speed Test'
          )}
        </button>
      </div>

      {/* Running Animation */}
      {running && (
        <div className="glass p-8 flex flex-col items-center gap-4">
          <div className="relative w-24 h-24">
            <div className="absolute inset-0 rounded-full border-4 border-bg-elevated" />
            <div className="absolute inset-0 rounded-full border-4 border-primary border-t-transparent animate-spin" />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-2xl">📡</span>
            </div>
          </div>
          <p className="text-sm text-txt-muted animate-pulse">Measuring your connection speed...</p>
          <p className="text-xs text-txt-muted">This may take up to 30 seconds</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="glass p-4 border-l-4 border-danger">
          <p className="text-sm text-danger font-medium">❌ {error}</p>
          <p className="text-xs text-txt-muted mt-1">
            Make sure <code className="bg-bg-elevated px-1 rounded">speedtest-cli</code> is installed:
            <code className="bg-bg-elevated px-1 rounded ml-1">pip install speedtest-cli</code>
          </p>
        </div>
      )}

      {/* Results */}
      {result && !running && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Download */}
            <div className="glass p-6 text-center group hover:border-success/30 transition-colors">
              <div className="text-3xl mb-2">⬇️</div>
              <div className="text-3xl font-extrabold text-success tabular-nums">
                {fmtSpeed(result.download)}
              </div>
              <div className="text-xs text-txt-muted mt-1 font-medium uppercase tracking-wide">Download</div>
            </div>

            {/* Upload */}
            <div className="glass p-6 text-center group hover:border-primary/30 transition-colors">
              <div className="text-3xl mb-2">⬆️</div>
              <div className="text-3xl font-extrabold text-primary tabular-nums">
                {result.upload > 0 ? fmtSpeed(result.upload) : '—'}
              </div>
              <div className="text-xs text-txt-muted mt-1 font-medium uppercase tracking-wide">Upload</div>
            </div>

            {/* Ping */}
            <div className="glass p-6 text-center group hover:border-warning/30 transition-colors">
              <div className="text-3xl mb-2">🏓</div>
              <div className="text-3xl font-extrabold text-warning tabular-nums">
                {result.ping > 0 ? `${result.ping} ms` : '—'}
              </div>
              <div className="text-xs text-txt-muted mt-1 font-medium uppercase tracking-wide">Ping</div>
            </div>
          </div>

          {/* Server Info */}
          <div className="glass p-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
              <div>
                <span className="text-txt-muted">Server:</span>
                <span className="ml-1 font-semibold">{result.server || '—'}</span>
              </div>
              <div>
                <span className="text-txt-muted">Location:</span>
                <span className="ml-1 font-semibold">{result.server_location || '—'}</span>
              </div>
              <div>
                <span className="text-txt-muted">ISP:</span>
                <span className="ml-1 font-semibold">{result.isp || '—'}</span>
              </div>
              <div>
                <span className="text-txt-muted">IP:</span>
                <span className="ml-1 font-semibold font-mono">{result.ip || '—'}</span>
              </div>
            </div>
            {result.fallback && (
              <p className="text-xs text-warning mt-2">⚠️ Using curl fallback. Install <code className="bg-bg-elevated px-1 rounded">speedtest-cli</code> for full results.</p>
            )}
          </div>
        </>
      )}

      {/* Empty State */}
      {!running && !result && !error && (
        <div className="glass p-12 flex flex-col items-center gap-3 text-center">
          <span className="text-5xl">🚀</span>
          <p className="text-sm text-txt-muted">Click "Run Speed Test" to measure your internet speed</p>
          <p className="text-xs text-txt-muted">Tests download, upload, and latency</p>
        </div>
      )}
    </div>
  )
}
