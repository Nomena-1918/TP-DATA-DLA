"""Tests d'intégration de l'application web FastAPI."""

import os

import pytest
from fastapi.testclient import TestClient
from tp_data_dla.web.app import app

client = TestClient(app)
AUTH = ("operateur_test", "mot-de-passe-fictif")


@pytest.fixture(autouse=True)
def operateur_test(monkeypatch):
    monkeypatch.setenv("TP_VALIDATION_USER", AUTH[0])
    monkeypatch.setenv("TP_VALIDATION_PASSWORD", AUTH[1])


def test_page_dashboard_accessible():
    response = client.get("/")
    assert response.status_code == 200
    assert "Référentiel Client NEW_ID" in response.text
    assert "Tableau de bord" in response.text


def test_page_recherche_accessible():
    response = client.get("/recherche")
    assert response.status_code == 200
    assert "Explorateur de groupes UID" in response.text


def test_page_validation_accessible():
    response = client.get("/validation", auth=AUTH)
    assert response.status_code == 200
    assert "File de validation humaine" in response.text


def test_action_validation_arbitrage():
    # Test d'une décision d'arbitrage
    response = client.post("/api/validation/9999999/decision", data={"action": "MAINTENIR_SEPARES"},
                           auth=AUTH, follow_redirects=False)
    # Pour un id_cas inexistant, renvoie 404
    assert response.status_code == 404


def test_validation_requiert_operateur_et_origine():
    assert client.get("/validation").status_code == 401
    assert client.post("/api/validation/1/decision", auth=AUTH,
                       headers={"Origin": "http://externe.test"},
                       data={"action": "ASSIGNER_MEME_UID"}).status_code == 403


