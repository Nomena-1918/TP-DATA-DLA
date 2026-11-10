-- Étape 4 du TP : Ajout manuel de la colonne UID dans la table cible
-- PostgreSQL 16, base tp_assurance_etl

ALTER TABLE etl.fiches_clients
    ADD COLUMN IF NOT EXISTS uid UUID;

-- Commentaire explicatif
COMMENT ON COLUMN etl.fiches_clients.uid IS 'Identifiant universel unique (NEW_ID / UID) commun aux fiches d''une même personne physique.';
