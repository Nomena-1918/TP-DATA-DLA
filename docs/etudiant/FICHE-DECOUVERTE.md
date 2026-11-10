# Fiche de découverte des sources — Assurances ARO (TP DATA D.L.A)

## 1. Contexte et objectifs

Dans le cadre de la réconciliation d'identités et de la mise en place d'un référentiel unique (`UID` / `NEW_ID`), nous avons exploré les trois sources de données du système d'information :
- **Auto** : Système de gestion des contrats automobiles sous PostgreSQL 16.
- **Life** : Système des adhésions retraite et épargne vie sous MySQL 8.4.
- **Autre** : Plateformes agricole et maritime distribuées via fichier CSV (`data/clients_autre.csv`).

L'objectif de cette étape est de caractériser les structures, les volumétries, les types et les formats afin d'identifier tous les écarts à normaliser avant d'effectuer le rapprochement.

---

## 2. Synthèse des volumétries observées

| Source | Support technique | Fiches observées | Personnes distinctes | Reprises (doublons internes) | Identifiant local |
| :--- | :--- | ---: | ---: | ---: | :--- |
| **Auto** | PostgreSQL 16 (`tp_assurance.clients_auto`) | 1 000 000 | 990 000 | 10 000 | `id_client_auto` (1 000 001 à 2 000 000) |
| **Life** | MySQL 8.4 (`tp_assurance_life.clients_life`) | 1 000 000 | 990 000 | 10 000 | `ref_adherent` (3 000 001 à 4 000 000) |
| **Autre** | CSV UTF-8 `;` (`data/clients_autre.csv`) | 2 000 000 | 1 980 000 | 20 000 | `ref_fiche` (`EXT-5000001` à `EXT-7000000`) |
| **Total** | Multi-sources | **4 000 000** | **2 560 000** | **40 000** | Références propres par système |

- **Cohorte commune aux 3 sources** : 700 000 personnes physiques possèdent au moins un dossier dans chacun des trois systèmes.
- **Exclusifs à chaque source** : 290 000 pour Auto, 290 000 pour Life, 1 280 000 pour Autre.

---

## 3. Comparaison des champs communs et écarts constatés

| Attribut | Auto (PostgreSQL) | Life (MySQL) | Autre (CSV) | Écart / Normalisation requise |
| :--- | :--- | :--- | :--- | :--- |
| **Pièce d’identité (CIN)** | `numero_cin` (TEXT)<br>Ex: `'CIN- 800005316023'` | `cin_numerique` (BIGINT)<br>Ex: `800005316023` | `piece_identite` (TEXT)<br>Ex: `'800005316023'` | Nettoyer le préfixe `'CIN- '` et extraire les 12 chiffres sous forme textuelle canonique. Gérer les `NULL` et les cas où le CIN est modifié. |
| **Nom de famille** | `nom_assure` (TEXT)<br>Ex: `' Ramanitra '` ou `'RAMANITRA'` | `nom_adherent` (TEXT)<br>Ex: `'RAMANITRA'` (sans accent) | `patronyme` (TEXT)<br>Ex: `'Ramanitra'` ou `'RAMANITRA'` | Supprimer les espaces (`trim`), supprimer les diacritiques (ex: `é` -> `e`), convertir en majuscules. |
| **Prénoms** | `prenoms_assure` (TEXT)<br>Ex: `'Faly Tahina'` | `prenoms_adherent` (TEXT)<br>Ex: `'FALY-TAHINA'` ou `'FALY TAHINA'` | `autres_noms` (TEXT)<br>Ex: `'Tahina Faly'` | Inversion fréquente de l'ordre des prénoms et présence de tirets. Découper en tokens, passer en majuscules sans accent et trier alphabétiquement. |
| **Date de naissance** | `ne_le` (DATE SQL)<br>Ex: `'1970-04-19'` | `date_naiss` (INT)<br>Ex: `19700419` | `date_naissance` (TEXT)<br>Ex: `'19-04-1970'` | Convertir l'ensemble au format standard ISO `YYYY-MM-DD`. |
| **Lieu de naissance** | `ne_a` (TEXT)<br>Ex: `'Toliara'` | `lieu_naiss` (TEXT)<br>Ex: `'TOLIARA'` | `commune_origine` (TEXT)<br>Ex: `'Toliara'` | Passer en majuscules sans accent (`trim`). Traiter les absences (environ 3 à 5 % de valeurs nulles). |
| **Ville / Résidence** | `ville_residence` (TEXT) | `commune_domicile` (TEXT) | `localite` (TEXT) | Passer en majuscules. Attention : une personne peut avoir déménagé entre deux souscriptions. |
| **Téléphone** | `mobile` (TEXT)<br>Ex: `'00 95 397 11'` | `tel_contact` (TEXT)<br>Ex: `'+000009539711'` | `contact_tel` (TEXT)<br>Ex: `'00-95-397-11'` | Retirer le préfixe international fictif `+000`, les espaces et les tirets pour isoler la séquence `00XXXXXXX`. |
| **Courriel** | `courriel` (TEXT) | `email_contact` (TEXT) | `contact_mail` (TEXT) | Passer en minuscules, `trim`. Noter la présence de variations de casse dans les sources. |
| **Sexe / Genre** | `sexe` (TEXT)<br>`'Masculin'` / `'Féminin'` | `genre` (TINYINT)<br>`1` (M) / `0` (F) | `code_sexe` (TEXT)<br>`'M'` / `'F'` | Unifier vers `'M'` et `'F'`. Cohérence garantie à 100 % sur la personne physique par SHA-256. |

