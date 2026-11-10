"""Application FastAPI de visualisation et de gestion du référentiel NEW_ID / UID."""

import json
import os
from pathlib import Path
from secrets import compare_digest
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from tp_data_dla.config import get_etl_connection, verrouiller_ecritures_etl

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(
    title="Plateforme Référentiel Client NEW_ID",
    description="Exploration des fiches sources intactes, regroupements par UID et validation humaine.",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

auth_validation = HTTPBasic(realm="Validation du TP", auto_error=False)


def exiger_operateur(
    request: Request,
    acces: Optional[HTTPBasicCredentials] = Depends(auth_validation),
) -> None:
    utilisateur = os.getenv("TP_VALIDATION_USER")
    mot_de_passe = os.getenv("TP_VALIDATION_PASSWORD")
    if not utilisateur or not mot_de_passe:
        raise HTTPException(status_code=503, detail="Accès opérateur non configuré")
    utilisateur_valide = compare_digest((acces.username if acces else "").encode(), utilisateur.encode())
    mot_de_passe_valide = compare_digest((acces.password if acces else "").encode(), mot_de_passe.encode())
    if not (utilisateur_valide and mot_de_passe_valide):
        raise HTTPException(status_code=401, detail="Accès opérateur requis",
                            headers={"WWW-Authenticate": 'Basic realm="Validation du TP"'})
    if request.method == "POST":
        origine = request.headers.get("origin")
        if origine is not None and origine != str(request.base_url).rstrip("/"):
            raise HTTPException(status_code=403, detail="Origine de la requête interdite")
        if request.headers.get("sec-fetch-site") in {"cross-site", "same-site"}:
            raise HTTPException(status_code=403, detail="Origine de la requête interdite")


def colonne_uid_presente(cur) -> bool:
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'etl' AND table_name = 'fiches_clients' AND column_name = 'uid'
        );
    """)
    return cur.fetchone()[0]


@app.get("/", response_class=HTMLResponse)
def page_dashboard(request: Request):
    """Tableau de bord : indicateurs globaux du dédoublonnage."""
    with get_etl_connection() as conn:
        with conn.cursor() as cur:
            has_uid_col = colonne_uid_presente(cur)

            uid_expr = "count(DISTINCT uid), count(*) FILTER (WHERE uid IS NOT NULL)" if has_uid_col else "0, 0"

            # Volumes totaux et par source
            cur.execute(f"""
                SELECT
                    count(*),
                    count(*) FILTER (WHERE source_system = 'AUTO'),
                    count(*) FILTER (WHERE source_system = 'LIFE'),
                    count(*) FILTER (WHERE source_system = 'AUTRE'),
                    {uid_expr}
                FROM etl.fiches_clients;
            """)
            total, auto_cnt, life_cnt, autre_cnt, uids_cnt, uid_non_null = cur.fetchone()

            # Distribution des tailles de clusters (groupes UID)
            cur.execute("""
                SELECT nb_fiches, count(*)
                FROM etl.groupes_uid
                GROUP BY nb_fiches
                ORDER BY nb_fiches;
            """)
            distribution_tailles = cur.fetchall()

            # État de la file de validation
            cur.execute("""
                SELECT
                    count(*) FILTER (WHERE statut = 'A_VALIDER'),
                    count(*) FILTER (WHERE statut = 'VALIDE_HUMAIN'),
                    count(*) FILTER (WHERE statut = 'REJETE_HUMAIN'),
                    count(*) FILTER (WHERE motif = 'CONFLIT_CIN' AND statut = 'A_VALIDER'),
                    count(*) FILTER (WHERE motif LIKE 'AMBIGU_%' AND statut = 'A_VALIDER'),
                    count(*) FILTER (WHERE motif = 'SUSPICION_FAUTE_CIN' AND statut = 'A_VALIDER')
                FROM etl.file_validation;
            """)
            val_a_traiter, val_valides, val_rejetes, conflits_cin, ambigus_c4, suspicions_cin = cur.fetchone()

            # Dernier run ETL / Union-Find
            cur.execute("""
                SELECT phase, statut, duree_secondes, lignes_traitees, details, horodatage
                FROM etl.journal_executions
                ORDER BY id_run DESC LIMIT 5;
            """)
            derniers_runs = cur.fetchall()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "total": total,
            "auto_cnt": auto_cnt,
            "life_cnt": life_cnt,
            "autre_cnt": autre_cnt,
            "uids_cnt": uids_cnt,
            "uid_non_null": uid_non_null,
            "distribution_tailles": distribution_tailles,
            "val_a_traiter": val_a_traiter,
            "val_valides": val_valides,
            "val_rejetes": val_rejetes,
            "conflits_cin": conflits_cin,
            "ambigus_c4": ambigus_c4,
            "suspicions_cin": suspicions_cin,
            "derniers_runs": derniers_runs,
        },
    )


@app.get("/recherche", response_class=HTMLResponse)
def page_recherche(
    request: Request,
    q: Optional[str] = Query(default="", description="Terme de recherche"),
    page: int = Query(default=1, ge=1),
):
    """Recherche multicritères et consultation des groupes UID."""
    limit = 25
    offset = (page - 1) * limit
    resultats = []
    total_trouve = 0
    terme = (q or "").strip()

    if terme:
        with get_etl_connection() as conn:
            with conn.cursor() as cur:
                # Recherche par UID exact ou par correspondance sur les fiches
                cur.execute("""
                    WITH cibles AS (
                        SELECT DISTINCT uid
                        FROM etl.fiches_clients
                        WHERE uid::text = %s
                           OR source_ref = %s
                           OR cin_norm = %s
                           OR nom_norm ILIKE %s
                           OR tel_norm = %s
                           OR mail_norm = %s
                        LIMIT 100
                    )
                    SELECT g.uid, g.nb_fiches, g.sources, g.cin_principal,
                           g.nom_principal, g.prenoms_principal, g.date_naiss_principale, g.ville_principale
                    FROM etl.groupes_uid g
                    JOIN cibles c ON c.uid = g.uid
                    ORDER BY g.nb_fiches DESC;
                """, (
                    terme,
                    terme,
                    terme.replace(" ", "").replace("-", ""),
                    f"%{terme}%",
                    terme.replace(" ", "").replace("-", ""),
                    terme.lower(),
                ))
                tous = cur.fetchall()
                total_trouve = len(tous)
                resultats = tous[offset:offset + limit]

    return templates.TemplateResponse(
        request=request,
        name="recherche.html",
        context={
            "q": terme,
            "page": page,
            "limit": limit,
            "total_trouve": total_trouve,
            "resultats": resultats,
        },
    )


@app.get("/groupes/{uid_val}", response_class=HTMLResponse)
def page_detail_uid(request: Request, uid_val: str):
    """Affiche toutes les fiches sources individuelles rattachées à un UID donné."""
    with get_etl_connection() as conn:
        with conn.cursor() as cur:
            # Récupération du groupe
            cur.execute("""
                SELECT uid, nb_fiches, sources, cin_principal, nom_principal,
                       prenoms_principal, date_naiss_principale, ville_principale, statut
                FROM etl.groupes_uid
                WHERE uid::text = %s;
            """, (uid_val,))
            groupe = cur.fetchone()
            if not groupe:
                raise HTTPException(status_code=404, detail="Groupe UID introuvable")

            # Récupération des fiches individuelles (intactes)
            cur.execute("""
                SELECT id_fiche, source_system, source_ref,
                       cin_brut, nom_brut, prenoms_brut, date_naiss_brute,
                       lieu_naiss_brut, ville_brute, tel_brut, mail_brut, sexe_brut,
                       details_metier,
                       cin_norm, nom_norm, prenoms_norm, prenoms_trie_norm,
                       date_naiss_norm, lieu_naiss_norm, ville_norm, tel_norm, mail_norm, sexe_norm
                FROM etl.fiches_clients
                WHERE uid::text = %s
                ORDER BY source_system, id_fiche;
            """, (uid_val,))
            fiches = cur.fetchall()

            # Liens d'historique ou conflits associés
            cur.execute("""
                SELECT id_cas, id_fiche_a, id_fiche_b, motif, regle, score, statut, decision_note
                FROM etl.file_validation
                WHERE uid_a::text = %s OR uid_b::text = %s
                ORDER BY id_cas DESC;
            """, (uid_val, uid_val))
            cas_validation = cur.fetchall()

    return templates.TemplateResponse(
        request=request,
        name="detail_uid.html",
        context={
            "uid": uid_val,
            "groupe": groupe,
            "fiches": fiches,
            "cas_validation": cas_validation,
        },
    )


@app.get("/validation", response_class=HTMLResponse, dependencies=[Depends(exiger_operateur)])
def page_validation(
    request: Request,
    statut: str = Query(default="A_VALIDER"),
    motif: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
):
    """File de validation humaine des cas ambigus et des conflits CIN."""
    limit = 20
    offset = (page - 1) * limit

    with get_etl_connection() as conn:
        with conn.cursor() as cur:
            where = ["statut = %s"]
            params = [statut]
            if motif:
                where.append("motif = %s")
                params.append(motif)

            where_sql = " AND ".join(where)

            cur.execute(f"SELECT count(*) FROM etl.file_validation WHERE {where_sql};", tuple(params))
            total = cur.fetchone()[0]

            uid_a, uid_b = "v.uid_a", "v.uid_b"
            if total and colonne_uid_presente(cur):
                uid_a = "CASE WHEN v.statut = 'A_VALIDER' THEN fa.uid ELSE v.uid_a END"
                uid_b = "CASE WHEN v.statut = 'A_VALIDER' THEN fb.uid ELSE v.uid_b END"
            query = f"""
                SELECT v.id_cas, v.id_fiche_a, v.id_fiche_b, {uid_a}, {uid_b},
                       v.motif, v.regle, v.score, v.statut, v.decision_note,
                       fa.source_system, fa.source_ref, fa.nom_brut, fa.prenoms_brut, fa.cin_brut, fa.tel_brut, fa.mail_brut,
                       fb.source_system, fb.source_ref, fb.nom_brut, fb.prenoms_brut, fb.cin_brut, fb.tel_brut, fb.mail_brut
                FROM etl.file_validation v
                JOIN etl.fiches_clients fa ON fa.id_fiche = v.id_fiche_a
                JOIN etl.fiches_clients fb ON fb.id_fiche = v.id_fiche_b
                WHERE {where_sql}
                ORDER BY v.id_cas DESC
                LIMIT %s OFFSET %s;
            """
            cur.execute(query, tuple(params + [limit, offset]))
            cas = cur.fetchall()

    return templates.TemplateResponse(
        request=request,
        name="validation.html",
        context={
            "statut": statut,
            "motif": motif,
            "page": page,
            "limit": limit,
            "total": total,
            "cas": cas,
        },
    )


@app.post("/api/validation/{id_cas}/decision", dependencies=[Depends(exiger_operateur)])
def post_decision_validation(
    id_cas: int,
    action: str = Form(..., description="'ASSIGNER_MEME_UID' ou 'MAINTENIR_SEPARES'"),
    note: Optional[str] = Form(default=""),
):
    """
    Arbitrage humain d'un cas :
    - ASSIGNER_MEME_UID : Aligne la colonne uid des fiches du groupe B sur celle du groupe A
      (Zéro suppression, zéro altération des autres colonnes !).
    - MAINTENIR_SEPARES : Maintient des uids distincts et archive le cas.
    """
    if action not in {"ASSIGNER_MEME_UID", "MAINTENIR_SEPARES"}:
        raise HTTPException(status_code=400, detail="Action non reconnue")
    with get_etl_connection() as conn:
        with conn.cursor() as cur:
            verrouiller_ecritures_etl(cur)
            cur.execute("""
                SELECT id_fiche_a, id_fiche_b, regle, statut
                FROM etl.file_validation
                WHERE id_cas = %s;
            """, (id_cas,))
            cas = cur.fetchone()
            if not cas:
                raise HTTPException(status_code=404, detail="Cas introuvable")

            id_a, id_b, regle, statut_actuel = cas
            if statut_actuel != "A_VALIDER":
                raise HTTPException(status_code=409, detail="Cas déjà traité")
            if not colonne_uid_presente(cur):
                raise HTTPException(status_code=409, detail="Colonne UID absente")
            cur.execute("""
                SELECT
                    (SELECT uid FROM etl.fiches_clients WHERE id_fiche = %s),
                    (SELECT uid FROM etl.fiches_clients WHERE id_fiche = %s);
            """, (id_a, id_b))
            uid_a, uid_b = cur.fetchone()
            if uid_a is None or uid_b is None:
                raise HTTPException(status_code=409, detail="UID courant manquant")

            if action == "ASSIGNER_MEME_UID" and uid_a != uid_b:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM etl.file_validation v
                        JOIN etl.fiches_clients a ON a.id_fiche = v.id_fiche_a
                        JOIN etl.fiches_clients b ON b.id_fiche = v.id_fiche_b
                        WHERE v.statut = 'REJETE_HUMAIN'
                          AND ((a.uid = %s AND b.uid = %s) OR (a.uid = %s AND b.uid = %s))
                    );
                """, (uid_a, uid_b, uid_b, uid_a))
                if cur.fetchone()[0]:
                    raise HTTPException(status_code=409, detail="Une décision antérieure impose de garder ces groupes séparés")
                # Aligne le UID du groupe B sur le groupe A sans modifier aucune ligne d'origine
                cur.execute("""
                    UPDATE etl.fiches_clients
                    SET uid = %s
                    WHERE uid = %s;
                """, (uid_a, uid_b))

                # Recalcule le résumé du groupe A
                cur.execute("""
                    UPDATE etl.groupes_uid
                    SET nb_fiches = (SELECT count(*) FROM etl.fiches_clients WHERE uid = %s),
                        sources = (SELECT array_agg(DISTINCT source_system) FROM etl.fiches_clients WHERE uid = %s),
                        statut = 'VALIDE_HUMAIN',
                        maj_le = now()
                    WHERE uid = %s;
                """, (uid_a, uid_a, uid_a))

                # Supprime l'entrée d'index obsolète du groupe B
                cur.execute("DELETE FROM etl.groupes_uid WHERE uid = %s;", (uid_b,))

            if action == "ASSIGNER_MEME_UID":
                # Trace le lien de confirmation
                cur.execute("""
                    INSERT INTO etl.liens_rapprochement (uid, id_fiche_a, id_fiche_b, regle, score, valide_par)
                    VALUES (%s, %s, %s, %s, %s, 'HUMAIN');
                """, (uid_a, id_a, id_b, f"VALIDATION_HUMAINE_{regle}", 100))

                # Met à jour le statut du cas
                cur.execute("""
                    UPDATE etl.file_validation
                    SET statut = 'VALIDE_HUMAIN', decision_note = %s, traite_le = now(),
                        uid_a = %s, uid_b = %s
                    WHERE id_cas = %s;
                """, (note or "Attribution du même UID confirmée manuellement", uid_a, uid_b, id_cas))

            else:
                if uid_a == uid_b:
                    raise HTTPException(status_code=409, detail="Les fiches partagent déjà un UID")
                cur.execute("""
                    UPDATE etl.file_validation
                    SET statut = 'REJETE_HUMAIN', decision_note = %s, traite_le = now(),
                        uid_a = %s, uid_b = %s
                    WHERE id_cas = %s;
                """, (note or "Maintien des identités distinctes confirmé", uid_a, uid_b, id_cas))

    return RedirectResponse(url="/validation", status_code=303)
