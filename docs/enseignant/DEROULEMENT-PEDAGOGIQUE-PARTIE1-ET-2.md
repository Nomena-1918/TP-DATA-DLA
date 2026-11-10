# Déroulement Pédagogique — Partie 1 & Partie 2
## Réconciliation de Données & Gouvernance (Licence Informatique)

Ce document fournit à l'enseignant la feuille de route opérationnelle et les recommandations pédagogiques pour l'animation des deux premières séances de TP (Partie 1 et Partie 2).

---

## 🎯 Vue d'ensemble du parcours pédagogique

| Séance | Thématique | Objectif Étudiant | Livrable clé |
| :--- | :--- | :--- | :--- |
| **Partie 1** | Cadrage, Stack technique & Setup | Déployer les 3 sources hétérogènes (PostgreSQL, MySQL, CSV) et valider l'environnement Python | Tests de connexion multi-SGBD validés (400 000 fiches prêtes) |
| **Partie 2** | Diagnostic, Normalisation & Règles | Analyser les disparités de données, concevoir des fonctions pures et formaliser les règles d'attribution UID | Module `normalisation.py` testé unitairement + Notebook 01 exécuté |
| **Partie 3** | Pipeline ETL en Streaming | Ingérer 400 000 fiches en base PostgreSQL unifiée avec curseurs et streaming mémoire | `chargement.py` avec batchs de 5 000 et colonne `donnees_brutes_json` |
| **Partie 4** | Attribution de l'UID & Graphe | Réconcilier les identités via `CompactUnionFind` et passes heuristiques ordonnées | Colonne `uid` attribuée + table d'arbitrage `fiches_arbitrage` |
| **Partie 5** | Interface Web & Audit 360° | Déployer un tableau de bord FastAPI pour auditer les clusters et traiter les cas ambigus | Application Web fonctionnelle avec fiche 360° et métriques |

---

## 🚀 SÉANCE 1 : Cadrage, Environnement & Alimentation des Sources

### 1. Ce que l'enseignant fournit aux étudiants
1. **Dépôt Git du projet** comprenant :
   - L'arborescence standardisée du projet (`src/tp_data_dla/`, `notebooks/`, `tests/`, `sql/leger/`).
   - Le fichier de dépendances `pyproject.toml` (avec `psycopg2-binary`, `PyMySQL`, `pytest`, `pandas`, `rapidfuzz`).
   - Les scripts SQL légers : `sql/leger/charger_auto_postgresql.sql` et `sql/leger/charger_life_mysql.sql`.
   - Le script générateur de la source CSV : `src/tp_data_dla/generateur_autre.py`.
   - Le modèle de configuration `.env.example`.
2. **Accès aux SGBD** :
   - Soit un fichier `docker-compose.yml` préconfiguré (recommandé pour la reproductibilité).
   - Soit des serveurs locaux PostgreSQL 16 (port 5432) et MySQL 8.4 (port 3306) déjà démarrés sur les machines de la salle de TP.
3. **Le support de présentation Partie 1** projeté en début de séance (15 à 20 min max).

### 2. Ce que les étudiants exécutent / génèrent par eux-mêmes
1. **Clonage et initialisation du venv** :
   ```bash
   git clone <url_repo_etudiants>
   cd TP-DATA-DLA
   uv sync  # ou python -m venv .venv && source .venv/bin/activate && pip install -e .
   ```
2. **Chargement des bases Auto et Life** :
   ```bash
   # PostgreSQL 16 : 100 000 fiches
   psql -X -d tp_assurance_auto -f sql/leger/charger_auto_postgresql.sql

   # MySQL 8.4 : 100 000 fiches
   mysql --default-character-set=utf8mb4 --database=tp_assurance_life < sql/leger/charger_life_mysql.sql
   ```
