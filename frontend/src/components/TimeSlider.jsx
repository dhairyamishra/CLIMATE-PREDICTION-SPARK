import React, { useState, useCallback } from 'react'
import { Calendar, Play, Pause } from 'lucide-react'

export default function TimeSlider({ startYear, endYear, value, onChange }) {
  const [localStart, setLocalStart] = useState(value.start)
  const [localEnd, setLocalEnd] = useState(value.end)
  const [isDragging, setIsDragging] = useState(false)

  const totalYears = endYear - startYear

  const handleStartChange = useCallback((e) => {
    const newStart = parseInt(e.target.value)
    if (newStart < localEnd) {
      setLocalStart(newStart)
    }
  }, [localEnd])

  const handleEndChange = useCallback((e) => {
    const newEnd = parseInt(e.target.value)
    if (newEnd > localStart) {
      setLocalEnd(newEnd)
    }
  }, [localStart])

  const handleCommit = useCallback(() => {
    setIsDragging(false)
    onChange(localStart, localEnd)
  }, [localStart, localEnd, onChange])

  const decades = []
  for (let y = Math.ceil(startYear / 10) * 10; y <= endYear; y += 10) {
    decades.push(y)
  }

  return (
    <div className="bg-card/95 backdrop-blur-sm border border-border rounded-lg px-5 py-3 shadow-lg">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Calendar className="w-4 h-4" />
          <span>Historical Time Range</span>
        </div>
        <div className="text-sm font-semibold text-primary">
          {localStart} — {localEnd}
        </div>
      </div>

      {/* Dual range slider */}
      <div className="relative h-8 mb-1">
        {/* Track background */}
        <div className="absolute top-1/2 -translate-y-1/2 left-0 right-0 h-1.5 bg-secondary rounded-full" />

        {/* Active range highlight */}
        <div
          className="absolute top-1/2 -translate-y-1/2 h-1.5 bg-primary/60 rounded-full"
          style={{
            left: `${((localStart - startYear) / totalYears) * 100}%`,
            right: `${((endYear - localEnd) / totalYears) * 100}%`,
          }}
        />

        {/* Start handle */}
        <input
          type="range"
          min={startYear}
          max={endYear}
          value={localStart}
          onChange={handleStartChange}
          onMouseDown={() => setIsDragging(true)}
          onMouseUp={handleCommit}
          onTouchEnd={handleCommit}
          className="absolute inset-0 w-full appearance-none bg-transparent pointer-events-auto cursor-pointer
            [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
            [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:shadow-md
            [&::-webkit-slider-thumb]:cursor-grab [&::-webkit-slider-thumb]:active:cursor-grabbing
            [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white/30
            [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:bg-primary
            [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-white/30"
          style={{ zIndex: localStart > endYear - 5 ? 5 : 3 }}
        />

        {/* End handle */}
        <input
          type="range"
          min={startYear}
          max={endYear}
          value={localEnd}
          onChange={handleEndChange}
          onMouseDown={() => setIsDragging(true)}
          onMouseUp={handleCommit}
          onTouchEnd={handleCommit}
          className="absolute inset-0 w-full appearance-none bg-transparent pointer-events-auto cursor-pointer
            [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
            [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:shadow-md
            [&::-webkit-slider-thumb]:cursor-grab [&::-webkit-slider-thumb]:active:cursor-grabbing
            [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white/30
            [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:bg-primary
            [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-white/30"
          style={{ zIndex: 4 }}
        />
      </div>

      {/* Decade markers */}
      <div className="relative h-4">
        {decades.map(year => (
          <div
            key={year}
            className="absolute text-[10px] text-muted-foreground -translate-x-1/2"
            style={{ left: `${((year - startYear) / totalYears) * 100}%` }}
          >
            {year}
          </div>
        ))}
      </div>
    </div>
  )
}