@pytest.mark.skipif(os.getenv("TP_TEST_ECRITURE") != "1", reason="Base ETL de test isolée requise")
def test_relances_et_arbitrages_lies(monkeypatch):
    from tp_data_dla import cli, etl, union_find
    from tp_data_dla.config import get_etl_connection

    with get_etl_connection() as conn:
        assert conn.execute("SELECT current_database()").fetchone()[0].startswith("tp_dla_test_")
        assert conn.execute("SELECT count(*) FROM etl.fiches_clients").fetchone()[0] == 0

    def fiche(reference, source):
        return (reference, source, str(reference), *([None] * 9), "{}", *([None] * 12))

    def life_en_echec(**_):
        raise RuntimeError("Source indisponible")

    monkeypatch.setattr(etl, "iter_auto", lambda **_: iter([fiche(1, "AUTO")]))
    monkeypatch.setattr(etl, "iter_life", life_en_echec)
    monkeypatch.setattr(etl, "iter_autre", lambda **_: iter([fiche(3, "AUTRE"), fiche(4, "AUTRE")]))
    with pytest.raises(RuntimeError, match="Source indisponible"):
        etl.executer_etl()
    with get_etl_connection() as conn:
        assert conn.execute("SELECT count(*) FROM etl.fiches_clients").fetchone()[0] == 0
    monkeypatch.setattr(etl, "iter_life", lambda **_: iter([fiche(2, "LIFE")]))
    assert etl.executer_etl() == 4
    cli.commande_add_uid(None)
    union_find.executer_union_find()

    with get_etl_connection() as conn:
        for a, b in [(1, 2), (2, 3), (3, 4), (1, 4)]:
            conn.execute("""
                INSERT INTO etl.file_validation (id_fiche_a, id_fiche_b, uid_a, uid_b, motif, regle, score)
                SELECT a.id_fiche, b.id_fiche, a.uid, b.uid, 'TEST', 'C4a', 50
                FROM etl.fiches_clients a, etl.fiches_clients b
                WHERE a.id_fiche = %s AND b.id_fiche = %s
            """, (a, b))

    def decision(cas, action="ASSIGNER_MEME_UID"):
        return client.post(f"/api/validation/{cas}/decision", auth=AUTH,
                           data={"action": action}, follow_redirects=False).status_code

    assert decision(1) == 303
    assert decision(2) == 303
    assert decision(2) == 409
    assert decision(3, "MAINTENIR_SEPARES") == 303
    assert decision(4) == 409
    cli.commande_init_db(None)
    with pytest.raises(RuntimeError, match="déjà"):
        etl.executer_etl()
    with pytest.raises(RuntimeError, match="déjà publié"):
        union_find.executer_union_find()
    with get_etl_connection() as conn:
        assert conn.execute("SELECT count(*), count(DISTINCT uid) FROM etl.fiches_clients").fetchone() == (4, 2)
        assert conn.execute("SELECT count(*) FROM etl.liens_rapprochement").fetchone()[0] == 2
        assert conn.execute("""
            SELECT statut FROM etl.file_validation ORDER BY id_cas
        """).fetchall() == [("VALIDE_HUMAIN",), ("VALIDE_HUMAIN",), ("REJETE_HUMAIN",), ("A_VALIDER",)]

    # --- Test du lot incrémental quotidien (Phase 2 : 00h00-07h00, WHERE uid IS NULL) ---
    with get_etl_connection() as conn:
        # Enrichissement de la fiche historique #1 pour simuler un client existant complet
        conn.execute("""
            UPDATE etl.fiches_clients
            SET cin_brut = '800001112223', cin_norm = '800001112223', cin_chiffres = '800001112223',
                nom_brut = 'RAMANITRA', nom_norm = 'RAMANITRA',
                prenoms_brut = 'TAHINA FALY', prenoms_norm = 'TAHINA FALY', prenoms_trie_norm = 'FALY TAHINA',
                date_naiss_brute = '1985-04-12', date_naiss_norm = '1985-04-12',
                lieu_naiss_brut = 'ANTANANARIVO', lieu_naiss_norm = 'ANTANANARIVO',
                ville_brute = 'ANTANANARIVO', ville_norm = 'ANTANANARIVO',
                tel_brut = '0341234567', tel_norm = '341234567', tel_chiffres = '0341234567',
                sexe_brut = 'M', sexe_norm = 'M'
            WHERE id_fiche = 1;
        """)
        uid_hist_1 = conn.execute("SELECT uid::text FROM etl.fiches_clients WHERE id_fiche = 1").fetchone()[0]
        conn.execute("""
            UPDATE etl.groupes_uid
            SET cin_principal = '800001112223', nom_principal = 'RAMANITRA',
                prenoms_principal = 'TAHINA FALY', date_naiss_principale = '1985-04-12',
                ville_principale = 'ANTANANARIVO'
            WHERE uid = %s;
        """, (uid_hist_1,))

        # Insertion d'un lot quotidien de 5 nouvelles fiches avec uid IS NULL (non normalisées) :
        # - Fiche 10 (Cas A via C1 : même CIN que la fiche historique #1)
        # - Fiche 11 (Cas A via C2_FLOU : faute de frappe 'RAMANITRAA' sans CIN, rattachée à #1)
        # - Fiches 12 et 13 (Cas B : nouveau client présent 2 fois dans le lot nocturne, fusion intra-lot)
        # - Fiche 14 (Cas C : suspicion faute CIN à 1 chiffre '800001112229' -> UID provisoire + file validation)
        conn.execute("""
            INSERT INTO etl.fiches_clients (
                id_fiche, source_system, source_ref,
                cin_brut, nom_brut, prenoms_brut, date_naiss_brute,
                lieu_naiss_brut, ville_brute, tel_brut, mail_brut, sexe_brut
            ) VALUES
            (10, 'LIFE', '10', '800001112223', 'Ramanitra', 'Tahina Faly', '1985-04-12', 'Antananarivo', 'Antananarivo', '0341234567', NULL, 'M'),
            (11, 'AUTRE', 'EXT-11', NULL, 'Ramanitraa', 'Faly Tahina', '1985-04-12', 'Antananarivo', 'Antananarivo', NULL, NULL, 'M'),
            (12, 'AUTO', '12', '800009998887', 'Rakotomalala', 'Mialy Kanto', '1992-08-20', 'Toamasina', 'Toamasina', '0329988776', NULL, 'F'),
            (13, 'LIFE', '13', '800009998887', 'RAKOTOMALALA', 'Kanto Mialy', '1992-08-20', 'Toamasina', 'Toamasina', '0329988776', NULL, 'F'),
            (14, 'AUTRE', 'EXT-14', '800001112229', 'Ramanitra', 'Tahina Faly', '1985-04-12', 'Antananarivo', 'Antananarivo', NULL, NULL, 'M');
        """)
        conn.commit()

    # En découpant par lots de 3 :
    # - Lot #1 (fiches 10, 11, 12) : 10 et 11 reconnus en Cas A, 12 nouveau en Cas B
    # - Lot #2 (fiches 13, 14) : 13 reconnaît la fiche 12 déjà publiée par le Lot #1 (Cas A), 14 en Cas C provisoire
    res_inc = union_find.executer_lot_incremental(chunk_size=3)
    assert res_inc["fiches_traitees"] == 5
    assert res_inc["chunks_traites"] == 2
    assert res_inc["restant_uid_null"] == 0
    assert res_inc["cas_a_reconnus"] == 3
    assert res_inc["cas_b_nouveaux"] == 1
    assert res_inc["cas_c_provisoires"] == 1

    with get_etl_connection() as conn:
        # 100 % des fiches ont désormais un UID non nul (garantie SLA 07h00)
        assert conn.execute("SELECT count(*) FROM etl.fiches_clients WHERE uid IS NULL").fetchone()[0] == 0

        # Cas A : les fiches 10 et 11 ont hérité du uid_hist_1
        uids_10_11 = conn.execute(
            "SELECT uid::text FROM etl.fiches_clients WHERE id_fiche IN (10, 11) ORDER BY id_fiche"
        ).fetchall()
        assert uids_10_11 == [(uid_hist_1,), (uid_hist_1,)]

        # Cas B : les fiches 12 et 13 partagent le même nouvel UID (distinct de uid_hist_1)
        uids_12_13 = conn.execute(
            "SELECT uid::text FROM etl.fiches_clients WHERE id_fiche IN (12, 13) ORDER BY id_fiche"
        ).fetchall()
        assert uids_12_13[0][0] == uids_12_13[1][0]
        assert uids_12_13[0][0] != uid_hist_1

        # Cas C : la fiche 14 a reçu un UID provisoire et un cas SUSPICION_FAUTE_CIN est en file de validation
        uid_prov_14 = conn.execute(
            "SELECT uid::text FROM etl.fiches_clients WHERE id_fiche = 14"
        ).fetchone()[0]
        assert uid_prov_14 != uid_hist_1
        cas_suspicion = conn.execute("""
            SELECT id_cas, motif, score FROM etl.file_validation
            WHERE (id_fiche_a = 14 OR id_fiche_b = 14) AND statut = 'A_VALIDER'
        """).fetchone()
        assert cas_suspicion is not None
        assert cas_suspicion[1] == "SUSPICION_FAUTE_CIN"
        assert cas_suspicion[2] == 75

    # Arbitrage humain sur le Cas C : l'opérateur confirme la faute de frappe -> réalignement sur l'UID historique
    assert decision(cas_suspicion[0], "ASSIGNER_MEME_UID") == 303
    with get_etl_connection() as conn:
        uid_final_14 = conn.execute(
            "SELECT uid::text FROM etl.fiches_clients WHERE id_fiche = 14"
        ).fetchone()[0]
        assert uid_final_14 == uid_hist_1


