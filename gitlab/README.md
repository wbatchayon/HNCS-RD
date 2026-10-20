# Intégration GitLab et infrastructure

Mise en œuvre de la spec [10](../spec.md#10-intégration-gitlab-et-infrastructure) (lots 3 et 5). La spec [`spec.md`](../spec.md) prévaut en cas d'écart.

- GitLab est la **référence** du code, des issues, des merge requests et des jalons ; SharePoint ne
  stocke **que** des liens et des métadonnées (P-05).
- La synchronisation **lit** GitLab et n'écrit **que** dans la liste technique `GitlabSync` : aucun
  statut métier, aucune écriture dans `SujetsRD` ni `Livrables` ([10.1](../spec.md#101-principes)).
- Seul le script de création de projet, lancé par un humain, reporte `GitlabProjetUrl` et
  `GitlabProjetId` sur le sujet concerné.
- Aucun secret (jeton, mot de passe, certificat) dans ce dépôt, qui est **public** (H-30), ni dans
  SharePoint ou `RessourcesTechniques` : variables d'environnement ou variables CI masquées uniquement.

## Contenu

| Chemin | Rôle | Lot |
| --- | --- | --- |
| `scripts/New-GitlabProjetSujet.ps1` | Création **à la demande d'un humain** du projet GitLab d'un sujet (projet, labels, jalons des livrables, modèles), puis report de l'URL et de l'ID sur le sujet | 3 |
| `templates/.gitlab/issue_templates/` | Modèles d'issues : `Tache-RD`, `Anomalie`, `Livrable` | 3 |
| `templates/.gitlab/merge_request_templates/` | Modèle de MR `MR-RD` (référence obligatoire au `LIV-…`) | 3 |
| `templates/README-projet-RD.md` | Modèle de README d'un projet R&D (IdHNCS, liens SharePoint, Definition of Done) | 3 |
| `sync/sync_gitlab_sharepoint.py` | Synchronisation lecture GitLab → liste `GitlabSync` (Python 3.12, bibliothèque standard) | 5 |
| `sync/tests/test_sync.py` | Tests hors ligne (doublures HTTP, aucun réseau) | 5 |
| `ci/.gitlab-ci.yml` | Pipeline GitLab planifié (quotidien 05:30) exécutant la synchronisation | 5 |

## Conventions GitLab (spec [10.2](../spec.md#102-conventions-gitlab))

| Élément | Convention |
| --- | --- |
| Groupe | `hncs-rd` ; sous-groupes par pôle facultatifs (`hncs-rd/p1-poc`, …) |
| Projet | Un projet par sujet : `suj-aaaa-nnnn-<slug>` ; description commençant par l'`IdHNCS` du sujet |
| Jalons | Un par livrable ayant une composante technique : titre `LIV-aaaa-nnnn : <titre>`, échéance = `Echeance` du livrable |
| Labels | `rd::sujet::SUJ-aaaa-nnnn`, `rd::livrable::LIV-aaaa-nnnn`, `rd::pole::P1`…`P4`, `rd::type::poc` / `plan` / `doc` |
| Issues et MR | Référencent l'`IdHNCS` du livrable dans la description (modèles fournis) |
| Liens SharePoint | `SujetsRD.GitlabProjetUrl`, `GitlabProjetId`, `GitlabIssueUrl`, `GitlabMilestone` ; `Livrables.LienGitlab` |

Le slug est dérivé du titre du sujet (minuscules ASCII sans accent, tirets, 40 caractères au plus) :
« Sauvegarde et PRA : démonstrateur » → `suj-2026-0003-sauvegarde-et-pra-demonstrateur`.
Le `rd::type` d'un livrable suit son `TypeLivrable` : POC / démonstrateur → `poc`, Plan de stratégie
→ `plan`, autres types → `doc`. Les labels `rd::…::…` sont des labels à portée (exclusifs) sur
GitLab Premium ; sur GitLab Free ce sont des labels ordinaires, ce qui ne change rien au script.

## Mise en place

### 1. GitLab

1. Créer le groupe `hncs-rd` et, si souhaité, les sous-groupes de pôle (le script ne crée pas de groupe).
2. **Jeton de la synchronisation** : *Groupe `hncs-rd` > Settings > Access tokens*, jeton d'accès de
   groupe, rôle **Reporter**, portée **`read_api`** uniquement, expiration d'un an au plus, rotation
   inscrite au calendrier d'exploitation. Il est saisi directement dans la variable CI masquée
   `GITLAB_TOKEN` (jamais dans un fichier).
3. **Jeton de création de projet** (script `New-GitlabProjetSujet.ps1`, spec [10.3](../spec.md#103-composants-livrés)) : jeton
   **personnel** de la personne qui lance le script, portée **`api`**, rôle Maintainer sur le groupe
   cible, durée courte. Il est saisi dans `$env:GITLAB_TOKEN` pour la session uniquement et **jamais
   stocké** (ni fichier, ni variable CI, ni profil PowerShell). Le jeton de groupe `read_api` de la
   synchronisation ne permet pas de créer un projet.
4. Créer un projet d'outillage (ex. `hncs-rd/outillage-suivi-rd`) contenant une copie du dossier
   `gitlab/` de ce dépôt (même arborescence) et `ci/.gitlab-ci.yml` placé à sa racine sous le nom
   `.gitlab-ci.yml`. Protéger la branche `main`.

### 2. Application Entra (permissions « Selected », spec [10.3](../spec.md#103-composants-livrés) et H-31)

1. *Entra ID > Inscriptions d'applications > Nouvelle inscription* : « HNCS-RD GitLab Sync », comptes
   de ce tenant uniquement, sans URI de redirection.
2. Choisir **une** des deux permissions d'application Microsoft Graph ci-dessous, puis donner le
   **consentement administrateur**. Aucune autre permission (ni `Sites.Read.All`, ni
   `Sites.ReadWrite.All`). Les octrois sont faits par un administrateur disposant de
   `Sites.FullControl.All` (par ex. depuis Graph Explorer), qui relève d'abord les identifiants :

   ```http
   GET https://graph.microsoft.com/v1.0/sites/<tenant>.sharepoint.com:/sites/HNCS-RD?$select=id
   GET https://graph.microsoft.com/v1.0/sites/{site-id}/lists?$select=id,name,displayName
   ```

#### Option recommandée : `Lists.SelectedOperations.Selected` (accès limité à trois listes)

L'application n'accède qu'aux listes octroyées : **`GitlabSync` en écriture**, **`SujetsRD` et
`Livrables` en lecture**. Elle ne voit ni le reste du site (CV compris), ni la liste de ses listes.

```http
POST https://graph.microsoft.com/v1.0/sites/{site-id}/lists/{id-GitlabSync}/permissions
Content-Type: application/json

{ "roles": ["write"], "grantedTo": { "application": { "id": "<client-id>" } } }
```

Même requête avec `"roles": ["read"]` sur `{id-SujetsRD}` puis sur `{id-Livrables}`. Vérification :
`GET /sites/{site-id}/lists/{list-id}/permissions`. Selon l'état de déploiement dans le tenant, ces
points d'accès peuvent n'exister qu'en `beta` : vérifier la documentation Microsoft Graph le jour de la
mise en place.

Comme l'application ne peut ni résoudre le site ni énumérer ses listes, renseigner les variables CI
**`HNCS_SITE_ID`**, **`HNCS_LISTE_ID_SUJETSRD`**, **`HNCS_LISTE_ID_LIVRABLES`** et
**`HNCS_LISTE_ID_GITLABSYNC`** (identifiants relevés ci-dessus, non secrets). Le script n'émet alors
aucune requête de niveau site ; sans elles, il s'arrête avec le code 2 et un message explicite.

#### Option de repli : `Sites.Selected` en écriture sur le site (risque accepté, H-31)

À n'utiliser que si `Lists.SelectedOperations.Selected` n'est pas disponible dans le tenant. Le droit
`write` porte sur **tout** le site HNCS-RD, y compris les listes et bibliothèques de recrutement : la
restriction à `GitlabSync` (et à la lecture de `SujetsRD` / `Livrables`) n'est garantie **que par le
code** de la synchronisation, revu et testé (aucune écriture hors `GitlabSync`). Ce risque doit être
accepté explicitement par la DSI et la Direction R&D (H-31, à confirmer) ; la mesure compensatoire est
la protection des informations d'identification (identité fédérée de préférence, variables protégées).
À défaut d'acceptation, la synchronisation (lot 5, facultative) reste désactivée.

```http
POST https://graph.microsoft.com/v1.0/sites/{site-id}/permissions
Content-Type: application/json

{
  "roles": ["write"],
  "grantedToIdentities": [
    { "application": { "id": "<client-id>", "displayName": "HNCS-RD GitLab Sync" } }
  ]
}
```

Équivalent PnP.PowerShell (connecté au centre d'administration) :
`Grant-PnPAzureADAppSitePermission -AppId <client-id> -DisplayName "HNCS-RD GitLab Sync" -Site <url du site> -Permissions Write`.
Vérification : `GET /sites/{site-id}/permissions`. Les variables `HNCS_SITE_ID` et `HNCS_LISTE_ID_*`
sont alors facultatives (résolution automatique).

#### Informations d'identification

- **Identité fédérée GitLab OIDC (recommandée, aucun secret)** : *Certificats et secrets >
  Informations d'identification fédérées > Autre émetteur*, émetteur = URL de l'instance GitLab,
  sujet = `project_path:hncs-rd/outillage-suivi-rd:ref_type:branch:ref:main`, audience
  `api://AzureADTokenExchange` ; décommenter le bloc `id_tokens` du job `synchro-gitlab-sharepoint`,
  qui fournit `HNCS_CLIENT_ASSERTION`, et ne pas définir `HNCS_CLIENT_SECRET` (prioritaire s'il existe).
- **Secret client** (à défaut) : durée de 6 à 12 mois, saisi dans la variable CI masquée et protégée
  `HNCS_CLIENT_SECRET`, rotation planifiée.

Un certificat n'est pas utilisable directement : signer l'assertion JWT exige une bibliothèque
cryptographique hors de la bibliothèque standard. Une assertion produite par un outil externe peut
être fournie dans `HNCS_CLIENT_ASSERTION`.

### 3. Variables CI/CD du projet d'outillage

Toutes **protégées** (branche `main` uniquement) ; les secrets **masqués**.

| Variable | Valeur | Masquée |
| --- | --- | --- |
| `GITLAB_URL` | `https://gitlab.example.com` | Non |
| `GITLAB_TOKEN` | jeton de groupe `read_api` (rôle Reporter) | **Oui** |
| `HNCS_TENANT_ID` | identifiant du tenant | Non |
| `HNCS_CLIENT_ID` | identifiant de l'application Entra | Non |
| `HNCS_CLIENT_SECRET` | secret de l'application (sauf identité fédérée) | **Oui** |
| `HNCS_SITE_URL` | `https://<tenant>.sharepoint.com/sites/HNCS-RD` | Non |
| `HNCS_SITE_ID` | identifiant Graph du site (obligatoire avec `Lists.SelectedOperations.Selected`) | Non |
| `HNCS_LISTE_ID_SUJETSRD`, `HNCS_LISTE_ID_LIVRABLES`, `HNCS_LISTE_ID_GITLABSYNC` | identifiants Graph des listes (idem) | Non |

Facultatives : `HNCS_GRAPH_URL`, `HNCS_LOGIN_URL` (clouds souverains uniquement).

### 4. Planification

*CI/CD > Schedules > New schedule* : description « Synchronisation GitLab → SharePoint », intervalle
`30 5 * * *`, fuseau **Europe/Paris**, branche `main`, variable `SCHEDULE_TYPE` = `gitlab-sync`.
L'heure précède l'actualisation Power BI de 06:00 ([9.1](../spec.md#91-projet)). Le job tourne dans `python:3.12-slim`
et un `resource_group` empêche deux exécutions simultanées.

### 5. SharePoint

La liste `GitlabSync` (lot 5) doit être déployée (`provisioning`, `-Lot 5`). Les sujets à suivre
portent `GitlabProjetId` (renseigné par le script de création, ou à la main).

## Exploitation

### Synchronisation

```bash
# simulation : lit tout, calcule, journalise les écritures prévues, n'écrit rien
python gitlab/sync/sync_gitlab_sharepoint.py --dry-run --verbose
# exécution réelle, éventuellement limitée à un sujet
python gitlab/sync/sync_gitlab_sharepoint.py [--sujet SUJ-2026-0003]
```

Dans GitLab : *Run pipeline* sur `main` avec `SYNC_DRY_RUN` = `1` lance le job de simulation.

| Colonne de `GitlabSync` | Ligne projet (`<projetId>:0`) | Ligne jalon (`<projetId>:<milestoneId>`) |
| --- | --- | --- |
| `Title` | chemin complet du projet | chemin complet du projet |
| `Sujet`, `GitlabProjetId` | sujet ayant ce `GitlabProjetId` | idem |
| `Milestone`, `MilestoneEcheance`, `MilestoneEtat` | vides | titre, `due_date`, `active` / `closed` |
| `IssuesOuvertes`, `IssuesFermees` | toutes les issues du projet | issues du jalon |
| `MRsOuvertes` | MR ouvertes du projet | MR ouvertes du jalon |
| `DerniereActivite` | `last_activity_at` du projet (à la minute) | idem |
| `IdLivrable` | vide | premier `LIV-\d{4}-\d{4,}` du titre du jalon |
| `EcartEcheance` | Non | Oui si l'échéance du jalon ≠ `Echeance` du livrable (jalon sans échéance compris) ; Non si le livrable est introuvable (avertissement au journal) |
| `Orpheline` | Non tant que le projet est rattaché à un sujet | Non tant que le jalon existe ; Oui si la ligne n'a plus de correspondance (jalon supprimé, sujet détaché, projet retiré du sujet) |
| `DateSynchro` | date de la dernière **écriture** de la ligne | idem |

Fonctionnement :

- **Idempotence** : une ligne n'est créée que si sa `CleSynchro` est absente et n'est mise à jour que
  si un champ a changé (seuls les champs modifiés sont envoyés, avec `DateSynchro`). Un second passage
  sans changement n'écrit rien.
- **Lignes orphelines** (spec [10.3](../spec.md#103-composants-livrés)) : une ligne existante sans correspondance GitLab (jalon supprimé,
  sujet détaché, projet retiré du sujet) n'est **jamais supprimée** : elle passe à `Orpheline` = Oui
  (une seule écriture, avec `DateSynchro`) et reste exclue des indicateurs Power BI ; si elle redevient
  valide (jalon rétabli, projet rattaché à nouveau), elle repasse à Non. Les lignes d'un projet
  illisible lors du passage (erreur GitLab) ne sont ni recalculées ni marquées.
- **Pagination** : en-tête `X-Next-Page` (GitLab), `@odata.nextLink` (Graph). Les MR sont comptées par
  l'en-tête `X-Total`, ou par parcours complet s'il est absent.
- **Nouvelles tentatives** : jusqu'à 5 essais sur HTTP 429, 500, 502, 503, 504 et erreurs réseau, en
  respectant `Retry-After` (au plus 120 s), sinon délai exponentiel.
- **Dates** : les colonnes « date seule » renvoyées par Graph en UTC sont ramenées à la date de Paris
  avant comparaison ; elles sont écrites à midi UTC pour rester sur le bon jour.
- **Journal** : une ligne par sujet, plan (créations, mises à jour, inchangées, orphelines) et écriture ;
  jamais de jeton ni de secret.
- **Codes de sortie** : `0` succès ; `1` au moins un projet illisible ou une écriture en échec (les autres
  projets sont tout de même traités ; le job est rouge) ; `2` configuration absente ou invalide, jeton
  Graph, site ou liste introuvable.

Incidents courants :

| Symptôme | Cause probable | Action |
| --- | --- | --- |
| Code 2, `invalid_client` / `AADSTS…` | secret expiré, mauvaise application, identité fédérée mal déclarée | renouveler le secret ou corriger l'identifiant fédéré |
| Code 2, « accès refusé au niveau du site » | `Lists.SelectedOperations.Selected` sans `HNCS_SITE_ID` / `HNCS_LISTE_ID_*` | renseigner les quatre identifiants |
| Code 2 ou 1, HTTP 403 sur une liste | octroi manquant sur la liste (ou sur le site en repli `Sites.Selected`) | refaire l'octroi de l'étape 2 |
| Code 1, HTTP 404 sur un projet | `GitlabProjetId` erroné, projet supprimé, jeton sans accès au sous-groupe | corriger le sujet ou les droits du jeton |
| Code 1, HTTP 401 GitLab | jeton expiré ou révoqué | régénérer le jeton de groupe, mettre à jour `GITLAB_TOKEN` |
| Avertissement « livrable introuvable » | identifiant mal saisi dans le titre du jalon | corriger le titre du jalon dans GitLab |
| Avertissement « ligne orpheline » | jalon supprimé, sujet détaché ou projet retiré du sujet | ligne conservée et marquée `Orpheline` = Oui ; suppression manuelle par G_PROP si souhaité |

### Création du projet d'un sujet (lot 3)

À lancer par une personne de l'équipe R&D, sur demande, avec PowerShell 7.2+ et PnP.PowerShell 2.x :

```powershell
$env:GITLAB_URL   = 'https://gitlab.example.com'
$env:GITLAB_TOKEN = Read-Host 'Jeton GitLab (portée api)' -MaskInput   # jamais versionné
./gitlab/scripts/New-GitlabProjetSujet.ps1 -IdSujet SUJ-2026-0003 -SousGroupe p2-strategie -DeposerModeles -WhatIf
./gitlab/scripts/New-GitlabProjetSujet.ps1 -IdSujet SUJ-2026-0003 -SousGroupe p2-strategie -DeposerModeles
Remove-Item Env:GITLAB_TOKEN
```

- Connexion SharePoint par `provisioning/modules/HNCSRD.Provisioning.psm1` (`Get-HNCSRDConfig`,
  `Connect-HNCSRD`, `Resolve-HNCSRDLookupId`) si `provisioning/config/tenant.json` existe ; sinon
  `Connect-PnPOnline -Interactive -ClientId` (`-SiteUrl` / `$env:HNCS_SITE_URL`, `-ClientId` /
  `$env:HNCS_PNP_CLIENT_ID`).
- Livrables pris en compte : ceux dont `Sujet` est le sujet, et ceux des affectations du sujet (si
  `Sujet` n'a pas encore été copié par PA-07). `-ExclureLivrable LIV-…` écarte les livrables sans
  composante technique.
- Idempotent : projet retrouvé par `GitlabProjetId` puis par le préfixe `suj-aaaa-nnnn` ; labels, jalons
  (reconnus par leur `LIV-…`) et fichiers existants réutilisés, jamais écrasés. Un jalon dont l'échéance
  diffère du livrable est signalé, pas modifié.
- `-WhatIf` : aucune écriture, ni dans GitLab ni dans SharePoint.
- `-DeposerModeles` : un commit avec `README.md` et les modèles `.gitlab/` manquants, jetons
  remplacés (`{{ID_SUJET}}`, `{{TITRE_SUJET}}`, `{{CODE_POLE}}`, `{{URL_SITE}}`, `{{URL_SUJET}}`,
  `{{URL_LIVRABLES}}`, `{{URL_DOSSIER_LIVRABLES}}`, `{{LISTE_LIVRABLES}}`). Pour un projet existant
  sans le script, copier `templates/.gitlab/` et remplacer ces jetons à la main.

### Tests

```bash
python -m unittest discover -s gitlab/sync/tests -v
```

Exécutés aussi par la CI GitHub (`.github/workflows/ci.yml`) et par le job `tests-synchro` du pipeline
GitLab. Ils couvrent l'extraction des identifiants, la clé de synchronisation, le calcul d'écart, les
dates de Paris, l'idempotence, le marquage des lignes orphelines, la pagination, les nouvelles tentatives, la simulation et les codes de
sortie, sans aucun accès réseau.

## Limites

- Jalons de **projet** uniquement (les jalons de groupe ne sont pas lus).
- Comptage des issues par `issues_statistics` (filtre sur le **titre** du jalon) : renommer un jalon
  est sans effet sur la clé (`milestoneId`), mais deux jalons de même titre seraient confondus.
- Pas de suppression des lignes orphelines (seulement `Orpheline` = Oui) ; pas de mise à jour de `DateSynchro` sans changement
  (`DateSynchro` = date de la dernière écriture de la ligne, spec [4](../spec.md#4-modèle-de-données--listes-sharepoint)).
- En repli `Sites.Selected`, la limitation à `GitlabSync` repose sur le code (H-31).
- Un livrable doit avoir un `IdHNCS` (attribué par PA-00D) pour recevoir un jalon.
- Le script de création ne crée ni groupe ni sous-groupe, et ne modifie jamais un jalon existant.
- Validé hors ligne uniquement : appels Graph et GitLab à recetter sur un vrai tenant et une vraie instance.

## Infrastructure (Proxmox / OVH)

Conformément à la spec [10.4](../spec.md#104-infrastructure-proxmox--ovh) et à H-21 :

- les serveurs, VM et environnements de démonstration (Proxmox, OVH) sont **référencés** dans la liste
  SharePoint `RessourcesTechniques` : `TypeRessource` (`VM Proxmox`, `Serveur OVH`, `Environnement de
  démonstration`…), `Url` d'administration ou de démonstration, `Sujet`, `Responsable`, `Commentaire` ;
- **aucun identifiant** (compte, mot de passe, clé SSH, jeton d'API, adresse de console avec
  identifiants intégrés) n'y est stocké, ni dans GitLab, ni dans ce dépôt ; les accès sont gérés hors
  de ces outils, selon les règles de la DSI ;
- **aucune automatisation d'infrastructure** n'est livrée (pas de création de VM, de DNS ni de
  sauvegarde) : les documents sources n'en prévoient pas. Toute évolution passe d'abord par la spec.
