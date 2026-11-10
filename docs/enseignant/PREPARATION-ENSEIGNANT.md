# TP de rapprochement de fiches clients — Préparation enseignant

Ce guide décrit la procédure de préparation des bases de données et des jeux de données pour les séances de travaux pratiques.

> [!IMPORTANT]
> **Déploiement officiel : Jeu léger (400 000 fiches)**
> Afin de garantir une exécution réactive sur les ordinateurs des étudiants sans saturer la mémoire vive ni le processeur, les séances de TP s'appuient exclusivement sur la **version légère de 400 000 fiches**. Les scripts correspondants sont situés sous `sql/leger/`. Une version complète de référence (4 000 000 de fiches sous `sql/complet/`) est conservée pour les bancs de tests sur serveur dédié.

---

## 1. Préparer et charger Auto et Life

Préparer les deux bases **dédiées** avant le chargement. Utiliser les clients `psql` 16 et `mysql` 8.4 avec les paramètres de connexion de l’environnement du TP :
- **Auto** : PostgreSQL 16, base `tp_assurance_auto`, encodage `UTF-8`. Schéma créé : `tp_assurance.clients_auto`.
- **Life** : MySQL 8.4, base `tp_assurance_life`, encodage `utf8mb4`. Table créée : `tp_assurance_life.clients_life`.

### Commandes de chargement (Version légère 100 000 fiches par base)

Depuis la racine du projet, exécuter les scripts SQL dédiés :

```sh
# 1. Chargement Auto (PostgreSQL 16)
psql -X -d tp_assurance_auto -f sql/leger/charger_auto_postgresql.sql

# 2. Chargement Life (MySQL 8.4)
mysql --batch --skip-force --default-character-set=utf8mb4 \
  --database=tp_assurance_life < sql/leger/charger_life_mysql.sql
```

**Auto (PostgreSQL 16)** : Le script vérifie la version 16, le nom de la base et son encodage UTF-8. Il crée le schéma `tp_assurance` et charge la table dans une transaction unique en quelques secondes. Pour les étudiants, accorder les droits `CONNECT` sur la base, `USAGE` sur le schéma et `SELECT` sur la table.

**Life (MySQL 8.4)** : Le script vérifie la version 8.4, la base et l'encodage `utf8mb4`. La table InnoDB est créée et peuplée en une seule instruction `CREATE TABLE … SELECT` atomique. Pour les étudiants, accorder `SELECT` sur la table.

### Contrôle des volumes après chargement

```sh
psql -X -d tp_assurance_auto -c \
  'SELECT count(*), min(id_client_auto), max(id_client_auto) FROM tp_assurance.clients_auto;'
mysql --default-character-set=utf8mb4 --database=tp_assurance_life \
  --execute='SELECT count(*), min(ref_adherent), max(ref_adherent) FROM tp_assurance_life.clients_life;'
```

Résultats attendus :
- **Auto** : `100 000` fiches, plage `1 000 001` à `1 100 000`.
- **Life** : `100 000` fiches, plage `3 000 001` à `3 100 000`.

---

## 2. Générer ou reproduire la source Autre (CSV)

Le générateur utilise la bibliothèque standard Python et génère le fichier en flux sans dépendance externe :

```sh
# Génération de la version légère (200 000 fiches)
python3 scripts/generer_autre.py --mode leger --sortie data/clients_autre.csv
wc -l data/clients_autre.csv
```

