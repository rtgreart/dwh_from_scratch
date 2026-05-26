# Path: databricks/build_silver.py
# Eseguito su: Databricks (workspace retailco, cluster retailco-cluster)
# Dipendenze: ddl_silver.sql, ingest_bronze.py (tabelle Bronze popolate)
# Descrizione: legge dal Bronze, deduplica per PK, applica typing e scrive
#              al Silver per ordini, vendite e clienti.

from pyspark.sql import SparkSession, functions as F, Window

spark = SparkSession.builder.getOrCreate()

BASE_PATH = "s3://<S3-BUCKET>/unity-catalog/<WORKSPACE-ID>/landing"


def dedup_and_type(source_table, target_table, pk_cols, type_map):
    """
    Deduplica per PK e applica il typing.

    - ROW_NUMBER partizionato su pk_cols, ordinato per _ingestion_ts DESC
      → tiene il record più recente in caso di duplicati cross-batch
    - Drop di _source_file: colonna Bronze non presente nel DDL Silver
    - Il cast da STRING a tipo concreto è il primo punto dove emergono
      errori di formato (es. date malformate → NULL)
    """
    raw = spark.table(source_table)
    w = Window.partitionBy(*pk_cols).orderBy(F.col("_ingestion_ts").desc())
    deduped = (raw
        .withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
        .drop("_source_file"))

    typed = deduped
    for col_name, col_type in type_map.items():
        typed = typed.withColumn(col_name, F.col(col_name).cast(col_type))

    typed.write.mode("overwrite").saveAsTable(target_table)
    count = spark.table(target_table).count()
    print(f"  {target_table}: {count:>10,} righe")
    return typed


# ── Ordini ──
dedup_and_type(
    "retail_platform.brz_sales.ordini_raw",
    "retail_platform.slv_sales.ordini",
    pk_cols=["order_id"],
    type_map={"data_ordine": "date"},
)

# ── Vendite ──
# DECIMAL(10,2) evita errori di arrotondamento float sugli importi monetari
dedup_and_type(
    "retail_platform.brz_sales.vendite_raw",
    "retail_platform.slv_sales.vendite",
    pk_cols=["order_id", "line_num"],
    type_map={
        "line_num":        "int",
        "quantita":        "int",
        "prezzo_unitario": "decimal(10,2)",
        "importo_riga":    "decimal(10,2)",
    },
)

# ── Clienti (da CSV su S3) ──
# Caricati direttamente da S3 senza passare dal Bronze.
# Nella Parte II, con l'aggiunta del CRM, confluiranno nel Bronze
# per gestire la riconciliazione cross-source.
clienti_raw = (spark.read.option("header", "true")
    .csv(f"{BASE_PATH}/clienti.csv")
    .withColumn("data_registrazione", F.col("data_registrazione").cast("date"))
    .withColumn("_ingestion_ts", F.current_timestamp())
    .dropDuplicates(["codice_fiscale"]))

clienti_raw.write.mode("overwrite").saveAsTable("retail_platform.slv_customer.clienti")
print(f"  clienti: {clienti_raw.count():>10,} righe")
