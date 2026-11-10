# Blueprint des slides — Partie 2 : Exploration, Nettoyage & Règles de rapprochement

Ce document définit le plan détaillé de la **Présentation 2** sur les 5 présentations prévues pour le TP Data D.L.A. Elle guide les étudiants dans l'exploration active des trois sources via le notebook Jupyter, la caractérisation des hétérogénéités et des anomalies réelles, l'écriture des fonctions pures de normalisation, et la conception de la matrice hiérarchique de rapprochement d'identités (`UID`) avec son verrou anti-conflit.

> **Règles de rédaction du support**
> - **Anonymisation stricte** : scénario présenté uniquement comme une compagnie d'assurance fictive à Madagascar ; aucune mention d'entreprise réelle ni de cabinet de conseil ; identifiant pivot nommé exclusivement `UID`.
> - **Dimensionnement local unique** : seuls les chiffres du jeu de travail léger (400 000 fiches au total, 100k Auto, 100k Life, 200k Autre, 70k cohorte commune, 256k population théorique) sont mentionnés.
> - **Accessibilité pour tous** : formulations naturelles, simples et directes ; suppression du jargon mathématique abstrait ; bannissement des répétitions de « 100 % » et de « coquilles » (synonymes variés).
> - **Visuels & Code snippets** : privilégier les schémas conceptuels, diagrammes de décision et boîtes de code style terminal sombre (`#1E293B`) avec coloration claire.
> - **Notes orateur** : repères oraux concrets pour chaque diapositive.

---

## Vue d'ensemble des 5 présentations du TP

| Présentation | Titre | Statut | Périmètre principal |
| :--- | :--- | :--- | :--- |
| **Partie 1** | **Cadrage, Préparation locale & Connexion aux datasources** | Validé & Déployé (18 slides) | Contexte métier, prérequis machine, feuille de route, règle d'or non destructive, cartographie, génération & colonnes détaillées des 3 sources, setup local (`uv`, `.env`), connexions en lecture seule. |
| **Partie 2** | **Exploration, Nettoyage & Règles de rapprochement** | **Document courant** (12 slides) | Diagnostic notebook, hétérogénéité des formats, fonctions pures de normalisation, tokenisation des prénoms, matrice hybride `C1`–`C4`, verrou anti-conflit CIN, fuzzy matching adaptatif et gestion des foyers. |
| **Partie 3** | **Modélisation cible & Pipeline ETL en flux** | À rédiger ultérieurement | Schéma cible `tp_assurance_etl` (sans `uid` au départ), conservation du brut + colonnes canoniques + `details_metier` JSONB, extraction streaming + `COPY`, indexation de base. |
| **Partie 4** | **Ajout DDL `UID` & Moteur Union-Find** | À rédiger ultérieurement | Ajout de la colonne `uid`, structure `CompactUnionFind`, passes exactes `C1`–`C3`, passe floue par blocage `(date_naiss_norm, sexe_norm)`, routage vers la file humaine. |
| **Partie 5** | **Mini-application Web, Arbitrage humain & Audit** | À rédiger ultérieurement | Interface FastAPI (tableau de bord, recherche, fiche groupe `UID`, file de validation dont `SUSPICION_FAUTE_CIN`), tests `pytest` et métriques de réconciliation. |

---

## Détail des diapositives — Présentation 2 (12 slides)

---

### Slide 1 — Page de titre : Exploration, Nettoyage & Règles de Rapprochement

- **Bandeau haut** : `LICENCE INFORMATIQUE · TP DATA D.L.A`
- **Titre** : Exploration, Nettoyage & Règles de Rapprochement
- **Sous-titre** : Partie 2 / 5 — De la disparité des sources à la matrice d'attribution du référentiel unique (`UID`)
- **Objectif pédagogique** : Poser le thème de la séance : transformer des données hétérogènes et bruitées en un socle canonique comparable et établir des règles d'attribution déterministes.

#### Schéma conceptuel central
```text
[ Auto (PostgreSQL 16) ]     [ Life (MySQL 8.4) ]     [ Autre (Fichier CSV) ]
           \                         |                         /
            \                        |                        /
     [ Diagnostic dans le notebook : formats, absences & erreurs de saisie ]
                                     |
     [ Pipeline de normalisation canonique : fonctions pures testables ]
                                     |
     [ Matrice hiérarchique C1–C4 + Verrou strict anti-conflit de CIN ]
                                     v
           [ Socle prêt pour le moteur de réconciliation UID ]
```

