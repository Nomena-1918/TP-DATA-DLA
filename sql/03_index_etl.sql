-- Indexation globale pour la base tp_assurance_etl
-- Accélère les requêtes du pipeline ETL, les regroupements Union-Find et la mini-application web.

-- ============================================================================
-- 1. INDEX SUR LES COLONNES DE BASE DE etl.fiches_clients
-- ============================================================================

-- Référence locale et système d'origine (recherche et unicité)
CREATE INDEX IF NOT EXISTS idx_fiches_source ON etl.fiches_clients (source_system, source_ref);

-- Identification par CIN (règles de rapprochement et recherche)
CREATE INDEX IF NOT EXISTS idx_fiches_cin_norm ON etl.fiches_clients (cin_norm) WHERE cin_norm IS NOT NULL;

-- Identification par état civil normalisé (Règles C1, C2, C3)
CREATE INDEX IF NOT EXISTS idx_fiches_nom_prenoms ON etl.fiches_clients (nom_norm, prenoms_norm);
CREATE INDEX IF NOT EXISTS idx_fiches_nom_prenoms_date ON etl.fiches_clients (nom_norm, prenoms_trie_norm, date_naiss_norm);
CREATE INDEX IF NOT EXISTS idx_fiches_nom_date ON etl.fiches_clients (nom_norm, date_naiss_norm);
CREATE INDEX IF NOT EXISTS idx_fiches_date_naiss_norm ON etl.fiches_clients (date_naiss_norm);
CREATE INDEX IF NOT EXISTS idx_fiches_bloc_naiss_sexe ON etl.fiches_clients (date_naiss_norm, sexe_norm) WHERE date_naiss_norm IS NOT NULL;

-- Coordonnées de contact normalisées (Règles C4a, C4b et ponts inter-systèmes)
CREATE INDEX IF NOT EXISTS idx_fiches_tel_norm ON etl.fiches_clients (tel_norm) WHERE tel_norm IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fiches_mail_norm ON etl.fiches_clients (mail_norm) WHERE mail_norm IS NOT NULL;

-- Recherche multicritères sur valeurs brutes (Explorateur web)
CREATE INDEX IF NOT EXISTS idx_fiches_cin_brut ON etl.fiches_clients (cin_brut) WHERE cin_brut IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fiches_tel_brut ON etl.fiches_clients (tel_brut) WHERE tel_brut IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fiches_mail_brut ON etl.fiches_clients (mail_brut) WHERE mail_brut IS NOT NULL;

-- Regroupement pivot UID (créé ou activé une fois la colonne uid ajoutée)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'etl' AND table_name = 'fiches_clients' AND column_name = 'uid'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_fiches_uid ON etl.fiches_clients (uid);
        -- Index partiel pour la sélection différentielle O(1) du lot incrémental quotidien (WHERE uid IS NULL)
        CREATE INDEX IF NOT EXISTS idx_fiches_uid_null ON etl.fiches_clients (id_fiche) WHERE uid IS NULL;
    END IF;
END $$;


-- ============================================================================
-- 2. INDEX SUR LA TABLE DES GROUPES CONSOLIDÉS (etl.groupes_uid)
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_groupes_nom ON etl.groupes_uid (nom_principal);
CREATE INDEX IF NOT EXISTS idx_groupes_cin ON etl.groupes_uid (cin_principal) WHERE cin_principal IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_groupes_nb ON etl.groupes_uid (nb_fiches DESC);
CREATE INDEX IF NOT EXISTS idx_groupes_sources ON etl.groupes_uid USING gin (sources);


-- ============================================================================
-- 3. INDEX SUR LA FILE DE VALIDATION HUMAINE (etl.file_validation)
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_validation_statut ON etl.file_validation (statut, motif);
CREATE INDEX IF NOT EXISTS idx_validation_fiches ON etl.file_validation (id_fiche_a, id_fiche_b);


-- ============================================================================
-- 4. INDEX SUR LE JOURNAL DES LIENS (etl.liens_rapprochement)
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_liens_uid ON etl.liens_rapprochement (uid);
CREATE INDEX IF NOT EXISTS idx_liens_fiches ON etl.liens_rapprochement (id_fiche_a, id_fiche_b);
