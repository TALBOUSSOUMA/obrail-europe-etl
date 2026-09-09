import { useEffect, useState } from "react";
import { getHealth, getQualite, API_URL } from "../api/client";

export default function EtatServicePage() {
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState(null);
  const [runs, setRuns] = useState([]);
  const [runsError, setRunsError] = useState(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((e) => setHealthError(e.message));
    getQualite(10)
      .then(setRuns)
      .catch((e) => setRunsError(e.message));
  }, []);

  const latest = runs[0];

  return (
    <>
      <p className="page-kicker">Supervision</p>
      <h1>État du service</h1>
      <p>
        Disponibilité de l'API et historique des dernières exécutions du pipeline ETL. Pour une supervision
        détaillée (latence, taux d'erreurs par minute), consultez le{" "}
        <a href="http://localhost:3001/d/obrail-api-supervision" target="_blank" rel="noreferrer">
          tableau de bord Grafana
        </a>{" "}
        (identifiants dans le rapport technique).
      </p>

      <h2>Disponibilité de l'API</h2>
      <div className="card" role="status" aria-live="polite">
        {health && (
          <p style={{ margin: 0 }}>
            <span className="status-ok">● Opérationnelle</span> — {API_URL} répond correctement.
          </p>
        )}
        {healthError && (
          <p style={{ margin: 0 }} className="state-message error">
            <span className="status-down">● Indisponible</span> — {healthError}
          </p>
        )}
        {!health && !healthError && <p style={{ margin: 0 }}>Vérification en cours…</p>}
      </div>

      <h2>Historique des exécutions ETL</h2>
      {runsError && <p className="state-message error">Impossible de charger l'historique : {runsError}</p>}
      {!runsError && runs.length === 0 && <p className="state-message">Aucune exécution enregistrée.</p>}
      {latest && (
        <div className="stat-grid">
          <div className="stat-card">
            <span className="value">{latest.nb_lignes_chargees.toLocaleString("fr-FR")}</span>
            <span className="label">Lignes chargées (dernier passage)</span>
          </div>
          <div className="stat-card">
            <span className="value">{latest.taux_completude_pct.toFixed(2)}%</span>
            <span className="label">Taux de lignes conservées</span>
          </div>
          <div className="stat-card">
            <span className="value">{latest.nb_doublons_supprimes}</span>
            <span className="label">Doublons supprimés</span>
          </div>
          <div className="stat-card">
            <span className="value">{latest.nb_valeurs_manquantes}</span>
            <span className="label">Valeurs manquantes</span>
          </div>
        </div>
      )}
      {runs.length > 0 && (
        <table>
          <caption>10 dernières exécutions du pipeline ETL</caption>
          <thead>
            <tr>
              <th scope="col">Date d'exécution</th>
              <th scope="col">Lignes lues</th>
              <th scope="col">Lignes chargées</th>
              <th scope="col">Complétude</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id_log}>
                <td>{new Date(r.date_execution).toLocaleString("fr-FR")}</td>
                <td>{r.nb_lignes_lues.toLocaleString("fr-FR")}</td>
                <td>{r.nb_lignes_chargees.toLocaleString("fr-FR")}</td>
                <td>{r.taux_completude_pct.toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
