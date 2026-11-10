-- Depuis la racine : psql -X -d tp_assurance_auto -f sql/charger_auto_postgresql_leger.sql
-- PostgreSQL 16, base dédiée préexistante (Version légère : 100 000 fiches au lieu de 1 000 000).
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL client_encoding = 'UTF8';
SET LOCAL search_path = pg_catalog;

DO $$
BEGIN
    IF current_database() <> 'tp_assurance_auto' THEN
        RAISE EXCEPTION 'Base dédiée tp_assurance_auto requise, base courante %',
            current_database();
    END IF;
    IF current_setting('server_version_num')::integer NOT BETWEEN 160000 AND 169999 THEN
        RAISE EXCEPTION 'PostgreSQL 16 requis.';
    END IF;
    IF current_setting('server_encoding') <> 'UTF8' THEN
        RAISE EXCEPTION 'La base du TP doit utiliser UTF8.';
    END IF;
END;
$$;

-- Recréation propre du schéma
DROP SCHEMA IF EXISTS tp_assurance CASCADE;
CREATE SCHEMA tp_assurance;
CREATE TABLE tp_assurance.clients_auto (
    id_client_auto bigint PRIMARY KEY,
    numero_cin text,
    nom_assure text NOT NULL,
    prenoms_assure text NOT NULL,
    ne_le date NOT NULL,
    ne_a text,
    ville_residence text NOT NULL,
    mobile text,
    courriel text,
    immatriculation text NOT NULL UNIQUE,
    annee_vehicule smallint NOT NULL,
    formule_auto text NOT NULL,
    sexe text NOT NULL CHECK (sexe IN ('Masculin', 'Féminin'))
);

