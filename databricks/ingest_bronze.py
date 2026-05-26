# Path: databricks/ingest_bronze.py
# Eseguito su: Databricks (workspace retailco, cluster retailco-cluster)
# Dipendenze: ddl_bronze.sql (tabelle brz_sales.ordini_raw, brz_sales.vendite_raw)
# Descrizione: legge i CSV dalla landing zone S3 e scrive nelle tabelle
#              Bronze Delta Lake con metadata di tracciabilità.
#
# I CSV sono esportati da PostgreSQL e caricati su S3 nel path registrato
# come External Location in Unity Catalog (vedere README.md).
# mode("append"): ogni esecuzione aggiunge un batch.
# La deduplicazione è responsabilità del layer Silver.

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, lit
import uuid

spark = SparkSession.builder.getOrCreate()
batch_id = str(uuid.uuid4())[:8]

BASE_PATH = "s3://<S3-BUCKET>/unity-catalog/<WORKSPACE-ID>/landing"

for table_name, s3_path, target in [
    (
        "ordini",
        f"{BASE_PATH}/ordini.csv",
        "retail_platform.brz_sales.ordini_raw",
    ),
    (
        "vendite",
        f"{BASE_PATH}/vendite.csv",
        "retail_platform.brz_sales.vendite_raw",
    ),
]:
    # ❶ Lettura CSV con header dalla landing zone S3
    df_source = spark.read.option("header", "true").csv(s3_path)

    # ❷ Cast a STRING + metadati di ingestione
    df = (
        df_source
        .select([col(c).cast("string").alias(c) for c in df_source.columns])
        .withColumn("_ingestion_ts", current_timestamp())
        .withColumn("_source_file", lit(f"postgres-source/{table_name}"))
        .withColumn("_batch_id", lit(batch_id))
    )

    # ❸ Append nella tabella Bronze Delta
    df.write.mode("append").saveAsTable(target)
    print(f"  {table_name}: {df.count():>10,} righe caricate")
