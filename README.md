# DWH From Scratch

Hands-on completo per costruire un data warehouse a tre layer — **Bronze → Silver → Gold** — per **RetailCo**, un retailer alimentare italiano (scenario sintetico). Sorgente PostgreSQL, destinazione Databricks su AWS con Unity Catalog.

---

## Struttura del progetto

```
dwh_from_scratch/
├── .gitignore                     # .venv/, contenuto di data/, cache Python
├── data/                          # CSV generati — il contenuto è gitignorato
│   └── .gitkeep                   # tiene la cartella nel repo (i CSV no)
├── databricks/                    # script che girano su Databricks
│   ├── ddl_bronze.sql             # DDL catalog, schema e tabelle Bronze
│   ├── ddl_silver.sql             # DDL schemi Silver e dimensioni SCD2
│   ├── ddl_gold.sql               # DDL schemi Gold, fact e dim_cliente
│   ├── ingest_bronze.py           # ingestion CSV → Bronze Delta Lake
│   ├── build_silver.py            # dedup, typing Bronze → Silver
│   ├── scd2_merge.py              # SCD Type 2 per dim_prodotto e dim_punto_vendita
│   ├── build_gold.py              # fact_vendite_giornaliere e dim_cliente
│   ├── dim_data.py                # generazione dim_data 2020-2030
│   └── test_grain.sql             # 5 test di verifica del modello
├── docs/
│   └── adr/
│       └── ADR-001.md             # decisione Kimball vs Data Vault
├── src/
│   └── modeling/
│       └── generate_data.py       # generatore dati sintetici RetailCo
├── LICENSE
├── pyproject.toml                 # dipendenze Python (uv)
├── setup_postgresql.yaml          # Docker Compose PostgreSQL
├── uv.lock
├── README.md                      # questo file
└── README-databricks-setup.md     # setup Databricks su AWS
```

---

## Prerequisiti

