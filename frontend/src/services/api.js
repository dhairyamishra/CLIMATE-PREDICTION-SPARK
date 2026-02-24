const API_BASE = '/api'

async function fetchJSON(url, options = {}) {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`)
  }
  return response.json()
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
}
