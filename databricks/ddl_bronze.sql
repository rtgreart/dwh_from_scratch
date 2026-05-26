-- Path: databricks/ddl_bronze.sql
-- Eseguito su: Databricks (workspace retailco, cluster retailco-cluster)
-- Dipendenze: nessuna (primo step della pipeline)
-- Descrizione: crea il catalog retail_platform, lo schema Bronze brz_sales
--              e le tabelle grezze ordini_raw e vendite_raw in Delta Lake.

-- ── Catalog ──
-- MANAGED LOCATION richiesta da Unity Catalog su AWS quando il workspace
-- è configurato con credenziali AWS proprie (no metastore root di default)
CREATE CATALOG IF NOT EXISTS retail_platform
MANAGED LOCATION 's3://<S3-BUCKET>/unity-catalog/<WORKSPACE-ID>';

-- ── Schema Bronze ──
CREATE SCHEMA IF NOT EXISTS retail_platform.brz_sales;

-- ── Tabella ordini grezzi ──
-- Grain: 1 riga per ordine
-- Tutte le colonne STRING: schema-on-read, nessuna assunzione sui tipi
-- Il typing avviene al layer Silver
-- _ingestion_ts: timestamp di ingestion (popolato da ingest_bronze.py)
-- _source_file:  sorgente di provenienza (popolato da ingest_bronze.py)
-- _batch_id:     UUID del batch di ingestion (popolato da ingest_bronze.py)
CREATE TABLE IF NOT EXISTS retail_platform.brz_sales.ordini_raw (
    order_id        STRING,
    pos_id          STRING,
    codice_fiscale  STRING,
    data_ordine     STRING,
    ora_ordine      STRING,
    _ingestion_ts   TIMESTAMP,
    _source_file    STRING,
    _batch_id       STRING
)
USING DELTA;

-- ── Tabella vendite grezze ──
-- Grain: 1 riga per linea ordine (order_id + line_num)
CREATE TABLE IF NOT EXISTS retail_platform.brz_sales.vendite_raw (
    order_id         STRING,
    line_num         STRING,
    cod_prodotto     STRING,
    quantita         STRING,
    prezzo_unitario  STRING,
    importo_riga     STRING,
    _ingestion_ts    TIMESTAMP,
    _source_file     STRING,
    _batch_id        STRING
)
USING DELTA;

-- ── Verifica ──
SHOW TABLES IN retail_platform.brz_sales;
