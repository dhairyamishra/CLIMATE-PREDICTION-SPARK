import React, { useRef, useEffect, useState, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import { api } from '../services/api'
import { useDebounce } from '../hooks/useApi'
import { MapLoadingSkeleton } from './Skeleton'

const ANOMALY_COLORS = {
  heatwave: '#ef4444',
  cold_snap: '#3b82f6',
  precip_extreme: '#22c55e',
}

const SEVERITY_RADIUS = {
  min: 4,
  max: 20,
}

const EMPTY_FC = { type: 'FeatureCollection', features: [] }

export default function AnomalyMap({ filters, timeRange, onStationSelect, onBoundsChange, showWind = false }) {
  const mapContainer = useRef(null)
  const mapRef = useRef(null)
  const [mapReady, setMapReady] = useState(false)
  const [dataLoading, setDataLoading] = useState(false)
  const [windVisible, setWindVisible] = useState(false)
  const debouncedFilters = useDebounce(filters, 500)
  const pendingData = useRef(null)

  // Initialize map with all sources/layers inline so they exist before tiles load
  useEffect(() => {
    if (mapRef.current && mapContainer.current?.childElementCount > 0) return

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        name: 'Dark',
        sources: {
          'osm-tiles': {
            type: 'raster',
            tiles: [
              'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
              'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
              'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
            ],
            tileSize: 256,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
          },
          'anomaly-heatmap': {
            type: 'geojson',
            data: EMPTY_FC,
          },
          'station-points': {
            type: 'geojson',
            data: EMPTY_FC,
          },
          'wind-arrows': {
            type: 'geojson',
            data: EMPTY_FC,
          },
        },
        layers: [
          {
            id: 'osm-tiles-layer',
            type: 'raster',
            source: 'osm-tiles',
            minzoom: 0,
            maxzoom: 19,
          },
          {
            id: 'anomaly-heat',
            type: 'heatmap',
            source: 'anomaly-heatmap',
            maxzoom: 12,
            paint: {
              'heatmap-weight': ['interpolate', ['linear'], ['get', 'severity'], 0, 0, 1, 1],
              'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 12, 3],
              'heatmap-color': [
                'interpolate', ['linear'], ['heatmap-density'],
                0, 'rgba(0,0,0,0)',
                0.1, 'rgba(30,60,180,0.4)',
                0.3, 'rgba(50,150,220,0.5)',
                0.5, 'rgba(80,220,100,0.6)',
                0.7, 'rgba(255,220,50,0.7)',
                0.9, 'rgba(255,100,30,0.8)',
                1, 'rgba(220,30,30,0.9)',
              ],
              'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 8, 6, 30, 12, 50],
              'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 7, 0.8, 12, 0.3],
            },
          },
          {
            id: 'anomaly-circles',
            type: 'circle',
            source: 'anomaly-heatmap',
            minzoom: 5,
            paint: {
              'circle-radius': [
                'interpolate', ['linear'], ['get', 'severity'],
                0, SEVERITY_RADIUS.min,
                1, SEVERITY_RADIUS.max,
              ],
              'circle-color': [
                'match', ['get', 'anomaly_type'],
                'heatwave', ANOMALY_COLORS.heatwave,
                'cold_snap', ANOMALY_COLORS.cold_snap,
                'precip_extreme', ANOMALY_COLORS.precip_extreme,
                '#888888',
              ],
              'circle-opacity': 0.7,
              'circle-stroke-width': 1,
              'circle-stroke-color': 'rgba(255,255,255,0.3)',
            },
          },
          {
            id: 'stations',
            type: 'circle',
            source: 'station-points',
            minzoom: 4,
            paint: {
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 2, 8, 5, 12, 8],
              'circle-color': '#94a3b8',
              'circle-opacity': 0.6,
              'circle-stroke-width': 1,
              'circle-stroke-color': 'rgba(255,255,255,0.2)',
            },
          },
          {
            id: 'wind-particles',
            type: 'circle',
            source: 'wind-arrows',
            paint: {
              'circle-radius': ['interpolate', ['linear'], ['get', 'speed'], 0, 2, 5, 4, 15, 8],
              'circle-color': [
                'interpolate', ['linear'], ['get', 'speed'],
                0, '#6baed6',
                5, '#22c55e',
                10, '#f59e0b',
                15, '#ef4444',
              ],
              'circle-opacity': 0.6,
              'circle-stroke-width': 0.5,
              'circle-stroke-color': 'rgba(255,255,255,0.3)',
            },
            layout: {
              'visibility': 'none',
            },
          },
        ],
      },
      center: [0, 20],
      zoom: 2,
      minZoom: 1,
      maxZoom: 15,
    })

    map.addControl(new maplibregl.NavigationControl(), 'bottom-right')

    let ready = false
    const markReady = () => {
      if (ready) return
      ready = true
      setMapReady(true)
    }

    map.on('load', markReady)
    const fallbackTimer = setTimeout(markReady, 2000)

    map.on('click', 'anomaly-circles', (e) => {
      const feature = e.features[0]
      if (feature) {
        onStationSelect({
          station_id: feature.properties.station_id,
          id: feature.properties.station_id,
          name: feature.properties.station_name,
          latitude: feature.geometry.coordinates[1],
          longitude: feature.geometry.coordinates[0],
          anomaly_type: feature.properties.anomaly_type,
          severity: feature.properties.severity,
        })
      }
    })

    map.on('click', 'stations', (e) => {
      const feature = e.features[0]
      if (feature) {
        onStationSelect({
          station_id: feature.properties.id,
          id: feature.properties.id,
          name: feature.properties.name,
          latitude: feature.geometry.coordinates[1],
          longitude: feature.geometry.coordinates[0],
          country: feature.properties.country,
        })
      }
    })

    map.on('mouseenter', 'anomaly-circles', () => { map.getCanvas().style.cursor = 'pointer' })
    map.on('mouseleave', 'anomaly-circles', () => { map.getCanvas().style.cursor = '' })
    map.on('mouseenter', 'stations', () => { map.getCanvas().style.cursor = 'pointer' })
    map.on('mouseleave', 'stations', () => { map.getCanvas().style.cursor = '' })

    const popup = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
    })

    map.on('mouseenter', 'anomaly-circles', (e) => {
      const f = e.features[0]
      if (!f) return

      const coords = f.geometry.coordinates.slice()
      const props = f.properties

      popup.setLngLat(coords).setHTML(`
        <div class="text-xs">
          <div class="font-semibold mb-1">${props.station_name || props.station_id}</div>
          <div class="flex items-center gap-1 mb-0.5">
            <span class="inline-block w-2 h-2 rounded-full" style="background:${ANOMALY_COLORS[props.anomaly_type] || '#888'}"></span>
            <span class="capitalize">${(props.anomaly_type || '').replace('_', ' ')}</span>
          </div>
          <div>Severity: <strong>${(props.severity * 100).toFixed(0)}%</strong></div>
          <div>${props.anomaly_date || ''}</div>
        </div>
      `).addTo(map)
    })

    map.on('mouseleave', 'anomaly-circles', () => {
      popup.remove()
    })

    map.on('moveend', () => {
      const bounds = map.getBounds()
      onBoundsChange?.({
        min_lat: bounds.getSouth(),
        max_lat: bounds.getNorth(),
        min_lon: bounds.getWest(),
        max_lon: bounds.getEast(),
      })
    })

    mapRef.current = map

    return () => { clearTimeout(fallbackTimer); map.remove(); mapRef.current = null }
  }, [])

  // Wind layer toggle
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return

    try {
      map.setLayoutProperty('wind-particles', 'visibility', windVisible ? 'visible' : 'none')
    } catch {}

    if (!windVisible) return

    const loadWind = async () => {
      try {
        const bounds = map.getBounds()
        const windData = await api.getWind({
          min_lat: bounds.getSouth(),
          max_lat: bounds.getNorth(),
          min_lon: bounds.getWest(),
          max_lon: bounds.getEast(),
          resolution: 15,
        })

        const features = windData.vectors?.map(v => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [v.lon, v.lat] },
          properties: { speed: v.speed, direction: v.direction, u: v.u, v: v.v },
        })) || []

        const src = map.getSource('wind-arrows')
        if (src) {
          src.setData({ type: 'FeatureCollection', features })
        }
      } catch {}
    }

    loadWind()
  }, [windVisible, mapReady])

  const applyDataToMap = useCallback((anomalyData, stationData) => {
    const map = mapRef.current
    if (!map) return false

    let heatmapSrc, stationSrc
    try {
      heatmapSrc = map.getSource('anomaly-heatmap')
      stationSrc = map.getSource('station-points')
    } catch { return false }

    if (!heatmapSrc || !stationSrc) return false

    if (anomalyData?.features) {
      heatmapSrc.setData(anomalyData)
    }

    if (stationData) {
      const stationGeoJSON = {
        type: 'FeatureCollection',
        features: stationData.map(s => ({
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [s.longitude, s.latitude],
          },
          properties: {
            id: s.id,
            name: s.name,
            country: s.country,
            record_count: s.record_count,
          },
        })),
      }
      stationSrc.setData(stationGeoJSON)
    }
    return true
  }, [mapReady])

  useEffect(() => {
    let cancelled = false
    const loadData = async () => {
      setDataLoading(true)
      try {
        const [anomalyData, stationData] = await Promise.all([
          api.getAnomalies({
            start_date: debouncedFilters.startDate,
            end_date: debouncedFilters.endDate,
            anomaly_type: debouncedFilters.anomalyType,
            min_severity: debouncedFilters.minSeverity,
            limit: 5000,
          }),
          api.getStations({ limit: 2000 }),
        ])
        if (cancelled) return

        if (!applyDataToMap(anomalyData, stationData)) {
          pendingData.current = { anomalyData, stationData }
        }
      } catch (err) {
        console.error('Failed to load map data:', err)
      } finally {
        if (!cancelled) setDataLoading(false)
      }
    }
    loadData()
    return () => { cancelled = true }
  }, [debouncedFilters, applyDataToMap])

  useEffect(() => {
    if (mapReady && pendingData.current) {
      const { anomalyData, stationData } = pendingData.current
      applyDataToMap(anomalyData, stationData)
      pendingData.current = null
    }
  }, [mapReady, applyDataToMap])

  return (
    <div className="relative w-full h-full">
      <div ref={mapContainer} className="w-full h-full" role="application" aria-label="Climate anomaly map" />
      {dataLoading && <MapLoadingSkeleton />}

      {/* Wind layer toggle */}
      <button
        onClick={() => setWindVisible(v => !v)}
        className={`absolute top-3 right-14 z-10 p-2 rounded-lg shadow-lg border transition-colors ${
          windVisible
            ? 'bg-primary text-primary-foreground border-primary'
            : 'bg-card/90 text-muted-foreground border-border hover:text-foreground'
        }`}
        title={windVisible ? 'Hide wind field' : 'Show wind field'}
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2" />
        </svg>
      </button>
    </div>
  )
}
