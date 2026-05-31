import { useState, useRef, useCallback, useEffect } from 'react'
import { useChannel } from '../hooks/useChannel'
import { useWs } from '../hooks/useWebSocket'
import { useToast } from '../components/Toast'
import { CardSkeleton } from '../components/Skeleton'

export default function Audio() {
  const { data, loading } = useChannel('audio')
  const ws = useWs()
  const toast = useToast()

  if (loading) return <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{[...Array(4)].map((_,i) => <CardSkeleton key={i} />)}</div>

  if (!data || data.status === 'error') return (
    <div className="glass p-10 text-center">
      <p className="text-4xl mb-3">🔇</p>
      <p className="text-txt-muted text-lg">Audio not available</p>
      <p className="text-txt-muted text-sm mt-2">{data?.error || 'PipeWire / PulseAudio not detected'}</p>
    </div>
  )

  const sinks = data?.sinks || []
  const sources = data?.sources || []
  const streams = data?.streams || []
  const summary = data?.summary || {}

  return (
    <div>
      {/* Summary */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-primary-muted text-primary">
          🎵 {data.backend}
        </span>
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-bg-elevated text-txt-muted">
          {summary.sinks || sinks.length} sinks
        </span>
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-bg-elevated text-txt-muted">
          {summary.sources || sources.length} sources
        </span>
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-success-muted text-success">
          {summary.active_streams || 0} active streams
        </span>
      </div>

      {/* Output Devices */}
      {sinks.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div className="text-sm font-semibold mb-3">🔊 Output Devices (Sinks)</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {sinks.map(s => <AudioDevice key={s.id} node={s} type="sink" ws={ws} toast={toast} />)}
          </div>
        </div>
      )}

      {/* Input Devices */}
      {sources.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div className="text-sm font-semibold mb-3">🎤 Input Devices (Sources)</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {sources.map(s => <AudioDevice key={s.id} node={s} type="source" ws={ws} toast={toast} />)}
          </div>
        </div>
      )}

      {/* Streams */}
      {streams.length > 0 && (
        <div>
          <div className="text-sm font-semibold mb-3">🎶 Active Streams</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {streams.map(s => <AudioDevice key={s.id} node={s} type="stream" ws={ws} toast={toast} />)}
          </div>
        </div>
      )}
    </div>
  )
}

