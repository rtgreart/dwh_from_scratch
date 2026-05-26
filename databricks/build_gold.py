# Path: databricks/build_gold.py
# Eseguito su: Databricks (workspace retailco, cluster retailco-cluster)
# Dipendenze: ddl_gold.sql, build_silver.py, scd2_merge.py
# Descrizione: popola il layer Gold con dim_cliente e fact_vendite_giornaliere.
#
# Grain fact_vendite_giornaliere: pos × prodotto × giorno
# sk_cliente NON fa parte del grain: includendolo nel groupBy si violerebbe
# la PK (sk_data, sk_prodotto, sk_punto_vendita) producendo duplicati
# per stesso giorno/prodotto/POS con clienti diversi.
# Per analisi a livello cliente usare una fact a grain order-line.
#
# importo_netto: importo_lordo / 1.10 (IVA media 10%)
# Nel Cap. 10 verrà sostituito con l'IVA specifica per prodotto.

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import StructType, StructField, StringType, DateType

spark = SparkSession.builder.getOrCreate()

# ── dim_cliente con riga sentinel ──
# La riga sentinel rappresenta il cliente sconosciuto (acquisti senza tessera).
# Schema esplicito necessario per la corretta inferenza dei tipi sui campi None.
schema = StructType([
    StructField("codice_fiscale",     StringType(), True),
    StructField("nome",               StringType(), True),
    StructField("cognome",            StringType(), True),
    StructField("citta",              StringType(), True),
    StructField("provincia",          StringType(), True),
    StructField("tessera_fedelta",    StringType(), True),
    StructField("segmento",           StringType(), True),
    StructField("data_registrazione", DateType(),   True),
])

sentinel = spark.createDataFrame(
    [("UNKNOWN", "Sconosciuto", "Sconosciuto", None, None, None, "sconosciuto", None)],
    schema=schema
)

dim_cliente = (spark.table("retail_platform.slv_customer.clienti")
    .select("codice_fiscale", "nome", "cognome", "citta",
            "provincia", "tessera_fedelta", "data_registrazione")
    .withColumn("segmento", F.lit("standard"))
    .unionByName(sentinel, allowMissingColumns=True))

dim_cliente.write.mode("overwrite").saveAsTable("retail_platform.gld_customer.dim_cliente")
print(f"  dim_cliente: {spark.table('retail_platform.gld_customer.dim_cliente').count():>10,} righe")

# ── fact_vendite_giornaliere ──
fact = (
    spark.table("retail_platform.slv_sales.vendite")
    .join(spark.table("retail_platform.slv_sales.ordini"), on="order_id")
    .join(
        spark.table("retail_platform.slv_sales.dim_prodotto")
            .filter(F.col("is_current") == True),
        on="cod_prodotto"
    )
    .join(
        spark.table("retail_platform.slv_sales.dim_punto_vendita")
            .filter(F.col("is_current") == True),
        on="pos_id"
    )
    .withColumn("sk_data",
        F.date_format(F.col("data_ordine"), "yyyyMMdd").cast("int"))
    .groupBy("sk_data", "sk_prodotto", "sk_punto_vendita")
    .agg(
        F.countDistinct("order_id").cast("int").alias("n_transazioni"),
        F.sum("quantita").cast("int").alias("quantita_totale"),
        F.sum("importo_riga").cast("decimal(12,2)").alias("importo_lordo"),
    )
    .withColumn("sk_cliente", F.lit(None).cast("long"))
    .withColumn("importo_netto",
        F.round(F.col("importo_lordo") / F.lit(1.10), 2).cast("decimal(12,2)"))
    .withColumn("sconto_totale", F.lit(0).cast("decimal(12,2)"))
)

fact.write.mode("overwrite").saveAsTable(
    "retail_platform.gld_sales.fact_vendite_giornaliere"
)
print(f"  fact_vendite_giornaliere: {spark.table('retail_platform.gld_sales.fact_vendite_giornaliere').count():>10,} righe")
