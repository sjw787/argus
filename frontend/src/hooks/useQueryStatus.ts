import { useEffect, useRef, useState, useCallback } from 'react'
import { api } from '../api/client'
import type { QueryStatusSnapshot } from '../api/client'

const TERMINAL_STATES = new Set(['SUCCEEDED', 'FAILED', 'CANCELLED'])

export interface UseQueryStatusOptions {
  executionId: string | undefined
  /** When true, skip SSE and go straight to HTTP polling (e.g. Lambda/API Gateway) */
  lambdaMode?: boolean
  onTerminal?: (snapshot: QueryStatusSnapshot) => void
}

export interface UseQueryStatusResult {
  status: QueryStatusSnapshot | null
  error: string | null
}

export function useQueryStatus({
  executionId,
  lambdaMode = false,
  onTerminal,
}: UseQueryStatusOptions): UseQueryStatusResult {
  const [status, setStatus] = useState<QueryStatusSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)

  const esRef = useRef<EventSource | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onTerminalRef = useRef(onTerminal)
  onTerminalRef.current = onTerminal

  const stopAll = useCallback(() => {
    if (esRef.current) { esRef.current.close(); esRef.current = null }
    if (pollRef.current) { clearTimeout(pollRef.current); pollRef.current = null }
  }, [])

  const startPolling = useCallback((id: string) => {
    const poll = async () => {
      try {
        const snapshot = await api.getQueryStatus(id)
        setStatus(snapshot)
        if (TERMINAL_STATES.has(snapshot.state)) {
          onTerminalRef.current?.(snapshot)
        } else {
          pollRef.current = setTimeout(poll, 2000)
        }
      } catch (e) {
        setError(String(e))
      }
    }
    poll()
  }, [])

  useEffect(() => {
    if (!executionId) return
    stopAll()
    setStatus(null)
    setError(null)

    if (lambdaMode) {
      startPolling(executionId)
      return stopAll
    }

    // Try SSE first; fall back to polling on connection error
    const es = new EventSource(`/api/v1/queries/${executionId}/stream`)
    esRef.current = es
    let sseFailed = false

    es.onerror = () => {
      if (!sseFailed) {
        sseFailed = true
        es.close()
        esRef.current = null
        startPolling(executionId)
      }
    }

    es.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string) as {
          query_execution_id: string
          state: string
          state_change_reason?: string
          error?: string
        }
        if (data.error) {
          setError(data.error)
          stopAll()
          return
        }
        const snapshot: QueryStatusSnapshot = {
          execution_id: data.query_execution_id,
          state: data.state,
          state_change_reason: data.state_change_reason,
        }
        setStatus(snapshot)
        if (TERMINAL_STATES.has(data.state)) {
          onTerminalRef.current?.(snapshot)
          es.close()
          esRef.current = null
        }
      } catch { /* ignore malformed events */ }
    }

    return stopAll
  }, [executionId, lambdaMode, startPolling, stopAll])

  return { status, error }
}
