# Path: databricks/dim_data.py
# Eseguito su: Databricks (workspace retailco, cluster retailco-cluster)
# Dipendenze: ddl_gold.sql (schema gld_sales già esistente)
# Descrizione: genera la dimensione data per il range 2020-2030 e la scrive
#              nella tabella gld_sales.dim_data in Delta Lake.
#
# sk_data: INT formato YYYYMMDD — compatto, ordinabile, leggibile senza JOIN
#          (es. 20241225 = Natale 2024)
# anno_fiscale: anno fiscale RetailCo inizia a luglio
#               (gennaio 2024 → anno fiscale 2023)
# ponte_flag: lunedì dopo festività o venerdì prima di festività
#             correlato con picchi di spesa alimentare in RetailCo
# Range 2020-2030: copre dati storici ERP (Parte IV) e proiezioni future
# Festività mobili (Pasqua): non incluse in questa versione base

from datetime import date, timedelta
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

FESTIVITA_FISSE = {
    (1,  1):  "Capodanno",
    (1,  6):  "Epifania",
    (4,  25): "Liberazione",
    (5,  1):  "Lavoro",
    (6,  2):  "Repubblica",
    (8,  15): "Ferragosto",
    (11, 1):  "Ognissanti",
    (12, 8):  "Immacolata",
    (12, 25): "Natale",
    (12, 26): "Santo Stefano",
}


def is_ponte(d: date, festivita_set: set) -> bool:
    """Lunedì adiacente a festività di domenica o venerdì adiacente a festività di sabato."""
    if d.weekday() == 0:
        return (d - timedelta(days=1)) in festivita_set
    if d.weekday() == 4:
        return (d + timedelta(days=1)) in festivita_set
    return False


def genera_dim_data(start_year: int = 2020, end_year: int = 2030) -> list[dict]:
    """Genera una riga per ogni giorno nel range [start_year, end_year]."""
    rows = []
    festivita_dates = set()
    for y in range(start_year, end_year + 1):
        for (m, g), _ in FESTIVITA_FISSE.items():
            festivita_dates.add(date(y, m, g))

    d = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    while d <= end:
        rows.append({
            "sk_data":          int(d.strftime("%Y%m%d")),
            "data":             d.isoformat(),
            "giorno":           d.day,
            "mese":             d.month,
            "anno":             d.year,
            "trimestre":        (d.month - 1) // 3 + 1,
            "settimana_iso":    int(d.isocalendar()[1]),
            "giorno_settimana": d.strftime("%A"),
            "nome_mese":        d.strftime("%B"),
            "festivo_flag":     d in festivita_dates,
            "ponte_flag":       is_ponte(d, festivita_dates),
            "weekend_flag":     d.weekday() >= 5,
            "anno_fiscale":     d.year if d.month >= 7 else d.year - 1,
        })
        d += timedelta(days=1)
    return rows


rows = genera_dim_data(2020, 2030)
df = spark.createDataFrame(rows)
df.write.mode("overwrite").saveAsTable("retail_platform.gld_sales.dim_data")
print(f"  dim_data: {spark.table('retail_platform.gld_sales.dim_data').count():>10,} righe")
