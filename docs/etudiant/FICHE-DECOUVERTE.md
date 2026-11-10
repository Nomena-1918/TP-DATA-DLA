# Fiche de découverte des sources — Référentiel Unique UID (TP DATA D.L.A)

## 1. Contexte et objectifs

Dans le cadre de la réconciliation d'identités et de la mise en place d'un référentiel unique (`UID`), nous avons exploré les trois sources de données du système d'information :
- **Auto** : Système de gestion des contrats automobiles sous PostgreSQL 16 (`tp_assurance.clients_auto`).
- **Life** : Système des adhésions retraite et épargne vie sous MySQL 8.4 (`tp_assurance_life.clients_life`).
- **Autre** : Plateformes agricole et maritime distribuées via fichier plat CSV (`data/clients_autre.csv`).

L'objectif de cette étape d'exploration est de caractériser les structures, les volumétries, les types et les formats afin d'identifier l'ensemble des écarts à normaliser avant d'effectuer le rapprochement.

---

## 2. Synthèse des volumétries observées (Jeu léger : 400 000 fiches)

| Source | Support technique | Fiches observées | Personnes distinctes | Reprises (doublons internes) | Identifiant local |
| :--- | :--- | ---: | ---: | ---: | :--- |
| **Auto** | PostgreSQL 16 (`tp_assurance.clients_auto`) | 100 000 | 99 000 | 1 000 | `id_client_auto` (1 000 001 à 1 100 000) |
| **Life** | MySQL 8.4 (`tp_assurance_life.clients_life`) | 100 000 | 99 000 | 1 000 | `ref_adherent` (3 000 001 à 3 100 000) |
| **Autre** | CSV UTF-8 `;` (`data/clients_autre.csv`) | 200 000 | 198 000 | 2 000 | `ref_fiche` (`EXT-5000001` à `EXT-5200000`) |
| **Total** | Multi-sources | **400 000** | **256 000** | **4 000** | Références propres par système |

- **Cohorte commune aux 3 sources** : 70 000 personnes physiques possèdent au moins un dossier dans chacun des trois systèmes.
- **Exclusifs à chaque source** : 29 000 pour Auto, 29 000 pour Life, 128 000 pour Autre.
- **Doublons internes (reprises)** : 1 % des fiches de chaque base correspondent à un renouvellement ou second contrat pour un même client (+1 000 Auto, +1 000 Life, +2 000 Autre).

---

## 3. Comparaison des champs communs et écarts constatés

