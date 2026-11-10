-- Depuis la racine : mysql --batch --skip-force --default-character-set=utf8mb4
--     --database=tp_assurance_life < sql/charger_life_mysql.sql
-- MySQL 8.4, base dédiée préexistante. Voir docs/enseignant/PREPARATION-ENSEIGNANT.md.
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;
SET SESSION sql_mode = 'STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION';

-- En mode batch sans --force, un identifiant inconnu arrête le script avant le DDL.
SET @garde_life = CASE
    WHEN VERSION() NOT LIKE '8.4.%' THEN 'SELECT `MySQL 8.4 requis`'
    WHEN NOT (CAST(DATABASE() AS BINARY) <=> 'tp_assurance_life')
        THEN 'SELECT `Selectionner la base tp_assurance_life`'
    WHEN @@SESSION.character_set_database <> 'utf8mb4'
        THEN 'SELECT `Encodage utf8mb4 requis pour la base`'
    WHEN @@GLOBAL.log_bin AND @@SESSION.binlog_format <> 'ROW'
        THEN 'SELECT `Format de journalisation ROW requis`'
    ELSE 'DO 0'
END;
PREPARE garde_life FROM @garde_life;
EXECUTE garde_life;
DEALLOCATE PREPARE garde_life;

-- Une instruction InnoDB crée et remplit la table. Une cible existante fait échouer
-- la création. Le nom qualifié limite l’écriture à la base dédiée.
CREATE TABLE tp_assurance_life.clients_life (
    ref_adherent BIGINT NOT NULL PRIMARY KEY,
    cin_numerique BIGINT,
    nom_adherent TEXT NOT NULL,
    prenoms_adherent TEXT NOT NULL,
    date_naiss INT NOT NULL,
    lieu_naiss TEXT,
    commune_domicile TEXT NOT NULL,
    tel_contact TEXT,
    email_contact TEXT,
    produit TEXT NOT NULL,
    cotisation_mensuelle_ar INT NOT NULL,
    date_adhesion DATE NOT NULL,
    genre TINYINT NOT NULL CHECK (genre IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs
AS
WITH chiffres (chiffre) AS (
    SELECT 0 UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
    UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9
), blocs AS (
    SELECT 10 * dizaines.chiffre + unites.chiffre AS valeur
    FROM chiffres AS dizaines CROSS JOIN chiffres AS unites
), numeros AS (
    SELECT CAST(1 + haut.valeur * 10000 + milieu.valeur * 100 + bas.valeur AS SIGNED) AS numero
    FROM blocs AS haut CROSS JOIN blocs AS milieu CROSS JOIN blocs AS bas
), rangs AS (
    SELECT
        3000000 + numero AS id_local,
        MOD((numero - 1) * 137 + 27183, 1000000) + 1 AS rang
    FROM numeros
), reprises AS (
    SELECT
        id_local,
        rang > 990000 AS reprise,
        CASE
            WHEN rang <= 990000 THEN rang
            WHEN rang <= 997000 THEN rang - 990000
            ELSE 700000 + rang - 997000
        END AS rang_initial
    FROM rangs
), cles AS (
    SELECT
        id_local,
        reprise,
        CASE
            WHEN rang_initial <= 700000 THEN rang_initial
            ELSE 990001 + rang_initial - 700001
        END AS cle
    FROM reprises
), calculs AS (
    SELECT
        id_local,
        cle,
        cle + 6 + 7 * reprise AS signal_fiche,
        MOD(cle, 211) = 0 AS pont,
        MOD((cle - (MOD(cle, 101) = 0)) * 131071 + 12345, 67108864) AS mix,
        cle - (MOD(cle, 67) = 0) AS contact
    FROM cles
), villes (rang_ville, nom_ville) AS (
    SELECT 0, 'Antananarivo' UNION ALL SELECT 1, 'Toamasina'
    UNION ALL SELECT 2, 'Antsirabe' UNION ALL SELECT 3, 'Mahajanga'
    UNION ALL SELECT 4, 'Fianarantsoa' UNION ALL SELECT 5, 'Toliara'
    UNION ALL SELECT 6, 'Antsiranana' UNION ALL SELECT 7, 'Morondava'
    UNION ALL SELECT 8, 'Sambava' UNION ALL SELECT 9, 'Ambatondrazaka'
), dossiers AS (
    SELECT
        id_local,
        cle,
        signal_fiche,
        pont,
        800000000000 + MOD(cle * 73 + 17, 10000000) AS cin,
        ELT(MOD(mix, 16) + 1,
            'Ravélo', 'Andriamahery', 'Rakotomalala', 'Ramanitra',
            'Razafindrano', 'Rasoatina', 'Randriavola', 'Raharisoa',
            'Ranaivo', 'Ravelomanana', 'Andriatsiry', 'Ratsimandresy',
            'Rabemanga', 'Rafaraléo', 'Rajaonina', 'Rasolofo'
        ) AS nom,
        ELT(MOD(mix DIV 16, 16) + 1,
            'Mialy', 'Tiana', 'Aina', 'Miora', 'Lova', 'Fara', 'Tahiry', 'Avotra',
            'Nirina', 'Hasina', 'Noé', 'Léa', 'Tahina', 'Feno', 'Sitraka', 'Valisoa'
        ) AS prenom,
        ELT(MOD(mix DIV 256, 16) + 1,
            'Hery', 'Soa', 'Rija', 'Faly', 'Nivo', 'Kanto', 'Voary', 'Zo',
            'Kolo', 'Tojo', 'Miary', 'Lanto', 'Tsiory', 'Haja', 'Mamy', 'Fanja'
        ) AS second_prenom,
        DATE_ADD(DATE '1960-01-01', INTERVAL (mix DIV 4096) DAY) AS naissance,
        lieu.nom_ville AS lieu,
        domicile.nom_ville AS ville,
        CONCAT('00', LPAD(MOD(contact * 131 + 29, 10000000), 7, '0')) AS telephone,
        MOD(id_local, 2) = 0 AS retraite
    FROM calculs
    JOIN villes AS lieu ON lieu.rang_ville = MOD(mix DIV 65536, 10)
    JOIN villes AS domicile
        ON domicile.rang_ville = MOD(cle * 37 DIV 13 + IF(MOD(signal_fiche, 53) = 0, 3, 0), 10)
)
SELECT
    id_local AS ref_adherent,
    CASE
        WHEN pont OR MOD(signal_fiche, 13) = 0 THEN NULL
        WHEN MOD(cle, 113) = 0 THEN cin + 10000000
        WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 3 AND MOD(id_local DIV 100, 3) = 0 THEN cin DIV 10
        WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 3 AND MOD(id_local DIV 100, 3) = 1 THEN cin * 10 + 7
        WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 3 AND MOD(id_local DIV 100, 3) = 2 THEN cin + 5
        ELSE cin
    END AS cin_numerique,
    CASE
        WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 0 AND MOD(id_local DIV 100, 3) = 0 THEN
            CONCAT(SUBSTRING(UPPER(REPLACE(nom, 'é', 'e')), 1, 2), SUBSTRING(UPPER(REPLACE(nom, 'é', 'e')), 4))
        WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 0 AND MOD(id_local DIV 100, 3) = 1 THEN
            CONCAT(SUBSTRING(UPPER(REPLACE(nom, 'é', 'e')), 1, 3), SUBSTRING(UPPER(REPLACE(nom, 'é', 'e')), 3, 1), SUBSTRING(UPPER(REPLACE(nom, 'é', 'e')), 4))
        WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 0 AND MOD(id_local DIV 100, 3) = 2 THEN
            CONCAT(SUBSTRING(UPPER(REPLACE(nom, 'é', 'e')), 1, 2), IF(SUBSTRING(UPPER(REPLACE(nom, 'é', 'e')), 3, 1) = 'A', 'E', 'A'), SUBSTRING(UPPER(REPLACE(nom, 'é', 'e')), 4))
        ELSE UPPER(REPLACE(nom, 'é', 'e'))
    END AS nom_adherent,
    CASE
        WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 1 AND MOD(id_local DIV 100, 3) = 0 THEN
            CONCAT(SUBSTRING(REPLACE(prenom, 'é', 'e'), 1, 2), SUBSTRING(REPLACE(prenom, 'é', 'e'), 4), IF(MOD(signal_fiche, 11) = 0, '-', ' '), REPLACE(second_prenom, 'é', 'e'))
        WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 1 AND MOD(id_local DIV 100, 3) = 1 THEN
            CONCAT(SUBSTRING(REPLACE(prenom, 'é', 'e'), 1, 3), SUBSTRING(REPLACE(prenom, 'é', 'e'), 3, 1), SUBSTRING(REPLACE(prenom, 'é', 'e'), 4), IF(MOD(signal_fiche, 11) = 0, '-', ' '), REPLACE(second_prenom, 'é', 'e'))
        WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 1 AND MOD(id_local DIV 100, 3) = 2 THEN
            CONCAT(SUBSTRING(REPLACE(prenom, 'é', 'e'), 1, 2), 'O', SUBSTRING(REPLACE(prenom, 'é', 'e'), 4), IF(MOD(signal_fiche, 11) = 0, '-', ' '), REPLACE(second_prenom, 'é', 'e'))
        ELSE CONCAT(REPLACE(prenom, 'é', 'e'), IF(MOD(signal_fiche, 11) = 0, '-', ' '), REPLACE(second_prenom, 'é', 'e'))
    END AS prenoms_adherent,
    CAST(DATE_FORMAT(naissance, '%Y%m%d') AS UNSIGNED) AS date_naiss,
    CASE WHEN MOD(signal_fiche, 31) <> 0 THEN UPPER(lieu) END AS lieu_naiss,
    CASE
        WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 2 AND MOD(id_local DIV 100, 3) = 0 THEN
            CONCAT(SUBSTRING(UPPER(ville), 1, 3), SUBSTRING(UPPER(ville), 5))
        WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 2 AND MOD(id_local DIV 100, 3) = 1 THEN
            CONCAT(SUBSTRING(UPPER(ville), 1, 4), SUBSTRING(UPPER(ville), 4, 1), SUBSTRING(UPPER(ville), 5))
        WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 2 AND MOD(id_local DIV 100, 3) = 2 THEN
            CONCAT(SUBSTRING(UPPER(ville), 1, 3), 'E', SUBSTRING(UPPER(ville), 5))
        ELSE UPPER(ville)
    END AS commune_domicile,
    CASE
        WHEN pont OR MOD(signal_fiche, 17) <> 0 THEN
            CASE
                WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 4 AND MOD(id_local DIV 100, 3) = 0 THEN
                    CONCAT('+000', SUBSTRING(telephone, 1, 8))
                WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 4 AND MOD(id_local DIV 100, 3) = 1 THEN
                    CONCAT('+000', telephone, '9')
                WHEN MOD(id_local, 20) = 0 AND MOD(id_local DIV 20, 5) = 4 AND MOD(id_local DIV 100, 3) = 2 THEN
                    CONCAT('+000', SUBSTRING(telephone, 1, 6), '8', SUBSTRING(telephone, 8))
                ELSE CONCAT('+000', telephone)
            END
    END AS tel_contact,
    CASE WHEN pont OR MOD(signal_fiche, 19) <> 0 THEN
        UPPER(CONCAT(REPLACE(CONCAT(prenom, '.', nom), 'é', 'e'),
            '.', LPAD(MOD(cle * 197 + 53, 10000000), 7, '0'),
            IF(MOD(cle, 3) = 0, '@courrier-ile.test', '@boite-mada.test')))
    END AS email_contact,
    IF(retraite, 'Retraite individuelle', 'Épargne vie') AS produit,
    IF(retraite, 50000, 20000) + MOD(id_local * 17, 29) * 5000 AS cotisation_mensuelle_ar,
    DATE_ADD(
        GREATEST(DATE '2018-01-01', DATE_ADD(naissance, INTERVAL 18 YEAR)),
        INTERVAL (MOD(id_local * 13, 1096)) DAY
    ) AS date_adhesion,
    CAST(CONV(LEFT(SHA2(CONCAT('sexe:', cle), 256), 2), 16, 10) AS UNSIGNED) DIV 128 AS genre
FROM dossiers;
