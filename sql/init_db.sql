-- ============================================================
-- ObRail Europe — Physical Data Model (PDM)
-- PostgreSQL database for the rail data warehouse
-- ============================================================
-- This script is IDEMPOTENT (replayable): DROP then CREATE, to meet
-- the ETL process's reproducibility requirement.

-- Everything is grouped into a dedicated schema to stay clean
CREATE SCHEMA IF NOT EXISTS obrail;
SET search_path TO obrail;

DROP TABLE IF EXISTS log_qualite CASCADE;
DROP TABLE IF EXISTS desserte CASCADE;
DROP TABLE IF EXISTS source_donnees CASCADE;
DROP TABLE IF EXISTS ligne CASCADE;
DROP TABLE IF EXISTS gare CASCADE;
DROP TABLE IF EXISTS operateur CASCADE;
DROP TABLE IF EXISTS pays CASCADE;

-- ============================================================
-- 1. PAYS — country reference data (cross-border comparison)
-- ============================================================
CREATE TABLE pays (
    code_pays     CHAR(2) PRIMARY KEY,       -- ISO 3166-1 alpha-2 code (FR, DE, AT...)
    nom_pays      VARCHAR(100) NOT NULL
);

-- ============================================================
-- 2. OPERATEUR — SNCF, ÖBB, DB, Trenitalia...
-- ============================================================
CREATE TABLE operateur (
    id_operateur  SERIAL PRIMARY KEY,
    nom_operateur VARCHAR(100) NOT NULL UNIQUE,
    code_pays     CHAR(2) REFERENCES pays(code_pays)
);

-- ============================================================
-- 3. GARE — unique station reference data
-- ============================================================
CREATE TABLE gare (
    id_gare       SERIAL PRIMARY KEY,
    nom_gare      VARCHAR(150) NOT NULL,
    code_pays     CHAR(2) NOT NULL REFERENCES pays(code_pays),
    latitude      NUMERIC(9,6),
    longitude     NUMERIC(9,6),
    UNIQUE (nom_gare, code_pays)              -- avoids duplicate stations
);

-- ============================================================
-- 4. LIGNE — commercial service type (attached to an operator)
-- ============================================================
CREATE TABLE ligne (
    id_ligne      SERIAL PRIMARY KEY,
    nom_ligne     VARCHAR(150) NOT NULL,
    type_train    VARCHAR(60) NOT NULL,       -- e.g. 'Intercite de nuit', 'TGV', 'Regional'
    id_operateur  INTEGER NOT NULL REFERENCES operateur(id_operateur),
    UNIQUE (nom_ligne, id_operateur)
);

-- ============================================================
-- 5. SOURCE_DONNEES — traceability (RGPD/quality requirement)
-- ============================================================
CREATE TABLE source_donnees (
    id_source     SERIAL PRIMARY KEY,
    nom_source    VARCHAR(100) NOT NULL UNIQUE,  -- e.g. 'SNCF GTFS', 'Back-on-Track'
    url_source    TEXT,
    date_extraction DATE NOT NULL DEFAULT CURRENT_DATE
);

-- ============================================================
-- 6. DESSERTE — central table: one precise rail service (analyzed fact)
-- ============================================================
CREATE TABLE desserte (
    trip_id             VARCHAR(150) PRIMARY KEY,  -- native identifier from the source (e.g. GTFS trip_id, up to 106 characters observed)
    id_ligne            INTEGER NOT NULL REFERENCES ligne(id_ligne),
    id_gare_origine     INTEGER NOT NULL REFERENCES gare(id_gare),
    id_gare_destination INTEGER NOT NULL REFERENCES gare(id_gare),
    service_type        VARCHAR(10) NOT NULL CHECK (service_type IN ('Jour', 'Nuit')),
    heure_depart         TIME NOT NULL,
    heure_arrivee        TIME NOT NULL,
    distance_km          NUMERIC(8,2) CHECK (distance_km >= 0),
    duree_h              NUMERIC(5,2) CHECK (duree_h >= 0),
    emission_gco2e_pkm    NUMERIC(6,2),          -- g CO2e per passenger-km
    emission_totale_gco2e NUMERIC(10,2),
    frequence_semaine     SMALLINT CHECK (frequence_semaine BETWEEN 0 AND 7),
    traction              VARCHAR(20) CHECK (traction IN ('electrique', 'diesel', 'mixte')),
    id_source             INTEGER NOT NULL REFERENCES source_donnees(id_source),
    CHECK (id_gare_origine <> id_gare_destination)  -- business rule: no station->itself trip
);

-- Indexes to speed up analytical queries (API + dashboard)
CREATE INDEX idx_desserte_service_type ON desserte(service_type);
CREATE INDEX idx_desserte_origine ON desserte(id_gare_origine);
CREATE INDEX idx_desserte_destination ON desserte(id_gare_destination);

-- ============================================================
-- 7. LOG_QUALITE — ETL run history
--    (feeds the quality control dashboard)
-- ============================================================
CREATE TABLE log_qualite (
    id_log               SERIAL PRIMARY KEY,
    date_execution        TIMESTAMP NOT NULL DEFAULT NOW(),
    nb_lignes_lues         INTEGER,
    nb_lignes_chargees      INTEGER,
    nb_doublons_supprimes   INTEGER,
    nb_valeurs_manquantes   INTEGER,
    taux_completude_pct     NUMERIC(5,2)
);

COMMENT ON TABLE desserte IS 'Central table: one row = one precise rail service (day or night)';
COMMENT ON TABLE log_qualite IS 'Quality traceability: one row per ETL pipeline run';