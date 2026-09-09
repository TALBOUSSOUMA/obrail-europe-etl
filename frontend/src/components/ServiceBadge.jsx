// The badge never relies on color alone: the "Jour" or "Nuit" text is
// always present, color is a visual reinforcement, not the sole carrier
// of information (RGAA requirement).
export default function ServiceBadge({ type }) {
  const cls = type === "Nuit" ? "nuit" : "jour";
  return <span className={`badge ${cls}`}>{type}</span>;
}
