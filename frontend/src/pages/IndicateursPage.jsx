import { useEffect, useState } from "react";
import { getDessertes, getStatsOperateurs, getStatsPays } from "../api/client";

export default function IndicateursPage() {
  const [status, setStatus] = useState("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [jour, setJour] = useState(0);
  const [nuit, setNuit] = useState(0);
  const [operateurs, setOperateurs] = useState([]);
  const [pays, setPays] = useState([]);
  const [nbPaysTotal, setNbPaysTotal] = useState(0);

  useEffect(() => {
    Promise.all([
      getDessertes({ service_type: "Jour", limit: 1 }),
      getDessertes({ service_type: "Nuit", limit: 1 }),
      getStatsOperateurs(),
      getStatsPays(),
    ])
      .then(([jourRes, nuitRes, opsRes, paysRes]) => {
        setJour(jourRes.total);
        setNuit(nuitRes.total);
        setOperateurs(opsRes.slice(0, 8));
        // paysRes contains one row per departure country present in the data:
        // its total length (before keeping only the top 8 for the chart) is
        // the real number of covered countries, not a value hardcoded in the code.
        setNbPaysTotal(paysRes.length);
        setPays(paysRes.slice(0, 8));
        setStatus("ready");
      })
      .catch((err) => {
        setErrorMessage(err.message);
        setStatus("error");
      });
  }, []);

  const total = jour + nuit;
  const maxOp = operateurs[0]?.nb_dessertes || 1;
  const maxPays = pays[0]?.nb_dessertes || 1;

  if (status === "loading") return <p className="state-message">Chargement des indicateurs…</p>;
  if (status === "error")
    return <p className="state-message error">Impossible de charger les indicateurs : {errorMessage}</p>;

  return (
    <>
      <p className="page-kicker">Vue d'ensemble</p>
      <h1>Indicateurs clés</h1>
      <p>Répartition jour/nuit, volumes par opérateur et couverture géographique de l'entrepôt de données.</p>

      <div className="stat-grid" role="list" aria-label="Chiffres clés">
        <div className="stat-card" role="listitem">
          <span className="value">{total.toLocaleString("fr-FR")}</span>
          <span className="label">Dessertes au total</span>
        </div>
        <div className="stat-card" role="listitem">
          <span className="value">{jour.toLocaleString("fr-FR")}</span>
          <span className="label">Dessertes de jour ({total ? Math.round((jour / total) * 100) : 0}%)</span>
        </div>
        <div className="stat-card" role="listitem">
          <span className="value">{nuit.toLocaleString("fr-FR")}</span>
          <span className="label">Dessertes de nuit ({total ? Math.round((nuit / total) * 100) : 0}%)</span>
        </div>
        <div className="stat-card" role="listitem">
          <span className="value">{nbPaysTotal > 0 ? nbPaysTotal : "—"}</span>
          <span className="label">Pays couverts</span>
        </div>
      </div>

      <h2>Volume par opérateur (8 premiers)</h2>
      <BarList items={operateurs} labelKey="nom_operateur" valueKey="nb_dessertes" max={maxOp} />

      <h2>Volume par pays de départ (8 premiers)</h2>
      <BarList items={pays} labelKey="nom_pays" valueKey="nb_dessertes" max={maxPays} />
    </>
  );
}

function BarList({ items, labelKey, valueKey, max }) {
  return (
    <table>
      <caption className="visually-hidden">Classement par volume de dessertes</caption>
      <tbody>
        {items.map((item) => (
          <tr key={item[labelKey]}>
            <td style={{ width: "220px" }}>{item[labelKey]}</td>
            <td>
              <div
                style={{
                  background: "var(--teal)",
                  height: "1.1rem",
                  borderRadius: 3,
                  width: `${Math.max(4, (item[valueKey] / max) * 100)}%`,
                }}
                aria-hidden="true"
              />
            </td>
            <td style={{ width: "90px", textAlign: "right" }}>
              {item[valueKey].toLocaleString("fr-FR")}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
