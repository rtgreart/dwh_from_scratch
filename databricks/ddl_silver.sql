-- Path: databricks/ddl_silver.sql
-- Eseguito su: Databricks (workspace retailco, cluster retailco-cluster)
-- Dipendenze: ddl_bronze.sql (catalog retail_platform già esistente)
-- Descrizione: crea gli schemi Silver slv_sales e slv_customer con le tabelle
--              normalizzate, tipizzate e con SCD Type 2 per le dimensioni.

-- ── Schemi Silver ──
CREATE SCHEMA IF NOT EXISTS retail_platform.slv_sales;
CREATE SCHEMA IF NOT EXISTS retail_platform.slv_customer;

-- ── Ordini (grain: 1 ordine) ──
-- data_ordine tipizzata a DATE (era STRING al Bronze)
-- delta.enableChangeDataFeed: abilita il Change Data Feed per CDC downstream
CREATE TABLE IF NOT EXISTS retail_platform.slv_sales.ordini (
    order_id        STRING NOT NULL,
    pos_id          STRING NOT NULL,
    codice_fiscale  STRING,
    data_ordine     DATE NOT NULL,
    ora_ordine      STRING,
    _ingestion_ts   TIMESTAMP,
    _batch_id       STRING,
    CONSTRAINT pk_ordini PRIMARY KEY (order_id)
)
USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

-- ── Vendite (grain: 1 order-line) ──
-- line_num e quantita tipizzati a INT
-- importi tipizzati a DECIMAL(10,2) per evitare errori di arrotondamento
CREATE TABLE IF NOT EXISTS retail_platform.slv_sales.vendite (
    order_id         STRING NOT NULL,
    line_num         INT NOT NULL,
    cod_prodotto     STRING NOT NULL,
    quantita         INT NOT NULL,
    prezzo_unitario  DECIMAL(10,2),
    importo_riga     DECIMAL(10,2),
    _ingestion_ts    TIMESTAMP,
    _batch_id        STRING,
    CONSTRAINT pk_vendite PRIMARY KEY (order_id, line_num)
)
USING DELTA;

-- ── Clienti (grain: 1 cliente) ──
CREATE TABLE IF NOT EXISTS retail_platform.slv_customer.clienti (
    codice_fiscale     STRING NOT NULL,
    nome               STRING,
    cognome            STRING,
    email              STRING,
    telefono           STRING,
    citta              STRING,
    provincia          STRING,
    tessera_fedelta    STRING,
    data_registrazione DATE,
    _ingestion_ts      TIMESTAMP,
    CONSTRAINT pk_clienti PRIMARY KEY (codice_fiscale)
)
USING DELTA;

-- ── dim_prodotto (SCD Type 2) ──
-- Attributi SCD2: nome, categoria, iva_perc → tracciati storicamente
-- Attributi SCD1: prezzo_unitario → sovrascritto in place
-- _hash_diff: SHA-256 degli attributi SCD2 per rilevare cambiamenti
-- sk_prodotto: surrogate key generata automaticamente (IDENTITY)
CREATE TABLE IF NOT EXISTS retail_platform.slv_sales.dim_prodotto (
    sk_prodotto       BIGINT GENERATED ALWAYS AS IDENTITY,
    cod_prodotto      STRING NOT NULL,
    nome              STRING,
    categoria         STRING,
    prezzo_unitario   DECIMAL(10,2),
    iva_perc          INT,
    valid_from        TIMESTAMP NOT NULL,
    valid_to          TIMESTAMP,          -- NULL = record corrente
    is_current        BOOLEAN,
    _hash_diff        STRING
)
USING DELTA;

-- ── dim_punto_vendita (SCD Type 2) ──
-- Attributi SCD2: indirizzo, cluster, manager → tracciati storicamente
-- Attributi SCD1: telefono → sovrascritto in place
CREATE TABLE IF NOT EXISTS retail_platform.slv_sales.dim_punto_vendita (
    sk_punto_vendita  BIGINT GENERATED ALWAYS AS IDENTITY,
    pos_id            STRING NOT NULL,
    nome              STRING,
    indirizzo         STRING,
    cluster           STRING,
    regione           STRING,
    manager           STRING,
    telefono          STRING,
    data_apertura     DATE,
    valid_from        TIMESTAMP NOT NULL,
    valid_to          TIMESTAMP,
    is_current        BOOLEAN,
    _hash_diff        STRING
)
USING DELTA;

-- ── Verifica ──
SHOW TABLES IN retail_platform.slv_sales;
SHOW TABLES IN retail_platform.slv_customer;
