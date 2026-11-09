import { useCallback, useEffect, useRef, useState } from 'react'
import { api, clean, errorMessage } from '../api/client.js'

/** GET helper with loading / error state. Re-fetches when url or params change; ignores stale responses. */
export function useGet(url, params, { enabled = true } = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState(null)
  const seq = useRef(0)
  const key = JSON.stringify(params || {})

  const load = useCallback(() => {
    if (!enabled || !url) return Promise.resolve()
    const id = ++seq.current
    setLoading(true)
    setError(null)
    return api.get(url, { params: clean(JSON.parse(key)) })
      .then((r) => { if (id === seq.current) setData(r.data) })
      .catch((e) => { if (id === seq.current) { setError(errorMessage(e)); setData(null) } })
      .finally(() => { if (id === seq.current) setLoading(false) })
  }, [url, key, enabled])

  useEffect(() => { load() }, [load])
  return { data, loading, error, reload: load }
}

/** Imperative request (POST/PATCH/...) with its own busy + error state. */
export function useAction() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const run = useCallback(async (fn) => {
    setBusy(true)
    setError(null)
    try { return await fn(api) } catch (e) { setError(errorMessage(e)); return null } finally { setBusy(false) }
  }, [])
  return { busy, error, run, setError }
}
