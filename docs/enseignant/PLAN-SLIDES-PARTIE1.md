# Blueprint des slides — Partie 1 : Cadrage, Préparation locale & Connexion aux datasources

Ce document définit le plan détaillé de la **Présentation 1** sur les 5 présentations prévues pour le TP Data D.L.A. Elle accompagne les étudiants en séance sur un **poste 100 % autonome en local** pour préparer les données, appréhender le modèle de population et les caractéristiques des trois sources, configurer l'environnement Python et établir des connexions sécurisées en lecture seule.

> **Règles de rédaction du support**
> - **Anonymisation stricte** : scénario présenté uniquement comme une compagnie d'assurance fictive à Madagascar ; aucune mention d'entreprise réelle ni de cabinet de conseil ; identifiant pivot nommé exclusivement `UID`.
> - **Dimensionnement local unique** : seuls les chiffres du jeu de travail léger (400 000 fiches au total, 100k Auto, 100k Life, 200k Autre, 70k cohorte commune, 256k population théorique) sont présentés.
> - **Accessibilité pédagogique** : le fonctionnement technique est vulgarisé et rendu accessible à tous, sans jargon abstrait ni formules mathématiques complexes.
> - **Rapprochement flou** : désigné rigoureusement comme *Rapprochement flou (Damerau-Levenshtein adaptatif)*.

---

## Vue d'ensemble des 5 présentations du TP

| Présentation | Titre | Statut | Périmètre principal |
| :--- | :--- | :--- | :--- |
| **Partie 1** | **Cadrage, Préparation locale & Connexion aux datasources** | **Document courant** (18 slides) | Contexte métier, prérequis machine, feuille de route, règle d'or non destructive, cartographie, génération & colonnes détaillées des 3 sources, setup local (`uv`, `.env`), connexions en lecture seule. |
| **Partie 2** | **Exploration, Nettoyage & Règles de rapprochement** | Blueprint validé (12 slides) | Diagnostic notebook, hétérogénéité des formats, fonctions pures de normalisation, tokenisation des prénoms, matrice hybride `C1`–`C4`, verrou anti-conflit CIN, fuzzy matching adaptatif et gestion des foyers. |
| **Partie 3** | **Modélisation cible & Pipeline ETL en flux** | À rédiger ultérieurement | Schéma cible `tp_assurance_etl` (sans `uid` au départ), conservation du brut + colonnes canoniques + `details_metier` JSONB, extraction streaming + `COPY`, indexation de base. |
| **Partie 4** | **Ajout DDL `UID` & Moteur Union-Find** | À rédiger ultérieurement | Ajout de la colonne `uid`, structure `CompactUnionFind`, passes exactes `C1`–`C3`, passe floue par blocage `(date_naiss_norm, sexe_norm)`, routage vers la file humaine. |
| **Partie 5** | **Mini-application Web, Arbitrage humain & Audit** | À rédiger ultérieurement | Interface FastAPI (tableau de bord, recherche, fiche groupe `UID`, file de validation dont `SUSPICION_FAUTE_CIN`), tests `pytest` et métriques de réconciliation. |

---

## Détail des diapositives — Présentation 1 (18 slides)

---

### Slide 1 — Page de titre : Réconciliation d'Identités Clients & Référentiel Unique (`UID`)

- **Titre** : Réconciliation d'Identités Clients & Référentiel Unique (`UID`)
- **Sous-titre** : Partie 1 / 5 — Cadrage métier, préparation de l'environnement local et connexion aux datasources
- **Objectif pédagogique** : Situer l'intitulé du TP, son cadre technologique et le rôle de cette première séance d'amorçage.
- **Contenu structuré** :
  - Cadre : TP Data D.L.A (niveau Licence) — scénario fictif d'une compagnie d'assurance à Madagascar.
  - Objectif : relier les fiches clients dispersées entre plusieurs applications métier grâce à un identifiant pivot commun (`UID`), sans détruire ni altérer les données d'origine.
  - Pile technique : `PostgreSQL 16`, `MySQL 8.4`, fichier `CSV` (`UTF-8`), `Python >= 3.12`, gestionnaire `uv`.