#### Éléments clés de cadrage
- **Environnement de la séance** : Notebook Jupyter `notebooks/01_exploration.ipynb` et module de normalisation `src/tp_data_dla/normalisation.py`.
- **Démarche d'ingénieur** : Observer d'abord (profilage statistique), comprendre les écarts, spécifier les fonctions pures de nettoyage, puis formaliser les critères de décision avant d'écrire l'ETL.
- **Notes orateur** : Rappeler que dans un projet d'entreprise comme dans ce TP, aucune réconciliation ne fonctionne par un simple `JOIN` SQL direct. La phase d'observation et de normalisation conditionne l'exactitude du référentiel cible.

---

### Slide 2 — Feuille de route & Objectifs de l'étape 2

- **Bandeau haut** : `FEUILLE DE ROUTE · PARCOURS EN 5 ÉTAPES`
- **Titre** : Feuille de route du TP : cap sur l'étape 2
- **Sous-titre** : Comprendre les disparités pour bâtir une matrice de décision irréprochable
- **Objectif pédagogique** : Replacer la séance dans le déroulé global et fixer les 3 livrables concrets attendus à l'issue de cette session.

#### Diagramme séquentiel du TP
```text
[ 1. Préparation & Connexions ]  --> TERMINÉ (18 slides · Environnement & Sources prêts)
             |
             v
[ 2. Exploration & Règles ]      --> SESSION COURANTE
  ├── 2.1 Diagnostiquer : profils statistiques, formats, anomalies
  ├── 2.2 Normaliser   : module de fonctions pures (normalisation.py)
  └── 2.3 Formaliser   : matrice C1 à C4, tolérance floue & verrou CIN
             |
             v
[ 3. Schéma Cible & ETL Flux ]   --> Prochaine étape (Partie 3)
             |
             v
[ 4. Moteur Union-Find & UID ]   --> À venir (Partie 4)
             |
             v
[ 5. App Web & Audit Qualité ]   --> À venir (Partie 5)
```

#### Les 3 objectifs de la séance
1. **Diagnostiquer les hétérogénéités** : types SQL disparates, formats textuels, dates, diacritiques, casse et conventions par système.
2. **Implémenter les fonctions pures de normalisation** : transformation déterministe vers des colonnes canoniques comparables.
3. **Formaliser la matrice hiérarchique de rapprochement** : règles `C1` à `C4`, gestion des seuils flous et verrou absolu anti-conflit de CIN.
- **Notes orateur** : Insister sur la distinction : aujourd'hui, on ne charge pas encore la base cible définitive et on n'assigne pas encore les `UID`. On analyse, on nettoie et on formalise les règles du jeu.

---

### Slide 3 — Le choc des formats : comparaison des fiches brutes

- **Bandeau haut** : `DIAGNOSTIC DES SOURCES · HÉTÉROGÉNÉITÉ TECHNIQUE`
- **Titre** : Le choc des formats : comparaison des fiches brutes
- **Sous-titre** : Pourquoi aucun simple `JOIN` SQL direct n'est possible
- **Objectif pédagogique** : Visualiser l'extrême hétérogénéité technique entre les trois silos sur une même personne physique.

#### Tableau comparatif concret (exemple réel d'un même individu)

