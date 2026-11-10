#!/usr/bin/env python3
"""Génère la source Autre en UTF-8, sans dépendance externe."""

import argparse
import csv
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile


ENTETE = (
    "ref_fiche", "plateforme", "piece_identite", "patronyme", "autres_noms",
    "date_naissance", "commune_origine", "localite", "contact_tel", "contact_mail",
    "culture", "superficie_ha", "garantie_agricole",
    "type_navire", "port_attache", "garantie_maritime", "code_sexe",
)
NOMS = (
    "Ravélo", "Andriamahery", "Rakotomalala", "Ramanitra",
    "Razafindrano", "Rasoatina", "Randriavola", "Raharisoa",
    "Ranaivo", "Ravelomanana", "Andriatsiry", "Ratsimandresy",
    "Rabemanga", "Rafaraléo", "Rajaonina", "Rasolofo",
)
PRENOMS = (
    "Mialy", "Tiana", "Aina", "Miora", "Lova", "Fara", "Tahiry", "Avotra",
    "Nirina", "Hasina", "Noé", "Léa", "Tahina", "Feno", "Sitraka", "Valisoa",
)
SECONDS_PRENOMS = (
    "Hery", "Soa", "Rija", "Faly", "Nivo", "Kanto", "Voary", "Zo",
    "Kolo", "Tojo", "Miary", "Lanto", "Tsiory", "Haja", "Mamy", "Fanja",
)
VILLES = (
    "Antananarivo", "Toamasina", "Antsirabe", "Mahajanga",
    "Fianarantsoa", "Toliara", "Antsiranana", "Morondava",
    "Sambava", "Ambatondrazaka",
)
CULTURES = (
    ("Riz", ("Inondation", "Cyclone")),
    ("Maïs", ("Sécheresse", "Cyclone")),
    ("Manioc", ("Sécheresse", "Inondation")),
    ("Vanille", ("Cyclone", "Excès de pluie")),
    ("Girofle", ("Cyclone", "Excès de pluie")),
)
NAVIRES = (
    ("Pirogue", ("Corps de navire", "Responsabilité civile")),
    ("Vedette de pêche", ("Corps de navire", "Responsabilité civile")),
    ("Caboteur", ("Corps de navire", "Responsabilité civile", "Cargaison")),
)
PORTS = ("Toamasina", "Mahajanga", "Toliara", "Antsiranana")
# Configuration des deux modes de génération (Complet 2M / Léger 200k)
CONFIGS = {
    "complet": {
        "volume": 2_000_000,
        "fiches_initiales": 1_980_000,
        "commun": 700_000,
        "reprises_communes": 14_000,
        "debut_exclusif": 1_280_001,
        "fichier_defaut": "clients_autre.csv",
    },
    "leger": {
        "volume": 200_000,
        "fiches_initiales": 198_000,
        "commun": 70_000,
        "reprises_communes": 1_400,
        "debut_exclusif": 128_001,
        "fichier_defaut": "clients_autre_leger.csv",
    },
}


def muter_chaine(texte: str, type_faute: int) -> str:
    """Applique une faute de frappe réaliste (suppression, insertion, substitution)."""
    if not texte or len(texte) < 3:
        return texte
    pos = 1 + (type_faute % (len(texte) - 1))
    mode = type_faute % 3
    if mode == 0:  # suppression milieu ou fin
        return texte[:pos] + texte[pos + 1:]
    elif mode == 1:  # insertion / duplication
        return texte[:pos] + texte[pos] + texte[pos:]
    else:  # substitution
        repl = "a" if texte[pos].lower() != "a" else "e"
        if texte[pos].isupper():
            repl = repl.upper()
        return texte[:pos] + repl + texte[pos + 1:]


def muter_chiffres(chiffres: str, type_faute: int) -> str:
    """Applique une faute numérique sur CIN ou Téléphone (11/13 car, ou chiffre changé)."""
    if not chiffres or len(chiffres) < 5:
        return chiffres
    pos = len(chiffres) - 1 - (type_faute % (len(chiffres) - 4))
    mode = type_faute % 3
    if mode == 0:  # suppression d'un chiffre
        return chiffres[:pos] + chiffres[pos + 1:]
    elif mode == 1:  # insertion d'un chiffre
        return chiffres[:pos] + chiffres[pos] + chiffres[pos:]
    else:  # substitution
        nouveau = str((int(chiffres[pos]) + 1) % 10)
        return chiffres[:pos] + nouveau + chiffres[pos + 1:]


