# PA-10b — Échéances des conventions et des écoles

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec (§ 8.4) — ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 3 |
| Type (spec) | Planifié (quotidien 07:10) |
| Définitions techniques | `PA-10b` |
| Activé par défaut | Oui |

## Objectif

Suivre les échéances des conventions et les prochaines actions des écoles.

## Déclencheur(s)

- `PA-10b` : Récurrence — Quotidien 07:10 (heure de Paris).

## Entrées

- `PA-10b` : Conventions « Signée / active » / « À renouveler » ; établissements avec prochaine action ; `Convention.AlerteExpirationJours`.

## Traitement pas à pas

1. `DateFin` dépassée → « Expirée » (CONV-T05, FLUX, `G_DATE_FIN_DEPASSEE`) + N-40.
2. `DateFin` dans `Convention.AlerteExpirationJours` → « À renouveler » (CONV-T04, FLUX) + N-40.
3. Établissements dont `DateProchaineAction` est atteinte → N-41 au responsable HNCS (chaque jour tant que l'échéance n'est pas mise à jour).

## Sorties

- `PA-10b` : Statuts de conventions, rappels.

## Transitions

| Code | De | Vers | Acteurs | Contrôles |
| --- | --- | --- | --- | --- |
| CONV-T04 | Signée / active | À renouveler | FLUX, ADMIN, ECOLES | — |
| CONV-T05-01 | Signée / active | Expirée | FLUX, ADMIN, ECOLES | G_DATE_FIN_DEPASSEE |
| CONV-T05-02 | À renouveler | Expirée | FLUX, ADMIN, ECOLES | G_DATE_FIN_DEPASSEE |

Statuts écrits par le compte de service (rôle `FLUX`, jamais une décision humaine) :

- `Conventions` : « Expirée », « À renouveler »

## Notifications

| Code | Destinataires | Canal | Objet | Modèle |
| --- | --- | --- | --- | --- |
| N-40 | Responsable de la convention, G_ECO | Mail | Convention {IdHNCS} {statut} | `flows/templates/N-40.html` |
| N-41 | Responsable HNCS de l'établissement | Mail+Teams | Prochaine action école : {IdHNCS} | `flows/templates/N-41.html` |

## Contrôles

- `G_DATE_FIN_DEPASSEE` : DateFin < aujourd'hui (non exigé pour une action humaine)

## Erreurs et reprise

- `PA-10b` : Socle (PA-00C).

## Décision humaine préservée

Constats de date uniquement.

## Points de test

- Convention échue hier → « Expirée » et N-40.
- Convention à J-30 → « À renouveler ».

## Données lues et écrites

- `PA-10b` : lit `Conventions`, `Etablissements`, `Parametres` ; écrit `Conventions` ; flux enfants PA-00A, PA-00B, PA-00C.
