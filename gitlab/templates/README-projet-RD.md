# {{ID_SUJET}} — {{TITRE_SUJET}}

> Projet GitLab du sujet R&D **{{ID_SUJET}}** (pôle {{CODE_POLE}}). GitLab est la référence du code,
> des issues, des merge requests et des jalons ; SharePoint (site HNCS-R&D) est le référentiel
> central du sujet, des livrables, des revues et des validations (spec § 1, P-05).

## Références SharePoint

| Élément | Lien |
| --- | --- |
| Fiche du sujet | {{URL_SUJET}} |
| Livrables du sujet | {{URL_LIVRABLES}} |
| Dossier documentaire (« 04 — Livrables R&D ») | {{URL_DOSSIER_LIVRABLES}} |
| Site HNCS-R&D | {{URL_SITE}} |

## Livrables et jalons

Un jalon GitLab par livrable ayant une composante technique : titre `LIV-aaaa-nnnn — <titre>`,
échéance = échéance du livrable dans SharePoint. Une échéance se modifie **d'abord** dans la liste
`Livrables`, puis dans le jalon ; la synchronisation quotidienne signale tout écart
(`GitlabSync.EcartEcheance`).

{{LISTE_LIVRABLES}}

## Conventions

- Étiquettes : `rd::sujet::{{ID_SUJET}}`, `rd::livrable::LIV-aaaa-nnnn`, `rd::pole::{{CODE_POLE}}`,
  `rd::type::poc` / `plan` / `doc`.
- Chaque issue et chaque merge request cite l'identifiant `LIV-aaaa-nnnn` du livrable concerné
  (modèles « Tache-RD », « Anomalie », « Livrable » et « MR-RD »).
- Branches : `feature/<objet>` ; messages de commit à l'impératif, en français (convention du
  dépôt de référence, spec § 2.2).
- Environnements de démonstration (Proxmox, OVH) : référencés dans la liste SharePoint
  `RessourcesTechniques`, **sans identifiant**.

## Démarrage

<!-- Prérequis, installation, lancement, démonstration. -->

## Definition of Done (POC et plans de stratégie)

Un POC ou un plan de stratégie n'est clôturé dans SharePoint que si les cinq critères sont cochés
sur l'élément `Livrables` (cases DoD1 à DoD5) :

1. **Fonctionnel et démontrable** — le démonstrateur fonctionne et peut être présenté.
2. **Fiche méthodologie rangée** — dans la bibliothèque « 04 — Livrables R&D », dossier du sujet.
3. **Restitution présentée** — restitution faite au référent ou au Comité R&D.
4. **Support de communication prêt** — support réutilisable pour la valorisation.
5. **Enseignements et limites documentés** — retour d'expérience, limites, suites possibles.

## Sécurité

- Aucun secret (jeton, mot de passe, clé), aucun identifiant d'infrastructure ni aucune donnée
  personnelle dans ce dépôt, ses issues, ses merge requests ou ses journaux de CI.
- Les secrets nécessaires à la CI sont des variables CI/CD masquées et protégées.
