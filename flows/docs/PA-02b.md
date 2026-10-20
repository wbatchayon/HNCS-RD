# PA-02b : Relance des candidatures sans traitement

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec ([\[8.4\]](../../spec.md#84-contrats-détaillés)) : ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 2 |
| Type (spec) | Planifié (quotidien 08:00) |
| Définitions techniques | `PA-02b` |
| Activé par défaut | Oui |

## Objectif

Relancer les candidatures restées sans traitement au-delà du délai paramétré.

## Déclencheur(s)

- `PA-02b` : Récurrence : Quotidien 08:00 (heure de Paris).

## Entrées

- `PA-02b` : Candidatures « Reçue », « À analyser », « En cours d'analyse » ; `Delai.RelanceAnalyseJours`.

## Traitement pas à pas

1. Sélection des candidatures dont `DateStatut` (ou à défaut `DateReception`) est antérieure à maintenant − délai.
2. N-09 au responsable d'analyse, sinon aux membres de G_RD, avec l'ancienneté en jours.
3. Aucune modification de statut ni de donnée.

## Sorties

- `PA-02b` : Relances.

## Transitions

Aucune transition de statut.

## Notifications

| Code | Destinataires | Canal | Objet | Modèle |
| --- | --- | --- | --- | --- |
| N-09 | Responsable d'analyse, sinon G_RD | Mail | Relance : candidature {IdHNCS} sans traitement | `flows/templates/N-09.html` |

## Contrôles

Aucun contrôle `G_*`.

## Erreurs et reprise

- `PA-02b` : Socle (PA-00C) ; le passage du lendemain rattrape une exécution manquée.

## Décision humaine préservée

Aucune modification : simple relance.

## Points de test

- Candidature reçue il y a 6 jours (délai 5) → N-09.
- Candidature « Présélectionnée » ancienne → aucune relance.
- Une exécution par jour (08:00) : au plus une relance par jour en fonctionnement normal.

## Données lues et écrites

- `PA-02b` : lit `Candidatures`, `Parametres` ; écrit - ; flux enfants PA-00C.
