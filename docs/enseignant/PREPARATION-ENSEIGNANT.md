# TP de rapprochement de fiches clients — Préparation enseignant

Pour la phase de découverte, copier [l’énoncé](../etudiant/ENONCE-TP.md) à la
racine d’un dossier de distribution distinct, puis y placer
[le CSV](../../data/clients_autre.csv) sous `data/clients_autre.csv`. Fournir aussi les
accès en lecture aux deux bases. La notice, les scripts SQL, le générateur et les
références internes restent côté enseignant.

## Charger Auto et Life

Préparer les deux bases **dédiées** avant le chargement. Utiliser les clients
`psql` 16 et `mysql` 8.4, puis adapter les paramètres de connexion à
l’environnement du TP. Prévoir de l’espace serveur pour les tables, les index
et les journaux.

| Source | Base à préparer | Table créée | Droits de chargement |
| --- | --- | --- | --- |
| Auto | PostgreSQL 16, `tp_assurance_auto`, UTF-8 | `tp_assurance.clients_auto` dans la base | Connexion et `CREATE` sur la base pour créer le schéma. |
| Life | MySQL 8.4, `tp_assurance_life`, `utf8mb4` | `tp_assurance_life.clients_life`, qualifiée directement par la base | Connexion, `CREATE` et `INSERT` sur la base dédiée ou la cible. |

Depuis la racine du projet, lancer les commandes dans des sessions distinctes.

```sh
psql -X -d tp_assurance_auto -f sql/charger_auto_postgresql.sql
mysql --batch --skip-force --default-character-set=utf8mb4 \
  --database=tp_assurance_life < sql/charger_life_mysql.sql
```

