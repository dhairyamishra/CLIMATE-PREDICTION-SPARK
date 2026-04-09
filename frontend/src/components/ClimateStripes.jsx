import React, { useMemo } from 'react'

const BLUE_TO_RED = [
  '#08306b', '#08519c', '#2171b5', '#4292c6', '#6baed6',
  '#9ecae1', '#c6dbef', '#deebf7', '#fee0d2', '#fcbba1',
  '#fc9272', '#fb6a4a', '#ef3b2c', '#cb181d', '#a50f15', '#67000d',
]

function valueToColor(value, min, max) {
  if (value == null) return '#1a1a2e'
  const t = Math.max(0, Math.min(1, (value - min) / (max - min || 1)))
  const idx = Math.round(t * (BLUE_TO_RED.length - 1))
  return BLUE_TO_RED[idx]
}

export default function ClimateStripes({ data, title, unit = '°C', height = 60 }) {
  const { stripes, min, max, years } = useMemo(() => {
    if (!data || data.length === 0) return { stripes: [], min: 0, max: 0, years: [] }

    const vals = data.map(d => d.value).filter(v => v != null)
    const mn = Math.min(...vals)
    const mx = Math.max(...vals)
    const yrs = data.map(d => d.year || d.label)

    return {
      stripes: data.map(d => ({
        color: valueToColor(d.value, mn, mx),
        year: d.year || d.label,
        value: d.value,
      })),
      min: mn,
      max: mx,
      years: yrs,
    }
  }, [data])

  if (stripes.length === 0) return null

  const barWidth = Math.max(2, Math.min(8, 280 / stripes.length))

  return (
    <div>
      {title && (
        <h4 className="text-xs font-medium text-muted-foreground mb-1.5">{title}</h4>
      )}
      <div className="relative" style={{ height }}>
        <div className="flex h-full gap-px rounded overflow-hidden">
          {stripes.map((s, i) => (
            <div
              key={i}
              className="flex-1 min-w-0 group relative"
              style={{ backgroundColor: s.color, minWidth: barWidth }}
              title={`${s.year}: ${s.value != null ? s.value.toFixed(1) : 'N/A'}${unit}`}
            />
          ))}
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-[9px] text-muted-foreground">{years[0]}</span>
          {years.length > 20 && (
            <span className="text-[9px] text-muted-foreground">
              {years[Math.floor(years.length / 2)]}
            </span>
          )}
          <span className="text-[9px] text-muted-foreground">{years[years.length - 1]}</span>
        </div>
      </div>
      <div className="flex items-center justify-between mt-1">
        <div className="flex items-center gap-1">
          <div
            className="w-3 h-2 rounded-sm"
            style={{ background: `linear-gradient(to right, ${BLUE_TO_RED[0]}, ${BLUE_TO_RED[BLUE_TO_RED.length - 1]})` }}
          />
          <span className="text-[9px] text-muted-foreground">
            {min.toFixed(1)} to {max.toFixed(1)}{unit}
          </span>
        </div>
      </div>
    </div>
  )
}
