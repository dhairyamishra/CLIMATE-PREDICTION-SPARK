import React, { useState, useEffect, useMemo } from 'react'
import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts'
import { TrendingUp } from 'lucide-react'
import { api } from '../services/api'

const SCENARIO_COLORS = {
  ssp126: '#22c55e',
  ssp245: '#f59e0b',
  ssp370: '#f97316',
  ssp585: '#ef4444',
}

const SCENARIO_LABELS = {
  ssp126: 'SSP1-2.6 (Low)',
  ssp245: 'SSP2-4.5 (Mid)',
  ssp370: 'SSP3-7.0 (High)',
  ssp585: 'SSP5-8.5 (Very High)',
}

export default function ProjectionChart({ stationId }) {
  const [projections, setProjections] = useState({})
  const [loading, setLoading] = useState(true)
  const [variable, setVariable] = useState('tmax')
  const [selectedScenarios, setSelectedScenarios] = useState(['ssp126', 'ssp245', 'ssp585'])

  useEffect(() => {
    if (!stationId) return
    setLoading(true)

    const loadAll = async () => {
      const results = {}
      for (const scenario of ['ssp126', 'ssp245', 'ssp370', 'ssp585']) {
        try {
          const data = await api.getStationProjections(stationId, { scenario, variable })
          results[scenario] = data.projections?.[variable] || []
        } catch {
          results[scenario] = []
        }
      }
      setProjections(results)
      setLoading(false)
    }

    loadAll()
  }, [stationId, variable])

  const chartData = useMemo(() => {
    const dateMap = {}

    Object.entries(projections).forEach(([scenario, points]) => {
      if (!selectedScenarios.includes(scenario)) return
      points.forEach(p => {
        const year = p.projection_date?.slice(0, 4)
        if (!year) return
        if (!dateMap[year]) dateMap[year] = { year }
        dateMap[year][`${scenario}_val`] = p.predicted_value
        dateMap[year][`${scenario}_upper`] = p.upper_bound
        dateMap[year][`${scenario}_lower`] = p.lower_bound
      })
    })

    return Object.values(dateMap).sort((a, b) => a.year.localeCompare(b.year))
  }, [projections, selectedScenarios])

  const toggleScenario = (s) => {
    setSelectedScenarios(prev =>
      prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
    )
  }

  const hasData = chartData.length > 0

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp className="w-4 h-4 text-primary" />
        <h4 className="text-xs font-medium text-muted-foreground">Climate Projections (2025-2100)</h4>
      </div>

      <div className="flex gap-1 mb-2">
        {['tmax', 'tmin', 'prcp'].map(v => (
          <button
            key={v}
            onClick={() => setVariable(v)}
            className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
              variable === v
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-muted-foreground hover:text-foreground'
            }`}
          >
            {v === 'tmax' ? 'T-Max' : v === 'tmin' ? 'T-Min' : 'Precip'}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-1 mb-2">
        {Object.entries(SCENARIO_LABELS).map(([key, label]) => (
          <button
            key={key}
            onClick={() => toggleScenario(key)}
            className={`px-1.5 py-0.5 rounded text-[9px] font-medium transition-colors border ${
              selectedScenarios.includes(key)
                ? 'border-current'
                : 'border-transparent opacity-40'
            }`}
            style={{ color: SCENARIO_COLORS[key] }}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-xs text-muted-foreground text-center py-6">Loading projections...</div>
      ) : hasData ? (
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(217,33%,15%)" />
            <XAxis
              dataKey="year"
              tick={{ fontSize: 9, fill: 'hsl(215,20%,55%)' }}
              interval={3}
            />
            <YAxis tick={{ fontSize: 10, fill: 'hsl(215,20%,55%)' }} />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(222,47%,10%)',
                border: '1px solid hsl(217,33%,25%)',
                borderRadius: 8,
                fontSize: 11,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 9 }} />
            {selectedScenarios.map(s => (
              <React.Fragment key={s}>
                <Area
                  type="monotone"
                  dataKey={`${s}_upper`}
                  stroke="none"
                  fill={`${SCENARIO_COLORS[s]}15`}
                  stackId={`ci-${s}`}
                />
                <Area
                  type="monotone"
                  dataKey={`${s}_lower`}
                  stroke="none"
                  fill={`${SCENARIO_COLORS[s]}15`}
                  stackId={`ci-${s}`}
                />
                <Line
                  type="monotone"
                  dataKey={`${s}_val`}
                  stroke={SCENARIO_COLORS[s]}
                  dot={false}
                  strokeWidth={1.5}
                  name={SCENARIO_LABELS[s]}
                />
              </React.Fragment>
            ))}
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        <div className="text-xs text-muted-foreground text-center py-6">
          No projection data available
        </div>
      )}
    </div>
  )
}
