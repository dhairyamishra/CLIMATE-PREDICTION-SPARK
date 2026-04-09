import React, { useState, useCallback, useRef, useEffect } from 'react'
import { Calendar, Play, Pause, SkipForward } from 'lucide-react'

export default function TimeSlider({ startYear, endYear, value, onChange }) {
  const [localStart, setLocalStart] = useState(value.start)
  const [localEnd, setLocalEnd] = useState(value.end)
  const [isDragging, setIsDragging] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playYear, setPlayYear] = useState(startYear)
  const playRef = useRef(null)

  const totalYears = endYear - startYear

  useEffect(() => {
    if (!isPlaying) {
      if (playRef.current) clearInterval(playRef.current)
      return
    }

    playRef.current = setInterval(() => {
      setPlayYear(prev => {
        const next = prev + 1
        if (next > endYear) {
          setIsPlaying(false)
          onChange(startYear, endYear)
          return startYear
        }
        onChange(prev, next)
        return next
      })
    }, 800)

    return () => { if (playRef.current) clearInterval(playRef.current) }
  }, [isPlaying, startYear, endYear, onChange])

  const togglePlay = useCallback(() => {
    if (isPlaying) {
      setIsPlaying(false)
      onChange(startYear, endYear)
    } else {
      setPlayYear(startYear)
      setIsPlaying(true)
    }
  }, [isPlaying, startYear, endYear, onChange])

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
        <div className="flex items-center gap-2">
          {isPlaying && (
            <span className="text-xs text-primary font-mono animate-pulse">{playYear}</span>
          )}
          <button
            onClick={togglePlay}
            className="p-1 rounded hover:bg-secondary transition-colors"
            title={isPlaying ? 'Stop animation' : 'Animate through years'}
          >
            {isPlaying
              ? <Pause className="w-3.5 h-3.5 text-primary" />
              : <Play className="w-3.5 h-3.5 text-muted-foreground" />
            }
          </button>
          <div className="text-sm font-semibold text-primary">
            {isPlaying ? `${playYear - 1}–${playYear}` : `${localStart} — ${localEnd}`}
          </div>
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
