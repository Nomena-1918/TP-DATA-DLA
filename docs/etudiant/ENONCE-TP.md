# TP de rapprochement de fiches clients — Découverte des sources

## 1. Contexte métier et objectif

Ce scénario fictif s’inspire du fonctionnement des compagnies d’assurance à Madagascar.
Une même personne physique peut souscrire plusieurs contrats auprès de différentes entités ou branches du groupe :
- Une police d'assurance automobile (agence Auto).
- Un contrat d’assurance vie ou de retraite (agence Life).
- Un dossier d’assurance agricole ou maritime sur une plateforme dédiée (plateforme Autre).

Chaque progiciel fonctionne en silo et attribue à ses dossiers sa propre référence locale. Selon l’application, les informations d'état civil et de contact peuvent être présentées sous des formats disparates, être incomplètes ou comporter des erreurs de saisie.

L'objectif de ce projet est de concevoir un pipeline de réconciliation d'identités capable de relier automatiquement les fiches appartenant à une même personne et de leur affecter un identifiant pivot unique (`UID`), sans jamais détruire ni altérer les données historiques.

> [!IMPORTANT]
> **Règle d'or : Zéro suppression, zéro altération**
> Aucun enregistrement d'origine ne doit être supprimé (`DELETE` proscrit) ni modifié (`UPDATE` sur les colonnes d'origine proscrit). Toutes les fiches sources restent intactes et consultables avec leur référence locale et leurs valeurs brutes. Le rapprochement consiste uniquement à affecter une valeur d'identifiant pivot (`UID`) commune aux fiches d'un même individu.

---

## 2. Prérequis techniques & Environnement de travail

Pour réaliser ce TP dans des conditions optimales, assurez-vous que les outils suivants sont installés et fonctionnels sur votre poste de travail :

1. **Python >= 3.12** : syntaxe moderne, typage strict et performances.
   - Commande de vérification : `python3 --version`
2. **Gestionnaire `uv` (Astral)** : gestionnaire d'environnements ultra-rapide en Rust garantissant la reproductibilité exacte des dépendances via `uv.lock`.
   - Commande de vérification : `uv --version`
3. **PostgreSQL 16** (port `5432`) : héberge la base relationnelle `tp_assurance_auto` (encodage `UTF-8`).
4. **MySQL 8.4** (port `3306`) : héberge la base relationnelle `tp_assurance_life` (encodage `utf8mb4`).
5. **Stockage plat & Outils système** :
   - Fichier plat `data/clients_autre.csv` (délimiteur `;`, encodage `UTF-8`).
   - Terminal (`bash` ou `zsh`), client `git`, éditeur de code et navigateur pour JupyterLab.

Vérifiez le fonctionnement des pilotes de bases de données depuis la racine du TP avec :
```sh
uv run python -c "import psycopg, mysql.connector; print('Pilotes PostgreSQL et MySQL opérationnels !')"
```

---

## 3. Les sources de données (Version légère : 400 000 fiches)

Afin de garantir des temps d'exécution courts (quelques secondes) et d'éviter toute saturation de la mémoire vive ou du processeur sur les ordinateurs des étudiants, le TP utilise exclusivement le **jeu de données léger de 400 000 fiches**.

| Source | Activité | Support technique local | Nombre de fiches | Plage des identifiants locaux |
| :--- | :--- | :--- | ---: | :--- |
| **Auto** | Assurance automobile | PostgreSQL 16 (`tp_assurance.clients_auto`) | 100 000 | `id_client_auto` (1 000 001 à 1 100 000) |
| **Life** | Assurance vie et retraite | MySQL 8.4 (`tp_assurance_life.clients_life`) | 100 000 | `ref_adherent` (3 000 001 à 3 100 000) |
| **Autre** | Plateformes agricole et maritime | Fichier plat `data/clients_autre.csv` (UTF-8, `;`) | 200 000 | `ref_fiche` (`EXT-5000001` à `EXT-5200000`) |
| **Total** | Multi-sources | Environnement local autonome | **400 000** | Références propres par système |

### Modèle de population simulé
Le générateur déterministe simule une population globale de **256 000 personnes physiques distinctes** :
- **Cohorte commune (70 000 personnes)** : clients présents simultanément dans les trois systèmes (cœur du rapprochement multi-sources).
- **Cohortes exclusives (186 000 personnes)** : clients n'ayant souscrit que dans une seule branche (29 000 Auto, 29 000 Life, 128 000 Autre).
- **Fidélité / Doublons internes (4 000 fiches)** : 1 % des fiches de chaque base correspondent à un second contrat souscrit par une même personne au sein de la même application (+1 000 Auto, +1 000 Life, +2 000 Autre).

---

## 4. Structure des colonnes et hétérogénéité des formats

### Informations d'état civil et de contact communes (10 attributs)