- **Notes orateur** : Rappeler dès l'ouverture que le TP complet se décompose en 5 parties progressives et que cette première séance vise à rendre chaque poste autonome et prêt à explorer les données.

---

### Slide 2 — Contexte métier : 1 client unique = 3 silos déconnectés

- **Titre** : Le constat : 1 client unique = 3 silos déconnectés
- **Sous-titre** : Pourquoi un référentiel client unique ?
- **Objectif pédagogique** : Comprendre le problème métier (doublons inter- et intra-sources, disparité des progiciels, erreurs de saisie).
- **Contenu structuré** :
  - **Exemple concret** : Jean RAKOTO, né le 12/04/1985, souscrit 3 contrats dans 3 agences distinctes.
  - **Auto (PostgreSQL)** : `id: 1004521`, RAKOTO Jean, né le 1985-04-12, Tél: 0340123456.
  - **Life (MySQL)** : `ref: 3001890`, RAKOTO Jean-Paul, né le 12/04/1985, Tél: +261340123456.
  - **Autre (CSV)** : `ref: EXT-5002145`, RAKOTOO Jean, Date: 12-Apr-85 (anomalie de saisie sur le nom).
  - **Résultat** : 3 fiches sans lien, aucune vue 360°, risques de surcoûts et de fraudes.
- **Notes orateur** : Montrer que le client réel est unique, mais que le système d'information le voit comme 3 personnes distinctes.

---

### Slide 3 — Prérequis techniques & Environnement de travail

- **Bandeau haut** : `CADRAGE DU TP · PRÉREQUIS TECHNIQUES`
- **Titre** : Prérequis indispensables : la pile technique locale
- **Sous-titre** : Tout ce qui doit être installé et opérationnel sur votre machine dès le démarrage.
- **Contenu structuré (4 blocs)** :
  1. **Python >= 3.12** : syntaxe moderne, typage strict et performances. Vérification : `python3 --version`.
  2. **Gestionnaire `uv` (Astral)** : gestionnaire d'environnements ultra-rapide en Rust, verrou déterministe via `uv.lock`. Vérification : `uv --version`.
  3. **Moteurs SGBD Relationnels** : PostgreSQL 16 (port 5432, base Auto) et MySQL 8.4 (port 3306, base Life, encodage `utf8mb4`).
  4. **Données, Terminal & Outils** : Fichier plat `clients_autre.csv` (UTF-8, `;`), terminal Bash/Zsh, client Git, navigateur Web pour JupyterLab.
  - **Bannière test** : `uv run python -c "import psycopg, mysql.connector; print('Pilotes OK')"`
- **Notes orateur** : Faire exécuter la ligne de test des pilotes immédiatement aux étudiants pour s'assurer qu'aucun blocage d'environnement ne subsiste.

---

### Slide 4 — Feuille de route : le parcours en 5 étapes

