# Blueprint des slides — Partie 2 : Exploration, Nettoyage & Règles de rapprochement

Ce document définit le plan détaillé de la **Présentation 2** sur les 5 présentations prévues pour le TP Data D.L.A. Conçu pour être accessible, visuel et pédagogique, il guide les étudiants dans l'exploration active des trois sources de données via le notebook Jupyter, la caractérisation des disparités de formats et des anomalies de saisie, l'écriture des fonctions pures de normalisation, et la conception de la matrice hiérarchique de rapprochement d'identités (`UID`) avec son verrou de sécurité anti-conflit.

> **Règles de rédaction & Identité visuelle**
> - **Anonymisation stricte** : scénario présenté uniquement comme une compagnie d'assurance fictive à Madagascar ; aucune mention d'entreprise réelle ni de cabinet de conseil ; identifiant pivot nommé exclusivement `UID`.
> - **Dimensionnement local unique** : seuls les chiffres du jeu de travail léger (400 000 fiches au total, 100k Auto, 100k Life, 200k Autre, 70k cohorte commune, 256k population théorique) sont mentionnés.
> - **Accessibilité pour tous** : formulations naturelles, simples et directes ; chaque concept mathématique ou algorithmique est expliqué par son intuition concrète ; bannissement des répétitions de pourcentages excessifs et de « coquilles » (synonymes variés : fautes de frappe, anomalies de saisie, écarts d'écriture, variations de graphie).
> - **Visuels & Code snippets** : diapositives allégées en texte, cartes à fort contraste visuel, diagrammes de décision fléchés et boîtes de code style terminal sombre (`#1E293B`) avec texte clair (`#F1F5F9`).
> - **Palette & Identité IT University** : Bleu institutionnel (`#283A97`), Vert feuille (`#76B729`), Vert citron (`#B2D235`), Arrière-plan doux (`#F8FAFC`) et boîtes sombres (`#1E293B`).
> - **Notes orateur** : repères oraux concrets pour l'enseignant sur chaque diapositive.

---

## Vue d'ensemble des 5 présentations du TP

| Présentation | Titre | Statut | Périmètre principal |
| :--- | :--- | :--- | :--- |
| **Partie 1** | **Cadrage, Préparation locale & Connexion aux datasources** | Validé & Déployé (18 slides) | Contexte métier, prérequis machine, feuille de route, règle d'or non destructive, cartographie, génération & colonnes détaillées des 3 sources, setup local (`uv`, `.env`), connexions en lecture seule. |
| **Partie 2** | **Exploration, Nettoyage & Règles de rapprochement** | **Document courant** (15 slides) | Diagnostic notebook, hétérogénéité des formats, fonctions pures de normalisation, tokenisation des prénoms, matrice hybride `C1`–`C4`, verrou anti-conflit CIN, tolérance floue adaptative, aiguillage tripartite et ponts transitifs. |
| **Partie 3** | **Modélisation cible & Pipeline ETL en flux** | À rédiger ultérieurement | Schéma cible `tp_assurance_etl` (sans `uid` au départ), conservation du brut + colonnes canoniques + `details_metier` JSONB, extraction streaming + `COPY`, indexation de base. |
| **Partie 4** | **Ajout DDL `UID` & Moteur Union-Find** | À rédiger ultérieurement | Ajout de la colonne `uid`, structure `CompactUnionFind`, passes exactes `C1`–`C3`, passe floue par blocage `(date_naiss_norm, sexe_norm)`, routage vers la file humaine. |
| **Partie 5** | **Mini-application Web, Arbitrage humain & Audit** | À rédiger ultérieurement | Interface FastAPI (tableau de bord, recherche, fiche groupe `UID`, file de validation dont `SUSPICION_FAUTE_CIN`), tests `pytest` et métriques de réconciliation. |

---

## Détail des 15 diapositives — Présentation 2

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

#### Schéma séquentiel du TP (5 blocs horizontaux / verticaux)
```text
[ Étape 1 : Préparation & Connexions ]  --> TERMINÉ (18 slides · Environnement & Sources prêts)
                    │
                    v
[ Étape 2 : Exploration & Règles ]      --> SÉANCE COURANTE
  ├── 1. Diagnostiquer : profils statistiques, formats, anomalies réelles
  ├── 2. Normaliser   : module de fonctions pures (normalisation.py)
  └── 3. Décider      : matrice C1 à C4, tolérance floue & verrou CIN
                    │
                    v
[ Étape 3 : Schéma Cible & ETL Flux ]   --> Prochaine étape
[ Étape 4 : Moteur Union-Find & UID ]   --> À venir
[ Étape 5 : App Web & Audit Qualité ]   --> À venir
```

#### Les 3 livrables concrets de la séance
1. **Diagnostiquer les hétérogénéités** : types SQL disparates, formats textuels, dates, diacritiques, casse et conventions par système.
2. **Implémenter les fonctions pures de normalisation** : transformation déterministe vers des colonnes canoniques comparables.
3. **Formaliser la matrice hiérarchique de rapprochement** : règles `C1` à `C4`, gestion des seuils flous et verrou absolu anti-conflit de CIN.
- **Notes orateur** : Aujourd'hui, on ne charge pas encore la base cible définitive et on n'assigne pas encore les `UID`. On observe, on nettoie et on formalise les critères de décision.

---

### Slide 3 — Le choc des formats réels : un même individu, 3 fiches incompatibles

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `DIAGNOSTIC DES SOURCES · DISPARITÉ TECHNIQUE` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Le choc des formats : un même individu, trois visions` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Exemple réel d'une même personne enregistrée dans nos trois bases` (Gris ardoise `#64748B`, 10.5pt).

#### Tableau comparatif concret (Carte centrale blanche `#FFFFFF` bordée de `#E2E8F0`)

| Attribut | Auto (PostgreSQL 16) | Life (MySQL 8.4) | Autre (Fichier CSV) | Diagnostic immédiat |
| :--- | :--- | :--- | :--- | :--- |
| **Identifiant local** | `id_client_auto` = `1004521` | `ref_adherent` = `3004521` | `ref_fiche` = `'EXT-5004521'` | Espaces de clés totalement disjoints |
| **Pièce d'identité** | `numero_cin` = `'CIN- 800005316023'` | `cin_numerique` = `800005316023` | `piece_identite` = `'800005316023'` | Préfixe texte vs entier `BIGINT` vs chaîne |
| **Nom de famille** | `nom_assure` = `' Ramanitra '` | `nom_adherent` = `'RAMANITRA'` | `patronyme` = `'Ramanitra'` | Espaces parasites, casse mixte |
| **Prénoms** | `prenoms_assure` = `'Faly Tahina'` | `prenoms_adherent` = `'FALY-TAHINA'` | `autres_noms` = `'Tahina Faly'` | Tirets, casse et inversion de l'ordre |
| **Date naissance** | `ne_le` = `'1970-04-19'` (`DATE`) | `date_naiss` = `19700419` (`INT`) | `date_naissance` = `'19-04-1970'` (`TEXT`) | Date SQL vs Entier compact vs Format français |
| **Téléphone** | `mobile` = `'00 95 397 11'` | `tel_contact` = `'+000009539711'` | `contact_tel` = `'00-95-397-11'` | Indicatif international, tirets, espaces |
| **Sexe / Genre** | `sexe` = `'Masculin'` | `genre` = `1` | `code_sexe` = `'M'` | Libellé texte vs code binaire (`0/1`) vs lettre |

- **Notes orateur** : Faire remarquer aux étudiants qu'aucune colonne n'est immédiatement comparable à l'état brut. Même la date de naissance est stockée sous 3 types physiques complètement différents.

---

### Slide 4 — Pourquoi la jointure SQL directe échoue lamentablement

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `DIAGNOSTIC TECHNIQUE · ÉCHEC DU JOIN CLASSIQUE` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Pourquoi un simple JOIN SQL direct est impossible` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Deux requêtes naïves et leurs conséquences immédiates` (Gris ardoise `#64748B`, 10.5pt).

#### 2 colonnes comparatives
- **Colonne gauche : Boîte Terminal sombre `#1E293B` (Code SQL naïf)** :
```sql
-- Tentative 1 : Jointure directe sur le CIN
SELECT a.nom_assure, l.nom_adherent 
FROM tp_assurance.clients_auto a
JOIN tp_assurance_life.clients_life l 
  ON a.numero_cin = l.cin_numerique;
-- ERREUR : Incompatibilité de types (TEXT vs BIGINT) !

-- Tentative 2 : Jointure sur Nom et Date
SELECT a.id_client_auto, l.ref_adherent
FROM tp_assurance.clients_auto a
JOIN tp_assurance_life.clients_life l
  ON a.nom_assure = l.nom_adherent
 AND a.ne_le::text = l.date_naiss::text;
-- RÉSULTAT : 0 correspondance trouvée !
```

- **Colonne droite : Carte d'analyse des blocages (`#FFFFFF`)** :
  - **1. Rupture de types physiques** : Un moteur SQL refuse d'office de joindre une chaîne formatée `'CIN- ...'` avec un entier numérique.
  - **2. Bruit invisible** : Les espaces de début/fin (`' Ramanitra '`) et la sensibilité à la casse font échouer l'égalité stricte `=`.
  - **3. Formats de date non alignés** : `'1970-04-19'` ne correspondra jamais à `'19700419'`.
  - **Conclusion** : Un pipeline de transformation canonique en amont est indispensable avant tout rapprochement.
- **Notes orateur** : Souligner que l'échec de la jointure directe est typique des systèmes d'information d'entreprise historiques bâtis en silos indépendants.

---

### Slide 5 — Les 4 familles d'anomalies de saisie du monde réel

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `QUALITÉ DES DONNÉES · BIAIS DE SAISIE HUMAINE` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Les 4 familles d'anomalies identifiées dans les sources` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Environ 5 % de bruit réaliste simulant les habitudes des agents de saisie` (Gris ardoise `#64748B`, 10.5pt).

#### 4 cartes visuelles équilibrées (Grille 2x2 avec fonds thématiques clairs)

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
- **Notes orateur** : Préciser que ces erreurs ne sont pas des bugs de notre générateur mais une reproduction fidèle des données réelles d'assurance où plusieurs personnes saisissent sur des formulaires différents au fil des décennies.

---

### Slide 6 — Deux pièges relationnels majeurs : Homonymes & Foyers

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `PIÈGES MÉTIER · ÉVITER LES AMALGAMMES` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Deux pièges relationnels : Homonymes et Foyers` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Pourquoi un algorithme naïf commet des fusions illégitimes catastrophiques` (Gris ardoise `#64748B`, 10.5pt).

#### 2 cartes contrastées (Danger / Avertissement)
- **Carte 1 : 👥 Le piège des homonymes (Rouge doux `#FEF2F2`, bordure rouge)** :
  - **Cas concret** : Deux individus distincts s'appellent « Jean RAKOTO », sont nés le même jour dans la même ville, mais ont deux numéros CIN officiels distincts.
  - **Risque d'un algorithme naïf** : Les regrouper sous un seul UID sur la base de l'état civil.
  - **Conséquence métier** : Fusion illégitime de contrats d'assurance, violation de la confidentialité des données personnelles.
- **Carte 2 : 🏠 Le piège du foyer familial (Jaune doux `#FEF3C7`, bordure ambre)** :
  - **Cas concret** : Deux conjoints ou un parent et son enfant partagent la même ligne fixe, le même mobile de contact ou la même boîte courriel.
  - **Risque d'un algorithme naïf** : Conclure qu'un même numéro de téléphone équivaut à un seul individu.
  - **Conséquence métier** : Amalgamation de deux personnes distinctes en une seule fiche client.
- **Notes orateur** : Insister sur ces deux pièges : un bon système de réconciliation ne doit pas seulement rapprocher ce qui se ressemble, il doit avant tout savoir ce qu'il est formellement interdit de fusionner !

---

### Slide 7 — Le pipeline de normalisation canonique

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
- Les fonctions de nettoyage sont pures : pour une même entrée, elles retournent toujours exactement la même sortie, sans modifier d'état global.
- **Notes orateur** : Ce découpage permet de tester chaque fonction unitairement dans `tests/test_normalisation.py` avant de la brancher sur des centaines de milliers de lignes.

---

### Slide 8 — Implémentation : les fonctions de nettoyage essentielles

- **Arrière-plan** : Blanc cassé moderne (`#F8FAFC`).
- **Badge supérieur** : `CODE SOURCE · MODULE NORMALISATION.PY` (Vert `#2EA853`, 10pt gras).
- **Titre** : `Implémentation : extraits de normalisation.py` (Bleu nuit `#1E293B`, 19pt gras).
- **Sous-titre** : `Robustesse face aux formats exotiques et types inattendus` (Gris ardoise `#64748B`, 10.5pt).

#### Boîte Terminal sombre `#1E293B` (Snippets Python réels du projet)
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
- Gestion défensive du type `Any` : accepte aussi bien un entier qu'une chaîne ou une instance `datetime`.
- Les expressions régulières (`re.compile`) sont précompilées au chargement du module pour garantir une vitesse d'exécution optimale.
- Validation immédiate via la suite de tests : `uv run pytest tests/test_normalisation.py`.
- **Notes orateur** : Montrer que chaque fonction gère le cas des valeurs absentes (`None`) dès la première ligne pour éviter toute exception en milieu de flux ETL.

---

### Slide 9 — Le traitement des prénoms : tokenisation et tri alphabétique

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
- **Notes orateur** : Souligner que cette règle simple résout à elle seule la très grande majorité des faux négatifs observés sur les prénoms composés malgaches où l'ordre de saisie varie selon les agences.

---

### Slide 10 — La matrice hiérarchique de rapprochement (C1 à C4)

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

### Slide 11 — Le verrou absolu anti-conflit de CIN

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

### Slide 12 — Rapprochement flou adaptatif : attraper les fautes de frappe

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

### Slide 13 — Routage métier : Automatique vs File de validation humaine

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

### Slide 14 — Cas complexes : le pont transitif de la cohorte commune

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

### Slide 15 — Bilan de la séance & Cap sur la Partie 3 (Pipeline ETL)

- **Arrière-plan** : Bleu ITU sombre (`#283A97`).
- **Badge supérieur** : `BILAN DE SÉANCE · PERSPECTIVES ÉTAPE 3` (Vert citron `#B2D235`, 10pt gras).
- **Titre** : `Bilan de la Partie 2 & Cap sur l'ETL` (Blanc `#FFFFFF`, 22pt gras).
- **Sous-titre** : `Nos règles sont formalisées, place à l'ingestion industrielle en streaming` (Bleu très clair `#CADCFC`, 11pt).

#### 2 cartes récapitulatives contrastées
- **Carte gauche : Checklist des acquis de la Partie 2 (`#1E293B`, bordure `#334155`)** :
  - `[X]` Profilage des 3 sources dans `notebooks/01_exploration.ipynb`.
  - `[X]` Module `normalisation.py` opérationnel (fonctions pures testées avec pytest).
  - `[X]` Tokenisation et tri alphabétique des prénoms validés.
  - `[X]` Matrice de décision hiérarchique `C1` à `C4` formalisée.
  - `[X]` Verrou de sécurité anti-conflit de CIN intégré à l'arbre logique.
- **Carte droite : Ce qui nous attend en Partie 3 (`#1E293B`, bordure `#334155`)** :
  - **Schéma cible unifié** : table PostgreSQL `tp_assurance_etl.clients_consolides`.
  - **Règle d'or respectée** : stockage brut d'origine + colonnes canoniques + détails métier en `JSONB`.
  - **Ingestion streaming** : extraction par curseur serveur, normalisation au fil de l'eau et insertion ultra-rapide par protocole binaire `COPY`.
- **Notes orateur** : Féliciter les étudiants pour la rigueur d'analyse acquise. Annoncer que lors de la prochaine séance, nous passerons à l'exécution du pipeline d'ingestion sous Python.
