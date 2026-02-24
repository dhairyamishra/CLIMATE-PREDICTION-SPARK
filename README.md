# 🌍 Global Climate Anomaly Detection & Forecasting Engine

A full-stack distributed platform for detecting anomalous climate events — heatwaves, cold snaps, precipitation extremes — across 100+ years of global weather station data, with ML-powered anomaly detection and time-series forecasting.

**Tech Stack:** PySpark 3.5 · Spark SQL · Window Functions · `applyInPandas` · HDFS · FastAPI · PostGIS · React 18 · MapLibre GL · Recharts · TailwindCSS · Docker Compose

![Status](https://img.shields.io/badge/status-complete-brightgreen) ![Files](https://img.shields.io/badge/files-52-blue) ![Docker Services](https://img.shields.io/badge/docker%20services-9-purple)

---

## Implementation Status

| Phase | Description | Status | Files |
|-------|-------------|--------|-------|
| **1. Scaffolding** | Repo structure, Docker Compose, Dockerfiles, env config | ✅ Complete | 10 |
| **2. Data Ingestion** | GHCN-Daily, ERA5, GISS ingestion scripts + ~5GB seed generator | ✅ Complete | 4 |
| **3. Spark Processing** | SQL joins, 30/90/365-day rolling stats, STL decomposition | ✅ Complete | 4 |
| **4. Anomaly Detection** | Isolation Forest, anomaly classification, tile aggregation | ✅ Complete | 1 |
| **5. Forecasting** | Prophet, statistical baseline, ensemble, per-station parallelism | ✅ Complete | 1 |
| **6. Backend API** | FastAPI + PostGIS schema, 7 API endpoints, ORM, Pydantic schemas | ✅ Complete | 14 |
| **7. Frontend** | React + MapLibre GL heatmap, Recharts charts, dark theme UI | ✅ Complete | 14 |
| **8. Pipeline & Deploy** | Spark→PostGIS export, pipeline scripts (Linux + Windows), README | ✅ Complete | 4 |

**Total: 52 files across the full stack.**

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Docker Compose Stack                         │
│                          (9 services)                                │
├─────────────┬───────────────┬────────────────┬───────────────────────┤
│   HDFS      │  Apache Spark │   PostGIS      │   Application        │
│  NameNode   │  Master       │  PostgreSQL 16 │                      │
│  DataNode×2 │  Worker×2     │  + PostGIS 3.4 │  FastAPI Backend     │
│             │               │                │  React 18 Frontend   │
│  Parquet    │  ETL, ML,     │  Geospatial    │  Nginx Reverse Proxy │
│  Data Lake  │  Forecasting  │  Queries       │                      │
└─────────────┴───────────────┴────────────────┴───────────────────────┘
```

### Data Flow

```
                          ┌─────────────────┐
  NOAA GHCN-Daily ───────▶│                 │
  ERA5 Reanalysis ───────▶│  HDFS Parquet   │──▶ Spark SQL Joins ──▶ Rolling Stats (30/90/365d)
  NASA GISS ─────────────▶│  Data Lake      │        │                     │
  Seed Generator ────────▶│  (geo-partitioned)       ▼                     ▼
                          └─────────────────┘   STL Decomp          Window Functions
                                                     │                     │
                                                     ▼                     ▼
                                              Isolation Forest ──▶ Anomaly Detection
                                                     │                     │
                                                     ▼                     ▼
                                              Prophet/Ensemble ──▶ Forecasting
                                                     │
                                                     ▼
                                              PostGIS Export ──▶ FastAPI REST ──▶ React UI
```

---

## Datasets

| Dataset | Source | Description | Size (Full) |
|---------|--------|-------------|-------------|
| NOAA GHCN-Daily | [NOAA](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily) | 2.5B+ daily observations from 100K+ stations | ~80 GB |
| ERA5 Reanalysis | [Copernicus/ECMWF](https://cds.climate.copernicus.eu/) | Gridded global climate reanalysis (2m temp, precip, wind) | ~500 GB subset |
| NASA GISS | [NASA](https://data.giss.nasa.gov/gistemp/) | Monthly surface temperature anomaly grids (GISTEMP v4) | ~2 GB |

> **Demo mode:** A **~5 GB synthetic seed dataset** (500 stations across 15 climate regions, 1970–2020, with 16 embedded real-world extreme events) is generated for end-to-end testing without downloading the full datasets.

### Seed Data Details

- **500 stations** across US, Canada, Mexico, Brazil, Argentina, UK, Germany, France, Russia, China, India, Japan, Australia, South Africa, Kenya
- **~9.1M daily observations** (50 years × 365 days × 500 stations)
- **ERA5-like gridded data** — 2m temperature, total precipitation, 10m wind, surface pressure at 2.5° resolution
- **GISS-like monthly anomalies** — 5° × 5° grid cells with temperature anomaly trends
- **16 embedded extreme events** — 2003 European heatwave, 2010 Russian heat, 2014 Polar Vortex, Hurricane Katrina, 2019 Australian bushfires, and more

---

## Spark Mastery Demonstrated

| Technique | File | Description |
|-----------|------|-------------|
| **Spark SQL Joins** | `join_datasets.py` | 4-way join: station metadata ⋈ daily obs ⋈ ERA5 grid ⋈ GISS anomalies, with geohash spatial matching |
| **Custom Partitioning** | All ingestion scripts | Hive-style geo-partitioned Parquet by `geohash_prefix` + `year`/`month` for spatial-temporal queries |
| **Window Functions** | `rolling_statistics.py` | 30/90/365-day rolling mean, stddev, min, max, z-scores via `Window.partitionBy().orderBy().rangeBetween()` |
| **Distributed STL** | `stl_decomposition.py` | Seasonal-Trend decomposition per station via `applyInPandas` on grouped DataFrame |
| **Isolation Forest** | `anomaly_detection.py` | Multi-variate anomaly detection (temp z-scores, precip z-scores, STL residuals) per station via `applyInPandas` |
| **Distributed Forecasting** | `forecasting.py` | Prophet + statistical baseline per station parallelized via `applyInPandas`, with ensemble combination |
| **Adaptive Execution** | `spark_config.py` | AQE enabled with coalescing, dynamic partition overwrite, Kryo serialization |
| **HDFS Data Lake** | Docker HDFS cluster | Real NameNode + 2 DataNodes, replication factor 2, Snappy-compressed Parquet |

---

## Quick Start

### Prerequisites

- **Docker & Docker Compose** (v2.0+)
- **~10 GB free disk space** (seed data + Docker images)

### 1. Clone & Configure

```bash
git clone https://github.com/yourusername/CLIMATE-PREDICTION-SPARK.git
cd CLIMATE-PREDICTION-SPARK
cp .env.example .env
```

### 2. Start Infrastructure

```bash
docker-compose up -d
```

This starts **9 services**: HDFS NameNode, 2 DataNodes, Spark Master, 2 Spark Workers, PostGIS, FastAPI backend, React frontend, and Nginx.

### 3. Run the Full Pipeline

**Linux / macOS:**
```bash
docker-compose exec spark-master bash /opt/scripts/run_pipeline.sh
```

**Windows:**
```cmd
scripts\run_pipeline.bat
```

The pipeline runs 7 steps:
1. Generate ~5 GB seed data (500 stations, 50 years)
2. Upload seed data to HDFS
3. Ingest raw data → Parquet (GHCN, ERA5, GISS)
4. Join datasets + compute rolling statistics
5. Run STL decomposition
6. Anomaly detection (Isolation Forest) + forecasting (Prophet + statistical)
7. Export results to PostGIS

### 4. Access the Application

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:5173 | React + MapLibre GL interactive map |
| **API Docs** | http://localhost:8000/docs | Swagger/OpenAPI auto-docs |
| **Spark UI** | http://localhost:8080 | Spark job monitoring |
| **HDFS UI** | http://localhost:9870 | HDFS file browser |
| **Nginx** | http://localhost:80 | Reverse proxy (production entry) |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/anomalies` | Query anomalies by bounding box, time range, type, severity |
| `GET` | `/api/stations` | List/search stations with geographic filtering |
| `GET` | `/api/stations/{id}` | Station detail with metadata + recent anomalies |
| `GET` | `/api/stations/{id}/forecast` | Temperature & precipitation forecasts with confidence intervals |
| `GET` | `/api/timeseries/{station_id}` | Historical observations at daily/monthly/yearly resolution |
| `GET` | `/api/tiles` | Pre-aggregated anomaly tiles for heatmap rendering |
| `GET` | `/api/summary` | Global dashboard statistics, monthly trends, top regions |
| `GET` | `/health` | Health check |

All endpoints support pagination (`limit`, `offset`) and return JSON. Anomaly and tile endpoints support spatial filtering (`min_lat`, `max_lat`, `min_lon`, `max_lon`).

---

## Frontend Features

- **Global anomaly heatmap** — MapLibre GL heatmap + circle layers over dark CARTO basemap, color-coded by anomaly type and severity
- **Time slider** — Dual-handle range slider for historical exploration (1970–2020) with decade markers
- **Anomaly type filters** — Toggle heatwave / cold snap / precipitation extreme with icon pills
- **Severity threshold** — Continuous slider to filter by minimum anomaly severity
- **Station drill-down** — Click any station for a detailed sidebar with:
  - **Time-series charts** — Temperature (T-Max, T-Min, 30d rolling avg) and precipitation via Recharts `LineChart` + `AreaChart`
  - **Forecast charts** — Predicted values with upper/lower confidence interval bands
  - **Anomaly timeline** — Severity badges with type, duration, and deviation stats
  - **Resolution toggle** — Switch between daily, monthly, yearly aggregation
- **Dashboard panel** — Global statistics with:
  - Summary cards (total stations, anomaly counts by type, avg severity)
  - Pie chart of anomaly distribution
  - Stacked bar chart of monthly anomaly trend
  - Top anomalous regions ranked list with progress bars
- **Dark theme** — Custom CSS variables, dark CARTO basemap, styled MapLibre popups and controls
- **Responsive sidebar** — Collapsible 400px panel with tab navigation

---

## Project Structure

```
CLIMATE-PREDICTION-SPARK/
│
├── spark/                              # PySpark processing (15 files)
│   ├── config/
│   │   └── spark_config.py             #   SparkSession config, HDFS paths, AQE settings
│   ├── ingestion/
│   │   ├── ghcn_daily.py               #   NOAA GHCN-Daily station + observation ingestion
│   │   ├── era5_reanalysis.py          #   ERA5 reanalysis NetCDF → geo-partitioned Parquet
│   │   └── giss_temperature.py         #   NASA GISS surface temp anomaly ingestion
│   ├── processing/
│   │   ├── join_datasets.py            #   4-way SQL join → unified climate table
│   │   ├── rolling_statistics.py       #   30/90/365-day rolling stats via Window functions
│   │   ├── stl_decomposition.py        #   Distributed STL decomposition per station
│   │   └── export_to_postgis.py        #   Spark → PostGIS bulk export (6 tables)
│   └── ml/
│       ├── anomaly_detection.py        #   Isolation Forest + classification + tile aggregation
│       └── forecasting.py              #   Prophet + statistical + ensemble forecasting
│
├── backend/                            # FastAPI application (14 files)
│   ├── Dockerfile
│   ├── requirements.txt                #   17 Python dependencies
│   ├── alembic/
│   │   └── init.sql                    #   PostGIS schema DDL (7 tables, 15+ indexes)
│   └── app/
│       ├── main.py                     #   FastAPI app, CORS, rate limiting, router
│       ├── core/
│       │   ├── config.py               #   Pydantic Settings (DB, Spark, API config)
│       │   └── database.py             #   Async SQLAlchemy engine + session
│       ├── api/
│       │   ├── anomalies.py            #   GET /anomalies — bbox + time + type filter
│       │   ├── stations.py             #   GET /stations, GET /stations/{id}
│       │   ├── forecasts.py            #   GET /stations/{id}/forecast
│       │   ├── timeseries.py           #   GET /timeseries/{id} — daily/monthly/yearly
│       │   ├── tiles.py                #   GET /tiles — pre-aggregated heatmap data
│       │   └── summary.py              #   GET /summary — global dashboard stats
│       └── models/
│           ├── orm.py                  #   SQLAlchemy models (7 tables, PostGIS geometry)
│           └── schemas.py              #   Pydantic request/response schemas
│
├── frontend/                           # React application (14 files)
│   ├── Dockerfile
│   ├── package.json                    #   Vite + React 18 + MapLibre GL + Recharts + Tailwind
│   ├── vite.config.js                  #   Vite config with @ alias and API proxy
│   ├── tailwind.config.js              #   Custom dark theme colors + CSS variables
│   ├── postcss.config.js
│   ├── index.html
│   ├── public/
│   │   └── vite.svg                    #   Custom climate-themed favicon
│   └── src/
│       ├── main.jsx                    #   React root + MapLibre CSS import
│       ├── index.css                   #   Tailwind base + dark theme + MapLibre overrides
│       ├── App.jsx                     #   App shell: map + sidebar + filters + time slider
│       ├── components/
│       │   ├── AnomalyMap.jsx          #   MapLibre GL: heatmap + circle + station layers
│       │   ├── TimeSlider.jsx          #   Dual-range year slider with decade markers
│       │   ├── FilterBar.jsx           #   Anomaly type pills + severity slider
│       │   ├── StationPanel.jsx        #   Station drill-down: charts + forecast + anomalies
│       │   ├── DashboardSummary.jsx    #   Global stats: pie chart + bar chart + rankings
│       │   ├── Header.jsx              #   App header with nav controls
│       │   └── Sidebar.jsx             #   Collapsible 400px detail panel
│       ├── hooks/
│       │   └── useApi.js               #   useApi hook + useDebounce
│       ├── services/
│       │   └── api.js                  #   API client (7 endpoint methods)
│       └── utils/
│           └── cn.js                   #   clsx + tailwind-merge utility
│
├── docker/                             # Infrastructure configs (7 files)
│   ├── hdfs/
│   │   ├── Dockerfile                  #   Hadoop 3.3.6 NameNode/DataNode image
│   │   ├── core-site.xml               #   HDFS core config (fs.defaultFS)
│   │   └── hdfs-site.xml               #   HDFS site config (replication=2)
│   ├── spark/
│   │   ├── Dockerfile                  #   Spark 3.5 + PySpark + Python ML deps
│   │   ├── core-site.xml               #   Spark → HDFS connection
│   │   └── hdfs-site.xml               #   Spark → HDFS connection
│   └── nginx/
│       └── nginx.conf                  #   Reverse proxy: /api → backend, / → frontend
│
├── scripts/                            # Pipeline orchestration (4 files)
│   ├── generate_seed_data.py           #   ~5GB synthetic dataset (500 stations, 50 years)
│   ├── upload_to_hdfs.py               #   Seed data → HDFS uploader
│   ├── run_pipeline.sh                 #   End-to-end pipeline (Linux/macOS)
│   └── run_pipeline.bat                #   End-to-end pipeline (Windows)
│
├── data/                               #   Generated data directory (gitignored)
│   └── .gitkeep
├── docker-compose.yml                  #   9-service orchestration with health checks
├── .env.example                        #   Environment template (DB, Spark, API keys)
├── .gitignore                          #   Python, Node, Docker, data exclusions
└── README.md                           #   This file
```

---

## Anomaly Detection Approach

1. **Feature Engineering** — Rolling z-scores (30d window), climatological deviation (day-of-year baseline), STL residuals
2. **Isolation Forest** — Trained per station on multi-variate features (`tmax_zscore`, `tmin_zscore`, `prcp_zscore`, `stl_residual`); contamination = 2%
3. **Classification** — Anomalies auto-classified as `heatwave` / `cold_snap` / `precip_extreme` based on z-score direction and magnitude thresholds
4. **Duration tracking** — Consecutive anomaly days grouped into events with duration and deviation metrics
5. **Tile aggregation** — Anomalies pre-aggregated by geohash prefix + year/month for fast heatmap rendering
6. **Monthly summaries** — Global anomaly counts by type with average severity per month
7. **Embedded extreme events** — Seed data includes realistic reproductions of 16 known climate events (2003 European heatwave, 2010 Russian heat, 2014 Polar Vortex, Hurricane Katrina, 2019 Australian bushfires, etc.)

## Forecasting Approach

1. **Prophet** — Weekly resampled, yearly seasonality, trained per station per variable via `applyInPandas`
2. **Statistical baseline** — Day-of-year climatology + linear trend extrapolation with empirical confidence intervals
3. **Ensemble** — Weighted average (70% Prophet / 30% statistical) with merged confidence intervals
4. **Validation** — Hold-out last 52 weeks; metrics: MAE, RMSE per station per variable (`tmax`, `tmin`, `prcp`)
5. **Model registry** — Results stored with model type, version, and performance metrics for tracking

## Docker Services

| Service | Image | Ports | Purpose |
|---------|-------|-------|---------|
| `namenode` | Custom Hadoop 3.3.6 | 9870, 9000 | HDFS NameNode |
| `datanode1` | Custom Hadoop 3.3.6 | — | HDFS DataNode |
| `datanode2` | Custom Hadoop 3.3.6 | — | HDFS DataNode |
| `spark-master` | Custom Spark 3.5 | 8080, 7077 | Spark Master |
| `spark-worker-1` | Custom Spark 3.5 | — | Spark Worker (2 cores, 2GB) |
| `spark-worker-2` | Custom Spark 3.5 | — | Spark Worker (2 cores, 2GB) |
| `postgis` | postgis/postgis:16-3.4 | 5432 | PostgreSQL + PostGIS |
| `backend` | Custom Python 3.11 | 8000 | FastAPI REST API |
| `frontend` | Custom Node 20 | 5173 | React dev server |
| `nginx` | nginx:alpine | 80 | Reverse proxy |

## PostGIS Schema

| Table | Rows (seed) | Description |
|-------|-------------|-------------|
| `stations` | 500 | Station metadata with PostGIS Point geometry |
| `observations` | ~180K (2% sample) | Daily obs with rolling stats |
| `anomalies` | Variable | Detected anomalies with type, severity, geometry |
| `forecasts` | Variable | Per-station forecasts with confidence intervals |
| `anomaly_tiles` | Variable | Pre-aggregated tiles by geohash + month |
| `monthly_summary` | ~600 | Monthly anomaly counts and avg severity |
| `model_registry` | Variable | ML model versions and performance metrics |

---

## Data Attribution

- NOAA Global Historical Climatology Network - Daily (GHCN-Daily), NOAA National Centers for Environmental Information
- ERA5 hourly data on single levels from 1940 to present, Copernicus Climate Change Service (C3S)
- GISS Surface Temperature Analysis (GISTEMP v4), NASA Goddard Institute for Space Studies

## License

MIT
