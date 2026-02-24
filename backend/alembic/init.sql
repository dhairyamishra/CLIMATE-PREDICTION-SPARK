-- Enable PostGIS extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Stations table
CREATE TABLE IF NOT EXISTS stations (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    elevation DOUBLE PRECISION,
    country VARCHAR(100),
    state VARCHAR(100),
    geohash VARCHAR(12) NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    first_year INTEGER,
    last_year INTEGER,
    record_count BIGINT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_stations_geom ON stations USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_stations_geohash ON stations(geohash);
CREATE INDEX IF NOT EXISTS idx_stations_country ON stations(country);

-- Climate observations (aggregated daily, loaded from Spark)
CREATE TABLE IF NOT EXISTS observations (
    id BIGSERIAL PRIMARY KEY,
    station_id VARCHAR(20) NOT NULL REFERENCES stations(id),
    obs_date DATE NOT NULL,
    tmax DOUBLE PRECISION,
    tmin DOUBLE PRECISION,
    prcp DOUBLE PRECISION,
    snow DOUBLE PRECISION,
    snwd DOUBLE PRECISION,
    tavg DOUBLE PRECISION,
    tmax_rolling_30d DOUBLE PRECISION,
    tmin_rolling_30d DOUBLE PRECISION,
    prcp_rolling_30d DOUBLE PRECISION,
    tmax_rolling_365d DOUBLE PRECISION,
    tmin_rolling_365d DOUBLE PRECISION,
    prcp_rolling_365d DOUBLE PRECISION,
    tmax_stddev_30d DOUBLE PRECISION,
    tmin_stddev_30d DOUBLE PRECISION,
    prcp_stddev_30d DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_obs_station_date ON observations(station_id, obs_date);
CREATE INDEX IF NOT EXISTS idx_obs_date ON observations(obs_date);

-- Detected anomalies
CREATE TABLE IF NOT EXISTS anomalies (
    id BIGSERIAL PRIMARY KEY,
    station_id VARCHAR(20) NOT NULL REFERENCES stations(id),
    anomaly_date DATE NOT NULL,
    anomaly_type VARCHAR(50) NOT NULL,  -- heatwave, cold_snap, precip_extreme
    severity DOUBLE PRECISION NOT NULL,  -- anomaly score 0-1
    duration_days INTEGER DEFAULT 1,
    temp_deviation DOUBLE PRECISION,
    precip_deviation DOUBLE PRECISION,
    description TEXT,
    geom GEOMETRY(Point, 4326) NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_anomalies_geom ON anomalies USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_anomalies_station_date ON anomalies(station_id, anomaly_date);
CREATE INDEX IF NOT EXISTS idx_anomalies_type ON anomalies(anomaly_type);
CREATE INDEX IF NOT EXISTS idx_anomalies_date ON anomalies(anomaly_date);
CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity);

-- Forecasts
CREATE TABLE IF NOT EXISTS forecasts (
    id BIGSERIAL PRIMARY KEY,
    station_id VARCHAR(20) NOT NULL REFERENCES stations(id),
    forecast_date DATE NOT NULL,
    variable VARCHAR(20) NOT NULL,  -- tmax, tmin, prcp
    predicted_value DOUBLE PRECISION NOT NULL,
    lower_bound DOUBLE PRECISION,
    upper_bound DOUBLE PRECISION,
    model_type VARCHAR(50) NOT NULL,  -- prophet, lstm, ensemble
    model_version VARCHAR(50),
    mae DOUBLE PRECISION,
    rmse DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_forecasts_station_date ON forecasts(station_id, forecast_date);
CREATE INDEX IF NOT EXISTS idx_forecasts_variable ON forecasts(variable);
CREATE INDEX IF NOT EXISTS idx_forecasts_model ON forecasts(model_type);

-- Pre-computed anomaly grid tiles (for heatmap)
CREATE TABLE IF NOT EXISTS anomaly_tiles (
    id BIGSERIAL PRIMARY KEY,
    geohash VARCHAR(12) NOT NULL,
    tile_date DATE NOT NULL,
    anomaly_count INTEGER DEFAULT 0,
    avg_severity DOUBLE PRECISION DEFAULT 0,
    dominant_type VARCHAR(50),
    heatwave_count INTEGER DEFAULT 0,
    cold_snap_count INTEGER DEFAULT 0,
    precip_extreme_count INTEGER DEFAULT 0,
    center_lat DOUBLE PRECISION NOT NULL,
    center_lon DOUBLE PRECISION NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tiles_geom ON anomaly_tiles USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_tiles_date ON anomaly_tiles(tile_date);
CREATE INDEX IF NOT EXISTS idx_tiles_geohash ON anomaly_tiles(geohash);

-- Model registry
CREATE TABLE IF NOT EXISTS model_registry (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    version VARCHAR(50) NOT NULL,
    station_id VARCHAR(20),
    variable VARCHAR(20),
    mae DOUBLE PRECISION,
    rmse DOUBLE PRECISION,
    mape DOUBLE PRECISION,
    parameters JSONB,
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_model_registry_active ON model_registry(is_active);

-- Monthly summary view
CREATE TABLE IF NOT EXISTS monthly_summary (
    id BIGSERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    total_anomalies INTEGER DEFAULT 0,
    heatwave_count INTEGER DEFAULT 0,
    cold_snap_count INTEGER DEFAULT 0,
    precip_extreme_count INTEGER DEFAULT 0,
    avg_severity DOUBLE PRECISION,
    top_region VARCHAR(100),
    global_temp_anomaly DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_monthly_summary_date ON monthly_summary(year, month);