- **Titre** : Feuille de route : le parcours en 5 étapes
- **Sous-titre** : Progression pédagogique : chaque étape produit un livrable direct pour la séance suivante
- **Contenu structuré (5 jalons)** :
  1. **Partie 1 (Aujourd'hui)** : Cadrage, préparation locale, 400 000 fiches, `uv`, `.env`, connexions en lecture seule.
  2. **Partie 2** : Notebook 01, profilage, normalisation, matrice `C1`–`C4`, rapprochement flou (tolérance aux fautes), verrou anti-conflit CIN.
  3. **Partie 3** : Schéma cible PostgreSQL `tp_assurance_etl`, conservation brut, `details_metier JSONB`, ingestion streaming `COPY`.
  4. **Partie 4** : Colonne pivot `UID`, moteur `CompactUnionFind`, détection conflits et file d'arbitrage humain.
  5. **Partie 5** : Application Web FastAPI, tableau de bord, vue 360°, validation humaine et audit qualité.
- **Notes orateur** : Bien situer que la Partie 1 pose les fondations matérielles et logiques de tout le TP.

---

### Slide 5 — Règle d'or : zéro suppression, zéro altération

- **Titre** : Règle d'or : zéro suppression, zéro altération
- **Sous-titre** : Relier les fiches par un UID sans jamais modifier l'historique
- **Contenu structuré (Tableau comparatif)** :
  - **Approche destructive (à proscrire)** : écrasement par `DELETE`, perte des références applicatives d'origine, altérations irréversibles, perte d'auditabilité.
  - **Approche retenue (conservative)** : 100 % des fiches sources conservées intactes à l'octet près, ajout d'une colonne dédiée `UID`, vue 360° par regroupement SQL, réversibilité totale.
- **Citation clé** : « Dédoublonner ne signifie pas supprimer des enregistrements, mais identifier leurs équivalences. »
- **Notes orateur** : Répéter qu'aucun `DELETE` ne sera toléré dans les requêtes des étudiants.

---

### Slide 6 — Cartographie technique des 3 datasources

- **Titre** : Les trois sources de données du TP
- **Sous-titre** : Cartographie technique et dimensionnement du TP local (400 000 fiches)
- **Contenu structuré** :
  - **Auto (PostgreSQL 16)** : base `tp_assurance_auto`, table `tp_assurance.clients_auto`, clé `id_client_auto` (1 000 001+), volume 100 000.
  - **Life (MySQL 8.4)** : base `tp_assurance_life`, table `tp_assurance_life.clients_life`, clé `ref_adherent` (3 000 001+), volume 100 000, encodage `utf8mb4`.
  - **Autre (Fichier CSV)** : fichier `data/clients_autre.csv` (délimiteur `;`), clé `ref_fiche` (`EXT-5000001`+), volume 200 000.
  - **Total TP local** : 400 000 fiches simulant 256 000 personnes réelles.
- **Notes orateur** : Rappeler qu'un client peut détenir plusieurs contrats dans différentes branches ou au sein d'une même base.

---

### Slide 7 — Génération (1/7) · Le modèle de population vulgarisé

- **Bandeau haut** : `GÉNÉRATION DES DONNÉES (1/7) · ARCHITECTURE`
- **Titre** : Génération : modèle de population
- **Sous-titre** : Un jeu de données réaliste simulant 256 000 personnes physiques réparties dans 3 bases.
- **Zone supérieure (3 cohortes)** :
  - **Cohorte commune (70 000 personnes)** : présentes à la fois dans Auto, Life et Autre. Cœur de la réconciliation.
  - **Cohortes exclusives (186 000 personnes)** : 29k Auto, 29k Life, 128k Autre (clients mono-contrat).
  - **Doublons internes (4 000 fiches)** : 1 % de clients fidèles qui reprennent un second contrat dans la même base (+1k Auto, +1k Life, +2k Autre).
- **Zone inférieure (3 principes vulgarisés)** :
  - **Reproductibilité garantie** : chaque étudiant obtient exactement les mêmes données grâce à des règles de calcul fixes (aucun aléa incontrôlé).
  - **Ordre brassé réaliste** : les fiches sont mélangées dans chaque source pour simuler des souscriptions étalées dans le temps.
  - **Évaluation automatisée** : une signature théorique invisible permet de mesurer automatiquement votre score (tous les vrais doublons identifiés, zéro faux positif).
- **Notes orateur** : Rassurer les étudiants : il n'y a pas de magie noire ni de hasard imprévisible ; les données sont calibrées pour reproduire exactement les cas d'école du métier.

---

### Slide 8 — Génération (2/7) · Source Auto : Synthèse directe en SQL

- **Bandeau haut** : `GÉNÉRATION DES DONNÉES (2/7) · SOURCE AUTO`
- **Titre** : Auto (PostgreSQL 16) : Synthèse directe en SQL
- **Sous-titre** : 100 000 fiches synthétisées en mémoire vive par PostgreSQL en moins de 3 secondes.
- **Colonne gauche (5 étapes simples)** :
  1. *Compteur instantané* : `generate_series()` génère 100 000 numéros en mémoire vive.
  2. *Brassage de l'ordre* : les numéros sont réordonnés pour disperser les clients dans le temps.
  3. *Clients fidèles (1 %)* : 1 000 clients reviennent pour souscrire une seconde assurance (doublons).
  4. *Pioche des identités* : noms, prénoms et villes sont piochés dans des listes réalistes malgaches.
  5. *Insertion directe* : toutes les lignes sont insérées d'un coup dans la table `clients_auto`.
- **Colonne droite (Boîte Terminal sombre `#1E293B`)** :
  Extrait SQL CTE `WITH numeros AS (...) INSERT INTO clients_auto SELECT ...`.
- **Notes orateur** : Montrer la puissance du SQL déclaratif : 100 000 lignes générées et insérées en moins de 3 secondes sans passer par un fichier intermédiaire.

---

### Slide 9 — Génération (3/7) · Source Auto : Colonnes d'identité et métier

- **Bandeau haut** : `GÉNÉRATION DES DONNÉES (3/7) · STRUCTURE AUTO`
- **Titre** : Auto (PostgreSQL 16) : Colonnes d'identité et métier
- **Sous-titre** : Schéma `tp_assurance.clients_auto` (100 000 lignes) : 10 champs d'état civil et 3 champs métier.
- **Bloc gauche (Identité de base · 10 colonnes communes)** :
  `id_client_auto` (BIGINT PK), `numero_cin` (TEXT préfixé `'CIN- '`), `nom_assure` (TEXT majuscules), `prenoms_assure` (TEXT), `ne_le` (DATE natif), `ne_a` (TEXT), `ville_residence` (TEXT), `mobile` (TEXT), `courriel` (TEXT), `sexe` (TEXT `'Masculin'` / `'Féminin'`).
- **Bloc droite (Métier Auto & Points d'attention)** :
  `immatriculation` (TEXT plaque unique), `annee_vehicule` (INTEGER 1998–2025), `formule_auto` (TEXT Tiers/Tous risques).
  *Vigilance ETL* : date SQL propre, mais préfixe `'CIN- '` à retirer, espaces de téléphone et sexe textuel à canoniser.
- **Notes orateur** : Souligner que les colonnes métier ne participent pas à la réconciliation de la personne physique, mais devront être conservées dans l'ETL (Partie 3).

---

### Slide 10 — Génération (4/7) · Source Life : Synthèse SQL sans boucle

- **Bandeau haut** : `GÉNÉRATION DES DONNÉES (4/7) · SOURCE LIFE`
- **Titre** : Life (MySQL 8.4) : Synthèse SQL sans boucle
- **Sous-titre** : 100 000 fiches créées en une seule instruction `CREATE TABLE ... AS SELECT`.
- **Colonne gauche (4 étapes simples)** :
  1. *Multiplication de chiffres* : séries de 10 chiffres pour créer 100 000 lignes sans boucle lente.
  2. *Brassage déterministe* : fiches réordonnées pour disperser les clients dans le temps.
  3. *Attribution par listes* : fonction SQL `ELT()` sélectionnant les patronymes et prénoms.
  4. *Création & chargement direct* : table InnoDB `clients_life` créée et remplie instantanément.
- **Colonne droite (Boîte Terminal sombre `#1E293B`)** :
  Extrait MySQL CTE récursive `WITH RECURSIVE chiffres AS (...) CREATE TABLE ... AS SELECT`.
- **Notes orateur** : Expliquer comment MySQL 8.4 gère les CTEs récursives pour éviter les scripts procéduraux lents.

---

### Slide 11 — Génération (5/7) · Source Life : Colonnes d'identité et métier

- **Bandeau haut** : `GÉNÉRATION DES DONNÉES (5/7) · STRUCTURE LIFE`
- **Titre** : Life (MySQL 8.4) : Colonnes d'identité et métier
- **Sous-titre** : Schéma `tp_assurance_life.clients_life` (100 000 lignes) : 10 champs d'état civil et 3 champs épargne.
- **Bloc gauche (Identité de base & Spécificités de type)** :
  `ref_adherent` (BIGINT PK), `cin_numerique` (BIGINT pur sans préfixe), `nom_adherent` (VARCHAR), `prenoms_adherent` (VARCHAR tirets), `date_naiss` (**ATTENTION : INT `YYYYMMDD`**), `lieu_naiss` (VARCHAR), `commune_domicile` (VARCHAR), `tel_contact` (VARCHAR avec indicatif `+000`), `email_contact` (VARCHAR), `genre` (**TINYINT binaire : 1=H / 0=F**).
- **Bloc droite (Métier Épargne & Vigilance)** :
  `produit` (Retraite / Épargne vie), `cotisation_mensuelle_ar` (INT en Ariary), `date_adhesion` (DATE).
  *Vigilance ETL* : parsing obligatoire de l'entier `date_naiss` en date ISO, et conversion du `genre` binaire en `'M'/'F'`.
- **Notes orateur** : Attirer l'attention des étudiants sur les pièges classiques de Life : une date stockée sous forme d'entier numérique et un genre binaire.

---

### Slide 12 — Génération (6/7) · Source Autre : Générateur Python streaming

- **Bandeau haut** : `GÉNÉRATION DES DONNÉES (6/7) · SOURCE AUTRE`
- **Titre** : Autre (CSV) : Générateur Python en streaming
- **Sous-titre** : 200 000 fiches produites au fil de l'eau sans saturer la mémoire vive de la machine.
- **Colonne gauche (3 principes de streaming)** :
  1. *Génération au fil de l'eau (`yield`)* : aucune accumulation en RAM, chaque fiche est écrite au fur et à mesure.
  2. *Écriture sécurisée & atomique* : écriture temporaire masquée puis renommage atomique en `clients_autre.csv` (zéro corruption).
  3. *Zéro bibliothèque tierce* : modules standard `csv` et `hashlib`.
- **Colonne droite (Boîte Terminal sombre `#1E293B`)** :
  Extrait Python `generer_flux_clients(nb_lignes=200_000)` avec `yield` et `csv.DictWriter`.
- **Notes orateur** : Expliquer le concept de générateur (`yield`) en Python et pourquoi il est crucial en Data Engineering pour traiter de volumineux jeux de données.

---

### Slide 13 — Génération (7/7) · Source Autre : Structure & Univers bivalent

- **Bandeau haut** : `GÉNÉRATION DES DONNÉES (7/7) · STRUCTURE AUTRE`
- **Titre** : Autre (CSV) : Colonnes d'identité et univers bivalent
- **Sous-titre** : Fichier `data/clients_autre.csv` (délimiteur ;) : 10 champs d'identité et 2 branches métier (50/50).
- **Bloc gauche (Identité de base · Format texte CSV)** :
  `ref_fiche` (str PK `EXT-5000001`+), `piece_identite` (str 12 car.), `patronyme` (str casse mixte), `autres_noms` (str prénoms inversés), `date_naissance` (**format français `DD-MM-YYYY`**), `commune_origine` (str), `localite` (str), `contact_tel` (str tirets), `contact_mail` (str), `code_sexe` (str `'M'`/`'F'`).
- **Bloc droite (Bivalence Métier 50 % Agricole / 50 % Maritime)** :
  - *50 % Agricole (100k)* : `culture`, `superficie_ha` (décimale à virgule), `garantie_agricole`. *Champs maritimes vides.*
  - *50 % Maritime (100k)* : `type_navire`, `port_attache`, `garantie_maritime`. *Champs agricoles vides.*
  - *Vigilance ETL* : structure clairsemée et date au format français.
- **Notes orateur** : Faire remarquer aux étudiants que la bivalence métier induit des colonnes optionnelles selon l'activité de l'assuré.

---

### Slide 14 — Réalisme du TP : 4 familles d'anomalies de saisie

- **Bandeau haut** : `RÉALISME DU TP · ANOMALIES DE SAISIE`
- **Titre** : Le réalisme : 4 familles d'anomalies de saisie
- **Sous-titre** : Environ 5 % d'erreurs réalistes simulant les erreurs humaines constatées sur le terrain.
- **Contenu structuré (4 familles)** :
  1. *Fautes d'orthographe & Saisie (~5 %)* : altérations de lettres (`'RAKTO'`, `'RAAKOTO'`, `'REKOTO'`), inversions de prénoms (`'Jean Hery'` vs `'Hery Jean'`), espaces et casse résiduelle.
  2. *Erreurs de frappe numériques (~5 %)* : chiffre altéré ou manquant sur CIN/téléphone. **Alerte : deux personnes distinctes peuvent avoir un CIN qui ne diffère que d'un chiffre ; ne jamais modifier un CIN à l'aveugle.**
  3. *Hétérogénéité des formats* : 3 formats de dates (`YYYY-MM-DD`, `YYYYMMDD`, `DD-MM-YYYY`), téléphones disparates et valeurs `NULL`.
  4. *Faux amis (Homonymes & Foyers)* : homonymes parfaits (même nom/prénom mais dates/lieux distincts) et foyers partagés (famille partageant téléphone fixe).
- **Notes orateur** : Insister sur le fait que ces 5 % d'anomalies justifient toute la complexité algorithmique étudiée en Partie 2 et Partie 4.

---

### Slide 15 — Setup local (1/2) : Initialisation des 3 sources

- **Titre** : Préparer les 3 sources en local (jeu léger 400k)
- **Sous-titre** : Scripts SQL dédiés et génération locale du fichier CSV
- **Contenu structuré** :
  - Commandes d'exécution : `psql -X -d tp_assurance_auto -f sql/leger/charger_auto_postgresql.sql`
  - Commande MySQL : `mysql --batch --skip-force --default-character-set=utf8mb4 --database=tp_assurance_life < sql/leger/charger_life_mysql.sql`
  - Commande Python CSV : `uv run python scripts/generer_autre.py --mode leger --sortie data/clients_autre.csv`
  - Contrôles de comptage : 100 000 Auto, 100 000 Life, 200 001 lignes CSV (avec header).
- **Notes orateur** : Rappeler que l'argument `--sortie data/clients_autre.csv` est indispensable pour placer le fichier au chemin attendu par le notebook.

---

### Slide 16 — Setup local (2/2) : Python, uv & Sécurité

- **Titre** : Configurer Python (uv) et sécuriser les accès (.env)
- **Sous-titre** : Dépendances verrouillées et gestion sécurisée des identifiants
- **Contenu structuré** :
  - Synchronisation des dépendances : `uv sync --locked --all-groups` (pilotes `psycopg`, `mysql-connector`, matching flou `rapidfuzz` Damerau-Levenshtein adaptatif, `python-dotenv`, `jupyterlab`, `fastapi`).
  - Fichier local `.env` : copie depuis `.env.example`, variables `TP_AUTO_*`, `TP_LIFE_*`.
  - Règle d'or de sécurité : aucun mot de passe commité dans Git, `.env` et `.venv/` dans `.gitignore`.
- **Notes orateur** : Montrer que le fichier `.env` est automatiquement lu par `config.py` et que les mots de passe ne sont jamais inscrits en dur dans le code.

---

### Slide 17 — Connexions sécurisées : patrons de lecture seule

- **Titre** : Établir des connexions sûres aux 3 sources
- **Sous-titre** : Patrons de code en lecture seule pour protéger les données
- **Contenu structuré** :
  - Auto PostgreSQL : `conn.read_only = True` et timeout à 5s.
  - Life MySQL : `conn.start_transaction(readonly=True)` et encodage `charset='utf8mb4'`.
  - Autre CSV : `csv.DictReader` en streaming ligne par ligne avec conservation en `str`.
  - Commande de lancement : `set -a && source .env && set +a && uv run --locked --group notebook jupyter lab --ip=127.0.0.1`
- **Notes orateur** : Insister sur l'intérêt du mode `read_only` : un étudiant ne peut pas détruire ou altérer accidentellement sa base source.

---

### Slide 18 — Bilan de la Partie 1 & Cap sur la Partie 2

- **Titre** : Poste prêt ! Bilan de la Partie 1
- **Sous-titre** : Checklist de fin de séance et perspectives pour la séance 2
- **Contenu structuré** :
  - *Checklist validée* : 100k Auto chargés, 100k Life chargés, 200k CSV générés, environnement `uv` synchronisé, connexions R/O validées.
  - *Ce qui nous attend en Partie 2* : ouverture de `01_exploration.ipynb`, inventaire des anomalies, matrice de rapprochement `C1`–`C4`, tolérance aux fautes par Damerau-Levenshtein, et verrou absolu anti-conflit de CIN.
- **Notes orateur** : Féliciter les étudiants pour la mise en place de leur environnement et donner rendez-vous pour la phase d'exploration active.