function AudioDevice({ node, type, ws, toast }) {
  const [localVol, setLocalVol] = useState(null)
  const [dragging, setDragging] = useState(false)
  const debounceRef = useRef(null)
  const clearRef = useRef(null)

  // Use localVol while dragging/recently changed, otherwise use server data
  const curVol = localVol !== null ? localVol : (node.volume || 0)
  const volPct = Math.round(curVol * 100)

  const setVolume = useCallback((newVol) => {
    const v = Math.max(0, Math.min(1.5, parseFloat(newVol)))
    setLocalVol(v)

    // Clear any pending reset
    if (clearRef.current) clearTimeout(clearRef.current)

    // Debounce the API call
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      await ws.action('audio', 'set_volume', { node_id: node.id, volume: v })
    }, 60)
  }, [ws, node.id])

  const handleDragEnd = useCallback(() => {
    setDragging(false)
    // Keep local vol for 6 seconds (2x the audio collector interval)
    // so the server data catches up before we release control
    if (clearRef.current) clearTimeout(clearRef.current)
    clearRef.current = setTimeout(() => setLocalVol(null), 6000)
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      if (clearRef.current) clearTimeout(clearRef.current)
    }
  }, [])

  const toggleMute = async () => {
    const r = await ws.action('audio', 'toggle_mute', { node_id: node.id })
    if (r?.message) toast(r.message, r.success ? 'success' : 'error')
  }

  const setDefault = async () => {
    const action = type === 'source' ? 'set_default_source' : 'set_default_sink'
    const r = await ws.action('audio', action, { node_id: node.id })
    if (r?.message) toast(r.message, r.success ? 'success' : 'error')
  }

  const isMuted = node.mute
  const isRunning = node.state === 'running'

  // Fill percentage for the slider (max=150%, so 100% = 66.7% of the bar)
  const fillPct = Math.min((curVol / 1.5) * 100, 100)
  const fillColor = isMuted ? '#666' : volPct > 100 ? '#f59e0b' : '#06b6d4'

  return (
    <div style={{
      padding: 16, borderRadius: 12,
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      opacity: isMuted ? 0.65 : 1, transition: 'opacity 0.3s',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {node.application || node.name}
            </div>
            {node.application && (
              <div style={{ fontSize: 11, color: 'var(--txt-muted)' }}>{node.media_class}</div>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          {node.channels && <span style={{ fontSize: 11, color: 'var(--txt-muted)' }}>{node.channels}ch</span>}
          {node.rate && <span style={{ fontSize: 11, color: 'var(--txt-muted)' }}>{node.rate}Hz</span>}
          <span style={{
            display: 'inline-flex', alignItems: 'center', padding: '2px 8px',
            fontSize: 10, fontWeight: 600, borderRadius: 99,
            background: isRunning ? 'rgba(34,197,94,0.15)' : 'rgba(255,255,255,0.06)',
            color: isRunning ? '#22c55e' : 'var(--txt-muted)',
          }}>
            {node.state}
          </span>
        </div>
      </div>

      {/* Volume Control */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* Mute Toggle */}
        <button
          onClick={toggleMute}
          style={{
            width: 42, height: 42, borderRadius: 10,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 20, border: 'none', cursor: 'pointer',
            transition: 'all 0.2s', flexShrink: 0,
            background: isMuted ? 'rgba(239,68,68,0.2)' : 'rgba(255,255,255,0.06)',
            color: isMuted ? '#ef4444' : 'var(--txt)',
          }}
          title={isMuted ? 'Unmute' : 'Mute'}
        >
          {isMuted ? '🔇' : volPct > 50 ? '🔊' : volPct > 0 ? '🔉' : '🔈'}
        </button>

        {/* Custom Visual Slider */}
        <div style={{ flex: 1, position: 'relative', height: 32, display: 'flex', alignItems: 'center' }}>
          {/* Background track */}
          <div style={{
            position: 'absolute', left: 0, right: 0, height: 12, borderRadius: 6,
            background: 'rgba(255,255,255,0.08)',
          }} />

          {/* Filled portion */}
          <div style={{
            position: 'absolute', left: 0, height: 12, borderRadius: 6,
            width: `${fillPct}%`,
            background: `linear-gradient(90deg, ${fillColor}, ${fillColor}dd)`,
            transition: dragging ? 'none' : 'width 0.2s ease',
            boxShadow: isMuted ? 'none' : `0 0 12px ${fillColor}44`,
          }} />

          {/* 100% mark */}
          <div style={{
            position: 'absolute', left: `${(1.0 / 1.5) * 100}%`,
            height: 18, width: 2, borderRadius: 1,
            background: 'rgba(255,255,255,0.25)',
            transform: 'translateX(-1px)',
          }} />

          {/* Native range input (transparent, on top for interaction) */}
          <input
            type="range"
            min="0"
            max="1.5"
            step="0.01"
            value={curVol}
            onChange={(e) => setVolume(e.target.value)}
            onMouseDown={() => setDragging(true)}
            onMouseUp={handleDragEnd}
            onTouchStart={() => setDragging(true)}
            onTouchEnd={handleDragEnd}
            style={{
              position: 'relative', zIndex: 2,
              width: '100%', height: 32,
              WebkitAppearance: 'none', appearance: 'none',
              background: 'transparent', cursor: 'pointer', outline: 'none',
            }}
          />
        </div>

        {/* Volume number */}
        <div style={{ minWidth: 54, textAlign: 'right', flexShrink: 0 }}>
          <span style={{
            fontWeight: 700, fontSize: 16,
            fontVariantNumeric: 'tabular-nums',
            color: isMuted ? '#ef4444' : volPct > 100 ? '#f59e0b' : 'var(--txt)',
            textDecoration: isMuted ? 'line-through' : 'none',
          }}>
            {volPct}%
          </span>
        </div>

        {/* Default button */}
        {type !== 'stream' && (
          <button
            onClick={setDefault}
            style={{
              padding: '6px 10px', borderRadius: 8, fontSize: 11, fontWeight: 600,
              background: 'rgba(255,255,255,0.06)', border: 'none', cursor: 'pointer',
              color: 'var(--txt-muted)', transition: 'all 0.2s', flexShrink: 0,
            }}
            title="Set as default device"
          >
            ★ Default
          </button>
        )}
      </div>

      {/* Status */}
      {isMuted && (
        <div style={{ fontSize: 11, color: '#ef4444', marginTop: 8, marginLeft: 54 }}>
          🔇 Audio muted — click speaker to unmute
        </div>
      )}
      {volPct > 100 && !isMuted && (
        <div style={{ fontSize: 11, color: '#f59e0b', marginTop: 8, marginLeft: 54 }}>
          ⚠️ Volume above 100% may distort
        </div>
      )}

      {/* Thumb CSS for the transparent range input */}
      <style>{`
        input[type=range]::-webkit-slider-thumb {
          -webkit-appearance: none; appearance: none;
          width: 22px; height: 22px; border-radius: 50%;
          background: ${isMuted ? '#ef4444' : fillColor};
          border: 3px solid var(--bg-card, #1a1a2e);
          box-shadow: 0 0 10px ${isMuted ? 'rgba(239,68,68,0.5)' : `${fillColor}88`};
          cursor: pointer; transition: transform 0.1s;
        }
        input[type=range]::-webkit-slider-thumb:hover { transform: scale(1.2); }
        input[type=range]::-moz-range-thumb {
          width: 22px; height: 22px; border-radius: 50%;
          background: ${isMuted ? '#ef4444' : fillColor};
          border: 3px solid var(--bg-card, #1a1a2e);
          box-shadow: 0 0 10px ${isMuted ? 'rgba(239,68,68,0.5)' : `${fillColor}88`};
          cursor: pointer;
        }
        input[type=range]::-webkit-slider-runnable-track {
          height: 12px; background: transparent;
        }
        input[type=range]::-moz-range-track {
          height: 12px; background: transparent;
        }
      `}</style>
    </div>
  )
}
