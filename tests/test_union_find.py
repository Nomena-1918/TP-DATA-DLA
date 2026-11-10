"""Tests unitaires du moteur Union-Find compact et du verrou anti-conflit CIN."""

from tp_data_dla.union_find import CompactUnionFind


def test_union_find_basique_et_transitivite():
    # 5 éléments (0..4)
    uf = CompactUnionFind(5, lambda x: x, lambda x: x)

    # Réunion 0 et 1 via C1
    assert uf.union(0, 1, regle="C1") is True
    assert uf.find(0) == uf.find(1)

    # Réunion 1 et 2 via C2
    assert uf.union(1, 2, regle="C2") is True
    # Transitivité : 0 et 2 doivent appartenir au même cluster
    assert uf.find(0) == uf.find(2)
    assert uf.find(3) != uf.find(0)


def test_verrou_anti_conflit_cin():
    uf = CompactUnionFind(4, lambda x: x, lambda x: x)
    # L'élément 0 a le CIN 800000000001
    uf.cluster_cin[0] = 800000000001
    # L'élément 1 a le CIN 800000000002
    uf.cluster_cin[1] = 800000000002
    # L'élément 2 n'a pas de CIN (-1)
    uf.cluster_cin[2] = -1

    # 1. 0 et 2 partagent le même état civil (C2) -> UNION ACCEPTÉE
    assert uf.union(0, 2, regle="C2") is True
    root_0_2 = uf.find(0)
    assert uf.cluster_cin[root_0_2] == 800000000001

    # 2. 1 et 2 partagent le même état civil (C2) -> CONFLIT STRICT DE CIN (800000000001 != 800000000002)
    assert uf.union(1, 2, regle="C2") is False
    assert uf.find(1) != uf.find(2)
    assert len(uf.conflits_cin) == 1
    assert uf.conflits_cin[0] == (1, 2, "C2")


def test_gestion_memoire_compacte():
    # Vérification que la structure pour 100 000 éléments s'alloue instantanément
    uf = CompactUnionFind(100_000, lambda x: x, lambda x: x)
    assert len(uf.parent) == 100_000
    assert len(uf.cluster_cin) == 100_000
    assert uf.parent.itemsize == 4  # int32 (4 octets)
    assert uf.cluster_cin.itemsize == 8  # int64 (8 octets)


def test_flou_resolution_fautes():
    """Vérifie la tolérance aux coquilles typographiques sur noms et prénoms."""
    from tp_data_dla.normalisation import (
        damerau_levenshtein_adaptatif,
        distance_prenoms_tokens,
    )
    # Fautes légères (1 caractère)
    assert damerau_levenshtein_adaptatif("RAMANITRA", "RAMANITRAA") == 1
    assert damerau_levenshtein_adaptatif("ANDRIAMAHERY", "ANDRIAMAHARI") == 2
    # Prénoms inversés avec faute
    assert distance_prenoms_tokens("TAHIRY HERY", "HERY TAHIRYY") == 1
    # Mot court : distance 2 refusée pour éviter faux positifs
    assert damerau_levenshtein_adaptatif("AINA", "TIANA") == 999


def test_evaluer_paire_floue_decisions():
    """Vérifie les décisions de _evaluer_paire_floue (UNION, SUSPICION_FAUTE_CIN, CONFLIT_CIN)."""
    from tp_data_dla.union_find import _evaluer_paire_floue

    base_a = {
        "nom_norm": "ANDRIAMAHERY",
        "prenoms_norm": "TAHIRY HERY",
        "lieu_naiss_norm": "ANTANANARIVO",
        "ville_norm": "ANTANANARIVO",
        "cin_norm": "800008941210",
        "cin_chiffres": "800008941210",
    }
    # 1. Coquille sur le nom + même CIN valide -> UNION (80)
    b_meme_cin = {**base_a, "nom_norm": "ANDRIAMAHERI"}
    assert _evaluer_paire_floue(base_a, b_meme_cin) == ("UNION", "C2_FLOU", 80)

    # 2. Coquille sur le nom + 1 seul chiffre d'écart sur CIN 12 chiffres -> SUSPICION_FAUTE_CIN (75)
    b_suspicion = {
        **base_a,
        "nom_norm": "ANDRIAMAHERI",
        "cin_norm": "800008941219",
        "cin_chiffres": "800008941219",
    }
    assert _evaluer_paire_floue(base_a, b_suspicion) == ("SUSPICION_FAUTE_CIN", "C2_FLOU", 75)

    # 3. Coquille sur le nom + >= 2 chiffres d'écart sur CIN 12 chiffres -> CONFLIT_CIN (0)
    b_conflit = {
        **base_a,
        "nom_norm": "ANDRIAMAHERI",
        "cin_norm": "800009999999",
        "cin_chiffres": "800009999999",
    }
    assert _evaluer_paire_floue(base_a, b_conflit) == ("CONFLIT_CIN", "C2_FLOU", 0)

    # 4. CIN malformé (11 chiffres, chiffre manquant) à distance 1 -> UNION (75)
    b_cin_11 = {
        **base_a,
        "nom_norm": "ANDRIAMAHERI",
        "cin_norm": None,
        "cin_chiffres": "80000894121",
    }
    assert _evaluer_paire_floue(base_a, b_cin_11) == ("UNION", "C2_FLOU", 75)


