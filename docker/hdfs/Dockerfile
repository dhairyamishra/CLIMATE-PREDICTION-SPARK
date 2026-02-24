FROM apache/hadoop:3.3.6

USER root

RUN mkdir -p /opt/hadoop/data/namenode /opt/hadoop/data/datanode

COPY core-site.xml /opt/hadoop/etc/hadoop/core-site.xml
COPY hdfs-site.xml /opt/hadoop/etc/hadoop/hdfs-site.xml

ENV HADOOP_HOME=/opt/hadoop
ENV PATH=$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$PATH

EXPOSE 9870 9000 9864 9866
