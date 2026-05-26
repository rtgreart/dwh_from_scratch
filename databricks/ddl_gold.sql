-- Path: databricks/ddl_gold.sql
-- Eseguito su: Databricks (workspace retailco, cluster retailco-cluster)
-- Dipendenze: ddl_silver.sql (catalog retail_platform già esistente)
-- Descrizione: crea gli schemi Gold gld_sales e gld_customer con la fact
--              table e le dimensioni conformate dello star schema Kimball.

-- ── Schemi Gold ──
CREATE SCHEMA IF NOT EXISTS retail_platform.gld_sales;
CREATE SCHEMA IF NOT EXISTS retail_platform.gld_customer;

-- ── Fact: vendite giornaliere ──
-- Grain: pos × prodotto × giorno
-- sk_cliente: nullable — non fa parte del grain giornaliero
-- sk_data: INT formato YYYYMMDD (compatto, ordinabile, leggibile senza JOIN)
-- PARTITIONED BY (sk_data): ottimizza le query BI che filtrano per periodo
CREATE TABLE IF NOT EXISTS retail_platform.gld_sales.fact_vendite_giornaliere (
    sk_data            INT NOT NULL,
    sk_prodotto        BIGINT NOT NULL,
    sk_punto_vendita   BIGINT NOT NULL,
    sk_cliente         BIGINT,
    n_transazioni      INT NOT NULL,
    quantita_totale    INT NOT NULL,
    importo_lordo      DECIMAL(12,2) NOT NULL,
    importo_netto      DECIMAL(12,2),
    sconto_totale      DECIMAL(12,2),
    CONSTRAINT pk_fact PRIMARY KEY (sk_data, sk_prodotto, sk_punto_vendita)
)
USING DELTA
PARTITIONED BY (sk_data);

-- ── Dim: cliente ──
-- segmento: placeholder per segmentazione ML (Parte VIII)
-- riga sentinel (codice_fiscale='UNKNOWN') inserita da build_gold.py
CREATE TABLE IF NOT EXISTS retail_platform.gld_customer.dim_cliente (
    sk_cliente         BIGINT GENERATED ALWAYS AS IDENTITY,
    codice_fiscale     STRING NOT NULL,
    nome               STRING,
    cognome            STRING,
    citta              STRING,
    provincia          STRING,
    tessera_fedelta    STRING,
    segmento           STRING,
    data_registrazione DATE,
    CONSTRAINT pk_dim_cliente PRIMARY KEY (sk_cliente)
)
USING DELTA;

-- ── Verifica ──
SHOW TABLES IN retail_platform.gld_sales;
SHOW TABLES IN retail_platform.gld_customer;
