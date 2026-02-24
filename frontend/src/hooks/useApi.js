import { useState, useEffect, useCallback, useRef } from 'react'

export function useApi(fetchFn, deps = [], options = {}) {
  const { immediate = true, initialData = null } = options
  const [data, setData] = useState(initialData)
  const [loading, setLoading] = useState(immediate)
  const [error, setError] = useState(null)
  const abortRef = useRef(null)

  const execute = useCallback(async (...args) => {
    if (abortRef.current) {
      abortRef.current.abort()
    }
    abortRef.current = new AbortController()

    setLoading(true)
    setError(null)

    try {
      const result = await fetchFn(...args)
      setData(result)
      return result
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message)
      }
      return null
    } finally {
      setLoading(false)
    }
  }, [fetchFn])

  useEffect(() => {
    if (immediate) {
      execute()
    }
    return () => {
      if (abortRef.current) {
        abortRef.current.abort()
      }
    }
  }, deps)

  return { data, loading, error, execute, setData }
}

export function useDebounce(value, delay = 300) {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debouncedValue
}
