# Règles de rapprochement d'identités — Référentiel NEW_ID (TP DATA D.L.A)

## 1. Principes directeurs d'architecture (Assurances ARO)

Conformément au dossier d'architecture DSI BICI Consulting pour Assurances ARO :
1. **Unicité métier** : Un même client physique = Un même `NEW_ID` (`uid` au format UUID) dans toutes les bases.
2. **Zéro suppression** : Aucun `DELETE` sur les lignes historiques. Toutes les fiches sources restent intactes.
3. **Zéro altération** : Aucun `UPDATE` sur les colonnes existantes d'origine. Seule la colonne `uid` est renseignée.
4. **Verrou algorithmique strict anti-conflit de CIN** : Deux CIN valides et distincts interdisent formellement l'attribution du même `uid`.
5. **Protection des foyers (Cas ambigus C4a/C4b à 50 %)** : L'attribution automatique d'un même `uid` est interdite sur la simple base du téléphone ou de l'e-mail avec nom. Ces cas sont isolés en file de validation humaine.

---

## 2. Fonctions de normalisation des données comparables

Avant toute comparaison, les valeurs sources sont converties vers des colonnes canoniques :

1. **CIN (`cin_norm`)** :
   - Extraction des 12 chiffres consécutifs.
   - Suppression des préfixes textuels (`CIN- `, etc.).
   - Format de sortie : chaîne `CHAR(12)` ou `NULL` si absent ou invalide.
2. **Nom (`nom_norm`)** :
   - Décomposition Unicode NFKD pour retirer les accents et diacritiques (ex: `é` -> `e`).
   - Suppression des espaces en début/fin et espaces multiples (`trim`).
   - Passage en majuscules.
3. **Prénoms triés (`prenoms_trie_norm`)** :
   - Nettoyage des diacritiques et passage en majuscules.
   - Remplacement des tirets `-` par des espaces.
   - Découpage en tokens (mots) et tri alphabétique.
   - *Exemple* : `'Faly-Tahina'`, `'Tahina Faly'` et `'Faly Tahina'` produisent tous `'FALY TAHINA'`.
4. **Date de naissance (`date_naiss_norm`)** :
   - Parsing des formats hétérogènes (`YYYY-MM-DD`, `YYYYMMDD`, `DD-MM-YYYY`).
   - Format de sortie : `DATE` ISO (`YYYY-MM-DD`) ou `NULL`.
5. **Lieu de naissance (`lieu_naiss_norm`) et Ville (`ville_norm`)** :
   - Nettoyage des accents, suppression des espaces, majuscules.
6. **Téléphone (`tel_norm`)** :
   - Suppression des espaces, tirets et préfixe international fictif `+000`.
   - Format de sortie : chaîne canonique de 9 chiffres `00XXXXXXX` ou `NULL`.
7. **Courriel (`mail_norm`)** :
   - Suppression des espaces et conversion en minuscules.
8. **Sexe (`sexe_norm`)** :
   - Conversion vers `'M'` (Masculin, 1, M) ou `'F'` (Féminin, 0, F).

---

## 3. Matrice hiérarchique de rapprochement (C1 – C4)

| Niveau | Règle | Critère de comparaison | Poids / Confiance | Action dans le moteur |
| :---: | :---: | :--- | :---: | :--- |
| **C1** | `CIN` identique | `cin_norm IS NOT NULL AND cin_norm_a = cin_norm_b` | **100 %** | **Attribution du même `uid`** (automatique). |
| **C2** | État civil complet + Ville | `nom_norm` + `prenoms_trie_norm` + `date_naiss_norm` + `lieu_naiss_norm` + `ville_norm` | **80 %** | **Attribution du même `uid`** sous contrôle strict du verrou anti-conflit CIN. |
| **C3** | État civil sans Ville | `nom_norm` + `prenoms_trie_norm` + `date_naiss_norm` + `lieu_naiss_norm` | **60 %** | **Attribution du même `uid`** sous contrôle strict du verrou anti-conflit CIN (absorbe les déménagements). |
| **C2/C3 FLOU** | Rapprochement tolérant aux fautes de frappe | Blocage `(date_naiss_norm, sexe_norm)` + Damerau-Levenshtein adaptatif ($\le 1$ sur mots courts, $\le 2$ si $\ge 9$ car.) | **70 % – 75 %** | **Attribution du même `uid`** si absence de CIN contradictoire ; **File de validation** (`SUSPICION_FAUTE_CIN`) si 1 chiffre d'écart sur CIN valide. |
| **C4a** | Identité + Téléphone | `nom_norm` + `prenoms_trie_norm` + `tel_norm` | **50 %** | **File de validation humaine** (`A_VALIDER`). Pas d'attribution automatique. |
| **C4b** | Identité + E-mail | `nom_norm` + `prenoms_trie_norm` + `mail_norm` | **50 %** | **File de validation humaine** (`A_VALIDER`). Pas d'attribution automatique. |

