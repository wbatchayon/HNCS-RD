# HNCS-RD : système de suivi R&D

Système de suivi du Département R&D de HNCS Groupe sous Microsoft 365. Il couvre tout le parcours : réception d'une candidature (site HNCS, LinkedIn, France Travail), analyse et présélection par la R&D, transmission à l'administration, entretiens, formalités et relation avec l'école, intégration de l'alternant, affectation à un pôle, un référent et un sujet, production et validation des livrables, comptes rendus périodiques, capitalisation et reporting Power BI.

La **source de vérité** du projet est [`spec.md`](spec.md). Toute évolution commence par la spec, puis se répercute dans le code ([\[14.2\]](spec.md#142-règle-de-changement)).

## Principes

| Principe | Mise en œuvre |
| --- | --- |
| Les décisions humaines ne sont jamais automatisées | Les flux notifient, tracent et ne font avancer un statut qu'après une action humaine ([\[1\]](spec.md#1-principes-directeurs-non-négociables), [\[6.1\]](spec.md#61-règles-générales)) |
| Une candidature ne passe à « Intégrée » que si les formalités sont au bon stade | Règle de validation de liste et contrôle `G_INTEGRATION` ([\[6.6\]](spec.md#66-catalogue-des-contrôles)) |
| Un changement de sujet ou de référent crée une nouvelle affectation | Affectation verrouillée dès son activation, succession par `AffectationRemplacee` ([\[8.4\]](spec.md#84-contrats-détaillés)) |
| Les CV et les données personnelles restent cloisonnés | Matrice d'accès, permissions par élément, Power BI sans donnée personnelle ([\[7.3\]](spec.md#73-matrice-daccès), [\[7.5\]](spec.md#75-sécurité-des-données-personnelles), [\[9.2\]](spec.md#92-tables-importées)) |
| Les champs de décision et les colonnes techniques sont protégés | Empreintes, statut de référence tiré de l'historique, rapprochement quotidien ([\[6.5\]](spec.md#65-formats-des-empreintes-p-09), [\[8.1\]](spec.md#81-socle-commun-sapplique-à-tous-les-flux)) |

## Socle technique

| Composant | Rôle |
| --- | --- |
| SharePoint (site HNCS-R&D) | Référentiel central : 26 listes et 6 bibliothèques |
| Power Automate | Orchestration : flux PA-00 à PA-14, solution `HNCSRDSuivi` |
| GitLab | Référence du code, des issues et des jalons ; synchronisation en lecture vers SharePoint |
| Power BI | Pilotage : 8 pages, 60 mesures, sécurité par rôle |
| Outlook et Teams | Notifications, réunions et rituels de gouvernance |

## Organisation du dépôt

| Dossier | Contenu |
| --- | --- |
| `spec.md`, `specs/` | Spécification de référence et sous-spécifications (vues, référentiels, notifications, rapport) |
| `tools/` | `spec_extract.py` : génère le modèle machine et contrôle la cohérence de la spec |
| `provisioning/` | Déploiement SharePoint rejouable (PnP PowerShell), contrôle post-déploiement, modèle généré |
| `flows/` | Flux Power Automate (définitions, générateur, solution, import, notifications, fiches) |
| `powerbi/` | Rapport Power BI au format PBIP (TMDL et PBIR), publication et contrôleur |
| `gitlab/` | Synchronisation GitLab, création de projet par sujet, modèles d'issues et de MR, pipeline |
| `testdata/` | Jeu de données fictif et script d'import |
| `tests/` | Tests hors ligne (Python) et tests de bout en bout (Pester), scénarios de recette, réconciliation |
| `docs/` | Installation, exploitation, architecture et guides d'utilisation par rôle |
| `BILAN.md` | État du projet : terminé, à valider, décisions ouvertes |

## Démarrage rapide

1. Lire [`docs/installation.md`](docs/installation.md) (prérequis, comptes, licences, ordre des lots).
2. Préparer `provisioning/config/tenant.json` et `membres.json` à partir des fichiers `*.sample.json`.
3. Déployer le socle : `pwsh ./provisioning/Deploy-HNCSRD.ps1 -ConfigPath ./provisioning/config/tenant.json -Lot 1`.
4. Contrôler : `pwsh ./provisioning/Test-HNCSRDDeploiement.ps1`.
5. Poursuivre lot par lot (flux, Power BI, GitLab) selon le guide d'installation.

## Vérifications hors ligne

```bash
python tools/spec_extract.py --check
python -m unittest discover -s tests/offline -v
python -m unittest discover -s gitlab/sync/tests -v
python flows/tools/check_flows.py
python flows/build/build_solution.py --check
python powerbi/tools/check_pbip.py
```

Ces contrôles sont exécutés par l'intégration continue (`.github/workflows/ci.yml`), ainsi que l'analyse syntaxique de tous les scripts PowerShell.

## Documentation

- [Guide d'installation](docs/installation.md)
- [Guide d'exploitation](docs/exploitation.md)
- [Architecture](docs/architecture.md)
- [Guides d'utilisation par rôle](docs/guides/README.md) : équipe R&D, administration, référent, alternant, direction
- [Bilan du projet](BILAN.md)

## Confidentialité

Les documents de cadrage sources sont confidentiels et ne sont pas versionnés ([\[13\]](spec.md#13-hypothèses-et-décisions-à-confirmer), H-30). Toutes les données du dépôt sont fictives.
