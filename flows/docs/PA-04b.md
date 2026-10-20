# PA-04b : Activation des alternants et rappels d'actions

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec ([\[8.4\]](../../spec.md#84-contrats-détaillés)) : ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 2 |
| Type (spec) | Planifié (quotidien 06:30) |
| Définitions techniques | `PA-04b` |
| Activé par défaut | Oui |

## Objectif

Activer les alternants à leur date de début et rappeler les actions de checklist à échéance.

## Déclencheur(s)

- `PA-04b` : Récurrence : Quotidien 06:30 (heure de Paris).

## Entrées

- `PA-04b` : Alternants « À intégrer » ; actions non terminées ; `Delai.RappelActionJours`.

## Traitement pas à pas

1. Alternants « À intégrer » dont `DateDebut` ≤ aujourd'hui (heure de Paris) → « Actif » (ALT-T02, FLUX, `G_DATE_DEBUT_ATTEINTE`), N-18 au référent principal.
2. Actions (tous contextes) non terminées dont l'échéance est dans `Delai.RappelActionJours` jours ou dépassée → N-19 au responsable (à défaut, résolution [\[8.1\]](../../spec.md#81-socle-commun-sapplique-à-tous-les-flux) du rôle responsable : ADMIN, RD et DIRECTION_RD → destinataires paramétrés, PROPRIETAIRE → `Destinataires.Support`, ECOLES → G_ECO), au plus une fois par jour (`DernierRappel` = `Rappel:AAAA-MM-JJ`).

## Sorties

- `PA-04b` : Statuts « Actif », rappels.

## Transitions

| Code | De | Vers | Acteurs | Contrôles |
| --- | --- | --- | --- | --- |
| ALT-T02-01 | À intégrer | Actif | FLUX, RD, ADMIN | G_DATE_DEBUT_ATTEINTE |
| ALT-T02-02 | Suspendu | Actif | FLUX, RD, ADMIN | G_DATE_DEBUT_ATTEINTE |

Statuts écrits par le compte de service (rôle `FLUX`, jamais une décision humaine) :

- `Alternants` : « Actif »

## Notifications

| Code | Destinataires | Canal | Objet | Modèle |
| --- | --- | --- | --- | --- |
| N-18 | Référent principal | Mail+Teams | {IdAlternant} démarre aujourd'hui | `flows/templates/N-18.html` |
| N-19 | Responsable de l'action | Mail+Teams | Action {IdHNCS} à échéance le {date} | `flows/templates/N-19.html` |

## Contrôles

- `G_DATE_DEBUT_ATTEINTE` : DateDebut ≤ aujourd'hui (non exigé pour la reprise depuis « Suspendu »)

## Erreurs et reprise

- `PA-04b` : Socle (PA-00C) ; rattrapage le lendemain.

## Décision humaine préservée

Le passage à « Actif » est un constat de date, pas une décision.

## Points de test

- Alternant dont la date de début est aujourd'hui → « Actif » et N-18.
- Action échue → un rappel par jour au plus.

## Données lues et écrites

- `PA-04b` : lit `ActionsIntegration`, `Alternants`, `Parametres`, `Referents` ; écrit `ActionsIntegration`, `Alternants` ; flux enfants PA-00A, PA-00B, PA-00C.