**Auto.** Le script vérifie la version, le nom de la base et son encodage.
Il crée le schéma et charge la table dans une transaction. Une erreur,
un schéma déjà présent ou un volume différent du million attendu arrête
le chargement. En cas d’échec avant validation, corriger la cause et
relancer après avoir vérifié l’absence du schéma. Pour les étudiants,
accorder `CONNECT` sur la base, `USAGE` sur le schéma et `SELECT` sur
la table. [Documentation de psql 16](https://www.postgresql.org/docs/16/app-psql.html)

**Life.** Le script vérifie la version, la base sélectionnée, son encodage
et le format `ROW` si le journal binaire est activé. Garder le mode batch sans
`--force` pour que le client s’arrête dès la première erreur. La table
InnoDB est créée et remplie par une seule instruction `CREATE TABLE … SELECT`.
Cette instruction est atomique dans la configuration prévue et refuse une
cible existante. En cas d’échec ou de coupure, vérifier l’état de la cible
avant de relancer. Si la table est absente, corriger la cause et relancer.
Si elle est présente, contrôler le volume et la plage des références.
Conserver une table chargée. Si une cible préexistante est vide ou
incomplète, la faire examiner et, au besoin, archiver par l’administrateur
avant une relance. Pour les étudiants, accorder `SELECT` sur la table.
[DDL atomique MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/atomic-ddl.html) · [CREATE TABLE … SELECT](https://dev.mysql.com/doc/refman/8.4/en/create-table-select.html)

Après chargement, contrôler les volumes et les plages de références.

```sh
psql -X -d tp_assurance_auto -c \
  'SELECT count(*), min(id_client_auto), max(id_client_auto) FROM tp_assurance.clients_auto;'
mysql --default-character-set=utf8mb4 --database=tp_assurance_life \
  --execute='SELECT count(*), min(ref_adherent), max(ref_adherent) FROM tp_assurance_life.clients_life;'
```

Résultats attendus. Auto `1000000, 1000001, 2000000`. Life
`1000000, 3000001, 4000000`. Les références sont des clés primaires.

## Reproduire Autre

Le CSV livré pèse **352 670 246 octets** (environ 336 Mio). Le générateur demande
Python 3.9 ou supérieur et utilise la bibliothèque standard. Il écrit les fiches
au fil de la génération et publie le fichier complet en une seule opération.
Prévoir assez d’espace pour le fichier existant et sa nouvelle copie temporaire.

```sh
# Depuis la racine du projet. Réécrit le CSV livré.
python3 scripts/generer_autre.py
wc -l data/clients_autre.csv
shasum -a 256 data/clients_autre.csv
```

`--sortie chemin/clients_autre.csv` permet de choisir une autre destination
dans un dossier existant. Le CSV est en UTF-8, avec des fins de ligne LF,
un séparateur point-virgule et une ligne d’en-tête. Les valeurs manquantes
et celles non applicables sont des champs vides. Les superficies utilisent
la virgule décimale. Pour une lecture automatisée, conserver les références,
les CIN et les téléphones sous forme de texte.

## Construction de la population

| Source | Fiches | Personnes distinctes | Communes aux trois | Propres à la source | Fiches supplémentaires |
| --- | ---: | ---: | ---: | ---: | ---: |
| Auto | 1 000 000 | 990 000 | 700 000 | 290 000 | 10 000 |
| Life | 1 000 000 | 990 000 | 700 000 | 290 000 | 10 000 |
| Autre | 2 000 000 | 1 980 000 | 700 000 | 1 280 000 | 20 000 |

Une fiche supplémentaire concerne une personne déjà représentée dans la
source. Elle a sa propre référence et peut porter un autre dossier métier.
Le recoupement entre deux sources est constitué de la cohorte commune aux
trois. Le TP comprend donc 2 560 000 personnes distinctes par construction.

1. Les références locales suivent trois plages distinctes. Auto utilise
   1000001 à 2000000, Life 3000001 à 4000000 et Autre `EXT-5000001` à
   `EXT-7000000`.
2. Chaque générateur part d’un compteur et permute les rangs avec la formule
   `((compteur - 1) × facteur + décalage) modulo volume + 1`. Le facteur
   est premier avec le volume, donc chaque rang apparaît exactement une fois.
   Les couples facteur et décalage sont (73, 41729) pour Auto, (137, 27183)
   pour Life et (193, 72821) pour Autre.
3. Le rang permuté sélectionne une clé interne. Les clés 1 à 700000 sont
   partagées. Les plages exclusives sont 700001 à 990000 pour Auto,
   990001 à 1280000 pour Life et 1280001 à 2560000 pour Autre. Les derniers
   rangs de chaque source rejouent 1 % de son volume, à raison de 70 % de
   reprises dans la cohorte commune et 30 % dans la cohorte exclusive.
4. Les mêmes listes et formules déterministes produisent le profil de départ
   à partir de la clé interne. Chaque source applique ensuite ses propres
   formats et variations. Seule la référence locale est publiée comme
   identifiant de fiche. La clé de génération est interne aux scripts.

Les choix pédagogiques incluent des variantes de casse, d’accents, de
ponctuation et d’ordre des prénoms, des lieux ou contacts manquants, et
quelques changements de ville ou de CIN entre sources. Des personnes
distinctes peuvent partager un état civil ou un téléphone. Une partie de la
cohorte commune présente un lien par téléphone entre Auto et Life, puis
par e-mail entre Life et Autre, avec des champs de contact absents ailleurs.
Les CIN et téléphones utilisent des séries fictives. Auto préfixe la CIN
par `CIN-` suivi d’une espace, Life la stocke en entier et Autre en texte
chiffré. L’e-mail associe le premier prénom et le nom du profil en ASCII à
un suffixe de sept chiffres et à un domaine fictif `courrier-ile.test` ou
`boite-mada.test`. Pour une même clé, le domaine et le suffixe restent
identiques. La casse varie selon les sources. Les personnes et dossiers
sont synthétiques.

### Encodage du sexe

Les trois champs représentent le même attribut fictif. Auto utilise
`sexe` avec `Masculin` ou `Féminin`. Life utilise `genre` avec `0`
pour féminin ou `1` pour masculin. Autre utilise `code_sexe` avec
`M` pour masculin ou `F` pour féminin. Le champ est renseigné dans
chaque fiche et figure en dernière position.

Les scripts calculent SHA-256 sur `sexe:` suivi de la clé de personne
en chiffres. Un premier octet inférieur à 128 donne le code féminin.
À partir de 128, le code est masculin. Le calcul repose uniquement
sur la clé partagée, indépendamment des prénoms, des références de
fiche, des reprises, des secteurs et des produits. [Fonctions binaires PostgreSQL 16](https://www.postgresql.org/docs/16/functions-binarystring.html) · [SHA2 dans MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/encryption-functions.html)

### Vérifier l’intersection hors base

Ce contrôle enseignant reconstruit une clé de personne à partir de chaque
référence locale. Pour Auto et Life, les références sont énumérées par
construction à partir des paramètres des scripts SQL. Pour Autre, elles
sont lues dans le CSV. Les trois ensembles sont codés par les bits 1, 2 et 4.
Une clé marquée 7 appartient aux trois ensembles, quel que soit le nombre
de fiches qui la portent.

```python
import csv
from hashlib import sha256

def cle_personne(n, volume, facteur, decalage, initiales, reprises_communes, prive):
    rang = ((n - 1) * facteur + decalage) % volume + 1
    if rang > initiales:
        rang -= initiales
        if rang > reprises_communes:
            rang += 700_000 - reprises_communes
    return rang if rang <= 700_000 else prive + rang - 700_001

presence = bytearray(2_560_001)
auto = (1_000_000, 73, 41_729, 990_000, 7_000, 700_001)
life = (1_000_000, 137, 27_183, 990_000, 7_000, 990_001)
autre = (2_000_000, 193, 72_821, 1_980_000, 14_000, 1_280_001)
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
assert numero == 2_000_000
assert tuple(presence.count(bit) for bit in (1, 2, 4, 7)) == (
    290_000, 290_000, 1_280_000, 700_000,
)
print(presence.count(7))
```

Après chargement, on peut remplacer les deux boucles d’énumération par des
lectures des références réelles en base. Soustraire 1 000 000 à
`id_client_auto` et 3 000 000 à `ref_adherent` avant de calculer la clé.
Les clés de personne du modèle sont distinctes des CIN, des e-mails et des
références de fiche. Ce contrôle reste côté enseignant.

## Repères du scénario malgache

Les trois sources combinent des listes de noms et de prénoms à consonance
malgache et dix localités réelles, dont Sambava et Ambatondrazaka. Les
associations entre identité, état civil, coordonnées et dossiers sont générées
pour le TP. Les fréquences découlent de la génération et servent aux
comptages de l’exercice. [Communes urbaines de Madagascar, INSTAT](https://instat.mg/documents/upload/main/INSTAT-RGPH%203_PopulationPrecarite%20ResidentielleMilieuUrbain_Fev.2022.pdf)

Les champs métier sont associés aux dossiers. Dans Auto, la formule dépend de
l’année du véhicule. Dans Life, la cotisation en ariary dépend du produit et
l’adhésion intervient à l’âge adulte. Les montants sont fixés pour l’exercice.
[Banky Foiben’i Madagasikara](https://www.banky-foibe.mg/politique-monetaire-de-change)

Autre comprend des dossiers de riz, maïs, manioc, vanille et girofle, associés
à des risques météo dans le scénario. Le port d’attache est Toamasina,
Mahajanga, Toliara ou Antsiranana. La garantie cargaison est réservée aux
caboteurs dans le jeu. [Productions végétales, INSTAT](https://www.instat.mg/documents/upload/main/INSTAT_jas09_Oct%202010.pdf) · [Ports malgaches, APMF](https://apmf.mg/en/node/74)

## Contrôles réalisés et attentes

- **CSV livré.** Comparaison en flux des 2 000 000 fiches avec la version
  précédente. Les 16 colonnes existantes sont identiques octet par octet.
  Les 2 000 000 valeurs de la nouvelle colonne sont renseignées et
  correspondent au code attendu pour chaque clé reconstruite.
  Le fichier comporte 2 000 001 lignes physiques, en-tête inclus.
- **Secteurs.** 1 000 000 de fiches agricoles et 1 000 000 de fiches maritimes.
  Le secteur agricole compte 500 662 codes `M` et 499 338 codes `F`.
  Le secteur maritime compte 500 829 codes `M` et 499 171 codes `F`.
  Les champs applicables sont renseignés et ceux de l’autre secteur sont
  vides. Les superficies vont de 0,50 à 15,50 ha. Les cinq cultures,
  les quatre ports, les dix couples culture–garantie et les sept couples
  navire–garantie ont été vérifiés.
- **Chevauchement hors bases.** Intersection calculée avec les paramètres
  des deux scripts SQL et les références effectivement lues dans le CSV.
  Résultat de 700 000 clés communes et 2 560 000 distinctes au total.
  Après décodage, les valeurs de sexe concordent pour les 700 000 clés
  communes. Elles restent identiques sur les 10 000 reprises d’Auto,
  les 10 000 de Life et les 20 000 d’Autre.
  La cohorte commune inclut 3 317 cas à lien indirect prévus par les
  masques de génération.
- **SQL.** Contrôles statiques hors serveur du chargement PostgreSQL 16,
  de la création et du chargement MySQL 8.4, des colonnes, des volumes
  construits et des listes partagées. Aucune connexion aux bases ni
  exécution SQL. Les volumes et les formats Auto et Life sont des
  résultats attendus après chargement.

Empreinte SHA-256 du CSV livré

```text
1baf5d2fca1bb83c915dc1d2df169c5f78f680e8e3d8602f5a5846b6fd66afde
```
