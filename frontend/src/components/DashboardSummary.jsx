import React, { useState, useEffect } from 'react'
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, ReferenceLine
} from 'recharts'
import {
  Globe, Flame, Snowflake, CloudRain, TrendingUp, AlertTriangle, Activity, Waves
} from 'lucide-react'
import { api } from '../services/api'
import { DashboardSkeleton } from './Skeleton'
import ClimateStripes from './ClimateStripes'

const TYPE_COLORS = {
  heatwave: '#ef4444',
  cold_snap: '#3b82f6',
  precip_extreme: '#22c55e',
}

function SummaryCard({ icon: Icon, label, value, color, sub }) {
  return (
    <div className="bg-secondary/50 rounded-lg p-3">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1.5">
        <Icon className="w-3.5 h-3.5" style={color ? { color } : {}} />
        {label}
      </div>
      <div className="text-xl font-bold" style={color ? { color } : {}}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      {sub && <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  )
}

export default function DashboardSummary() {
  const [summary, setSummary] = useState(null)
  const [indices, setIndices] = useState(null)
  const [selectedIndex, setSelectedIndex] = useState('oni')
  const [indexSeries, setIndexSeries] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const loadSummary = async () => {
      try {
        const [summaryData, indicesData] = await Promise.allSettled([
          api.getSummary(),
          api.getIndices(),
        ])
        if (summaryData.status === 'fulfilled') setSummary(summaryData.value)
        if (indicesData.status === 'fulfilled') setIndices(indicesData.value)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    loadSummary()
  }, [])

  useEffect(() => {
    api.getIndexSeries(selectedIndex, { limit: 600 })
      .then(setIndexSeries)
      .catch(() => setIndexSeries(null))
  }, [selectedIndex])

  if (loading) {
    return <DashboardSkeleton />
  }

  if (error) {
    return (
      <div className="p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-destructive mx-auto mb-2" />
        <p className="text-sm text-muted-foreground">Failed to load dashboard: {error}</p>
        <p className="text-xs text-muted-foreground mt-1">Make sure the backend API is running.</p>
      </div>
    )
  }

  if (!summary) return null

  const pieData = [
    { name: 'Heatwave', value: summary.heatwave_count, color: TYPE_COLORS.heatwave },
    { name: 'Cold Snap', value: summary.cold_snap_count, color: TYPE_COLORS.cold_snap },
    { name: 'Precip Extreme', value: summary.precip_extreme_count, color: TYPE_COLORS.precip_extreme },
  ]

  const monthlyTrend = [...(summary.monthly_trend || [])].reverse().map(m => ({
    label: `${m.year}-${String(m.month).padStart(2, '0')}`,
    heatwave: m.heatwave_count,
    cold_snap: m.cold_snap_count,
    precip_extreme: m.precip_extreme_count,
    total: m.total_anomalies,
    severity: m.avg_severity ? +(m.avg_severity * 100).toFixed(1) : 0,
  }))

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-2 mb-1">
        <Activity className="w-5 h-5 text-primary" />
        <h2 className="text-base font-semibold">Global Dashboard</h2>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-2">
        <SummaryCard icon={Globe} label="Total Stations" value={summary.total_stations} />
        <SummaryCard icon={AlertTriangle} label="Total Anomalies" value={summary.total_anomalies} color="#f59e0b" />
        <SummaryCard icon={Flame} label="Heatwaves" value={summary.heatwave_count} color={TYPE_COLORS.heatwave} />
        <SummaryCard icon={Snowflake} label="Cold Snaps" value={summary.cold_snap_count} color={TYPE_COLORS.cold_snap} />
        <SummaryCard icon={CloudRain} label="Precip Extremes" value={summary.precip_extreme_count} color={TYPE_COLORS.precip_extreme} />
        <SummaryCard
          icon={TrendingUp}
          label="Avg Severity"
          value={`${(summary.avg_severity * 100).toFixed(1)}%`}
        />
      </div>

      {/* Anomaly type distribution */}
      <div>
        <h3 className="text-xs font-medium text-muted-foreground mb-2">Anomaly Distribution</h3>
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              innerRadius={45}
              outerRadius={70}
              paddingAngle={3}
              dataKey="value"
            >
              {pieData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(222,47%,10%)',
                border: '1px solid hsl(217,33%,25%)',
                borderRadius: 8,
                fontSize: 12,
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: 11 }}
              formatter={(value) => <span className="text-foreground">{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Monthly trend */}
      {monthlyTrend.length > 0 && (
        <div>
          <h3 className="text-xs font-medium text-muted-foreground mb-2">Monthly Anomaly Trend</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={monthlyTrend.slice(-60)} margin={{ top: 5, right: 5, bottom: 5, left: -15 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(217,33%,15%)" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 9, fill: 'hsl(215,20%,55%)' }}
                interval={11}
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
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Bar dataKey="heatwave" stackId="a" fill={TYPE_COLORS.heatwave} name="Heatwave" />
              <Bar dataKey="cold_snap" stackId="a" fill={TYPE_COLORS.cold_snap} name="Cold Snap" />
              <Bar dataKey="precip_extreme" stackId="a" fill={TYPE_COLORS.precip_extreme} name="Precip" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Climate Indices */}
      {indices?.indices?.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Waves className="w-3.5 h-3.5 text-primary" />
            <h3 className="text-xs font-medium text-muted-foreground">Climate Indices</h3>
          </div>
          <div className="flex flex-wrap gap-1 mb-2">
            {(indices.available || ['oni', 'nao', 'pdo', 'amo', 'iod']).map(idx => (
              <button
                key={idx}
                onClick={() => setSelectedIndex(idx)}
                className={`px-2 py-0.5 rounded text-[10px] font-medium uppercase transition-colors ${
                  selectedIndex === idx
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-secondary text-muted-foreground hover:text-foreground'
                }`}
              >
                {idx}
              </button>
            ))}
          </div>
          {indexSeries?.data?.length > 0 && (
            <ResponsiveContainer width="100%" height={140}>
              <AreaChart data={indexSeries.data} margin={{ top: 5, right: 5, bottom: 5, left: -15 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(217,33%,15%)" />
                <XAxis
                  dataKey="index_date"
                  tick={{ fontSize: 9, fill: 'hsl(215,20%,55%)' }}
                  tickFormatter={d => d?.slice(0, 7)}
                  interval={Math.max(1, Math.floor(indexSeries.data.length / 8))}
                />
                <YAxis tick={{ fontSize: 9, fill: 'hsl(215,20%,55%)' }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(222,47%,10%)',
                    border: '1px solid hsl(217,33%,25%)',
                    borderRadius: 8,
                    fontSize: 11,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  fill="hsl(217,91%,60%)"
                  fillOpacity={0.15}
                  stroke="hsl(217,91%,60%)"
                  strokeWidth={1.5}
                  name={selectedIndex.toUpperCase()}
                />
                <ReferenceLine y={0} stroke="hsl(215,20%,40%)" strokeDasharray="3 3" />
              </AreaChart>
            </ResponsiveContainer>
          )}
          <p className="text-[9px] text-muted-foreground mt-1">{indexSeries?.description || ''}</p>
        </div>
      )}

      {/* Global Warming Stripes */}
      {monthlyTrend.length > 12 && (
        <ClimateStripes
          title="Global Anomaly Stripes (Monthly)"
          data={monthlyTrend
            .filter(m => m.severity > 0)
            .map(m => ({ year: m.label, value: m.severity }))}
          unit="%"
          height={40}
        />
      )}

      {/* Top regions */}
      {summary.top_regions?.length > 0 && (
        <div>
          <h3 className="text-xs font-medium text-muted-foreground mb-2">Top Anomalous Regions</h3>
          <div className="space-y-1.5">
            {summary.top_regions.slice(0, 8).map((region, i) => (
              <div key={i} className="flex items-center justify-between bg-secondary/30 rounded px-3 py-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-muted-foreground w-4">{i + 1}</span>
                  <span className="text-sm">{region.country}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">
                    {region.anomaly_count.toLocaleString()} anomalies
                  </span>
                  <div className="w-16 h-1.5 bg-secondary rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full"
                      style={{
                        width: `${(region.anomaly_count / summary.top_regions[0].anomaly_count) * 100}%`
                      }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