def lignes(mode: str = "complet"):
    cfg = CONFIGS[mode]
    volume = cfg["volume"]
    fiches_initiales = cfg["fiches_initiales"]
    commun = cfg["commun"]
    reprises_communes = cfg["reprises_communes"]
    debut_exclusif = cfg["debut_exclusif"]

    dates = [
        (date(1960, 1, 1) + timedelta(days=jour)).strftime("%d-%m-%Y")
        for jour in range(16_384)
    ]
    for numero in range(1, volume + 1):
        rang = ((numero - 1) * 193 + 72_821) % volume + 1
        reprise = rang > fiches_initiales
        rang_initial = rang
        if reprise:
            rang_initial = rang - fiches_initiales
            if rang_initial > reprises_communes:
                rang_initial += commun - reprises_communes

        cle = rang_initial
        if rang_initial > commun:
            cle = debut_exclusif + rang_initial - commun - 1

        empreinte_sexe = sha256(f"sexe:{cle}".encode("ascii")).digest()
        code_sexe = "M" if empreinte_sexe[0] >= 128 else "F"

        # Une paire peut partager l'état civil, et d'autres paires un numéro de contact.
        profil = cle - (cle % 101 == 0)
        contact = cle - (cle % 67 == 0)
        mix = (profil * 131_071 + 12_345) % 67_108_864
        signal = cle + 9 + 7 * reprise
        pont = cle % 211 == 0

        nom_canonique = NOMS[mix % 16]
        nom = nom_canonique
        if signal % 4 == 0:
            nom = nom.upper()
        if signal % 23 == 0:
            nom = f" {nom} "

        prenom = PRENOMS[(mix // 16) % 16]
        second = SECONDS_PRENOMS[(mix // 256) % 16]
        prenoms = f"{second} {prenom}" if signal % 11 == 0 else f"{prenom} {second}"
        naissance = dates[mix // 4096]
        commune = "" if signal % 37 == 0 else VILLES[(mix // 65_536) % len(VILLES)]
        rang_ville = cle * 37 // 13 + 3 * (signal % 53 == 0)
        localite = VILLES[rang_ville % len(VILLES)].lower()

        cin = ""
        if not pont and signal % 13 != 0:
            cin = str(800_000_000_000 + (cle * 73 + 17) % 10_000_000)

        telephone = ""
        if not pont and signal % 17 != 0:
            digits = f"00{(contact * 131 + 29) % 10_000_000:07d}"
            telephone = f"{digits[:2]}-{digits[2:4]}-{digits[4:7]}-{digits[7:]}"

        email = ""
        if pont or signal % 19 != 0:
            alias = f"{prenom}.{nom_canonique}".lower().replace("é", "e")
            suffixe = (cle * 197 + 53) % 10_000_000
            domaine = "courrier-ile.test" if cle % 3 == 0 else "boite-mada.test"
            email = f"{alias}.{suffixe:07d}@{domaine}"
        if signal % 7 == 0:
            email = email.upper()

        # Injection déterministe de fautes d'orthographe et numériques sur ~5 % des fiches
        if numero % 20 == 0:
            cible = (numero // 20) % 5
            type_faute = numero // 100
            if cible == 0:
                nom = muter_chaine(nom, type_faute)
            elif cible == 1:
                prenoms = muter_chaine(prenoms, type_faute)
            elif cible == 2:
                localite = muter_chaine(localite, type_faute)
            elif cible == 3 and cin:
                cin = muter_chiffres(cin, type_faute)
            elif cible == 4 and telephone:
                raw_tel = telephone.replace("-", "")
                telephone = muter_chiffres(raw_tel, type_faute)

        dossier = numero // 2
        if (numero + reprise) % 2:
            plateforme = "AGRICOLE"
            quotient, choix = divmod(dossier, len(CULTURES))
            culture, garanties = CULTURES[choix]
            garantie_agricole = garanties[quotient % len(garanties)]
            centiemes_ha = 50 + (dossier * 43) % 1501
            superficie = f"{centiemes_ha // 100},{centiemes_ha % 100:02d}"
            navire, port, garantie_maritime = "", "", ""
        else:
            plateforme = "MARITIME"
            culture, superficie, garantie_agricole = "", "", ""
            quotient, choix = divmod(dossier, len(NAVIRES))
            navire, garanties = NAVIRES[choix]
            garantie_maritime = garanties[quotient % len(garanties)]
            port = PORTS[dossier % len(PORTS)]

        yield (
            f"EXT-{5_000_000 + numero}", plateforme, cin, nom, prenoms,
            naissance, commune, localite, telephone, email,
            culture, superficie, garantie_agricole, navire, port, garantie_maritime, code_sexe,
        )


def generer(sortie: Path, mode: str = "complet"):
    # Écrit à côté de la cible pour publier le fichier complet en une seule opération.
    cfg = CONFIGS[mode]
    with NamedTemporaryFile(
        dir=sortie.parent, prefix=f".{sortie.name}.", suffix=".tmp",
        mode="w", encoding="utf-8", newline="", delete=False,
    ) as fichier:
        temporaire = Path(fichier.name)
        try:
            writer = csv.writer(fichier, delimiter=";", lineterminator="\n")
            writer.writerow(ENTETE)
            writer.writerows(lignes(mode=mode))
            fichier.close()
            temporaire.replace(sortie)
        finally:
            fichier.close()
            temporaire.unlink(missing_ok=True)


if __name__ == "__main__":
    dossier_data = Path(__file__).resolve().parents[1] / "data"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=["complet", "leger"], default="complet",
        help="mode du dataset : 'complet' (2 000 000 fiches) ou 'leger' (200 000 fiches)",
    )
    parser.add_argument(
        "--sortie", type=Path, default=None,
        help="chemin du CSV à écrire ou à remplacer (déduit du mode par défaut)",
    )
    args = parser.parse_args()
    dossier_data.mkdir(exist_ok=True)
    fichier_cible = args.sortie or (dossier_data / CONFIGS[args.mode]["fichier_defaut"])
    generer(fichier_cible, mode=args.mode)
    nb_lignes = CONFIGS[args.mode]["volume"]
    print(f"[{args.mode.upper()}] {nb_lignes:,} lignes écrites dans {fichier_cible}".replace(",", " "))
