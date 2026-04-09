import React, { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer
} from 'recharts'
import { GitCompare, X, Search } from 'lucide-react'
import { api } from '../services/api'

const COLORS = ['#ef4444', '#3b82f6', '#22c55e', '#f59e0b']

export default function ComparisonView({ stationA, onClose }) {
  const [stationBId, setStationBId] = useState('')
  const [stationB, setStationB] = useState(null)
  const [dataA, setDataA] = useState(null)
  const [dataB, setDataB] = useState(null)
  const [loading, setLoading] = useState(false)
  const [variable, setVariable] = useState('tmax')

  useEffect(() => {
    if (!stationA?.id && !stationA?.station_id) return
    const id = stationA.station_id || stationA.id
    api.getTimeSeries(id, { resolution: 'yearly', limit: 200 })
      .then(setDataA)
      .catch(() => {})
  }, [stationA])

  const handleCompare = async () => {
    if (!stationBId.trim()) return
    setLoading(true)
    try {
      const [detail, ts] = await Promise.all([
        api.getStation(stationBId.trim()),
        api.getTimeSeries(stationBId.trim(), { resolution: 'yearly', limit: 200 }),
      ])
      setStationB(detail)
      setDataB(ts)
    } catch {
      setStationB(null)
      setDataB(null)
    } finally {
      setLoading(false)
    }
  }

  const chartData = useMemo(() => {
    if (!dataA?.data) return []

    const mapA = {}
    dataA.data.forEach(d => { mapA[d.obs_date] = d })

    const mapB = {}
    if (dataB?.data) {
      dataB.data.forEach(d => { mapB[d.obs_date] = d })
    }

    const allDates = new Set([...Object.keys(mapA), ...Object.keys(mapB)])
    return Array.from(allDates).sort().map(date => ({
      date,
      stationA: mapA[date]?.[variable],
      stationB: mapB[date]?.[variable],
    }))
  }, [dataA, dataB, variable])

  const nameA = stationA?.name || stationA?.station_id || 'Station A'
  const nameB = stationB?.name || stationBId || 'Station B'

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitCompare className="w-5 h-5 text-primary" />
          <h2 className="text-base font-semibold">Station Comparison</h2>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-secondary">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="bg-secondary/30 rounded-lg p-3 text-sm">
        <div className="text-xs text-muted-foreground mb-1">Station A</div>
        <div className="font-medium">{nameA}</div>
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={stationBId}
          onChange={e => setStationBId(e.target.value)}
          placeholder="Enter Station B ID..."
          className="flex-1 bg-secondary/50 border border-border rounded px-3 py-1.5 text-sm
            placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          onKeyDown={e => e.key === 'Enter' && handleCompare()}
        />
        <button
          onClick={handleCompare}
          disabled={loading}
          className="px-3 py-1.5 bg-primary text-primary-foreground rounded text-sm font-medium
            hover:bg-primary/90 disabled:opacity-50"
        >
          <Search className="w-4 h-4" />
        </button>
      </div>

      <div className="flex gap-1">
        {['tmax', 'tmin', 'prcp'].map(v => (
          <button
            key={v}
            onClick={() => setVariable(v)}
            className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
              variable === v
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-muted-foreground hover:text-foreground'
            }`}
          >
            {v === 'tmax' ? 'T-Max' : v === 'tmin' ? 'T-Min' : 'Precip'}
          </button>
        ))}
      </div>

      {chartData.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-muted-foreground mb-2">
            {variable === 'prcp' ? 'Precipitation (mm)' : 'Temperature (°C)'} — Yearly Average
          </h4>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(217,33%,15%)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: 'hsl(215,20%,55%)' }}
                tickFormatter={d => d?.slice(0, 4)}
              />
              <YAxis tick={{ fontSize: 10, fill: 'hsl(215,20%,55%)' }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(222,47%,10%)',
                  border: '1px solid hsl(217,33%,25%)',
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line
                type="monotone"
                dataKey="stationA"
                stroke={COLORS[0]}
                dot={false}
                strokeWidth={2}
                name={nameA}
              />
              {dataB && (
                <Line
                  type="monotone"
                  dataKey="stationB"
                  stroke={COLORS[1]}
                  dot={false}
                  strokeWidth={2}
                  name={nameB}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {!dataB && !loading && (
        <div className="text-sm text-muted-foreground text-center py-4">
          Enter a station ID above to compare
        </div>
      )}
    </div>
  )
}
