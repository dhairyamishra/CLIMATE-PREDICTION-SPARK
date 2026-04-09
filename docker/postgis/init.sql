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

-- Phase 1.1: Climate indices (ENSO, NAO, PDO, AMO, IOD)
CREATE TABLE IF NOT EXISTS climate_indices (
    id                  BIGSERIAL PRIMARY KEY,
    index_date          DATE NOT NULL,
    index_name          VARCHAR(20) NOT NULL,
    value               DOUBLE PRECISION NOT NULL,
    anomaly             DOUBLE PRECISION,
    description         TEXT,
    source              VARCHAR(100),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Phase 1.2: Extreme value statistics (GEV/GPD return periods)
CREATE TABLE IF NOT EXISTS extreme_value_stats (
    id                  BIGSERIAL PRIMARY KEY,
    station_id          VARCHAR(20) NOT NULL REFERENCES stations(id),
    variable            VARCHAR(20) NOT NULL,
    distribution        VARCHAR(20) NOT NULL DEFAULT 'gev',
    return_period       INTEGER NOT NULL,
    return_level        DOUBLE PRECISION NOT NULL,
    lower_ci            DOUBLE PRECISION,
    upper_ci            DOUBLE PRECISION,
    shape_param         DOUBLE PRECISION,
    location_param      DOUBLE PRECISION,
    scale_param         DOUBLE PRECISION,
    n_years             INTEGER,
    computed_at         TIMESTAMPTZ DEFAULT NOW()
);

-- Phase 1.3: Trend analysis (Mann-Kendall + Sen's slope)
CREATE TABLE IF NOT EXISTS trend_analysis (
    id                  BIGSERIAL PRIMARY KEY,
    station_id          VARCHAR(20) NOT NULL REFERENCES stations(id),
    variable            VARCHAR(20) NOT NULL,
    period_start        INTEGER NOT NULL,
    period_end          INTEGER NOT NULL,
    trend_direction     VARCHAR(20) NOT NULL,
    sens_slope          DOUBLE PRECISION NOT NULL,
    p_value             DOUBLE PRECISION NOT NULL,
    z_statistic         DOUBLE PRECISION,
    tau                 DOUBLE PRECISION,
    slope_per_decade    DOUBLE PRECISION,
    ci_lower            DOUBLE PRECISION,
    ci_upper            DOUBLE PRECISION,
    significant         BOOLEAN DEFAULT FALSE,
    computed_at         TIMESTAMPTZ DEFAULT NOW()
);

-- Phase 2.3: Climate projections (CMIP6 SSP scenarios)
CREATE TABLE IF NOT EXISTS climate_projections (
    id                  BIGSERIAL PRIMARY KEY,
    station_id          VARCHAR(20) REFERENCES stations(id),
    projection_date     DATE NOT NULL,
    scenario            VARCHAR(20) NOT NULL,
    variable            VARCHAR(20) NOT NULL,
    predicted_value     DOUBLE PRECISION NOT NULL,
    lower_bound         DOUBLE PRECISION,
    upper_bound         DOUBLE PRECISION,
    model_name          VARCHAR(100),
    ensemble_size       INTEGER,
    bias_corrected      BOOLEAN DEFAULT FALSE
);

-- Phase 4.3: User management, saved views, alerts, annotations
CREATE TABLE IF NOT EXISTS users (
    id              VARCHAR(20) PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    email           VARCHAR(255),
    role            VARCHAR(20) DEFAULT 'researcher',
    token_hash      VARCHAR(64) NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saved_views (
    id              VARCHAR(20) PRIMARY KEY,
    user_id         VARCHAR(20) REFERENCES users(id),
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    view_state      JSONB NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alert_subscriptions (
    id              VARCHAR(20) PRIMARY KEY,
    user_id         VARCHAR(20) REFERENCES users(id),
    station_id      VARCHAR(20) REFERENCES stations(id),
    alert_type      VARCHAR(50) NOT NULL,
    min_severity    DOUBLE PRECISION DEFAULT 0.5,
    email           VARCHAR(255),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS annotations (
    id              VARCHAR(20) PRIMARY KEY,
    user_id         VARCHAR(20) REFERENCES users(id),
    station_id      VARCHAR(20) NOT NULL REFERENCES stations(id),
    annotation_date DATE,
    note            TEXT NOT NULL,
    category        VARCHAR(50) DEFAULT 'observation',
    created_at      TIMESTAMPTZ DEFAULT NOW()
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

-- Climate indices
CREATE INDEX IF NOT EXISTS idx_climate_indices_name_date ON climate_indices (index_name, index_date DESC);
CREATE INDEX IF NOT EXISTS idx_climate_indices_date      ON climate_indices (index_date DESC);

-- Extreme value stats
CREATE INDEX IF NOT EXISTS idx_evs_station_var  ON extreme_value_stats (station_id, variable, return_period);

-- Trend analysis
CREATE INDEX IF NOT EXISTS idx_trend_station_var ON trend_analysis (station_id, variable);
CREATE INDEX IF NOT EXISTS idx_trend_significant ON trend_analysis (significant) WHERE significant = TRUE;

-- Climate projections
CREATE INDEX IF NOT EXISTS idx_projections_station  ON climate_projections (station_id, scenario, variable, projection_date);
CREATE INDEX IF NOT EXISTS idx_projections_scenario ON climate_projections (scenario, variable);

-- Users & features
CREATE INDEX IF NOT EXISTS idx_users_token ON users (token_hash) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_saved_views_user ON saved_views (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_user ON alert_subscriptions (user_id) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_alerts_station ON alert_subscriptions (station_id) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_annotations_station ON annotations (station_id, annotation_date DESC);
