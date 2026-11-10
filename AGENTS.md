# TP Data D.L.A — Cadrage & Référentiel Technique

## Contexte et Principes Directeurs

TP de licence fondé sur la problématique de réconciliation d'identités et de dédoublonnage client pour une compagnie d'assurance fictive à Madagascar.

Sources de données locales en lecture seule (Version légère : 400 000 fiches au total) :
- **Auto** (PostgreSQL 16, `tp_assurance.clients_auto`) : 100 000 fiches.
- **Life** (MySQL 8.4, `tp_assurance_life.clients_life`) : 100 000 fiches.
- **Autre** (CSV UTF-8, `data/clients_autre.csv`) : 200 000 fiches.

**Règle d'or de gouvernance** :
- **Zéro suppression et zéro altération** : Aucune ligne source n'est fusionnée physiquement ou supprimée. Toutes les 400 000 fiches individuelles restent intactes et consultables dans la table cible `etl.fiches_clients` avec leur référence et leurs valeurs brutes.
- **Attribution d'un identifiant pivot commun** : Le rapprochement consiste uniquement à attribuer la même valeur sur la colonne `uid` (au format UUID) aux fiches appartenant à une même personne physique afin de permettre leur regroupement instantané en vue 360°.

---

## Commandes de Référence (Build, Exécution et Tests)

Depuis la racine de `TP-DATA-DLA` :

```sh
# 1. Synchronisation de l'environnement Python
uv sync --locked --all-groups

# 2. Exécution des tests automatisés (unitaires et intégration)
uv run pytest

# 3. Chargement des bases de données locales (version légère)
psql -X -d tp_assurance_auto -f sql/leger/charger_auto_postgresql.sql
mysql --batch --skip-force --default-character-set=utf8mb4 \
  --database=tp_assurance_life < sql/leger/charger_life_mysql.sql

# Génération du CSV Autre (version légère 200 000 fiches)
uv run python scripts/generer_autre.py --mode leger --sortie data/clients_autre.csv

# 4. Exécution du pipeline complet
# Option A : Version légère (400 000 fiches - standard officiel pour les étudiants)
uv run tp-dla run-all --dataset leger

# Option B : Version complète (4 000 000 de fiches - serveur dédié de référence)
uv run tp-dla run-all --dataset complet

# (Ou par étapes individuelles selon l'avancement du TP)
uv run tp-dla init-db                      # Étape 1 & 2 : Schéma sans colonne UID
uv run tp-dla etl --dataset leger          # Étape 3 : Chargement (400k) + index de base
uv run tp-dla add-uid-column               # Étape 4 : Ajout manuel de la colonne UID (DDL)
uv run tp-dla union-find                   # Étape 5 : Rapprochement C1-C3 + passes floues + UIDs
uv run tp-dla create-indexes               # Étape 6 : Finalisation et vérification des index

# 5. Audit qualité et métriques sur la vérité terrain
uv run python scripts/evaluer_qualite.py

# 6. Lancement de la mini-application web de visualisation (Étape 6)
uv run tp-dla web --host 127.0.0.1 --port 8000
```

---

## Sécurité et Gestion des Secrets

- Ne jamais commiter de mots de passe ou clés réelles dans le dépôt Git.
- Les fichiers `.env` et `.env.*` sont strictement ignorés par Git.
- Seul `.env.example` avec des valeurs d'exemple (`<utilisateur>`, `<mot_de_passe>`) est versionné.
- Les relances sur une cible déjà chargée doivent préserver les fiches et les décisions. Réserver les essais d’écriture à une base dédiée vide.
- Utiliser la boucle locale (`127.0.0.1`) et un compte opérateur distinct pour la validation.
- Toute anomalie de sécurité ou exposition accidentelle doit être immédiatement signalée et corrigée.
