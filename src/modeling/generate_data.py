"""RetailCo — Generazione dati sintetici.
Path: src/modeling/generate_data.py

Genera 5 tabelle (punti_vendita, prodotti, clienti, ordini, vendite)
e le carica direttamente in PostgreSQL via COPY FROM.
Seed deterministico (42): ogni esecuzione produce gli stessi dati.
"""
import csv
import io
import random
from datetime import date, timedelta

import psycopg2
from faker import Faker

# ── Inizializzazione Faker con locale italiano e seed fisso ──
fake = Faker("it_IT")
Faker.seed(42)
random.seed(42)

# ── Dimensioni del dataset ──
N_CLIENTI   = 10_000
N_PRODOTTI  = 500       # 20 categorie × 25 prodotti per categoria
N_CATEGORIE = 20
N_POS       = 50
N_ORDINI    = 100_000
DATE_START  = date(2023, 1, 1)
DATE_END    = date(2024, 12, 31)

# ── Cluster regionali ──
# Ogni cluster ha un peso che determina la quota di fatturato generata.
# Il Nord-Ovest produce il 35% degli ordini, le Isole il 5%.
CLUSTER = [
    {"nome": "Nord-Ovest", "regioni": ["MI", "TO", "GE"], "n_pos": 15, "peso": 0.35},
    {"nome": "Nord-Est",   "regioni": ["VE", "UD", "TN"], "n_pos": 10, "peso": 0.22},
    {"nome": "Centro",     "regioni": ["FI", "RM", "PG"], "n_pos": 12, "peso": 0.23},
    {"nome": "Sud",        "regioni": ["NA", "BA", "CZ"], "n_pos":  9, "peso": 0.15},
    {"nome": "Isole",      "regioni": ["PA", "CA"],       "n_pos":  4, "peso": 0.05},
]

# ── Stagionalità mensile ──
# Coefficienti moltiplicativi sul volume ordini.
# Dicembre +30%, agosto -20%, gennaio/febbraio -15%.
STAGIONALITA = {
    1: 0.85, 2: 0.85, 3: 0.95, 4: 1.00, 5: 1.00, 6: 1.05,
    7: 0.95, 8: 0.80, 9: 1.00, 10: 1.05, 11: 1.10, 12: 1.30,
}

# ── Categorie prodotto ──
CATEGORIE = [
    "Frutta", "Verdura", "Latticini", "Carne", "Pesce",
    "Pane", "Pasta", "Bevande", "Surgelati", "Dolci",
    "Pulizia Casa", "Igiene Persona", "Cancelleria", "Pet Food",
    "Snack", "Conserve", "Condimenti", "Cereali", "Vini", "Bio",
]

# ── Aliquote IVA per categoria ──
IVA_MAP = {
    "Vini": 22, "Pulizia Casa": 22, "Cancelleria": 22,
    "Carne": 10, "Pesce": 10,
}
IVA_DEFAULT = 4  # alimentari di base


# ── Generatori ──

def genera_punti_vendita() -> list[dict]:
    """
    Genera N_POS punti vendita distribuiti nei cluster regionali.
    Il pos_id segue il formato IT-{REGIONE}-{NNN} (es. IT-MI-001).
    La regione è scelta casualmente tra quelle del cluster.
    """
    punti = []
    for cluster in CLUSTER:
        for _ in range(cluster["n_pos"]):
            regione = random.choice(cluster["regioni"])
            punti.append({
                "pos_id":         f"IT-{regione}-{len(punti)+1:03d}",
                "nome":           f"RetailCo {fake.city()}",
                "indirizzo":      fake.address().replace("\n", ", "),
                "cluster":        cluster["nome"],
                "regione":        regione,
                "manager":        fake.name(),
                "telefono":       fake.phone_number(),
                "data_apertura":  fake.date_between(
                    start_date=date(2015, 1, 1),
                    end_date=date(2022, 6, 30),
                ).isoformat(),
            })
    return punti


