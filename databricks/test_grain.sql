-- Path: databricks/test_grain.sql
-- Eseguito su: Databricks (workspace retailco, cluster retailco-cluster)
-- Dipendenze: build_gold.py, scd2_merge.py, dim_data.py
-- Descrizione: verifica cinque proprietà fondamentali del modello dati.
--              Tutti i test devono restituire 0 righe (o il valore atteso indicato).
--              Eseguire dopo ogni modifica agli script di build.

-- ── Test 1: grain fact_vendite_giornaliere ──
-- Verifica che la PK (sk_data, sk_prodotto, sk_punto_vendita) non abbia duplicati.
-- Risultato atteso: 0 righe
SELECT sk_data, sk_prodotto, sk_punto_vendita, COUNT(*) AS n
FROM retail_platform.gld_sales.fact_vendite_giornaliere
GROUP BY 1, 2, 3
HAVING n > 1;

-- ── Test 2: integrità referenziale → dim_prodotto ──
-- Verifica che non esistano FK orfane verso dim_prodotto.
-- Risultato atteso: 0 righe
SELECT f.sk_prodotto, COUNT(*) AS n
FROM retail_platform.gld_sales.fact_vendite_giornaliere f
LEFT JOIN retail_platform.slv_sales.dim_prodotto d
  ON f.sk_prodotto = d.sk_prodotto
WHERE d.sk_prodotto IS NULL
GROUP BY 1;

-- ── Test 3: riconciliazione importi Bronze vs Gold ──
-- Verifica che la somma degli importi al Gold coincida con il Bronze.
-- Risultato atteso: delta = 0.00
WITH brz AS (
    SELECT SUM(CAST(importo_riga AS DECIMAL(12,2))) AS tot_brz
    FROM retail_platform.brz_sales.vendite_raw
),
gld AS (
    SELECT SUM(importo_lordo) AS tot_gld
    FROM retail_platform.gld_sales.fact_vendite_giornaliere
)
SELECT brz.tot_brz, gld.tot_gld,
       ABS(brz.tot_brz - gld.tot_gld) AS delta
FROM brz CROSS JOIN gld;

-- ── Test 4: SCD2 — 1 record corrente per prodotto ──
-- Verifica che ogni prodotto abbia esattamente 1 versione corrente.
-- Risultato atteso: 0 righe
SELECT cod_prodotto, COUNT(*) AS n_current
FROM retail_platform.slv_sales.dim_prodotto
WHERE is_current = true
GROUP BY 1
HAVING n_current != 1;

-- ── Test 5: completezza dim_data 2023-2024 ──
-- Il 2024 è bisestile: 365 + 366 = 731 giorni.
-- Risultato atteso: 731
SELECT COUNT(*) AS n_giorni
FROM retail_platform.gld_sales.dim_data
WHERE anno BETWEEN 2023 AND 2024;
