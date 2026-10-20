# PA-03b : Rappels d'entretien et demande de résultat

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec ([\[8.4\]](../../spec.md#84-contrats-détaillés)) : ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 2 |
| Type (spec) | Planifié (toutes les heures, 07:00 à 20:00) |
| Définitions techniques | `PA-03b` |
| Activé par défaut | Oui |

## Objectif

Rappeler les entretiens à venir et demander la saisie des résultats en retard.

## Déclencheur(s)

- `PA-03b` : Récurrence : Toutes les heures de 07:00 à 20:00 (heure de Paris).

## Entrées

- `PA-03b` : Entretiens « Planifié » ; `Delai.RappelEntretienHeures`.

## Traitement pas à pas

1. Entretiens dans les `Delai.RappelEntretienHeures` à venir avec `RappelEnvoye` = Non → N-10 aux participants puis `RappelEnvoye` = Oui.
2. Entretiens dont la date est passée de plus de 2 h avec `DemandeResultatEnvoyee` = Non → N-14 à l'administration puis `DemandeResultatEnvoyee` = Oui.

## Sorties

- `PA-03b` : Rappels et demandes, indicateurs posés (idempotence).

## Transitions

Aucune transition de statut.

## Notifications

| Code | Destinataires | Canal | Objet | Modèle |
| --- | --- | --- | --- | --- |
| N-10 | Participants de l'entretien | Mail+Teams | Rappel : entretien {IdHNCS} le {date} | `flows/templates/N-10.html` |
| N-14 | Destinataires.Administration | Mail | Résultat d'entretien à saisir ({IdHNCS}) | `flows/templates/N-14.html` |

## Contrôles

Aucun contrôle `G_*`.

## Erreurs et reprise

- `PA-03b` : Socle (PA-00C) ; rattrapage au passage horaire suivant.

## Décision humaine préservée

Aucune.

## Points de test

- Entretien dans 20 h → un seul rappel.
- Entretien passé de 3 h → une seule demande de résultat.

## Données lues et écrites

- `PA-03b` : lit `Candidatures`, `Entretiens`, `Parametres` ; écrit `Entretiens` ; flux enfants PA-00C.
