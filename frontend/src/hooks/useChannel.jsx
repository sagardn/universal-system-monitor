import { useEffect, useState, useRef, useCallback } from 'react'
import { useWs } from './useWebSocket'

/**
 * Subscribe to a WS channel and get reactive data.
 * Automatically subscribes on mount and retries if WS reconnects.
 */
export function useChannel(channel) {
  const ws = useWs()
  const [data, setData] = useState(null)
  const [ts, setTs] = useState(null)

  useEffect(() => {
    if (!ws) return

    // Subscribe immediately
    ws.subscribe([channel])

    // Listen for data on this channel
    const unsub = ws.on(channel, (d, t) => {
      setData(d)
      setTs(t)
    })

    // Also re-subscribe when WS reconnects (status changes to 'connected')
    const unsubStatus = ws.on('__status__', (newStatus) => {
      if (newStatus === 'connected') {
        ws.subscribe([channel])
      }
    })

    return () => {
      unsub()
      if (unsubStatus) unsubStatus()
    }
  }, [ws, channel])

  return { data, ts, loading: data === null }
}

/**
 * Keep a rolling history of a numeric value from channel data.
 */
export function useHistory(channel, selector, maxLen = 60) {
  const ws = useWs()
  const histRef = useRef([])
  const [history, setHistory] = useState([])

  useEffect(() => {
    if (!ws) return
    ws.subscribe([channel])
    const unsub = ws.on(channel, (d) => {
      const val = selector(d)
      if (val != null) {
        histRef.current.push(val)
        if (histRef.current.length > maxLen) histRef.current.shift()
        setHistory([...histRef.current])
      }
    })
    return unsub
  }, [ws, channel, selector, maxLen])

  return history
}
