const API_BASE = '/api'

const RETRY_DELAYS = [0, 1000, 3000]

async function fetchJSON(url, options = {}) {
  const { retries = RETRY_DELAYS.length, signal } = options
  let lastError

  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      if (attempt > 0) {
        await new Promise(r => setTimeout(r, RETRY_DELAYS[attempt] || 3000))
      }

      const response = await fetch(`${API_BASE}${url}`, {
        headers: { 'Content-Type': 'application/json' },
        signal,
      })

      if (!response.ok) {
        const isRetryable = response.status >= 500 || response.status === 429
        const msg = `${response.status} ${response.statusText}`
        if (!isRetryable || attempt === retries - 1) {
          throw new Error(msg)
        }
        lastError = new Error(msg)
        continue
      }

      return response.json()
    } catch (err) {
      if (err.name === 'AbortError') throw err
      lastError = err
      if (attempt === retries - 1) throw lastError
    }
  }

  throw lastError
}

export const api = {
  // Anomalies
  getAnomalies: (params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        query.append(key, value)
      }
    })
    return fetchJSON(`/anomalies?${query}`)
  },

  // Stations
  getStations: (params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        query.append(key, value)
      }
    })
    return fetchJSON(`/stations?${query}`)
  },

  getStation: (stationId) => fetchJSON(`/stations/${stationId}`),

  // Forecasts
  getStationForecast: (stationId, params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined) {
        query.append(key, value)
      }
    })
    return fetchJSON(`/stations/${stationId}/forecast?${query}`)
  },

  // Tiles
  getTiles: (params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined) {
        query.append(key, value)
      }
    })
    return fetchJSON(`/tiles?${query}`)
  },

  // Time series
  getTimeSeries: (stationId, params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined) {
        query.append(key, value)
      }
    })
    return fetchJSON(`/timeseries/${stationId}?${query}`)
  },

  // Summary
  getSummary: () => fetchJSON('/summary'),

  // Climate indices
  getIndices: () => fetchJSON('/indices'),
  getIndexSeries: (indexName, params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined) query.append(key, value)
    })
    return fetchJSON(`/indices/${indexName}?${query}`)
  },

  // Extreme value stats
  getStationExtremes: (stationId, params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined) query.append(key, value)
    })
    return fetchJSON(`/stations/${stationId}/extremes?${query}`)
  },

  // Trend analysis
  getStationTrends: (stationId, params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined) query.append(key, value)
    })
    return fetchJSON(`/stations/${stationId}/trends?${query}`)
  },

  // Climate projections
  getStationProjections: (stationId, params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined) query.append(key, value)
    })
    return fetchJSON(`/stations/${stationId}/projections?${query}`)
  },
  getProjectionScenarios: () => fetchJSON('/projections/scenarios'),

  // Data export
  exportTimeSeries: (stationId, format = 'csv') =>
    fetchJSON(`/export/timeseries/${stationId}?format=${format}`),
  // Wind data
  getWind: (params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined) query.append(key, value)
    })
    return fetchJSON(`/wind?${query}`)
  },

  exportAnomalies: (params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined) query.append(key, value)
    })
    return fetchJSON(`/export/anomalies?${query}`)
  },
}
