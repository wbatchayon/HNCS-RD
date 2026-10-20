# Prérequis du projet HNCS-RD

> Public : responsable du projet, administrateurs Microsoft 365, Power Platform, Power BI et GitLab, DSI.
> Ce document recense **tout ce qui doit être réuni avant de lancer le projet**, de l'organisation jusqu'au poste
> d'installation. Il ne décrit pas l'installation elle-même : les commandes, dans l'ordre, sont dans le
> [guide d'installation](docs/installation.md). La [spécification](spec.md) (v1.7.1) fait foi en cas d'écart.

## Sommaire

1. Vue d'ensemble : quoi, pour quand, fourni par qui
2. Organisation et décisions préalables (lot 0)
3. Licences
4. Comptes, boîtes et adresses fonctionnelles
5. Droits d'administration
6. Environnements et ressources de la plateforme
7. Applications Microsoft Entra
8. GitLab
9. Poste d'installation
10. Fichiers de configuration à préparer
11. Sécurité, confidentialité et conformité
12. Prérequis de la recette
13. Prérequis lot par lot
14. Check-list finale

---

## 1. Vue d'ensemble : quoi, pour quand, fourni par qui

| Domaine | Élément | Nécessaire avant | Fourni par |
| --- | --- | --- | --- |
| Organisation | Atelier de validation du lot 0, responsables désignés | Lot 1 | Direction R&D, Direction Générale |
| Licences | Microsoft 365, Power Automate (standard), Power BI Pro | Lot 1 (Power BI : lot 4) | DSI |
| Identités | Compte de service, boîte partagée R&D, adresses fonctionnelles | Lot 1 | DSI, messagerie |
| Administration | Administrateur SharePoint, administrateur de collection de sites | Lot 1 | DSI |
| Plateforme | Environnements Power Platform avec Dataverse (recette, production) | Lot 2 | Administrateur Power Platform |
| Plateforme | Espace Power BI « HNCS-R&D Pilotage » | Lot 4 | Administrateur Power BI |
| Entra | Application « HNCS-RD Provisioning » (PnP.PowerShell) | Lot 1 | Administrateur Entra |
| Entra | Application « HNCS-RD GitLab Sync » | Lot 5 | Administrateur Entra |
| GitLab | Instance, groupe `hncs-rd`, jetons, projet d'outillage | Lot 3 (création de projets), lot 5 (synchronisation) | Administrateur GitLab |
| Poste | PowerShell 7.4+, PnP.PowerShell, Python 3.12, Power Platform CLI, Pester, Az.Accounts | Lot 1 | Équipe d'installation |
| Configuration | `tenant.json`, `membres.json`, `deploymentSettings.json` | Lot 1 (paramètres de flux : lot 1) | Équipe d'installation |
| Recette | Site de recette, comptes de test par persona | Avant chaque mise en production | DSI |

---

## 2. Organisation et décisions préalables (lot 0)

Le lot 0 ne déploie rien : il valide la spécification. Sa condition de sortie est l'accord des responsables
métier et administratifs sur les hypothèses de la spec ([\[11\]](spec.md#11-découpage-en-lots-0-à-5),
[\[13\]](spec.md#13-hypothèses-et-décisions-à-confirmer)).

### 2.1 Rôles à désigner

| Rôle | Responsabilité | Nécessaire avant |
| --- | --- | --- |
| Responsable du projet | Pilote les lots, tient la spec à jour (règle « spec d'abord », [\[14.2\]](spec.md#142-règle-de-changement)) | Lot 0 |
| Direction R&D | Valide les paramètres métier, les modèles et les vues ; propriétaire des modèles initiaux | Lot 1 |
| Administration (Carine, H-05) | Interlocutrice des formalités, membre de `HNCS-RD-Administration` | Lot 1 |
| Responsable support des flux | Reçoit les alertes N-98 et N-99, reprend les exécutions en erreur. **Condition de sortie du lot 2** | Lot 2 |
| Référents de pôle | Encadrent les alternants, valident les livrables | Lot 2 |
| Responsable de la relation école | Conventions et partenariats (groupe `HNCS-RD-RelationEcoles`, H-43) | Lot 3 |
| DPO et juridique | Durée de conservation des candidatures (H-10), information des candidats (H-09) | Avant l'activation de PA-13 et des messages au candidat |

### 2.2 Décisions à arbitrer

Les valeurs par défaut de la spec permettent de démarrer. Les décisions ci-dessous restent à confirmer en atelier :
l'installation peut avancer tant qu'elles ne sont pas tranchées, mais certaines fonctions restent alors désactivées.

| Décision | Hypothèses | Effet tant qu'elle n'est pas tranchée |
| --- | --- | --- |
| Responsable final de la sélection et confirmation d'intégration | H-06, H-40 | Comportement par défaut de la spec |
| Validation des communications externes, décision de partenariat ou de sponsoring | H-11, H-37 | Comportement par défaut de la spec |
| Durée de conservation des candidatures (RGPD) | H-10 | PA-13 reste désactivé ; `Conservation.CandidatureNonRetenueMois` reste vide |
| Accusé de réception et information des candidats | H-09 | `Fonction.AccuseReceptionActif` et `Fonction.InformationCandidatAuto` restent à Non |
| Canaux LinkedIn, France Travail et site HNCS | H-04 | Aucune API : réception par règles Outlook dans la boîte R&D |
| Cadence des comptes rendus | H-08 | Quinzaine, paramétrable |
| Compte de service, appartenance directe aux groupes, licences | H-13, H-14, H-15 | **Bloquant pour le lot 1** |
| Permissions de la synchronisation GitLab | H-31 | Synchronisation désactivée (facultative) |
| Valeurs contrôlées proposées hors sources | H-38 | Valeurs proposées par la spec |
| Acteurs support RH, Juridique, Finance ; trajectoire M0 à M12 | H-32, H-34 | Comportement par défaut de la spec |

### 2.3 Contenus à préparer par le métier

- Validation des **paramètres initiaux** ([`specs/referentiels-initiaux.md`](specs/referentiels-initiaux.md)) : délais,
  cadences, destinataires, fonctions activables (H-22).
- **Modèles documentaires** du registre : fichiers à produire et approuver par leurs propriétaires ; aucun livrable
  n'est proposé automatiquement tant qu'un modèle n'est pas « Approuvé ».
- **Règles Outlook** de la boîte R&D qui déposent les candidatures dans le dossier `Candidatures` (formulaire du site
  balisé `[CANDIDATURE-SITE]`, notifications LinkedIn et France Travail), définies par la R&D (H-04).
- **Objectifs à un an** de la table Power BI `Objectifs` : valeurs indicatives du cadrage, à confirmer (H-20).
- **Liste nominative des membres** de chaque groupe (section 10.2).

---

## 3. Licences

| Public | Licence | Référence |
| --- | --- | --- |
| Utilisateurs métier | Microsoft 365 avec SharePoint, Outlook et Teams | [\[2\]](spec.md#2-architecture-et-conventions-de-nommage) |
| Compte de service | Microsoft 365 avec Power Automate (connecteurs standard) et messagerie | H-13 |
| Flux | Power Automate inclus dans Microsoft 365, **connecteurs standard uniquement** (SharePoint, Office 365 Outlook, Office 365 Utilisateurs, Microsoft Teams). Aucun connecteur premium sans validation budgétaire | P-08, H-15 |
| Lecteurs du rapport | **Power BI Pro** (Direction Générale, Direction R&D, équipe R&D, administration, relation école, référents). Les alternants n'ont pas accès au rapport et n'ont besoin d'aucune licence Power BI (H-19) | H-16 |
| Compte de publication Power BI | Power BI Pro ; selon la configuration du tenant, les API de définition d'éléments Fabric utilisées par le script peuvent exiger un espace sur capacité (Fabric, Premium ou PPU). À défaut : publication manuelle depuis Power BI Desktop | H-15, H-16 |
| GitLab | Instance existante ; GitLab Premium n'est utile que pour l'exclusivité des labels à portée `rd::…::…` (sans effet sur les scripts) | [\[10.2\]](spec.md#102-conventions-gitlab) |

---

## 4. Comptes, boîtes et adresses fonctionnelles

### 4.1 Compte de service

Compte dédié, par exemple `svc-hncs-rd@<domaine>`, propriétaire de tous les flux et identité de toutes leurs
connexions ([\[8.1\]](spec.md#81-socle-commun-sapplique-à-tous-les-flux), H-13).

| Exigence | Détail |
| --- | --- |
| Licence | Section 3 |
| Mot de passe | Sans expiration, **ou** procédure de renouvellement documentée (une expiration coupe toutes les connexions des flux) |
| MFA et accès conditionnel | Politique compatible avec des connexions Power Automate durables |
| Boîte R&D | Droit **« Envoyer en tant que »** sur la boîte partagée R&D |
| Groupes | Membre **direct** de `HNCS-RD-Proprietaires` (posé par `Set-HNCSRDMembres.ps1`, contrôlé par `Grant-HNCSRDServiceAccount.ps1`) ; jamais via un groupe Entra (H-14) |
| Power BI | Identifiants OAuth de la source de données du modèle (H-16) |
| Usage | Aucun usage interactif quotidien : ses écritures ne déclenchent aucun flux (anti-boucle) |

### 4.2 Boîte partagée R&D

- Adresse, par exemple `rd@<domaine>` : expéditeur de toutes les notifications (`Destinataires.BoiteRD`).
- Dossier **`Candidatures`** surveillé par PA-01b. Son **identifiant de dossier** est demandé dans le fichier de
  paramètres des flux (`hncs_BoiteRDDossierCandidatures`) ; il s'obtient par exemple avec Microsoft Graph
  (`mailFolders` de la boîte).
- La rétention de cette boîte est hors périmètre du projet (H-10).

### 4.3 Adresses fonctionnelles

| Adresse | Paramètre | Usage |
| --- | --- | --- |
| Administration (Carine) | `Destinataires.Administration` | Transmission des candidatures, formalités |
| Direction R&D | `Destinataires.DirectionRD` | Synthèses, propriétaire des modèles initiaux |
| Direction Générale | `Destinataires.Direction` | Synthèses de gouvernance (identifiants uniquement, [\[7.5\]](spec.md#75-sécurité-des-données-personnelles)) |
| Support des flux | `Destinataires.Support`, `hncs_SupportEmail` | Alertes N-99 (erreur) et N-98 (synthèse quotidienne) |

Une boîte ou une liste de distribution est préférable à une adresse personnelle pour le support et l'administration.

---

## 5. Droits d'administration

| Rôle | Usage | Lot |
| --- | --- | --- |
| Administrateur SharePoint | Création du site par `TenantAdminUrl` | 1 |
| Administrateur de la collection de sites HNCS-RD (ou `SiteOwner`) | Rupture d'héritage, retrait des attributions non prévues, groupes | 1 et suivants |
| Administrateur Entra (ou administrateur d'applications) | Inscription des applications et consentement administrateur | 1 et 5 |
| Créateur de l'environnement, ou administrateur système Dataverse | Import de la solution `HNCSRDSuivi`, activation des flux | 2 |
| Administrateur de l'espace Power BI | Publication, identifiants, rôles RLS et OLS, application et audiences | 4 |
| Propriétaire du groupe GitLab `hncs-rd` | Jetons de groupe, projet d'outillage, variables CI | 3 et 5 |

---

## 6. Environnements et ressources de la plateforme

### 6.1 SharePoint

- Un site de **recette** dont l'URL contient `recette`, `test`, `qualif` ou `dev` (exigé par le script d'import du
  jeu de test), puis le site de **production** `https://<tenant>.sharepoint.com/sites/HNCS-RD`.
- Les sites sont **créés par le script** (site d'équipe `STS#3` sans groupe Microsoft 365, français, fuseau de
  Paris, [\[2.2\]](spec.md#22-conventions-de-nommage)). Aucune URL ne doit être occupée par un site en corbeille.

### 6.2 Power Platform

- Un environnement **avec Dataverse** pour la recette et un pour la production (l'environnement par défaut est
  accepté, H-15). Sans Dataverse : import des flux un par un comme packages hérités, connexions à réassocier à la main.
- Dans chaque environnement, **quatre connexions créées par le compte de service** : SharePoint, Office 365 Outlook,
  Microsoft Teams, Office 365 Utilisateurs. Leurs identifiants sont reportés dans `deploymentSettings.json`.
- La production reçoit une **solution gérée**, exportée de la recette avec `pac solution export --managed`
  ([\[8.1\]](spec.md#81-socle-commun-sapplique-à-tous-les-flux)).

### 6.3 Power BI

- Espace « HNCS-R&D Pilotage », créé par le script de publication s'il n'existe pas (`-CapacityId` facultatif).
- Groupes Entra ou personnes à affecter aux cinq rôles du modèle : `Direction`, `PilotageRD`, `Administration`,
  `RelationEcoles`, `Referent` ([\[9.6\]](spec.md#96-sécurité-du-modèle-rls--ols)). Une personne ne relève que d'un
  seul rôle.

### 6.4 Teams (facultatif)

Équipe « HNCS R&D » distincte, créée par le provisionnement si `Teams.Creer` = `true` (canaux Général, Comité R&D,
Alternants). Ses fichiers ne sont pas la référence (H-44).

---

## 7. Applications Microsoft Entra

### 7.1 « HNCS-RD Provisioning » (obligatoire, lot 1)

L'application multi-tenant historique de PnP n'existe plus : une application propre au tenant est obligatoire.

| Élément | Valeur |
| --- | --- |
| Création | `Register-PnPEntraIDAppForInteractiveLogin -ApplicationName "HNCS-RD Provisioning" -Tenant <tenant>.onmicrosoft.com` |
| Permissions déléguées | SharePoint `AllSites.FullControl` ; pour l'étape `Teams` : Microsoft Graph `Group.ReadWrite.All`, `Channel.Create`, `TeamsTab.Create` |
| Mode automatisé (facultatif) | Certificat de l'application et permissions **d'application** équivalentes ; mot de passe du `.pfx` dans `-CertificatePassword` ou `HNCSRD_CERT_PASSWORD` |
| Report | Identifiant de l'application dans `PnPClientId` (`tenant.json`) et `ClientId` (`tests/e2e/config.json`) |

### 7.2 « HNCS-RD GitLab Sync » (lot 5, facultative)

Application à comptes du tenant, sans URI de redirection, **une seule** permission d'application Microsoft Graph avec
consentement administrateur ([\[10.3\]](spec.md#103-composants-livrés), H-31) :

| Option | Permission | Portée | Condition |
| --- | --- | --- | --- |
| Recommandée | `Lists.SelectedOperations.Selected` | Écriture sur `GitlabSync`, lecture sur `SujetsRD` et `Livrables` | Disponibilité de la permission sur le tenant (`v1.0` ou `beta`) ; identifiants du site et des trois listes à fournir |
| Repli | `Sites.Selected` | Écriture sur tout le site | Le site entier, CV compris, devient techniquement accessible : **acceptation explicite par la DSI et la Direction R&D** |

Aucune autre permission (ni `Sites.Read.All`, ni `Sites.ReadWrite.All`). Informations d'identification : identité
fédérée GitLab OIDC recommandée (aucun secret), sinon secret client de 6 à 12 mois stocké uniquement dans une
variable CI masquée.

---

## 8. GitLab

| Élément | Exigence | Lot |
| --- | --- | --- |
| Instance | Instance GitLab de l'entreprise, accessible depuis le poste d'installation et depuis les runners CI | 3 |
| Groupe | `hncs-rd` créé à la main (le script ne crée aucun groupe), sous-groupes de pôle facultatifs | 3 |
| Jeton personnel | Portée `api`, détenu par un membre de l'équipe R&D, saisi pour la session et jamais stocké : création des projets de sujet | 3 |
| Jeton de groupe | Groupe `hncs-rd`, rôle Reporter, portée `read_api` seule, expiration d'un an au plus | 5 |
| Projet d'outillage | Par exemple `hncs-rd/outillage-suivi-rd` : copie du dossier `gitlab/`, `.gitlab-ci.yml` à la racine, branche `main` protégée | 5 |
| Runner | Capable d'exécuter l'image `python:3.12-slim` et d'atteindre `graph.microsoft.com` et `login.microsoftonline.com` | 5 |
| Variables CI/CD | Protégées, secrets masqués : `GITLAB_URL`, `GITLAB_TOKEN`, `HNCS_TENANT_ID`, `HNCS_CLIENT_ID`, `HNCS_CLIENT_SECRET` (sauf OIDC), `HNCS_SITE_URL`, `HNCS_SITE_ID`, `HNCS_LISTE_ID_SUJETSRD`, `HNCS_LISTE_ID_LIVRABLES`, `HNCS_LISTE_ID_GITLABSYNC` | 5 |
| Planification | `30 5 * * *`, fuseau Europe/Paris, branche `main`, variable `SCHEDULE_TYPE` = `gitlab-sync` | 5 |

---

## 9. Poste d'installation

| Outil | Version | Installation | Usage |
| --- | --- | --- | --- |
| PowerShell | **7.4 ou ultérieure** (`pwsh`) | Paquet Microsoft | Provisionnement, flux, Power BI, jeu de test, tests |
| PnP.PowerShell | **2.12 ou ultérieure** (ou 3.x) | `Install-Module PnP.PowerShell -Scope CurrentUser` | SharePoint |
| Python | **3.12**, bibliothèque standard uniquement | Paquet python.org ou gestionnaire de paquets | Contrôle de la spec, génération et construction des flux, Power BI, tests hors ligne, réconciliation |
| Power Platform CLI (`pac`) | Version courante | Installation Microsoft (outil .NET ou MSI) | Import et export de la solution |
| Az.Accounts | Version courante | `Install-Module Az.Accounts -Scope CurrentUser` | Activation des flux (API Dataverse) et publication Power BI (`-Auth Az`) ; à défaut, activation manuelle |
| MicrosoftPowerBIMgmt | Facultatif | `Install-Module MicrosoftPowerBIMgmt -Scope CurrentUser` | Alternative d'authentification Power BI (`-Auth PowerBIMgmt`) |
| Pester | **5.5 ou ultérieure** | `Install-Module Pester -MinimumVersion 5.5.0 -Scope CurrentUser` | Tests de bout en bout |
| Power BI Desktop | 2025 ou ultérieure (PBIP, TMDL, PBIR) | Microsoft Store ou installateur | Facultatif : contrôle ou publication manuelle |
| Git | Version courante | | Récupération du dépôt |

Autres exigences du poste :

- **Fuseau horaire de Paris** : les heures du jeu de test et des exports de réconciliation sont interprétées dans le
  fuseau du poste.
- Accès réseau à `*.sharepoint.com`, `login.microsoftonline.com`, `graph.microsoft.com`, à l'environnement
  Dataverse (`https://<org>.crm4.dynamics.com`), à `api.powerbi.com` et à l'instance GitLab.
- Avant toute installation, **vérifier le dépôt** : tous les contrôles hors ligne doivent réussir (guide
  d'installation, section 2.4).

---

## 10. Fichiers de configuration à préparer

Ces fichiers contiennent des adresses réelles ou des identifiants : ils sont **ignorés par git** et ne doivent
jamais être versionnés (le dépôt est public, H-30). Prévoir un jeu de fichiers par environnement.

### 10.1 `provisioning/config/tenant.json`

Copie de `tenant.sample.json`.

| Clé | Contenu |
| --- | --- |
| `TenantName` | Nom court du tenant (`contoso`) |
| `TenantAdminUrl` | `https://<tenant>-admin.sharepoint.com` |
| `SiteUrl` | URL du site (recette : avec un marqueur de recette) |
| `SiteOwner` | Propriétaire du site créé |
| `PnPClientId` | Identifiant de l'application « HNCS-RD Provisioning » |
| `CertificatePath`, `CertificateThumbprint` | Facultatifs : mode certificat |
| `ServiceAccountEmail` | Compte de service |
| `Parametres.BoiteRD`, `EmailAdministration`, `EmailDirectionRD`, `EmailDirection`, `EmailSupport` | Adresses de la section 4 |
| `Parametres.UrlRapportPowerBI` | Vide jusqu'au lot 4 |
| `Parametres.UrlCanalTeamsComite` | Lien du canal « Comité R&D » ; peut rester vide |
| `Teams.Creer`, `Teams.NomEquipe` | Création de l'équipe Teams (facultatif) |

### 10.2 `provisioning/config/membres.json`

Copie de `membres.sample.json`. Clés = codes de groupe, valeurs = listes d'UPN de **comptes utilisateurs** (un groupe
Entra ou SharePoint est refusé, H-14). Une même personne peut figurer dans plusieurs groupes
([\[7.1\]](spec.md#71-groupes-sharepoint)).

| Code | Groupe SharePoint | Membres |
| --- | --- | --- |
| G_PROP | HNCS-RD-Proprietaires | Administrateurs Microsoft 365 et IT, compte de service (ajouté d'office) |
| G_DRD | HNCS-RD-DirectionRD | Direction R&D |
| G_RD | HNCS-RD-EquipeRD | Équipe R&D |
| G_ADM | HNCS-RD-Administration | Carine et l'équipe administrative habilitée |
| G_REF | HNCS-RD-Referents | Experts référents de pôle |
| G_ALT | HNCS-RD-Alternants | Alternants et stagiaires actifs |
| G_DIR | HNCS-RD-Direction | Direction Générale |
| G_ECO | HNCS-RD-RelationEcoles | Responsables de la relation école et membres R&D qui la préparent (H-43) |

### 10.3 `flows/deploy/deploymentSettings.json`

Copie de `deploymentSettings.sample.json` (format `pac solution create-settings`). Toutes les valeurs sont
obligatoires dès le lot 1 : le script refuse une valeur vide ou commençant par `<`.

| Variable d'environnement | Valeur |
| --- | --- |
| `hncs_SiteUrl` | URL du site, sans barre finale |
| `hncs_ServiceAccountEmail` | Compte de service |
| `hncs_SupportEmail` | Adresse du support |
| `hncs_BoiteRDEmail` | Boîte partagée R&D, identique à `Destinataires.BoiteRD` |
| `hncs_BoiteRDDossierCandidatures` | Identifiant du dossier `Candidatures` de la boîte |

| Référence de connexion | Connecteur |
| --- | --- |
| `hncs_sharepoint` | SharePoint |
| `hncs_outlook` | Office 365 Outlook |
| `hncs_teams` | Microsoft Teams |
| `hncs_o365users` | Office 365 Utilisateurs |

### 10.4 Fichiers de recette

| Fichier | Modèle | Contenu |
| --- | --- | --- |
| `testdata/personas.json` | `testdata/personas.sample.json` | UPN des comptes de test (section 12) |
| `tests/e2e/config.json` | `tests/e2e/config.sample.json` | `SiteUrl` de recette, `ClientId`, `Tenant`, `ModeConnexion` (`Interactive` ou `DeviceLogin`), chemins |

---

## 11. Sécurité, confidentialité et conformité

- **Dépôt GitHub** : il est public alors que les documents de cadrage sont confidentiels. Recommandation : le
  rendre **privé** avant toute mise en service (H-30). Les documents sources ne sont pas versionnés.
- **Secrets** : aucun secret dans le dépôt, dans SharePoint ni dans `RessourcesTechniques`
  ([\[10.1\]](spec.md#101-principes)). Jetons GitLab saisis pour la session ou stockés en variables CI masquées ;
  mots de passe de certificat en variable d'environnement.
- **Données personnelles** : les CV et données nominatives restent cloisonnés ; la Direction n'accède à aucune liste
  nominative et le rapport Power BI n'importe aucune colonne personnelle
  ([\[7.5\]](spec.md#75-sécurité-des-données-personnelles), [\[9.2\]](spec.md#92-tables-importées)).
- **RGPD** : durée de conservation des candidatures et information des candidats à valider par le DPO avant
  l'activation de PA-13 et des messages automatiques (H-09, H-10).
- **Accès conditionnel** : vérifier que les politiques du tenant n'interrompent ni les connexions du compte de
  service ni l'application de synchronisation GitLab.
- **Revue des accès** : fréquence de revue des membres des groupes à fixer par la DSI (guide d'exploitation).

---

## 12. Prérequis de la recette

- Site de recette distinct de la production (section 6.1) et environnement Power Platform de recette.
- **Un compte de test par persona** de `testdata/personas.sample.json`, uniquement sur le site de recette : `IT`,
  `SVC` (compte de service de recette), `DIR_RD`, `RD1`, `RD2`, `ADMIN_CARINE`, `REF1`, `REF2`, `ALT1` à `ALT5`,
  `ALT_FIN`, `ALT_ANCIEN`, `DIRECTION`, `ECOLES`, soit 17 comptes.
- Licences de ces comptes (section 3) et accès Power BI pour les personas concernées.
- Jeu de test 100 % fictif fourni dans `testdata/` : aucune donnée réelle n'est nécessaire.
- Scénarios de recette : [\[12.1\]](spec.md#121-scénarios-de-recette) et
  [`tests/e2e/scenarios.md`](tests/e2e/scenarios.md).

---

## 13. Prérequis lot par lot

| Lot | Prérequis à réunir avant de commencer |
| --- | --- |
| 0 : Cadrage | Rôles désignés (2.1) ; atelier de validation tenu ; poste d'installation prêt (9) ; contrôles hors ligne réussis |
| 1 : Socle SharePoint | Licences (3) ; compte de service et boîte R&D (4) ; droits SharePoint (5) ; application « HNCS-RD Provisioning » (7.1) ; `tenant.json`, `membres.json` (10.1, 10.2) ; environnement Power Platform et `deploymentSettings.json` complet, pour PA-00C et PA-00D (6.2, 10.3) |
| 2 : Automatisations prioritaires | Responsable support désigné ; connexions du compte de service créées ; règles Outlook de la boîte R&D en place ; paramètres validés par la Direction R&D ; `Fonction.Lot2Actif` prêt à passer à Oui pendant la mise en service |
| 3 : Suivi opérationnel complet | Groupe GitLab `hncs-rd` ; jeton personnel `api` pour la création des projets ; responsables de la relation école désignés |
| 4 : Power BI | Lot 3 déployé (le modèle lit ses listes) ; licences Power BI Pro ; espace et, si nécessaire, capacité ; groupes à affecter aux rôles ; identifiants OAuth du compte de service |
| 5 : Stabilisation | Application « HNCS-RD GitLab Sync » et décision H-31 ; jeton de groupe `read_api` ; projet d'outillage et runner ; décision H-10 avant toute activation de PA-13 |

---

## 14. Check-list finale

| Fait | Prérequis | Section |
| --- | --- | --- |
| ☐ | Atelier du lot 0 tenu, hypothèses bloquantes tranchées (H-13, H-14, H-15) | 2 |
| ☐ | Responsable du projet, Direction R&D, administration et support désignés | 2.1 |
| ☐ | Licences Microsoft 365, Power Automate et Power BI Pro attribuées | 3 |
| ☐ | Compte de service créé, licencié, sans expiration ou avec renouvellement, « Envoyer en tant que » sur la boîte R&D | 4.1 |
| ☐ | Boîte partagée R&D et dossier `Candidatures` créés, identifiant du dossier relevé | 4.2 |
| ☐ | Adresses de l'administration, des directions et du support définies | 4.3 |
| ☐ | Droits d'administration SharePoint, Entra, Power Platform, Power BI et GitLab obtenus | 5 |
| ☐ | Environnements Power Platform avec Dataverse (recette et production) | 6.2 |
| ☐ | Quatre connexions créées par le compte de service dans chaque environnement | 6.2 |
| ☐ | Application « HNCS-RD Provisioning » inscrite, permissions accordées | 7.1 |
| ☐ | Poste d'installation équipé et réglé sur le fuseau de Paris | 9 |
| ☐ | Contrôles hors ligne du dépôt réussis | 9 |
| ☐ | `tenant.json`, `membres.json` et `deploymentSettings.json` renseignés, hors du dépôt | 10 |
| ☐ | Dépôt GitHub passé en privé | 11 |
| ☐ | Site et comptes de recette prêts (17 personas) | 12 |
| ☐ | Avant le lot 4 : espace Power BI et groupes des rôles | 6.3 |
| ☐ | Avant le lot 5 : application « HNCS-RD GitLab Sync », décision H-31, projet d'outillage et variables CI | 7.2, 8 |
| ☐ | Avant l'activation de PA-13 : durée de conservation validée par le DPO (H-10) | 2.2 |

Une fois cette liste complète, dérouler le [guide d'installation](docs/installation.md) à partir de la section 3.
