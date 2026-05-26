# Path: databricks/scd2_merge.py
# Eseguito su: Databricks (workspace retailco, cluster retailco-cluster)
# Dipendenze: ddl_silver.sql, build_silver.py
# Descrizione: implementa SCD Type 2 con MERGE INTO per dim_prodotto
#              e dim_punto_vendita usando un pattern a due passaggi.
#
# Pattern a due passaggi:
# Passaggio 1 — MERGE:
#   - WHEN MATCHED AND hash != → chiude il record corrente
#                                (valid_to = now, is_current = false)
#   - WHEN MATCHED AND hash == → aggiorna attributi SCD1 in place
#   - WHEN NOT MATCHED         → inserisce nuovo record corrente
#
# Passaggio 2 — INSERT:
#   Inserisce la nuova versione corrente per i record chiusi nel Passaggio 1
#   che non hanno ancora un is_current = true.
#
# _hash_diff: SHA-256 degli attributi SCD2 — confronto in O(1) invece di O(N colonne)
# Idempotenza: eseguire N volte con gli stessi dati produce lo stesso risultato.

from pyspark.sql import SparkSession, functions as F

spark = SparkSession.builder.getOrCreate()

BASE_PATH = "s3://<S3-BUCKET>/unity-catalog/<WORKSPACE-ID>/landing"

# ════════════════════════════════════════════════════════
# dim_prodotto
# SCD2: nome, categoria, iva_perc
# SCD1: prezzo_unitario (sovrascritto in place)
# ════════════════════════════════════════════════════════

incoming_prodotti = (spark.read.option("header", "true")
    .csv(f"{BASE_PATH}/prodotti.csv")
    .withColumn("prezzo_unitario", F.col("prezzo_unitario").cast("decimal(10,2)"))
    .withColumn("iva_perc", F.col("iva_perc").cast("int"))
    .withColumn("_hash_diff",
        F.sha2(F.concat_ws("||",
            F.col("nome"), F.col("categoria"),
            F.col("iva_perc").cast("string")
        ), 256))
)
incoming_prodotti.createOrReplaceTempView("incoming_prodotti")

# ── Passaggio 1: MERGE ──
spark.sql("""
MERGE INTO retail_platform.slv_sales.dim_prodotto AS tgt
USING incoming_prodotti AS src
ON tgt.cod_prodotto = src.cod_prodotto AND tgt.is_current = true

WHEN MATCHED AND tgt._hash_diff != src._hash_diff THEN
  UPDATE SET tgt.valid_to = current_timestamp(), tgt.is_current = false

WHEN MATCHED AND tgt._hash_diff = src._hash_diff THEN
  UPDATE SET tgt.prezzo_unitario = src.prezzo_unitario

WHEN NOT MATCHED THEN INSERT (
    cod_prodotto, nome, categoria, prezzo_unitario, iva_perc,
    valid_from, valid_to, is_current, _hash_diff
) VALUES (
    src.cod_prodotto, src.nome, src.categoria,
    src.prezzo_unitario, src.iva_perc,
    current_timestamp(), NULL, true, src._hash_diff
)
""")

# ── Passaggio 2: INSERT nuove versioni per record chiusi ──
spark.sql("""
INSERT INTO retail_platform.slv_sales.dim_prodotto (
    cod_prodotto, nome, categoria, prezzo_unitario, iva_perc,
    valid_from, valid_to, is_current, _hash_diff
)
SELECT
    src.cod_prodotto, src.nome, src.categoria,
    src.prezzo_unitario, src.iva_perc,
    current_timestamp(), NULL, true, src._hash_diff
FROM incoming_prodotti src
WHERE NOT EXISTS (
    SELECT 1 FROM retail_platform.slv_sales.dim_prodotto tgt
    WHERE tgt.cod_prodotto = src.cod_prodotto
    AND tgt.is_current = true
)
""")

print(f"  dim_prodotto: {spark.table('retail_platform.slv_sales.dim_prodotto').count():>10,} righe")

# ════════════════════════════════════════════════════════
# dim_punto_vendita
# SCD2: indirizzo, cluster, manager
# SCD1: telefono (sovrascritto in place)
# ════════════════════════════════════════════════════════

incoming_pv = (spark.read.option("header", "true")
    .csv(f"{BASE_PATH}/punti_vendita.csv")
    .withColumn("data_apertura", F.col("data_apertura").cast("date"))
    .withColumn("_hash_diff",
        F.sha2(F.concat_ws("||",
            F.col("indirizzo"), F.col("cluster"), F.col("manager")
        ), 256))
)
incoming_pv.createOrReplaceTempView("incoming_pv")

# ── Passaggio 1: MERGE ──
spark.sql("""
MERGE INTO retail_platform.slv_sales.dim_punto_vendita AS tgt
USING incoming_pv AS src
ON tgt.pos_id = src.pos_id AND tgt.is_current = true

WHEN MATCHED AND tgt._hash_diff != src._hash_diff THEN
  UPDATE SET tgt.valid_to = current_timestamp(), tgt.is_current = false

WHEN MATCHED AND tgt._hash_diff = src._hash_diff THEN
  UPDATE SET tgt.telefono = src.telefono

WHEN NOT MATCHED THEN INSERT (
    pos_id, nome, indirizzo, cluster, regione, manager,
    telefono, data_apertura, valid_from, valid_to, is_current, _hash_diff
) VALUES (
    src.pos_id, src.nome, src.indirizzo, src.cluster,
    src.regione, src.manager, src.telefono, src.data_apertura,
    current_timestamp(), NULL, true, src._hash_diff
)
""")

# ── Passaggio 2: INSERT nuove versioni per record chiusi ──
spark.sql("""
INSERT INTO retail_platform.slv_sales.dim_punto_vendita (
    pos_id, nome, indirizzo, cluster, regione, manager,
    telefono, data_apertura, valid_from, valid_to, is_current, _hash_diff
)
SELECT
    src.pos_id, src.nome, src.indirizzo, src.cluster,
    src.regione, src.manager, src.telefono, src.data_apertura,
    current_timestamp(), NULL, true, src._hash_diff
FROM incoming_pv src
WHERE NOT EXISTS (
    SELECT 1 FROM retail_platform.slv_sales.dim_punto_vendita tgt
    WHERE tgt.pos_id = src.pos_id
    AND tgt.is_current = true
)
""")

print(f"  dim_punto_vendita: {spark.table('retail_platform.slv_sales.dim_punto_vendita').count():>10,} righe")
