"""
Query functions: one function per API need, each a single parametrized
SQL statement joining the star schema back into a flat, readable shape.
Kept separate from main.py so route handlers stay thin and each query
can be unit-tested or reused independently.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

BASE_SELECT = """
    SELECT
        d.trip_id, l.nom_ligne, l.type_train, o.nom_operateur,
        go.nom_gare AS gare_origine, po.nom_pays AS pays_origine,
        gd.nom_gare AS gare_destination, pdest.nom_pays AS pays_destination,
        d.service_type, d.heure_depart, d.heure_arrivee, d.distance_km, d.duree_h,
        d.emission_gco2e_pkm, d.emission_totale_gco2e, d.frequence_semaine,
        d.traction, s.nom_source
    FROM obrail.desserte d
    JOIN obrail.ligne l           ON d.id_ligne = l.id_ligne
    JOIN obrail.operateur o       ON l.id_operateur = o.id_operateur
    JOIN obrail.gare go           ON d.id_gare_origine = go.id_gare
    JOIN obrail.pays po           ON go.code_pays = po.code_pays
    JOIN obrail.gare gd           ON d.id_gare_destination = gd.id_gare
    JOIN obrail.pays pdest        ON gd.code_pays = pdest.code_pays
    JOIN obrail.source_donnees s  ON d.id_source = s.id_source
"""


def _build_filters(
    ville_depart: str | None,
    ville_arrivee: str | None,
    type_train: str | None,
    service_type: str | None,
    pays_origine: str | None,
    pays_destination: str | None,
) -> tuple[str, dict]:
    """Build a WHERE clause + bound params from optional filters.

    Every value is passed as a bound parameter (never string-interpolated
    into the SQL), which is what makes this safe from SQL injection even
    though the filters come straight from user-supplied query parameters.
    """
    clauses = []
    params: dict = {}

    if ville_depart:
        clauses.append("go.nom_gare ILIKE :ville_depart")
        params["ville_depart"] = f"%{ville_depart}%"
    if ville_arrivee:
        clauses.append("gd.nom_gare ILIKE :ville_arrivee")
        params["ville_arrivee"] = f"%{ville_arrivee}%"
    if type_train:
        clauses.append("l.type_train ILIKE :type_train")
        params["type_train"] = f"%{type_train}%"
    if service_type:
        clauses.append("d.service_type = :service_type")
        params["service_type"] = service_type
    if pays_origine:
        clauses.append("po.code_pays = :pays_origine")
        params["pays_origine"] = pays_origine.upper()
    if pays_destination:
        clauses.append("pdest.code_pays = :pays_destination")
        params["pays_destination"] = pays_destination.upper()

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, params


def list_dessertes(
    db: Session,
    ville_depart: str | None = None,
    ville_arrivee: str | None = None,
    type_train: str | None = None,
    service_type: str | None = None,
    pays_origine: str | None = None,
    pays_destination: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    where_sql, params = _build_filters(
        ville_depart, ville_arrivee, type_train, service_type,
        pays_origine, pays_destination,
    )

    count_sql = f"SELECT COUNT(*) FROM obrail.desserte d " \
                f"JOIN obrail.ligne l ON d.id_ligne = l.id_ligne " \
                f"JOIN obrail.gare go ON d.id_gare_origine = go.id_gare " \
                f"JOIN obrail.pays po ON go.code_pays = po.code_pays " \
                f"JOIN obrail.gare gd ON d.id_gare_destination = gd.id_gare " \
                f"JOIN obrail.pays pdest ON gd.code_pays = pdest.code_pays " \
                f"{where_sql}"
    total = db.execute(text(count_sql), params).scalar_one()

    rows_sql = f"{BASE_SELECT} {where_sql} ORDER BY d.heure_depart LIMIT :limit OFFSET :offset"
    rows = db.execute(
        text(rows_sql), {**params, "limit": limit, "offset": offset}
    ).mappings().all()

    return total, rows


def get_desserte(db: Session, trip_id: str):
    row = db.execute(
        text(f"{BASE_SELECT} WHERE d.trip_id = :trip_id"),
        {"trip_id": trip_id},
    ).mappings().first()
    return row


def list_pays(db: Session):
    return db.execute(
        text("SELECT code_pays, nom_pays FROM obrail.pays ORDER BY nom_pays")
    ).mappings().all()


def list_operateurs(db: Session):
    return db.execute(
        text("SELECT id_operateur, nom_operateur FROM obrail.operateur ORDER BY nom_operateur")
    ).mappings().all()


def latest_quality_runs(db: Session, limit: int = 10):
    return db.execute(
        text(
            """
            SELECT id_log, date_execution, nb_lignes_lues, nb_lignes_chargees,
                   nb_doublons_supprimes, nb_valeurs_manquantes, taux_completude_pct
            FROM obrail.log_qualite
            ORDER BY date_execution DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()


def stats_by_operateur(db: Session):
    return db.execute(
        text(
            """
            SELECT o.nom_operateur, COUNT(*) AS nb_dessertes
            FROM obrail.desserte d
            JOIN obrail.ligne l ON d.id_ligne = l.id_ligne
            JOIN obrail.operateur o ON l.id_operateur = o.id_operateur
            GROUP BY o.nom_operateur
            ORDER BY nb_dessertes DESC
            """
        )
    ).mappings().all()


def stats_by_pays(db: Session):
    """Counts dessertes by ORIGIN country - a proxy for "where in Europe
    this data covers", used by the dashboard's geographic coverage view."""
    return db.execute(
        text(
            """
            SELECT p.nom_pays, p.code_pays, COUNT(*) AS nb_dessertes
            FROM obrail.desserte d
            JOIN obrail.gare g ON d.id_gare_origine = g.id_gare
            JOIN obrail.pays p ON g.code_pays = p.code_pays
            GROUP BY p.nom_pays, p.code_pays
            ORDER BY nb_dessertes DESC
            """
        )
    ).mappings().all()
