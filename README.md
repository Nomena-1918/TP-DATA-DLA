# TP Data D.L.A — Réconciliation d'Identités Clients & Référentiel Unique (`UID`)

TP de licence en informatique sur le rapprochement de fiches clients et la conception d'un référentiel pivot unique (`UID`), dans un scénario d’assurance fictif à Madagascar.

Afin de garantir une exécution fluide et rapide sur les postes de travail des étudiants sans saturer la mémoire vive ni le processeur, le TP s'appuie exclusivement sur la **version légère (400 000 fiches au total)** :
- **Auto** : PostgreSQL 16 (100 000 fiches d'assurance automobile).
- **Life** : MySQL 8.4 (100 000 fiches d'épargne vie et retraite).
- **Autre** : Fichier plat CSV de 200 000 fiches (100 000 fiches agricoles et 100 000 maritimes).

| Emplacement | Contenu |
| --- | --- |
| [docs/etudiant/ENONCE-TP.md](docs/etudiant/ENONCE-TP.md) | Énoncé complet du TP et description détaillée des sources. |
| [docs/etudiant/FICHE-DECOUVERTE.md](docs/etudiant/FICHE-DECOUVERTE.md) | Grille d'exploration et de relevé des anomalies. |
| [docs/etudiant/REGLES-RAPPROCHEMENT.md](docs/etudiant/REGLES-RAPPROCHEMENT.md) | Matrice de décision C1–C4, verrou anti-conflit CIN et seuils flous. |
| [docs/enseignant/](docs/enseignant/) | Procédures de préparation, blueprints des slides et détails de génération. |
| [notebooks/01_exploration.ipynb](notebooks/01_exploration.ipynb) | Notebook d'exploration en lecture seule des trois sources. |
| `data/clients_autre.csv` | CSV Autre (version légère 200k fiches). |
| [scripts/](scripts/) | Générateur déterministe (`generer_autre.py`) et script d'audit qualité (`evaluer_qualite.py`). |
| [sql/leger/](sql/leger/) | Scripts de chargement rapide Auto (PostgreSQL 16) et Life (MySQL 8.4). |
| `src/tp_data_dla/` | Module applicatif Python (normalisation, ETL streaming, Union-Find et application Web). |

---

## 1. Prérequis et installation de l’environnement Python

Le projet nécessite **Python >= 3.12** et le gestionnaire d'environnements **`uv`** (Astral).

Depuis la racine du projet, synchronisez l'environnement verrouillé :
```sh
uv sync --locked --python 3.12
```

Vérifiez immédiatement la disponibilité des pilotes relationnels sans ouvrir de connexion :
```sh
uv run --locked python -c "import psycopg, mysql.connector; print('Pilotes PostgreSQL et MySQL opérationnels !')"
```

> [!TIP]
> Par défaut, `uv` gère son environnement virtuel sous `.venv/`. Si votre IDE utilise un dossier `venv/` existant, vous pouvez définir `export UV_PROJECT_ENVIRONMENT=venv` dans votre terminal avant de lancer les commandes `uv`.

---

## 2. Charger les bases de données locales (Auto et Life)

Préparez les deux bases dédiées sur vos moteurs SGBD locaux :
- PostgreSQL 16 (port 5432) : base `tp_assurance_auto` (encodage `UTF-8`).
- MySQL 8.4 (port 3306) : base `tp_assurance_life` (encodage `utf8mb4`).

Exécutez les scripts de chargement de la version légère depuis la racine du projet :
```sh
# Chargement de la source Auto (100 000 fiches sur PostgreSQL 16)
psql -X -d tp_assurance_auto -f sql/leger/charger_auto_postgresql.sql

# Chargement de la source Life (100 000 fiches sur MySQL 8.4)
mysql --batch --skip-force --default-character-set=utf8mb4 \
  --database=tp_assurance_life < sql/leger/charger_life_mysql.sql
```

Contrôlez les volumes et les plages d'identifiants créés :
```sh
psql -X -d tp_assurance_auto -c \
  'SELECT count(*), min(id_client_auto), max(id_client_auto) FROM tp_assurance.clients_auto;'
mysql --default-character-set=utf8mb4 --database=tp_assurance_life \
  --execute='SELECT count(*), min(ref_adherent), max(ref_adherent) FROM tp_assurance_life.clients_life;'
```

Résultats attendus :
- **Auto** : `100 000` fiches, plage de `1 000 001` à `1 100 000`.
- **Life** : `100 000` fiches, plage de `3 000 001` à `3 100 000`.

---

## 3. Générer ou vérifier la source plate Autre (CSV)

Le fichier `data/clients_autre.csv` est encodé en UTF-8, avec une ligne d'en-tête et un séparateur point-virgule (`;`). Il comprend **200 000 fiches** (100 000 agricoles et 100 000 maritimes).

Pour vérifier son volume :
```python
import csv
from pathlib import Path

with Path("data/clients_autre.csv").open(encoding="utf-8", newline="") as f:
    lecteur = csv.DictReader(f, delimiter=";")
    print(sum(1 for _ in lecteur))  # Affiche 200000
```

Si le fichier n'est pas encore présent, générez-le directement en mode léger :
```sh
python3 scripts/generer_autre.py --mode leger --sortie data/clients_autre.csv
wc -l data/clients_autre.csv
```
La commande `wc -l` doit retourner **200 001 lignes** (200 000 enregistrements de données + 1 ligne d'en-tête).

---

## 4. Lancer le notebook d’exploration (Partie 1)

Installez les dépendances du groupe optionnel `notebook` :
```sh
uv sync --locked --python 3.12 --group notebook
```

Configurez vos identifiants d'accès dans le fichier `.env` (en vous basant sur `.env.example`) ou exportez les variables d'environnement, puis démarrez JupyterLab :
```sh
export TP_AUTO_HOST=127.0.0.1 TP_AUTO_PORT=5432 TP_AUTO_USER=lecteur_auto
export TP_LIFE_HOST=127.0.0.1 TP_LIFE_PORT=3306 TP_LIFE_USER=lecteur_life
uv run --locked --group notebook jupyter lab --ip=127.0.0.1
```

Ouvrez `notebooks/01_exploration.ipynb` et exécutez les cellules dans l'ordre pour relever les hétérogénéités de formats et compléter `docs/etudiant/FICHE-DECOUVERTE.md`.

---

## 5. Exécuter le pipeline complet de réconciliation

Le pilotage du pipeline s'effectue via l'outil en ligne de commande `tp-dla` :

```sh
# 1. Initialiser le schéma cible dans tp_assurance_etl (sans colonne uid)
uv run tp-dla init-db

# 2. Extraire, normaliser et charger les 400 000 fiches en streaming
uv run tp-dla etl --dataset leger

# 3. Ajouter manuellement la colonne pivot UID (Phase 4)
uv run tp-dla add-uid-column

# 4. Exécuter le moteur Union-Find (passes exactes C1-C3 et passe floue adaptative)
uv run tp-dla union-find

# 5. Créer les index finaux
uv run tp-dla create-indexes

# 6. Évaluer la précision, le rappel et la pureté des clusters formés
uv run python scripts/evaluer_qualite.py

# 7. Lancer la mini-application Web de consultation 360° et de validation humaine
uv run tp-dla web --host 127.0.0.1 --port 8000
```

Accessible depuis votre navigateur sur `http://127.0.0.1:8000`.

---

## 6. Exécution des tests automatisés

Lancez la suite de tests unitaires et de validation :
```sh
uv run pytest
```