3. **Génération du fichier CSV plat (200 000 lignes)** :
   ```bash
   python -m tp_data_dla.generateur_autre --nb 200000 --output data/autre_clients.csv
   ```
   *(Temps d'exécution : ~2 à 3 secondes grâce à l'algorithme déterministe en streaming).*

### 3. Ce que les étudiants doivent coder par eux-mêmes
- **Fichier de configuration `.env`** : renseigner leurs identifiants de bases locales.
- **Script de validation `scripts/verifier_sources.py`** :
  - Se connecter successivement aux 3 sources.
  - Vérifier par requêtes SQL que `COUNT(*)` donne exactement 100 000 sur Auto, 100 000 sur Life, et 200 000 lignes sur le CSV.
  - Afficher les types de données de la colonne CIN dans les 3 sources pour constater la divergence (`TEXT` vs `BIGINT` vs chaîne brute).

### 4. Conseils pédagogiques & Pièges à anticiper (Partie 1)
- ⚠️ **Le piège de l'installation qui dure tout le TP** : Ne pas laisser les étudiants passer 1h30 à se débattre avec un connecteur MySQL ou une variable d'environnement manquante. Fournir un script `verifier_sources.py` qui teste immédiatement les connexions et affiche des messages d'erreur explicites.
- 💡 **Le choc cognitif initial** : Demander en début de séance : *"Qui peut m'écrire la requête SQL pour faire la jointure entre nos clients Auto et Life ?"*. Laisser un étudiant essayer, puis montrer qu'un serveur PostgreSQL ne peut pas interroger MySQL nativement, et que même s'ils étaient sur la même base, `TEXT = BIGINT` plante avec `operator does not exist`.
- 📊 **Le choix du volume léger (400 000 fiches)** : Expliquer aux étudiants pourquoi on travaille sur 400 000 fiches et non 40 millions : cela permet une rétroaction immédiate en TP sans latence tout en imposant des règles d'ingestion propres (interdiction des algorithmes $O(N^2)$).

---

## 🔍 SÉANCE 2 : Exploration, Normalisation Canonique & Règles Métier

### 1. Ce que l'enseignant fournit aux étudiants
1. **Le support de présentation Partie 2** (16 diapositives projetées).
2. **Le notebook d'exploration** : `notebooks/01_exploration.ipynb` pré-rempli avec les requêtes de lecture et des zones à compléter (exercices de détection d'anomalies).
3. **Le squelette de code** : `src/tp_data_dla/normalisation.py` avec les signatures de fonctions, les regex précompilées, le typage strict (`Optional[str]`), et les docstrings détaillées.
4. **Le jeu de tests unitaires** : `tests/test_normalisation.py` couvrant les cas nominaux et les cas limites.

### 2. Ce que les étudiants explorent par eux-mêmes (Notebook 01)
1. **Échantillonnage et observation des données brutes** :
   - Constater les espaces parasites (`' Ramanitra '`).
   - Constater les variations de casse (`'RAMANITRA'` vs `'Rakoto'`).
   - Constater l'inversion des prénoms (`'Faly Tahina'` vs `'Tahina Faly'`).
   - Constater les formats de date incompatibles (`'1970-04-19'`, `19700419`, `'19-04-1970'`).
2. **Identification des cas pièges** :
   - Trouver une paire de fiches avec le même nom et la même date de naissance mais **deux numéros de CIN distincts** (homonymes parfaits).
   - Trouver deux fiches partageant le même numéro de téléphone mais ayant des états civils complètement distincts (foyer familial : conjoints).

### 3. Ce que les étudiants doivent coder par eux-mêmes
Les étudiants complètent le module `src/tp_data_dla/normalisation.py` pour implémenter 7 fonctions pures :
1. `normaliser_nom(valeur: Any) -> Optional[str]` :
   - Suppression des espaces superflus (strip et espaces internes multiples).
   - Suppression des accents (`unicodedata.normalize('NFKD', ...)`).
   - Passage systématique en majuscules.