| Attribut | Auto (PostgreSQL 16) | Life (MySQL 8.4) | Autre (Fichier CSV) | Diagnostic immédiat |
| :--- | :--- | :--- | :--- | :--- |
| **Identifiant local** | `id_client_auto` = `1004521` | `ref_adherent` = `3004521` | `ref_fiche` = `'EXT-5004521'` | Espaces de clés totalement disjoints |
| **Pièce d'identité** | `numero_cin` = `'CIN- 800005316023'` | `cin_numerique` = `800005316023` | `piece_identite` = `'800005316023'` | Préfixe textuel vs nombre entier vs chaîne |
| **Nom de famille** | `nom_assure` = `' Ramanitra '` | `nom_adherent` = `'RAMANITRA'` | `patronyme` = `'Ramanitra'` | Espaces parasites, casse mixte |
| **Prénoms** | `prenoms_assure` = `'Faly Tahina'` | `prenoms_adherent` = `'FALY-TAHINA'` | `autres_noms` = `'Tahina Faly'` | Tirets, casse et inversion de l'ordre |
| **Date de naissance** | `ne_le` = `'1970-04-19'` (`DATE`) | `date_naiss` = `19700419` (`INT`) | `date_naissance` = `'19-04-1970'` (`TEXT`) | Date SQL vs Entier `YYYYMMDD` vs Texte français |
| **Téléphone** | `mobile` = `'00 95 397 11'` | `tel_contact` = `'+000009539711'` | `contact_tel` = `'00-95-397-11'` | Préfixe international fictif, tirets, espaces |
| **Sexe / Genre** | `sexe` = `'Masculin'` | `genre` = `1` | `code_sexe` = `'M'` | Libellé texte vs code binaire (`0/1`) vs code lettre |

#### Échec de la jointure directe (Boîte Terminal sombre `#1E293B`)
```sql
-- Tentative de jointure directe : résultat = 0 correspondance !
SELECT a.nom_assure, l.nom_adherent 
FROM tp_assurance.clients_auto a
JOIN tp_assurance_life.clients_life l 
  ON a.numero_cin = l.cin_numerique; -- Types incompatibles (TEXT vs BIGINT)
```
- **Notes orateur** : Montrer que même sur un attribut standardisé comme la date de naissance, on a 3 représentations incompatibles (`DATE`, `INT`, `TEXT`). Une phase de transformation intermédiaire est obligatoire.

---

### Slide 4 — Diagnostic des anomalies : les 4 familles de bruit du monde réel

- **Bandeau haut** : `DIAGNOSTIC DES SOURCES · BRUIT & ANOMALIES`
- **Titre** : Les 4 familles d'anomalies identifiées dans les sources
- **Sous-titre** : Pourquoi un nettoyage purement syntaxique ne suffit pas
- **Objectif pédagogique** : Comprendre la nature des bruits rencontrés en production (casse, diacritiques, manques, fautes de saisie et pièges relationnels).

#### Schéma en 4 cartes d'anomalies

```text
┌────────────────────────────────────────┐   ┌────────────────────────────────────────┐
│ 1. Écarts d'écriture & Casse           │   │ 2. Inversion & Séparateurs de prénoms  │
│ • Espaces multiples et trim            │   │ • Tirets vs espaces : 'FALY-TAHINA'    │
│ • Minuscules / Majuscules désordonnées │   │ • Ordre inversé : 'TAHINA FALY'        │
│ • Accents et diacritiques (é/e, etc.)  │   │ • Prénoms multiples asymétriques       │
└────────────────────────────────────────┘   └────────────────────────────────────────┘
                    ▲                                            ▲
                    │                                            │
┌────────────────────────────────────────┐   ┌────────────────────────────────────────┐
│ 3. Attributs absents (NULL / Vides)    │   │ 4. Fautes de frappe réalistes (~5 %)   │
│ • ~3 % à 5 % de lieux manquants        │   │ • Lettre substituée ou doublée         │
│ • Téléphone ou e-mail non renseigné    │   │ • Transposition de 2 lettres           │
│ • CIN manquant sur certains dossiers   │   │ • 1 chiffre erroné sur CIN/téléphone   │
└────────────────────────────────────────┘   └────────────────────────────────────────┘
```

#### Deux pièges relationnels majeurs à retenir
- **Homonymes parfaits** : Deux personnes physiques distinctes partageant le même nom, les mêmes prénoms et la même date de naissance, mais avec deux CIN différents.
- **Membres d'un même foyer** : Deux personnes physiques distinctes (ex. conjoints) partageant le même numéro de téléphone ou la même adresse de courriel.
- **Notes orateur** : Souligner l'importance des deux pièges : si un algorithme regroupe des personnes uniquement parce qu'elles ont le même téléphone ou la même date de naissance, il commet une faute métier grave en mélangeant les contrats d'un couple ou d'homonymes.

---

### Slide 5 — Le pipeline de normalisation canonique (Fonctions pures)

