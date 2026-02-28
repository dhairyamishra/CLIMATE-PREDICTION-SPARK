import React from 'react'
import { Filter, Flame, Snowflake, CloudRain, X } from 'lucide-react'

const ANOMALY_TYPES = [
  { key: 'heatwave', label: 'Heatwave', icon: Flame, color: 'text-heatwave', bg: 'bg-heatwave/20 border-heatwave/40' },
  { key: 'cold_snap', label: 'Cold Snap', icon: Snowflake, color: 'text-coldsnap', bg: 'bg-coldsnap/20 border-coldsnap/40' },
  { key: 'precip_extreme', label: 'Precip Extreme', icon: CloudRain, color: 'text-precip', bg: 'bg-precip/20 border-precip/40' },
]

export default function FilterBar({ filters, onFilterChange }) {
  const handleTypeToggle = (type) => {
    onFilterChange({
      anomalyType: filters.anomalyType === type ? null : type,
    })
  }

  const handleSeverityChange = (e) => {
    onFilterChange({ minSeverity: parseFloat(e.target.value) })
  }

  const clearFilters = () => {
    onFilterChange({
      anomalyType: null,
      minSeverity: 0,
    })
  }

  const hasActiveFilters = filters.anomalyType || filters.minSeverity > 0

  return (
    <div className="flex items-center gap-2 flex-wrap" role="toolbar" aria-label="Map filters">
      {/* Anomaly type pills */}
      <div className="flex items-center gap-1.5 bg-card/95 backdrop-blur-sm border border-border rounded-lg px-3 py-1.5 shadow-lg" role="group" aria-label="Anomaly type filter">
        <Filter className="w-4 h-4 text-muted-foreground mr-1" aria-hidden="true" />

        {ANOMALY_TYPES.map(({ key, label, icon: Icon, color, bg }) => (
          <button
            key={key}
            onClick={() => handleTypeToggle(key)}
            aria-pressed={filters.anomalyType === key}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all border ${
              filters.anomalyType === key
                ? `${bg} ${color}`
                : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-secondary'
            }`}
          >
            <Icon className="w-3.5 h-3.5" aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>

      {/* Severity slider */}
      <div className="flex items-center gap-2 bg-card/95 backdrop-blur-sm border border-border rounded-lg px-3 py-1.5 shadow-lg">
        <label htmlFor="severity-slider" className="text-xs text-muted-foreground whitespace-nowrap">Min Severity:</label>
        <input
          id="severity-slider"
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={filters.minSeverity}
          onChange={handleSeverityChange}
          aria-valuenow={filters.minSeverity}
          aria-valuemin={0}
          aria-valuemax={1}
          aria-label="Minimum severity threshold"
          className="w-24 h-1.5 appearance-none bg-secondary rounded-full cursor-pointer
            [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3
            [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:rounded-full"
        />
        <span className="text-xs font-mono text-foreground w-8" aria-live="polite">
          {(filters.minSeverity * 100).toFixed(0)}%
        </span>
      </div>

      {/* Clear filters */}
      {hasActiveFilters && (
        <button
          onClick={clearFilters}
          className="flex items-center gap-1 bg-card/95 backdrop-blur-sm border border-border rounded-lg px-3 py-1.5 shadow-lg text-xs text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Clear all filters"
        >
          <X className="w-3.5 h-3.5" aria-hidden="true" />
          Clear
        </button>
      )}
    </div>
  )
}
