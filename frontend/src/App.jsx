import React, { useState, useCallback } from 'react'
import Header from './components/Header'
import AnomalyMap from './components/AnomalyMap'
import Sidebar from './components/Sidebar'
import StationPanel from './components/StationPanel'
import DashboardSummary from './components/DashboardSummary'
import TimeSlider from './components/TimeSlider'
import FilterBar from './components/FilterBar'

export default function App() {
  const [selectedStation, setSelectedStation] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [showDashboard, setShowDashboard] = useState(false)
  const [filters, setFilters] = useState({
    startDate: '1970-01-01',
    endDate: '2020-12-31',
    anomalyType: null,
    minSeverity: 0,
  })
  const [timeRange, setTimeRange] = useState({ start: 1970, end: 2020 })
  const [mapBounds, setMapBounds] = useState(null)

  const handleStationSelect = useCallback((station) => {
    setSelectedStation(station)
    setSidebarOpen(true)
    setShowDashboard(false)
  }, [])

  const handleCloseStation = useCallback(() => {
    setSelectedStation(null)
  }, [])

  const handleTimeChange = useCallback((start, end) => {
    setTimeRange({ start, end })
    setFilters(prev => ({
      ...prev,
      startDate: `${start}-01-01`,
      endDate: `${end}-12-31`,
    }))
  }, [])

  const handleFilterChange = useCallback((newFilters) => {
    setFilters(prev => ({ ...prev, ...newFilters }))
  }, [])

  const handleBoundsChange = useCallback((bounds) => {
    setMapBounds(bounds)
  }, [])

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        onToggleDashboard={() => setShowDashboard(!showDashboard)}
        showDashboard={showDashboard}
      />

      <div className="flex-1 flex overflow-hidden relative">
        {/* Sidebar */}
        {sidebarOpen && (
          <Sidebar
            selectedStation={selectedStation}
            onClose={() => setSidebarOpen(false)}
          >
            {selectedStation ? (
              <StationPanel
                stationId={selectedStation.station_id || selectedStation.id}
                stationData={selectedStation}
                onClose={handleCloseStation}
              />
            ) : showDashboard ? (
              <DashboardSummary />
            ) : (
              <div className="p-4 text-muted-foreground text-sm">
                <p className="mb-3">Click a station on the map to view details, or open the dashboard for global statistics.</p>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-heatwave" />
                    <span>Heatwave</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-coldsnap" />
                    <span>Cold Snap</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-precip" />
                    <span>Precipitation Extreme</span>
                  </div>
                </div>
              </div>
            )}
          </Sidebar>
        )}

        {/* Map */}
        <div className="flex-1 relative">
          <AnomalyMap
            filters={filters}
            timeRange={timeRange}
            onStationSelect={handleStationSelect}
            onBoundsChange={handleBoundsChange}
          />

          {/* Filter bar overlay */}
          <div className="absolute top-3 left-3 right-3 z-10">
            <FilterBar
              filters={filters}
              onFilterChange={handleFilterChange}
            />
          </div>

          {/* Time slider overlay */}
          <div className="absolute bottom-6 left-16 right-16 z-10">
            <TimeSlider
              startYear={1970}
              endYear={2020}
              value={timeRange}
              onChange={handleTimeChange}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
