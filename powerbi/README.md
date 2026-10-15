# Power BI — HNCS-RD (lot 4)

Projet Power BI du système de suivi R&D, au format **PBIP** : modèle sémantique en **TMDL**, rapport au format
**PBIR**. Il met en œuvre `spec.md` § 9 (qui prévaut) et `specs/powerbi-rapport.md`. Reporting **en lecture seule** :
aucune réécriture vers SharePoint.

## 1. Structure

```text
powerbi/
├── HNCS-RD.pbip                         # point d'entrée Power BI Desktop
├── .gitignore                           # .pbi/localSettings.json, .pbi/cache.abf
├── HNCS-RD.SemanticModel/
│   ├── definition.pbism
│   ├── .platform
│   └── definition/
│       ├── database.tmdl                # compatibilityLevel 1600 (OLS)
│       ├── model.tmdl                   # culture fr-FR, ref table / ref role, mesures implicites désactivées
│       ├── expressions.tmdl             # paramètre SiteUrl + fonctions M partagées
│       ├── relationships.tmdl           # PBI_RELATIONS (§ 9.3)
│       ├── tables/<Table>.tmdl          # 22 tables SharePoint + Calendrier + Objectifs + Mesures
│       └── roles/<Rôle>.tmdl            # Direction, PilotageRD, Administration, Referent
├── HNCS-RD.Report/
│   ├── definition.pbir                  # byPath ../HNCS-RD.SemanticModel
│   ├── .platform
│   ├── StaticResources/                 # thème de base + thème HNCS-RD (couleurs de statut)
│   └── definition/
│       ├── report.json, version.json
│       └── pages/pages.json, pages/<id>/page.json, pages/<id>/visuals/<id>/visual.json (8 pages)
├── deploy/Publish-HNCSRDPowerBI.ps1     # publication Fabric REST (idempotente)
├── tools/generate_pbip.py               # génère TMDL + PBIR depuis provisioning/model/model.generated.json
├── tools/check_pbip.py                  # contrôle hors ligne (0 erreur exigée)
├── MESURES.md                           # définition, DAX et vigilance de chaque mesure
└── README.md
```

Les fichiers du modèle et du rapport sont **générés** : ne pas les modifier à la main, mais modifier la spec (règle
« spec d'abord »), régénérer `model.generated.json` (`python tools/spec_extract.py`), puis :

```bash
python powerbi/tools/generate_pbip.py   # réécrit HNCS-RD.SemanticModel/definition et HNCS-RD.Report
python powerbi/tools/check_pbip.py      # doit afficher « 0 erreur(s) »
```

Le générateur est déterministe (identifiants `lineageTag`, noms de pages et de visuels dérivés des noms). Une
modification faite dans Desktop puis enregistrée doit être reportée dans le générateur, sinon elle sera écrasée.

`check_pbip.py` (bibliothèque standard) vérifie notamment : JSON valides et `$schema` officiels ; chaque mesure de
`model.powerbi.measures` présente avec le **même nom** et le **même DAX** (espaces ignorés, hors divergences
déclarées) ; colonnes importées = `PBI_TABLES`, types et clés ; colonnes calculées = § 9.4 ; `$select` des requêtes M
limité aux colonnes autorisées, aucune colonne `perso`/`confidentiel` (sauf `Alternants.Title` → `NomAffichage`) ;
relations et état actif = `PBI_RELATIONS` ; rôles, RLS et OLS = `PBI_ROLES` ; 8 pages de § 9.7 ; références de
chaque visuel ; `NomAffichage` uniquement en pages 3 et 7 ; script PowerShell compatible 5.1 (BOM, parseur) ;
`MESURES.md` complet.

## 2. Ouvrir dans Power BI Desktop

1. Power BI Desktop récent (2025 ou ultérieur). Si nécessaire : *Fichier > Options > Fonctionnalités en
   préversion* : cocher « Enregistrement du projet Power BI (.pbip) », « Stocker le modèle sémantique au format
   TMDL » et « Stocker les rapports au format PBIR ».
2. Ouvrir `powerbi/HNCS-RD.pbip`.
3. *Transformer les données > Modifier les paramètres* : renseigner **`SiteUrl`**
   (ex. `https://contoso.sharepoint.com/sites/HNCS-RD`, sans `/` final). La valeur versionnée est un exemple
   (`VOTRE-TENANT`).
4. À la première connexion : source **Web** `SiteUrl`, authentification **Compte d'organisation**, confidentialité
   **Organisationnel**.
5. *Actualiser*. Contrôler *Modélisation > Gérer les rôles > Afficher en tant que* pour chaque rôle.

## 3. Source de données (Power Query)

- Une seule source : l'**API REST SharePoint**, via la fonction partagée `fnLireListeSharePoint`
  (`expressions.tmdl`) : `Web.Contents(SiteUrl, [RelativePath = "_api/web/lists/getbytitle('<titre>')/items",
  Query = [$select, $expand, $top = 5000, $skiptoken], Headers = [Accept = "application/json;odata=nometadata"]])`.
  L'URL de base étant le paramètre `SiteUrl`, la requête est **actualisable dans le service** (pas de source
  dynamique).
