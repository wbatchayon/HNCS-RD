# Power BI : HNCS-RD (lot 4)

Projet Power BI du système de suivi R&D, au format **PBIP** : modèle sémantique en **TMDL**, rapport au format
**PBIR**. Il met en œuvre `spec.md` [\[9\]](../spec.md#9-modèle-power-bi-et-mesures-dax) (v1.6.0, qui prévaut) et `specs/powerbi-rapport.md`. Reporting **en lecture
seule** : aucune réécriture vers SharePoint.

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
│       └── roles/<Rôle>.tmdl            # Direction, PilotageRD, Administration, RelationEcoles, Referent
├── HNCS-RD.Report/
│   ├── definition.pbir                  # byPath ../HNCS-RD.SemanticModel
│   ├── .platform
│   ├── StaticResources/                 # thème de base + thème HNCS-RD (couleurs de statut)
│   └── definition/
│       ├── report.json, version.json
│       └── pages/pages.json, pages/<id>/page.json, pages/<id>/visuals/<id>/visual.json (8 pages)
├── deploy/Publish-HNCSRDPowerBI.ps1     # publication Fabric REST (idempotente)
├── tools/generate_pbip.py               # génère TMDL + PBIR depuis provisioning/model/model.generated.json et spec.md § 9.4
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

`check_pbip.py` (bibliothèque standard, indépendant du générateur) vérifie notamment :

- JSON valides et `$schema` officiels ;
- chaque mesure de `model.powerbi.measures` présente avec le **même nom** et le **même DAX** que [\[9.5\]](../spec.md#95-mesures) (espaces
  ignorés), aucune mesure hors spec ;
- colonnes importées = `PBI_TABLES` (types, clés, `sourceColumn`), colonnes calculées = [\[9.4\]](../spec.md#94-colonnes-calculées) (DAX identique),
  `Calendrier`, `Objectifs` et colonne masquée `Mesures[DerniereActualisation]` (`DateTimeZone.FixedUtcNow`) ;
- lecture SharePoint par `GetList` sur le **nom interne** (jamais `getbytitle`), `$select` limité aux colonnes
  autorisées, aucune colonne `perso`/`confidentiel` (sauf `Alternants.Title` → `NomAffichage`), conversion en heure
  de Paris de chaque colonne `Date` / `DateTime`, `GitlabSync` seule liste facultative ;
- relations et état actif = `PBI_RELATIONS`, filtrage simple ;
- 5 rôles, RLS et OLS = `PBI_ROLES` ;
- 8 pages de [\[9.7\]](../spec.md#97-pages-du-rapport) ; chaque visuel ne référence que des mesures / colonnes existantes ; **`NomAffichage` dans aucun
  visuel** ; chaque mesure `[X]` et colonne `Table[Colonne]` citée par `specs/powerbi-rapport.md` présente sur sa
  page ; `[Dernière actualisation]` sur chaque page ;
- équilibre des parenthèses / crochets / accolades du DAX et du M ;
- script PowerShell compatible 5.1 (BOM, pas de `??` / `?.`, parseur Windows PowerShell si disponible) ;
- `MESURES.md` complet.

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
  (`expressions.tmdl`) :
  `Web.Contents(SiteUrl, [RelativePath = "_api/web/GetList('<chemin du site>/Lists/<NomInterne>')/items",
  Query = [$select, $expand, $top = 5000, $skiptoken], Headers = [Accept = "application/json;odata=nometadata"]])`.
  Le chemin du site est dérivé de `SiteUrl` (`Uri.Parts(SiteUrl)[Path]`) ; les bibliothèques (aucune importée à ce
  jour) utilisent `GetList('<chemin du site>/<NomInterne>')` (5ᵉ paramètre `bibliotheque`). L'URL de base étant le
  paramètre `SiteUrl`, la requête est **actualisable dans le service** (pas de source dynamique).
- Les listes sont désignées par leur **nom interne** (URL, [\[2.2\]](../spec.md#22-conventions-de-nommage)), jamais par leur titre affiché : un renommage du
  titre n'a pas d'effet.
- **Pagination** : suivi de `odata.nextLink` ; seul le `$skiptoken` en est extrait et réinjecté dans `Query`.
- **Minimisation (P-04)** : chaque table ne demande que ses colonnes de `PBI_TABLES` (`$select` explicite). Aucune
  donnée personnelle ne transite, sauf `Alternants.Title` (→ `NomAffichage`, masquée par OLS pour `Direction` et
  absente de tous les visuels). Recherches : `<Nom>Id` ; personne : `Referents.Compte/EMail` (`$expand=Compte`) →
  `CompteEmail` (minuscules, RLS ; UPN = adresse, H-47).
- **URL** : `Livrables.LienDocument` et `CommunicationsRD.UrlPublication` sont importées en texte (catégorie *URL
  web*, liens cliquables) ; `Livrables.LienDocument` et `LienGitlab` donnent aussi les booléens `ADocument` /
  `AGitlab` (copie de la colonne brute avant typage).
- **Dates** : SharePoint renvoie l'UTC (une colonne « date seule » vaut minuit heure de Paris exprimé en UTC, ex.
  `2026-10-13T22:00:00Z` pour le 14/10). `fnHeureParis` convertit explicitement en heure de Paris (règle de l'heure
  d'été européenne), indépendamment du fuseau de la machine d'actualisation ; les colonnes `Date` deviennent des
  dates locales ([\[9.1\]](../spec.md#91-projet)).
- **Types** (`fnTyperColonnes`) : `Id` et recherches en Int64, nombres sans décimale en Int64, booléens (vide → faux),
  dates, date-heures, texte, URL.
- `SujetDomaine` : développement de `SujetsRD.DomainesId` (recherche multiple) en couples `SujetId` / `DomaineId`.
- Liste **facultative** : `GitlabSync` (lot 5) ; si elle n'existe pas encore, HTTP 404 → table vide. Toute autre
  liste absente fait échouer l'actualisation (volontairement).

## 4. Modèle sémantique

- Tables : celles de `PBI_TABLES` ([\[9.2\]](../spec.md#92-tables-importées)), plus `Mesures` (table de mesures ; colonne masquée
  `DerniereActualisation` = `DateTimeZone.FixedUtcNow` converti en heure de Paris). `Calendrier` est une table
  calculée DAX (années complètes couvrant les données, au moins 2025-2028, plafonnées à 2020-2035 ; `Semaine` au
  format ISO `AAAA-Snn`, `AnneeMois` `AAAA-MM`, `Mois` trié par `NumMois`), marquée table de dates. `Objectifs` est un
  `DATATABLE` des 7 cibles de [\[9.5\]](../spec.md#95-mesures) (H-20).
- Colonnes calculées : exactement [\[9.4\]](../spec.md#94-colonnes-calculées) (dates ramenées au jour par `DATE ( YEAR, MONTH, DAY )` ; `PoleNom`
  dénormalisé sur `SujetsRD`, `Offres`, `Candidatures`).
- Relations : exactement `PBI_RELATIONS` (plusieurs-à-un, filtrage simple, inactives activables par
  `USERELATIONSHIP`).
- Mesures : les 60 mesures de [\[9.5\]](../spec.md#95-mesures), noms et DAX identiques, rangées en dossiers Recrutement / Effectifs / Livrables /
  Comptes rendus / Écoles / Communications / Qualité / Objectifs / Technique (sections de [\[9.5\]](../spec.md#95-mesures)). Détail : `MESURES.md`.
- Mesures implicites désactivées (`discourageImplicitMeasures`) ; date/heure automatique désactivée.

**Portée du filtre `Calendrier`** (relations actives) : candidatures par `DateReceptionJour`, livrables et comptes
rendus par `Echeance`, communications par `DateEffective`, mobilisations par `DateMobilisation`. Par propagation,
les entretiens suivent la date de réception de leur candidature. Les alternants, affectations, conventions,
établissements et actions ne sont pas filtrés par `Calendrier` (sauf `[Alternants présents sur la période]`, qui lit
la période sélectionnée). Les relations communications → livrable source et mobilisations → livrable sont
**inactives** : un segment sur les livrables ou les sujets ne filtre ni les communications ni les mobilisations.
`ActionsIntegration[AlternantId]` → `Alternants` est active : un filtre sur les alternants (pôle, établissement)
écarte les actions rattachées à une seule candidature.

## 5. Sécurité (RLS / OLS)

| Rôle | Membres (service) | RLS | OLS |
| --- | --- | --- | --- |
| Direction | Direction Générale | `Parametres` : seule la clé `Delai.SeuilAttenteCandidatureJours` ; `HistoriqueStatuts` : `FALSE ()` | `Alternants[NomAffichage]` : `metadataPermission: none` |
| PilotageRD | Direction R&D, équipe R&D | aucune | aucune |
| Administration | Équipe administrative | `Candidatures` : `NOT ISBLANK ( Candidatures[DateTransmissionAdmin] )` (et donc leurs entretiens) ; `Livrables`, `ComptesRendus`, `Mobilisations`, `GitlabSync` : `FALSE ()` | aucune |
| RelationEcoles | Relation écoles (G_ECO) | `Candidatures`, `Entretiens`, `ActionsIntegration`, `Livrables`, `ComptesRendus`, `Mobilisations`, `GitlabSync` : `FALSE ()` ; `Parametres` : seule la clé `Delai.SeuilAttenteCandidatureJours` ; `HistoriqueStatuts` : `FALSE ()` | `Alternants[NomAffichage]` : `metadataPermission: none` |
| Referent | Référents | `Referents[CompteEmail] = USERPRINCIPALNAME ()` ; alternants de ses affectations ; `ActionsIntegration` : actions rattachées aux alternants de ses affectations (`AlternantId` non vide) ; `Candidatures`, `Entretiens` : `FALSE ()` ; `Parametres` : seule la clé `Delai.SeuilAttenteCandidatureJours` ; `HistoriqueStatuts` : `FALSE ()` | aucune |

- Les membres sont affectés **dans le service** (H-16) : *Modèle sémantique > Sécurité*. Aucun membre n'est versionné.
- Les membres doivent être **Lecteurs** de l'espace (les rôles Administrateur, Membre et Contributeur ne sont pas
  soumis à la RLS/OLS). Les alternants n'ont **aucun** accès (H-19) ; pas de rôle Communication / Avant-vente (H-52).
- Une personne relève d'**un seul** rôle : Power BI interdit de cumuler un rôle avec OLS (`Direction`) et un rôle avec
  RLS (`Administration`, `RelationEcoles`, `Referent`).
- `NomAffichage` n'est utilisé par aucun visuel : l'OLS est une défense en profondeur, et aucun visuel n'est en erreur.
  Règle (RX-03) : la colonne est masquée par OLS pour **tout rôle dont le groupe SharePoint n'a pas d'accès à la liste
  `Alternants`** (matrice [\[7.3\]](../spec.md#73-matrice-daccès) : G_DIR et G_ECO → `Direction`, `RelationEcoles`) ; `check_pbip.py` la vérifie à partir
  de la matrice. Les tableaux identifient les alternants par leur `IdHNCS`.
- RX-04 : les rôles `Direction`, `RelationEcoles` et `Referent` ne voient de `Parametres` que la clé du seuil d'attente
  (utilisée par `[Seuil attente (j)]`) et aucune ligne de `HistoriqueStatuts` (`[Transitions refusées]` vide).
- La RLS `Referent` compare `USERPRINCIPALNAME ()` à l'adresse `EMail` du compte SharePoint (UPN = adresse, H-47).

### 5.1 Pages par public : audiences de l'application Power BI

La RLS et l'OLS protègent les **données**, pas les **pages** : un membre d'un rôle voit toutes les pages du
rapport (avec des données filtrées). La restriction des pages par public se fait par les **audiences de
l'application Power BI** publiée depuis l'espace « HNCS-R&D Pilotage » (spec [\[9.7\]](../spec.md#97-pages-du-rapport)) :

| Audience (= rôle) | Pages visibles |
| --- | --- |
| Direction | 1 Vue exécutive, 3 Effectifs et encadrement, 4 Projets et livrables, 5 Établissements et partenariats, 6 Communications et valorisation |
| Administration | 2 Recrutement, 3 Effectifs et encadrement, 5 Établissements et partenariats |
| RelationEcoles | 3 Effectifs et encadrement, 5 Établissements et partenariats |
| Referent | 3 Effectifs et encadrement, 4 Projets et livrables, 7 Comité R&D |
| PilotageRD | toutes (1 à 8) |

Mise en place (manuelle, après publication) : *Espace de travail > Créer une application > Audience* : une audience
par public ci-dessus, pages masquées / affichées en conséquence, accès donné aux mêmes groupes Entra que le rôle RLS
correspondant. Chaque membre d'une audience doit aussi être affecté au rôle de même nom ([\[5\]](../spec.md#5-bibliothèques-documentaires)) ; une personne relève
d'une seule audience et d'un seul rôle. Les audiences ne sont pas une mesure de sécurité : la sécurité reste la
RLS / OLS. Les liens `LienDocument` (page 4) sont visibles de la Direction, qui a la lecture sur « 04 - Livrables R&D »
(travaux sans donnée personnelle, spec [\[9.7\]](../spec.md#97-pages-du-rapport)).

## 6. Rapport

| # | Page | Contenu |
| --- | --- | --- |
| 1 | Vue exécutive | 10 cartes (dont `[Sujets actifs]`), 6 jauges indicateur / `[Cible]`, jauge couverture (0-100 %), livrables par statut, candidatures par statut ; segments année, trimestre |
| 2 | Recrutement | 8 cartes, entonnoir (… → `[Candidatures avec entretien réalisé]` → …), candidatures par mois × canal, motifs agrégés, entretiens à venir ; segments canal, offre, période, statut |
| 3 | Effectifs et encadrement | 6 cartes, alternants par pôle, charge des référents, matrice établissement × pôle, tableau des affectations (IdHNCS affectation et alternant, sans nom) ; segments pôle, établissement, référent, période |
| 4 | Projets et livrables | 9 cartes (dont `[Écarts d'échéance GitLab]`), livrables type × statut, échéances par semaine, avancement par sujet, livrables et documents (`LienDocument`), jalons GitLab non orphelins (colonne `EcartEcheance`, filtre de visuel `Orpheline` = Faux, RX-07) ; segments pôle (`PoleNom`), sujet, type, période |
| 5 | Établissements et partenariats | 5 cartes, alternants accueillis par établissement, recommandations, conventions, prochaines interactions (`DateProchaineAction`) ; segments établissement, type de convention |
| 6 | Communications et valorisation | 4 cartes, publications externes par mois (`DateEffective`), communications par canal, communications publiées (IdHNCS, titre, canal, date, externe, `UrlPublication`) ; segments canal, période |
| 7 | Comité R&D | 6 cartes ; tableaux livrables (14 jours / retard), affectations à risque ou bloquées, sujets bloqués, comptes rendus manquants ; segments pôle, référent |
| 8 | Qualité des données | 4 cartes, transitions refusées par objet et en détail |

Chaque page porte un titre et la carte `[Dernière actualisation]`. Les jauges filtrent `Objectifs[Indicateur]` au
niveau du visuel. Les tableaux de détail n'exposent que des `IdHNCS`, des titres de sujets, de livrables ou de
communications, des statuts, des dates et des liens.

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
avec `-ConfigurerPlanification`, applique l'actualisation quotidienne 07:45 (Romance Standard Time). `-WhatIf` est pris
en charge. Compatible Windows PowerShell 5.1 (fichier UTF-8 avec BOM) et PowerShell 7.

Prérequis : droits de création d'espace / d'éléments ; selon la configuration du tenant, les API de définition
d'éléments Fabric peuvent exiger un espace sur capacité (Fabric, Premium ou PPU). À défaut, utiliser 7.2.

### 7.2 Alternative manuelle

Ouvrir le PBIP dans Desktop ([\[2\]](../spec.md#2-architecture-et-conventions-de-nommage)), actualiser, *Fichier > Publier* vers « HNCS-R&D Pilotage ».

### 7.3 Étapes manuelles dans le service (après la première publication)

1. **Identifiants** : *Paramètres du modèle > Informations d'identification de la source de données > Web
   (SiteUrl) > Modifier* : OAuth2, compte de service (H-13, H-16), confidentialité « Organisationnel ».
2. **Actualisation planifiée** : quotidienne à **07:45** (Romance Standard Time), après les flux planifiés du matin, notification
   en cas d'échec, si `-ConfigurerPlanification` n'a pas pu l'appliquer (identifiants absents).
3. **Rôles** : affecter les groupes Entra / personnes à `Direction`, `PilotageRD`, `Administration`,
   `RelationEcoles`, `Referent` (H-16), une personne dans un seul rôle.
4. **Application et audiences** : publier l'application de l'espace avec les audiences du [\[5.1\]](../spec.md#5-bibliothèques-documentaires) ; lien de
   l'application dans le paramètre `Lien.RapportPowerBI` (synthèses PA-11).

## 8. Actualisation

Mode import, une source (SharePoint REST), sans passerelle. Volume : `$top=5000` par page, pagination illimitée.
Les listes sont relues intégralement à chaque actualisation (pas d'actualisation incrémentielle en V1). Échecs
typiques : identifiants expirés, liste supprimée ou dont le nom interne change (impossible par convention), colonne
supprimée ou renommée (`$select` en erreur 400).

## 9. Réconciliation avec SharePoint (`tests/e2e/reconciliation/`)

Principe : pour chaque mesure clé, recompter les éléments SharePoint avec la même règle, **sans filtre de rapport**,
sous un compte non restreint (rôle PilotageRD), juste après une actualisation. Requête de référence :
`GET {SiteUrl}/_api/web/GetList('{chemin du site}/Lists/{NomInterne}')/items?$select=Id,...&$filter=<filtre>&$top=5000`
(paginer sur `odata.nextLink`, compter les éléments). Les comparaisons de dates se font en **heure de Paris**
(convertir « aujourd'hui » et les dates UTC renvoyées par l'API). Les filtres relatifs à aujourd'hui sont plus simples
à appliquer côté test après lecture (`$select` des colonnes utiles) qu'en OData. Dans les filtres OData, une
apostrophe est doublée (`'Établissement d''accueil'`) et un booléen vaut `1` / `0`.

| Mesure | Liste (nom interne) | Règle SharePoint équivalente (`$filter` OData ou calcul après lecture) | Vue SharePoint proche |
| --- | --- | --- | --- |
| Candidatures reçues | Candidatures | tous les éléments | - |
| Candidatures actives | Candidatures | `Statut ne 'Intégrée' and Statut ne 'Non retenue' and Statut ne 'Clôturée'` | Candidatures en cours |
| Candidatures en attente | Candidatures + Parametres | actives et (aujourd'hui − `DateStatut` ou `DateReception`, en jours calendaires) > `Delai.SeuilAttenteCandidatureJours` (10 si absent ou non numérique) | - |
| Délai moyen de présélection (j) | Candidatures | moyenne des écarts en jours calendaires (Paris) `DateDecisionPreselection − DateReception`, éléments où la décision est renseignée | - |
| Candidatures analysées | Candidatures | `DateDecisionPreselection ne null` | - |
| Candidatures présélectionnées | Candidatures | `DateTransmissionAdmin ne null` | Transmises à l'administration (approx.) |
| Candidatures avec entretien réalisé | Entretiens | nombre de `CandidatureId` distincts parmi `Statut eq 'Réalisé'` | - |
| Entretiens à venir | Entretiens | `Statut eq 'Planifié' and DateHeure ge datetime'<maintenant UTC>'` | Entretiens à venir |
| Candidatures retenues | Candidatures | `Statut eq 'Retenue' or Statut eq 'Formalités en cours' or Statut eq 'Intégrée'` | - |
| Candidatures intégrées | Candidatures | `Statut eq 'Intégrée'` | - |
| Doublons signalés | Candidatures | `DoublonPotentiel eq 1 and DoublonVerifie ne 1` (vide = Non) | Doublons potentiels (sans les clôturées) |
| Alternants actifs | Alternants | `Statut eq 'Actif' or Statut eq 'Fin planifiée'` | Alternants actifs (inclut À intégrer, Suspendu) |
| Alternants accueillis | Alternants | `Statut ne 'À intégrer'` et (`DateFinReelle` vide ou ≥ `DateDebut`) | Historique des alternants |
| Affectations actives | Affectations | `Statut eq 'Active' or Statut eq 'À risque' or Statut eq 'Bloquée'` | Affectations en cours (inclut À préparer) |
| Affectations sans référent | Affectations | `ReferentId eq null` et statut ∈ {À préparer, Active, À risque, Bloquée} | Sans référent |
| Affectations incomplètes | Affectations + Livrables | non terminées et (sans référent, ou sans `DateFin`, ou aucun livrable dont `AffectationId` = l'affectation) | - |
| Taux de charge référent | Affectations + Referents | alternants distincts (`AlternantId`) des affectations actives ÷ somme des `CapaciteIndicative` | - |
| Livrables validés | Livrables | `Statut eq 'Validé' or Statut eq 'Archivé / clôturé'` | Capitalisés (archivés seuls) |
| Livrables en retard | Livrables | statut ∈ {À produire, En cours, Corrections demandées} et `Echeance` < aujourd'hui (Paris) | En retard (`EnRetard`, recalculé par PA-06 à 07:00) |
| Taux de remise à l'heure | Livrables | échus (`Echeance` ≤ aujourd'hui, hors Suspendu / abandonné) avec `DatePremierDepot` (date Paris) ≤ `Echeance` ÷ échus | - |
| Taux de validation au premier passage | Livrables | (validés ou archivés avec `NbCorrections` = 0 ou vide) ÷ (`DatePremierDepot ne null`) | - |
| Taux de capitalisation | Livrables | archivés avec `LienDocument` et, si POC / plan, DoD1-5 = Oui ÷ validés ou archivés | Capitalisés |
| POC réalisés | Livrables | `Statut eq 'Archivé / clôturé' and TypeLivrable eq 'POC / démonstrateur'` et DoD1-5 = Oui | Capitalisés (regroupés par type) |
| Plans de stratégie formalisés | Livrables | idem avec `TypeLivrable eq 'Plan de stratégie'` | Capitalisés |
| Couverture des domaines cibles | DomainesCibles, SujetsRD, Affectations, Livrables | domaines `Cible` = Oui et `Statut` = Actif ayant au moins un sujet (`DomainesId`) qui porte une affectation avec un livrable validé ou archivé ÷ domaines cibles actifs | - |
| Sujets bloqués | SujetsRD | `Statut eq 'Bloqué' or Statut eq 'À arbitrer'` | À arbitrer (inclut Proposé) |
| Sujets actifs | SujetsRD | `Statut eq 'Priorisé' or Statut eq 'En cours' or Statut eq 'Bloqué'` | Portefeuille (approx.) |
| Mobilisations commerciales | Mobilisations | tous les éléments (période : `DateMobilisation`) | - |
| Comptes rendus manquants | ComptesRendus | `Statut eq 'Non remis'` ou (statut ∈ {Attendu, En rédaction} et `Echeance` < aujourd'hui) | Non remis (statut seul) |
| Blocages signalés | ComptesRendus | `BlocageSignale eq 1` | Blocages signalés |
| Partenariats académiques actifs | Conventions | `Statut eq 'Signée / active' and (TypeConvention eq 'Convention de partenariat' or TypeConvention eq 'Sponsoring')` | Conventions en cours (filtrer) |
| Conventions à renouveler | Conventions | `Statut eq 'À renouveler'` | À renouveler |
| Établissements collaborants | Etablissements | `Statut` ∈ {Établissement d'accueil, Partenariat à évaluer, Partenaire actif} | - |
| Partenariats à évaluer | Etablissements | `Statut eq 'Partenariat à évaluer'` | Partenariats à évaluer |
| Bilans réalisés | BilansAlternance | `Statut eq 'Réalisé'` | - |
| Communications publiées | CommunicationsRD | `Statut eq 'Publiée' and Externe eq 1` (période : `DateEffective`) | - |
| Livrables valorisés | CommunicationsRD | nombre de `LivrableSourceId` **distincts non vides** parmi `Statut eq 'Publiée'` | - |
| Actions en retard | ActionsIntegration | statut ∈ {À faire, En cours, Bloquée} et `Echeance` < aujourd'hui | - |
| Transitions refusées | HistoriqueStatuts | `Resultat eq 'Refusée et annulée'` | - |
| Écarts d'échéance GitLab | GitlabSync | `EcartEcheance eq 1 and Orpheline ne 1` (vide = Non ; lignes orphelines exclues) | - |

Contrôles complémentaires par rôle (*Afficher en tant que* ou API `executeQueries` avec `impersonatedUserName`) :
`Administration` ne voit que les candidatures transmises et aucun livrable ; `RelationEcoles` aucune candidature, aucun
livrable ni compte rendu, ni `NomAffichage` ; `Referent` uniquement les alternants de ses affectations et leurs actions
(`[Actions en retard]` recalculé sur ce périmètre) ; `Direction` aucune colonne `NomAffichage` ; pour `Direction`,
`RelationEcoles` et `Referent`, `Parametres` réduit à `Delai.SeuilAttenteCandidatureJours` et `[Transitions refusées]`
vide.

## 10. Divergences et questions pour la spec

### 10.1 Divergences précédentes (D-01 à D-13) : intégrées en v1.1.0

D-01 `DISTINCTCOUNTNOBLANK`, D-02 `[Candidatures avec entretien réalisé]`, D-03 datation propre des communications et
mobilisations, D-04 `CommunicationsRD.Title`, D-05 `[Dernière actualisation]`, D-06 repli du seuil, D-07 UPN (H-47),
D-08 `GetList`, D-09 `DATE ( YEAR, MONTH, DAY )` et H-48, D-10 `NomAffichage` absent des visuels et règle de
non-cumul des rôles, D-11 dénominateur du premier passage, D-12 `GitlabSync` facultative, D-13 tableau GitLab complet.
Le projet n'a plus **aucune** surcharge de mesure ni mesure hors spec.

### 10.2 Points E-01 à E-05 : intégrés en v1.3.0

E-01 section « Technique » de [\[9.5\]](../spec.md#95-mesures), E-02 tableau des communications publiées avec colonne `Externe`, E-03
`LienDocument` visible de la Direction (accepté), E-04 taux de capitalisation (effet voulu), E-05 RLS Administration
sans filtre des actions (documenté). v1.3.0 ajoute `Candidatures.DoublonVerifie` et le filtre correspondant de
`[Doublons signalés]`. v1.6.0 (revue croisée) : RX-03 OLS `NomAffichage` pour RelationEcoles, RX-04 `Parametres` /
`HistoriqueStatuts` restreints, RX-05 actions du référent, RX-07 `GitlabSync.Orpheline`. Aucun point ouvert côté Power BI.

## 11. Limites

- Aucun tenant ni Power BI Desktop n'était disponible à la génération : le projet est validé hors ligne
  (`check_pbip.py`, parseur PowerShell, préparation à blanc du script), pas ouvert dans Desktop. À valider à la
  première ouverture : lecture TMDL (colonnes de tables calculées, OLS, `dataCategory: WebUrl`), schémas PBIR
  (versions 1.0.0 des schémas visuels / pages, `displayName` des projections), rendu des visuels (entonnoir
  multi-mesures, jauges filtrées, segments « entre »), thème de base minimal (`CY24SU10.json`), et, sur le site réel :
  forme de `Compte/EMail` après `$expand`, format de `DomainesId`, `GetList` et `$skiptoken`, conversion des dates.
- Pas d'actualisation incrémentielle ; pas de passerelle (source cloud).
- `[Couverture des domaines cibles]` ignore les filtres du rapport (indicateur global, conforme à la spec).
- `TODAY ()` / `NOW ()` en UTC dans le service (écart toléré 00:00-02:00, H-48).
- Les identifiants OAuth, la planification (si non appliquée par le script) et les membres des rôles restent manuels.
