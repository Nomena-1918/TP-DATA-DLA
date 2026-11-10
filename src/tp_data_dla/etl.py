"""Pipeline ETL : extraction en flux, normalisation et chargement dans tp_assurance_etl."""

import csv
import json
import time
from pathlib import Path
from typing import Generator, Optional, Tuple

from tp_data_dla.config import (
    get_auto_connection,
    get_etl_connection,
    get_life_connection,
    verrouiller_ecritures_etl,
)
from tp_data_dla.normalisation import (
    extraire_cin_chiffres,
    extraire_tel_chiffres,
    normaliser_cin,
    normaliser_date,
    normaliser_lieu,
    normaliser_mail,
    normaliser_nom,
    normaliser_prenoms,
    normaliser_sexe,
    normaliser_tel,
    normaliser_ville,
)

CSV_PATH_DEFAULT = Path(__file__).resolve().parents[2] / "data" / "clients_autre.csv"
CSV_PATH_LEGER = Path(__file__).resolve().parents[2] / "data" / "clients_autre_leger.csv"
BATCH_SIZE = 50_000


def creer_index_fiches_base(cur):
    """Crée les index sur les colonnes de base de etl.fiches_clients pour accélérer les requêtes et jointures."""
    print("Création / vérification des index sur les colonnes de base (etl.fiches_clients)...")
    index_sqls = [
        "CREATE INDEX IF NOT EXISTS idx_fiches_source ON etl.fiches_clients (source_system, source_ref);",
        "CREATE INDEX IF NOT EXISTS idx_fiches_cin_norm ON etl.fiches_clients (cin_norm) WHERE cin_norm IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_fiches_nom_prenoms ON etl.fiches_clients (nom_norm, prenoms_norm);",
        "CREATE INDEX IF NOT EXISTS idx_fiches_nom_prenoms_date ON etl.fiches_clients (nom_norm, prenoms_trie_norm, date_naiss_norm);",
        "CREATE INDEX IF NOT EXISTS idx_fiches_nom_date ON etl.fiches_clients (nom_norm, date_naiss_norm);",
        "CREATE INDEX IF NOT EXISTS idx_fiches_date_naiss_norm ON etl.fiches_clients (date_naiss_norm);",
        "CREATE INDEX IF NOT EXISTS idx_fiches_bloc_naiss_sexe ON etl.fiches_clients (date_naiss_norm, sexe_norm) WHERE date_naiss_norm IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_fiches_tel_norm ON etl.fiches_clients (tel_norm) WHERE tel_norm IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_fiches_mail_norm ON etl.fiches_clients (mail_norm) WHERE mail_norm IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_fiches_cin_brut ON etl.fiches_clients (cin_brut) WHERE cin_brut IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_fiches_tel_brut ON etl.fiches_clients (tel_brut) WHERE tel_brut IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_fiches_mail_brut ON etl.fiches_clients (mail_brut) WHERE mail_brut IS NOT NULL;",
    ]
    for sql in index_sqls:
        cur.execute(sql)
    print("-> Index de base vérifiés et prêts sur etl.fiches_clients.")