- **Pagination** : suivi de `odata.nextLink` ; seul le `$skiptoken` en est extrait et réinjecté dans `Query`.
- **Minimisation (P-04)** : chaque table ne demande que ses colonnes de `PBI_TABLES` (`$select` explicite). Aucune
  donnée personnelle ne transite, sauf `Alternants.Title` (→ `NomAffichage`, masquée par OLS pour `Direction`).
  Recherches : `<Nom>Id` ; personne : `Referents.Compte/EMail` (`$expand=Compte`) → `CompteEmail` (minuscules, RLS).
  `Livrables.LienDocument` / `LienGitlab` sont réduits à des booléens (`ADocument`, `AGitlab`) : l'URL n'est pas
  conservée.
- **Dates** : SharePoint renvoie l'UTC (une colonne « date seule » vaut minuit heure de Paris exprimé en UTC, ex.
  `2026-10-13T22:00:00Z` pour le 14/10). `fnHeureParis` convertit explicitement en heure de Paris (règle de l'heure
  d'été européenne), indépendamment du fuseau de la machine d'actualisation ; les colonnes `Date` deviennent des
  dates locales.
- **Types** (`fnTyperColonnes`) : `Id` et recherches en Int64, nombres sans décimale en Int64, booléens (vide → faux),
  dates, date-heures, texte.
- `SujetDomaine` : développement de `SujetsRD.DomainesId` (recherche multiple) en couples `SujetId` / `DomaineId`.
- Listes **facultatives** : `GitlabSync` (lot 5) ; si la liste n'existe pas encore, HTTP 404 → table vide. Toute autre
  liste absente fait échouer l'actualisation (volontairement).
- Les titres de listes utilisés par `getbytitle` sont les **titres affichés** de la spec (§ 4.3), ex. « Pôles R&D »,
  « Actions d'intégration et checklists » (apostrophe doublée automatiquement).

## 4. Modèle sémantique

- Tables : celles de `PBI_TABLES` (§ 9.2), plus `Mesures` (table de mesures ; colonne technique masquée
  `DerniereActualisation`). `Calendrier` est une table calculée DAX (années complètes couvrant les données, au moins
  2025-2028, plafonnées à 2020-2035 ; `Semaine` au format ISO `AAAA-Snn`, `AnneeMois` `AAAA-MM`, `Mois` trié par
  `NumMois`), marquée table de dates. `Objectifs` est un `DATATABLE` des 7 cibles de § 9.5 (H-20).
- Colonnes calculées : exactement § 9.4 (dont `PoleNom` dénormalisé sur `SujetsRD`, `Offres`, `Candidatures`).
- Relations : exactement `PBI_RELATIONS` (plusieurs-à-un, filtrage simple, inactives activées par `USERELATIONSHIP`).
- Mesures : les 57 mesures de § 9.5 (noms et DAX identiques, sauf divergence § 10), rangées en dossiers Recrutement
  / Effectifs / Livrables / Comptes rendus / Écoles / Communications / Qualité / Objectifs, plus 2 mesures techniques
  (dossier « Technique (hors spec) »). Détail : `MESURES.md`.
- Mesures implicites désactivées (`discourageImplicitMeasures`) ; date/heure automatique désactivée.

**Portée du filtre `Calendrier`** (relations actives) : candidatures par `DateReceptionJour`, livrables et comptes
rendus par `Echeance`. Par propagation, les entretiens suivent la date de réception de leur candidature, et les
communications et mobilisations suivent **l'échéance du livrable lié** (voir § 10, D-03). Les alternants, affectations,
conventions et établissements ne sont pas filtrés par `Calendrier` (sauf `[Alternants présents sur la période]`).

## 5. Sécurité (RLS / OLS)

| Rôle | Membres (service) | RLS | OLS |
| --- | --- | --- | --- |
| Direction | Direction Générale | aucune | `Alternants[NomAffichage]` : `metadataPermission: none` |
| PilotageRD | Direction R&D, équipe R&D | aucune | aucune |
| Administration | Équipe administrative | `Livrables`, `ComptesRendus`, `Mobilisations`, `GitlabSync` : `FALSE ()` | aucune |
| Referent | Référents | `Referents[CompteEmail] = USERPRINCIPALNAME ()` ; alternants de ses affectations ; `Candidatures`, `Entretiens`, `ActionsIntegration` : `FALSE ()` | aucune |

- Les membres sont affectés **dans le service** (H-16) : *Modèle sémantique > Sécurité*. Aucun membre n'est versionné.
- Les alternants n'ont **aucun** accès au rapport ni à l'espace (H-19).
- Les membres de l'espace ayant le rôle Administrateur, Membre ou Contributeur **ne sont pas soumis** à la RLS/OLS :
  les publics du rapport doivent être **Lecteurs** (ou recevoir une application).
- Limitation Power BI : une personne ne peut pas cumuler un rôle avec OLS (`Direction`) et un rôle avec RLS
  (`Administration`, `Referent`) — erreur à l'affichage. Une personne de la Direction Générale qui est aussi référent
  doit être placée dans un seul rôle.
- Pour le rôle `Direction`, les visuels qui utilisent `NomAffichage` (tableau des affectations de la page 3) affichent
  une erreur de champ : c'est l'effet attendu de l'OLS (page 7 : public PilotageRD / Referent).
- La RLS `Referent` compare `USERPRINCIPALNAME ()` à l'adresse `EMail` du compte SharePoint : l'UPN et l'adresse de
  messagerie doivent coïncider (voir § 10, D-07).

## 6. Rapport

| # | Page | Contenu |
| --- | --- | --- |
| 1 | Vue exécutive | 9 cartes, 6 jauges indicateur / `[Cible]`, jauge couverture (0-100 %), livrables par statut ; segments année, trimestre |
| 2 | Recrutement | 8 cartes, entonnoir, candidatures par mois × canal, motifs agrégés, entretiens à venir ; segments canal, offre, période, statut |
| 3 | Effectifs et encadrement | 6 cartes, alternants par pôle, charge des référents, matrice établissement × pôle, tableau des affectations ; segments pôle, établissement, référent, période |
| 4 | Projets et livrables | 8 cartes, livrables type × statut, échéances par semaine, avancement par sujet, jalons GitLab en écart ; segments pôle (`PoleNom`), sujet, type, période |
| 5 | Établissements et partenariats | 5 cartes, alternants accueillis par établissement, recommandations, conventions ; segments établissement, type de convention |
| 6 | Communications et valorisation | 4 cartes, publications par mois (date de publication), communications par canal, communications publiées ; segments canal, période |
| 7 | Comité R&D | 6 cartes ; tableaux livrables (14 jours / retard), affectations à risque ou bloquées, sujets bloqués, comptes rendus manquants ; segments pôle, référent |
| 8 | Qualité des données | 4 cartes, transitions refusées par objet et en détail |

Chaque page porte un titre et la date de dernière actualisation (`[Dernière actualisation]`). Les jauges filtrent
`Objectifs[Indicateur]` au niveau du visuel. Les tableaux de détail n'exposent que des `IdHNCS`, des titres de sujets
ou de livrables, des statuts et des dates ; `NomAffichage` uniquement en pages 3 et 7.

## 7. Publication

### 7.1 Script (API REST Fabric)

```powershell
# Az.Accounts (défaut) ; ou -Auth PowerBIMgmt (MicrosoftPowerBIMgmt) ; ou -Auth Token -AccessToken <jeton>
.\powerbi\deploy\Publish-HNCSRDPowerBI.ps1 -SiteUrl https://contoso.sharepoint.com/sites/HNCS-RD -ConfigurerPlanification
# Vérification hors ligne des définitions envoyées (aucun appel d'API) :
.\powerbi\deploy\Publish-HNCSRDPowerBI.ps1 -SiteUrl https://contoso.sharepoint.com/sites/HNCS-RD -PreparationSeule -DossierSortie .\out
```

Le script : obtient un jeton (audience Power BI / Fabric) ; crée l'espace « HNCS-R&D Pilotage » s'il n'existe pas
(`-CapacityId` facultatif) ; envoie le modèle (`POST /v1/workspaces/{id}/semanticModels`, ou
`.../semanticModels/{id}/updateDefinition` s'il existe) avec `SiteUrl` injecté dans `expressions.tmdl` ; envoie le
rapport (`/reports`, idem) en réécrivant `definition.pbir` en `byConnection` vers le modèle publié ; suit les opérations
longues (202 + `Location`) et les limitations (429) ; déclenche une actualisation (`-SkipRefresh` pour l'éviter) ;
avec `-ConfigurerPlanification`, applique l'actualisation quotidienne 06:00 (Romance Standard Time). `-WhatIf` est pris
en charge. Compatible Windows PowerShell 5.1 (fichier UTF-8 avec BOM) et PowerShell 7.

Prérequis : droits de création d'espace / d'éléments ; selon la configuration du tenant, les API de définition
d'éléments Fabric peuvent exiger un espace sur capacité (Fabric, Premium ou PPU). À défaut, utiliser 7.2.

### 7.2 Alternative manuelle

Ouvrir le PBIP dans Desktop (§ 2), actualiser, *Fichier > Publier* vers « HNCS-R&D Pilotage ».

### 7.3 Étapes manuelles dans le service (après la première publication)

1. **Identifiants** : *Paramètres du modèle > Informations d'identification de la source de données > Web
   (SiteUrl) > Modifier* : OAuth2, compte de service (H-13, H-16), confidentialité « Organisationnel ».
2. **Actualisation planifiée** : quotidienne à **06:00** (Romance Standard Time), après les flux de nuit, notification
   en cas d'échec — si `-ConfigurerPlanification` n'a pas pu l'appliquer (identifiants absents).
3. **Rôles** : affecter les groupes Entra / personnes à `Direction`, `PilotageRD`, `Administration`, `Referent` (H-16).
4. **Accès** : publics en Lecteur ; lien du rapport dans le paramètre `Lien.RapportPowerBI` (synthèses PA-11).

## 8. Actualisation

Mode import, une source (SharePoint REST), sans passerelle. Volume : `$top=5000` par page, pagination illimitée.
Les listes sont relues intégralement à chaque actualisation (pas d'actualisation incrémentielle en V1). Échec typique :
identifiants expirés, liste renommée (le titre affiché est la clé de `getbytitle`), colonne supprimée ou renommée
(`$select` en erreur 400).

## 9. Réconciliation avec SharePoint (`tests/e2e/reconciliation/`)

Principe : pour chaque mesure clé, recompter les éléments SharePoint avec la même règle, **sans filtre de rapport**,
sous un compte non restreint (rôle PilotageRD), juste après une actualisation. Requête de référence :
`GET {SiteUrl}/_api/web/lists/getbytitle('<titre>')/items?$select=Id,...&$filter=<filtre>&$top=5000` (paginer sur
`odata.nextLink`, compter les éléments). Les comparaisons de dates se font en **heure de Paris** (convertir
« aujourd'hui » et les dates UTC renvoyées par l'API). Les filtres « < aujourd'hui » sont plus simples à appliquer
côté test après lecture (`$select` des colonnes utiles) qu'en OData.

| Mesure | Liste (titre) | Règle SharePoint équivalente (`$filter` OData ou calcul après lecture) | Vue SharePoint proche |
| --- | --- | --- | --- |
| Candidatures reçues | Candidatures | tous les éléments | — |
| Candidatures actives | Candidatures | `Statut ne 'Intégrée' and Statut ne 'Non retenue' and Statut ne 'Clôturée'` | Candidatures en cours |
| Candidatures en attente | Candidatures + Paramètres | actives et (aujourd'hui − `DateStatut` ou `DateReception`, en jours calendaires) > `Delai.SeuilAttenteCandidatureJours` | — |
| Délai moyen de présélection (j) | Candidatures | moyenne des écarts en jours calendaires (Paris) `DateDecisionPreselection − DateReception`, éléments où la décision est renseignée | — |
| Candidatures analysées | Candidatures | `DateDecisionPreselection ne null` | — |
| Candidatures présélectionnées | Candidatures | `DateTransmissionAdmin ne null` | Transmises à l'administration (approx.) |
| Entretiens réalisés | Entretiens | `Statut eq 'Réalisé'` | Tous les entretiens (regroupés) |
| Entretiens à venir | Entretiens | `Statut eq 'Planifié' and DateHeure ge datetime'<maintenant UTC>'` | Entretiens à venir |
| Candidatures retenues | Candidatures | `Statut eq 'Retenue' or Statut eq 'Formalités en cours' or Statut eq 'Intégrée'` | — |
| Candidatures intégrées | Candidatures | `Statut eq 'Intégrée'` | — |
| Doublons signalés | Candidatures | `DoublonPotentiel eq 1` | Doublons potentiels (sans les clôturées) |
| Alternants actifs | Alternants | `Statut eq 'Actif' or Statut eq 'Fin planifiée'` | Alternants actifs (inclut À intégrer, Suspendu) |
| Alternants accueillis | Alternants | `Statut ne 'À intégrer'` | Historique des alternants |
| Affectations actives | Affectations | `Statut eq 'Active' or Statut eq 'À risque' or Statut eq 'Bloquée'` | Affectations en cours (inclut À préparer) |
| Affectations sans référent | Affectations | `ReferentId eq null` et statut ∈ {À préparer, Active, À risque, Bloquée} | Sans référent |
| Affectations incomplètes | Affectations + Livrables | non terminées et (sans référent, ou sans `DateFin`, ou aucun livrable dont `AffectationId` = l'affectation) | — |
| Livrables validés | Livrables | `Statut eq 'Validé' or Statut eq 'Archivé / clôturé'` | Capitalisés (archivés seuls) |
| Livrables en retard | Livrables | statut ∈ {À produire, En cours, Corrections demandées} et `Echeance` < aujourd'hui (Paris) | En retard (`EnRetard`, recalculé par PA-06 à 07:00) |
| Taux de remise à l'heure | Livrables | échus (`Echeance` ≤ aujourd'hui, hors Suspendu / abandonné) avec `DatePremierDepot` (date Paris) ≤ `Echeance` ÷ échus | — |
| Taux de validation au premier passage | Livrables | (validés ou archivés avec `NbCorrections` = 0 ou vide) ÷ (`DateRevue ne null`) | — |
| Taux de capitalisation | Livrables | archivés avec `LienDocument` et, si POC / plan, DoD1-5 = Oui ÷ archivés | Capitalisés |
| POC réalisés | Livrables | `Statut eq 'Archivé / clôturé' and TypeLivrable eq 'POC / démonstrateur'` et DoD1-5 = Oui | Capitalisés (regroupés par type) |
| Plans de stratégie formalisés | Livrables | idem avec `TypeLivrable eq 'Plan de stratégie'` | Capitalisés |
| Couverture des domaines cibles | DomainesCibles, SujetsRD, Affectations, Livrables | domaines `Cible` = Oui et `Statut` = Actif ayant au moins un sujet (`DomainesId`) qui porte une affectation avec un livrable validé ou archivé ÷ domaines cibles actifs | — |
| Sujets bloqués | Sujets R&D | `Statut eq 'Bloqué' or Statut eq 'À arbitrer'` | À arbitrer (inclut Proposé) |
| Mobilisations commerciales | Mobilisations commerciales | tous les éléments | — |
| Comptes rendus manquants | Comptes rendus de suivi | `Statut eq 'Non remis'` ou (statut ∈ {Attendu, En rédaction} et `Echeance` < aujourd'hui) | Non remis (statut seul) |
| Blocages signalés | Comptes rendus de suivi | `BlocageSignale eq 1` | Blocages signalés |
| Partenariats académiques actifs | Conventions et partenariats | `Statut eq 'Signée / active' and (TypeConvention eq 'Convention de partenariat' or TypeConvention eq 'Sponsoring')` | Conventions en cours (filtrer) |
| Conventions à renouveler | Conventions et partenariats | `Statut eq 'À renouveler'` | À renouveler |
| Établissements collaborants | Écoles et établissements | `Statut` ∈ {Établissement d'accueil, Partenariat à évaluer, Partenaire actif} (apostrophe doublée en OData) | — |
| Partenariats à évaluer | Écoles et établissements | `Statut eq 'Partenariat à évaluer'` | Partenariats à évaluer |
| Bilans réalisés | Bilans d'alternance | `Statut eq 'Réalisé'` | — |
| Communications publiées | Communications R&D | `Statut eq 'Publiée'` | — |
| Livrables valorisés | Communications R&D | nombre de `LivrableSourceId` **distincts non vides** parmi les publiées | — |
| Actions en retard | Actions d'intégration et checklists | statut ∈ {À faire, En cours, Bloquée} et `Echeance` < aujourd'hui | — |
| Transitions refusées | Historique des statuts | `Resultat eq 'Refusée — annulée'` | — |

Contrôles complémentaires : par rôle (*Afficher en tant que* ou API `executeQueries` avec `impersonatedUserName`),
`Administration` doit voir 0 livrable, `Referent` uniquement les alternants de ses affectations, `Direction` aucune
colonne `NomAffichage`.

## 10. Divergences et questions pour la spec

| ID | Section | Constat | Implémenté | Proposition pour `spec.md` |
| --- | --- | --- | --- | --- |
| D-01 | § 9.5 `[Livrables valorisés]` | `DISTINCTCOUNT` compte la valeur vide : une communication publiée sans livrable source ajoute 1 | `DISTINCTCOUNTNOBLANK` (seule mesure modifiée) | Remplacer `DISTINCTCOUNT` par `DISTINCTCOUNTNOBLANK` |
| D-02 | § 9.5 `[Entretiens réalisés]` dans l'entonnoir (§ 9.7 p. 2) | La mesure compte des entretiens, pas des candidatures ; l'étape peut dépasser les présélectionnées | Mesure de la spec, utilisée telle quelle dans l'entonnoir | Ajouter `[Candidatures avec entretien réalisé] = CALCULATE ( DISTINCTCOUNT ( Entretiens[CandidatureId] ), Entretiens[Statut] = "Réalisé" )` pour l'entonnoir |
| D-03 | § 9.3 / § 9.7 p. 1 et 6 | Avec un filtre `Calendrier`, `CommunicationsRD` et `Mobilisations` sont filtrées par l'**échéance du livrable lié** (chemin actif `Calendrier → Livrables → …`) et les éléments sans livrable disparaissent ; « publications par mois » est impossible avec les seules mesures de la spec | Relations de la spec ; mesure technique `[Communications publiées (date de publication)]` (`USERELATIONSHIP` sur `DateEffective`) pour l'histogramme mensuel | Ajouter cette mesure à § 9.5, et préciser la portée temporelle voulue des cartes Communications / Mobilisations en page 1 (ou ajouter `Mobilisations[DateMobilisation] → Calendrier[Date]` inactive) |
| D-04 | `specs/powerbi-rapport.md` p. 6 | Le tableau des communications publiées demande le **titre**, mais `CommunicationsRD.Title` n'est pas dans `PBI_TABLES` | Tableau : IdHNCS, canal, date, titre du livrable source | Ajouter `Title` à `CommunicationsRD` dans `PBI_TABLES` (colonne non personnelle) ou retirer « titre » |
| D-05 | `specs/powerbi-rapport.md` (dates de dernière actualisation) | Aucune mesure ni table ne porte l'horodatage d'actualisation | Colonne masquée `Mesures[DerniereActualisation]` + mesure technique `[Dernière actualisation]` | Ajouter la mesure à § 9.5 |
| D-06 | § 9.5 `[Seuil attente (j)]` | Si la clé est absente, `VALUE ( BLANK () )` peut renvoyer une valeur vide sans erreur : le repli sur 10 ne joue pas | Mesure de la spec | `VAR v = … RETURN IF ( ISBLANK ( v ), 10, IFERROR ( VALUE ( v ), 10 ) )` |
| D-07 | § 9.2 / § 9.6 (RLS Referent) | `CompteEmail` = adresse `EMail` SharePoint, comparée à `USERPRINCIPALNAME ()` : faux négatif si UPN ≠ adresse principale | `Compte/EMail` en minuscules (la comparaison DAX est insensible à la casse) | Décider (DSI) : exiger UPN = adresse, ou importer l'UPN depuis `Compte/Name` (`i:0#.f\|membership\|<upn>`) |
| D-08 | § 9.1 (`getbytitle`) | Le titre affiché est la clé d'accès : un renommage de liste casse l'actualisation ; accents, `&`, apostrophes | `getbytitle` avec titres de § 4.3 (apostrophes doublées) | Envisager `_api/web/GetList('<chemin>/Lists/<NomInterne>')` (nom interne stable) |
| D-09 | § 9.5 / § 9.4 (dates) | `TODAY ()` / `NOW ()` sont en UTC dans le service ; `DATEVALUE` sur des date-heures dépend d'une conversion texte implicite | Spec telle quelle ; dates SharePoint converties en heure de Paris dans M | Accepter l'écart (00:00-02:00) ou introduire une mesure « Aujourd'hui (Paris) » ; préférer `INT ( … )` à `DATEVALUE` |
| D-10 | § 9.6 / § 9.7 p. 3 | OLS sur `NomAffichage` : le tableau des affectations de la page 3 (public Direction) est en erreur pour ce rôle ; Power BI interdit de cumuler OLS et RLS via plusieurs rôles | Conforme à la spec | Retirer `NomAffichage` de la page 3 ou dédier un visuel non Direction ; documenter la règle de non-cumul des rôles |
| D-11 | § 9.5 `[Taux de validation au premier passage]` | Cadrage § 8.2 : dénominateur « livrables soumis à revue » ; spec : livrables **revus** (`DateRevue`) | Spec | Confirmer le dénominateur |
| D-12 | § 9.2 `GitlabSync` (lot 5) | Le rapport est livré au lot 4 alors que la liste n'existe qu'au lot 5 | Liste lue en mode facultatif (404 → table vide) | Mentionner ce mode facultatif dans § 9.2 |
| D-13 | `specs/powerbi-rapport.md` p. 4 | Un tableau GitLab contenant `[Écarts d'échéance GitLab]` n'affiche que les jalons en écart (lignes sans valeur masquées) | Tableau titré « Jalons GitLab en écart d'échéance » | Confirmer, ou afficher la colonne `EcartEcheance` sans mesure |

## 11. Limites

- Aucun tenant ni Power BI Desktop n'était disponible à la génération : le projet est validé hors ligne
  (`check_pbip.py`, parseur PowerShell, préparation à blanc du script), pas ouvert dans Desktop. À valider à la
  première ouverture : lecture TMDL (colonnes de tables calculées, OLS), schémas PBIR (versions 1.0.0 des schémas
  visuels / pages), rendu des visuels (entonnoir multi-mesures, jauges filtrées, segments), thème de base minimal
  (`CY24SU10.json`, remplaçable par celui de Desktop), et performances de la pagination sur les grosses listes.
- Pas d'actualisation incrémentielle ; pas de passerelle (source cloud).
- `[Couverture des domaines cibles]` ignore les filtres du rapport (indicateur global, conforme à la spec).
- Les identifiants OAuth, la planification (si non appliquée par le script) et les membres des rôles restent manuels.
