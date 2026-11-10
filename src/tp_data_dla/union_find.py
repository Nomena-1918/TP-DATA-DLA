"""Moteur de dédoublonnage Union-Find compact, rapide et basse consommation."""

from array import array
import itertools
import json
from pathlib import Path
import time
import uuid
from typing import Dict, List, Optional, Tuple

from rapidfuzz.distance import DamerauLevenshtein

from tp_data_dla.config import get_etl_connection, verrouiller_ecritures_etl
from tp_data_dla.normalisation import (
    damerau_levenshtein_adaptatif,
    distance_prenoms_tokens,
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

# Namespace fixe pour générer des UUIDv5 déterministes et reproductibles
NAMESPACE_CLIENT = uuid.UUID("a47ac10b-58cc-4372-a567-0e02b2c3d479")


class CompactUnionFind:
    """
    Structure Union-Find hautement compacte pour 4 millions d'éléments.
    parent : array('i') où parent[i] < 0 indique une racine et -parent[i] est la taille.
    cluster_cin : array('q') stockant le CIN (entier 64-bit) de la composante (-1 si aucun).
    """

    def __init__(self, n: int, id_to_idx_fn, idx_to_id_fn):
        self.n = n
        self.id_to_idx = id_to_idx_fn
        self.idx_to_id = idx_to_id_fn
        # 16 Mo pour 4M entiers 32-bit
        self.parent = array("i", [-1] * n)
        # 32 Mo pour 4M entiers 64-bit
        self.cluster_cin = array("q", [-1] * n)
        self.conflits_cin: List[Tuple[int, int, str]] = []

    def find(self, i: int) -> int:
        """Compression de chemin itérative."""
        root = i
        while self.parent[root] >= 0:
            root = self.parent[root]
        curr = i
        while curr != root:
            nxt = self.parent[curr]
            if nxt < 0:
                break
            self.parent[curr] = root
            curr = nxt
        return root

    def union(self, a: int, b: int, regle: str = "C") -> bool:
        """
        Rassemble deux éléments sous le même cluster logique.
        Applique le verrou strict anti-conflit de CIN en O(1).
        Retourne True si réunion effectuée ou déjà dans le même cluster.
        Retourne False si refusé pour conflit de CIN.
        """
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return True

        cin_a = self.cluster_cin[ra]
        cin_b = self.cluster_cin[rb]

        # Règle d'exclusion : Deux CIN distincts valides interdisent le regroupement
        if cin_a != -1 and cin_b != -1 and cin_a != cin_b:
            self.conflits_cin.append((self.idx_to_id(a), self.idx_to_id(b), regle))
            return False

        # Union pondérée par la taille du cluster
        size_a = -self.parent[ra]
        size_b = -self.parent[rb]

        if size_a < size_b:
            ra, rb = rb, ra
            cin_a, cin_b = cin_b, cin_a

        self.parent[ra] -= size_b  # size_a + size_b
        self.parent[rb] = ra

        # Préservation du CIN sur la nouvelle racine
        if cin_a != -1:
            self.cluster_cin[ra] = cin_a
        elif cin_b != -1:
            self.cluster_cin[ra] = cin_b

        return True


def creer_mapping_indices(conn) -> Tuple[int, any, any]:
    """
    Construit les fonctions de conversion id_fiche <-> index interne (0..N-1).
    Optimisé en O(1) sans mémoire si la table suit la numérotation standard,
    ou avec tableau compact si numérotation partielle.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT count(*), min(id_fiche), max(id_fiche) FROM etl.fiches_clients;")
        count, min_id, max_id = cur.fetchone()

    if count == 0:
        raise RuntimeError("La table etl.fiches_clients est vide. Lancez l'ETL au préalable.")

    # Détection de la numérotation standard TP (1M Auto, 1M Life, 2M Autre)
    if count == 4_000_000 and min_id == 1_000_001 and max_id == 7_000_000:
        def id_to_idx(id_fiche: int) -> int:
            if id_fiche <= 2_000_000:
                return id_fiche - 1_000_001
            elif id_fiche <= 4_000_000:
                return 1_000_000 + (id_fiche - 3_000_001)
            else:
                return 2_000_000 + (id_fiche - 5_000_001)

        def idx_to_id(idx: int) -> int:
            if idx < 1_000_000:
                return 1_000_001 + idx
            elif idx < 2_000_000:
                return 3_000_001 + (idx - 1_000_000)
            else:
                return 5_000_001 + (idx - 2_000_000)

        return count, id_to_idx, idx_to_id

    # Mode générique (ex: --limit pour tests)
    print(f"Numérotation non standard ou restreinte ({count:,} fiches). Construction du tableau compact d'indices...")
    with conn.cursor(name="cur_ids") as cur:
        cur.itersize = 50_000
        cur.execute("SELECT id_fiche FROM etl.fiches_clients ORDER BY id_fiche;")
        id_list = array("q", (row[0] for row in cur))

    id_to_idx_dict = {id_fiche: idx for idx, id_fiche in enumerate(id_list)}

    def id_to_idx_gen(id_fiche: int) -> int:
        return id_to_idx_dict[id_fiche]

    def idx_to_id_gen(idx: int) -> int:
        return id_list[idx]

    return count, id_to_idx_gen, idx_to_id_gen


def executer_union_find() -> Dict[str, any]:
    """
    Exécute les passes de rapprochement C1, C2, C3, C4a, C4b,
    assigne le même UID aux fiches reliées et renseigne etl.file_validation.
    """
    debut = time.perf_counter()

    with get_etl_connection() as conn:
        # Augmente work_mem pour accélérer les GROUP BY sans saturer la RAM globale
        with conn.cursor() as cur:
            verrouiller_ecritures_etl(cur)
            cur.execute("""
                SELECT EXISTS (SELECT 1 FROM etl.fiches_clients WHERE uid IS NOT NULL)
                    OR EXISTS (SELECT 1 FROM etl.groupes_uid)
                    OR EXISTS (SELECT 1 FROM etl.file_validation)
                    OR EXISTS (SELECT 1 FROM etl.liens_rapprochement);
            """)
            if cur.fetchone()[0]:
                raise RuntimeError("Rapprochement déjà publié ou état existant. Utiliser une base ETL de test vide pour recalculer.")
            cur.execute("SET LOCAL work_mem = '64MB';")

        print("1. Initialisation de la structure Union-Find compacte...")
        count, id_to_idx, idx_to_id = creer_mapping_indices(conn)
        uf = CompactUnionFind(count, id_to_idx, idx_to_id)

        # 2. Renseignement initial des CIN connus
        print("2. Chargement des CIN initiaux...")
        with conn.cursor(name="cur_cin_init") as cur:
            cur.itersize = 50_000
            cur.execute("SELECT id_fiche, cin_norm::bigint FROM etl.fiches_clients WHERE cin_norm IS NOT NULL;")
            for id_fiche, cin_int in cur:
                idx = id_to_idx(id_fiche)
                uf.cluster_cin[idx] = cin_int

        # 3. Passe C1 : CIN identique (100 %)
        print("3. Passe C1 : Rapprochement par CIN identique (100 %)...")
        c1_reunions = 0
        with conn.cursor(name="cur_c1") as cur:
            cur.itersize = 50_000
            cur.execute("""
                SELECT array_agg(id_fiche ORDER BY id_fiche)
                FROM etl.fiches_clients
                WHERE cin_norm IS NOT NULL
                GROUP BY cin_norm
                HAVING count(*) > 1;
            """)
            for (ids,) in cur:
                first_idx = id_to_idx(ids[0])
                for other_id in ids[1:]:
                    if uf.union(first_idx, id_to_idx(other_id), regle="C1"):
                        c1_reunions += 1

        print(f"-> Passe C1 : {c1_reunions:,} paires de fiches reliées.")

        # 4. Passe C2 : État civil complet + Ville (80 %)
        print("4. Passe C2 : Rapprochement par État civil complet + Ville (80 %)...")
        c2_reunions = 0
        with conn.cursor(name="cur_c2") as cur:
            cur.itersize = 50_000
            cur.execute("""
                SELECT array_agg(id_fiche ORDER BY id_fiche)
                FROM etl.fiches_clients
                WHERE nom_norm IS NOT NULL AND prenoms_trie_norm IS NOT NULL
                  AND date_naiss_norm IS NOT NULL AND lieu_naiss_norm IS NOT NULL
                  AND ville_norm IS NOT NULL
                GROUP BY nom_norm, prenoms_trie_norm, date_naiss_norm, lieu_naiss_norm, ville_norm
                HAVING count(*) > 1;
            """)
            for (ids,) in cur:
                first_idx = id_to_idx(ids[0])
                for other_id in ids[1:]:
                    if uf.union(first_idx, id_to_idx(other_id), regle="C2"):
                        c2_reunions += 1

        print(f"-> Passe C2 : {c2_reunions:,} paires reliées.")

        # 5. Passe C3 : État civil sans Ville (60 %)
        print("5. Passe C3 : Rapprochement par État civil sans Ville (60 %)...")
        c3_reunions = 0
        with conn.cursor(name="cur_c3") as cur:
            cur.itersize = 50_000
            cur.execute("""
                SELECT array_agg(id_fiche ORDER BY id_fiche)
                FROM etl.fiches_clients
                WHERE nom_norm IS NOT NULL AND prenoms_trie_norm IS NOT NULL
                  AND date_naiss_norm IS NOT NULL AND lieu_naiss_norm IS NOT NULL
                GROUP BY nom_norm, prenoms_trie_norm, date_naiss_norm, lieu_naiss_norm
                HAVING count(*) > 1;
            """)
            for (ids,) in cur:
                first_idx = id_to_idx(ids[0])
                for other_id in ids[1:]:
                    if uf.union(first_idx, id_to_idx(other_id), regle="C3"):
                        c3_reunions += 1

        print(f"-> Passe C3 : {c3_reunions:,} paires reliées.")

        # Structure de collecte pour la file de validation humaine
        cas_validation = []
        vu_paires = set()

        def ajouter_paire_validation(id_a: int, id_b: int, motif: str, regle: str, score: int):
            paire = (min(id_a, id_b), max(id_a, id_b))
            if paire not in vu_paires:
                vu_paires.add(paire)
                cas_validation.append((paire[0], paire[1], motif, regle, score))

        def ajouter_cas_validation(ids: list, motif: str, regle: str, score: int):
            for i in range(len(ids)):
                idx_a = id_to_idx(ids[i])
                root_a = uf.find(idx_a)
                for j in range(i + 1, len(ids)):
                    idx_b = id_to_idx(ids[j])
                    root_b = uf.find(idx_b)
                    if root_a != root_b:
                        ajouter_paire_validation(ids[i], ids[j], motif, regle, score)

        # 5bis. Passe Floue : Blocage B1 (Date de naissance + Sexe) avec Damerau-Levenshtein adaptatif
        print("5bis. Passe Floue : Blocage B1 (Date de naissance + Sexe) & filtrage adaptatif...")
        flou_reunions = 0
        with conn.cursor(name="cur_b1") as cur:
            cur.itersize = 20_000
            cur.execute("""
                SELECT
                    id_fiche, cin_norm, cin_chiffres, nom_norm, prenoms_norm, prenoms_trie_norm,
                    lieu_naiss_norm, ville_norm, date_naiss_norm, sexe_norm
                FROM etl.fiches_clients
                WHERE date_naiss_norm IS NOT NULL AND sexe_norm IS NOT NULL
                ORDER BY date_naiss_norm, sexe_norm;
            """)

            for (naiss, sexe), group in itertools.groupby(cur, key=lambda r: (r[8], r[9])):
                bloc = list(group)
                if len(bloc) < 2 or len(bloc) > 300:
                    continue

                for i in range(len(bloc)):
                    row_a = bloc[i]
                    id_a = row_a[0]
                    idx_a = id_to_idx(id_a)
                    nom_a = row_a[3]
                    pre_a = row_a[4]
                    lieu_a = row_a[6]
                    ville_a = row_a[7]
                    cin_norm_a = row_a[1]
                    cin_chiffres_a = row_a[2]

                    for j in range(i + 1, len(bloc)):
                        row_b = bloc[j]
                        id_b = row_b[0]
                        idx_b = id_to_idx(id_b)

                        # Si déjà regroupés sous la même racine, passer
                        if uf.find(idx_a) == uf.find(idx_b):
                            continue

                        nom_b = row_b[3]
                        pre_b = row_b[4]

                        # Pruning rapide sur le nom
                        if not nom_a or not nom_b:
                            continue
                        len_diff = abs(len(nom_a) - len(nom_b))
                        seuil_nom = 2 if min(len(nom_a), len(nom_b)) >= 9 else 1
                        if len_diff > seuil_nom:
                            continue

                        d_nom = damerau_levenshtein_adaptatif(nom_a, nom_b)
                        if d_nom > 2:
                            continue

                        # Pruning et calcul sur les prénoms
                        d_pre = distance_prenoms_tokens(pre_a, pre_b)
                        if d_pre > 2:
                            continue

                        # Somme des écarts civils : tolérance globale <= 2 fautes
                        d_etat_civil = d_nom + d_pre
                        if d_etat_civil > 2:
                            continue

                        # Vérification de l'ancrage géographique (lieu de naissance ou commune)
                        lieu_b = row_b[6]
                        ville_b = row_b[7]
                        d_lieu = damerau_levenshtein_adaptatif(lieu_a, lieu_b) if (lieu_a and lieu_b) else 999
                        d_ville = damerau_levenshtein_adaptatif(ville_a, ville_b) if (ville_a and ville_b) else 999

                        geo_valide = (
                            (d_lieu <= 2) or (d_ville <= 2) or
                            (not lieu_a and not ville_a) or
                            (not lieu_b and not ville_b)
                        )
                        if not geo_valide:
                            continue

                        # Analyse du CIN / chiffres
                        cin_norm_b = row_b[1]
                        cin_chiffres_b = row_b[2]

                        if cin_norm_a and cin_norm_b:
                            # Deux CIN de 12 chiffres valides
                            if cin_norm_a == cin_norm_b:
                                if uf.union(idx_a, idx_b, regle="C2_FLOU"):
                                    flou_reunions += 1
                            else:
                                dl_cin = DamerauLevenshtein.distance(cin_norm_a, cin_norm_b, score_cutoff=2)
                                if dl_cin == 1:
                                    # 1 seul chiffre d'écart sur un CIN valide -> Suspicion faute de frappe, arbitrage humain
                                    ajouter_paire_validation(id_a, id_b, "SUSPICION_FAUTE_CIN", "C2_FLOU", 75)
                                else:
                                    ajouter_paire_validation(id_a, id_b, "CONFLIT_CIN", "C2_FLOU", 0)
                        elif cin_chiffres_a and cin_chiffres_b:
                            # Au moins un des CIN a une faute de frappe (11 ou 13 chiffres)
                            dl_cin = DamerauLevenshtein.distance(cin_chiffres_a, cin_chiffres_b, score_cutoff=2)
                            if dl_cin <= 1:
                                if uf.union(idx_a, idx_b, regle="C2_FLOU"):
                                    flou_reunions += 1
                            else:
                                ajouter_paire_validation(id_a, id_b, "CONFLIT_CIN", "C2_FLOU", 0)
                        else:
                            # Un seul ou aucun CIN renseigné -> Réunion automatique si concordance forte
                            if d_etat_civil <= 1 or (d_lieu <= 1 and d_ville <= 1):
                                if uf.union(idx_a, idx_b, regle="C2_FLOU"):
                                    flou_reunions += 1
                            else:
                                ajouter_paire_validation(id_a, id_b, "AMBIGU_FLOU_CIVIL", "C2_FLOU", 60)

        print(f"-> Passe Floue : {flou_reunions:,} paires reliées par tolérance aux coquilles.")

        # 6. Passes C4a & C4b : Cas ambigus Téléphone / E-mail (50 %)
        # Ces cas NE SONT PAS fusionnés automatiquement mais envoyés en file de validation
        print("6. Passes C4a & C4b : Détection des cas ambigus à 50 % (Téléphone / E-mail)...")

        # C4a (Téléphone)
        with conn.cursor(name="cur_c4a") as cur:
            cur.itersize = 50_000
            cur.execute("""
                SELECT array_agg(id_fiche ORDER BY id_fiche)
                FROM etl.fiches_clients
                WHERE nom_norm IS NOT NULL AND prenoms_trie_norm IS NOT NULL AND tel_norm IS NOT NULL
                GROUP BY nom_norm, prenoms_trie_norm, tel_norm
                HAVING count(*) > 1;
            """)
            for (ids,) in cur:
                ajouter_cas_validation(ids, "AMBIGU_C4A", "C4a", 50)

        # C4b (E-mail)
        with conn.cursor(name="cur_c4b") as cur:
            cur.itersize = 50_000
            cur.execute("""
                SELECT array_agg(id_fiche ORDER BY id_fiche)
                FROM etl.fiches_clients
                WHERE nom_norm IS NOT NULL AND prenoms_trie_norm IS NOT NULL AND mail_norm IS NOT NULL
                GROUP BY nom_norm, prenoms_trie_norm, mail_norm
                HAVING count(*) > 1;
            """)
            for (ids,) in cur:
                ajouter_cas_validation(ids, "AMBIGU_C4B", "C4b", 50)

        # 6bis. Passe Floue Contacts : Ambigus avec fautes légères sur contacts ou noms
        print("6bis. Passe Floue Contacts : Ambigus avec téléphone partagé et fiches distinctes...")
        flou_contacts = 0
        with conn.cursor(name="cur_tel_flou") as cur:
            cur.itersize = 20_000
            cur.execute("""
                SELECT tel_norm, array_agg(id_fiche ORDER BY id_fiche)
                FROM etl.fiches_clients
                WHERE tel_norm IS NOT NULL
                GROUP BY tel_norm
                HAVING count(*) BETWEEN 2 AND 50;
            """)
            for tel, ids in cur:
                for i in range(len(ids)):
                    id_a = ids[i]
                    idx_a = id_to_idx(id_a)
                    for j in range(i + 1, len(ids)):
                        id_b = ids[j]
                        idx_b = id_to_idx(id_b)
                        if uf.find(idx_a) != uf.find(idx_b):
                            ajouter_paire_validation(id_a, id_b, "AMBIGU_FLOU_CONTACT", "C4a_FLOU", 45)
                            flou_contacts += 1

        print(f"-> Passe Floue Contacts : {flou_contacts:,} cas ambigus ajoutés.")

        # Ajout des conflits de CIN détectés
        for id_a, id_b, regle in uf.conflits_cin:
            ajouter_paire_validation(id_a, id_b, "CONFLIT_CIN", regle, 0)

        print(f"-> File de validation : {len(cas_validation):,} cas ambigus ou conflits de CIN isolés.")

        # 7. Génération des UUIDs par cluster et mise à jour de etl.fiches_clients.uid
        print("7. Attribution de l'UID (NEW_ID) à chaque fiche individuelle...")
        # Un UUID déterministe est attribué à chaque racine (id minimale)
        root_to_uuid = {}
        for idx in range(count):
            r = uf.find(idx)
            if r not in root_to_uuid:
                root_id = idx_to_id(r)
                root_to_uuid[r] = str(uuid.uuid5(NAMESPACE_CLIENT, f"client:{root_id}"))

        nb_clusters = len(root_to_uuid)
        print(f"-> {nb_clusters:,} personnes physiques distinctes (groupes UID) identifiées sur {count:,} fiches.")

        # Chargement rapide via table temporaire UNLOGGED
        print("Écriture des UIDs dans PostgreSQL via table de chargement temporaire...")
        with conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE temp_uids (id_fiche BIGINT PRIMARY KEY, uid UUID) ON COMMIT DROP;")
            with cur.copy("COPY temp_uids (id_fiche, uid) FROM STDIN") as copy:
                for idx in range(count):
                    id_fiche = idx_to_id(idx)
                    root_idx = uf.find(idx)
                    u = root_to_uuid[root_idx]
                    copy.write_row((id_fiche, u))

            print("Exécution de l'UPDATE etl.fiches_clients.uid...")
            cur.execute("""
                UPDATE etl.fiches_clients f
                SET uid = t.uid
                FROM temp_uids t
                WHERE f.id_fiche = t.id_fiche;
            """)

        # 8. Alimentation de etl.groupes_uid (Index de regroupement pour mini-app)
        print("8. Alimentation de la table d'index etl.groupes_uid...")
        with conn.cursor() as cur:

            cur.execute("""
                INSERT INTO etl.groupes_uid (
                    uid, nb_fiches, sources,
                    cin_principal, nom_principal, prenoms_principal,
                    date_naiss_principale, ville_principale
                )
                SELECT
                    uid,
                    count(*)::integer AS nb_fiches,
                    array_agg(DISTINCT source_system) AS sources,
                    max(cin_norm) AS cin_principal,
                    max(nom_norm) AS nom_principal,
                    max(prenoms_norm) AS prenoms_principal,
                    max(date_naiss_norm) AS date_naiss_principale,
                    max(ville_norm) AS ville_principale
                FROM etl.fiches_clients
                GROUP BY uid;
            """)

        # 9. Alimentation de etl.file_validation
        print("9. Insertion des cas en attente dans etl.file_validation...")
        with conn.cursor() as cur:

            if cas_validation:
                with cur.copy("""
                    COPY etl.file_validation (id_fiche_a, id_fiche_b, uid_a, uid_b, motif, regle, score)
                    FROM STDIN
                """) as copy:
                    for id_a, id_b, motif, regle, score in cas_validation:
                        uid_a = root_to_uuid[uf.find(id_to_idx(id_a))]
                        uid_b = root_to_uuid[uf.find(id_to_idx(id_b))]
                        copy.write_row((id_a, id_b, uid_a, uid_b, motif, regle, score))

        # 10. Création post-chargement des index
        print("10. Création des index post-rapprochement...")
        sql_index_path = Path(__file__).resolve().parents[2] / "sql" / "03_index_etl.sql"
        if sql_index_path.is_file():
            with conn.cursor() as cur:
                cur.execute(sql_index_path.read_text(encoding="utf-8"))

        duree = time.perf_counter() - debut
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO etl.journal_executions (phase, statut, duree_secondes, lignes_traitees, details)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                "UNION_FIND", "SUCCES", round(duree, 2), count,
                json.dumps({
                    "fiches_total": count,
                    "groupes_uid": nb_clusters,
                    "c1_reunions": c1_reunions,
                    "c2_reunions": c2_reunions,
                    "c3_reunions": c3_reunions,
                    "flou_reunions": flou_reunions,
                    "cas_validation": len(cas_validation),
                })
            ))

    print(f"\nUnion-Find terminé avec succès en {duree:.2f} s !")
    return {
        "fiches": count,
        "groupes_uid": nb_clusters,
        "c1": c1_reunions,
        "c2": c2_reunions,
        "c3": c3_reunions,
        "flou": flou_reunions,
        "validation": len(cas_validation),
        "duree": duree,
    }


def _evaluer_paire_floue(fa: Dict[str, any], fb: Dict[str, any]) -> Optional[Tuple[str, str, int]]:
    """
    Évalue deux fiches partageant le même bloc (date_naiss_norm, sexe_norm).
    Retourne None si pas de correspondance, ou un tuple (decision, regle, score) :
    - ('UNION', 'C2_FLOU', score) pour une fusion automatique
    - ('SUSPICION_FAUTE_CIN', 'C2_FLOU', 75) pour 1 chiffre d'écart sur 2 CIN valides à 12 chiffres
    - ('CONFLIT_CIN', 'C2_FLOU', 0) pour un conflit strict de CIN (>= 2 chiffres d'écart)
    - ('AMBIGU_FLOU_CIVIL', 'C2_FLOU', 60) pour un rapprochement flou nécessitant arbitrage
    """
    nom_a, nom_b = fa["nom_norm"], fb["nom_norm"]
    pre_a, pre_b = fa["prenoms_norm"], fb["prenoms_norm"]
    if not nom_a or not nom_b:
        return None

    len_diff = abs(len(nom_a) - len(nom_b))
    seuil_nom = 2 if min(len(nom_a), len(nom_b)) >= 9 else 1
    if len_diff > seuil_nom:
        return None

    d_nom = damerau_levenshtein_adaptatif(nom_a, nom_b)
    if d_nom > 2:
        return None

    d_pre = distance_prenoms_tokens(pre_a, pre_b)
    if d_pre > 2:
        return None

    d_etat_civil = d_nom + d_pre
    if d_etat_civil > 2:
        return None

    lieu_a, lieu_b = fa["lieu_naiss_norm"], fb["lieu_naiss_norm"]
    ville_a, ville_b = fa["ville_norm"], fb["ville_norm"]
    d_lieu = damerau_levenshtein_adaptatif(lieu_a, lieu_b) if (lieu_a and lieu_b) else 999
    d_ville = damerau_levenshtein_adaptatif(ville_a, ville_b) if (ville_a and ville_b) else 999

    geo_valide = (
        (d_lieu <= 2) or (d_ville <= 2) or
        (not lieu_a and not ville_a) or
        (not lieu_b and not ville_b)
    )
    if not geo_valide:
        return None

    cin_norm_a, cin_norm_b = fa["cin_norm"], fb["cin_norm"]
    cin_chiffres_a, cin_chiffres_b = fa["cin_chiffres"], fb["cin_chiffres"]

    if cin_norm_a and cin_norm_b:
        if cin_norm_a == cin_norm_b:
            return ("UNION", "C2_FLOU", 80)
        dl_cin = DamerauLevenshtein.distance(cin_norm_a, cin_norm_b, score_cutoff=2)
        if dl_cin == 1:
            return ("SUSPICION_FAUTE_CIN", "C2_FLOU", 75)
        return ("CONFLIT_CIN", "C2_FLOU", 0)
    elif cin_chiffres_a and cin_chiffres_b:
        dl_cin = DamerauLevenshtein.distance(cin_chiffres_a, cin_chiffres_b, score_cutoff=2)
        if dl_cin <= 1:
            return ("UNION", "C2_FLOU", 75)
        return ("CONFLIT_CIN", "C2_FLOU", 0)
    else:
        if d_etat_civil <= 1 or (d_lieu <= 1 and d_ville <= 1):
            return ("UNION", "C2_FLOU", 70)
        return ("AMBIGU_FLOU_CIVIL", "C2_FLOU", 60)


def executer_lot_incremental(chunk_size: int = 2000, limit: Optional[int] = None) -> Dict[str, any]:
    """
    Exécute le lot incrémental quotidien (Phase 2 : fenêtre 00h00-07h00)
    sur les nouvelles fiches ayant `WHERE uid IS NULL`, sans recalculer l'historique.

    Fonctionnement en 5 étapes par lot unitaire (chunk) :
    1. Sélection différentielle `WHERE uid IS NULL` et normalisation à la volée si requise.
    2. Dédoublonnage intra-lot (Delta x Delta) via CompactUnionFind.
    3. Recherche indexée contre l'historique (Delta x Historique `WHERE uid IS NOT NULL`).
    4. Attribution non bloquante du `uid` (Cas A : réutilisation UID historique,
       Cas B : nouveau client UUIDv5, Cas C : UID provisoire + mise en file de validation).
    5. Mise à jour incrémentale de `etl.groupes_uid`, `etl.file_validation`,
       `etl.liens_rapprochement` et commit unitaire pour reprise sur erreur idempotente.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size doit être strictement positif.")

    debut = time.perf_counter()

    with get_etl_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'etl' AND table_name = 'fiches_clients' AND column_name = 'uid'
                );
            """)
            if not cur.fetchone()[0]:
                raise RuntimeError(
                    "La colonne uid est absente de etl.fiches_clients. Exécutez add-uid-column au préalable."
                )
            cur.execute("SELECT count(*) FROM etl.fiches_clients WHERE uid IS NULL;")
            total_en_attente = cur.fetchone()[0]

    cible = min(total_en_attente, limit) if limit is not None else total_en_attente
    print(f"=== LOT INCRÉMENTAL QUOTIDIEN (Fiches en attente WHERE uid IS NULL : {total_en_attente:,}) ===")

    total_traite = 0
    chunks_traites = 0
    stats = {
        "cas_a_reconnus": 0,
        "cas_b_nouveaux": 0,
        "cas_c_provisoires": 0,
        "c1": 0,
        "c2": 0,
        "c3": 0,
        "flou": 0,
        "validation": 0,
    }

    while total_traite < cible:
        taille_lot = min(chunk_size, cible - total_traite)
        with get_etl_connection() as conn:
            with conn.cursor() as cur:
                verrouiller_ecritures_etl(cur)
                cur.execute("""
                    SELECT
                        id_fiche, source_system, source_ref,
                        cin_brut, nom_brut, prenoms_brut, date_naiss_brute,
                        lieu_naiss_brut, ville_brute, tel_brut, mail_brut, sexe_brut,
                        cin_norm, cin_chiffres, nom_norm, prenoms_norm, prenoms_trie_norm,
                        date_naiss_norm, lieu_naiss_norm, ville_norm,
                        tel_norm, tel_chiffres, mail_norm, sexe_norm
                    FROM etl.fiches_clients
                    WHERE uid IS NULL
                    ORDER BY id_fiche
                    LIMIT %s;
                """, (taille_lot,))
                rows = cur.fetchall()

                if not rows:
                    break

                # 1. Préparation et normalisation à la volée des fiches du lot Delta
                fiches_delta: List[Dict[str, any]] = []
                for r in rows:
                    (
                        id_fiche, source_system, source_ref,
                        cin_brut, nom_brut, prenoms_brut, date_naiss_brute,
                        lieu_naiss_brut, ville_brute, tel_brut, mail_brut, sexe_brut,
                        cin_norm, cin_chiffres, nom_norm, prenoms_norm, prenoms_trie_norm,
                        date_naiss_norm, lieu_naiss_norm, ville_norm,
                        tel_norm, tel_chiffres, mail_norm, sexe_norm,
                    ) = r

                    besoin_maj_norm = False
                    if (
                        nom_norm is None and prenoms_norm is None and cin_norm is None
                        and (nom_brut is not None or prenoms_brut is not None or cin_brut is not None)
                    ):
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
                        besoin_maj_norm = True
                    else:
                        if cin_chiffres is None and cin_brut is not None:
                            cin_chiffres = extraire_cin_chiffres(cin_brut)
                            besoin_maj_norm = True
                        if tel_chiffres is None and tel_brut is not None:
                            tel_chiffres = extraire_tel_chiffres(tel_brut)
                            besoin_maj_norm = True

                    date_str = str(date_naiss_norm) if date_naiss_norm is not None else None
                    fiches_delta.append({
                        "id_fiche": id_fiche,
                        "source_system": source_system,
                        "source_ref": source_ref,
                        "cin_norm": cin_norm.strip() if cin_norm else None,
                        "cin_chiffres": cin_chiffres,
                        "nom_norm": nom_norm,
                        "prenoms_norm": prenoms_norm,
                        "prenoms_trie_norm": prenoms_trie_norm,
                        "date_naiss_norm": date_str,
                        "lieu_naiss_norm": lieu_naiss_norm,
                        "ville_norm": ville_norm,
                        "tel_norm": tel_norm,
                        "tel_chiffres": tel_chiffres,
                        "mail_norm": mail_norm,
                        "sexe_norm": sexe_norm.strip() if sexe_norm else None,
                        "besoin_maj_norm": besoin_maj_norm,
                    })

                n_delta = len(fiches_delta)
                id_to_idx_map = {f["id_fiche"]: idx for idx, f in enumerate(fiches_delta)}
                idx_to_id_list = [f["id_fiche"] for f in fiches_delta]

                uf = CompactUnionFind(
                    n_delta,
                    lambda id_f: id_to_idx_map[id_f],
                    lambda idx: idx_to_id_list[idx],
                )

                for idx, f in enumerate(fiches_delta):
                    if f["cin_norm"]:
                        uf.cluster_cin[idx] = int(f["cin_norm"])

                cas_validation: List[Tuple[int, int, str, str, int]] = []
                vu_paires = set()
                liens_intra: List[Tuple[int, int, str, int]] = []

                def ajouter_paire_validation(id_a: int, id_b: int, motif: str, regle: str, score: int):
                    paire = (min(id_a, id_b), max(id_a, id_b))
                    if paire not in vu_paires and id_a != id_b:
                        vu_paires.add(paire)
                        cas_validation.append((paire[0], paire[1], motif, regle, score))

                # 2. Dédoublonnage intra-lot (Delta x Delta)
                # 2a. Passe C1 intra-lot
                par_cin: Dict[str, List[int]] = {}
                for idx, f in enumerate(fiches_delta):
                    if f["cin_norm"]:
                        par_cin.setdefault(f["cin_norm"], []).append(idx)
                for idxs in par_cin.values():
                    first = idxs[0]
                    for other in idxs[1:]:
                        if uf.find(first) != uf.find(other) and uf.union(first, other, regle="C1"):
                            stats["c1"] += 1
                            liens_intra.append((idx_to_id_list[first], idx_to_id_list[other], "C1", 100))

                # 2b. Passe C2 intra-lot
                par_c2: Dict[Tuple, List[int]] = {}
                for idx, f in enumerate(fiches_delta):
                    if (
                        f["nom_norm"] and f["prenoms_trie_norm"] and f["date_naiss_norm"]
                        and f["lieu_naiss_norm"] and f["ville_norm"]
                    ):
                        cle = (
                            f["nom_norm"], f["prenoms_trie_norm"], f["date_naiss_norm"],
                            f["lieu_naiss_norm"], f["ville_norm"],
                        )
                        par_c2.setdefault(cle, []).append(idx)
                for idxs in par_c2.values():
                    first = idxs[0]
                    for other in idxs[1:]:
                        if uf.find(first) != uf.find(other) and uf.union(first, other, regle="C2"):
                            stats["c2"] += 1
                            liens_intra.append((idx_to_id_list[first], idx_to_id_list[other], "C2", 80))

                # 2c. Passe C3 intra-lot
                par_c3: Dict[Tuple, List[int]] = {}
                for idx, f in enumerate(fiches_delta):
                    if (
                        f["nom_norm"] and f["prenoms_trie_norm"]
                        and f["date_naiss_norm"] and f["lieu_naiss_norm"]
                    ):
                        cle = (f["nom_norm"], f["prenoms_trie_norm"], f["date_naiss_norm"], f["lieu_naiss_norm"])
                        par_c3.setdefault(cle, []).append(idx)
                for idxs in par_c3.values():
                    first = idxs[0]
                    for other in idxs[1:]:
                        if uf.find(first) != uf.find(other) and uf.union(first, other, regle="C3"):
                            stats["c3"] += 1
                            liens_intra.append((idx_to_id_list[first], idx_to_id_list[other], "C3", 60))

                # 2d. Passe 5bis Floue intra-lot (bloc date_naiss_norm + sexe_norm)
                par_bloc: Dict[Tuple[str, str], List[int]] = {}
                for idx, f in enumerate(fiches_delta):
                    if f["date_naiss_norm"] and f["sexe_norm"]:
                        par_bloc.setdefault((f["date_naiss_norm"], f["sexe_norm"]), []).append(idx)
                for idxs in par_bloc.values():
                    if len(idxs) < 2 or len(idxs) > 300:
                        continue
                    for i in range(len(idxs)):
                        idx_a = idxs[i]
                        fa = fiches_delta[idx_a]
                        for j in range(i + 1, len(idxs)):
                            idx_b = idxs[j]
                            if uf.find(idx_a) == uf.find(idx_b):
                                continue
                            fb = fiches_delta[idx_b]
                            res = _evaluer_paire_floue(fa, fb)
                            if not res:
                                continue
                            decision, regle, score = res
                            if decision == "UNION":
                                if uf.union(idx_a, idx_b, regle=regle):
                                    stats["flou"] += 1
                                    liens_intra.append((fa["id_fiche"], fb["id_fiche"], regle, score))
                            else:
                                ajouter_paire_validation(fa["id_fiche"], fb["id_fiche"], decision, regle, score)

                # 2e. Passes C4a, C4b & 6bis intra-lot
                par_c4a: Dict[Tuple, List[int]] = {}
                par_c4b: Dict[Tuple, List[int]] = {}
                par_tel: Dict[str, List[int]] = {}
                for idx, f in enumerate(fiches_delta):
                    if f["tel_norm"]:
                        par_tel.setdefault(f["tel_norm"], []).append(idx)
                        if f["nom_norm"] and f["prenoms_trie_norm"]:
                            par_c4a.setdefault((f["nom_norm"], f["prenoms_trie_norm"], f["tel_norm"]), []).append(idx)
                    if f["mail_norm"] and f["nom_norm"] and f["prenoms_trie_norm"]:
                        par_c4b.setdefault((f["nom_norm"], f["prenoms_trie_norm"], f["mail_norm"]), []).append(idx)

                for idxs in par_c4a.values():
                    for i in range(len(idxs)):
                        for j in range(i + 1, len(idxs)):
                            if uf.find(idxs[i]) != uf.find(idxs[j]):
                                ajouter_paire_validation(
                                    idx_to_id_list[idxs[i]], idx_to_id_list[idxs[j]], "AMBIGU_C4A", "C4a", 50
                                )
                for idxs in par_c4b.values():
                    for i in range(len(idxs)):
                        for j in range(i + 1, len(idxs)):
                            if uf.find(idxs[i]) != uf.find(idxs[j]):
                                ajouter_paire_validation(
                                    idx_to_id_list[idxs[i]], idx_to_id_list[idxs[j]], "AMBIGU_C4B", "C4b", 50
                                )
                for idxs in par_tel.values():
                    if 2 <= len(idxs) <= 50:
                        for i in range(len(idxs)):
                            for j in range(i + 1, len(idxs)):
                                if uf.find(idxs[i]) != uf.find(idxs[j]):
                                    ajouter_paire_validation(
                                        idx_to_id_list[idxs[i]], idx_to_id_list[idxs[j]],
                                        "AMBIGU_FLOU_CONTACT", "C4a_FLOU", 45,
                                    )

                for id_a, id_b, regle in uf.conflits_cin:
                    ajouter_paire_validation(id_a, id_b, "CONFLIT_CIN", regle, 0)

                # 3. Recherche indexée contre l'historique (Delta x Historique WHERE uid IS NOT NULL)
                root_hist_uid: Dict[int, str] = {}
                hist_uid_cin: Dict[str, int] = {}
                hist_id_to_uid: Dict[int, str] = {}
                liens_hist: List[Tuple[str, int, int, str, int]] = []

                def tenter_rattachement_historique(
                    idx_d: int, id_d: int, id_h: int, uid_h: str, cin_h_str: Optional[str], regle: str, score: int
                ) -> bool:
                    hist_id_to_uid[id_h] = uid_h
                    r = uf.find(idx_d)
                    cin_d = uf.cluster_cin[r]
                    cin_h = int(cin_h_str.strip()) if (cin_h_str and cin_h_str.strip()) else -1
                    cin_eff_h = hist_uid_cin.get(uid_h, cin_h)
                    if cin_eff_h != -1:
                        hist_uid_cin[uid_h] = cin_eff_h

                    # Verrou strict anti-conflit de CIN (ou suspicion de faute à 1 chiffre)
                    if cin_d != -1 and cin_eff_h != -1 and cin_d != cin_eff_h:
                        dl_cin = DamerauLevenshtein.distance(str(cin_d), str(cin_eff_h), score_cutoff=2)
                        if dl_cin == 1:
                            ajouter_paire_validation(id_d, id_h, "SUSPICION_FAUTE_CIN", regle, 75)
                        else:
                            ajouter_paire_validation(id_d, id_h, "CONFLIT_CIN", regle, 0)
                        return False

                    if r in root_hist_uid:
                        if root_hist_uid[r] == uid_h:
                            return False
                        return False

                    root_hist_uid[r] = uid_h
                    if cin_d != -1 and cin_eff_h == -1:
                        hist_uid_cin[uid_h] = cin_d
                    elif cin_d == -1 and cin_eff_h != -1:
                        uf.cluster_cin[r] = cin_eff_h

                    liens_hist.append((uid_h, min(id_d, id_h), max(id_d, id_h), regle, score))
                    return True

                # 3a. Recherche C1 historique sur idx_fiches_cin_norm
                cins_delta = list({f["cin_norm"] for f in fiches_delta if f["cin_norm"]})
                if cins_delta:
                    cur.execute("""
                        SELECT DISTINCT ON (h.cin_norm)
                            h.cin_norm, h.id_fiche, h.uid::text, COALESCE(g.cin_principal, h.cin_norm)
                        FROM etl.fiches_clients h
                        LEFT JOIN etl.groupes_uid g ON g.uid = h.uid
                        WHERE h.uid IS NOT NULL AND h.cin_norm = ANY(%s)
                        ORDER BY h.cin_norm, h.id_fiche;
                    """, (cins_delta,))
                    hist_par_cin = {row[0].strip(): (row[1], row[2], row[3]) for row in cur.fetchall()}
                    for idx, f in enumerate(fiches_delta):
                        cin_k = f["cin_norm"]
                        if cin_k and cin_k in hist_par_cin:
                            id_h, uid_h, cin_h_str = hist_par_cin[cin_k]
                            if tenter_rattachement_historique(idx, f["id_fiche"], id_h, uid_h, cin_h_str, "C1", 100):
                                stats["c1"] += 1

                # 3b. Recherche C2 & C3 historique sur idx_fiches_nom_prenoms_date
                cles_npd = list({
                    (f["nom_norm"], f["prenoms_trie_norm"], f["date_naiss_norm"])
                    for f in fiches_delta
                    if f["nom_norm"] and f["prenoms_trie_norm"] and f["date_naiss_norm"] and f["lieu_naiss_norm"]
                })
                if cles_npd:
                    noms_arr = [c[0] for c in cles_npd]
                    pres_arr = [c[1] for c in cles_npd]
                    naiss_arr = [c[2] for c in cles_npd]
                    cur.execute("""
                        SELECT
                            h.id_fiche, h.uid::text, COALESCE(g.cin_principal, h.cin_norm),
                            h.nom_norm, h.prenoms_trie_norm, h.date_naiss_norm::text,
                            h.lieu_naiss_norm, h.ville_norm
                        FROM unnest(%s::text[], %s::text[], %s::date[]) AS k(nom, pre_trie, naiss)
                        JOIN etl.fiches_clients h
                          ON h.nom_norm = k.nom
                         AND h.prenoms_trie_norm = k.pre_trie
                         AND h.date_naiss_norm = k.naiss
                        LEFT JOIN etl.groupes_uid g ON g.uid = h.uid
                        WHERE h.uid IS NOT NULL AND h.lieu_naiss_norm IS NOT NULL
                        ORDER BY h.id_fiche;
                    """, (noms_arr, pres_arr, naiss_arr))
                    rows_npd = cur.fetchall()

                    hist_c2: Dict[Tuple, List[Tuple]] = {}
                    hist_c3: Dict[Tuple, List[Tuple]] = {}
                    for id_h, uid_h, cin_h_str, nom_h, pre_h, naiss_h, lieu_h, ville_h in rows_npd:
                        hist_id_to_uid[id_h] = uid_h
                        if ville_h:
                            hist_c2.setdefault((nom_h, pre_h, naiss_h, lieu_h, ville_h), []).append(
                                (id_h, uid_h, cin_h_str)
                            )
                        hist_c3.setdefault((nom_h, pre_h, naiss_h, lieu_h), []).append(
                            (id_h, uid_h, cin_h_str)
                        )

                    # Passe C2 historique (80 %)
                    for idx, f in enumerate(fiches_delta):
                        if (
                            f["nom_norm"] and f["prenoms_trie_norm"] and f["date_naiss_norm"]
                            and f["lieu_naiss_norm"] and f["ville_norm"]
                        ):
                            cle2 = (
                                f["nom_norm"], f["prenoms_trie_norm"], f["date_naiss_norm"],
                                f["lieu_naiss_norm"], f["ville_norm"],
                            )
                            for id_h, uid_h, cin_h_str in hist_c2.get(cle2, ()):
                                if tenter_rattachement_historique(
                                    idx, f["id_fiche"], id_h, uid_h, cin_h_str, "C2", 80
                                ):
                                    stats["c2"] += 1

                    # Passe C3 historique (60 %)
                    for idx, f in enumerate(fiches_delta):
                        if (
                            f["nom_norm"] and f["prenoms_trie_norm"]
                            and f["date_naiss_norm"] and f["lieu_naiss_norm"]
                        ):
                            cle3 = (
                                f["nom_norm"], f["prenoms_trie_norm"],
                                f["date_naiss_norm"], f["lieu_naiss_norm"],
                            )
                            for id_h, uid_h, cin_h_str in hist_c3.get(cle3, ()):
                                if tenter_rattachement_historique(
                                    idx, f["id_fiche"], id_h, uid_h, cin_h_str, "C3", 60
                                ):
                                    stats["c3"] += 1

                # 3c. Recherche 5bis Floue historique sur idx_fiches_bloc_naiss_sexe
                blocs_ns = list({
                    (f["date_naiss_norm"], f["sexe_norm"])
                    for f in fiches_delta
                    if f["date_naiss_norm"] and f["sexe_norm"]
                })
                if blocs_ns:
                    b_naiss = [b[0] for b in blocs_ns]
                    b_sexe = [b[1] for b in blocs_ns]
                    cur.execute("""
                        SELECT
                            h.id_fiche, h.uid::text, COALESCE(g.cin_principal, h.cin_norm),
                            h.cin_norm, h.cin_chiffres, h.nom_norm, h.prenoms_norm, h.prenoms_trie_norm,
                            h.lieu_naiss_norm, h.ville_norm, h.date_naiss_norm::text, h.sexe_norm
                        FROM unnest(%s::date[], %s::text[]) AS k(naiss, sexe)
                        JOIN etl.fiches_clients h
                          ON h.date_naiss_norm = k.naiss
                         AND h.sexe_norm = k.sexe
                        LEFT JOIN etl.groupes_uid g ON g.uid = h.uid
                        WHERE h.uid IS NOT NULL
                        ORDER BY h.id_fiche;
                    """, (b_naiss, b_sexe))

                    hist_par_bloc: Dict[Tuple[str, str], List[Dict[str, any]]] = {}
                    for r_h in cur.fetchall():
                        (
                            id_h, uid_h, cin_grp_h, cin_norm_h, cin_chiffres_h,
                            nom_h, pre_h, pre_trie_h, lieu_h, ville_h, naiss_h, sexe_h,
                        ) = r_h
                        hist_id_to_uid[id_h] = uid_h
                        cle_b = (naiss_h, sexe_h.strip() if sexe_h else None)
                        hist_par_bloc.setdefault(cle_b, []).append({
                            "id_fiche": id_h,
                            "uid": uid_h,
                            "cin_grp": cin_grp_h.strip() if cin_grp_h else None,
                            "cin_norm": cin_norm_h.strip() if cin_norm_h else None,
                            "cin_chiffres": cin_chiffres_h,
                            "nom_norm": nom_h,
                            "prenoms_norm": pre_h,
                            "prenoms_trie_norm": pre_trie_h,
                            "lieu_naiss_norm": lieu_h,
                            "ville_norm": ville_h,
                        })

                    for idx, fa in enumerate(fiches_delta):
                        if not fa["date_naiss_norm"] or not fa["sexe_norm"]:
                            continue
                        candidats_h = hist_par_bloc.get((fa["date_naiss_norm"], fa["sexe_norm"]), ())
                        if len(candidats_h) > 300:
                            continue
                        for fb in candidats_h:
                            r = uf.find(idx)
                            if root_hist_uid.get(r) == fb["uid"]:
                                continue
                            res = _evaluer_paire_floue(fa, fb)
                            if not res:
                                continue
                            decision, regle, score = res
                            if decision == "UNION":
                                if tenter_rattachement_historique(
                                    idx, fa["id_fiche"], fb["id_fiche"],
                                    fb["uid"], fb["cin_grp"], regle, score,
                                ):
                                    stats["flou"] += 1
                            else:
                                ajouter_paire_validation(
                                    fa["id_fiche"], fb["id_fiche"], decision, regle, score
                                )

                # 3d. Recherche C4a, C4b & 6bis sur idx_fiches_tel_norm et idx_fiches_mail_norm
                tels_delta = list({f["tel_norm"] for f in fiches_delta if f["tel_norm"]})
                if tels_delta:
                    cur.execute("""
                        SELECT h.id_fiche, h.uid::text, h.nom_norm, h.prenoms_trie_norm, h.tel_norm
                        FROM etl.fiches_clients h
                        WHERE h.uid IS NOT NULL AND h.tel_norm = ANY(%s)
                        ORDER BY h.id_fiche;
                    """, (tels_delta,))
                    hist_par_tel: Dict[str, List[Tuple]] = {}
                    for id_h, uid_h, nom_h, pre_h, tel_h in cur.fetchall():
                        hist_id_to_uid[id_h] = uid_h
                        hist_par_tel.setdefault(tel_h, []).append((id_h, uid_h, nom_h, pre_h))

                    for idx, f in enumerate(fiches_delta):
                        t_k = f["tel_norm"]
                        if not t_k or t_k not in hist_par_tel:
                            continue
                        cands = hist_par_tel[t_k]
                        if len(cands) > 50:
                            continue
                        r = uf.find(idx)
                        uid_d = root_hist_uid.get(r)
                        for id_h, uid_h, nom_h, pre_h in cands:
                            if uid_d == uid_h:
                                continue
                            if (
                                f["nom_norm"] and f["prenoms_trie_norm"]
                                and f["nom_norm"] == nom_h and f["prenoms_trie_norm"] == pre_h
                            ):
                                ajouter_paire_validation(f["id_fiche"], id_h, "AMBIGU_C4A", "C4a", 50)
                            else:
                                ajouter_paire_validation(
                                    f["id_fiche"], id_h, "AMBIGU_FLOU_CONTACT", "C4a_FLOU", 45
                                )

                mails_delta = list({
                    f["mail_norm"] for f in fiches_delta
                    if f["mail_norm"] and f["nom_norm"] and f["prenoms_trie_norm"]
                })
                if mails_delta:
                    cur.execute("""
                        SELECT h.id_fiche, h.uid::text, h.nom_norm, h.prenoms_trie_norm, h.mail_norm
                        FROM etl.fiches_clients h
                        WHERE h.uid IS NOT NULL AND h.mail_norm = ANY(%s)
                        ORDER BY h.id_fiche;
                    """, (mails_delta,))
                    hist_par_mail: Dict[str, List[Tuple]] = {}
                    for id_h, uid_h, nom_h, pre_h, mail_h in cur.fetchall():
                        hist_id_to_uid[id_h] = uid_h
                        hist_par_mail.setdefault(mail_h, []).append((id_h, uid_h, nom_h, pre_h))

                    for idx, f in enumerate(fiches_delta):
                        m_k = f["mail_norm"]
                        if not m_k or m_k not in hist_par_mail:
                            continue
                        r = uf.find(idx)
                        uid_d = root_hist_uid.get(r)
                        for id_h, uid_h, nom_h, pre_h in hist_par_mail[m_k]:
                            if uid_d == uid_h:
                                continue
                            if f["nom_norm"] == nom_h and f["prenoms_trie_norm"] == pre_h:
                                ajouter_paire_validation(f["id_fiche"], id_h, "AMBIGU_C4B", "C4b", 50)

                # 4. Attribution non bloquante du UID (Cas A, Cas B, Cas C)
                min_id_par_root: Dict[int, int] = {}
                for idx, f in enumerate(fiches_delta):
                    r = uf.find(idx)
                    if r not in min_id_par_root or f["id_fiche"] < min_id_par_root[r]:
                        min_id_par_root[r] = f["id_fiche"]

                # Filtrage des cas de validation pour ne conserver que les paires d'UIDs distincts
                ids_en_validation = set()
                root_to_uuid: Dict[int, str] = {}
                for r, min_id in min_id_par_root.items():
                    if r in root_hist_uid:
                        root_to_uuid[r] = root_hist_uid[r]
                    else:
                        root_to_uuid[r] = str(uuid.uuid5(NAMESPACE_CLIENT, f"client:{min_id}"))

                def resoudre_uid_fiche(id_f: int) -> str:
                    if id_f in id_to_idx_map:
                        return root_to_uuid[uf.find(id_to_idx_map[id_f])]
                    return hist_id_to_uid[id_f]

                cas_validation_finaux = []
                for id_a, id_b, motif, regle, score in cas_validation:
                    uid_a = resoudre_uid_fiche(id_a)
                    uid_b = resoudre_uid_fiche(id_b)
                    if uid_a != uid_b:
                        cas_validation_finaux.append((id_a, id_b, uid_a, uid_b, motif, regle, score))
                        ids_en_validation.add(id_a)
                        ids_en_validation.add(id_b)

                # Comptabilisation Cas A / Cas B / Cas C par fiche traitée
                for idx, f in enumerate(fiches_delta):
                    r = uf.find(idx)
                    if r in root_hist_uid:
                        stats["cas_a_reconnus"] += 1
                    elif f["id_fiche"] in ids_en_validation:
                        stats["cas_c_provisoires"] += 1
                    else:
                        stats["cas_b_nouveaux"] += 1

                # 5. Mise à jour de etl.fiches_clients, etl.groupes_uid, etl.file_validation et etl.liens_rapprochement
                for idx, f in enumerate(fiches_delta):
                    u_val = root_to_uuid[uf.find(idx)]
                    if f["besoin_maj_norm"]:
                        cur.execute("""
                            UPDATE etl.fiches_clients
                            SET uid = %s,
                                cin_norm = %s, cin_chiffres = %s,
                                nom_norm = %s, prenoms_norm = %s, prenoms_trie_norm = %s,
                                date_naiss_norm = %s, lieu_naiss_norm = %s, ville_norm = %s,
                                tel_norm = %s, tel_chiffres = %s, mail_norm = %s, sexe_norm = %s
                            WHERE id_fiche = %s;
                        """, (
                            u_val,
                            f["cin_norm"], f["cin_chiffres"],
                            f["nom_norm"], f["prenoms_norm"], f["prenoms_trie_norm"],
                            f["date_naiss_norm"], f["lieu_naiss_norm"], f["ville_norm"],
                            f["tel_norm"], f["tel_chiffres"], f["mail_norm"], f["sexe_norm"],
                            f["id_fiche"],
                        ))
                    else:
                        cur.execute(
                            "UPDATE etl.fiches_clients SET uid = %s WHERE id_fiche = %s;",
                            (u_val, f["id_fiche"]),
                        )

                uids_impactes = list(set(root_to_uuid.values()))
                if uids_impactes:
                    cur.execute("""
                        INSERT INTO etl.groupes_uid (
                            uid, nb_fiches, sources,
                            cin_principal, nom_principal, prenoms_principal,
                            date_naiss_principale, ville_principale, maj_le
                        )
                        SELECT
                            uid,
                            count(*)::integer AS nb_fiches,
                            array_agg(DISTINCT source_system) AS sources,
                            max(cin_norm) AS cin_principal,
                            max(nom_norm) AS nom_principal,
                            max(prenoms_norm) AS prenoms_principal,
                            max(date_naiss_norm) AS date_naiss_principale,
                            max(ville_norm) AS ville_principale,
                            now()
                        FROM etl.fiches_clients
                        WHERE uid = ANY(%s::uuid[])
                        GROUP BY uid
                        ON CONFLICT (uid) DO UPDATE SET
                            nb_fiches = EXCLUDED.nb_fiches,
                            sources = EXCLUDED.sources,
                            cin_principal = COALESCE(etl.groupes_uid.cin_principal, EXCLUDED.cin_principal),
                            nom_principal = COALESCE(etl.groupes_uid.nom_principal, EXCLUDED.nom_principal),
                            prenoms_principal = COALESCE(etl.groupes_uid.prenoms_principal, EXCLUDED.prenoms_principal),
                            date_naiss_principale = COALESCE(etl.groupes_uid.date_naiss_principale, EXCLUDED.date_naiss_principale),
                            ville_principale = COALESCE(etl.groupes_uid.ville_principale, EXCLUDED.ville_principale),
                            maj_le = now();
                    """, (uids_impactes,))

                # Enregistrement des cas en attente d'arbitrage humain (sans doublon)
                for id_a, id_b, uid_a, uid_b, motif, regle, score in cas_validation_finaux:
                    cur.execute("""
                        INSERT INTO etl.file_validation (id_fiche_a, id_fiche_b, uid_a, uid_b, motif, regle, score)
                        SELECT %s, %s, %s, %s, %s, %s, %s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM etl.file_validation v
                            WHERE v.id_fiche_a = %s AND v.id_fiche_b = %s
                        );
                    """, (id_a, id_b, uid_a, uid_b, motif, regle, score, id_a, id_b))
                    if cur.rowcount > 0:
                        stats["validation"] += 1

                # Traçabilité dans etl.liens_rapprochement
                for id_a, id_b, regle, score in liens_intra:
                    u_val = resoudre_uid_fiche(id_a)
                    cur.execute("""
                        INSERT INTO etl.liens_rapprochement (uid, id_fiche_a, id_fiche_b, regle, score, valide_par)
                        VALUES (%s, %s, %s, %s, %s, 'SYSTEM');
                    """, (u_val, min(id_a, id_b), max(id_a, id_b), regle, score))

                for uid_h, id_a, id_b, regle, score in liens_hist:
                    cur.execute("""
                        INSERT INTO etl.liens_rapprochement (uid, id_fiche_a, id_fiche_b, regle, score, valide_par)
                        VALUES (%s, %s, %s, %s, %s, 'SYSTEM');
                    """, (uid_h, id_a, id_b, regle, score))

            conn.commit()
            total_traite += n_delta
            chunks_traites += 1
            print(
                f"-> Lot #{chunks_traites} validé ({n_delta:,} fiches traitées, "
                f"cumul : {total_traite:,}/{cible:,})."
            )

    duree = time.perf_counter() - debut
    with get_etl_connection() as conn:
        with conn.cursor() as cur:
            verrouiller_ecritures_etl(cur)
            cur.execute("SELECT count(*) FROM etl.fiches_clients WHERE uid IS NULL;")
            restant_null = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO etl.journal_executions (phase, statut, duree_secondes, lignes_traitees, details)
                VALUES (%s, %s, %s, %s, %s);
            """, (
                "INCREMENTAL", "SUCCES", round(duree, 2), total_traite,
                json.dumps({
                    "fiches_traitees": total_traite,
                    "chunks_traites": chunks_traites,
                    "cas_a_reconnus": stats["cas_a_reconnus"],
                    "cas_b_nouveaux": stats["cas_b_nouveaux"],
                    "cas_c_provisoires": stats["cas_c_provisoires"],
                    "c1_reunions": stats["c1"],
                    "c2_reunions": stats["c2"],
                    "c3_reunions": stats["c3"],
                    "flou_reunions": stats["flou"],
                    "cas_validation": stats["validation"],
                    "restant_uid_null": restant_null,
                }),
            ))
        conn.commit()

    print(
        f"\nLot incrémental terminé en {duree:.2f} s : {total_traite:,} fiches traitées "
        f"(Cas A reconnus : {stats['cas_a_reconnus']:,}, Cas B nouveaux : {stats['cas_b_nouveaux']:,}, "
        f"Cas C provisoires : {stats['cas_c_provisoires']:,}, restant sans UID : {restant_null:,})."
    )
    return {
        "fiches_traitees": total_traite,
        "chunks_traites": chunks_traites,
        "cas_a_reconnus": stats["cas_a_reconnus"],
        "cas_b_nouveaux": stats["cas_b_nouveaux"],
        "cas_c_provisoires": stats["cas_c_provisoires"],
        "c1": stats["c1"],
        "c2": stats["c2"],
        "c3": stats["c3"],
        "flou": stats["flou"],
        "validation": stats["validation"],
        "restant_uid_null": restant_null,
        "duree": duree,
    }