def iter_auto(limit: Optional[int] = None) -> Generator[Tuple, None, None]:
    """Extrait et normalise les fiches Auto en streaming."""
    query = (
        "SELECT id_client_auto, numero_cin, nom_assure, prenoms_assure, ne_le, ne_a, "
        "ville_residence, mobile, courriel, immatriculation, annee_vehicule, formule_auto, sexe "
        "FROM tp_assurance.clients_auto ORDER BY id_client_auto"
    )
    if limit:
        query += f" LIMIT {limit}"

    with get_auto_connection() as conn:
        with conn.cursor(name="cur_auto_stream") as cur:
            cur.itersize = BATCH_SIZE
            cur.execute(query)
            for r in cur:
                id_fiche = r[0]
                cin_brut = r[1]
                nom_brut = r[2]
                prenoms_brut = r[3]
                date_naiss_brute = str(r[4]) if r[4] else None
                lieu_naiss_brut = r[5]
                ville_brute = r[6]
                tel_brut = r[7]
                mail_brut = r[8]
                sexe_brut = r[12]

                details_metier = json.dumps({
                    "immatriculation": r[9],
                    "annee_vehicule": r[10],
                    "formule_auto": r[11],
                }, ensure_ascii=False)

                cin_norm = normaliser_cin(cin_brut)
                cin_chiffres = extraire_cin_chiffres(cin_brut)
                nom_norm = normaliser_nom(nom_brut)
                prenoms_norm, prenoms_trie_norm = normaliser_prenoms(prenoms_brut)
                date_naiss_norm = normaliser_date(r[4])
                lieu_naiss_norm = normaliser_lieu(lieu_naiss_brut)
                ville_norm = normaliser_ville(ville_brute)
                tel_norm = normaliser_tel(tel_brut)
                tel_chiffres = extraire_tel_chiffres(tel_brut)
                mail_norm = normaliser_mail(mail_brut)
                sexe_norm = normaliser_sexe(sexe_brut)

                yield (
                    id_fiche, "AUTO", str(id_fiche),
                    cin_brut, nom_brut, prenoms_brut, date_naiss_brute,
                    lieu_naiss_brut, ville_brute, tel_brut, mail_brut, sexe_brut,
                    details_metier,
                    cin_norm, cin_chiffres, nom_norm, prenoms_norm, prenoms_trie_norm,
                    date_naiss_norm, lieu_naiss_norm, ville_norm,
                    tel_norm, tel_chiffres, mail_norm, sexe_norm,
                )


def iter_life(limit: Optional[int] = None) -> Generator[Tuple, None, None]:
    """Extrait et normalise les fiches Life en streaming."""
    query = (
        "SELECT ref_adherent, cin_numerique, nom_adherent, prenoms_adherent, date_naiss, "
        "lieu_naiss, commune_domicile, tel_contact, email_contact, produit, "
        "cotisation_mensuelle_ar, date_adhesion, genre "
        "FROM tp_assurance_life.clients_life ORDER BY ref_adherent"
    )
    if limit:
        query += f" LIMIT {limit}"

    with get_life_connection() as conn:
        cursor = conn.cursor(buffered=False)
        cursor.execute(query)
        for r in cursor:
            id_fiche = r[0]
            cin_brut = str(r[1]) if r[1] is not None else None
            nom_brut = r[2]
            prenoms_brut = r[3]
            date_naiss_brute = str(r[4]) if r[4] is not None else None
            lieu_naiss_brut = r[5]
            ville_brute = r[6]
            tel_brut = r[7]
            mail_brut = r[8]
            sexe_brut = str(r[12]) if r[12] is not None else None

            details_metier = json.dumps({
                "produit": r[9],
                "cotisation_mensuelle_ar": r[10],
                "date_adhesion": str(r[11]) if r[11] else None,
            }, ensure_ascii=False)

            cin_norm = normaliser_cin(cin_brut)
            cin_chiffres = extraire_cin_chiffres(cin_brut)
            nom_norm = normaliser_nom(nom_brut)
            prenoms_norm, prenoms_trie_norm = normaliser_prenoms(prenoms_brut)
            date_naiss_norm = normaliser_date(r[4])
            lieu_naiss_norm = normaliser_lieu(lieu_naiss_brut)
            ville_norm = normaliser_ville(ville_brute)
            tel_norm = normaliser_tel(tel_brut)
            tel_chiffres = extraire_tel_chiffres(tel_brut)
            mail_norm = normaliser_mail(mail_brut)
            sexe_norm = normaliser_sexe(sexe_brut)

            yield (
                id_fiche, "LIFE", str(id_fiche),
                cin_brut, nom_brut, prenoms_brut, date_naiss_brute,
                lieu_naiss_brut, ville_brute, tel_brut, mail_brut, sexe_brut,
                details_metier,
                cin_norm, cin_chiffres, nom_norm, prenoms_norm, prenoms_trie_norm,
                date_naiss_norm, lieu_naiss_norm, ville_norm,
                tel_norm, tel_chiffres, mail_norm, sexe_norm,
            )


