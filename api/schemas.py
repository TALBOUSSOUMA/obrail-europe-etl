"""
Pydantic schemas: define the JSON shape returned by the API, decoupled
from the SQL column names (French in the DB, kept French here too for
consistency across the whole project - SQL, ETL and API all speak the
same vocabulary, which matters when defending the data model).

Note: field names themselves stay French (e.g. `pays_origine`) to match
the database columns 1:1 - only comments/docstrings are in English.
"""

import datetime
from pydantic import BaseModel, ConfigDict


class DesserteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trip_id: str
    nom_ligne: str
    type_train: str
    nom_operateur: str
    gare_origine: str
    pays_origine: str          # ISO code (e.g. "DE") - consistent with the ?pays_origine= filter on GET /dessertes
    nom_pays_origine: str      # full name (e.g. "Allemagne") - for client-side display
    gare_destination: str
    pays_destination: str      # ISO code
    nom_pays_destination: str  # full name
    service_type: str
    heure_depart: datetime.time
    heure_arrivee: datetime.time
    distance_km: float | None
    duree_h: float | None
    emission_gco2e_pkm: float | None
    emission_totale_gco2e: float | None
    frequence_semaine: float | None
    traction: str | None
    nom_source: str


class DesserteListOut(BaseModel):
    total: int
    limit: int
    offset: int
    resultats: list[DesserteOut]


class PaysOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code_pays: str
    nom_pays: str


class OperateurOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_operateur: int
    nom_operateur: str


class GareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    nom_gare: str
    code_pays: str


class TypeTrainOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    type_train: str


class QualiteRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_log: int
    date_execution: datetime.datetime
    nb_lignes_lues: int
    nb_lignes_chargees: int
    nb_doublons_supprimes: int
    nb_valeurs_manquantes: int
    taux_completude_pct: float


class OperateurStatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    nom_operateur: str
    nb_dessertes: int


class PaysStatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    nom_pays: str
    code_pays: str
    nb_dessertes: int
