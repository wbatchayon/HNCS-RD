# PA-00E — Supervision quotidienne des flux

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec (§ 8.4) — ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 2 |
| Type (spec) | Planifié (quotidien 07:30) |
| Définitions techniques | `PA-00E` |
| Activé par défaut | Oui |

## Objectif

Rappeler chaque jour les erreurs de flux non reprises.

## Déclencheur(s)

- `PA-00E` : Récurrence — Quotidien 07:30 (heure de Paris).

## Entrées

- `PA-00E` : `JournalFlux` : Niveau = Erreur et `StatutReprise` = « À reprendre ».

## Traitement pas à pas

1. Lister les erreurs à reprendre.
2. Si la liste n'est pas vide : N-98 (synthèse avec liens d'exécution) au support (`hncs_SupportEmail`) et aux membres de G_PROP.

## Sorties

- `PA-00E` : Courriel de synthèse.

## Transitions

Aucune transition de statut.

## Notifications

| Code | Destinataires | Canal | Objet | Modèle |
| --- | --- | --- | --- | --- |
| N-98 | Destinataires.Support, G_PROP | Mail | Erreurs de flux à reprendre ({n}) | `flows/templates/N-98.html` |

## Contrôles

Aucun contrôle `G_*`.

## Erreurs et reprise

- `PA-00E` : Socle (PA-00C).

## Décision humaine préservée

Sans objet.

## Points de test

- Aucune erreur : aucun courriel.
- Deux erreurs à reprendre : N-98 avec deux lignes ; après « Reprise effectuée », plus de rappel.

## Données lues et écrites

- `PA-00E` : lit `JournalFlux`, `Parametres` ; écrit — ; flux enfants PA-00C.