def iter_autre(csv_path: Optional[Path] = None, limit: Optional[int] = None) -> Generator[Tuple, None, None]:
    """Extrait et normalise les fiches Autre depuis le CSV en streaming."""
    chemin = csv_path or CSV_PATH_DEFAULT
    with chemin.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        count = 0
        for r in reader:
            if limit and count >= limit:
                break
            count += 1
            ref_fiche = r["ref_fiche"]
            id_fiche = int(ref_fiche.replace("EXT-", ""))

            plateforme = r["plateforme"]
            if plateforme == "AGRICOLE":
                details = {
                    "plateforme": "AGRICOLE",
                    "culture": r["culture"],
                    "superficie_ha": r["superficie_ha"],
                    "garantie_agricole": r["garantie_agricole"],
                }
            else:
                details = {
                    "plateforme": "MARITIME",
                    "type_navire": r["type_navire"],
                    "port_attache": r["port_attache"],
                    "garantie_maritime": r["garantie_maritime"],
                }
            details_metier = json.dumps(details, ensure_ascii=False)

            cin_brut = r["piece_identite"] or None
            nom_brut = r["patronyme"] or None
            prenoms_brut = r["autres_noms"] or None
            date_naiss_brute = r["date_naissance"] or None
            lieu_naiss_brut = r["commune_origine"] or None
            ville_brute = r["localite"] or None
            tel_brut = r["contact_tel"] or None
            mail_brut = r["contact_mail"] or None
            sexe_brut = r["code_sexe"] or None

            cin_norm = normaliser_cin(cin_brut)
            cin_chiffres = extraire_cin_chiffres(cin_brut)
            nom_norm = normaliser_nom(nom_brut)
            prenoms_norm, prenoms_trie_norm = normaliser_prenoms(prenoms_brut)
            date_naiss_norm = normaliser_date(date_naiss_brute)
            lieu_naiss_norm = normaliser_lieu(lieu_naiss_brut)
            ville_norm = normaliser_ville(ville_brute)
            tel_norm = normaliser_tel(tel_brut)
            tel_chiffres = extraire_tel_chiffres(tel_brut)
            mail_norm = normaliser_mail(mail_brut)
            sexe_norm = normaliser_sexe(sexe_brut)

            yield (
                id_fiche, "AUTRE", ref_fiche,
                cin_brut, nom_brut, prenoms_brut, date_naiss_brute,
                lieu_naiss_brut, ville_brute, tel_brut, mail_brut, sexe_brut,
                details_metier,
                cin_norm, cin_chiffres, nom_norm, prenoms_norm, prenoms_trie_norm,
                date_naiss_norm, lieu_naiss_norm, ville_norm,
                tel_norm, tel_chiffres, mail_norm, sexe_norm,
            )


