import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Dessertes", end: true },
  { to: "/indicateurs", label: "Indicateurs" },
  { to: "/prediction", label: "Prédiction" },
  { to: "/etat-service", label: "État du service" },
];

export default function Nav() {
  return (
    <header className="top-nav">
      <a className="brand" href="/">
        <strong>ObRail Europe</strong>
        <span>Portail des dessertes</span>
      </a>
      <nav aria-label="Navigation principale">
        <ul>
          {links.map((l) => (
            <li key={l.to}>
              <NavLink to={l.to} end={l.end}>
                {l.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
