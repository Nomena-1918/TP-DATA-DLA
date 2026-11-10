# TP de rapprochement de fiches clients — Découverte des sources

## Contexte

Ce scénario fictif s’inspire du fonctionnement des compagnies d’assurance à
Madagascar. Une personne peut souscrire une assurance auto, ouvrir un contrat
d’assurance vie ou de retraite, ou déposer un dossier sur une plateforme
agricole ou maritime.

Chaque application lui attribue sa propre référence. Selon l’application, les
informations peuvent être présentées différemment, être incomplètes ou avoir changé.

À terme, le projet devra relier les fiches qui concernent une même personne et
leur attribuer un identifiant commun (UID). Les fiches d’origine doivent rester
consultables avec leur référence et leurs valeurs. Les personnes, leurs
coordonnées et leurs dossiers sont fictifs. Les lieux cités sont réels.

## Les sources à explorer

| Source | Activité | Support fourni pour le TP | Nombre de fiches |
| --- | --- | --- | ---: |
| Auto | Assurance automobile | PostgreSQL 16, base `tp_assurance_auto`, table `tp_assurance.clients_auto` | 1 000 000 |
| Life | Assurance vie et retraite | MySQL 8.4, base `tp_assurance_life`, table `tp_assurance_life.clients_life` | 1 000 000 |
| Autre | Plateformes agricole et maritime | `data/clients_autre.csv`, UTF-8, séparateur point-virgule, une ligne d’en-tête | 2 000 000 |

Les volumes comptent les fiches. Plusieurs fiches peuvent concerner une seule
personne, y compris au sein d’une source. Pour explorer les données, commencez
par un échantillon de chaque source et utilisez des comptages pour confirmer
les volumes complets.

### Informations communes

| Information | Auto | Life | Autre |
| --- | --- | --- | --- |
| Référence locale | `id_client_auto`, entier | `ref_adherent`, entier | `ref_fiche`, texte préfixé |
| CIN fictive | `numero_cin`, texte avec le préfixe `CIN-` suivi d’une espace et de 12 chiffres | `cin_numerique`, entier `BIGINT` | `piece_identite`, texte de 12 chiffres |
| Nom | `nom_assure` | `nom_adherent` | `patronyme` |
| Prénoms | `prenoms_assure` | `prenoms_adherent` | `autres_noms` |
| Date de naissance | `ne_le`, type `date` | `date_naiss`, entier `AAAAMMJJ` | `date_naissance`, texte `JJ-MM-AAAA` |
| Lieu de naissance | `ne_a` | `lieu_naiss` | `commune_origine` |
| Ville de résidence | `ville_residence` | `commune_domicile` | `localite` |
| Téléphone fictif | `mobile`, groupes séparés par des espaces | `tel_contact`, texte avec préfixe de test | `contact_tel`, groupes séparés par des tirets |
| E-mail fictif | `courriel` | `email_contact` | `contact_mail` |
| Sexe | `sexe`, texte `Masculin` ou `Féminin` | `genre`, entier `0` pour féminin ou `1` pour masculin | `code_sexe`, texte `M` pour masculin ou `F` pour féminin |

Le champ `genre` de Life représente le même attribut fictif que les deux autres
champs de sexe.

### Informations propres à chaque source

| Source | Champs métier |
| --- | --- |
| Auto | `immatriculation` (référence véhicule fictive), `annee_vehicule`, `formule_auto` |
| Life | `produit`, `cotisation_mensuelle_ar` (en ariary), `date_adhesion` (type `date`) |
| Autre, agricole | `plateforme` vaut `AGRICOLE`. `culture`, `superficie_ha` (en hectares, virgule décimale) et `garantie_agricole` (risque couvert, par exemple sécheresse). |
| Autre, maritime | `plateforme` vaut `MARITIME`. `type_navire`, `port_attache` (port malgache) et `garantie_maritime` (par exemple corps de navire ou cargaison). |

Dans Autre, les champs propres à l’autre secteur sont vides. Les garanties du
jeu servent à comparer les dossiers et leurs expositions dans le scénario du TP.

## Travail demandé pour cette première partie

Ouvrez `notebooks/01_exploration.ipynb`. Commencez en mode rapide,
puis activez le profil complet pour vérifier les volumes et les absences.

1. Relevez le volume et la structure de chaque source. Indiquez comment
   chaque application identifie ses propres fiches.
2. Comparez les champs communs sur des échantillons. Relevez les différences
   de types, de formats et de valeurs manquantes, puis notez lesquelles devront
   être traitées avant de comparer les fiches.
3. Vérifiez à quoi servent les champs métier et dans quels cas ils sont
   renseignés. Pour Autre, observez des fiches des deux plateformes.
4. Remettez une courte fiche de découverte avec votre tableau de comparaison
   et quelques exemples observés. Conservez les sources brutes.

## Suite du TP

1. **Découvrir les sources** et rendre la fiche de découverte.
2. **Définir les règles de rapprochement** dans un second temps, à partir des
   observations.
3. **Réaliser l’ETL** pour extraire les fiches, préparer les données comparables
   et les charger en conservant leur provenance.
4. **Créer manuellement la colonne UID** dans la cible de travail.
5. **Utiliser Union-Find** pour regrouper les fiches reliées, traiter les doublons
   et attribuer un UID à chaque groupe.
6. **Réaliser la mini-application de visualisation** en toute fin pour explorer
   les groupes et consulter leurs fiches sources.
