"""Tests unitaires des fonctions pures de normalisation."""

from datetime import date
from tp_data_dla.normalisation import (
    normaliser_cin,
    normaliser_date,
    normaliser_lieu,
    normaliser_mail,
    normaliser_nom,
    normaliser_prenoms,
    normaliser_sexe,
    normaliser_tel,
    normaliser_ville,
)


def test_normaliser_cin():
    assert normaliser_cin("CIN- 800005316023") == "800005316023"
    assert normaliser_cin(800005316023) == "800005316023"
    assert normaliser_cin("800005316023") == "800005316023"
    assert normaliser_cin(None) is None
    assert normaliser_cin("") is None
    assert normaliser_cin("12345") is None  # Longueur invalide


def test_normaliser_nom():
    assert normaliser_nom("Ravélo") == "RAVELO"
    assert normaliser_nom("  Ramanitra  ") == "RAMANITRA"
    assert normaliser_nom("RAKOTOMALALA") == "RAKOTOMALALA"
    assert normaliser_nom(None) is None


def test_normaliser_prenoms():
    p_norm, p_trie = normaliser_prenoms("Faly Tahina")
    assert p_norm == "FALY TAHINA"
    assert p_trie == "FALY TAHINA"

    # Inversion de prénoms
    p_norm2, p_trie2 = normaliser_prenoms("Tahina Faly")
    assert p_norm2 == "TAHINA FALY"
    assert p_trie2 == "FALY TAHINA"  # Doit être identique !

    # Avec tiret et accents
    _, p_trie3 = normaliser_prenoms("Noé-Léa")
    assert p_trie3 == "LEA NOE"


def test_normaliser_date():
    assert normaliser_date(date(1970, 4, 19)) == "1970-04-19"
    assert normaliser_date(19700419) == "1970-04-19"
    assert normaliser_date("19-04-1970") == "1970-04-19"
    assert normaliser_date("1970-04-19") == "1970-04-19"
    assert normaliser_date(None) is None


def test_normaliser_tel():
    assert normaliser_tel("00 95 397 11") == "009539711"
    assert normaliser_tel("+000009539711") == "009539711"
    assert normaliser_tel("00-95-397-11") == "009539711"
    assert normaliser_tel(None) is None


def test_normaliser_mail():
    assert normaliser_mail("TAHINA.RAMANITRA@COURRIER-ILE.TEST") == "tahina.ramanitra@courrier-ile.test"
    assert normaliser_mail("  nirina@test.org  ") == "nirina@test.org"
    assert normaliser_mail(None) is None


def test_normaliser_sexe():
    assert normaliser_sexe("Masculin") == "M"
    assert normaliser_sexe("Féminin") == "F"
    assert normaliser_sexe(1) == "M"
    assert normaliser_sexe(0) == "F"
    assert normaliser_sexe("M") == "M"
    assert normaliser_sexe("F") == "F"
