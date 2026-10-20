# PA-07b : Dépôt d'une nouvelle version

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec ([8.4](../../spec.md#84-contrats-détaillés)) : ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 2 |
| Type (spec) | Automatisé |
| Définitions techniques | `PA-07b` |
| Activé par défaut | Oui |

## Objectif

Rattacher les documents déposés dans « 04 : Livrables R&D » à leur livrable, sans changer son statut.

## Déclencheur(s)

- `PA-07b` : SharePoint : fichier de la bibliothèque « 04 - Livrables R&D » créé ou modifié (propriétés uniquement).
  - condition de déclenchement : `@not(equals(toLower(triggerOutputs()?['body/Editor/Email']), toLower(parameters('hncs_ServiceAccountEmail (hncs_ServiceAccountEmail)'))))`
  - condition de déclenchement : `@not(empty(triggerOutputs()?['body/Livrable/Id']))`

## Entrées

- `PA-07b` : Fichier créé ou modifié dans `LivrablesRD` avec la colonne `Livrable` renseignée.

## Traitement pas à pas

1. `IdObjet` = `IdHNCS` du livrable ; `Sujet` du document = sujet du livrable si vide.
2. `LienDocument` du livrable vide → renseigné avec le lien du fichier.
3. **Aucun changement de statut** : la soumission reste une action explicite (LIV-T03).

## Sorties

- `PA-07b` : Métadonnées du document, lien du livrable.

## Transitions

Aucune transition de statut.

## Notifications

| Code | Destinataires | Canal | Objet | Modèle |
| --- | --- | --- | --- | --- |
| N-92 | Auteur de la modification | Mail+Teams | {IdHNCS} : modification d'un champ protégé annulée | `flows/templates/N-92.html` |

## Contrôles

Aucun contrôle `G_*`.

## Erreurs et reprise

- `PA-07b` : Socle (PA-00C).

## Décision humaine préservée

La soumission reste une décision de l'alternant.

## Points de test

- Dépôt d'un fichier lié → `IdObjet` et `Sujet` renseignés, statut inchangé.

## Données lues et écrites

- `PA-07b` : lit `Livrables`, `LivrablesRD`, `Parametres` ; écrit `Livrables`, `LivrablesRD` ; flux enfants PA-00C.
