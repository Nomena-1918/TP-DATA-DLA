#!/usr/bin/env python3
"""
Script d'évaluation de la qualité du dédoublonnage (Audit / Enseignant).
Reconstruit les clés internes théoriques (PREPARATION-ENSEIGNANT.md)
et vérifie la précision, le rappel et la pureté des clusters UID.
"""

from collections import Counter, defaultdict
import time
from tp_data_dla.config import get_etl_connection


def cle_personne(n: int, volume: int, facteur: int, decalage: int, initiales: int, reprises_communes: int, prive: int, commun: int) -> int:
    """Formule mathématique déterministe de reconstruction de la clé de personne (adaptable léger ou complet)."""
    rang = ((n - 1) * facteur + decalage) % volume + 1
    if rang > initiales:
        rang -= initiales
        if rang > reprises_communes:
            rang += commun - reprises_communes
    return rang if rang <= commun else prive + rang - commun - 1


def evaluer():
    debut = time.perf_counter()

    with get_etl_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM etl.fiches_clients;")
            total_fiches_table = cur.fetchone()[0]

    is_leger = total_fiches_table <= 500_000
    if is_leger:
        nb_communs = 70_000
        print(f"Mode détecté : DATASET LÉGER ({total_fiches_table:,} fiches, {nb_communs:,} cohortes communes)")
        params_auto = (100_000, 73, 41_729, 99_000, 700, 70_001, 70_000)
        params_life = (100_000, 137, 27_183, 99_000, 700, 99_001, 70_000)
        params_autre = (200_000, 193, 72_821, 198_000, 1_400, 128_001, 70_000)
    else:
        nb_communs = 700_000
        print(f"Mode détecté : DATASET COMPLET ({total_fiches_table:,} fiches, {nb_communs:,} cohortes communes)")
        params_auto = (1_000_000, 73, 41_729, 990_000, 7_000, 700_001, 700_000)
        params_life = (1_000_000, 137, 27_183, 990_000, 7_000, 990_001, 700_000)
        params_autre = (2_000_000, 193, 72_821, 1_980_000, 14_000, 1_280_001, 700_000)

    print("Lecture des fiches et calcul des clés théoriques de vérité terrain...")
    cle_theorique_par_fiche = {}
    fiches_par_uid = defaultdict(list)

    with get_etl_connection() as conn:
        with conn.cursor(name="cur_eval") as cur:
            cur.itersize = 50_000
            cur.execute("SELECT id_fiche, source_system, source_ref, uid FROM etl.fiches_clients;")
            for id_fiche, source, ref, uid in cur:
                if source == "AUTO":
                    n = int(ref) - 1_000_000
                    cle = cle_personne(n, *params_auto)
                elif source == "LIFE":
                    n = int(ref) - 3_000_000
                    cle = cle_personne(n, *params_life)
                else:
                    n = int(ref.replace("EXT-", "")) - 5_000_000
                    cle = cle_personne(n, *params_autre)

                cle_theorique_par_fiche[id_fiche] = cle
                if uid:
                    fiches_par_uid[uid].append(id_fiche)

    print(f"-> {len(cle_theorique_par_fiche):,} fiches analysées.")

    # 1. Pureté des clusters (Faux positifs)
    # Un cluster UID est pur s'il ne contient qu'une seule clé théorique de personne
    clusters_purs = 0
    clusters_impurs = 0
    cles_par_uid = {}

    for uid, fiches in fiches_par_uid.items():
        cles = {cle_theorique_par_fiche[fid] for fid in fiches}
        cles_par_uid[uid] = cles
        if len(cles) == 1:
            clusters_purs += 1
        else:
            clusters_impurs += 1

    taux_purete = (clusters_purs / len(fiches_par_uid)) * 100 if fiches_par_uid else 0

    # 2. Rappel (Faux négatifs / Séparations)
    # Vérification sur les 700 000 clés communes
    uids_par_cle = defaultdict(set)
    for uid, cles in cles_par_uid.items():
        for c in cles:
            uids_par_cle[c].add(uid)

    cles_communes_regroupees = sum(1 for c in range(1, nb_communs + 1) if len(uids_par_cle[c]) == 1)
    cles_communes_fractionnees = sum(1 for c in range(1, nb_communs + 1) if len(uids_par_cle[c]) > 1)

    # 3. Vérification des cas spécifiques
    ponts_regroupes = sum(1 for c in range(1, nb_communs + 1) if c % 211 == 0 and len(uids_par_cle[c]) == 1)
    ponts_total = sum(1 for c in range(1, nb_communs + 1) if c % 211 == 0)

    conflits_cin_total = sum(1 for c in range(1, nb_communs + 1) if c % 113 == 0)
    conflits_cin_separes = sum(1 for c in range(1, nb_communs + 1) if c % 113 == 0 and len(uids_par_cle[c]) > 1)

    duree = time.perf_counter() - debut
    print("\n========================================================")
    print("           RAPPORT D'ÉVALUATION DE QUALITÉ              ")
    print("========================================================")
    print(f"Total fiches évaluées         : {len(cle_theorique_par_fiche):,}")
    print(f"Total clusters UID générés    : {len(fiches_par_uid):,}")
    print(f"Clusters 100 % purs           : {clusters_purs:,} ({taux_purete:.4f} %)")
    print(f"Clusters impurs (faux pos.)   : {clusters_impurs:,}")
    print("--------------------------------------------------------")
    print(f"Clés communes réunies (1 UID) : {cles_communes_regroupees:,} / {nb_communs:,} ({cles_communes_regroupees/nb_communs*100:.2f} %)")
    print(f"Clés communes fractionnées    : {cles_communes_fractionnees:,}")
    print(f"Ponts indirects (cle % 211)   : {ponts_regroupes:,} / {ponts_total:,} réunis automatiquement")
    print(f"Conflits CIN isolés (% 113)   : {conflits_cin_separes:,} / {conflits_cin_total:,} protégés par le verrou")
    print(f"Temps d'audit                 : {duree:.2f} s")
    print("========================================================\n")


if __name__ == "__main__":
    evaluer()