- **Bandeau haut** : `NORMALISATION · FONCTIONS PURES DÉTERMINISTES`
- **Titre** : Pipeline de normalisation canonique
- **Sous-titre** : Des fonctions pures, déterministes et sans effet de bord (`normalisation.py`)
- **Objectif pédagogique** : Structurer la couche de nettoyage sous forme d'une suite de fonctions unitaires testables produisant des colonnes canoniques.

#### Disposition en deux colonnes : Principe (Gauche) & Extrait de code (Droite)
- **Colonne gauche (Tableau des transformations canoniques)** :
  - `'CIN- 800005316023'` $\rightarrow$ `normaliser_cin()` $\rightarrow$ `'800005316023'` (`CHAR(12)`)
  - `'  Ramanitra  '` $\rightarrow$ `normaliser_nom()` $\rightarrow$ `'RAMANITRA'` (Majuscule, sans accent)
  - `'Faly-Tahina'` $\rightarrow$ `normaliser_prenoms()` $\rightarrow$ `'FALY TAHINA'` (Tokens triés)
  - `'19700419'` (`INT`) $\rightarrow$ `normaliser_date()` $\rightarrow$ `'1970-04-19'` (`DATE` ISO)
  - `'+000009539711'` $\rightarrow$ `normaliser_tel()` $\rightarrow$ `'009539711'` (9 chiffres `00XXXXXXX`)
  - `'Contact@Mail.MG'` $\rightarrow$ `normaliser_mail()` $\rightarrow$ `'contact@mail.mg'` (Minuscules)
  - `1` ou `'Masculin'` $\rightarrow$ `normaliser_sexe()` $\rightarrow$ `'M'` (`'M'` ou `'F'`)

- **Colonne droite (Boîte Terminal sombre `#1E293B`)** :
```python
# src/tp_data_dla/normalisation.py
def normaliser_nom(valeur: Any) -> Optional[str]:
    """Nettoie le patronyme : trim, sans accents, majuscules."""
    if not valeur:
        return None
    texte = supprimer_accents(str(valeur)).strip().upper()
    return RE_ESPACES.sub(" ", texte) or None

def normaliser_cin(valeur: Any) -> Optional[str]:
    """Extrait un CIN canonique sur 12 chiffres consécutifs."""
    if valeur is None:
        return None
    chiffres = RE_CHIFRES.sub("", str(valeur))
    return chiffres if len(chiffres) == 12 else None
```
- **Notes orateur** : Expliquer pourquoi nous conservons toujours la donnée brute dans la base cible et que nous ajoutons ces colonnes canoniques à côté. Cela respecte rigoureusement notre règle d'or non destructive.

---

### Slide 6 — Focus : la tokenisation et le tri des prénoms

- **Bandeau haut** : `NORMALISATION · GESTION DES PRÉNOMS COMPOSÉS`
- **Titre** : Le cas des prénoms : tokenisation et tri alphabétique
- **Sous-titre** : Comment absorber toutes les inversions d'ordre sans perte d'information
- **Objectif pédagogique** : Comprendre le fonctionnement de l'attribut `prenoms_trie_norm` pour réconcilier les variations d'ordre des prénoms composés.

#### Schéma du mécanisme de tokenisation

```text
       Source Auto (PostgreSQL)               Source Life (MySQL)                 Source Autre (CSV)
            'Faly Tahina'                        'FALY-TAHINA'                       'Tahina Faly'
                  │                                    │                                   │
                  ▼                                    ▼                                   ▼
          Nettoyage accents                    Remplacement '-'                    Nettoyage accents
           + Majuscules                           par espace                          + Majuscules
                  │                                    │                                   │
                  ▼                                    ▼                                   ▼
        Tokens : ['FALY', 'TAHINA']          Tokens : ['FALY', 'TAHINA']         Tokens : ['TAHINA', 'FALY']
                  │                                    │                                   │
                  └──────────────────┬─────────────────┴───────────────────┘
                                     ▼
                          Tri alphabétique des tokens
                                     │
                                     ▼
                     Forme canonique : 'FALY TAHINA'
```

