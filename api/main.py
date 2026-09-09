"""
ObRail Europe - REST API (deliverable #4 of the specifications).

Exposes the desserte (rail service) warehouse for consultation, filterable
by departure city / arrival city / train type, as explicitly required.
Auto-generated interactive docs are available at /docs (Swagger UI) -
this is the "clear technical documentation, including request examples"
the specifications ask for; FastAPI generates it from the type hints and
docstrings below, so it never goes stale relative to the actual code.

Run locally with:
    uvicorn main:app --reload --port 8001
(port 8001, not 8000, to avoid clashing with the group project's API
already running in Docker on this machine)
"""

import logging
import sys
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

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

logger = logging.getLogger("obrail.api")


@app.exception_handler(DBAPIError)
async def database_unavailable_handler(request: Request, exc: DBAPIError):
    """Post-incident fix (see docs/INCIDENT_POSTMORTEM.md).

    Before this handler, an unreachable database (container stopped,
    network outage...) surfaced as a bare 500 Internal Server Error, with
    no actionable message for the client and no clear log line to
    diagnose it - exactly the kind of incident monitoring is supposed to
    help detect and resolve quickly. Now: an explicit 503 HTTP response
    (the client knows it should retry, this isn't a mistake on its part)
    + a dedicated, easily grep-able log line, instead of a raw Python
    trace spanning dozens of lines.
    """
    logger.error("Base de donnees injoignable sur %s %s : %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "Service temporairement indisponible : impossible de joindre la base de "
                "donnees. Reessayez dans quelques instants."
            )
        },
    )

# Digital accessibility / interoperability: allows the dashboard (and any
# other third-party client) to consume the API from a different port/domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Supervision (the "monitoring" deliverable of the specifications): exposes
# standard Prometheus metrics on /metrics (request count, latency, status
# codes per endpoint) without a single line of manual code - the library
# instruments every FastAPI route automatically. Scraped by the "prometheus"
# service in docker-compose and visualized in Grafana (see monitoring/README.md).
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/", tags=["meta"])
def root():
    return {
        "service": "ObRail Europe API",
        "docs": "/docs",
        "endpoints": [
            "/dessertes", "/dessertes/{trip_id}", "/pays", "/operateurs",
            "/gares", "/types-train", "/qualite",
        ],
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
        None, description="Filter on the departure station (partial match, e.g. 'Paris')"
    ),
    ville_arrivee: str | None = Query(
        None, description="Filter on the arrival station (partial match, e.g. 'Nice')"
    ),
    type_train: str | None = Query(
        None, description="Filter on the train type (e.g. 'Regional', 'TGV inOui', 'Intercites de nuit')"
    ),
    service_type: str | None = Query(
        None, description="'Jour' (day) or 'Nuit' (night)"
    ),
    pays_origine: str | None = Query(
        None, description="ISO country code of departure, e.g. 'FR'"
    ),
    pays_destination: str | None = Query(
        None, description="ISO country code of arrival, e.g. 'CH'"
    ),
    limit: int = Query(50, ge=1, le=500, description="Number of results (max 500)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """List rail services, with optional filters.

    Example: `/dessertes?ville_depart=Paris&service_type=Nuit&limit=10`
    returns the first 10 night trains departing from a Paris-area station.
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
    """Retrieve one specific rail service by its native identifier (trip_id)."""
    row = crud.get_desserte(db, trip_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Desserte '{trip_id}' introuvable")
    return schemas.DesserteOut.model_validate(dict(row))


@app.get("/pays", response_model=list[schemas.PaysOut], tags=["referentiels"])
def get_pays(db: Session = Depends(get_db)):
    """List of countries present in the data warehouse."""
    return [schemas.PaysOut.model_validate(dict(r)) for r in crud.list_pays(db)]


@app.get("/operateurs", response_model=list[schemas.OperateurOut], tags=["referentiels"])
def get_operateurs(db: Session = Depends(get_db)):
    """List of rail operators (SNCF, OBB, Trenitalia...)."""
    return [schemas.OperateurOut.model_validate(dict(r)) for r in crud.list_operateurs(db)]


@app.get("/gares", response_model=list[schemas.GareOut], tags=["referentiels"])
def get_gares(db: Session = Depends(get_db)):
    """Station reference data (756 rows) - feeds the frontend's
    departure/arrival city filter autocomplete (too many stations for a
    classic dropdown, a <datalist> is a better fit)."""
    return [schemas.GareOut.model_validate(dict(r)) for r in crud.list_gares(db)]


@app.get("/types-train", response_model=list[schemas.TypeTrainOut], tags=["referentiels"])
def get_types_train(db: Session = Depends(get_db)):
    """Distinct train types present in the data warehouse - feeds the
    frontend's 'Type de train' dropdown (a short, closed list, unlike
    stations)."""
    return [schemas.TypeTrainOut.model_validate(dict(r)) for r in crud.list_types_train(db)]


@app.get("/qualite", response_model=list[schemas.QualiteRunOut], tags=["qualite"])
def get_quality_runs(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """History of ETL pipeline runs - feeds the quality-control dashboard
    requested by the specifications."""
    return [schemas.QualiteRunOut.model_validate(dict(r)) for r in crud.latest_quality_runs(db, limit)]


@app.get("/stats/operateurs", response_model=list[schemas.OperateurStatOut], tags=["statistiques"])
def get_stats_operateurs(db: Session = Depends(get_db)):
    """Number of rail services per operator - feeds the dashboard."""
    return [schemas.OperateurStatOut.model_validate(dict(r)) for r in crud.stats_by_operateur(db)]


@app.get("/stats/pays", response_model=list[schemas.PaysStatOut], tags=["statistiques"])
def get_stats_pays(db: Session = Depends(get_db)):
    """Number of rail services per departure country - feeds the
    geographic coverage shown in the dashboard."""
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
    """Predicts the weekly frequency of a hypothetical rail service
    (TPRE622: integrating the learning model into the application).

    Example: a TGV inOui Paris-Marseille (850 km, 6h30, SNCF, FR->FR)
    will predict a plausible weekly frequency for this type of service.
    """
    try:
        result = predict_frequence(**payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Prediction impossible: {e}")
    return PredictionResponse(frequence_semaine_predite=result)
