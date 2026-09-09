# Rapports pour l'oral (certification Simplon RNCP 37827)

5 rapports correspondant aux 5 évaluations de la convocation du 11/09/2026, dans l'ordre
de passage indiqué (installation 5 min, puis 90 min de soutenance : 80 min de démo/rapport
+ 10 min de questions du jury).

| Évaluation | Durée | Rapport |
|---|---|---|
| 1 — Collecte, stockage, mise à disposition des données | 15 min | [01-collecte-stockage-donnees.md](01-collecte-stockage-donnees.md) |
| 2 — Installation et configuration du service d'IA préconisé | 15 min | [02-installation-service-ia.md](02-installation-service-ia.md) |
| 3 — Intégration des modèles et services d'IA (+ démo) | 20 min | [03-integration-modeles-ia.md](03-integration-modeles-ia.md) |
| 4 — Réalisation d'une application intégrant un service d'IA (+ démo) | 20 min | [04-application-service-ia.md](04-application-service-ia.md) |
| 5 — Monitorage applicatif et résolution d'un incident | 10 min | [05-monitorage-incident.md](05-monitorage-incident.md) |

**Total : 80 min** de présentation, + 10 min de questions.

## Comment s'en servir

Chaque rapport commence par un bloc **"Points clés à retenir avant d'entrer"** — à relire
juste avant chaque évaluation, pas pendant. Le corps du rapport est écrit pour être
**parlé**, pas lu mot à mot : les chiffres et exemples sont réels et vérifiés (voir
`docs/INCIDENT_POSTMORTEM.md` et les résultats de tests), donc réutilisables tels quels
si le jury demande une précision.

Les rapports 3, 4 et 5 contiennent chacun un **script de démonstration minuté** — à
répéter en conditions réelles (chronomètre + `docker compose up` déjà lancé) avant le
jour J, pas improvisé sur place.

## Ce qui reste à faire avant l'oral

- [ ] Répéter les scripts de démo des rapports 3, 4 et 5, chronomètre en main.
- [ ] Relire chaque rapport à voix haute une fois, pour reformuler avec ses propres mots
      plutôt que de lire.
- [ ] Préparer les réponses aux questions probables (voir section "Limites assumées" de
      chaque rapport - c'est exactement le genre de question qu'un jury pose).