def genera_prodotti() -> list[dict]:
    """
    Genera N_PRODOTTI prodotti (25 per categoria).
    Il prezzo unitario segue una normale troncata tra €0.50 e €45.00
    con media €8.50 e deviazione standard €4.00.
    L'IVA è assegnata per categoria tramite IVA_MAP.
    """
    prodotti = []
    for cat in CATEGORIE:
        for _ in range(N_PRODOTTI // N_CATEGORIE):
            prezzo = round(random.gauss(8.5, 4.0), 2)
            prezzo = max(0.50, min(prezzo, 45.00))  # troncatura
            prodotti.append({
                "cod_prodotto":    f"P-{len(prodotti)+1:05d}",
                "nome":            f"{fake.word().capitalize()} {cat}",
                "categoria":       cat,
                "prezzo_unitario": prezzo,
                "iva_perc":        IVA_MAP.get(cat, IVA_DEFAULT),
            })
    return prodotti


def genera_clienti() -> list[dict]:
    """
    Genera N_CLIENTI clienti con anagrafica italiana sintetica.
    Il 70% ha una tessera fedeltà (TF-{NNN}), il 30% acquista anonimo.
    Il codice_fiscale ha formato valido (16 caratteri) ma non passa
    il check digit — usato come business key, non validato.
    """
    clienti = []
    for i in range(N_CLIENTI):
        ha_tessera = random.random() < 0.70
        clienti.append({
            "codice_fiscale":     fake.ssn(),
            "nome":               fake.first_name(),
            "cognome":            fake.last_name(),
            "email":              fake.email(),
            "telefono":           fake.phone_number(),
            "citta":              fake.city(),
            "provincia":          fake.city_suffix()[:2].upper(),
            "tessera_fedelta":    f"TF-{i+1:06d}" if ha_tessera else None,
            "data_registrazione": fake.date_between(
                start_date=date(2020, 1, 1),
                end_date=DATE_END,
            ).isoformat(),
        })
    return clienti


def genera_ordini(
    clienti: list[dict],
    prodotti: list[dict],
    punti_vendita: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Genera N_ORDINI ordini e le relative righe vendita.

    Logica di assegnazione:
    - Il POS è scelto con peso proporzionale al cluster (random.choices).
    - Il giorno è scelto casualmente; la stagionalità funziona come
      filtro probabilistico: nei mesi deboli alcuni ordini vengono
      'rimbalzati' a una data diversa, riducendone la concentrazione.
    - Il numero di linee per ordine segue una normale troncata [1, 12]
      centrata su 3.5 — coerente con i ~350.000 record vendita attesi.
    - La quantità per riga segue pesi decrescenti [50,25,15,7,3]
      per valori [1,2,3,4,5].
    """
    ordini, vendite = [], []

    # Peso di ogni POS proporzionale al peso del suo cluster
    pesi_pos = []
    for pv in punti_vendita:
        cluster = next(c for c in CLUSTER if c["nome"] == pv["cluster"])
        pesi_pos.append(cluster["peso"] / cluster["n_pos"])

    # Lista di tutti i giorni nel range
    giorni = []
    d = DATE_START
    while d <= DATE_END:
        giorni.append(d)
        d += timedelta(days=1)

    for i in range(N_ORDINI):
        # Stagionalità: nei mesi deboli alcuni ordini vengono rimbalzati
        giorno = random.choice(giorni)
        if random.random() > STAGIONALITA[giorno.month]:
            giorno = random.choice(giorni)

        pos     = random.choices(punti_vendita, weights=pesi_pos, k=1)[0]
        cliente = random.choice(clienti)

        ordini.append({
            "order_id":      f"ORD-{i+1:07d}",
            "pos_id":        pos["pos_id"],
            "codice_fiscale": cliente["codice_fiscale"],
            "data_ordine":   giorno.isoformat(),
            "ora_ordine":    (
                f"{random.randint(8, 21):02d}:"
                f"{random.randint(0, 59):02d}:00"
            ),
        })

        # Righe vendita per questo ordine
        n_linee = max(1, min(12, int(random.gauss(3.5, 1.5))))
        prodotti_scelti = random.sample(prodotti, n_linee)
        for line_num, prod in enumerate(prodotti_scelti, 1):
            qta = random.choices(
                [1, 2, 3, 4, 5],
                weights=[50, 25, 15, 7, 3],
                k=1,
            )[0]
            vendite.append({
                "order_id":       f"ORD-{i+1:07d}",
                "line_num":       line_num,
                "cod_prodotto":   prod["cod_prodotto"],
                "quantita":       qta,
                "prezzo_unitario": prod["prezzo_unitario"],
                "importo_riga":   round(qta * prod["prezzo_unitario"], 2),
            })

    return ordini, vendite


# ── Connessione PostgreSQL ──
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "retail_oltp",
    "user":     "retail",
    "password": "retail",
}


def carica_postgres(nome_tabella: str, righe: list[dict]) -> None:
    """
    Carica una lista di dizionari in PostgreSQL via COPY FROM.

    - Ricrea la tabella a ogni esecuzione (DROP + CREATE con colonne TEXT).
      Il typing corretto è responsabilità del layer Silver, non della sorgente.
    - Usa COPY FROM via StringIO: ordini di grandezza più veloce
      di INSERT riga per riga su 100.000 record.
    - I valori None vengono serializzati come \\N (standard COPY FROM
      PostgreSQL) per preservare la distinzione NULL vs stringa vuota.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

    colonne  = list(righe[0].keys())
    col_defs = ", ".join(f"{c} TEXT" for c in colonne)

    cur.execute(f"DROP TABLE IF EXISTS {nome_tabella}")
    cur.execute(f"CREATE TABLE {nome_tabella} ({col_defs})")

    # Serializzazione in buffer TSV in memoria
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=colonne,
        delimiter="\t",
        lineterminator="\n",
    )
    for r in righe:
        writer.writerow({
            k: (v if v is not None else "\\N")
            for k, v in r.items()
        })

    buf.seek(0)
    cur.copy_from(buf, nome_tabella, columns=colonne, null="\\N")

    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    """
    Punto di ingresso: genera tutti i dataset e li carica in PostgreSQL.
    L'ordine di caricamento rispetta le dipendenze referenziali:
    prima le anagrafiche (punti_vendita, prodotti, clienti),
    poi le transazioni (ordini, vendite).
    """
    print("Generazione dati RetailCo...")

    pv              = genera_punti_vendita()
    pr              = genera_prodotti()
    cl              = genera_clienti()
    ordini, vendite = genera_ordini(cl, pr, pv)

    tabelle = [
        ("punti_vendita", pv),
        ("prodotti",      pr),
        ("clienti",       cl),
        ("ordini",        ordini),
        ("vendite",       vendite),
    ]

    for nome, dati in tabelle:
        print(f"  Caricamento {nome}...", end=" ", flush=True)
        carica_postgres(nome, dati)
        print(f"{len(dati):>10,} righe")

    print("Done.")
