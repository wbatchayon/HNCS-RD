# Jeu de test HNCS-RD (données fictives)

Jeu de données **100 % fictif** (le dépôt est public, H-30) pour la recette du système de suivi R&D : noms inventés,
e-mails des candidats et contacts en `@example.org`, comptes internes désignés uniquement par des **clés de persona**.
Il est aligné sur la spec **v1.7.0** et vérifié hors ligne par `tests/offline/test_testdata.py`.

## Contenu

| Fichier | Rôle |
| --- | --- |
| `data/<NomInterneListe>.json` | Un tableau d'éléments par liste, colonnes désignées par leur **nom interne** |
| `personas.sample.json` | Modèle des personas de recette (clé → `upn`, `groupes`, `description`, `compteService`) |
| `personas.json` | Vraies adresses des comptes de recette : **ignoré par git**, à créer à partir du modèle |
| `Import-TestData.ps1` | Chargement idempotent dans un site de recette, réinitialisation, export des membres |

Les référentiels livrés par le provisionnement (`Poles`, `DomainesCibles`, `ModelesActions`, `RegistreModeles`,
`Parametres`, `TransitionsStatuts`, cf. `specs/referentiels-initiaux.md`) ne sont **pas** dupliqués : le jeu y renvoie
par leurs `IdHNCS` / `Code`. Il ajoute seulement trois modèles (`MOD-2026-9001` « Approuvé », `9002` « En validation »,
`9003` « Obsolète ») et un domaine cible inactif (`DOM-2026-9001`) pour couvrir tous les statuts.

## Conventions de valeurs

| Type de colonne | Valeur dans le JSON | Résolution à l'import |
| --- | --- | --- |
| Lookup / LookupMulti | `IdHNCS` de la cible (chaîne / tableau) | ID SharePoint de l'élément cible (jeu ou référentiel) |
| User / UserMulti | `"@persona:CLE"` (chaîne / tableau) | UPN de la persona dans `personas.json` |
| Text contenant une adresse | `"@persona:CLE"` (ex. `EmailPro`, `ActeurEmail`) | UPN |
| Date | `"@J"`, `"@J+7"`, `"@J-30"` ou `AAAA-MM-JJ` | jour d'import (ou `-DateReference`) ± n jours |
| DateTime | `"@J-30T09:00"` ou ISO 8601 | idem, à l'heure indiquée (heure locale du poste) |
| URL | `"@site:/chemin"` ou `https://…example.org/…` | URL du site + chemin ; description = dernier segment |
| Number `ItemId`, Text `EmpreinteReferent` | `"@id:IDHNCS"` | ID SharePoint de l'élément |
| `Affectations.EmpreinteVerrou` | `"@empreinte"` | `{"AlternantId":<id>,"SujetId":<id>,"ReferentId":<id>,"DateDebut":"AAAA-MM-JJ"}` |
| `ActionsIntegration.EmpreinteAction` | `"@empreinte"` | `{"Bloquante":true,"Statut":"Terminée"}` |
| Boolean, Number, Choice | valeur JSON native ; MultiChoice = tableau | inchangée |

Règles :

