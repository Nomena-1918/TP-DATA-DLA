"""Interface en ligne de commande (CLI) tp-dla pour piloter le pipeline."""

import argparse
import sys
from pathlib import Path

from tp_data_dla.config import get_etl_connection, verrouiller_ecritures_etl
from tp_data_dla.etl import executer_etl
from tp_data_dla.union_find import executer_lot_incremental, executer_union_find

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"


def executer_script_sql(chemin: Path):
    """Exécute un fichier de script SQL sur la base tp_assurance_etl."""
    if not chemin.is_file():
        raise FileNotFoundError(f"Fichier SQL introuvable : {chemin}")
    print(f"Exécution du script SQL : {chemin.name}...")
    with get_etl_connection() as conn:
        with conn.cursor() as cur:
            verrouiller_ecritures_etl(cur)
            cur.execute(chemin.read_text(encoding="utf-8"))
        conn.commit()
    print(f"-> {chemin.name} exécuté avec succès.")


def commande_init_db(args):
    """Crée le schéma et les tables cibles (sans colonne uid)."""
    executer_script_sql(SQL_DIR / "01_schema_etl.sql")


def commande_etl(args):
    """Lance l'extraction, normalisation et chargement des fiches."""
    executer_etl(limit=args.limit, reset=args.reset, dataset=args.dataset)


def commande_add_uid(args):
    """Ajoute manuellement la colonne uid sur etl.fiches_clients (Étape 4)."""
    executer_script_sql(SQL_DIR / "02_ajouter_uid_manuel.sql")


def commande_union_find(args):
    """Exécute le dédoublonnage Union-Find et affecte les UIDs."""
    executer_union_find()


def commande_incremental(args):
    """Exécute le lot incrémental quotidien (00h00-07h00) sur les fiches WHERE uid IS NULL."""
    executer_lot_incremental(chunk_size=args.chunk_size, limit=args.limit)


def commande_indexes(args):
    """Crée ou met à jour l'ensemble des index sur la base finale."""
    executer_script_sql(SQL_DIR / "03_index_etl.sql")


def commande_run_all(args):
    """Enchaîne toutes les phases dans l'ordre strict du TP."""
    print("=== ÉTAPE 1 & 2 : Initialisation du schéma ETL ===")
    executer_script_sql(SQL_DIR / "01_schema_etl.sql")

    print(f"\n=== ÉTAPE 3 : Pipeline ETL ({args.dataset.upper()}) ===")
    executer_etl(limit=args.limit, reset=False, dataset=args.dataset)

    print("\n=== ÉTAPE 4 : Ajout manuel de la colonne UID ===")
    executer_script_sql(SQL_DIR / "02_ajouter_uid_manuel.sql")

    print("\n=== ÉTAPE 5 : Rapprochement Union-Find & Affectation des UIDs ===")
    executer_union_find()

    print("\n=== ÉTAPE 6 : Finalisation et vérification des index ===")
    executer_script_sql(SQL_DIR / "03_index_etl.sql")

    print("\nPipeline complet exécuté avec succès !")


def commande_web(args):
    """Lance le serveur web FastAPI."""
    import uvicorn
    print(f"Démarrage de la mini-application web sur http://{args.host}:{args.port}...")
    uvicorn.run("tp_data_dla.web.app:app", host=args.host, port=args.port, reload=args.reload)


def main():
    parser = argparse.ArgumentParser(description="Outils du TP Data D.L.A - Réconciliation et Référentiel Client")
    subparsers = parser.add_subparsers(dest="commande", required=True)

    # init-db
    p_init = subparsers.add_parser("init-db", help="Crée le schéma et tables dans tp_assurance_etl")
    p_init.set_defaults(func=commande_init_db)

    # etl
    p_etl = subparsers.add_parser("etl", help="Extrait, normalise et charge les données")
    p_etl.add_argument(
        "--dataset", choices=["leger", "complet"], default="leger",
        help="Version du dataset : 'leger' (400k fiches pour TP étudiants) ou 'complet' (4M fiches)",
    )
    p_etl.add_argument("--limit", type=int, default=None, help="Nombre max de fiches par source")
    p_etl.add_argument("--reset", action="store_true", help="Ancienne option désactivée. Utiliser une cible de test vide.")
    p_etl.set_defaults(func=commande_etl)

    # add-uid-column
    p_uid = subparsers.add_parser("add-uid-column", help="Ajoute manuellement la colonne uid (Phase 4)")
    p_uid.set_defaults(func=commande_add_uid)

    # union-find
    p_uf = subparsers.add_parser("union-find", help="Exécute Union-Find et affecte les UIDs (Phase 5)")
    p_uf.set_defaults(func=commande_union_find)

    # incremental
    p_inc = subparsers.add_parser(
        "incremental",
        help="Lot incrémental quotidien (00h00-07h00) sur les nouvelles fiches WHERE uid IS NULL",
    )
    p_inc.add_argument(
        "--chunk-size", type=int, default=2000,
        help="Taille des lots unitaires pour la reprise sur erreur (défaut : 2000)",
    )
    p_inc.add_argument(
        "--limit", type=int, default=None,
        help="Plafond de fiches en attente à traiter lors de cette exécution",
    )
    p_inc.set_defaults(func=commande_incremental)

    # create-indexes
    p_idx = subparsers.add_parser("create-indexes", help="Crée ou met à jour les index sur la base finale")
    p_idx.set_defaults(func=commande_indexes)

    # run-all
    p_all = subparsers.add_parser("run-all", help="Enchaîne toutes les phases du pipeline")
    p_all.add_argument(
        "--dataset", choices=["leger", "complet"], default="leger",
        help="Version du dataset : 'leger' (400k fiches pour TP étudiants) ou 'complet' (4M fiches)",
    )
    p_all.add_argument("--limit", type=int, default=None, help="Nombre max de fiches par source")
    p_all.set_defaults(func=commande_run_all)

    # web
    p_web = subparsers.add_parser("web", help="Lance la mini-application web (Phase 6)")
    p_web.add_argument("--host", default="127.0.0.1", help="Adresse d'écoute")
    p_web.add_argument("--port", type=int, default=8000, help="Port d'écoute")
    p_web.add_argument("--reload", action="store_true", help="Rechargement à chaud")
    p_web.set_defaults(func=commande_web)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
