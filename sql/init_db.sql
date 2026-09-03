-- ============================================================
-- ObRail Europe — Modèle Physique de Données (MPD)
-- Base PostgreSQL pour l'entrepôt de données ferroviaires
-- ============================================================
-- Ce script est IDEMPOTENT (rejouable) : DROP puis CREATE,
-- pour respecter l'exigence de reproductibilité du processus ETL.

-- On regroupe tout dans un schéma dédié pour rester propre
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
-- 1. PAYS — référentiel des pays (comparaison transfrontalière)
-- ============================================================
CREATE TABLE pays (
    code_pays     CHAR(2) PRIMARY KEY,       -- code ISO 3166-1 alpha-2 (FR, DE, AT...)
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
-- 3. GARE — référentiel unique des gares
-- ============================================================
CREATE TABLE gare (
    id_gare       SERIAL PRIMARY KEY,
    nom_gare      VARCHAR(150) NOT NULL,
    code_pays     CHAR(2) NOT NULL REFERENCES pays(code_pays),
    latitude      NUMERIC(9,6),
    longitude     NUMERIC(9,6),
    UNIQUE (nom_gare, code_pays)              -- évite les doublons de gares
);

-- ============================================================
-- 4. LIGNE — type de service commercial (rattaché à un opérateur)
-- ============================================================
CREATE TABLE ligne (
    id_ligne      SERIAL PRIMARY KEY,
    nom_ligne     VARCHAR(150) NOT NULL,
    type_train    VARCHAR(60) NOT NULL,       -- ex: 'Intercité de nuit', 'TGV', 'Régional'
    id_operateur  INTEGER NOT NULL REFERENCES operateur(id_operateur),
    UNIQUE (nom_ligne, id_operateur)
);

-- ============================================================
-- 5. SOURCE_DONNEES — traçabilité (exigence RGPD/qualité)
-- ============================================================
CREATE TABLE source_donnees (
    id_source     SERIAL PRIMARY KEY,
    nom_source    VARCHAR(100) NOT NULL UNIQUE,  -- ex: 'SNCF GTFS', 'Back-on-Track'
    url_source    TEXT,
    date_extraction DATE NOT NULL DEFAULT CURRENT_DATE
);

-- ============================================================
-- 6. DESSERTE — table centrale : un trajet précis (fait analysé)
-- ============================================================
CREATE TABLE desserte (
    trip_id             VARCHAR(150) PRIMARY KEY,  -- identifiant natif de la source (ex: GTFS trip_id, jusqu'a 106 caracteres observes)
    id_ligne            INTEGER NOT NULL REFERENCES ligne(id_ligne),
    id_gare_origine     INTEGER NOT NULL REFERENCES gare(id_gare),
    id_gare_destination INTEGER NOT NULL REFERENCES gare(id_gare),
    service_type        VARCHAR(10) NOT NULL CHECK (service_type IN ('Jour', 'Nuit')),
    heure_depart         TIME NOT NULL,
    heure_arrivee        TIME NOT NULL,
    distance_km          NUMERIC(8,2) CHECK (distance_km >= 0),
    duree_h              NUMERIC(5,2) CHECK (duree_h >= 0),
    emission_gco2e_pkm    NUMERIC(6,2),          -- g CO2e par passager-km
    emission_totale_gco2e NUMERIC(10,2),
    frequence_semaine     SMALLINT CHECK (frequence_semaine BETWEEN 0 AND 7),
    traction              VARCHAR(20) CHECK (traction IN ('electrique', 'diesel', 'mixte')),
    id_source             INTEGER NOT NULL REFERENCES source_donnees(id_source),
    CHECK (id_gare_origine <> id_gare_destination)  -- règle métier : pas de trajet gare→elle-même
);

-- Index pour accélérer les requêtes analytiques (API + dashboard)
CREATE INDEX idx_desserte_service_type ON desserte(service_type);
CREATE INDEX idx_desserte_origine ON desserte(id_gare_origine);
CREATE INDEX idx_desserte_destination ON desserte(id_gare_destination);

-- ============================================================
-- 7. LOG_QUALITE — historique des exécutions ETL
--    (alimente le tableau de bord de contrôle qualité)
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

COMMENT ON TABLE desserte IS 'Table centrale : une ligne = un trajet ferroviaire précis (jour ou nuit)';
COMMENT ON TABLE log_qualite IS 'Traçabilité qualité : une ligne par exécution du pipeline ETL';