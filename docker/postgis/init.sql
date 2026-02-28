-- ============================================================
-- Climate Anomaly Engine — PostGIS Schema & Performance Indexes
-- Runs automatically on first container start.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---- Tables ------------------------------------------------

CREATE TABLE IF NOT EXISTS stations (
    id          VARCHAR(20) PRIMARY KEY,
    name        VARCHAR(255),
    latitude    DOUBLE PRECISION NOT NULL,
    longitude   DOUBLE PRECISION NOT NULL,
    elevation   DOUBLE PRECISION,
    country     VARCHAR(100),
    state       VARCHAR(100),
    geohash     VARCHAR(12) NOT NULL,
    geom        GEOMETRY(POINT, 4326) NOT NULL,
    first_year  INTEGER,
    last_year   INTEGER,
    record_count BIGINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS observations (
    id                  BIGSERIAL PRIMARY KEY,
    station_id          VARCHAR(20) NOT NULL REFERENCES stations(id),
    obs_date            DATE NOT NULL,
    tmax                DOUBLE PRECISION,
    tmin                DOUBLE PRECISION,
    prcp                DOUBLE PRECISION,
    snow                DOUBLE PRECISION,
    snwd                DOUBLE PRECISION,
    tavg                DOUBLE PRECISION,
    tmax_rolling_30d    DOUBLE PRECISION,
    tmin_rolling_30d    DOUBLE PRECISION,
    prcp_rolling_30d    DOUBLE PRECISION,
    tmax_rolling_365d   DOUBLE PRECISION,
    tmin_rolling_365d   DOUBLE PRECISION,
    prcp_rolling_365d   DOUBLE PRECISION,
    tmax_stddev_30d     DOUBLE PRECISION,
    tmin_stddev_30d     DOUBLE PRECISION,
    prcp_stddev_30d     DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS anomalies (
    id                  BIGSERIAL PRIMARY KEY,
    station_id          VARCHAR(20) NOT NULL REFERENCES stations(id),
    anomaly_date        DATE NOT NULL,
    anomaly_type        VARCHAR(50) NOT NULL,
    severity            DOUBLE PRECISION NOT NULL,
    duration_days       INTEGER DEFAULT 1,
    temp_deviation      DOUBLE PRECISION,
    precip_deviation    DOUBLE PRECISION,
    description         TEXT,
    geom                GEOMETRY(POINT, 4326) NOT NULL,
    detected_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS forecasts (
    id                  BIGSERIAL PRIMARY KEY,
    station_id          VARCHAR(20) NOT NULL REFERENCES stations(id),
    forecast_date       DATE NOT NULL,
    variable            VARCHAR(20) NOT NULL,
    predicted_value     DOUBLE PRECISION NOT NULL,
    lower_bound         DOUBLE PRECISION,
    upper_bound         DOUBLE PRECISION,
    model_type          VARCHAR(50) NOT NULL,
    model_version       VARCHAR(50),
    mae                 DOUBLE PRECISION,
    rmse                DOUBLE PRECISION,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS anomaly_tiles (
    id                      BIGSERIAL PRIMARY KEY,
    geohash                 VARCHAR(12) NOT NULL,
    tile_date               DATE NOT NULL,
    anomaly_count           INTEGER DEFAULT 0,
    avg_severity            DOUBLE PRECISION DEFAULT 0,
    dominant_type           VARCHAR(50),
    heatwave_count          INTEGER DEFAULT 0,
    cold_snap_count         INTEGER DEFAULT 0,
    precip_extreme_count    INTEGER DEFAULT 0,
    center_lat              DOUBLE PRECISION NOT NULL,
    center_lon              DOUBLE PRECISION NOT NULL,
    geom                    GEOMETRY(POINT, 4326) NOT NULL
);

CREATE TABLE IF NOT EXISTS model_registry (
    id              SERIAL PRIMARY KEY,
    model_name      VARCHAR(100) NOT NULL,
    model_type      VARCHAR(50) NOT NULL,
    version         VARCHAR(50) NOT NULL,
    station_id      VARCHAR(20),
    variable        VARCHAR(20),
    mae             DOUBLE PRECISION,
    rmse            DOUBLE PRECISION,
    mape            DOUBLE PRECISION,
    parameters      JSONB,
    trained_at      TIMESTAMPTZ DEFAULT NOW(),
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS monthly_summary (
    id                      BIGSERIAL PRIMARY KEY,
    year                    INTEGER NOT NULL,
    month                   INTEGER NOT NULL,
    total_anomalies         INTEGER DEFAULT 0,
    heatwave_count          INTEGER DEFAULT 0,
    cold_snap_count         INTEGER DEFAULT 0,
    precip_extreme_count    INTEGER DEFAULT 0,
    avg_severity            DOUBLE PRECISION,
    top_region              VARCHAR(100),
    global_temp_anomaly     DOUBLE PRECISION
);

-- ---- Performance Indexes -----------------------------------

-- Stations: spatial + geographic filters
CREATE INDEX IF NOT EXISTS idx_stations_geom        ON stations USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_stations_geohash     ON stations (geohash);
CREATE INDEX IF NOT EXISTS idx_stations_country     ON stations (country);
CREATE INDEX IF NOT EXISTS idx_stations_latlon      ON stations (latitude, longitude);

-- Observations: time-series lookups by station + date
CREATE INDEX IF NOT EXISTS idx_obs_station_date     ON observations (station_id, obs_date DESC);
CREATE INDEX IF NOT EXISTS idx_obs_date             ON observations (obs_date);

-- Anomalies: filtered queries by type, severity, date, spatial
CREATE INDEX IF NOT EXISTS idx_anomalies_geom       ON anomalies USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_anomalies_station    ON anomalies (station_id, anomaly_date DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_date       ON anomalies (anomaly_date DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_type       ON anomalies (anomaly_type);
CREATE INDEX IF NOT EXISTS idx_anomalies_severity   ON anomalies (severity DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_composite  ON anomalies (anomaly_type, severity DESC, anomaly_date DESC);

-- Forecasts: station + variable lookups
CREATE INDEX IF NOT EXISTS idx_forecasts_station    ON forecasts (station_id, variable, forecast_date);

-- Tiles: heatmap aggregation queries
CREATE INDEX IF NOT EXISTS idx_tiles_geohash_date   ON anomaly_tiles (geohash, tile_date);
CREATE INDEX IF NOT EXISTS idx_tiles_date           ON anomaly_tiles (tile_date);
CREATE INDEX IF NOT EXISTS idx_tiles_geom           ON anomaly_tiles USING GIST (geom);

-- Monthly summary: dashboard trend queries
CREATE INDEX IF NOT EXISTS idx_monthly_year_month   ON monthly_summary (year DESC, month DESC);

-- Model registry: active model lookups
CREATE INDEX IF NOT EXISTS idx_model_active         ON model_registry (model_name, is_active) WHERE is_active = TRUE;