- Docker Desktop con WSL2
- Python 3.11+
- [uv](https://astral.sh/uv) — gestore ambienti Python
- Account AWS con Databricks workspace `retailco` configurato
  (vedere `README-databricks-setup.md`)

---

## Setup ambiente locale

### 1. Clona il repository

```powershell
git clone https://github.com/rtgreart/dwh_from_scratch.git
cd dwh_from_scratch
```

### 2. Virtual environment

```powershell
uv sync
.venv\Scripts\activate
```

### 3. PostgreSQL

```powershell
docker compose -f setup_postgresql.yaml up -d
```

Verifica:

```powershell
docker exec postgres-source psql -U retail -d retail_oltp -c "\l"
```

---

## Step 1 — Generazione dati sintetici

Popola il database PostgreSQL con i dati RetailCo:

```powershell
python src/modeling/generate_data.py
```

Output atteso — il seed è fisso (`42`), quindi i conteggi sono esatti e
identici a ogni esecuzione:

```
Generazione dati RetailCo...
  Caricamento punti_vendita...         50 righe
  Caricamento prodotti...             500 righe
  Caricamento clienti...           10,000 righe
  Caricamento ordini...           100,000 righe
  Caricamento vendite...          305,729 righe
Done.
```

Verifica stagionalità:

```powershell
docker exec postgres-source psql -U retail -d retail_oltp -c \
  "SELECT date_trunc('month', data_ordine::date), COUNT(*) FROM ordini GROUP BY 1 ORDER BY 1"
```

---

## Step 2 — Bronze

### Esportazione CSV da PostgreSQL

```powershell
docker exec postgres-source psql -U retail -d retail_oltp -c "\copy ordini TO '/tmp/ordini.csv' CSV HEADER"
docker exec postgres-source psql -U retail -d retail_oltp -c "\copy vendite TO '/tmp/vendite.csv' CSV HEADER"
docker exec postgres-source psql -U retail -d retail_oltp -c "\copy clienti TO '/tmp/clienti.csv' CSV HEADER"
docker exec postgres-source psql -U retail -d retail_oltp -c "\copy prodotti TO '/tmp/prodotti.csv' CSV HEADER"
docker exec postgres-source psql -U retail -d retail_oltp -c "\copy punti_vendita TO '/tmp/punti_vendita.csv' CSV HEADER"

docker cp postgres-source:/tmp/ordini.csv .\data\
docker cp postgres-source:/tmp/vendite.csv .\data\
docker cp postgres-source:/tmp/clienti.csv .\data\
docker cp postgres-source:/tmp/prodotti.csv .\data\
docker cp postgres-source:/tmp/punti_vendita.csv .\data\
```

I CSV finiscono in `data/`, che git ignora (vedi *Note architetturali*).

### Caricamento su S3

Carica tutti i CSV su S3 nel path:

```
s3://<S3-BUCKET>/unity-catalog/<WORKSPACE-ID>/landing/
```

### Esecuzione su Databricks

Esegui in ordine su Databricks:

1. `databricks/ddl_bronze.sql`
2. `databricks/ingest_bronze.py`

---

## Step 3 — Silver

Esegui in ordine su Databricks:

1. `databricks/ddl_silver.sql`
2. `databricks/build_silver.py`
3. `databricks/scd2_merge.py`

---

## Step 4 — Gold

Esegui in ordine su Databricks:

1. `databricks/ddl_gold.sql`
2. `databricks/build_gold.py`
3. `databricks/dim_data.py`

---

## Step 5 — Test di verifica

Esegui su Databricks:

```
databricks/test_grain.sql
```

Risultati attesi:

| Test | Descrizione | Atteso |
|------|-------------|--------|
| 1 | Grain fact (zero duplicati PK) | 0 righe |
| 2 | FK orfane verso dim_prodotto | 0 righe |
| 3 | Riconciliazione Bronze vs Gold | delta = 0.00 |
| 4 | SCD2 — 1 record corrente per prodotto | 0 righe |
| 5 | dim_data copre 2023-2024 | 731 righe |

---

## Configurazione PostgreSQL

| Parametro | Valore |
|-----------|--------|
| Host | localhost |
| Porta | 5432 |
| Database | retail_oltp |
| Utente | retail |
| Password | retail |
| Container | postgres-source |
| Immagine | postgres:16 |

---

## Configurazione Databricks

| Parametro | Valore |
|-----------|--------|
| Workspace | retailco |
| Regione AWS | eu-west-1 |
| Cluster | retailco-cluster |
| Node type | i3.xlarge, Single node |
| Runtime | 17.3 LTS (Spark 4.0) |
| Terminate after | 20 minuti |

Per il setup completo del workspace Databricks su AWS vedere
`README-databricks-setup.md`.

---

## Dipendenze Python

Dichiarate in `pyproject.toml`, gestite con `uv`.

**Runtime** (`dependencies`):

| Pacchetto | Uso |
|-----------|-----|
| faker | Generazione dati sintetici italiani (locale `it_IT`) |
| psycopg2-binary | Caricamento dati in PostgreSQL via `COPY FROM` |

**Sviluppo** (`dependency-groups.dev`):

| Pacchetto | Uso |
|-----------|-----|
| pytest | Framework di test |
| pyspark | Esecuzione e test in locale delle trasformazioni Spark |

Gli script in `databricks/` girano sul cluster, dove Spark è fornito dal
runtime: `pyspark` serve solo per provarli in locale.

---

## Note architetturali

- I CSV in `data/` sono ignorati da git (`.gitignore`): sono dati
  **generati**, riproducibili in qualsiasi momento con `generate_data.py`
  (seed fisso). La cartella resta versionata grazie a `data/.gitkeep`.
- Sostituire `<S3-BUCKET>` e `<WORKSPACE-ID>` con i valori reali nei file
  in `databricks/`.
- Il cluster Databricks si spegne dopo 20 minuti di inattività.
- Vedere `docs/adr/ADR-001.md` per la motivazione della scelta
  Kimball vs Data Vault.
