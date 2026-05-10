import { useState, useEffect, useCallback } from 'react'

export function usePolling(fetchFn, interval = 30000) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  const fetch = useCallback(async () => {
    try {
      const res = await fetchFn()
      setData(res.data)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [fetchFn])

  useEffect(() => {
    fetch()
    const id = setInterval(fetch, interval)
    return () => clearInterval(id)
  }, [fetch, interval])

  return { data, loading, error, refetch: fetch }
}