2. `normaliser_cin(valeur: Any) -> Optional[str]` :
   - Suppression de tout caractère non numérique.
   - Validation de la longueur stricte : exactement 12 chiffres (sinon `None`).
3. `normaliser_date(valeur: Any) -> Optional[str]` :
   - Détection robuste du format d'entrée (entier `YYYYMMDD`, date SQL `YYYY-MM-DD`, ou chaîne française `DD-MM-YYYY`).
   - Formatage de sortie standardisé ISO 8601 : `YYYY-MM-DD`.
4. `normaliser_prenoms(valeur: Any) -> Tuple[Optional[str], Optional[str]]` :
   - Découpage par expressions régulières (espaces, tirets, séparateurs).
   - Production de `prenoms_norm` (ordre d'origine conservé).
   - Production de `prenoms_trie_norm` (tokens triés par ordre alphabétique pour permettre l'égalité stricte).
5. `normaliser_tel(valeur: Any) -> Optional[str]` : extraction des chiffres nationaux (9 chiffres significatifs).
6. `normaliser_mail(valeur: Any) -> Optional[str]` : strip et mise en minuscules.
7. `normaliser_sexe(valeur: Any) -> Optional[str]` : mapping canonique vers `'M'` ou `'F'`.

**Validation exigée** :
```bash
pytest tests/test_normalisation.py -v
```
Tous les tests doivent être au vert avant la fin de la séance.

### 4. Conseils pédagogiques & Moments clés (Partie 2)
- 🧠 **Débat en classe sur le Record Linkage** :
  - Expliquer la différence entre l'approche **statistique / probabiliste** (modèle de Fellegi-Sunter / ML) et l'approche **déterministe par règles hiérarchiques**.
  - Poser la question : *"Pourquoi une banque ou une compagnie d'assurance refuse-t-elle souvent une boîte noire probabiliste pour attribuer un identifiant unique ?"*
  - Réponse attendue : L'explicabilité juridique, l'auditabilité réglementaire et l'impossibilité de justifier un score de 0.82 lors d'une contestation de sinistre.
- 🛡️ **L'exercice du verrou anti-conflit de CIN** :
  - Montrer le diagramme Mermaid (Slide 12).
  - Poser la question piège : *"Deux fiches ont exactement le même nom, prénom et date de naissance. Mais fiche A a le CIN X et fiche B a le CIN Y. Doit-on les fusionner ?"*
  - Faire comprendre que le CIN prime : deux numéros nationaux différents garantissent qu'il s'agit d'homonymes et non de la même personne.
- 👥 **Le piège du foyer familial** :
  - Pourquoi ne jamais fusionner deux fiches sous prétexte qu'elles ont le même téléphone ou la même adresse email ?
  - Parce que les conjoints ou parents/enfants partagent souvent la même ligne. Ces fiches doivent être aiguillées vers la file de validation humaine (`SUSPICION_FOYER`).
- 🔄 **L'astuce de la tokenisation des prénoms** :
  - Faire illustrer au tableau : `'Faly Tahina'` et `'Tahina Faly'`.
  - Expliquer que le tri des tokens `['FALY', 'TAHINA']` résout instantanément ce gisement massif de faux négatifs sans faire de jointure floue coûteuse.

---

## 📋 Récapitulatif des livrables étudiants attendus à l'issue des Parties 1 & 2

| Étape | Livrable attendu | Modalité d'évaluation |
| :--- | :--- | :--- |
| **Fin Séance 1** | Environnement opérationnel, 3 sources alimentées et script de test validé | Exécution sans erreur de `scripts/verifier_sources.py` |
| **Fin Séance 2** | Module de normalisation propre et testé | Exécution avec succès de `pytest tests/test_normalisation.py` (100 % de réussite) |
| **Fin Séance 2** | Réponses aux questions d'exploration du Notebook 01 | Identification des 4 familles d'anomalies et justification des règles C1 à C4 |