La commande `wc -l` doit indiquer **200 001 lignes** (200 000 enregistrements + 1 ligne d'en-tête). Le fichier pèse environ 35 Mo en version légère (contre ~336 Mo en version complète).

---

## 3. Construction de la population (Version légère)

| Source | Fiches | Personnes distinctes | Communes aux trois | Propres à la source | Fiches supplémentaires (reprises 1 %) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| **Auto** | 100 000 | 99 000 | 70 000 | 29 000 | 1 000 |
| **Life** | 100 000 | 99 000 | 70 000 | 29 000 | 1 000 |
| **Autre** | 200 000 | 198 000 | 70 000 | 128 000 | 2 000 |
| **Total** | **400 000** | **256 000** | **70 000** | **186 000** | **4 000** |

### Principes du modèle déterministe
1. **Plages d'identifiants disjointes** : Auto utilise `1 000 001` à `1 100 000`, Life utilise `3 000 001` à `3 100 000`, Autre utilise `EXT-5000001` à `EXT-5200000`.
2. **Permutation pseudo-aléatoire sans doublon** : Chaque générateur utilise la formule de mélange linéaire `((numero - 1) × facteur + décalage) modulo volume + 1`. Les couples (facteur, décalage) sont (73, 41729) pour Auto, (137, 27183) pour Life et (193, 72821) pour Autre.
3. **Clés internes théoriques de population** :
   - Clés 1 à 70 000 : communes aux trois sources.
   - Clés 70 001 à 99 000 : exclusives à Auto (29 000).
   - Clés 99 001 à 128 000 : exclusives à Life (29 000).
   - Clés 128 001 à 256 000 : exclusives à Autre (128 000).
   - Les derniers rangs de chaque source rejouent 1 % de fiches existantes (70 % issues de la cohorte commune, 30 % de la cohorte exclusive).
4. **Cohérence du sexe** : L'empreinte SHA-256 sur `sexe:<cle>` détermine le code canonique (`M` si premier octet $\ge 128$, `F` sinon), assurant une cohérence absolue entre les trois sources pour une même personne physique.

---

## 4. Contrôle d'intersection hors base (Vérification enseignant)

Ce script autonome reconstruit les clés théoriques et vérifie l'exactitude des volumes et de l'intersection sur le jeu léger :

```python
import csv
from hashlib import sha256

def cle_personne(n, volume, facteur, decalage, initiales, reprises_communes, prive, commun):
    rang = ((n - 1) * facteur + decalage) % volume + 1
    if rang > initiales:
        rang -= initiales
        if rang > reprises_communes:
            rang += commun - reprises_communes
    return rang if rang <= commun else prive + rang - commun - 1

presence = bytearray(256_001)
auto = (100_000, 73, 41_729, 99_000, 700, 70_001, 70_000)
life = (100_000, 137, 27_183, 99_000, 700, 99_001, 70_000)
autre = (200_000, 193, 72_821, 198_000, 1_400, 128_001, 70_000)

for bit, params in ((1, auto), (2, life)):
    for n in range(1, params[0] + 1):
        presence[cle_personne(n, *params)] |= bit

with open("data/clients_autre.csv", encoding="utf-8", newline="") as fichier:
    for numero, fiche in enumerate(csv.DictReader(fichier, delimiter=";"), 1):
        reference = fiche["ref_fiche"]
        assert reference == f"EXT-{5_000_000 + numero}"
        n = int(reference.removeprefix("EXT-")) - 5_000_000
        cle = cle_personne(n, *autre)
        masculin = sha256(f"sexe:{cle}".encode("ascii")).digest()[0] >= 128
        assert fiche["code_sexe"] == ("M" if masculin else "F")
        presence[cle] |= 4

assert numero == 200_000
assert tuple(presence.count(bit) for bit in (1, 2, 4, 7)) == (
    29_000, 29_000, 128_000, 70_000,
)
print("Vérification réussie : 70 000 clés communes identifiées sur 256 000 personnes distinctes.")
```

---

## 5. Script d'évaluation automatique de la réconciliation

Pour évaluer les travaux des étudiants sur la base cible `tp_assurance_etl` :

```sh
uv run python scripts/evaluer_qualite.py
```

Le script détecte automatiquement le volume de la table `etl.fiches_clients` (mode léger 400k ou complet 4M) et calcule :
- Le taux de pureté des clusters UID (absence de faux positifs).
- Le taux de rappel sur les 70 000 clés communes (absence de faux négatifs).
- La résolution des 331 cas de transitivité indirecte ("ponts" `cle % 211 == 0`).
- La détection stricte des conflits de CIN (`cle % 113 == 0`).
