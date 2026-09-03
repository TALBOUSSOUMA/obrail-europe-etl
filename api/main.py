"""
ObRail Europe - API REST (livrable n.4 du cahier des charges).

Exposes the desserte warehouse for consultation, filterable by
ville de depart / ville d'arrivee / type de train, as explicitly
required. Auto-generated interactive docs are available at /docs
(Swagger UI) - this is the "documentation technique claire, incluant
des exemples de requetes" the cahier des charges asks for; FastAPI
generates it from the type hints and docstrings below, so it never
goes stale relative to the actual code.

Run locally with:
    uvicorn main:app --reload --port 8001
(port 8001, not 8000, to avoid clashing with the group project's API
already running in Docker on this machine)
"""

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ml"))
from predict import predict as predict_frequence  # noqa: E402

import crud
import schemas
from database import get_db

app = FastAPI(
    title="ObRail Europe API",
    description=(
        "API de consultation de l'entrepot de donnees ferroviaires ObRail Europe. "
        "Interroge les dessertes jour/nuit collectees depuis le GTFS SNCF et la "
        "Back-on-Track Open Night Train Database."
    ),
    version="1.0.0",
)

# Accessibilite numerique / interoperabilite : autorise le dashboard
# (et tout autre client tiers) a consommer l'API depuis un autre port/domaine.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", tags=["meta"])
def root():
    return {
        "service": "ObRail Europe API",
        "docs": "/docs",
        "endpoints": ["/dessertes", "/dessertes/{trip_id}", "/pays", "/operateurs", "/qualite"],
    }


@app.get("/health", tags=["meta"])
def health(db: Session = Depends(get_db)):
    """Liveness/readiness check: confirms the API can actually reach PostgreSQL,
    not just that the process is running."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/dessertes", response_model=schemas.DesserteListOut, tags=["dessertes"])
def get_dessertes(
    ville_depart: str | None = Query(
        None, description="Filtre sur la gare de depart (recherche partielle, ex: 'Paris')"
    ),
    ville_arrivee: str | None = Query(
        None, description="Filtre sur la gare d'arrivee (recherche partielle, ex: 'Nice')"
    ),
    type_train: str | None = Query(
        None, description="Filtre sur le type de train (ex: 'Regional', 'TGV inOui', 'Intercites de nuit')"
    ),
    service_type: str | None = Query(
        None, description="'Jour' ou 'Nuit'"
    ),
    pays_origine: str | None = Query(
        None, description="Code pays ISO de depart, ex: 'FR'"
    ),
    pays_destination: str | None = Query(
        None, description="Code pays ISO d'arrivee, ex: 'CH'"
    ),
    limit: int = Query(50, ge=1, le=500, description="Nombre de resultats (max 500)"),
    offset: int = Query(0, ge=0, description="Decalage pour la pagination"),
    db: Session = Depends(get_db),
):
    """Liste les dessertes ferroviaires, avec filtres optionnels.

    Exemple : `/dessertes?ville_depart=Paris&service_type=Nuit&limit=10`
    renvoie les 10 premiers trains de nuit au depart d'une gare parisienne.
    """
    total, rows = crud.list_dessertes(
        db, ville_depart, ville_arrivee, type_train, service_type,
        pays_origine, pays_destination, limit, offset,
    )
    return schemas.DesserteListOut(
        total=total, limit=limit, offset=offset,
        resultats=[schemas.DesserteOut.model_validate(dict(r)) for r in rows],
    )


@app.get("/dessertes/{trip_id}", response_model=schemas.DesserteOut, tags=["dessertes"])
def get_one_desserte(trip_id: str, db: Session = Depends(get_db)):
    """Recupere une desserte precise par son identifiant natif (trip_id)."""
    row = crud.get_desserte(db, trip_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Desserte '{trip_id}' introuvable")
    return schemas.DesserteOut.model_validate(dict(row))


@app.get("/pays", response_model=list[schemas.PaysOut], tags=["referentiels"])
def get_pays(db: Session = Depends(get_db)):
    """Liste des pays presents dans l'entrepot de donnees."""
    return [schemas.PaysOut.model_validate(dict(r)) for r in crud.list_pays(db)]


@app.get("/operateurs", response_model=list[schemas.OperateurOut], tags=["referentiels"])
def get_operateurs(db: Session = Depends(get_db)):
    """Liste des operateurs ferroviaires (SNCF, OBB, Trenitalia...)."""
    return [schemas.OperateurOut.model_validate(dict(r)) for r in crud.list_operateurs(db)]


@app.get("/qualite", response_model=list[schemas.QualiteRunOut], tags=["qualite"])
def get_quality_runs(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Historique des executions du pipeline ETL - alimente le tableau de
    bord de controle qualite demande par le cahier des charges."""
    return [schemas.QualiteRunOut.model_validate(dict(r)) for r in crud.latest_quality_runs(db, limit)]


@app.get("/stats/operateurs", response_model=list[schemas.OperateurStatOut], tags=["statistiques"])
def get_stats_operateurs(db: Session = Depends(get_db)):
    """Nombre de dessertes par operateur - alimente le tableau de bord."""
    return [schemas.OperateurStatOut.model_validate(dict(r)) for r in crud.stats_by_operateur(db)]


@app.get("/stats/pays", response_model=list[schemas.PaysStatOut], tags=["statistiques"])
def get_stats_pays(db: Session = Depends(get_db)):
    """Nombre de dessertes par pays de depart - alimente la couverture
    geographique affichee dans le tableau de bord."""
    return [schemas.PaysStatOut.model_validate(dict(r)) for r in crud.stats_by_pays(db)]


class PredictionRequest(BaseModel):
    distance_km: float
    duree_h: float
    type_train: str
    service_type: str
    nom_operateur: str
    pays_origine: str
    pays_destination: str


class PredictionResponse(BaseModel):
    frequence_semaine_predite: float
    modele: str = "random_forest"


@app.post("/predict", response_model=PredictionResponse, tags=["ia"])
def predict_endpoint(payload: PredictionRequest):
    """Predit la frequence hebdomadaire d'une desserte hypothetique
    (TPRE622 : integration du modele d'apprentissage dans l'application).

    Exemple : un TGV inOui Paris-Marseille (850 km, 6h30, SNCF, FR->FR)
    predira une frequence hebdomadaire plausible pour ce type de service.
    """
    try:
        result = predict_frequence(**payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Prediction impossible: {e}")
    return PredictionResponse(frequence_semaine_predite=result)