-- Les clés de génération 1 à 70000 sont communes aux trois sources (version légère).
WITH rangs AS (
    SELECT
        1000000 + numero AS id_local,
        ((numero - 1) * 73 + 41729) % 100000 + 1 AS rang
    FROM generate_series(1::bigint, 100000::bigint) AS serie(numero)
), reprises AS (
    SELECT
        id_local,
        rang > 99000 AS reprise,
        CASE
            WHEN rang <= 99000 THEN rang
            WHEN rang <= 99700 THEN rang - 99000
            ELSE 70000 + rang - 99700
        END AS cle
    FROM rangs
), calculs AS (
    SELECT
        id_local,
        cle,
        cle + 3 + 7 * reprise::integer AS signal,
        cle % 211 = 0 AS pont,
        ((cle - (cle % 101 = 0)::integer) * 131071 + 12345) % 67108864 AS mix,
        cle - (cle % 67 = 0)::integer AS contact
    FROM reprises
), listes AS (
    SELECT
        ARRAY[
            'Ravélo', 'Andriamahery', 'Rakotomalala', 'Ramanitra',
            'Razafindrano', 'Rasoatina', 'Randriavola', 'Raharisoa',
            'Ranaivo', 'Ravelomanana', 'Andriatsiry', 'Ratsimandresy',
            'Rabemanga', 'Rafaraléo', 'Rajaonina', 'Rasolofo'
        ] AS noms,
        ARRAY[
            'Mialy', 'Tiana', 'Aina', 'Miora', 'Lova', 'Fara', 'Tahiry', 'Avotra',
            'Nirina', 'Hasina', 'Noé', 'Léa', 'Tahina', 'Feno', 'Sitraka', 'Valisoa'
        ] AS prenoms,
        ARRAY[
            'Hery', 'Soa', 'Rija', 'Faly', 'Nivo', 'Kanto', 'Voary', 'Zo',
            'Kolo', 'Tojo', 'Miary', 'Lanto', 'Tsiory', 'Haja', 'Mamy', 'Fanja'
        ] AS seconds,
        ARRAY[
            'Antananarivo', 'Toamasina', 'Antsirabe', 'Mahajanga',
            'Fianarantsoa', 'Toliara', 'Antsiranana', 'Morondava',
            'Sambava', 'Ambatondrazaka'
        ] AS villes
), dossiers AS (
    SELECT
        id_local,
        signal,
        pont,
        800000000000 + (cle * 73 + 17) % 10000000 AS cin,
        noms[(mix % 16)::integer + 1] AS nom,
        prenoms[(mix / 16 % 16)::integer + 1] || ' ' ||
            seconds[(mix / 256 % 16)::integer + 1] AS prenoms,
        DATE '1960-01-01' + (mix / 4096)::integer AS naissance,
        villes[(mix / 65536 % cardinality(villes))::integer + 1] AS lieu,
        villes[(cle * 37 / 13 % cardinality(villes))::integer + 1] AS ville,
        '00' || lpad(((contact * 131 + 29) % 10000000)::text, 7, '0') AS telephone,
        lower(translate(prenoms[(mix / 16 % 16)::integer + 1] || '.' ||
            noms[(mix % 16)::integer + 1], 'é', 'e') COLLATE "C") ||
            '.' || lpad(((cle * 197 + 53) % 10000000)::text, 7, '0') ||
            CASE WHEN cle % 3 = 0 THEN '@courrier-ile.test' ELSE '@boite-mada.test' END AS email,
        (1998 + id_local * 11 % 28)::smallint AS annee,
        get_byte(sha256(convert_to('sexe:' || cle::text, 'UTF8')), 0) >= 128 AS masculin
    FROM calculs CROSS JOIN listes
)
INSERT INTO tp_assurance.clients_auto (
    id_client_auto, numero_cin, nom_assure, prenoms_assure, ne_le, ne_a,
    ville_residence, mobile, courriel, immatriculation, annee_vehicule, formule_auto, sexe
)
SELECT
    id_local,
    CASE
        WHEN NOT (pont OR signal % 13 <> 0) THEN NULL
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 3 AND (id_local / 100) % 3 = 0 THEN 'CIN- ' || (cin / 10)::text
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 3 AND (id_local / 100) % 3 = 1 THEN 'CIN- ' || (cin::text || '7')
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 3 AND (id_local / 100) % 3 = 2 THEN 'CIN- ' || (cin + 5)::text
        ELSE 'CIN- ' || cin::text
    END,
    CASE
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 0 AND (id_local / 100) % 3 = 0 THEN substr(nom, 1, 2) || substr(nom, 4)
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 0 AND (id_local / 100) % 3 = 1 THEN substr(nom, 1, 3) || substr(nom, 3, 1) || substr(nom, 4)
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 0 AND (id_local / 100) % 3 = 2 THEN substr(nom, 1, 2) || CASE WHEN lower(substr(nom, 3, 1)) = 'a' THEN 'e' ELSE 'a' END || substr(nom, 4)
        WHEN signal % 5 = 0 THEN ' ' || upper(translate(nom, 'é', 'e') COLLATE "C") || ' '
        ELSE nom
    END,
    CASE
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 1 AND (id_local / 100) % 3 = 0 THEN substr(prenoms, 1, 2) || substr(prenoms, 4)
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 1 AND (id_local / 100) % 3 = 1 THEN substr(prenoms, 1, 3) || substr(prenoms, 3, 1) || substr(prenoms, 4)
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 1 AND (id_local / 100) % 3 = 2 THEN substr(prenoms, 1, 2) || 'o' || substr(prenoms, 4)
        ELSE prenoms
    END,
    naissance,
    CASE WHEN signal % 29 <> 0 THEN lieu END,
    CASE
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 2 AND (id_local / 100) % 3 = 0 THEN substr(ville, 1, 3) || substr(ville, 5)
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 2 AND (id_local / 100) % 3 = 1 THEN substr(ville, 1, 4) || substr(ville, 4, 1) || substr(ville, 5)
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 2 AND (id_local / 100) % 3 = 2 THEN substr(ville, 1, 3) || 'e' || substr(ville, 5)
        ELSE ville
    END,
    CASE
        WHEN NOT (pont OR signal % 17 <> 0) THEN NULL
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 4 AND (id_local / 100) % 3 = 0 THEN substr(telephone, 1, 8)
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 4 AND (id_local / 100) % 3 = 1 THEN telephone || '9'
        WHEN id_local % 20 = 0 AND (id_local / 20) % 5 = 4 AND (id_local / 100) % 3 = 2 THEN substr(telephone, 1, 6) || '8' || substr(telephone, 8)
        ELSE substr(telephone, 1, 2) || ' ' || substr(telephone, 3, 2) || ' ' || substr(telephone, 5, 3) || ' ' || substr(telephone, 8, 2)
    END,
    CASE WHEN NOT pont AND signal % 19 <> 0 THEN email END,
    'TP-' || lpad((id_local - 1000000)::text, 7, '0') || '-AUTO',
    annee,
    CASE
        WHEN annee < 2010 THEN 'Tiers'
        WHEN annee < 2019 THEN 'Tiers étendu'
        ELSE 'Tous risques'
    END,
    CASE WHEN masculin THEN 'Masculin' ELSE 'Féminin' END
FROM dossiers;

SELECT :ROW_COUNT::bigint = 100000 AS volume_valide
\gset
\if :volume_valide
    COMMIT;
    \echo Auto chargé (version légère). 100 000 fiches dans la base dédiée.
\else
    DO $$
    BEGIN
        RAISE EXCEPTION 'Volume inséré différent des 100 000 fiches attendues.';
    END;
    $$;
\endif
