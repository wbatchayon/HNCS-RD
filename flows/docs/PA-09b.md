# PA-09b — Détection des fins d'alternance

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec (§ 8.4) — ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 3 |
| Type (spec) | Planifié (quotidien 06:50) |
| Définitions techniques | `PA-09b` |
| Activé par défaut | Oui |

## Objectif

Détecter les fins d'alternance proches et préparer la clôture.

## Déclencheur(s)

- `PA-09b` : Récurrence — Quotidien 06:50 (heure de Paris).

## Entrées

- `PA-09b` : Alternants « Actif » ; `Fin.AnticipationJours`.

## Traitement pas à pas

1. `DateFin` ≤ aujourd'hui + `Fin.AnticipationJours` → « Fin planifiée » (ALT-T04, FLUX).
2. Effets du statut cible (§ 6.1-8) : checklist « Clôture d'alternance » (idempotente), bilan « À réaliser » s'il n'existe pas (référent CSS), N-35 au référent, à G_RD et au responsable HNCS de l'école.

## Sorties

- `PA-09b` : Statuts, checklists, bilans, N-35.

## Transitions

| Code | De | Vers | Acteurs | Contrôles |
| --- | --- | --- | --- | --- |
| ALT-T04 | Actif | Fin planifiée | FLUX, RD | — |

Statuts écrits par le compte de service (rôle `FLUX`, jamais une décision humaine) :

- `ActionsIntegration` : « À faire »
- `Alternants` : « Fin planifiée »
- `BilansAlternance` : « À réaliser »

## Notifications

| Code | Destinataires | Canal | Objet | Modèle |
| --- | --- | --- | --- | --- |
| N-35 | Référent principal, G_RD, responsable HNCS de l'école | Mail | Fin d'alternance planifiée : {IdAlternant} | `flows/templates/N-35.html` |

## Contrôles

Aucun contrôle `G_*`.

## Erreurs et reprise

- `PA-09b` : Socle (PA-00C) ; rattrapage le lendemain.

## Décision humaine préservée

« Fin planifiée » est un constat de date ; « Terminé » reste humain.

## Points de test

- Alternant à J-30 → « Fin planifiée », checklist et bilan créés une seule fois.

## Données lues et écrites

- `PA-09b` : lit `ActionsIntegration`, `Alternants`, `BilansAlternance`, `Etablissements`, `ModelesActions`, `Parametres`, `Referents` ; écrit `ActionsIntegration`, `Alternants`, `BilansAlternance` ; flux enfants PA-00A, PA-00B, PA-00C.
