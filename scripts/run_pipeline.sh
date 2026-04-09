#!/usr/bin/env bash
# =============================================================
# Climate Anomaly Detection & Forecasting Engine
# End-to-end pipeline: seed data -> HDFS -> Spark ETL ->
#   anomaly detection -> forecasting -> PostGIS export
# =============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================================"
echo " Climate Anomaly Engine - Full Pipeline"
echo " Project: $PROJECT_DIR"
echo "============================================================"

# ---------------------------------------------------------------
# Step 1: Generate seed data (if not already present)
# ---------------------------------------------------------------
SEED_DIR="$PROJECT_DIR/data/seed"
if [ ! -d "$SEED_DIR/ghcn-daily" ]; then
    echo ""
    echo "[Step 1/7] Generating seed data (~5GB)..."
    python "$SCRIPT_DIR/generate_seed_data.py"
else
    echo ""
    echo "[Step 1/7] Seed data already exists, skipping generation."
fi

# ---------------------------------------------------------------
# Step 2: Upload seed data to HDFS
# ---------------------------------------------------------------
echo ""
echo "[Step 2/7] Uploading seed data to HDFS..."
python "$SCRIPT_DIR/upload_to_hdfs.py"

# ---------------------------------------------------------------
# Step 3: Ingest raw data into Parquet on HDFS
# ---------------------------------------------------------------
echo ""
echo "[Step 3/7] Ingesting raw data (GHCN, ERA5, GISS) -> Parquet..."

spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory 2g \
    --executor-memory 2g \
    --executor-cores 2 \
    "$PROJECT_DIR/spark/ingestion/ghcn_daily.py" stations

spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory 2g \
    --executor-memory 2g \
    --executor-cores 2 \
    "$PROJECT_DIR/spark/ingestion/ghcn_daily.py" observations

spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory 2g \
    --executor-memory 2g \
    --executor-cores 2 \
    "$PROJECT_DIR/spark/ingestion/era5_reanalysis.py"

spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory 2g \
    --executor-memory 2g \
    --executor-cores 2 \
    "$PROJECT_DIR/spark/ingestion/giss_temperature.py"

# ---------------------------------------------------------------
# Step 4: Join datasets & compute rolling statistics
# ---------------------------------------------------------------
echo ""
echo "[Step 4/7] Joining datasets & computing rolling statistics..."

spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory 2g \
    --executor-memory 2g \
    --executor-cores 2 \
    "$PROJECT_DIR/spark/processing/join_datasets.py"

spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory 2g \
    --executor-memory 2g \
    --executor-cores 2 \
    "$PROJECT_DIR/spark/processing/rolling_statistics.py"

# ---------------------------------------------------------------
# Step 5: STL decomposition (optional, can be slow)
# ---------------------------------------------------------------
echo ""
echo "[Step 5/7] Running STL decomposition..."

spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory 2g \
    --executor-memory 2g \
    --executor-cores 2 \
    "$PROJECT_DIR/spark/processing/stl_decomposition.py" || \
    echo "  WARNING: STL decomposition failed or timed out, continuing..."

# ---------------------------------------------------------------
# Step 5.5: Extremes Analysis (Gaps and Islands)
# ---------------------------------------------------------------
echo ""
echo "[Step 5.5/7] Running Gaps & Islands Extreme Events Analysis..."

spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory 2g \
    --executor-memory 2g \
    --executor-cores 2 \
    "$PROJECT_DIR/spark/processing/extremes_analysis.py"

# ---------------------------------------------------------------
# Step 6: Anomaly detection & forecasting
# ---------------------------------------------------------------
echo ""
echo "[Step 6/7] Running anomaly detection (Isolation Forest)..."

spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory 2g \
    --executor-memory 2g \
    --executor-cores 2 \
    "$PROJECT_DIR/spark/ml/anomaly_detection.py"

echo ""
echo "Running forecasting (statistical baseline)..."

spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory 2g \
    --executor-memory 2g \
    --executor-cores 2 \
    "$PROJECT_DIR/spark/ml/forecasting.py" statistical

# Prophet forecasting (optional, requires prophet installed)
echo ""
echo "Running forecasting (Prophet)..."
spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory 2g \
    --executor-memory 2g \
    --executor-cores 2 \
    "$PROJECT_DIR/spark/ml/forecasting.py" prophet || \
    echo "  WARNING: Prophet forecasting failed, continuing with statistical forecasts..."

# ---------------------------------------------------------------
# Step 7: Export to PostGIS
# ---------------------------------------------------------------
echo ""
echo "[Step 7/7] Exporting results to PostGIS..."

spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory 2g \
    --executor-memory 2g \
    --executor-cores 2 \
    --packages org.postgresql:postgresql:42.7.1 \
    "$PROJECT_DIR/spark/processing/export_to_postgis.py" all

echo ""
echo "============================================================"
echo " Pipeline complete!"
echo " - API: http://localhost:8000/docs"
echo " - Frontend: http://localhost:5173"
echo " - Spark UI: http://localhost:8080"
echo " - HDFS UI: http://localhost:9870"
echo "============================================================"
