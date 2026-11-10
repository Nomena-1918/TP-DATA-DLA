-- Schéma cible pour l'ETL et le dédoublonnage NEW_ID / UID
-- PostgreSQL 16, base tp_assurance_etl

CREATE SCHEMA IF NOT EXISTS etl;

-- 1. Table principale : 4 000 000 de fiches individuelles intactes
-- ATTENTION : La colonne 'uid' N'EST PAS présente à ce stade.
-- Elle est ajoutée manuellement à l'étape 4 via sql/02_ajouter_uid_manuel.sql.
CREATE TABLE IF NOT EXISTS etl.fiches_clients (
    id_fiche BIGINT PRIMARY KEY,
    source_system TEXT NOT NULL CHECK (source_system IN ('AUTO', 'LIFE', 'AUTRE')),
    source_ref TEXT NOT NULL,
    -- Données sources brutes intactes (zéro altération)
    cin_brut TEXT,
    nom_brut TEXT,
    prenoms_brut TEXT,
    date_naiss_brute TEXT,
    lieu_naiss_brut TEXT,
    ville_brute TEXT,
    tel_brut TEXT,
    mail_brut TEXT,
    sexe_brut TEXT,
    details_metier JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Données normalisées comparables
    cin_norm CHAR(12),
    cin_chiffres TEXT,
    nom_norm TEXT,
    prenoms_norm TEXT,
    prenoms_trie_norm TEXT,
    date_naiss_norm DATE,
    lieu_naiss_norm TEXT,
    ville_norm TEXT,
    tel_norm TEXT,
    tel_chiffres TEXT,
    mail_norm TEXT,
    sexe_norm CHAR(1) CHECK (sexe_norm IN ('M', 'F')),
    CONSTRAINT uq_source_ref UNIQUE (source_system, source_ref)
);

-- 2. Index de regroupement rapide par UID (alimenté lors du Union-Find)
CREATE TABLE IF NOT EXISTS etl.groupes_uid (
    uid UUID PRIMARY KEY,
    nb_fiches INTEGER NOT NULL,
    sources TEXT[] NOT NULL,
    cin_principal CHAR(12),
    nom_principal TEXT,
    prenoms_principal TEXT,
    date_naiss_principale DATE,
    ville_principale TEXT,
    regle_max TEXT,
    score_confiance SMALLINT,
    statut TEXT NOT NULL DEFAULT 'AUTO_VALIDE',
    maj_le TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Journal des correspondances et justifications
CREATE TABLE IF NOT EXISTS etl.liens_rapprochement (
    id_lien BIGSERIAL PRIMARY KEY,
    uid UUID NOT NULL,
    id_fiche_a BIGINT NOT NULL,
    id_fiche_b BIGINT NOT NULL,
    regle TEXT NOT NULL,
    score SMALLINT NOT NULL,
    valide_par TEXT NOT NULL DEFAULT 'SYSTEM',
    cree_le TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. File de validation humaine (cas ambigus C4a/C4b 50 % et conflits CIN)
CREATE TABLE IF NOT EXISTS etl.file_validation (
    id_cas BIGSERIAL PRIMARY KEY,
    id_fiche_a BIGINT NOT NULL,
    id_fiche_b BIGINT NOT NULL,
    uid_a UUID,
    uid_b UUID,
    motif TEXT NOT NULL,
    regle TEXT NOT NULL,
    score SMALLINT NOT NULL,
    cle_partagee TEXT,
    statut TEXT NOT NULL DEFAULT 'A_VALIDER' CHECK (statut IN ('A_VALIDER', 'VALIDE_HUMAIN', 'REJETE_HUMAIN')),
    decision_note TEXT,
    traite_le TIMESTAMPTZ
);

-- 5. Journal des exécutions du pipeline
CREATE TABLE IF NOT EXISTS etl.journal_executions (
    id_run BIGSERIAL PRIMARY KEY,
    phase TEXT NOT NULL,
    statut TEXT NOT NULL,
    duree_secondes NUMERIC(8, 2),
    lignes_traitees BIGINT,
    details JSONB,
    horodatage TIMESTAMPTZ NOT NULL DEFAULT now()
);
