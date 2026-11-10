# TP Data D.L.A

TP de licence sur le rapprochement de fiches clients, dans un scénario
d’assurance fictif à Madagascar. Auto est sur PostgreSQL 16 et Life sur MySQL
8.4, avec un million de fiches chacune après chargement. Autre est un CSV de
deux millions de fiches agricoles et maritimes.

| Emplacement | Contenu |
| --- | --- |
| [docs/etudiant/](docs/etudiant/) | Énoncé de découverte des sources. |
| [docs/enseignant/](docs/enseignant/) | Procédure de préparation et détails de génération. |
| [notebooks/01_exploration.ipynb](notebooks/01_exploration.ipynb) | Exploration en lecture seule des trois sources. |
| `data/` | CSV Autre livré localement. Le fichier volumineux est ignoré par Git. |
| [scripts/](scripts/) | Générateur déterministe du CSV Autre. |
| [sql/](sql/) | Scripts de chargement Auto (PostgreSQL 16) et Life (MySQL 8.4). |
| `main.py` | Point de départ du projet Python. |

## Installer l’environnement Python

Utiliser Python 3.12 ou supérieur et `uv`. Le projet conserve sa version et sa
contrainte Python d’origine. Depuis la racine, synchroniser l’environnement
avec le fichier `uv.lock`, puis vérifier les imports sans ouvrir de connexion.

```sh
uv sync --locked --python 3.12
uv run --locked python -c 'import psycopg, mysql.connector; print(psycopg.__version__, mysql.connector.__version__)'
```

Par défaut, `uv` utilise `.venv/`. Si l’IDE pointe déjà vers `venv/`,
exécuter `export UV_PROJECT_ENVIRONMENT=venv` dans le terminal avant les
commandes `uv`. [Environnements de projet uv](https://docs.astral.sh/uv/concepts/projects/config/)

`psycopg[binary]` fournit le pilote PostgreSQL, importé par `psycopg`.
`mysql-connector-python` fournit `mysql.connector` pour Life sur MySQL 8.4.
Conserver les paramètres de connexion dans
l’environnement local. [Installation de Psycopg](https://www.psycopg.org/install/) · [Versions de MySQL Connector/Python](https://dev.mysql.com/doc/connector-python/en/connector-python-versions.html)

## Lancer le notebook d’exploration

Depuis la racine du projet, installer le groupe optionnel `notebook`.
Remplacer les noms d’utilisateur d’exemple par ceux des comptes en lecture
fournis pour le TP. Adapter les adresses et ports si les bases ne sont pas
sur la machine locale.

```sh
uv sync --locked --python 3.12 --group notebook
export TP_AUTO_HOST=127.0.0.1 TP_AUTO_PORT=5432 TP_AUTO_USER=lecteur_auto
export TP_LIFE_HOST=127.0.0.1 TP_LIFE_PORT=3306 TP_LIFE_USER=lecteur_life
uv run --locked --group notebook jupyter lab --ip=127.0.0.1
```

Ouvrir `notebooks/01_exploration.ipynb` avec le noyau Python 3 et exécuter
les cellules dans l’ordre. Les variables `TP_AUTO_PASSWORD` et
`TP_LIFE_PASSWORD` peuvent être fournies par l’environnement du processus.
Sinon, le noyau demande les mots de passe dans une saisie masquée.

Le mode rapide affiche les types et des échantillons bornés. Pour le
profil complet, définir `PROFIL_COMPLET = True` dans la cellule de
configuration ou lancer JupyterLab avec `TP_PROFIL_COMPLET=1`. Les
bases calculent les agrégats et le CSV est parcouru une seule fois.
Le chemin du CSV est résolu depuis la racine du projet ou depuis `notebooks/`.

## Lire ou reproduire Autre

Le CSV `data/clients_autre.csv` est en UTF-8, avec une ligne d’en-tête et
des champs séparés par des points-virgules. Le module standard `csv` lit les
fiches en flux et conserve les valeurs sous forme de texte.
La dernière colonne, `code_sexe`, contient `M` (masculin) ou `F` (féminin).

```python
import csv
from pathlib import Path

with Path("data/clients_autre.csv").open(encoding="utf-8", newline="") as fichier:
    fiches = csv.DictReader(fichier, delimiter=";")
    print(sum(1 for _ in fiches))  # 2 000 000
```

Si le CSV manque, le générateur le crée avec la bibliothèque standard depuis
la racine du projet. Cette commande remplace le CSV s’il existe déjà.

```sh
python3 scripts/generer_autre.py
wc -l data/clients_autre.csv
shasum -a 256 data/clients_autre.csv
```

`wc -l` doit indiquer 2 000 001 lignes, en-tête compris. L’empreinte de
référence figure dans la [notice enseignant](docs/enseignant/PREPARATION-ENSEIGNANT.md).

## Charger Auto et Life manuellement

Sur la machine de l’enseignant, préparer `tp_assurance_auto` en UTF-8
sur PostgreSQL 16 et `tp_assurance_life` en `utf8mb4` sur MySQL 8.4. Depuis
la racine, utiliser les deux commandes avec les paramètres de connexion du TP.
La [notice enseignant](docs/enseignant/PREPARATION-ENSEIGNANT.md) détaille les
droits requis, les contrôles après chargement et la reprise en cas d’erreur.

```sh
psql -X -d tp_assurance_auto -f sql/charger_auto_postgresql.sql
mysql --batch --skip-force --default-character-set=utf8mb4 \
  --database=tp_assurance_life < sql/charger_life_mysql.sql
```

## Relancer le pipeline et ouvrir la validation

`init-db` crée les tables manquantes et conserve les tables existantes.
L’ETL charge les trois sources dans une seule transaction et exige une
cible vide. Union-Find publie également ses résultats dans une seule
transaction et refuse de recalculer des UID déjà publiés. Pour refaire
un parcours complet, utiliser une base de test dédiée et vide en
configurant `TP_ETL_DB`.

Renseigner les identifiants de base dans `.env` ou dans l’environnement.
Pour ouvrir la file de validation, configurer aussi `TP_VALIDATION_USER`
et `TP_VALIDATION_PASSWORD`. Le navigateur demande ces identifiants à
l’ouverture de la file. Lancer l’application sur la boucle locale.

```sh
chmod 600 .env
uv run tp-dla web --host 127.0.0.1 --port 8000
```

Pour tester les relances et les arbitrages, sélectionner une base de test
vide dont le nom commence par `tp_dla_test_`, puis lancer `init-db` et
`TP_TEST_ECRITURE=1 uv run pytest`. Le test y écrit des fiches fictives.

## Distribuer les fichiers

Pour la découverte, remettre [l’énoncé étudiant](docs/etudiant/ENONCE-TP.md)
à la racine du dossier de distribution, avec le CSV sous
`data/clients_autre.csv`, le notebook sous `notebooks/` et les accès en
lecture à PostgreSQL et MySQL. Fournir aussi `pyproject.toml`, `uv.lock`
et la section de lancement du README.
Les documents de préparation, les scripts SQL et le générateur restent côté
enseignant.
