"""
SQLAlchemy ORM models with PostGIS geometry support.
"""
from sqlalchemy import (
    Column, String, Float, Integer, BigInteger, Date, Text,
    DateTime, Boolean, ForeignKey, Index, func, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry

from app.core.database import Base


class Station(Base):
    __tablename__ = "stations"
    __table_args__ = (
        Index("idx_stations_country", "country"),
        Index("idx_stations_latlon", "latitude", "longitude"),
    )

    id = Column(String(20), primary_key=True)
    name = Column(String(255))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    elevation = Column(Float)
    country = Column(String(100))
    state = Column(String(100))
    geohash = Column(String(12), nullable=False, index=True)
    geom = Column(Geometry("POINT", srid=4326), nullable=False)
    first_year = Column(Integer)
    last_year = Column(Integer)
    record_count = Column(BigInteger, default=0)


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        Index("idx_obs_station_date", "station_id", "obs_date"),
        Index("idx_obs_date", "obs_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    station_id = Column(String(20), ForeignKey("stations.id"), nullable=False, index=True)
    obs_date = Column(Date, nullable=False)
    tmax = Column(Float)
    tmin = Column(Float)
    prcp = Column(Float)
    snow = Column(Float)
    snwd = Column(Float)
    tavg = Column(Float)
    tmax_rolling_30d = Column(Float)
    tmin_rolling_30d = Column(Float)
    prcp_rolling_30d = Column(Float)
    tmax_rolling_365d = Column(Float)
    tmin_rolling_365d = Column(Float)
    prcp_rolling_365d = Column(Float)
    tmax_stddev_30d = Column(Float)
    tmin_stddev_30d = Column(Float)
    prcp_stddev_30d = Column(Float)


class Anomaly(Base):
    __tablename__ = "anomalies"
    __table_args__ = (
        Index("idx_anomalies_station", "station_id", "anomaly_date"),
        Index("idx_anomalies_type", "anomaly_type"),
        Index("idx_anomalies_severity", "severity"),
        Index("idx_anomalies_date", "anomaly_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    station_id = Column(String(20), ForeignKey("stations.id"), nullable=False)
    anomaly_date = Column(Date, nullable=False)
    anomaly_type = Column(String(50), nullable=False)
    severity = Column(Float, nullable=False)
    duration_days = Column(Integer, default=1)
    temp_deviation = Column(Float)
    precip_deviation = Column(Float)
    description = Column(Text)
    geom = Column(Geometry("POINT", srid=4326), nullable=False)
    detected_at = Column(DateTime, server_default=func.now())


class Forecast(Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        Index("idx_forecasts_station", "station_id", "variable", "forecast_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    station_id = Column(String(20), ForeignKey("stations.id"), nullable=False)
    forecast_date = Column(Date, nullable=False)
    variable = Column(String(20), nullable=False)
    predicted_value = Column(Float, nullable=False)
    lower_bound = Column(Float)
    upper_bound = Column(Float)
    model_type = Column(String(50), nullable=False)
    model_version = Column(String(50))
    mae = Column(Float)
    rmse = Column(Float)
    created_at = Column(DateTime, server_default=func.now())


class AnomalyTile(Base):
    __tablename__ = "anomaly_tiles"
    __table_args__ = (
        Index("idx_tiles_geohash_date", "geohash", "tile_date"),
        Index("idx_tiles_date", "tile_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    geohash = Column(String(12), nullable=False, index=True)
    tile_date = Column(Date, nullable=False)
    anomaly_count = Column(Integer, default=0)
    avg_severity = Column(Float, default=0)
    dominant_type = Column(String(50))
    heatwave_count = Column(Integer, default=0)
    cold_snap_count = Column(Integer, default=0)
    precip_extreme_count = Column(Integer, default=0)
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    geom = Column(Geometry("POINT", srid=4326), nullable=False)


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(100), nullable=False)
    model_type = Column(String(50), nullable=False)
    version = Column(String(50), nullable=False)
    station_id = Column(String(20))
    variable = Column(String(20))
    mae = Column(Float)
    rmse = Column(Float)
    mape = Column(Float)
    parameters = Column(JSONB)
    trained_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)


class MonthlySummary(Base):
    __tablename__ = "monthly_summary"
    __table_args__ = (
        Index("idx_monthly_year_month", "year", "month"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    total_anomalies = Column(Integer, default=0)
    heatwave_count = Column(Integer, default=0)
    cold_snap_count = Column(Integer, default=0)
    precip_extreme_count = Column(Integer, default=0)
    avg_severity = Column(Float)
    top_region = Column(String(100))
    global_temp_anomaly = Column(Float)


class ClimateIndex(Base):
    __tablename__ = "climate_indices"
    __table_args__ = (
        Index("idx_climate_indices_name_date", "index_name", "index_date"),
        Index("idx_climate_indices_date", "index_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    index_date = Column(Date, nullable=False)
    index_name = Column(String(20), nullable=False)
    value = Column(Float, nullable=False)
    anomaly = Column(Float)
    description = Column(Text)
    source = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())


class ExtremeValueStat(Base):
    __tablename__ = "extreme_value_stats"
    __table_args__ = (
        Index("idx_evs_station_var", "station_id", "variable", "return_period"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    station_id = Column(String(20), ForeignKey("stations.id"), nullable=False)
    variable = Column(String(20), nullable=False)
    distribution = Column(String(20), nullable=False, default="gev")
    return_period = Column(Integer, nullable=False)
    return_level = Column(Float, nullable=False)
    lower_ci = Column(Float)
    upper_ci = Column(Float)
    shape_param = Column(Float)
    location_param = Column(Float)
    scale_param = Column(Float)
    n_years = Column(Integer)
    computed_at = Column(DateTime, server_default=func.now())


class TrendAnalysis(Base):
    __tablename__ = "trend_analysis"
    __table_args__ = (
        Index("idx_trend_station_var", "station_id", "variable"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    station_id = Column(String(20), ForeignKey("stations.id"), nullable=False)
    variable = Column(String(20), nullable=False)
    period_start = Column(Integer, nullable=False)
    period_end = Column(Integer, nullable=False)
    trend_direction = Column(String(20), nullable=False)
    sens_slope = Column(Float, nullable=False)
    p_value = Column(Float, nullable=False)
    z_statistic = Column(Float)
    tau = Column(Float)
    slope_per_decade = Column(Float)
    ci_lower = Column(Float)
    ci_upper = Column(Float)
    significant = Column(Boolean, default=False)
    computed_at = Column(DateTime, server_default=func.now())


class ClimateProjection(Base):
    __tablename__ = "climate_projections"
    __table_args__ = (
        Index("idx_projections_station", "station_id", "scenario", "variable", "projection_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    station_id = Column(String(20), ForeignKey("stations.id"))
    projection_date = Column(Date, nullable=False)
    scenario = Column(String(20), nullable=False)
    variable = Column(String(20), nullable=False)
    predicted_value = Column(Float, nullable=False)
    lower_bound = Column(Float)
    upper_bound = Column(Float)
    model_name = Column(String(100))
    ensemble_size = Column(Integer)
    bias_corrected = Column(Boolean, default=False)


class User(Base):
    __tablename__ = "users"

    id = Column(String(20), primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255))
    role = Column(String(20), default="researcher")
    token_hash = Column(String(64), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class SavedView(Base):
    __tablename__ = "saved_views"
    __table_args__ = (
        Index("idx_saved_views_user", "user_id"),
    )

    id = Column(String(20), primary_key=True)
    user_id = Column(String(20), ForeignKey("users.id"))
    name = Column(String(200), nullable=False)
    description = Column(Text)
    view_state = Column(JSONB, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class AlertSubscription(Base):
    __tablename__ = "alert_subscriptions"
    __table_args__ = (
        Index("idx_alerts_user", "user_id"),
    )

    id = Column(String(20), primary_key=True)
    user_id = Column(String(20), ForeignKey("users.id"))
    station_id = Column(String(20), ForeignKey("stations.id"))
    alert_type = Column(String(50), nullable=False)
    min_severity = Column(Float, default=0.5)
    email = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Annotation(Base):
    __tablename__ = "annotations"
    __table_args__ = (
        Index("idx_annotations_station", "station_id", "annotation_date"),
    )

    id = Column(String(20), primary_key=True)
    user_id = Column(String(20), ForeignKey("users.id"))
    station_id = Column(String(20), ForeignKey("stations.id"), nullable=False)
    annotation_date = Column(Date)
    note = Column(Text, nullable=False)
    category = Column(String(50), default="observation")
    created_at = Column(DateTime, server_default=func.now())