#### Boîte de code (Terminal sombre `#1E293B`)
```python
# Découpage en tokens et tri alphabétique
tokens = [t for t in RE_ESPACES.split(texte) if t]
prenoms_norm = " ".join(tokens)             # 'TAHINA FALY' (ordre conservé)
prenoms_trie_norm = " ".join(sorted(tokens)) # 'FALY TAHINA' (forme pivot)
```
- **Notes orateur** : Signaler aux étudiants que cette règle simple résout à elle seule un très grand nombre de faux négatifs constatés dans les bases malgaches où l'ordre des prénoms varie fréquemment selon les agences ou habitudes de saisie.

---

### Slide 7 — La matrice de rapprochement hiérarchique (C1 à C4)

- **Bandeau haut** : `MOTEUR DE RÉCONCILIATION · MATRICE HIÉRARCHIQUE`
- **Titre** : La matrice hiérarchique de rapprochement
- **Sous-titre** : 4 niveaux de règles ordonnées par degré de certitude
- **Objectif pédagogique** : Présenter la matrice de décision régissant l'attribution automatique ou l'arbitrage humain.

#### Pyramide de décision

```text
  [ Règle C1 : CIN Identique (Certitude maximale) ]
  ├── cin_norm_a = cin_norm_b (valide et non NULL)
  └── Attribution automatique immédiate du même UID
        │ (si non concluant)
        ▼
  [ Règle C2 : État Civil Complet + Ville (Forte confiance) ]
  ├── nom_norm + prenoms_trie_norm + date_naiss_norm + lieu_naiss_norm + ville_norm
  └── Attribution automatique sous contrôle du verrou CIN
        │ (si non concluant)
        ▼
  [ Règle C3 : État Civil sans Ville (Confiance modérée) ]
  ├── nom_norm + prenoms_trie_norm + date_naiss_norm + lieu_naiss_norm (absorbe déménagement)
  └── Attribution automatique sous contrôle du verrou CIN
        │ (si non concluant)
        ▼
  [ Règle C4 : Coordonnées de Contact seules (Ambiguïté Foyer) ]
  ├── C4a (Identité + Tel) / C4b (Identité + Mail)
  └── ATTRIBUTION AUTOMATIQUE INTERDITE --> File de validation humaine
```

#### Tableau de synthèse des actions du moteur

| Règle | Critères obligatoires | Degré de certitude | Décision moteur | Motif traçabilité |
| :---: | :--- | :---: | :--- | :--- |
| **C1** | `cin_norm` identique et non nul | **Certitude absolue** | Attribution automatique du même `UID` | `PIVOT_CIN` |
| **C2** | Nom + Prénoms triés + Date naissance + Lieu + Ville | **Très élevé** | Attribution automatique si pas de conflit CIN | `ETAT_CIVIL_EXACT_VILLE` |
| **C3** | Nom + Prénoms triés + Date naissance + Lieu | **Élevé** | Attribution automatique si pas de conflit CIN | `ETAT_CIVIL_EXACT_DEMENAGEMENT` |
| **C4a / C4b** | Identité concordante + Téléphone OU E-mail | **Ambigu (foyer)** | **File humaine obligatoire** (suspicion foyer) | `SUSPICION_FOYER` |

- **Notes orateur** : Souligner la hiérarchie : on commence toujours par le critère le plus certain (`C1`). Ce n'est qu'en l'absence de CIN qu'on fait appel à l'état civil (`C2`, `C3`).

---

### Slide 8 — Le verrou absolu anti-conflit de CIN

- **Bandeau haut** : `INTÉGRITÉ ALGORITHMIQUE · SÉCURITÉ ABSOLUE`
- **Titre** : Le verrou algorithmique anti-conflit de CIN
- **Sous-titre** : Interdiction formelle de relier deux fiches aux CIN distincts
- **Objectif pédagogique** : Comprendre le rôle du verrou algorithmique pour empêcher la fusion d'homonymes parfaits.

#### Schéma logique du verrou anti-conflit

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