| Attribut conceptuel | Auto (PostgreSQL 16) | Life (MySQL 8.4) | Autre (CSV UTF-8 `;`) | Pièges & Écarts constatés |
| :--- | :--- | :--- | :--- | :--- |
| **Identifiant local** | `id_client_auto` (BIGINT) | `ref_adherent` (BIGINT) | `ref_fiche` (TEXT) | Espaces de clés disjoints par système. |
| **Pièce d'identité (CIN)** | `numero_cin` (TEXT) | `cin_numerique` (BIGINT) | `piece_identite` (TEXT) | Préfixe textuel `'CIN- '` sur Auto, entier pur sur Life, chaîne de 12 chiffres sur Autre. |
| **Nom de famille** | `nom_assure` (TEXT) | `nom_adherent` (TEXT) | `patronyme` (TEXT) | Espaces superflus (`' Ramanitra '`), minuscules/majuscules, diacritiques (`é` vs `e`). |
| **Prénoms** | `prenoms_assure` (TEXT) | `prenoms_adherent` (TEXT) | `autres_noms` (TEXT) | Inversions d'ordre (`'Tahina Faly'` vs `'Faly Tahina'`), présence de tirets (`'FALY-TAHINA'`). |
| **Date de naissance** | `ne_le` (DATE SQL) | `date_naiss` (INT) | `date_naissance` (TEXT) | Format ISO `YYYY-MM-DD` sur Auto, entier numérique `AAAAMMJJ` sur Life, texte `JJ-MM-AAAA` sur Autre. |
| **Lieu de naissance** | `ne_a` (TEXT) | `lieu_naiss` (TEXT) | `commune_origine` (TEXT) | 3 à 5 % de valeurs manquantes (NULL ou chaînes vides), variations d'accents. |
| **Ville de résidence** | `ville_residence` (TEXT) | `commune_domicile` (TEXT) | `localite` (TEXT) | Déménagements possibles entre deux souscriptions (la ville peut changer pour une même personne). |
| **Numéro de téléphone** | `mobile` (TEXT) | `tel_contact` (TEXT) | `contact_tel` (TEXT) | Groupes séparés par des espaces sur Auto, préfixe international fictif `+000` sur Life, tirets sur Autre. |
| **Courriel** | `courriel` (TEXT) | `email_contact` (TEXT) | `contact_mail` (TEXT) | Variations de casse (`Jean.Rakoto@...` vs `jean.rakoto@...`). |
| **Sexe / Genre** | `sexe` (TEXT) | `genre` (TINYINT) | `code_sexe` (TEXT) | `'Masculin'`/`'Féminin'` sur Auto, binaire `1`/`0` sur Life, `'M'`/`'F'` sur Autre. |

### Informations métier propres à chaque univers

| Source | Colonnes métier spécifiques | Description & Cas d'usage |
| :--- | :--- | :--- |
| **Auto** | `immatriculation`<br>`annee_vehicule`<br>`formule_auto` | Immatriculation véhicule fictive (clé unique locale).<br>Année de mise en circulation (1998 à 2025).<br>Formule souscrite (`Tiers`, `Tiers étendu`, `Tous risques`). |
| **Life** | `produit`<br>`cotisation_mensuelle_ar`<br>`date_adhesion` | Type de contrat (`Retraite individuelle`, `Épargne vie`, `Décès`).<br>Montant mensuel en Ariary malgache (MGA).<br>Date de signature du contrat d'adhésion. |
| **Autre**<br>*(Agricole : 100k)* | `plateforme = 'AGRICOLE'`<br>`culture`<br>`superficie_ha`<br>`garantie_agricole` | Type de culture (Riz, Maïs, Manioc, Vanille, Girofle).<br>Superficie en hectares (notation décimale avec virgule).<br>Garantie climatique (Inondation, Cyclone, Sécheresse, Excès de pluie). |
| **Autre**<br>*(Maritime : 100k)* | `plateforme = 'MARITIME'`<br>`type_navire`<br>`port_attache`<br>`garantie_maritime` | Embarcation (Pirogue, Vedette de pêche, Caboteur).<br>Port d'attache malgache (Toamasina, Mahajanga, Toliara, Antsiranana).<br>Couverture (Corps de navire, Responsabilité civile, Cargaison). |

> [!NOTE]
> Dans le fichier CSV `clients_autre.csv`, les champs maritimes sont vides pour les dossiers agricoles, et inversement.

---

## 5. Travail demandé pour la Partie 1

Ouvrez le notebook d'exploration `notebooks/01_exploration.ipynb` dans votre environnement JupyterLab :
```sh
uv run --group notebook jupyter lab --ip=127.0.0.1
```

Exécutez les cellules pas à pas en mode rapide, puis activez `PROFIL_COMPLET = True` pour parcourir l'intégralité des 400 000 fiches :

1. **Caractérisation des sources** : Relevez le volume exact de chaque source, le mode d'identification locale et vérifiez les comptages.
2. **Diagnostic des écarts** : Sur des échantillons concrets, listez les disparités de formats (CIN, dates, téléphones, sexe) et les anomalies de saisie (espaces, diacritiques, inversions de prénoms).
3. **Analyse des champs métier** : Vérifiez comment sont stockées les colonnes propres à chaque univers et confirmez la séparation bivalente 50 % Agricole / 50 % Maritime dans le fichier plat.
4. **Rédaction de la fiche de découverte** : Complétez votre tableau de synthèse dans `docs/etudiant/FICHE-DECOUVERTE.md` en illustrant chaque anomalie constatée par un exemple tiré des données.

---

## 6. Feuille de route globale du TP (5 étapes)

1. **Partie 1 (Séance courante)** : Cadrage, préparation locale, exploration des 400 000 fiches et rédaction de la fiche de découverte.
2. **Partie 2** : Normalisation canonique (fonctions pures), formalisation de la matrice de décision `C1`–`C4`, verrou anti-conflit de CIN et rapprochement flou adaptatif (Damerau-Levenshtein).
3. **Partie 3** : Schéma cible `tp_assurance_etl`, ingestion en flux via streaming et chargement unifié sans perte d'information.
4. **Partie 4** : Création manuelle de la colonne pivot `UID`, moteur `CompactUnionFind`, détection des conflits et routage en file d'arbitrage humain.
5. **Partie 5** : Déploiement de la mini-application Web (FastAPI), vue 360°, console d'arbitrage humain et audit automatisé de la qualité de réconciliation.