| Attribut | Auto (PostgreSQL) | Life (MySQL) | Autre (CSV) | Écart / Normalisation requise |
| :--- | :--- | :--- | :--- | :--- |
| **Pièce d’identité (CIN)** | `numero_cin` (TEXT)<br>Ex: `'CIN- 800005316023'` | `cin_numerique` (BIGINT)<br>Ex: `800005316023` | `piece_identite` (TEXT)<br>Ex: `'800005316023'` | Nettoyer le préfixe `'CIN- '` et extraire les 12 chiffres sous forme textuelle canonique. Gérer les `NULL` et les cas où le CIN comporte des erreurs de frappe. |
| **Nom de famille** | `nom_assure` (TEXT)<br>Ex: `' Ramanitra '` ou `'RAMANITRA'` | `nom_adherent` (TEXT)<br>Ex: `'RAMANITRA'` (sans accent) | `patronyme` (TEXT)<br>Ex: `'Ramanitra'` ou `'RAMANITRA'` | Supprimer les espaces parasites (`trim`), éliminer les diacritiques (ex: `é` -> `e`), convertir en majuscules. |
| **Prénoms** | `prenoms_assure` (TEXT)<br>Ex: `'Faly Tahina'` | `prenoms_adherent` (TEXT)<br>Ex: `'FALY-TAHINA'` ou `'FALY TAHINA'` | `autres_noms` (TEXT)<br>Ex: `'Tahina Faly'` | Inversion fréquente de l'ordre des prénoms et présence de tirets. Découper en tokens, passer en majuscules sans accent et trier alphabétiquement. |
| **Date de naissance** | `ne_le` (DATE SQL)<br>Ex: `'1970-04-19'` | `date_naiss` (INT)<br>Ex: `19700419` | `date_naissance` (TEXT)<br>Ex: `'19-04-1970'` | Convertir l'ensemble au format standard ISO `YYYY-MM-DD`. |
| **Lieu de naissance** | `ne_a` (TEXT)<br>Ex: `'Toliara'` | `lieu_naiss` (TEXT)<br>Ex: `'TOLIARA'` | `commune_origine` (TEXT)<br>Ex: `'Toliara'` | Passer en majuscules sans accent (`trim`). Traiter les absences (environ 3 à 5 % de valeurs nulles). |
| **Ville / Résidence** | `ville_residence` (TEXT) | `commune_domicile` (TEXT) | `localite` (TEXT) | Passer en majuscules. Attention : une personne peut avoir déménagé entre deux souscriptions. |
| **Téléphone** | `mobile` (TEXT)<br>Ex: `'00 95 397 11'` | `tel_contact` (TEXT)<br>Ex: `'+000009539711'` | `contact_tel` (TEXT)<br>Ex: `'00-95-397-11'` | Retirer le préfixe international fictif `+000`, les espaces et les tirets pour isoler la séquence `00XXXXXXX`. |
| **Courriel** | `courriel` (TEXT) | `email_contact` (TEXT) | `contact_mail` (TEXT) | Passer en minuscules, `trim`. Noter la présence de variations de casse dans les sources. |
| **Sexe / Genre** | `sexe` (TEXT)<br>`'Masculin'` / `'Féminin'` | `genre` (TINYINT)<br>`1` (M) / `0` (F) | `code_sexe` (TEXT)<br>`'M'` / `'F'` | Unifier vers `'M'` et `'F'`. Cohérence garantie sur la personne physique par empreinte déterministe. |

---

## 4. Données et champs métier propres à chaque univers

Chaque application gère son périmètre métier sans impact sur l'identité :
- **Auto** : `immatriculation` (unique par véhicule), `annee_vehicule` (1998–2025), `formule_auto` (`Tiers`, `Tiers étendu`, `Tous risques`).
- **Life** : `produit` (`Retraite individuelle`, `Épargne vie`), `cotisation_mensuelle_ar` (en Ariary), `date_adhesion`.
- **Autre (Agricole - 100 000 fiches)** : `plateforme = 'AGRICOLE'`, `culture` (Riz, Maïs, Manioc, Vanille, Girofle), `superficie_ha` (décimale avec virgule), `garantie_agricole` (Inondation, Cyclone, Sécheresse, Excès de pluie). Champs maritimes vides.
- **Autre (Maritime - 100 000 fiches)** : `plateforme = 'MARITIME'`, `type_navire` (Pirogue, Vedette de pêche, Caboteur), `port_attache` (Toamasina, Mahajanga, Toliara, Antsiranana), `garantie_maritime` (Corps de navire, Responsabilité civile, Cargaison). Champs agricoles vides.

---

## 5. Particularités et cas remarquables pour le rapprochement

1. **Conservation absolue des données sources (Non destructif)** :
   Aucune fiche source ne doit être altérée ou fusionnée physiquement. L'objectif est d'ajouter un identifiant commun (`UID`) à toutes les fiches d'une même personne.
2. **Homonymes parfaits** :
   Des personnes distinctes partagent le même état civil (nom, prénoms, date et lieu de naissance) mais possèdent des CIN et des coordonnées distincts. Le verrou CIN doit interdire tout regroupement erroné.
3. **Membres d'un même foyer** :
   Des personnes distinctes partagent le même numéro de téléphone ou le même courriel (ex. conjoints). Les règles fondées uniquement sur le contact (`C4a`/`C4b` à 50 %) ne doivent pas provoquer de regroupement automatique mais être transmises à la file de validation humaine.
4. **Cas à lien indirect ("ponts" - 331 cas dans la cohorte commune)** :
   Auto possède le CIN et le téléphone (sans courriel). Autre possède uniquement le courriel (sans CIN ni téléphone). Life possède le téléphone et le courriel (sans CIN). La transitivité par **Union-Find** permet de relier Auto et Autre via Life.
