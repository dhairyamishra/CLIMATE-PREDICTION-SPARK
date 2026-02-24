"""
Pydantic schemas for API request/response models.
"""
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional


# --- Station Schemas ---
class StationBase(BaseModel):
    id: str
    name: Optional[str] = None
    latitude: float
    longitude: float
    elevation: Optional[float] = None
    country: Optional[str] = None
    state: Optional[str] = None
    geohash: str
    first_year: Optional[int] = None
    last_year: Optional[int] = None
    record_count: int = 0


class StationDetail(StationBase):
    recent_anomalies: list["AnomalyBrief"] = []


class StationSearchResult(BaseModel):
    id: str
    name: Optional[str] = None
    country: Optional[str] = None
    latitude: float
    longitude: float


# --- Anomaly Schemas ---
class AnomalyBrief(BaseModel):
    id: int
    anomaly_date: date
    anomaly_type: str
    severity: float


class AnomalyDetail(BaseModel):
    id: int
    station_id: str
    anomaly_date: date
    anomaly_type: str
    severity: float
    duration_days: int = 1
    temp_deviation: Optional[float] = None
    precip_deviation: Optional[float] = None
    description: Optional[str] = None
    latitude: float
    longitude: float


class AnomalyGeoJSON(BaseModel):
    type: str = "FeatureCollection"
    features: list[dict]


# --- Forecast Schemas ---
class ForecastPoint(BaseModel):
    forecast_date: date
    variable: str
    predicted_value: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    model_type: str


class StationForecast(BaseModel):
    station_id: str
    variable: str
    forecasts: list[ForecastPoint]


# --- Time Series Schemas ---
class TimeSeriesPoint(BaseModel):
    obs_date: date
    tmax: Optional[float] = None
    tmin: Optional[float] = None
    prcp: Optional[float] = None
    tavg: Optional[float] = None
    tmax_rolling_30d: Optional[float] = None
    tmin_rolling_30d: Optional[float] = None
    prcp_rolling_30d: Optional[float] = None


class StationTimeSeries(BaseModel):
    station_id: str
    data: list[TimeSeriesPoint]
    total_records: int


# --- Summary Schemas ---
class GlobalSummary(BaseModel):
    total_stations: int
    total_anomalies: int
    heatwave_count: int
    cold_snap_count: int
    precip_extreme_count: int
    avg_severity: float
    top_regions: list[dict]
    monthly_trend: list[dict]


# --- Tile Schemas ---
class TilePoint(BaseModel):
    geohash: str
    latitude: float
    longitude: float
    anomaly_count: int
    avg_severity: float
    dominant_type: Optional[str] = None
    heatwave_count: int = 0
    cold_snap_count: int = 0
    precip_extreme_count: int = 0


# --- Query Parameters ---
class AnomalyQuery(BaseModel):
    min_lat: float = Field(-90, ge=-90, le=90)
    max_lat: float = Field(90, ge=-90, le=90)
    min_lon: float = Field(-180, ge=-180, le=180)
    max_lon: float = Field(180, ge=-180, le=180)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    anomaly_type: Optional[str] = None
    min_severity: float = Field(0, ge=0, le=1)
    limit: int = Field(1000, ge=1, le=10000)


# Forward reference resolution
StationDetail.model_rebuild()
