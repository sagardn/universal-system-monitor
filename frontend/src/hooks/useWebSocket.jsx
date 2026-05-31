import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'

const WsContext = createContext(null)

const CHANNELS = [
  'system', 'processes', 'gpu', 'docker', 'services', 'cgroups',
  'battery', 'network', 'security', 'audio', 'packages', 'snapshots',
  'scheduler', 'alerts', 'thermal', 'disks', 'startup', 'cron', 'cleanup',
]

export function WebSocketProvider({ children }) {
  const wsRef = useRef(null)
  const handlersRef = useRef(new Map())
  const subsRef = useRef(new Set())
  const [status, setStatus] = useState('disconnected')
  const retryRef = useRef(1000)
  const actionIdRef = useRef(0)
  const actionCallbacksRef = useRef(new Map())

  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  const subscribe = useCallback((channels) => {
    channels.forEach(ch => subsRef.current.add(ch))
    send({ type: 'subscribe', channels })
  }, [send])

  const unsubscribe = useCallback((channels) => {
    channels.forEach(ch => subsRef.current.delete(ch))
    send({ type: 'unsubscribe', channels })
  }, [send])

  const on = useCallback((channel, handler) => {
    if (!handlersRef.current.has(channel)) handlersRef.current.set(channel, new Set())
    handlersRef.current.get(channel).add(handler)
    return () => handlersRef.current.get(channel)?.delete(handler)
  }, [])

  const action = useCallback((target, actionName, params = {}) => {
    return new Promise((resolve) => {
      const id = ++actionIdRef.current
      const timeout = setTimeout(() => {
        actionCallbacksRef.current.delete(id)
        resolve({ success: false, message: 'Timeout' })
      }, 30000)
      actionCallbacksRef.current.set(id, { resolve, timeout, target, action: actionName })
      send({ type: 'action', target, action: actionName, params, id })
    })
  }, [send])

  useEffect(() => {
    let mounted = true
    let reconnectTimer = null

    function connect() {
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const url = `${proto}//${location.host}/ws`
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (!mounted) return
        setStatus('connected')
        retryRef.current = 1000
        // Notify all listeners of reconnection
        const statusHandlers = handlersRef.current.get('__status__')
        if (statusHandlers) statusHandlers.forEach(h => h('connected'))
        if (subsRef.current.size > 0) {
          send({ type: 'subscribe', channels: [...subsRef.current] })
        }
      }

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.type === 'data' && msg.channel) {
            const handlers = handlersRef.current.get(msg.channel)
            if (handlers) handlers.forEach(h => h(msg.data, msg.timestamp))
          } else if (msg.type === 'action_result') {
            // Match by target+action for now
            for (const [id, cb] of actionCallbacksRef.current.entries()) {
              if (cb.target === msg.data?.target && cb.action === msg.data?.action) {
                clearTimeout(cb.timeout)
                cb.resolve(msg.data)
                actionCallbacksRef.current.delete(id)
                break
              }
            }
            const handlers = handlersRef.current.get('action_result')
            if (handlers) handlers.forEach(h => h(msg.data))
          } else if (msg.type === 'alert') {
            const handlers = handlersRef.current.get('alert')
            if (handlers) handlers.forEach(h => h(msg.data))
          }
        } catch {}
      }

      ws.onclose = () => {
        if (!mounted) return
        setStatus('reconnecting')
        reconnectTimer = setTimeout(() => {
          retryRef.current = Math.min(retryRef.current * 1.5, 30000)
          connect()
        }, retryRef.current)
      }

      ws.onerror = () => {}
    }

    connect()

    return () => {
      mounted = false
      clearTimeout(reconnectTimer)
      wsRef.current?.close()
    }
  }, [send])

  const ctx = { status, subscribe, unsubscribe, on, action, send }

  return <WsContext.Provider value={ctx}>{children}</WsContext.Provider>
}

export function useWs() {
  return useContext(WsContext)
}
