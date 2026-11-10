# Blueprint des slides — Partie 2 : Exploration, Nettoyage & Règles de rapprochement

Ce document définit le plan détaillé de la **Présentation 2** sur les 5 présentations prévues pour le TP Data D.L.A. Conçu pour être particulièrement aéré, direct et visuel, il évite toute redondance et guide pas à pas les étudiants dans l'exploration des données, le nettoyage par fonctions pures, la découverte du Record Linkage et la formalisation de la matrice de rapprochement d'identités (`UID`).

> **Règles de rédaction & Identité visuelle**
> - **Anonymisation stricte** : scénario présenté uniquement comme une compagnie d'assurance fictive à Madagascar ; aucune mention d'entreprise réelle ni de cabinet de conseil ; identifiant pivot nommé exclusivement `UID`.
> - **Dimensionnement local unique** : seuls les chiffres du jeu de travail léger (400 000 fiches au total, 100k Auto, 100k Life, 200k Autre, 70k cohorte commune, 256k population théorique, 331 fiches ponts) sont mentionnés.
> - **Zéro répétition & Clarté maximale** : chaque diapositive apporte un angle nouveau sans paraphraser les précédentes ; formulations sobres, directes et accessibles à tous ; vocabulaire varié pour les anomalies (fautes de frappe, anomalies de saisie, écarts d'écriture, variations de graphie, bruit).
> - **Aération & Visuels explicatifs** : diapositives allégées au maximum en texte brut ; priorité aux schémas décisionnels, comparaisons en cartes contrastées et boîtes de code style terminal sombre (`#1E293B`) avec annotations explicatives ligne par ligne.
> - **Palette & Identité IT University** : Bleu institutionnel (`#283A97`), Vert feuille (`#76B729`), Vert citron (`#B2D235`), Arrière-plan doux (`#F8FAFC`) et boîtes sombres (`#1E293B`).
> - **Notes orateur** : repères oraux concrets pour l'enseignant sur chaque diapositive.

---

## Vue d'ensemble des 5 présentations du TP

| Présentation | Titre | Statut | Périmètre principal |
| :--- | :--- | :--- | :--- |
| **Partie 1** | **Cadrage, Préparation locale & Connexion aux datasources** | Validé & Déployé (18 slides) | Contexte métier, prérequis machine, feuille de route, règle d'or non destructive, cartographie, génération & colonnes détaillées des 3 sources, setup local (`uv`, `.env`), connexions en lecture seule. |
| **Partie 2** | **Exploration, Nettoyage & Règles de rapprochement** | **Document courant** (16 slides) | Diagnostic notebook, hétérogénéité des formats, fonctions pures de normalisation, tokenisation des prénoms, concept de Record Linkage (statistique vs déterministe), matrice `C1`–`C4`, verrou anti-conflit CIN, tolérance floue adaptative, aiguillage tripartite et ponts transitifs. |
| **Partie 3** | **Modélisation cible & Pipeline ETL en flux** | À rédiger ultérieurement | Schéma cible `tp_assurance_etl` (sans `uid` au départ), conservation du brut + colonnes canoniques + `details_metier` JSONB, extraction streaming + `COPY`, indexation de base. |
| **Partie 4** | **Ajout DDL `UID` & Moteur Union-Find** | À rédiger ultérieurement | Ajout de la colonne `uid`, structure `CompactUnionFind`, passes exactes `C1`–`C3`, passe floue par blocage `(date_naiss_norm, sexe_norm)`, routage vers la file humaine. |
| **Partie 5** | **Mini-application Web, Arbitrage humain & Audit** | À rédiger ultérieurement | Interface FastAPI (tableau de bord, recherche, fiche groupe `UID`, file de validation dont `SUSPICION_FAUTE_CIN`), tests `pytest` et métriques de réconciliation. |

---

## Détail des 16 diapositives — Présentation 2

---

### Slide 1 — Page de titre : Exploration, Nettoyage & Règles de Rapprochement

- **Arrière-plan** : Bleu ITU sombre (`#283A97`).
- **Badge supérieur** : `LICENCE INFORMATIQUE · TP DATA D.L.A` (Vert citron `#B2D235`, 10pt gras).
- **Titre principal** : `Exploration, Nettoyage & Règles de Rapprochement` (Blanc `#FFFFFF`, 23pt gras).
- **Sous-titre** : `Partie 2 / 5 — De la disparité des sources à la matrice d'attribution du référentiel unique (UID)` (Bleu très clair `#CADCFC`, 12pt).
- **Badges horizontaux (Sources)** :
  - `Auto : PostgreSQL 16 (100k)` · `Life : MySQL 8.4 (100k)` · `Autre : Fichier CSV (200k)`
- **Logo** : IT University (variante claire avec texte blanc).
- **Notes orateur** : Rappeler l'objectif de la séance : transformer des données hétérogènes et bruitées en un socle canonique propre et comparable, puis établir des règles de décision claires avant d'écrire le moindre code d'ingestion.

---

### Slide 2 — Feuille de route & Objectifs de l'étape 2

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `FEUILLE DE ROUTE · PARCOURS EN 5 SÉANCES` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Feuille de route : cap sur l'étape 2` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Comprendre les disparités pour bâtir une matrice de décision irréprochable` (Gris ardoise `#64748B`, 10.5pt).

#### Schéma séquentiel épuré (Progression visuelle)
```text
[ Étape 1 : Préparation & Connexions ]  ──> TERMINÉ (18 slides · Environnement & Sources prêts)
                    │
                    ▼
[ Étape 2 : Exploration & Règles ]      ──> SÉANCE COURANTE
  ├── 1. Diagnostiquer : profils statistiques, formats, anomalies réelles
  ├── 2. Normaliser   : module de fonctions pures (normalisation.py)
  └── 3. Décider      : Record Linkage, matrice C1 à C4 & verrou CIN
                    │
                    ▼
[ Étape 3 : Schéma Cible & ETL Flux ]   ──> Prochaine étape
[ Étape 4 : Moteur Union-Find & UID ]   ──> À venir
[ Étape 5 : App Web & Audit Qualité ]   ──> À venir
```

#### Les 3 livrables concrets de la séance
1. **Diagnostiquer** : cartographier les écarts de types et formats dans `notebooks/01_exploration.ipynb`.
2. **Nettoyer** : coder et valider les fonctions pures dans `src/tp_data_dla/normalisation.py`.
3. **Formaliser** : définir les règles de Record Linkage déterministe avec verrou anti-conflit de CIN.
- **Notes orateur** : Souligner que l'on n'écrit pas encore de données dans la base cible aujourd'hui : on forge les règles et les outils de transformation.

---

### Slide 3 — Le choc des formats réels : un même individu, 3 fiches incompatibles

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `DIAGNOSTIC DES SOURCES · DISPARITÉ TECHNIQUE` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Le choc des formats : un même individu, trois visions` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Cas réel d'une même personne physique présente dans nos trois systèmes` (Gris ardoise `#64748B`, 10.5pt).

#### Tableau comparatif central (Carte blanche `#FFFFFF` bordée de `#E2E8F0`)

| Attribut | Auto (PostgreSQL 16) | Life (MySQL 8.4) | Autre (Fichier CSV) | Diagnostic immédiat |
| :--- | :--- | :--- | :--- | :--- |
| **Identifiant local** | `id_client_auto` = `1004521` | `ref_adherent` = `3004521` | `ref_fiche` = `'EXT-5004521'` | Espaces de clés disjoints |
| **Pièce d'identité** | `numero_cin` = `'CIN- 800005316023'` | `cin_numerique` = `800005316023` | `piece_identite` = `'800005316023'` | Texte préfixé vs BIGINT vs chaîne |
| **Nom de famille** | `nom_assure` = `' Ramanitra '` | `nom_adherent` = `'RAMANITRA'` | `patronyme` = `'Ramanitra'` | Espaces superflus, casse mixte |
| **Prénoms** | `prenoms_assure` = `'Faly Tahina'` | `prenoms_adherent` = `'FALY-TAHINA'` | `autres_noms` = `'Tahina Faly'` | Tirets, casse et ordre inversé |
| **Date naissance** | `ne_le` = `'1970-04-19'` (`DATE`) | `date_naiss` = `19700419` (`INT`) | `date_naissance` = `'19-04-1970'` (`TEXT`) | Date SQL vs Entier compact vs Format texte |
| **Téléphone** | `mobile` = `'00 95 397 11'` | `tel_contact` = `'+000009539711'` | `contact_tel` = `'00-95-397-11'` | Indicatif international, tirets, espaces |
| **Sexe / Genre** | `sexe` = `'Masculin'` | `genre` = `1` | `code_sexe` = `'M'` | Libellé texte vs code binaire (`0/1`) vs lettre |

- **Notes orateur** : Montrer que sans traitement préalable, aucun attribut n'est strictement égal entre les bases.

---

### Slide 4 — Pourquoi un simple JOIN SQL direct est impossible

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `DIAGNOSTIC TECHNIQUE · ÉCHEC DU JOIN CLASSIQUE` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Pourquoi un simple JOIN SQL direct est impossible` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Cloisonnement physique multi-SGBD et rupture sémantique des données` (Gris ardoise `#64748B`, 10.5pt).

#### 2 colonnes aérées
- **Colonne gauche : Boîte Terminal sombre `#1E293B` (Multi-SGBD & SQL naïf)** :
```sql
-- 1. Obstacle physique : 3 moteurs totalement disjoints !
-- Auto  -> PostgreSQL 16 (port 5432)
-- Life  -> MySQL 8.4 (port 3306)
-- Autre -> Disque local (fichier CSV)
-- Impossible d'exécuter un JOIN direct entre serveurs distincts !

-- 2. Même si les tables étaient réunies dans la même base :
SELECT a.nom_assure, l.nom_adherent 
FROM clients_auto a
JOIN clients_life l 
  ON a.numero_cin = l.cin_numerique;
-- ERREUR : operator does not exist: text = bigint

-- 3. Sensibilité à la casse, espaces et formats de date :
SELECT a.id_client_auto, l.ref_adherent
FROM clients_auto a
JOIN clients_life l
  ON a.nom_assure = l.nom_adherent
 AND a.ne_le::text = l.date_naiss::text;
-- RÉSULTAT : 0 correspondance trouvée !
```

- **Colonne droite : Carte explicative (`#FFFFFF`)** :
  - **1. Éparpillement multi-bases** : Données réparties sur 3 technologies différentes. Aucun SGBD ne peut nativement joindre ces sources sans un outillage lourd (connecteurs distants, FDW) ou un pipeline d'ingestion centralisé.
  - **2. Le piège de la migration de schéma** : Consolider ces données dans une base cible exige une migration de schéma préalable, elle-même source majeure de pannes (conflits d'encodage `utf8mb4`/`latin1`, perte de précision, conversions de types).
  - **3. Incompatibilité syntaxique des attributs** : Types physiques opposés (`TEXT` vs `BIGINT`), espaces parasites, casse désordonnée et dates incompatibles (`YYYY-MM-DD` vs entier `19700419`).
  - **Conclusion** : Ni la base de données seule, ni une simple requête SQL ne peuvent résoudre ce problème : un pipeline Python orchestré avec normalisation dédiée est incontournable.
- **Notes orateur** : Bien insister sur le double verrou : le verrou d'architecture (données réparties sur des SGBD hétérogènes imposant une étape délicate d'ingestion) et le verrou sémantique (données sales qui ne se joignent pas).

---

### Slide 5 — Les 4 familles d'anomalies de saisie du monde réel

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `QUALITÉ DES DONNÉES · BIAIS DE SAISIE HUMAINE` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Les 4 familles d'anomalies identifiées dans les sources` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Environ 5 % de variations réalistes reproduisant les habitudes des agents de saisie` (Gris ardoise `#64748B`, 10.5pt).

#### 4 cartes visuelles équilibrées (Grille 2x2 aérée)

```text
┌────────────────────────────────────────┐   ┌────────────────────────────────────────┐
│ 🔤 1. Écarts d'écriture & Casse        │   │ 🔄 2. Variations sur les prénoms       │
│ • Espaces multiples et superflus       │   │ • Séparateurs variés : '-' vs espace   │
│ • Minuscules / Majuscules disparates   │   │ • Ordre inversé : 'TAHINA FALY'        │
│ • Accents et caractères diacritiques   │   │ • Prénoms composés tronqués            │
│   Ex : 'Ramanitra ' vs 'RAMANITRA'     │   │   Ex : 'Faly-Tahina' vs 'Tahina Faly'  │
└────────────────────────────────────────┘   └────────────────────────────────────────┘
                    ▲                                            ▲
                    │                                            │
┌────────────────────────────────────────┐   ┌────────────────────────────────────────┐
│ ⌨️ 3. Fautes de frappe réalistes (~5%) │   │ ⭕ 4. Valeurs manquantes (NULL)        │
│ • Lettre substituée ou doublée         │   │ • ~3 % à 5 % de communes absentes      │
│ • Permutation de deux lettres voisines │   │ • Téléphone ou adresse mail omis       │
│ • Un chiffre erroné sur CIN/téléphone  │   │ • Pièce d'identité en attente (NULL)   │
│   Ex : 'RAKOTOO' ou '800000000083'     │   │   Ex : 'Lieu de naissance : NULL'      │
└────────────────────────────────────────┘   └────────────────────────────────────────┘
```
- **Notes orateur** : Ces anomalies simulent des dizaines d'années de saisies manuelles en agence sans validation centralisée.

---

### Slide 6 — Deux pièges relationnels : Homonymes & Foyers

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `PIÈGES MÉTIER · ÉVITER LES AMALGAMMES` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Deux pièges relationnels : Homonymes et Foyers` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Pourquoi un algorithme naïf commet des fusions destructrices` (Gris ardoise `#64748B`, 10.5pt).

#### 2 cartes contrastées (Danger / Avertissement)
- **Carte 1 : 👥 Le piège des homonymes (Rouge doux `#FEF2F2`, bordure rouge)** :
  - **Situation** : Deux personnes physiques distinctes ont exactement le même nom, les mêmes prénoms et la même date de naissance, mais ont deux numéros de CIN officiels distincts.
  - **Erreur naïve** : Les fusionner sur la seule base de l'état civil.
  - **Conséquence métier** : Violation de la confidentialité et contrats mélangés.
- **Carte 2 : 🏠 Le piège du foyer familial (Jaune doux `#FEF3C7`, bordure ambre)** :
  - **Situation** : Deux conjoints ou un parent et son enfant partagent la même ligne téléphonique ou la même boîte mail de contact.
  - **Erreur naïve** : Fusionner deux fiches dès qu'un numéro de téléphone concorde.
  - **Conséquence métier** : Deux personnes réelles regroupées sous un seul contrat.
- **Notes orateur** : Un bon algorithme de réconciliation doit d'abord savoir ce qu'il est rigoureusement interdit de fusionner.

---

### Slide 7 — Le pipeline de normalisation : principe des fonctions pures

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `NORMALISATION CANONIQUE · ARCHITECTURE` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Le pipeline de normalisation : principe des fonctions pures` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Des transformations déterministes, sans effet de bord et testables unitairement` (Gris ardoise `#64748B`, 10.5pt).

#### Schéma en entonnoir de normalisation
```text
[ Donnée source brute ]  ──> [ Fonction pure de nettoyage ] ──> [ Attribut canonique normalisé ]
'CIN- 800005316023'     ──>       normaliser_cin()         ──> '800005316023' (12 chiffres)
'  Ramanitra  '         ──>       normaliser_nom()         ──> 'RAMANITRA' (sans accent)
'Faly-Tahina'           ──>     normaliser_prenoms()       ──> 'FALY TAHINA' (tokens triés)
'19700419' (INT)        ──>       normaliser_date()        ──> '1970-04-19' (ISO DATE)
'+000009539711'         ──>       normaliser_tel()         ──> '009539711' (9 chiffres)
'Contact@Mail.MG'       ──>       normaliser_mail()        ──> 'contact@mail.mg' (minuscules)
1 ou 'Masculin'         ──>       normaliser_sexe()        ──> 'M' ('M' ou 'F')
```

#### Règle d'or appliquée à l'architecture
- **La donnée brute n'est jamais écrasée ni effacée**.
- Dans la table consolidée, chaque enregistrement conserve sa colonne brute d'origine ET dispose d'une colonne canonique normalisée (`nom_norm`, `cin_norm`, etc.).
- Chaque fonction pure est isolée et testée dans `tests/test_normalisation.py`.
- **Notes orateur** : Ce principe garantit l'auditabilité : on peut toujours remonter à l'exacte saisie initiale d'une agence.

---

### Slide 8 — Implémentation : extraits de normalisation.py

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `CODE SOURCE · MODULE NORMALISATION.PY` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Implémentation : extraits de normalisation.py` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Robustesse face aux formats exotiques et types inattendus` (Gris ardoise `#64748B`, 10.5pt).

#### Boîte Terminal sombre `#1E293B` (Snippets Python réels et commentés)
```python
# src/tp_data_dla/normalisation.py

def normaliser_nom(valeur: Any) -> Optional[str]:
    """Nettoie le patronyme : trim, suppression accents, majuscules."""
    if not valeur:
        return None
    texte = supprimer_accents(str(valeur)).strip().upper()
    return RE_ESPACES.sub(" ", texte) or None

def normaliser_cin(valeur: Any) -> Optional[str]:
    """Extrait une chaîne de 12 chiffres consécutifs sans préfixe."""
    if valeur is None:
        return None
    chiffres = RE_CHIFFRES.sub("", str(valeur))
    return chiffres if len(chiffres) == 12 else None

def normaliser_date(valeur: Any) -> Optional[str]:
    """Convertit INT numérique (19850412), date ou texte vers YYYY-MM-DD."""
    if not valeur:
        return None
    # Gère le piège MySQL (INT 19850412) et formats texte français
    return parse_date_universelle(valeur)
```

#### Carte explicative latérale (`#FFFFFF`)
- **Signature `Any`** : Accepte chaîne, entier ou date sans lever d'exception.
- **Gestion immédiate des `None`** : Sécurité totale face aux valeurs absentes en streaming.
- **Vérification automatique** : Validation de la suite avec `uv run pytest tests/test_normalisation.py`.
- **Notes orateur** : Insister sur l'utilisation de regex précompilées (`RE_CHIFFRES`) pour traiter les 400 000 fiches en quelques secondes.

---

### Slide 9 — Prénoms composés : tokenisation et tri alphabétique

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `NORMALISATION AVANCÉE · PRÉNOMS COMPOSÉS` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Prénoms composés : tokenisation et tri alphabétique` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Comment absorber les variations d'ordre sans aucune perte d'information` (Gris ardoise `#64748B`, 10.5pt).

#### Schéma du mécanisme de tokenisation
```text
   Source Auto (PostgreSQL)            Source Life (MySQL)               Source Autre (CSV)
        'Faly Tahina'                     'FALY-TAHINA'                     'Tahina Faly'
              │                                 │                                 │
              ▼                                 ▼                                 ▼
      Nettoyage accents                 Remplacement '-'                  Nettoyage accents
       + Majuscules                        par espace                        + Majuscules
              │                                 │                                 │
              ▼                                 ▼                                 ▼
    Tokens : ['FALY', 'TAHINA']       Tokens : ['FALY', 'TAHINA']       Tokens : ['TAHINA', 'FALY']
              │                                 │                                 │
              └────────────────┬────────────────┴─────────────────────────────────┘
                               ▼
                    Tri alphabétique des tokens
                               │
                               ▼
               Forme pivot canonique : 'FALY TAHINA'
```

#### Boîte de code (Terminal sombre `#1E293B`)
```python
# Extraction des tokens et tri alphabétique
tokens = [t for t in RE_ESPACES.split(texte_nettoye) if t]
prenoms_norm = " ".join(tokens)              # 'TAHINA FALY' (ordre d'origine)
prenoms_trie_norm = " ".join(sorted(tokens))  # 'FALY TAHINA' (forme pivot commune)
```
- **Notes orateur** : Cette règle très simple élimine à elle seule un gisement majeur de faux négatifs sur les patronymes malgaches.

---

### Slide 10 — Introduction au Record Linkage : du nettoyage à la réconciliation

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `CONCEPTS FONDAMENTAUX · RECORD LINKAGE` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Record Linkage : pourquoi et comment relier ?` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Passer du nettoyage d'attributs individuels à la réconciliation d'identités réelles` (Gris ardoise `#64748B`, 10.5pt).

#### 1. La problématique fondamentale
- Nous avons nettoyé les colonnes individuellement (`nom_norm`, `cin_norm`, etc.).
- **Le défi central** : Comment décider que **deux fiches complètes** issues de bases différentes représentent la **même personne physique**, en l'absence de clé primaire commune ?
- C'est la discipline du **Record Linkage** (ou Rapprochement d'enregistrements / Résolution d'entités).

#### 2. Les deux grandes écoles de Record Linkage
```text
┌──────────────────────────────────────────────┐   ┌──────────────────────────────────────────────┐
│ 1. Approche Statistique / Probabiliste       │   │ 2. Approche Déterministe par Règles          │
│ • Modèle classique de Fellegi-Sunter         │   │ • Suite de règles logiques strictes          │
│ • Poids de vraisemblance et score global     │   │ • Prédicats ordonnés (SI condition ALORS UID)│
│ • Problème : effet boîte noire, difficile    │   │ • Explicabilité totale, motif tracé en base  │
│   à justifier devant un régulateur ou client │   │ • Auditabilité absolue à tout moment         │
└──────────────────────────────────────────────┘   └──────────────────────────────────────────────┘
```

#### 3. Notre choix stratégique : L'approche déterministe hiérarchique
- **Exigence métier & légale** : Dans l'assurance, une fusion de contrats doit être **justifiable et prouvée**.
- **Architecture retenue** : Une cascade de règles déterministes (`C1` à `C4`) avec verrou de sécurité, complétée par une file d'arbitrage humain pour les cas ambigus.
- **Notes orateur** : Souligner que l'approche statistique produit des scores de confiance (ex: 82%) insuffisants pour garantir les droits juridiques d'un assuré sans validation humaine.

---

### Slide 11 — La matrice hiérarchique de rapprochement (C1 à C4)

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `MOTEUR DE RÉCONCILIATION · MATRICE HIÉRARCHIQUE` (Vert `#2EA853`, 10pt gras).
- **Titre** : `La matrice hiérarchique de rapprochement` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Quatre niveaux de règles ordonnées par degré de certitude décroissant` (Gris ardoise `#64748B`, 10.5pt).

#### Pyramide de décision des règles

```text
  [ Règle C1 : Numéro CIN identique (Certitude absolue) ]
  ├── cin_norm valide, complet (12 chiffres) et identique sur les deux fiches
  └── Décision : Attribution automatique immédiate du même UID (Motif: PIVOT_CIN)
        │ (si non concluant / CIN manquant)
        ▼
  [ Règle C2 : État civil complet avec Commune (Très forte confiance) ]
  ├── nom_norm + prenoms_trie_norm + date_naiss_norm + lieu_naiss_norm + ville_norm
  └── Décision : Attribution automatique sous contrôle du verrou CIN
        │ (si non concluant / commune différente)
        ▼
  [ Règle C3 : État civil sans la Commune (Absorbe les déménagements) ]
  ├── nom_norm + prenoms_trie_norm + date_naiss_norm + lieu_naiss_norm
  └── Décision : Attribution automatique sous contrôle du verrou CIN
        │ (si non concluant)
        ▼
  [ Règle C4 : Coordonnées de contact seules (Ambiguïté foyer) ]
  ├── C4a (Identité + Téléphone) ou C4b (Identité + E-mail)
  └── Décision : ATTRIBUTION AUTOMATIQUE INTERDITE ──> File d'arbitrage humain
```

#### Synthèse des règles
- On commence toujours par le critère le plus certain (`C1`).
- Ce n'est qu'en l'absence de CIN qu'on fait appel à l'état civil (`C2`, `C3`).
- **Notes orateur** : Expliquer que la règle `C4` ne doit jamais fusionner automatiquement des dossiers pour ne pas créer d'amalgames entre conjoints ou collègues.

---

### Slide 12 — Le verrou absolu anti-conflit de CIN

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `SÉCURITÉ ALGORITHMIQUE · VERROU INFRANGIBLE` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Le verrou algorithmique anti-conflit de CIN` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Interdiction formelle de relier deux fiches ayant deux CIN distincts` (Gris ardoise `#64748B`, 10.5pt).

#### Diagramme de flux décisionnel du verrou

```text
                   Tentative de rapprochement par C2 ou C3
             (État civil identique : même Nom, Prénoms, Date)
                                    │
                                    ▼
                     Les deux fiches ont-elles un CIN ?
                                    │
                  ┌─────────────────┴─────────────────┐
                 NON                                 OUI
                  │                                   │
                  ▼                                   ▼
        Au moins un CIN est NULL             Les 2 CIN sont-ils identiques ?
                  │                                   │
                  ▼                         ┌─────────┴─────────┐
          UNION AUTORISÉE                  OUI                 NON
        Le CIN connu est propagé            │                   │
                                            ▼                   ▼
                                     UNION AUTORISÉE     VERROU ACTIVÉ !
                                    (Confirmé par C1)   Attribution INTERDITE
                                                        Envoi en CONFLIT_CIN
```

#### Étude de cas : la protection des homonymes
- **Fiche A (Auto)** : `'ANDRIANINA Mamy'`, né le `1985-06-12` à Antananarivo, CIN = `'101234567890'`
- **Fiche B (Life)** : `'ANDRIANINA Mamy'`, né le `1985-06-12` à Antananarivo, CIN = `'201987654321'`
- **Sans le verrou** : `C2` regroupe les deux fiches sous un même `UID`. **Faute métier grave**.
- **Avec le verrou** : Le moteur détecte deux numéros CIN valides différents, bloque l'union et consigne l'alerte `CONFLIT_CIN`.
- **Notes orateur** : À Madagascar, la carte d'identité nationale est la vérité d'état civil officielle. Deux CIN valides différents garantissent qu'il s'agit de deux personnes physiques différentes, peu importe leur nom.

---

### Slide 13 — Rapprochement flou adaptatif : attraper les fautes de frappe

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `ALGORITHMIQUE · RAPPROCHEMENT FLOU` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Rapprochement flou adaptatif : l'intuition concrète` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Comment rattraper les fautes de frappe sans provoquer d'amalgames` (Gris ardoise `#64748B`, 10.5pt).

#### L'intuition concrète de la distance textuelle
- **Mesure de ressemblance (Damerau-Levenshtein)** : On compte le nombre minimal d'opérations d'édition (insertion, suppression, substitution ou inversion de 2 lettres adjacentes) pour passer d'un mot à l'autre.
- **Règle adaptative selon la longueur du mot** :
  - **Mots courts (< 9 lettres)** : Seuil toléré = **1 opération maximum**.
    - Exemple : `'HERY'` $\leftrightarrow$ `'HERI'` (1 lettre substituée $\rightarrow$ accepté).
    - Rejeté : `'HERY'` $\leftrightarrow$ `'FALY'` (2 lettres différentes $\rightarrow$ rejeté !).
  - **Mots longs ($\ge$ 9 lettres)** : Seuil toléré = **2 opérations maximum**.
    - Exemple : `'ANDRIAMAHERY'` $\leftrightarrow$ `'ANDRIAMAHARI'` (2 lettres d'écart sur mot long $\rightarrow$ accepté).

#### Règle d'or sur les attributs numériques (CIN & Téléphone)
- **Tolérance maximale = 1 seul chiffre d'écart** (jamais $\ge$ 2).
- **Pourquoi ?** Deux séries de chiffres consécutifs diffèrent de 2 chiffres mais désignent deux personnes réelles totalement différentes (`800000000083` vs `800000000010`).
- Tout écart d'un chiffre sur un CIN fait l'objet d'un contrôle humain sous le statut `SUSPICION_FAUTE_CIN`.
- **Notes orateur** : Expliquer que fixer un seuil trop laxiste sur les nombres provoquerait une catastrophe d'avalanche : des milliers d'inconnus se retrouveraient regroupés sous le même UID.

---

### Slide 14 — Routage des décisions : automatique vs arbitrage humain

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `ARBITRAGE MÉTIER · ROUTAGE À 3 VOIES` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Routage des décisions : automatique vs arbitrage humain` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Quand le système tranche-t-il seul et quand passe-t-il la main au gestionnaire ?` (Gris ardoise `#64748B`, 10.5pt).

#### Schéma d'aiguillage tripartite

```text
                           Candidat au rapprochement
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
  [ Voie Automatique (Verte) ] [ File de Validation (Ambre) ] [ Voie Maintien (Rouge) ]
  • C1 : CIN identique         • C4a / C4b (Suspicion Foyer)  • CONFLIT_CIN (>= 2 chiffres)
  • C2 : État civil complet    • SUSPICION_FAUTE_CIN          • Incohérence majeure
  • C3 : Sans commune            (Même état civil mais        • Homonymes confirmés
  • C2/C3 Flou conforme           1 chiffre d'écart sur CIN)
            │                          │                          │
            ▼                          ▼                          ▼
      Attribution UID            Écran Arbitrage            Maintien fiches
     sans intervention             Gestionnaire               séparées
```

#### Les deux motifs isolés pour la validation humaine
1. **`SUSPICION_FOYER`** : Fiches partageant le même téléphone ou e-mail sans état civil identique (évite d'amalgamer les conjoints).
2. **`SUSPICION_FAUTE_CIN`** : Même état civil exact, mais un CIN diffère d'un chiffre (faute de frappe probable nécessitant un contrôle visuel sur document officiel).
- **Notes orateur** : Présenter la file humaine comme une force du système : savoir solliciter un opérateur sur les cas ambigus plutôt que d'altérer la base est la marque d'un système robuste.

---

### Slide 15 — Cas complexes : les 331 ponts de la cohorte commune

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `CAS COMPLEXES · TRANSITIVITÉ MULTI-SOURCES` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Cas complexes : les 331 ponts de la cohorte commune` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Comment relier deux fiches ne partageant aucun attribut direct` (Gris ardoise `#64748B`, 10.5pt).

#### Schéma du pont transitif entre les trois dossiers
```text
  [ Fiche Auto ]                   [ Fiche Life ]                   [ Fiche Autre ]
  • CIN : 800005316023             • CIN : NULL                     • CIN : NULL
  • TEL : 009539711                • TEL : 009539711                • TEL : NULL
  • MAIL : NULL                    • MAIL : client@mail.mg          • MAIL : client@mail.mg
         │                                │                                │
         └────────── Lien A ──────────────┘                                │
             (Même Téléphone + Nom)                                        │
                                          └────────── Lien B ──────────────┘
                                               (Même E-mail + Nom)
                                                          │
  ════════════════════════════════════════════════════════╪══════════════════════════════════════════════
                                                          ▼
               Transitivité : Fiche Auto <---> Fiche Life <---> Fiche Autre
                                                          │
                                                          ▼
                               Un seul et même individu physique identifié :
                                     Attribution d'un UID unique commun !
```

#### La puissance de la transitivité
- En interrogeant uniquement Auto et Autre, aucun attribut n'est commun : une jointure bipartite classique échoue.
- La présence de la fiche Life sert de **pont** : si $A$ est relié à $B$ et que $B$ est relié à $C$, alors $A$ et $C$ appartiennent au même individu.
- C'est cette logique transitive qui justifiera l'utilisation de la structure de données **Union-Find** en Partie 4.
- **Notes orateur** : Faire prendre conscience aux étudiants qu'un enchaînement de requêtes SQL `UPDATE` ne peut pas gérer ces ponts sans risquer des boucles ou des incohérences.

---

### Slide 16 — Bilan de la Partie 2 & Cap sur l'ETL (Partie 3)

- **Arrière-plan** : Bleu ITU sombre (`#283A97`).
- **Badge supérieur** : `BILAN DE SÉANCE · PERSPECTIVES ÉTAPE 3` (Vert citron `#B2D235`, 10pt gras).
- **Titre** : `Bilan de la Partie 2 & Cap sur l'ETL` (Blanc `#FFFFFF`, 22pt gras).
- **Sous-titre** : `Nos règles sont formalisées, place à l'ingestion industrielle en streaming` (Bleu très clair `#CADCFC`, 11pt).

#### 2 cartes récapitulatives contrastées
- **Carte gauche : Acquis validés de la séance (`#1E293B`, bordure `#334155`)** :
  - `[X]` Profilage des 3 sources dans `notebooks/01_exploration.ipynb`.
  - `[X]` Module `normalisation.py` opérationnel (fonctions pures testées avec pytest).
  - `[X]` Tokenisation et tri alphabétique des prénoms validés.
  - `[X]` Choix et justification du Record Linkage déterministe.
  - `[X]` Matrice de décision hiérarchique `C1` à `C4` formalisée.
  - `[X]` Verrou de sécurité anti-conflit de CIN intégré à l'arbre logique.
- **Carte droite : Ce qui nous attend en Partie 3 (`#1E293B`, bordure `#334155`)** :
  - **Schéma cible unifié** : table PostgreSQL `tp_assurance_etl.clients_consolides`.
  - **Règle d'or respectée** : stockage brut d'origine + colonnes canoniques + détails métier en `JSONB`.
  - **Ingestion streaming** : extraction par curseur serveur, normalisation au fil de l'eau et insertion ultra-rapide par protocole binaire `COPY`.
- **Notes orateur** : Féliciter les étudiants pour la rigueur d'analyse acquise. Annoncer que lors de la prochaine séance, nous passerons à l'exécution du pipeline d'ingestion sous Python.
