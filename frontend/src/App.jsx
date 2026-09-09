import { BrowserRouter, Routes, Route } from "react-router-dom";
import Nav from "./components/Nav";
import DessertesPage from "./pages/DessertesPage";
import IndicateursPage from "./pages/IndicateursPage";
import PredictionPage from "./pages/PredictionPage";
import EtatServicePage from "./pages/EtatServicePage";

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <a className="skip-link" href="#contenu">
          Aller au contenu principal
        </a>
        <Nav />
        <main id="contenu" tabIndex={-1}>
          <Routes>
            <Route path="/" element={<DessertesPage />} />
            <Route path="/indicateurs" element={<IndicateursPage />} />
            <Route path="/prediction" element={<PredictionPage />} />
            <Route path="/etat-service" element={<EtatServicePage />} />
          </Routes>
        </main>
        <footer>
          ObRail Europe — Portail interne. Données SNCF GTFS et Back-on-Track Open Night Train Database.
        </footer>
      </div>
    </BrowserRouter>
  );
}
