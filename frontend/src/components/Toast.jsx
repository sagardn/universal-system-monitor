import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react'

const ToastCtx = createContext(null)
let toastId = 0

const ICONS = {
  success: '✅',
  error: '❌',
  warning: '⚠️',
  info: 'ℹ️',
}

const COLORS = {
  success: { bg: 'rgba(34,197,94,0.08)', border: 'rgba(34,197,94,0.25)', accent: '#22c55e' },
  error:   { bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.25)', accent: '#ef4444' },
  warning: { bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.25)', accent: '#f59e0b' },
  info:    { bg: 'rgba(59,130,246,0.08)', border: 'rgba(59,130,246,0.25)', accent: '#3b82f6' },
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const show = useCallback((message, severity = 'info', duration = 4000) => {
    const id = ++toastId
    const dur = severity === 'error' ? 8000 : duration
    setToasts(prev => [...prev.slice(-4), { id, message, severity, dur, createdAt: Date.now() }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), dur)
  }, [])

  return (
    <ToastCtx.Provider value={show}>
      {children}
      <div style={{
        position: 'fixed', top: '16px', right: '16px', zIndex: 1100,
        display: 'flex', flexDirection: 'column', gap: '8px',
        maxWidth: '400px', pointerEvents: 'none',
      }}>
        {toasts.map(t => (
          <ToastItem key={t.id} toast={t} onDismiss={() => setToasts(prev => prev.filter(x => x.id !== t.id))} />
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

function ToastItem({ toast, onDismiss }) {
  const [exiting, setExiting] = useState(false)
  const colors = COLORS[toast.severity] || COLORS.info
  const icon = ICONS[toast.severity] || ICONS.info
  const timerRef = useRef(null)

  const dismiss = useCallback(() => {
    setExiting(true)
    setTimeout(onDismiss, 200)
  }, [onDismiss])

  // Auto-dismiss with progress
  useEffect(() => {
    timerRef.current = setTimeout(dismiss, toast.dur)
    return () => clearTimeout(timerRef.current)
  }, [toast.dur, dismiss])

  return (
    <div
      onClick={dismiss}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
        padding: '12px 16px',
        background: colors.bg,
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: `1px solid ${colors.border}`,
        borderLeft: `3px solid ${colors.accent}`,
        borderRadius: '10px',
        boxShadow: `0 8px 32px rgba(0,0,0,0.12), 0 0 0 1px ${colors.border}`,
        cursor: 'pointer',
        pointerEvents: 'auto',
        position: 'relative',
        overflow: 'hidden',
        animation: exiting
          ? 'toast-exit 0.2s ease forwards'
          : 'toast-enter 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) forwards',
        transformOrigin: 'top right',
      }}
    >
      {/* Icon */}
      <span style={{ fontSize: '16px', lineHeight: '20px', flexShrink: 0 }}>{icon}</span>

      {/* Message */}
      <span style={{
        flex: 1,
        fontSize: '0.8125rem',
        lineHeight: '1.45',
        color: 'var(--color-txt)',
        fontWeight: 500,
        wordBreak: 'break-word',
      }}>
        {toast.message}
      </span>

      {/* Close button */}
      <button
        onClick={(e) => { e.stopPropagation(); dismiss() }}
        style={{
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--color-txt-muted)', fontSize: '14px', padding: '0 2px',
          lineHeight: '20px', flexShrink: 0, opacity: 0.6,
        }}
        onMouseEnter={(e) => e.target.style.opacity = 1}
        onMouseLeave={(e) => e.target.style.opacity = 0.6}
      >
        ✕
      </button>

      {/* Progress bar */}
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: '2px',
        background: colors.accent,
        opacity: 0.4,
        animation: `toast-progress ${toast.dur}ms linear forwards`,
        transformOrigin: 'left',
      }} />

      <style>{`
        @keyframes toast-enter {
          from { opacity: 0; transform: translateX(100%) scale(0.8); }
          to { opacity: 1; transform: translateX(0) scale(1); }
        }
        @keyframes toast-exit {
          from { opacity: 1; transform: translateX(0) scale(1); }
          to { opacity: 0; transform: translateX(100%) scale(0.8); }
        }
        @keyframes toast-progress {
          from { transform: scaleX(1); }
          to { transform: scaleX(0); }
        }
      `}</style>
    </div>
  )
}

export function useToast() { return useContext(ToastCtx) }