---

## 4. Tolérance aux fautes de frappe et Gestion des nombres (Fuzzy Matching)

Dans les données du monde réel comme dans nos jeux de données récents, environ 5 % des enregistrements comportent des coquilles (lettre ou chiffre manquant, caractère doublé, permutation de deux lettres adjacentes, substitution).

### A. Distance de Damerau-Levenshtein adaptative
La distance prend en compte les suppressions, insertions, substitutions et transpositions de caractères adjacents. Le seuil de tolérance s'adapte à la taille des termes :
- **Mots courts (< 9 caractères)** : Distance maximale autorisée = **1** (pour éviter de confondre des prénoms distincts comme `AINA` et `TIANA`, ou `HERY` et `FALY`).
- **Mots longs ($\ge 9$ caractères)** : Distance maximale autorisée = **2** (absorbe des coquilles comme `ANDRIAMAHERY` $\leftrightarrow$ `ANDRIAMAHARI`).
- **Prénoms composés** : Tolérance combinée respectant les inversions d'ordre de prénoms (ex: `TAHIRY HERY` $\leftrightarrow$ `HERY TAHIRYY`).

### B. Gestion stricte des nombres (CIN et Téléphone) : Pourquoi distance 1 et JAMAIS 2 ou 3 ?
Les identifiants numériques suivent souvent des séries consécutives ou des clés modulaires (`cle % 101 == 0`). Dans les bases de données d'assurance :
- Deux personnes distinctes générées de manière consécutive diffèrent souvent de seulement 2 ou 3 chiffres sur leur CIN ou leur numéro de téléphone (ex: `800000000083` vs `800000000010` : 2 chiffres d'écart, ou avec retenue 3 chiffres).
- Autoriser une distance $\ge 2$ sur les nombres provoquerait des collisions massives (faux positifs destructeurs) entre individus différents.
- **Règle absolue sur les nombres** :
  1. Si un CIN est malformé (11 ou 13 chiffres) : il est conservé dans `cin_chiffres` et comparé à distance $\le 1$.
  2. Si deux fiches ont deux CIN valides de 12 chiffres qui diffèrent d'**exactement 1 chiffre** (`dl == 1`) avec un état civil concordant : le cas est orienté vers la file de validation humaine avec le motif explicite **`SUSPICION_FAUTE_CIN`** (score 75 %) sans union aveugle.
  3. Tout écart $\ge 2$ chiffres sur des CIN renseignés est traité comme un **`CONFLIT_CIN`** strict (score 0 %).

---

## 4. Algorithme du verrou anti-conflit CIN

Dans la structure Union-Find :
- Chaque représentant de composante connexe $R$ maintient l'identifiant $CIN(R)$ de la composante (s'il en existe un).
- Pour toute tentative de réunion entre deux composantes $R_A$ et $R_B$ via les règles C2 ou C3 :
  - Si $CIN(R_A) \neq \text{NULL}$ et $CIN(R_B) \neq \text{NULL}$ et $CIN(R_A) \neq CIN(R_B)$ :
    - L'attribution du même `uid` est **interdite**.
    - Un enregistrement de conflit est créé dans `etl.file_validation` avec le motif `'CONFLIT_CIN'`.
  - Sinon :
    - Les deux composantes reçoivent le même représentant.
    - $CIN(R_{nouveau}) = CIN(R_A) \lor CIN(R_B)$.

---

## 5. Résolution des cas indirects (3 317 ponts de la cohorte commune)

Dans le jeu de données, 3 317 personnes ont été générées avec un schéma de diffusion d'attributs complémentaires :
- **Auto** possède `CIN` et `TEL` (sans `MAIL`).
- **Life** possède `TEL` et `MAIL` (sans `CIN`).
- **Autre** possède `MAIL` (sans `CIN` ni `TEL`).

Lorsque le lieu de naissance est renseigné, ces fiches se rejoignent directement via la règle **C2** ou **C3**.
Lorsque le lieu de naissance est manquant ou altéré, Auto et Life partagent `(NOM, PRENOMS, TEL)` et Life et Autre partagent `(NOM, PRENOMS, MAIL)`. La transitivité d'Union-Find et la file de validation humaine garantissent que le gestionnaire peut visualiser ce chaînage et confirmer l'attribution du même `uid` sans ambiguïté.
