# PA-00C — Journaliser une erreur

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec (§ 8.4) — ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 1 |
| Type (spec) | Flux enfant |
| Définitions techniques | `PA-00C` |
| Activé par défaut | Oui |

## Objectif

Tracer une erreur, un avertissement ou un événement métier dans `JournalFlux` et prévenir le support en cas d'erreur.

## Déclencheur(s)

- `PA-00C` : Déclenchement manuel par un flux parent (action « Exécuter un flux enfant »).

## Entrées

- `PA-00C` : `CodeFlux`, `Niveau`, `Liste`, `ItemId`, `IdObjet`, `Message`, `DetailErreur`, `RunUrl`.

## Traitement pas à pas

1. Créer l'élément `JournalFlux` (`StatutReprise` = « À reprendre » si Niveau = Erreur, sinon « Sans objet »).
2. Lire la boîte expéditrice (`Destinataires.BoiteRD`), même si l'écriture du journal a échoué.
3. Niveau = Erreur : envoyer N-99 à `hncs_SupportEmail` (tenté même si le journal n'a pas pu être écrit).

## Sorties

- `PA-00C` : `IdJournal` (vide si l'écriture a échoué).

## Transitions

Aucune transition de statut.

## Notifications

| Code | Destinataires | Canal | Objet | Modèle |
| --- | --- | --- | --- | --- |
| N-99 | `hncs_SupportEmail` (variable d'environnement) | Mail | Erreur du flux {code} | `flows/templates/N-99.html` |

## Contrôles

Aucun contrôle `G_*`.

## Erreurs et reprise

- `PA-00C` : Le courriel N-99 est tenté quel que soit le résultat de l'écriture du journal ; le flux répond toujours à l'appelant.

## Décision humaine préservée

Sans objet.

## Points de test

- Niveau Erreur : élément « À reprendre » et N-99 reçu.
- Liste `JournalFlux` indisponible : N-99 reçu quand même.
- Niveau Info : aucun courriel.

## Données lues et écrites

- `PA-00C` : lit `Parametres` ; écrit `JournalFlux` ; flux enfants —.