#### Étude de cas : le piège des homonymes
- **Fiche A (Auto)** : `'ANDRIANINA Mamy'`, né le `1985-06-12` à Antananarivo, CIN = `'101234567890'`
- **Fiche B (Life)** : `'ANDRIANINA Mamy'`, né le `1985-06-12` à Antananarivo, CIN = `'201987654321'`
- **Sans le verrou** : `C2` regroupe les deux fiches sous un même `UID` car l'état civil est rigoureusement identique. **Erreur métier catastrophique**.
- **Avec le verrou** : Le moteur détecte deux CIN valides différents, bloque la réunion, trace l'anomalie et préserve l'indépendance des deux personnes.
- **Notes orateur** : Insister fortement sur ce concept : un CIN valide est la vérité juridique absolue d'une personne physique à Madagascar. Deux CIN distincts = deux individus distincts, quel que soit leur degré de ressemblance d'état civil.

---

### Slide 9 — Tolérance aux erreurs de frappe : Fuzzy Matching adaptatif

- **Bandeau haut** : `ALGORITHMIQUE · RAPPROCHEMENT FLOU`
- **Titre** : Rapprochement flou adaptatif (Damerau-Levenshtein)
- **Sous-titre** : Pourquoi le texte tolère la distance 2 mais les nombres exigent la distance 1
- **Objectif pédagogique** : Définir la distance de Damerau-Levenshtein adaptée à la longueur des chaînes et formaliser la règle d'or sur les attributs numériques.

#### Schéma des seuils de tolérance selon la nature de la donnée

```text
  [ Textes alphabétiques (Nom, Prénoms) ]
  ├── Mots courts (< 9 caractères) : Distance max = 1
  │   └── Autorisé : 'HERY' <-> 'HERI' | Rejeté : 'HERY' <-> 'FALY' (distance 2 sur mot court)
  └── Mots longs (>= 9 caractères) : Distance max = 2
      └── Autorisé : 'ANDRIAMAHERY' <-> 'ANDRIAMAHARI' (distance 2 sur patronyme long)

  [ Nombres canoniques (CIN, Téléphone) ]
  ├── Règle absolue : Seuil max = 1 chiffre d'écart (JAMAIS >= 2)
  └── Pourquoi ? Les séries numériques consécutives génèrent des voisins à distance 2 :
      Exemple : '800000000083' vs '800000000010' (2 chiffres d'écart mais 2 personnes distinctes !)
```

#### Boîte de code (Terminal sombre `#1E293B`)
```python
# Distance de Damerau-Levenshtein adaptative (RapidFuzz)
min_len = min(len(s1), len(s2))
seuil_max = 2 if min_len >= 9 else 1

if abs(len(s1) - len(s2)) > seuil_max:
    return False # Écart de longueur excessif

dist = DamerauLevenshtein.distance(s1, s2, score_cutoff=seuil_max)
return dist <= seuil_max
```
- **Notes orateur** : Faire comprendre pourquoi autoriser une distance de 2 ou 3 sur les numéros de CIN provoquerait l'effondrement du graphe d'identités : des milliers d'inconnus se retrouveraient fusionnés ensemble.

---

### Slide 10 — L'arbitrage : décision automatique vs file humaine

- **Bandeau haut** : `ARBITRAGE MÉTIER · ROUTAGE DES DÉCISIONS`
- **Titre** : L'arbitrage : décision automatique vs file humaine
- **Sous-titre** : Savoir quand le moteur tranche seul et quand il sollicite l'opérateur
- **Objectif pédagogique** : Maîtriser le routage tripartite du moteur : attribution automatique, validation humaine guidée ou maintien séparé.

#### Diagramme de routage des décisions

```text
                           Candidat au rapprochement
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
  [ Branche Automatique ]    [ File de Validation ]      [ Branche Maintien / Rejet ]
  • C1 : CIN identique       • C4a / C4b (Foyers)        • CONFLIT_CIN (>= 2 chiffres)
  • C2 : État civil complet  • SUSPICION_FAUTE_CIN       • Incohérence majeure
  • C3 : Sans ville            (État civil concordant    • Homonymes avérés
  • C2/C3 Flou conforme        mais 1 chiffre d'écart)
            │                          │                          │
            ▼                          ▼                          ▼
      Attribution UID            Écran Arbitrage            Maintien fiches
     sans intervention             Gestionnaire               séparées
```

