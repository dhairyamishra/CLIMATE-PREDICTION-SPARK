import React, { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine
} from 'recharts'
import {
  MapPin, Thermometer, CloudRain, Mountain, Calendar, TrendingUp,
  AlertTriangle, ChevronDown, ChevronUp, X
} from 'lucide-react'
import { api } from '../services/api'
import { StationPanelSkeleton } from './Skeleton'

const SEVERITY_COLORS = {
  heatwave: '#ef4444',
  cold_snap: '#3b82f6',
  precip_extreme: '#22c55e',
}

function StatCard({ icon: Icon, label, value, sub, color }) {
  return (
    <div className="bg-secondary/50 rounded-lg p-3">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
        <Icon className="w-3.5 h-3.5" style={color ? { color } : {}} />
        {label}
      </div>
      <div className="text-lg font-semibold" style={color ? { color } : {}}>
        {value}
      </div>
      {sub && <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  )
}

function AnomalyBadge({ type, severity }) {
  const color = SEVERITY_COLORS[type] || '#888'
  const label = (type || '').replace('_', ' ')
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium capitalize"
      style={{ backgroundColor: `${color}20`, color, border: `1px solid ${color}40` }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
      {label}
      <span className="opacity-70">{(severity * 100).toFixed(0)}%</span>
    </span>
  )
}

export default function StationPanel({ stationId, stationData, onClose }) {
  const [station, setStation] = useState(stationData)
  const [timeSeries, setTimeSeries] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('timeseries')
  const [tsResolution, setTsResolution] = useState('monthly')
  const [showAllAnomalies, setShowAllAnomalies] = useState(false)

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      try {
        const [stationDetail, tsData, forecastData] = await Promise.allSettled([
          api.getStation(stationId),
          api.getTimeSeries(stationId, { resolution: tsResolution, limit: 5000 }),
          api.getStationForecast(stationId),
        ])

        if (stationDetail.status === 'fulfilled') setStation(stationDetail.value)
        if (tsData.status === 'fulfilled') setTimeSeries(tsData.value)
        if (forecastData.status === 'fulfilled') setForecast(forecastData.value)
      } catch (err) {
        console.error('Error loading station data:', err)
      } finally {
        setLoading(false)
      }
    }

    if (stationId) loadData()
  }, [stationId, tsResolution])

  if (loading && !station) {
    return <StationPanelSkeleton />
  }

  const anomalies = station?.recent_anomalies || []
  const displayedAnomalies = showAllAnomalies ? anomalies : anomalies.slice(0, 5)

  const tsData = useMemo(() => {
    if (!timeSeries?.data) return []
    return [...timeSeries.data].reverse().map(d => ({ ...d, date: d.obs_date }))
  }, [timeSeries])

  const forecastData = forecast?.forecasts
  const forecastTmax = useMemo(() => forecastData?.tmax || [], [forecastData])
  const forecastTmin = useMemo(() => forecastData?.tmin || [], [forecastData])
  const forecastPrcp = useMemo(() => forecastData?.prcp || [], [forecastData])

  return (
    <div className="flex flex-col">
      {/* Station header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-start justify-between mb-2">
          <div>
            <h3 className="font-semibold text-base">
              {station?.name || stationId}
            </h3>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-1">
              <MapPin className="w-3 h-3" />
              {station?.latitude?.toFixed(4)}°, {station?.longitude?.toFixed(4)}°
              {station?.country && <span className="ml-1">· {station.country}</span>}
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-secondary transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Quick stats */}
        <div className="grid grid-cols-3 gap-2 mt-3">
          <StatCard
            icon={Mountain}
            label="Elevation"
            value={station?.elevation ? `${station.elevation}m` : 'N/A'}
          />
          <StatCard
            icon={Calendar}
            label="Record Span"
            value={station?.first_year && station?.last_year
              ? `${station.last_year - station.first_year}yr`
              : 'N/A'}
            sub={station?.first_year ? `${station.first_year}–${station.last_year}` : ''}
          />
          <StatCard
            icon={AlertTriangle}
            label="Anomalies"
            value={anomalies.length}
            color="#f59e0b"
          />
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex border-b border-border">
        {[
          { key: 'timeseries', label: 'Time Series' },
          { key: 'forecast', label: 'Forecast' },
          { key: 'anomalies', label: `Anomalies (${anomalies.length})` },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 px-3 py-2.5 text-xs font-medium transition-colors ${
              activeTab === tab.key
                ? 'text-primary border-b-2 border-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-4">
        {activeTab === 'timeseries' && (
          <div>
            {/* Resolution selector */}
            <div className="flex gap-1 mb-3">
              {['daily', 'monthly', 'yearly'].map(res => (
                <button
                  key={res}
                  onClick={() => setTsResolution(res)}
                  className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                    tsResolution === res
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {res.charAt(0).toUpperCase() + res.slice(1)}
                </button>
              ))}
            </div>

            {tsData.length > 0 ? (
              <>
                {/* Temperature chart */}
                <div className="mb-4">
                  <h4 className="text-xs font-medium text-muted-foreground mb-2">Temperature (°C)</h4>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={tsData} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(217,33%,15%)" />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'hsl(215,20%,55%)' }} tickFormatter={d => d?.slice(0, 7)} />
                      <YAxis tick={{ fontSize: 10, fill: 'hsl(215,20%,55%)' }} />
                      <Tooltip
                        contentStyle={{ backgroundColor: 'hsl(222,47%,10%)', border: '1px solid hsl(217,33%,25%)', borderRadius: 8, fontSize: 12 }}
                        labelStyle={{ color: 'hsl(210,40%,96%)' }}
                      />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line type="monotone" dataKey="tmax" stroke="#ef4444" dot={false} strokeWidth={1.5} name="T-Max" />
                      <Line type="monotone" dataKey="tmin" stroke="#3b82f6" dot={false} strokeWidth={1.5} name="T-Min" />
                      {tsData[0]?.tmax_rolling_30d !== undefined && (
                        <Line type="monotone" dataKey="tmax_rolling_30d" stroke="#fbbf24" dot={false} strokeWidth={1} strokeDasharray="4 2" name="30d Avg" />
                      )}
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Precipitation chart */}
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-2">Precipitation (mm)</h4>
                  <ResponsiveContainer width="100%" height={150}>
                    <AreaChart data={tsData} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(217,33%,15%)" />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'hsl(215,20%,55%)' }} tickFormatter={d => d?.slice(0, 7)} />
                      <YAxis tick={{ fontSize: 10, fill: 'hsl(215,20%,55%)' }} />
                      <Tooltip
                        contentStyle={{ backgroundColor: 'hsl(222,47%,10%)', border: '1px solid hsl(217,33%,25%)', borderRadius: 8, fontSize: 12 }}
                      />
                      <Area type="monotone" dataKey="prcp" fill="#22c55e30" stroke="#22c55e" strokeWidth={1.5} name="Precipitation" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </>
            ) : (
              <div className="text-sm text-muted-foreground text-center py-8">
                {loading ? 'Loading time series...' : 'No time series data available'}
              </div>
            )}
          </div>
        )}

        {activeTab === 'forecast' && (
          <div>
            {forecastTmax.length > 0 || forecastTmin.length > 0 ? (
              <>
                <h4 className="text-xs font-medium text-muted-foreground mb-2">Temperature Forecast (°C)</h4>
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart
                    data={forecastTmax.map((d, i) => ({
                      date: d.forecast_date,
                      tmax: d.predicted_value,
                      tmax_upper: d.upper_bound,
                      tmax_lower: d.lower_bound,
                      tmin: forecastTmin[i]?.predicted_value,
                      tmin_upper: forecastTmin[i]?.upper_bound,
                      tmin_lower: forecastTmin[i]?.lower_bound,
                    }))}
                    margin={{ top: 5, right: 5, bottom: 5, left: -10 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(217,33%,15%)" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'hsl(215,20%,55%)' }} tickFormatter={d => d?.slice(0, 7)} />
                    <YAxis tick={{ fontSize: 10, fill: 'hsl(215,20%,55%)' }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: 'hsl(222,47%,10%)', border: '1px solid hsl(217,33%,25%)', borderRadius: 8, fontSize: 12 }}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Area type="monotone" dataKey="tmax_upper" fill="#ef444420" stroke="none" name="T-Max CI" />
                    <Area type="monotone" dataKey="tmax_lower" fill="#ef444420" stroke="none" />
                    <Line type="monotone" dataKey="tmax" stroke="#ef4444" strokeWidth={2} dot={false} name="T-Max Forecast" />
                    <Area type="monotone" dataKey="tmin_upper" fill="#3b82f620" stroke="none" name="T-Min CI" />
                    <Area type="monotone" dataKey="tmin_lower" fill="#3b82f620" stroke="none" />
                    <Line type="monotone" dataKey="tmin" stroke="#3b82f6" strokeWidth={2} dot={false} name="T-Min Forecast" />
                  </AreaChart>
                </ResponsiveContainer>

                {forecastPrcp.length > 0 && (
                  <div className="mt-4">
                    <h4 className="text-xs font-medium text-muted-foreground mb-2">Precipitation Forecast (mm)</h4>
                    <ResponsiveContainer width="100%" height={150}>
                      <AreaChart
                        data={forecastPrcp.map(d => ({
                          date: d.forecast_date,
                          prcp: d.predicted_value,
                          upper: d.upper_bound,
                          lower: d.lower_bound,
                        }))}
                        margin={{ top: 5, right: 5, bottom: 5, left: -10 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(217,33%,15%)" />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'hsl(215,20%,55%)' }} />
                        <YAxis tick={{ fontSize: 10, fill: 'hsl(215,20%,55%)' }} />
                        <Tooltip
                          contentStyle={{ backgroundColor: 'hsl(222,47%,10%)', border: '1px solid hsl(217,33%,25%)', borderRadius: 8, fontSize: 12 }}
                        />
                        <Area type="monotone" dataKey="upper" fill="#22c55e15" stroke="none" />
                        <Area type="monotone" dataKey="lower" fill="#22c55e15" stroke="none" />
                        <Area type="monotone" dataKey="prcp" fill="#22c55e30" stroke="#22c55e" strokeWidth={2} name="Precip Forecast" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Model metrics */}
                {forecastTmax[0]?.mae && (
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <div className="bg-secondary/50 rounded p-2 text-xs">
                      <span className="text-muted-foreground">MAE: </span>
                      <span className="font-mono">{forecastTmax[0].mae.toFixed(3)}°C</span>
                    </div>
                    <div className="bg-secondary/50 rounded p-2 text-xs">
                      <span className="text-muted-foreground">Model: </span>
                      <span className="capitalize">{forecastTmax[0].model_type}</span>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-sm text-muted-foreground text-center py-8">
                {loading ? 'Loading forecasts...' : 'No forecast data available for this station'}
              </div>
            )}
          </div>
        )}

        {activeTab === 'anomalies' && (
          <div>
            {anomalies.length > 0 ? (
              <>
                <div className="space-y-2">
                  {displayedAnomalies.map((a, i) => (
                    <div
                      key={a.id || i}
                      className="bg-secondary/30 rounded-lg p-3 border border-border/50"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <AnomalyBadge type={a.anomaly_type} severity={a.severity} />
                        <span className="text-xs text-muted-foreground">{a.anomaly_date}</span>
                      </div>
                      {a.description && (
                        <p className="text-xs text-muted-foreground mt-1">{a.description}</p>
                      )}
                      <div className="flex gap-3 mt-1.5 text-xs text-muted-foreground">
                        {a.duration_days > 1 && <span>{a.duration_days} days</span>}
                        {a.temp_deviation && <span>Δ{a.temp_deviation > 0 ? '+' : ''}{a.temp_deviation.toFixed(1)}σ temp</span>}
                        {a.precip_deviation && <span>Δ+{a.precip_deviation.toFixed(1)}σ precip</span>}
                      </div>
                    </div>
                  ))}
                </div>

                {anomalies.length > 5 && (
                  <button
                    onClick={() => setShowAllAnomalies(!showAllAnomalies)}
                    className="flex items-center gap-1 mt-3 text-xs text-primary hover:underline mx-auto"
                  >
                    {showAllAnomalies ? (
                      <><ChevronUp className="w-3.5 h-3.5" /> Show less</>
                    ) : (
                      <><ChevronDown className="w-3.5 h-3.5" /> Show all {anomalies.length} anomalies</>
                    )}
                  </button>
                )}
              </>
            ) : (
              <div className="text-sm text-muted-foreground text-center py-8">
                No anomalies detected for this station
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
