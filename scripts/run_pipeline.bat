@echo off
REM =============================================================
REM Climate Anomaly Detection & Forecasting Engine
REM End-to-end pipeline (Windows)
REM Run from project root with Docker Compose running
REM =============================================================

echo ============================================================
echo  Climate Anomaly Engine - Full Pipeline (Windows)
echo ============================================================

echo.
echo [Step 1/7] Generating seed data (~5GB)...
docker-compose exec spark-master python /opt/scripts/generate_seed_data.py
if %ERRORLEVEL% neq 0 echo WARNING: Seed data generation encountered issues.

echo.
echo [Step 2/7] Uploading seed data to HDFS...
docker-compose exec spark-master spark-submit --master local[1] /opt/scripts/upload_to_hdfs.py
if %ERRORLEVEL% neq 0 echo WARNING: HDFS upload encountered issues.

echo.
echo [Step 3/7] Ingesting raw data into Parquet...
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /opt/spark-jobs/ingestion/ghcn_daily.py stations /climate-data/raw/station-metadata/ghcnd-stations.txt
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /opt/spark-jobs/ingestion/ghcn_daily.py observations /climate-data/raw/ghcn-daily/*.csv
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /opt/spark-jobs/ingestion/era5_reanalysis.py
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /opt/spark-jobs/ingestion/giss_temperature.py

echo.
echo [Step 4/7] Joining datasets and computing rolling statistics...
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /opt/spark-jobs/processing/join_datasets.py
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /opt/spark-jobs/processing/rolling_statistics.py

echo.
echo [Step 5/7] Running STL decomposition...
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /opt/spark-jobs/processing/stl_decomposition.py

echo.
echo [Step 5.5/7] Running Gaps ^& Islands Extreme Events Analysis...
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /opt/spark-jobs/processing/extremes_analysis.py

echo.
echo [Step 6/7] Running anomaly detection and forecasting...
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /opt/spark-jobs/ml/anomaly_detection.py
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /opt/spark-jobs/ml/forecasting.py statistical
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 /opt/spark-jobs/ml/forecasting.py prophet

echo.
echo [Step 7/7] Exporting results to PostGIS...
docker-compose exec spark-master spark-submit --master spark://spark-master:7077 --packages org.postgresql:postgresql:42.7.1 /opt/spark-jobs/processing/export_to_postgis.py all

echo.
echo ============================================================
echo  Pipeline complete!
echo  Frontend: http://localhost:5173
echo  API Docs: http://localhost:8000/docs
echo  Spark UI: http://localhost:8080
echo  HDFS UI:  http://localhost:9870
echo ============================================================
