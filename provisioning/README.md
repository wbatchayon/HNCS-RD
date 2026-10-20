# Provisionnement SharePoint HNCS-RD

Scripts PowerShell qui déploient le socle SharePoint du système de suivi R&D (spec [11](../spec.md#11-découpage-en-lots-0-à-5), lot 1 et suivants)
à partir du **modèle machine** `provisioning/model/model.generated.json`, généré depuis `spec.md` par
`python tools/spec_extract.py`. Aucune liste, colonne, vue, groupe ou permission n'est écrit en dur dans
les scripts : pour changer un comportement, on modifie la spec, on régénère le modèle, puis on rejoue le
déploiement.

## Contenu

| Fichier | Rôle |
| --- | --- |
| `Deploy-HNCSRD.ps1` | Point d'entrée idempotent : site, niveau d'autorisation, groupes, listes, colonnes, lookups, validations, vues, permissions, référentiels, transitions, navigation, Teams (optionnel) |
| `Set-HNCSRDMembres.ps1` | Membres **directs** des groupes SharePoint depuis `config/membres.json` (H-14) ; `-Synchroniser` retire les absents |
| `Grant-HNCSRDServiceAccount.ps1` | Contrôle du compte de service (membre de G_PROP, permissions effectives) ; `-Corriger` l'ajoute à G_PROP |
| `Test-HNCSRDDeploiement.ps1` | Contrôle post-déploiement **en lecture seule** : rapport d'écarts site ↔ modèle, code 1 si écart |
| `modules/HNCSRD.Provisioning.psd1/.psm1` | Fonctions réutilisables (`Ensure-*`, `Set-*`, `Sync-*`, fonctions pures) |
| `config/tenant.sample.json`, `config/membres.sample.json` | Contrats de configuration partagés avec les autres lots |
| `tests/*.Tests.ps1` | Tests hors ligne des fonctions pures (CAML de toutes les vues, XML de toutes les colonnes…) |
| `logs/` | Journaux d'exécution (ignorés par git) |

## Prérequis

1. **PowerShell 7.4+** (`pwsh`) et **PnP.PowerShell 2.12+** (ou 3.x) :
   `Install-Module PnP.PowerShell -Scope CurrentUser`.
2. **Application Entra** pour PnP (obligatoire depuis septembre 2024, l'application multi-tenant PnP n'existe plus) :
   `Register-PnPEntraIDAppForInteractiveLogin -ApplicationName "HNCS-RD Provisioning" -Tenant contoso.onmicrosoft.com`,
   puis reporter son identifiant dans `PnPClientId`. Permissions déléguées SharePoint `AllSites.FullControl`
   (et, pour l'étape Teams, Microsoft Graph `Group.ReadWrite.All`, `Channel.Create`, `TeamsTab.Create`).
   Mode automatisation : certificat de l'application (`CertificatePath` + mot de passe dans la variable
   d'environnement `HNCSRD_CERT_PASSWORD`, ou `CertificateThumbprint` du magasin Windows) et permissions
   **d'application** équivalentes ; le domaine `<TenantName>.onmicrosoft.com` est passé en `-Tenant`.
3. **Droits** : administrateur SharePoint (création du site via `TenantAdminUrl`) et **administrateur de
   collection de sites** du site HNCS-RD pour les autres étapes. Le compte qui exécute le script doit être
   `SiteOwner` ou administrateur de collection : la rupture d'héritage retire ensuite toute attribution
   directe non prévue (dont celle ajoutée automatiquement au compte exécutant).
4. Configuration : copier `config/tenant.sample.json` en `config/tenant.json` et `config/membres.sample.json`
   en `config/membres.json` (fichiers ignorés par git), puis les compléter.

## Commandes

```powershell
# Simulation complète du lot 1 (aucune écriture ; chaque modification prévue est journalisée « Simule »)
pwsh ./provisioning/Deploy-HNCSRD.ps1 -Lot 1 -WhatIf

# Déploiement du lot 1, puis ajout des membres et contrôle du compte de service
pwsh ./provisioning/Deploy-HNCSRD.ps1 -Lot 1
pwsh ./provisioning/Set-HNCSRDMembres.ps1
pwsh ./provisioning/Grant-HNCSRDServiceAccount.ps1 -Lot 1

# Contrôle post-déploiement (lecture seule), rapport JSON facultatif
pwsh ./provisioning/Test-HNCSRDDeploiement.ps1 -Lot 1 -RapportPath ./provisioning/logs/ecarts.json

# Passage au lot 3 (cumulatif : objets et colonnes de lot <= 3)
pwsh ./provisioning/Deploy-HNCSRD.ps1 -Lot 3

# Rejouer seulement certaines étapes (toujours exécutées dans l'ordre canonique)
pwsh ./provisioning/Deploy-HNCSRD.ps1 -Lot 1 -Etapes Vues, Permissions

# Synchroniser les membres (retire les absents du fichier) : contrôler d'abord avec -WhatIf
pwsh ./provisioning/Set-HNCSRDMembres.ps1 -Synchroniser -WhatIf
```

Code de sortie : 0 si aucune erreur, 1 sinon. Chaque exécution écrit `logs/deploy-<horodatage>.log` (resp.
`membres-`, `compte-service-`, `test-`) et un résumé par étape (créé / mis à jour / inchangé / retiré /
simulé / avertissements / erreurs).

## Étapes et correspondance avec la spec

| Étape | Spec | Ce qui est fait |
| --- | --- | --- |
| `Site` | [2.2](../spec.md#22-conventions-de-nommage) | Site d'équipe sans groupe M365 (`STS#3`), LCID 1036, fuseau Paris (ID SharePoint 3), titre du modèle ; s'il existe, rien n'est modifié (écart signalé) ; site en corbeille = erreur |
| `NiveauxAutorisation` | [7.2](../spec.md#72-niveaux-dautorisation) | « HNCS - Contribution sans suppression » = Contributor − `DeleteListItems` − `DeleteVersions` (créé ou corrigé) ; FC et R résolus par `RoleTypeKind` |
| `Groupes` | [7.1](../spec.md#71-groupes-sharepoint) | 8 groupes (noms exacts), propriétaire G_PROP, sans membres |
| `Listes` | [2.2](../spec.md#22-conventions-de-nommage), [4](../spec.md#4-modèle-de-données--listes-sharepoint), [5](../spec.md#5-bibliothèques-documentaires) | Listes sous `/Lists/<NomInterne>`, bibliothèques sous `/<NomInterne>`, titre affiché du modèle ; versioning : listes majeures 50, bibliothèques selon `versioning` |
| `Colonnes` | [2.3](../spec.md#23-colonnes-implicites-ajoutées-par-lextracteur), [2.4](../spec.md#24-conventions-de-lecture-des-tableaux-de-colonnes), [4](../spec.md#4-modèle-de-données--listes-sharepoint), [5](../spec.md#5-bibliothèques-documentaires) | Title des listes renommé / obligatoire / indexé / unique (Titre des documents jamais modifié) ; `IdHNCS` indexé sans unicité ; `hidden` = masquée des formulaires ; colonnes créées par XML (`Name` = `StaticName` = nom interne, `DisplayName` = nom interne puis libellé) ; choix ordonnés, défauts, obligatoire, index, unicité, min/max/décimales, Date = DateOnly, personne = PeopleOnly, URL = Hyperlink, Note brute (`appendonly` → `AppendOnly="TRUE"`) |
| `Lookups` | [2.2](../spec.md#22-conventions-de-nommage) | 2e passe : `ShowField="IdHNCS"`, `LookupMulti` avec `Mult="TRUE"`, auto-références (`Affectations.AffectationRemplacee`, `Livrables.LivrableOrigine`) |
| `Validation` | [2.4](../spec.md#24-conventions-de-lecture-des-tableaux-de-colonnes) | `ValidationFormula` / `ValidationMessage` après toutes les colonnes (noms internes traduits en noms affichés) |
| `Vues` | `specs/sharepoint-vues.md` | CAML généré (`ConvertTo-HNCSRDCaml`), 30 éléments par page, vue par défaut, regroupements dépliés ; listes : `LinkTitle` (en tête si la vue ne cite pas `Title`) ; bibliothèques : `DocIcon` et `LinkFilename` en tête ; mise à jour de la vue de même nom |
| `Permissions` | [7.2](../spec.md#72-niveaux-dautorisation), [7.3](../spec.md#73-matrice-daccès) | Héritage rompu sans copie (une seule fois, sous-éléments préservés) ; attributions = matrice (`FC`, `CSS`, `R` ; `R+IL(x)` → `R` ; `-` et `IL(x)` → rien) ; site : G_PROP FC, autres R ; attributions non prévues retirées et journalisées ; « Accès limité » jamais retiré ; groupes par défaut du site vidés et sans attribution (jamais supprimés) ; listes système laissées en héritage |
| `Referentiels` | `specs/referentiels-initiaux.md` | Paramètres (marqueurs `<BoiteRD>`… remplacés depuis `Parametres` de la config) et seeds (pôles, domaines avec résolution `POL-Px`, modèles d'actions, registre des modèles avec `Proprietaire` = `<EmailDirectionRD>`) ; identifiants réservés (recherche par `Title` ou `Code`, `IdHNCS` vide complété, erreur si l'identifiant est déjà porté) ; éléments injectés : `StatutPrecedent` = `Statut`, `DateStatut` = date du déploiement ; **jamais d'écrasement** d'une valeur non vide (clé Title, IdHNCS ou Code), valeur de paramètre vide complétée depuis la configuration |
| `Transitions` | [6](../spec.md#6-statuts-et-transitions-autorisées), [11](../spec.md#11-découpage-en-lots-0-à-5) | `TransitionsStatuts` synchronisée **en entier** quel que soit le lot (clé = code) : ajout, mise à jour, `Actif` = Non pour les codes disparus, jamais de suppression |
| `Navigation` | [4.2](../spec.md#42-domaines-et-lots) | Navigation rapide : A. Recrutement, B. Gestion des alternants, C. Production R&D, D. Écoles et partenariats, Bibliothèques, Technique |
| `Teams` | [2.2](../spec.md#22-conventions-de-nommage), H-44 | Si `Teams.Creer` = true : équipe distincte (canaux Général, Comité R&D, Alternants), onglet site web vers le site ; ce n'est pas le référentiel |

`-Lot 0` (cadrage) contrôle uniquement le modèle et la configuration.

## Idempotence et rejeu

- Toutes les étapes comparent l'existant au modèle et n'écrivent que les écarts ; un second passage
  donne uniquement des « inchangé ».
- Une colonne dont le **type** ou la **liste cible** diffère du modèle n'est jamais modifiée : erreur
  signalée (suppression / recréation manuelle après sauvegarde, la spec interdisant de renommer un nom interne).
- Les paramètres et référentiels existants ne sont jamais écrasés (une valeur modifiée par la Direction R&D
  est conservée) ; une valeur de paramètre **vide** est complétée dès que la configuration la fournit
  (ex. `Lien.RapportPowerBI` après le lot 4) ; un marqueur `<…>` resté non résolu est signalé par
  `Test-HNCSRDDeploiement.ps1`, qui contrôle aussi l'absence de doublons d'`IdHNCS` non vides et que les
  groupes par défaut du site sont vides.
- En cas d'échec, corriger la cause et relancer la même commande : chaque objet est traité indépendamment.

## Référentiels initiaux : identifiants réservés

Les éléments des référentiels initiaux portent des `IdHNCS` **réservés** fixés par la spec ([2.2](../spec.md#22-conventions-de-nommage) :
plage `0001` à `0099` de 2026, `POL-Px` pour les pôles). L'étape `Referentiels` recherche l'existant par
`Title` (par `Code` pour `ModelesActions` ; par clé `Title` pour `Parametres`), complète un `IdHNCS` vide
avec l'identifiant réservé, ne modifie aucun autre champ, et signale une **erreur** si l'identifiant réservé
est déjà porté par un autre élément ou si l'élément trouvé porte un autre identifiant (correction manuelle).

## Changement de type d'une colonne (site déjà déployé)

Le script ne change jamais le type d'une colonne existante (erreur « Type : attendu … constaté … »). La
spec v1.6.0 (RX-01) fait passer de `Text` à `Note` (texte brut) trois empreintes techniques :
`Livrables.EmpreinteRevue`, `Livrables.EmpreinteCommentaire` et `ComptesRendus.EmpreinteRevue`. Sur un
déploiement neuf, rien à faire. Sur un site déjà déployé :

1. Désactiver les flux PA-07 et PA-08 (et PA-00D) pendant l'opération.
2. Supprimer les trois colonnes (paramètres de la liste ou
   `Remove-PnPField -List Lists/Livrables -Identity EmpreinteRevue -Force`, idem pour
   `EmpreinteCommentaire` et pour `Lists/ComptesRendus` / `EmpreinteRevue`). Leur contenu est purement
   technique : aucune donnée métier n'est perdue.
3. Rejouer `pwsh ./provisioning/Deploy-HNCSRD.ps1 -Lot <n> -Etapes Colonnes` : les colonnes sont recréées
   avec le même nom interne, en type `Note`, masquées des formulaires.
4. Réactiver les flux : PA-00D réinitialise les empreintes vides à partir des valeurs courantes ([6.5](../spec.md#65-formats-des-empreintes-p-09),
   « empreinte vide = non encore initialisée »).
5. Contrôler avec `Test-HNCSRDDeploiement.ps1`.

## Réutilisation par les autres scripts

```powershell
Import-Module ./provisioning/modules/HNCSRD.Provisioning.psd1 -DisableNameChecking
$modele = Get-HNCSRDModel           # modèle généré (compatible Windows PowerShell 5.1)
$config = Get-HNCSRDConfig          # config/tenant.json
Connect-HNCSRD -Config $config      # interactif ou certificat selon la config
Resolve-HNCSRDLookupId -List Poles -IdHNCS POL-P2
Get-HNCSRDListUrl -Name Candidatures   # « Lists/Candidatures »
```

`-DisableNameChecking` évite l'avertissement sur le verbe non approuvé `Ensure`.

## Tests hors ligne

```powershell
powershell -NoProfile -File provisioning/tests/ConvertTo-HNCSRDCaml.Tests.ps1      # CAML de toutes les vues
powershell -NoProfile -File provisioning/tests/HNCSRD.Provisioning.Pure.Tests.ps1  # colonnes, matrice, formules…
Invoke-Pester provisioning/tests                                                     # Pester 3.4 ou 5
```

Les scripts sont enregistrés en UTF-8 avec BOM et CRLF (lecture correcte des accents par Windows PowerShell 5.1)
et restent analysables par le parseur 5.1.

## Limites connues

- Non exécuté contre un tenant au moment de la livraison : voir la section « à tester » du rapport.
- Les listes et bibliothèques système du modèle STS#3 (« Documents », « Pages du site »…) héritent du site
  et ne doivent contenir aucune donnée métier ([7.2](../spec.md#72-niveaux-dautorisation)) ; les groupes par défaut du site sont vidés et privés
  de toute attribution, jamais supprimés.
- La vue « Tous les éléments » créée avec chaque liste est conservée (la vue par défaut devient celle du modèle).
- Les politiques de versions au niveau du tenant ou du site (limites automatiques) peuvent prévaloir sur les
  limites de versions définies par liste.
- La vérification « Envoyer en tant que » sur la boîte R&D et la licence du compte de service ne sont pas
  contrôlables par PnP (rappel affiché par `Grant-HNCSRDServiceAccount.ps1`).
