"""
SQLAlchemy ORM models with PostGIS geometry support.
"""
from sqlalchemy import (
    Column, String, Float, Integer, BigInteger, Date, Text,
    DateTime, Boolean, ForeignKey, Index, func
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
