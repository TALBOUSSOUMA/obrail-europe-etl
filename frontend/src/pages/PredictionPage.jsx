import { useEffect, useState } from "react";
import { postPredict, getOperateurs, getPays, getTypesTrain } from "../api/client";

const initialForm = {
  distance_km: 850,
  duree_h: 6.5,
  type_train: "TGV inOui",
  service_type: "Jour",
  nom_operateur: "",
  pays_origine: "FR",
  pays_destination: "FR",
};

export default function PredictionPage() {
  const [form, setForm] = useState(initialForm);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [errorMessage, setErrorMessage] = useState("");
  const [pays, setPays] = useState([]);
  const [operateurs, setOperateurs] = useState([]);
  const [typesTrain, setTypesTrain] = useState([]);

  useEffect(() => {
    getPays()
      .then(setPays)
      .catch(() => setPays([]));
    getOperateurs()
      .then((ops) => {
        setOperateurs(ops);
        // Pre-selects the first operator in the list rather than leaving
        // an empty field or a made-up value ("SNCF" hardcoded).
        if (ops.length > 0) {
          setForm((f) => (f.nom_operateur ? f : { ...f, nom_operateur: ops[0].nom_operateur }));
        }
      })
      .catch(() => setOperateurs([]));
    // Types actually present in the data (endpoint /types-train):
    // suggested via <datalist> without locking the field, in case someone
    // wants to simulate a hypothetical train type that doesn't exist yet.
    getTypesTrain()
      .then(setTypesTrain)
      .catch(() => setTypesTrain([]));
  }, []);

  function update(field, value) {
    setForm({ ...form, [field]: value });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setStatus("loading");
    try {
      const payload = { ...form, distance_km: Number(form.distance_km), duree_h: Number(form.duree_h) };
      const res = await postPredict(payload);
      setResult(res);
      setStatus("done");
    } catch (err) {
      setErrorMessage(err.message);
      setStatus("error");
    }
  }

  return (
    <>
      <p className="page-kicker">Modèle prédictif</p>
      <h1>Estimer une fréquence hebdomadaire</h1>
      <p>
        Décrivez une liaison ferroviaire (existante ou à l'étude) pour estimer combien de fois par semaine
        elle serait susceptible de circuler, à partir d'un modèle entraîné sur les dessertes réelles de
        l'entrepôt ObRail. Utile par exemple pour évaluer, avant de la créer, la viabilité d'une nouvelle
        liaison.
      </p>

      <form className="filters" onSubmit={handleSubmit} aria-label="Paramètres de la desserte">
        <div className="field">
          <label htmlFor="distance_km">Distance (km)</label>
          <input
            id="distance_km"
            type="number"
            min="0"
            required
            value={form.distance_km}
            onChange={(e) => update("distance_km", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="duree_h">Durée (heures)</label>
          <input
            id="duree_h"
            type="number"
            min="0"
            step="0.1"
            required
            value={form.duree_h}
            onChange={(e) => update("duree_h", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="type_train">Type de train</label>
          <input
            id="type_train"
            type="text"
            required
            list="types-train-suggestions"
            value={form.type_train}
            onChange={(e) => update("type_train", e.target.value)}
          />
          <datalist id="types-train-suggestions">
            {typesTrain.map((t) => (
              <option key={t.type_train} value={t.type_train} />
            ))}
          </datalist>
          <span className="muted-inline">Suggestions issues des données réelles ; autre valeur possible.</span>
        </div>
        <div className="field">
          <label htmlFor="service_type">Service</label>
          <select id="service_type" value={form.service_type} onChange={(e) => update("service_type", e.target.value)}>
            <option value="Jour">Jour</option>
            <option value="Nuit">Nuit</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="nom_operateur">Opérateur</label>
          <select
            id="nom_operateur"
            required
            value={form.nom_operateur}
            onChange={(e) => update("nom_operateur", e.target.value)}
          >
            <option value="">Choisir…</option>
            {operateurs.map((o) => (
              <option key={o.id_operateur} value={o.nom_operateur}>
                {o.nom_operateur}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="pays_origine">Pays de départ</label>
          <select
            id="pays_origine"
            required
            value={form.pays_origine}
            onChange={(e) => update("pays_origine", e.target.value)}
          >
            <option value="">Choisir…</option>
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
            required
            value={form.pays_destination}
            onChange={(e) => update("pays_destination", e.target.value)}
          >
            <option value="">Choisir…</option>
            {pays.map((p) => (
              <option key={p.code_pays} value={p.code_pays}>
                {p.nom_pays}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className="primary" disabled={status === "loading"}>
          {status === "loading" ? "Calcul…" : "Estimer"}
        </button>
      </form>

      <div aria-live="polite">
        {status === "error" && (
          <p className="state-message error">Prédiction impossible : {errorMessage}</p>
        )}
        {status === "done" && result && (
          <div className="card">
            <h2 style={{ marginTop: 0 }}>Résultat</h2>
            <p style={{ margin: 0 }}>
              Fréquence hebdomadaire estimée : {" "}
              <strong style={{ fontSize: "1.4rem", color: "var(--navy)" }}>
                {result.frequence_semaine_predite} jour(s)/semaine
              </strong>
            </p>
            <p style={{ marginTop: "0.5rem", color: "var(--muted)", fontSize: "0.9rem" }}>
              Modèle utilisé : {result.modele}. Cette estimation reste indicative — voir le rapport
              technique pour la méthodologie, la marge d'erreur et les limites du modèle.
            </p>
          </div>
        )}
      </div>
    </>
  );
}
