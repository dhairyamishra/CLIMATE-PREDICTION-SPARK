import React, { useRef, useEffect, useState, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import { api } from '../services/api'
import { useDebounce } from '../hooks/useApi'

const ANOMALY_COLORS = {
  heatwave: '#ef4444',
  cold_snap: '#3b82f6',
  precip_extreme: '#22c55e',
}

const SEVERITY_RADIUS = {
  min: 4,
  max: 20,
}

export default function AnomalyMap({ filters, timeRange, onStationSelect, onBoundsChange }) {
  const mapContainer = useRef(null)
  const mapRef = useRef(null)
  const [mapLoaded, setMapLoaded] = useState(false)
  const debouncedFilters = useDebounce(filters, 500)

  // Initialize map
  useEffect(() => {
    if (mapRef.current) return

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
        },
        layers: [
          {
            id: 'osm-tiles-layer',
            type: 'raster',
            source: 'osm-tiles',
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: [0, 20],
      zoom: 2,
      minZoom: 1,
      maxZoom: 15,
    })

    map.addControl(new maplibregl.NavigationControl(), 'bottom-right')

    map.on('load', () => {
      // Add anomaly heatmap source
      map.addSource('anomaly-heatmap', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })

      // Add station points source
      map.addSource('station-points', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })

      // Heatmap layer
      map.addLayer({
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
      })

      // Anomaly circle layer (visible at higher zoom)
      map.addLayer({
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
      })

      // Station point layer
      map.addLayer({
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
      })

      setMapLoaded(true)
    })

    // Click handler for anomaly circles
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

    // Click handler for station points
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

    // Hover cursors
    map.on('mouseenter', 'anomaly-circles', () => { map.getCanvas().style.cursor = 'pointer' })
    map.on('mouseleave', 'anomaly-circles', () => { map.getCanvas().style.cursor = '' })
    map.on('mouseenter', 'stations', () => { map.getCanvas().style.cursor = 'pointer' })
    map.on('mouseleave', 'stations', () => { map.getCanvas().style.cursor = '' })

    // Popup on hover for anomaly circles
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

    // Track bounds
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

    return () => map.remove()
  }, [])

  // Fetch and update anomaly data when filters change
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return

    const loadData = async () => {
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

        // Update anomaly heatmap
        if (anomalyData?.features) {
          mapRef.current.getSource('anomaly-heatmap')?.setData(anomalyData)
        }

        // Update station points
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
          mapRef.current.getSource('station-points')?.setData(stationGeoJSON)
        }
      } catch (err) {
        console.error('Failed to load map data:', err)
      }
    }

    loadData()
  }, [mapLoaded, debouncedFilters])

  return (
    <div ref={mapContainer} className="w-full h-full" />
  )
}
