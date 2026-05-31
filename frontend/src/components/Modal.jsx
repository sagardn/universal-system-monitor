import { useState } from 'react'

export default function Modal({ open, onClose, title, children, confirmText = 'Confirm', danger = false, onConfirm }) {
  if (!open) return null
  return (
    <div className="modal-overlay" onClick={() => onClose(false)}>
      <div className="modal-dialog" onClick={e => e.stopPropagation()}>
        <div className="modal-header" style={danger ? { background: 'var(--danger-muted)' } : undefined}>
          <h2>{title}</h2>
          <button className="btn btn-icon btn-ghost" onClick={() => onClose(false)} style={{ fontSize: 18 }}>✕</button>
        </div>
        <div className="modal-body">{children}</div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={() => onClose(false)}>Cancel</button>
          <button className={danger ? 'btn btn-danger' : 'btn btn-primary'} onClick={() => { onConfirm?.(); onClose(true) }}>
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