#### Les deux motifs isolés pour la validation humaine
1. **`SUSPICION_FOYER`** : Fiches partageant le même téléphone ou e-mail mais dont l'état civil n'est pas strictement identique (évite d'amalgamer les conjoints).
2. **`SUSPICION_FAUTE_CIN`** : Même état civil exact, mais un CIN diffère d'exactement 1 chiffre (faute de frappe probable de l'agent de saisie nécessitant vérification sur pièce justificative).
- **Notes orateur** : Présenter la file humaine comme une force du système et non une faiblesse : un bon système de réconciliation sait précisément délimiter ses certitudes et alerter un opérateur sur les cas ambigus plutôt que d'altérer la base.

---

### Slide 11 — Cas complexes : les 3 317 « ponts » de la cohorte commune

- **Bandeau haut** : `CAS COMPLEXES · TRANSITIVITÉ MULTI-SOURCES`
- **Titre** : Cas complexes : les 3 317 « ponts » de la cohorte commune
- **Sous-titre** : Comment relier deux dossiers sans attribut partagé direct
- **Objectif pédagogique** : Visualiser la résolution des cas sans intersection directe grâce aux fiches pivots et à la transitivité des regroupements.

#### Schéma du pont transitif entre les 3 sources

```text
  [ Dossier Auto ]                 [ Dossier Life ]                 [ Dossier Autre ]
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
               Transitivité : Dossier Auto <---> Dossier Life <---> Dossier Autre
                                                          │
                                                          ▼
                               Un seul et même individu physique identifié :
                                     Attribution d'un UID unique commun !
```

#### Propriétés remarquables
- En interrogeant uniquement Auto et Autre, aucun attribut de contact ou d'identité n'est commun : une jointure bipartite échoue.
- La présence du dossier Life sert de **pont** : la relation d'équivalence logique $A \sim B$ et $B \sim C \implies A \sim C$ résout l'énigme.
- C'est exactement cette logique transitive qui justifiera l'utilisation de la structure de données **Union-Find** en Partie 4.
- **Notes orateur** : Ce transparent montre pourquoi une simple succession de requêtes `UPDATE` ne peut pas résoudre les fusions en chaîne et pourquoi une structure de graphe (composantes connexes) s'impose.

---

### Slide 12 — Bilan & Teaser Partie 3 : Modélisation cible & Pipeline ETL

- **Bandeau haut** : `BILAN DE SÉANCE · PERSPECTIVES ÉTAPE 3`
- **Titre** : Bilan de la Partie 2 & Cap sur l'ETL
- **Sous-titre** : Nos règles sont prêtes, passons à l'ingestion industrielle
- **Objectif pédagogique** : Récapituler les acquis de la séance et poser les enjeux de la Partie 3 (modélisation de la base cible PostgreSQL et chargement en streaming).

#### Matrice des acquis de la Partie 2
```text
  ┌────────────────────────────────────────────────────────────────────────┐
  │                           ACQUIS DE LA SÉANCE 2                        │
  │  ✔ Profilage complet des 3 sources dans le notebook 01                 │
  │  ✔ Module normalisation.py opérationnel (fonctions pures testées)      │
  │  ✔ Matrice de rapprochement hiérarchique C1 à C4 formalisée            │
  │  ✔ Verrou absolu anti-conflit de CIN intégré à la logique décisionnelle│
  │  ✔ Règles de rapprochement flou adaptatif (Damerau-Levenshtein)        │
  └────────────────────────────────────────────────────────────────────────┘
```

#### Ce qui nous attend en Partie 3 (Aperçu)
- **Modélisation de la base cible** : création de la table consolidée `tp_assurance_etl.clients_consolides` dans PostgreSQL.
- **Règle d'or appliquée au schéma** : stockage simultané des valeurs brutes d'origine et des colonnes canoniques nettoyées, sans altération.
- **Détails métier préservés** : encapsulation des spécificités (immatriculation, formules, cultures, navires) dans une colonne `details_metier JSONB`.
- **Pipeline d'ingestion streaming** : extraction par curseur côté serveur, normalisation en vol et insertion ultra-rapide par protocole binaire `COPY`.
- **Notes orateur** : Féliciter les étudiants pour le travail d'analyse conceptuelle accompli. Annoncer que lors de la prochaine séance, nous passerons à l'ingestion des flux avec l'exécution du pipeline ETL sous Python.