---

## 4. Données et champs métier propres à chaque univers

Chaque application gère son périmètre métier sans impact sur l'identité :
- **Auto** : `immatriculation` (unique par véhicule), `annee_vehicule` (1998–2025), `formule_auto` (`Tiers`, `Tiers étendu`, `Tous risques`).
- **Life** : `produit` (`Retraite individuelle`, `Épargne vie`), `cotisation_mensuelle_ar` (en Ariary), `date_adhesion`.
- **Autre (Agricole - 1 000 000 fiches)** : `plateforme = 'AGRICOLE'`, `culture` (Riz, Maïs, Manioc, Vanille, Girofle), `superficie_ha` (décimale avec virgule), `garantie_agricole` (Inondation, Cyclone, Sécheresse, Excès de pluie). Champs maritimes vides.
- **Autre (Maritime - 1 000 000 fiches)** : `plateforme = 'MARITIME'`, `type_navire` (Pirogue, Vedette de pêche, Caboteur), `port_attache` (Toamasina, Mahajanga, Toliara, Antsiranana), `garantie_maritime` (Corps de navire, Responsabilité civile, Cargaison). Champs agricoles vides.

---

## 5. Particularités et cas remarquables pour le rapprochement

1. **Conservation absolue des données sources (Non destructif)** :
   Aucune fiche source ne doit être altérée ou fusionnée physiquement. L'objectif est d'ajouter un identifiant commun (`uid` / `NEW_ID`) à toutes les fiches d'une même personne.
2. **Homonymes parfaits** :
   Des personnes distinctes partagent le même état civil (nom, prénoms, date et lieu de naissance) mais possèdent des CIN et des coordonnées distincts. Le verrou CIN doit interdire tout regroupement erroné.
3. **Membres d'un même foyer** :
   Des personnes distinctes partagent le même numéro de téléphone ou le même courriel (ex. conjoints). Les règles fondées uniquement sur le contact (`C4a`/`C4b` à 50 %) ne doivent pas provoquer de regroupement automatique mais être transmises à la file de validation humaine.
4. **Cas à lien indirect ("ponts" - 3 317 cas dans la cohorte commune)** :
   Auto possède le CIN et le téléphone (sans courriel). Autre possède uniquement le courriel (sans CIN ni téléphone). Life possède le téléphone et le courriel (sans CIN). La transitivité par **Union-Find** permet de relier Auto et Autre via Life.
