FROM bitnami/spark:3.5.1

USER root

RUN pip install --no-cache-dir \
    pyspark==3.5.1 \
    pyarrow>=14.0.0 \
    pandas>=2.0.0 \
    numpy>=1.24.0 \
    scipy>=1.11.0 \
    scikit-learn>=1.3.0 \
    statsmodels>=0.14.0 \
    prophet>=1.1.5 \
    python-geohash>=0.8.5 \
    requests>=2.31.0 \
    psycopg2-binary>=2.9.9 \
    sqlalchemy>=2.0.0 \
    geoalchemy2>=0.14.0

COPY core-site.xml /opt/bitnami/spark/conf/core-site.xml
COPY hdfs-site.xml /opt/bitnami/spark/conf/hdfs-site.xml

WORKDIR /opt/spark-jobs
