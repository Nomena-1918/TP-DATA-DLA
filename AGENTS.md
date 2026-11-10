# TP Data D.L.A — Cadrage & Référentiel Technique (Assurances ARO)

## Contexte et Principes Directeurs

TP de licence fondé sur la problématique de réconciliation d'identités et de dédoublonnage client pour la compagnie Assurances ARO à Madagascar.

Sources de données réelles (lecture seule) :
- **Auto** (PostgreSQL 16, `tp_assurance.clients_auto`) : 1 000 000 de fiches.
- **Life** (MySQL 8.4, `tp_assurance_life.clients_life`) : 1 000 000 de fiches.
- **Autre** (CSV UTF-8, `data/clients_autre.csv`) : 2 000 000 de fiches.

**Règle d'or de gouvernance (Slide 5 du dossier ARO)** :
- **Zéro suppression et zéro altération** : Aucune ligne source n'est fusionnée physiquement ou supprimée. Toutes les 4 000 000 de fiches individuelles restent intactes et consultables dans la table cible `etl.fiches_clients` avec leur référence et leurs valeurs brutes.
- **Attribution d'un identifiant commun** : Le rapprochement consiste uniquement à attribuer la même valeur sur la colonne `uid` (`NEW_ID` au format UUID) aux fiches appartenant à une même personne physique afin de permettre leur regroupement instantané.

---

## Commandes de Référence (Build, Exécution et Tests)

Depuis la racine de `TP-DATA-DLA` :

```sh
# 1. Synchronisation de l'environnement Python
uv sync --locked --all-groups

# 2. Exécution des tests automatisés (unitaires et intégration)
uv run pytest

# 3. Exécution du pipeline complet
# Option A : Version légère (400 000 fiches au total - recommandée pour étudiants et machines limitées)
uv run tp-dla run-all --dataset leger

# Option B : Version complète de référence (4 000 000 de fiches)
uv run tp-dla run-all --dataset complet

# (Ou par étapes individuelles selon l'avancement du TP)
uv run tp-dla init-db                      # Étape 1 & 2 : Schéma sans colonne UID
uv run tp-dla etl --dataset leger          # Étape 3 : Chargement (400k ou 4M) + index de base
uv run tp-dla add-uid-column               # Étape 4 : Ajout manuel de la colonne UID (DDL)
uv run tp-dla union-find                   # Étape 5 : Rapprochement C1-C3 + UIDs + File validation
uv run tp-dla create-indexes               # Étape 6 : Finalisation et vérification des index

# Génération du CSV Autre (version légère 200k ou complète 2M)
uv run python scripts/generer_autre.py --mode leger
uv run python scripts/generer_autre.py --mode complet

# 4. Audit qualité et métriques sur la vérité terrain
uv run python scripts/evaluer_qualite.py

# 5. Lancement de la mini-application web de visualisation (Étape 6)
uv run tp-dla web --host 127.0.0.1 --port 8000
```

---

## Sécurité et Gestion des Secrets

- Ne jamais commiter de mots de passe ou clés réelles dans le dépôt Git.
- Les fichiers `.env` et `.env.*` sont strictement ignorés par Git.
- Seul `.env.example` avec des valeurs d'exemple (`<utilisateur>`, `<mot_de_passe>`) est versionné.
- Les relances sur une cible déjà chargée doivent préserver les fiches et
  les décisions. Réserver les essais d’écriture à une base dédiée vide.
- Utiliser la boucle locale et un compte opérateur distinct pour la validation.
- Toute faille de sécurité ou exposition accidentelle doit être immédiatement signalée et corrigée.
