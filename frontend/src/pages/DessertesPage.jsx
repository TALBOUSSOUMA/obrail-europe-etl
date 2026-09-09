import { useEffect, useMemo, useState } from "react";
import { getDessertes, getGares, getPays, getTypesTrain } from "../api/client";
import ServiceBadge from "../components/ServiceBadge";

const PAGE_SIZE = 20;

const emptyFilters = {
  ville_depart: "",
  ville_arrivee: "",
  type_train: "",
  service_type: "",
  pays_origine: "",
  pays_destination: "",
};

export default function DessertesPage() {
  const [filters, setFilters] = useState(emptyFilters);
  const [appliedFilters, setAppliedFilters] = useState(emptyFilters);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [errorMessage, setErrorMessage] = useState("");
  const [pays, setPays] = useState([]);
  const [gares, setGares] = useState([]);
  const [typesTrain, setTypesTrain] = useState([]);

  useEffect(() => {
    getPays()
      .then(setPays)
      .catch(() => setPays([])); // on failure, the country dropdowns stay empty but the rest still works
    getGares()
      .then(setGares)
      .catch(() => setGares([]));
    getTypesTrain()
      .then(setTypesTrain)
      .catch(() => setTypesTrain([]));
  }, []);

  // 756 stations: some share the same name across different countries
  // (e.g. border stations). Names are deduplicated for the <datalist> -
  // the filter is still an ILIKE on the API side, so the country shown
  // here doesn't matter.
  const nomsGares = useMemo(() => [...new Set(gares.map((g) => g.nom_gare))].sort(), [gares]);

  useEffect(() => {
    setStatus("loading");
    getDessertes({ ...appliedFilters, limit: PAGE_SIZE, offset })
      .then((res) => {
        setData(res);
        setStatus("ready");
      })
      .catch((err) => {
        setErrorMessage(err.message);
        setStatus("error");
      });
  }, [appliedFilters, offset]);

  function handleSubmit(e) {
    e.preventDefault();
    setOffset(0);
    setAppliedFilters(filters);
  }

  function handleReset() {
    setFilters(emptyFilters);
    setAppliedFilters(emptyFilters);
    setOffset(0);
  }

  return (
    <>
      <p className="page-kicker">Consultation</p>
      <h1>Rechercher une desserte</h1>
      <p>
        Filtrez les {" "}
        <strong>{data ? data.total.toLocaleString("fr-FR") : "…"}</strong>{" "}
        dessertes de l'entrepôt par ville, type de train ou pays.
      </p>

      <form className="filters" onSubmit={handleSubmit} role="search" aria-label="Filtrer les dessertes">
        <div className="field">
          <label htmlFor="ville_depart">Ville de départ</label>
          <input
            id="ville_depart"
            type="text"
            list="gares-suggestions"
            placeholder="ex. Paris"
            value={filters.ville_depart}
            onChange={(e) => setFilters({ ...filters, ville_depart: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="ville_arrivee">Ville d'arrivée</label>
          <input
            id="ville_arrivee"
            type="text"
            list="gares-suggestions"
            placeholder="ex. Nice"
            value={filters.ville_arrivee}
            onChange={(e) => setFilters({ ...filters, ville_arrivee: e.target.value })}
          />
        </div>
        {/* Shared by both city fields: a single list of 756 stations to
            load, the browser filters locally based on what is typed. */}
        <datalist id="gares-suggestions">
          {nomsGares.map((nom) => (
            <option key={nom} value={nom} />
          ))}
        </datalist>
        <div className="field">
          <label htmlFor="type_train">Type de train</label>
          <select
            id="type_train"
            value={filters.type_train}
            onChange={(e) => setFilters({ ...filters, type_train: e.target.value })}
          >
            <option value="">Tous</option>
            {typesTrain.map((t) => (
              <option key={t.type_train} value={t.type_train}>
                {t.type_train}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="service_type">Service</label>
          <select
            id="service_type"
            value={filters.service_type}
            onChange={(e) => setFilters({ ...filters, service_type: e.target.value })}
          >
            <option value="">Tous</option>
            <option value="Jour">Jour</option>
            <option value="Nuit">Nuit</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="pays_origine">Pays de départ</label>
          <select
            id="pays_origine"
            value={filters.pays_origine}
            onChange={(e) => setFilters({ ...filters, pays_origine: e.target.value })}
          >
            <option value="">Tous les pays</option>
            {pays.map((p) => (
              <option key={p.code_pays} value={p.code_pays}>
                {p.nom_pays}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="pays_destination">Pays d'arrivée</label>
          <select
            id="pays_destination"
            value={filters.pays_destination}
            onChange={(e) => setFilters({ ...filters, pays_destination: e.target.value })}
          >
            <option value="">Tous les pays</option>
            {pays.map((p) => (
              <option key={p.code_pays} value={p.code_pays}>
                {p.nom_pays}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className="primary">
          Rechercher
        </button>
        <button type="button" className="secondary" onClick={handleReset}>
          Réinitialiser
        </button>
      </form>

      <div aria-live="polite">
        {status === "loading" && <p className="state-message">Chargement des dessertes…</p>}
        {status === "error" && (
          <p className="state-message error">
            Impossible de charger les dessertes : {errorMessage}. Vérifiez que l'API est démarrée.
          </p>
        )}
        {status === "ready" && data.resultats.length === 0 && (
          <p className="state-message">Aucune desserte ne correspond à ces critères.</p>
        )}
        {status === "ready" && data.resultats.length > 0 && (
          <>
            <table>
              <caption>
                Résultats {offset + 1}–{offset + data.resultats.length} sur {data.total.toLocaleString("fr-FR")}
              </caption>
              <thead>
                <tr>
                  <th scope="col">Ligne</th>
                  <th scope="col">Origine</th>
                  <th scope="col">Destination</th>
                  <th scope="col">Service</th>
                  <th scope="col">Départ</th>
                  <th scope="col">Arrivée</th>
                  <th scope="col">Distance</th>
                  <th scope="col">Opérateur</th>
                </tr>
              </thead>
              <tbody>
                {data.resultats.map((d) => (
                  <tr key={d.trip_id}>
                    <td>{d.nom_ligne}</td>
                    <td>
                      {d.gare_origine} <span className="muted-inline">({d.nom_pays_origine})</span>
                    </td>
                    <td>
                      {d.gare_destination} <span className="muted-inline">({d.nom_pays_destination})</span>
                    </td>
                    <td>
                      <ServiceBadge type={d.service_type} />
                    </td>
                    <td>{d.heure_depart?.slice(0, 5)}</td>
                    <td>{d.heure_arrivee?.slice(0, 5)}</td>
                    <td>{d.distance_km != null ? `${d.distance_km} km` : "—"}</td>
                    <td>{d.nom_operateur}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pagination">
              <button
                type="button"
                className="secondary"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                ← Précédent
              </button>
              <span>
                Page {Math.floor(offset / PAGE_SIZE) + 1} sur {Math.max(1, Math.ceil(data.total / PAGE_SIZE))}
              </span>
              <button
                type="button"
                className="secondary"
                disabled={offset + PAGE_SIZE >= data.total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Suivant →
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