def executer_etl(
    limit: Optional[int] = None,
    reset: bool = False,
    csv_path: Optional[Path] = None,
    dataset: str = "complet",
) -> int:
    """
    Exécute le pipeline complet d'extraction et de chargement dans etl.fiches_clients.
    
    Arguments:
        limit: Plafond forcé de fiches par source (optionnel).
        reset: Ancienne option, refusée pour protéger la cible.
        csv_path: Chemin explicite vers le CSV Autre (optionnel).
        dataset: Version du dataset :
            - 'complet' : 4 000 000 de fiches (Auto 1M, Life 1M, Autre 2M).
            - 'leger'   : 400 000 fiches (Auto 100k, Life 100k, Autre 200k) pour TP étudiants.
    
    Retourne:
        Nombre total de fiches chargées.
    """
    if reset:
        raise RuntimeError("Réinitialisation refusée. Utiliser une base ETL de test vide.")
    debut = time.perf_counter()

    # Configuration des volumes selon le dataset
    if dataset == "leger":
        lim_auto = limit or 100_000
        lim_life = limit or 100_000
        lim_autre = limit or 200_000
        fichier_csv = csv_path or (CSV_PATH_LEGER if CSV_PATH_LEGER.is_file() else CSV_PATH_DEFAULT)
        print(f"=== ETL MODE LÉGER (Cible : ~400 000 fiches) ===")
    else:
        lim_auto = limit
        lim_life = limit
        lim_autre = limit
        fichier_csv = csv_path or CSV_PATH_DEFAULT
        print(f"=== ETL MODE COMPLET (Cible : ~4 000 000 fiches) ===")

    print(f"Source CSV Autre utilisée : {fichier_csv.name}")

    colonnes = (
        "id_fiche", "source_system", "source_ref",
        "cin_brut", "nom_brut", "prenoms_brut", "date_naiss_brute",
        "lieu_naiss_brut", "ville_brute", "tel_brut", "mail_brut", "sexe_brut",
        "details_metier",
        "cin_norm", "cin_chiffres", "nom_norm", "prenoms_norm", "prenoms_trie_norm",
        "date_naiss_norm", "lieu_naiss_norm", "ville_norm",
        "tel_norm", "tel_chiffres", "mail_norm", "sexe_norm"
    )
    cols_sql = ", ".join(colonnes)

    total_insere = 0
    with get_etl_connection() as conn:
        with conn.cursor() as cur:
            verrouiller_ecritures_etl(cur)
            cur.execute("""
                SELECT EXISTS (SELECT 1 FROM etl.fiches_clients)
                    OR EXISTS (SELECT 1 FROM etl.groupes_uid)
                    OR EXISTS (SELECT 1 FROM etl.file_validation)
                    OR EXISTS (SELECT 1 FROM etl.liens_rapprochement);
            """)
            if cur.fetchone()[0]:
                raise RuntimeError("La cible contient déjà des fiches ou des résultats. Utiliser une base ETL de test vide.")

            # 1. AUTO
            print("Extraction et chargement de Auto (PostgreSQL)...")
            count_auto = 0
            with cur.copy(f"COPY etl.fiches_clients ({cols_sql}) FROM STDIN") as copy:
                for row in iter_auto(limit=lim_auto):
                    copy.write_row(row)
                    count_auto += 1
            total_insere += count_auto
            print(f"-> Auto : {count_auto:,} fiches chargées.")

            # 2. LIFE
            print("Extraction et chargement de Life (MySQL)...")
            count_life = 0
            with cur.copy(f"COPY etl.fiches_clients ({cols_sql}) FROM STDIN") as copy:
                for row in iter_life(limit=lim_life):
                    copy.write_row(row)
                    count_life += 1
            total_insere += count_life
            print(f"-> Life : {count_life:,} fiches chargées.")

            # 3. AUTRE
            print("Extraction et chargement de Autre (CSV)...")
            count_autre = 0
            with cur.copy(f"COPY etl.fiches_clients ({cols_sql}) FROM STDIN") as copy:
                for row in iter_autre(csv_path=fichier_csv, limit=lim_autre):
                    copy.write_row(row)
                    count_autre += 1
            total_insere += count_autre
            print(f"-> Autre : {count_autre:,} fiches chargées.")

            # 4. CRÉATION DES INDEX SUR LES COLONNES DE BASE
            creer_index_fiches_base(cur)

            duree = time.perf_counter() - debut
            cur.execute(
                "INSERT INTO etl.journal_executions (phase, statut, duree_secondes, lignes_traitees, details) "
                "VALUES (%s, %s, %s, %s, %s)",
                ("ETL", "SUCCES", round(duree, 2), total_insere, json.dumps({
                    "dataset": dataset,
                    "auto": count_auto,
                    "life": count_life,
                    "autre": count_autre,
                    "limit": limit
                }))
            )

    print(f"\nETL terminé en {duree:.2f} s. Total : {total_insere:,} fiches chargées.")
    return total_insere
