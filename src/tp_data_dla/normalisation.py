"""Fonctions pures de nettoyage et de normalisation des attributs comparables."""

import re
import unicodedata
from datetime import date, datetime
from typing import Any, Optional, Tuple

from rapidfuzz.distance import DamerauLevenshtein

RE_CHIFRES = re.compile(r"\D")
RE_ESPACES = re.compile(r"\s+")
RE_DATE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_DATE_FR = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")
RE_DATE_INT = re.compile(r"^(\d{4})(\d{2})(\d{2})$")


def supprimer_accents(texte: str) -> str:
    """Retire les accents et diacritiques d'une chaîne (NFKD)."""
    nfkd = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normaliser_cin(valeur: Any) -> Optional[str]:
    """Extrait un numéro de CIN canonique sur 12 chiffres consécutifs."""
    if valeur is None:
        return None
    chiffres = RE_CHIFRES.sub("", str(valeur))
    return chiffres if len(chiffres) == 12 else None


def normaliser_nom(valeur: Any) -> Optional[str]:
    """Nettoie le nom de famille : trim, sans accents, en majuscules."""
    if not valeur:
        return None
    texte = supprimer_accents(str(valeur)).strip().upper()
    texte = RE_ESPACES.sub(" ", texte)
    return texte or None


def normaliser_prenoms(valeur: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Nettoie les prénoms et produit :
    1. prenoms_norm : tokens en majuscules séparés par un espace.
    2. prenoms_trie_norm : tokens triés alphabétiquement (absorbe 'A B' vs 'B A').
    """
    if not valeur:
        return None, None
    texte = supprimer_accents(str(valeur)).replace("-", " ").strip().upper()
    tokens = [t for t in RE_ESPACES.split(texte) if t]
    if not tokens:
        return None, None
    prenoms_norm = " ".join(tokens)
    prenoms_trie_norm = " ".join(sorted(tokens))
    return prenoms_norm, prenoms_trie_norm


def normaliser_date(valeur: Any) -> Optional[str]:
    """Convertit une date en chaîne ISO YYYY-MM-DD."""
    if valeur is None:
        return None
    if isinstance(valeur, (date, datetime)):
        return valeur.strftime("%Y-%m-%d")

    s = str(valeur).strip()
    if RE_DATE_ISO.match(s):
        return s

    m_fr = RE_DATE_FR.match(s)
    if m_fr:
        jour, mois, annee = m_fr.groups()
        return f"{annee}-{mois}-{jour}"

    m_int = RE_DATE_INT.match(s)
    if m_int:
        annee, mois, jour = m_int.groups()
        return f"{annee}-{mois}-{jour}"

    return None


def normaliser_lieu(valeur: Any) -> Optional[str]:
    """Nettoie un lieu (naissance ou commune) : trim, sans accents, majuscules."""
    if not valeur:
        return None
    texte = supprimer_accents(str(valeur)).strip().upper()
    texte = RE_ESPACES.sub(" ", texte)
    return texte or None


def normaliser_ville(valeur: Any) -> Optional[str]:
    """Nettoie la ville de résidence : trim, sans accents, majuscules."""
    return normaliser_lieu(valeur)


def normaliser_tel(valeur: Any) -> Optional[str]:
    """Normalise un numéro de téléphone vers une chaîne de 9 chiffres (00XXXXXXX)."""
    if not valeur:
        return None
    chiffres = RE_CHIFRES.sub("", str(valeur))
    if chiffres.startswith("000"):
        chiffres = chiffres[3:]
    return chiffres if len(chiffres) == 9 and chiffres.startswith("00") else None


def normaliser_mail(valeur: Any) -> Optional[str]:
    """Normalise une adresse de courriel en minuscules."""
    if not valeur:
        return None
    s = str(valeur).strip().lower()
    return s if "@" in s and "." in s else None


def normaliser_sexe(valeur: Any) -> Optional[str]:
    """Normalise le sexe / genre vers 'M' ou 'F'."""
    if valeur is None:
        return None
    s = supprimer_accents(str(valeur)).strip().upper()
    if s in ("M", "1", "MASCULIN"):
        return "M"
    if s in ("F", "0", "FEMININ"):
        return "F"
    return None


def extraire_cin_chiffres(valeur: Any) -> Optional[str]:
    """
    Extrait les chiffres du CIN sans exiger strictement 12 caractères.
    Tolère les chiffres manquants ou superflus dus aux fautes de saisie (10 à 14 chiffres).
    """
    if valeur is None:
        return None
    chiffres = RE_CHIFRES.sub("", str(valeur))
    return chiffres if 10 <= len(chiffres) <= 14 else None


def extraire_tel_chiffres(valeur: Any) -> Optional[str]:
    """
    Extrait les chiffres d'un numéro de téléphone tolérant les fautes légères (7 à 12 chiffres).
    """
    if not valeur:
        return None
    chiffres = RE_CHIFRES.sub("", str(valeur))
    return chiffres if 7 <= len(chiffres) <= 12 else None


def damerau_levenshtein_adaptatif(s1: Optional[str], s2: Optional[str]) -> int:
    """
    Calcule la distance de Damerau-Levenshtein avec seuil adaptatif selon la longueur :
    - Chaînes < 9 caractères : distance maximale acceptée = 1 (évite les collisions sur mots courts).
    - Chaînes >= 9 caractères : distance maximale acceptée = 2.
    Retourne 999 si les chaînes ne sont pas comparables ou si la distance dépasse le seuil.
    """
    if s1 is None or s2 is None:
        return 999
    if s1 == s2:
        return 0

    len1 = len(s1)
    len2 = len(s2)
    min_len = min(len1, len2)
    seuil_max = 2 if min_len >= 9 else 1

    # Pruning rapide sur la différence de longueurs
    if abs(len1 - len2) > seuil_max:
        return 999

    dist = DamerauLevenshtein.distance(s1, s2, score_cutoff=seuil_max)
    return dist if dist <= seuil_max else 999


def distance_prenoms_tokens(p1: Optional[str], p2: Optional[str]) -> int:
    """
    Calcule la distance sur une liste de prénoms en tenant compte des inversions de tokens.
    Tolère une coquille légère sur l'un des prénoms ou un ordre inversé (ex: 'TAHIRY HERY' vs 'HERY TAHIRYY').
    """
    if p1 is None or p2 is None:
        return 999
    if p1 == p2:
        return 0

    tokens1 = p1.split()
    tokens2 = p2.split()
    if not tokens1 or not tokens2:
        return 999

    # Si tokens triés identiques (inversion pure déjà couverte)
    if sorted(tokens1) == sorted(tokens2):
        return 0

    if len(tokens1) == len(tokens2) == 1:
        return damerau_levenshtein_adaptatif(tokens1[0], tokens2[0])

    if len(tokens1) == len(tokens2) == 2:
        # Alignement direct
        d1 = damerau_levenshtein_adaptatif(tokens1[0], tokens2[0])
        d2 = damerau_levenshtein_adaptatif(tokens1[1], tokens2[1])
        d_direct = d1 + d2 if (d1 <= 2 and d2 <= 2) else 999

        # Alignement inversé
        r1 = damerau_levenshtein_adaptatif(tokens1[0], tokens2[1])
        r2 = damerau_levenshtein_adaptatif(tokens1[1], tokens2[0])
        d_inverse = r1 + r2 if (r1 <= 2 and r2 <= 2) else 999

        best = min(d_direct, d_inverse)
        return best if best <= 2 else 999

    # Pour les cas plus longs ou asymétriques : distance sur les formes triées
    s1_trie = " ".join(sorted(tokens1))
    s2_trie = " ".join(sorted(tokens2))
    return damerau_levenshtein_adaptatif(s1_trie, s2_trie)