- `IdHNCS` explicites au format `{PREFIXE}-{AAAA}-{NNNN}`, numéros **9xxx** pour ne pas entrer en collision avec les
  identifiants attribués par PA-00D sur un site de recette ; uniques (la colonne n'a plus de contrainte d'unicité
  SharePoint depuis la v1.2.0 : c'est `tests/offline` qui le vérifie).
- `StatutPrecedent` n'est jamais renseigné : l'import le pose **égal à** `Statut` (données « déjà validées »).
- Les colonnes `flux` sont renseignées comme si les flux étaient passés (dates de transmission, empreintes…).
- Les empreintes calculées suivent les formats de la spec ([6.5](../spec.md#65-formats-des-empreintes-p-09)).
  `Livrables.EmpreinteRevue` et `ComptesRendus.EmpreinteRevue` sont laissées **vides** : une empreinte vide signifie
  « non encore initialisée » et PA-00D l'initialise à partir des valeurs courantes, sans rien rétablir (H-55).
- Chaque élément d'un objet à statut contrôlé possède un historique complet : son `Statut` est le dernier
  `StatutApres` accepté de `HistoriqueStatuts`, statut de référence des flux ([8.1](../spec.md#81-socle-commun-sapplique-à-tous-les-flux)).
  Les chaînes non scénarisées sont des parcours valides du graphe des transitions, attribués aux personas habilitées.
- Listes sans `IdHNCS` : clé d'idempotence `FluxRunId` (`HistoriqueStatuts`), `RunUrl` (`JournalFlux`),
  `CleSynchro` (`GitlabSync`).

## Couverture

Tous les statuts de toutes les énumérations de statut des listes présentes (référentiels compris pour
`RegistreModeles` et `DomainesCibles`), ainsi que les cas limites demandés par la recette :

| Domaine | Cas couverts (identifiants) |
| --- | --- |
| Candidatures (25) | 13 statuts ; canaux Site HNCS (9001), LinkedIn (9002), France Travail (9003), spontanée (9004), boîte mail « À qualifier » (9005), école (9025) ; doublon signalé (9006 → 9002) et doublon **vérifié** (9025 → 9003) ; courriel de plateforme sans identité (9023, S-11) ; présélectionnée bloquée par une erreur de partage (9007) ; non retenue après analyse (9016), après entretien (9017), par l'administration sans entretien (9024, CAND-T17) ; clôturée par désistement (9018) ; retenue (9012) ; formalités incomplètes (9013, **ne doit pas** pouvoir passer « Intégrée ») ; 6 intégrées avec toutes les actions bloquantes terminées avec preuve (une « Non applicable » justifiée) |
| Alternants (8) | 6 statuts ; deux reprises de l'existant sans candidature (9005, 9008) ; `ReferentPrincipal` = référent de l'affectation active la plus récente ; ancien alternant aux accès retirés (persona `ALT_ANCIEN`) |
| Écoles / conventions | 6 statuts d'établissement ; ECO-2026-9001 reliée à 4 alternants sans doublon ; 8 statuts de convention ; partenariat signé avec décision (CONV-2026-9003) ; décision « À examiner » (9004, S-19) |
| Affectations (11) | 6 statuts ; ALT-2026-9003 change de sujet (AFF-9003 → 9004) puis de référent (9004 → 9005), anciennes terminées avec `AffectationRemplacee` et `MotifFin` ; sans référent (9011) |
| Livrables (16) | 8 statuts ; POC archivé avec DoD complète (9001) ; corrigé puis validé, `NbCorrections` = 1 (9002) ; en retard (9003, 9004, 9014) ; suspendu (9008) ; échéance déplacée (9014) ; repris via `LivrableOrigine` après remplacement d'affectation (9015 → 9016) |
| Comptes rendus (9) | 6 statuts ; blocage signalé (9003) ; échu encore « Attendu » pour PA-08b (9009) |
| Historique | chaînes complètes cohérentes avec les transitions du modèle (candidature, livrable, affectation, alternant, convention, compte rendu, communication, sujet), entretiens, changement de référent principal, 5 refus (transition inexistante, `G_INTEGRATION`, `G_IDENTITE`, rôle sur livrable et sur sujet) |
| Journal des flux | 3 niveaux, 4 statuts de reprise, une erreur « À reprendre » (PA-02 sur CAND-2026-9007) |

Les valeurs attendues des mesures Power BI sur ce jeu sont figées dans `tests/offline/test_reconciliation.py`
(recalcul : `python tests/e2e/reconciliation/reconcilier.py --source testdata/data`).

## Personas

| Clé | Groupes | Rôle dans le jeu |
| --- | --- | --- |
| `IT` | G_PROP | Administration de la plateforme, exécution des imports |
| `SVC` | G_PROP | Compte de service (rôle FLUX), acteur des transitions automatiques |
| `DIR_RD` | G_DRD | Direction R&D : réouverture, arbitrages, décisions de partenariat |
| `RD1`, `RD2` | G_RD | Analyse des candidatures, affectations ; `RD2` est l'ancien référent REF-2026-9003 |
| `ADMIN_CARINE` | G_ADM | Administration (exemple : Carine) : entretiens, décisions, formalités |
| `REF1`, `REF2` | G_REF | Référents REF-2026-9001 et REF-2026-9002 |
| `ALT1` … `ALT5` | G_ALT | Alternants ALT-2026-9001, 9002, 9003, 9006, 9007 |
| `ALT_FIN` | G_ALT | Alternant terminé ALT-2026-9005 (accès non encore retirés) |
| `ALT_ANCIEN` | aucun | Alternant clôturé ALT-2026-9008 (accès retirés) |
| `DIRECTION` | G_DIR | Direction Générale |
| `ECOLES` | G_ECO | Relation écoles |

## Import dans un site de recette

Prérequis : PowerShell 7.4, PnP.PowerShell 2.x, site provisionné (`provisioning/Deploy-HNCSRD.ps1`), compte membre de
`HNCS-RD-Proprietaires`. **Désactiver les flux** pendant l'import, ou l'exécuter sous le compte de service : ses
écritures ne déclenchent aucun flux (spec [8.1](../spec.md#81-socle-commun-sapplique-à-tous-les-flux)). Le script refuse une URL sans marqueur de recette (`recette`, `test`,
`qualif`, `dev`), sauf `-Force`.

```powershell
# 1. Personas : copier le modèle et y mettre les UPN des comptes de recette
Copy-Item ./testdata/personas.sample.json ./testdata/personas.json
# 2. Fichier des membres des groupes, puis ajout des membres (provisionnement)
pwsh ./testdata/Import-TestData.ps1 -ExporterMembres ./provisioning/config/membres.json
pwsh ./provisioning/Set-HNCSRDMembres.ps1 -ConfigPath ./provisioning/config/tenant.json -MembresPath ./provisioning/config/membres.json
# 3. Import (simulation, puis réel) avec émulation des permissions par élément de [7.4](../spec.md#74-permissions-au-niveau-élément-ou-dossier-posées-par-les-flux)
pwsh ./testdata/Import-TestData.ps1 -ConfigPath ./provisioning/config/tenant.json -SiteUrl https://contoso.sharepoint.com/sites/HNCS-RD-Recette -WhatIf
pwsh ./testdata/Import-TestData.ps1 -ConfigPath ./provisioning/config/tenant.json -SiteUrl https://contoso.sharepoint.com/sites/HNCS-RD-Recette -PermissionsElement
# 4. Réinitialisation : supprime (corbeille) UNIQUEMENT les éléments dont la clé figure dans le jeu
pwsh ./testdata/Import-TestData.ps1 -ConfigPath ./provisioning/config/tenant.json -SiteUrl https://contoso.sharepoint.com/sites/HNCS-RD-Recette -Reset
```

Paramètres utiles : `-Lot <1-5>` (n'importe que les listes de lot ≤ n ; les listes absentes du site sont ignorées
avec un avertissement), `-Listes Candidatures,Entretiens` (sous-ensemble), `-DateReference 2026-10-15` (rejouer un
jeu daté), `-PartageTransmission Destinataire` (H-45), `-ClientId` (sans fichier de configuration).

Comportement :

1. ordre d'import **topologique** calculé depuis les lookups du modèle (et les jetons `@id:`), les lookups vers la
   même liste (`AffectationRemplacee`, `LivrableOrigine`) étant posés en seconde passe ;
2. chaque élément est retrouvé par sa clé puis **mis à jour**, sinon créé : un second import ne crée aucun doublon ;
3. `-PermissionsElement` reproduit les attributions par élément de [7.4](../spec.md#74-permissions-au-niveau-élément-ou-dossier-posées-par-les-flux) (candidatures transmises, affectations,
   livrables, comptes rendus, communications, fiches alternants, actions, bilans, modèles, entretiens) ; les
   permissions de **dossiers** restent du ressort des flux ou de la procédure manuelle du lot 1
   (`docs/exploitation.md`) ;
4. bilan par liste (créés, mis à jour, supprimés, erreurs) ; code d'erreur si un élément a échoué.

Limites : les éléments créés **par les flux** pendant la recette (historique, actions générées, comptes rendus…)
ne sont pas supprimés par `-Reset` ; les dates relatives sont recalculées à chaque import (un réimport « rajeunit »
le jeu) ; les heures sont interprétées dans le fuseau du poste qui exécute l'import (exécuter en heure de Paris).

## Contrôles hors ligne

```powershell
python -m unittest discover -s tests/offline -v
```

`test_testdata.py` vérifie notamment : correspondance fichiers ↔ listes du modèle, colonnes existantes, valeurs
d'énumération, lookups résolus (jeu ou référentiels), formats et unicité des identifiants, champs obligatoires,
règles de validation de liste (évaluateur des formules SharePoint de la spec), couverture des statuts, contrôles
`G_*` sur tous les chemins menant au statut courant, P-02 (`G_INTEGRATION`), P-03 (chaîne de remplacement, dates
sans chevauchement), P-09 (empreintes, référent principal dérivé, valideur légitime), cohérence de l'historique avec
les transitions et les rôles des personas, absence de donnée réelle (domaines `example.org`).
