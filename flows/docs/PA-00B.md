# PA-00B — Appliquer ou annuler une transition

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec (§ 8.4) — ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 2 |
| Type (spec) | Flux enfant |
| Définitions techniques | `PA-00B` |
| Activé par défaut | Oui |

## Objectif

Appliquer (acceptation) ou annuler (refus) une transition et l'historiser.

## Déclencheur(s)

- `PA-00B` : Déclenchement manuel par un flux parent (action « Exécuter un flux enfant »).

## Entrées

- `PA-00B` : `Liste`, `ItemId`, `IdObjet`, `Objet`, `StatutAvant`, `StatutApres`, `Accepte`, `CodeTransition`, `ActeurEmail`, `Origine`, `Motif`, `RunId`.

## Traitement pas à pas

1. Lire les paramètres (boîte R&D, notifications Teams).
2. Acceptée : `StatutPrecedent` = `StatutApres`, `DateStatut` = maintenant (REST `MERGE`, liste désignée par son nom interne via `GetList`).
3. Refusée : `Statut` = `StatutAvant` (`StatutPrecedent` inchangé) puis N-90 à l'acteur. Refus d'une création (`StatutAvant` = `∅`, § 6.1-3 bis) : l'élément est envoyé à la corbeille du site (`recycle`, récupérable 93 jours, jamais supprimé définitivement), puis N-90.
4. Dans les deux cas : création d'un élément `HistoriqueStatuts` (`Acceptée` ou `Refusée — annulée`).

## Sorties

- `PA-00B` : `Ok` = true.

## Transitions

Aucune transition de statut.

## Notifications

| Code | Destinataires | Canal | Objet | Modèle |
| --- | --- | --- | --- | --- |
| N-90 | Auteur de la modification | Mail+Teams | Changement de statut refusé ({IdHNCS}) | `flows/templates/N-90.html` |

## Contrôles

Aucun contrôle `G_*`.

## Erreurs et reprise

- `PA-00B` : Toute erreur d'écriture termine le flux en échec : l'action d'appel du parent échoue et le parent passe en portée `Erreur` (PA-00C).

## Décision humaine préservée

Le flux ne modifie jamais une décision : il ne fait que rétablir le dernier statut validé.

## Points de test

- Refus : statut rétabli, historique « Refusée — annulée », N-90 reçu.
- Acceptation : `StatutPrecedent` et `DateStatut` mis à jour.
- Écriture impossible (liste verrouillée) : le parent journalise une erreur.

## Données lues et écrites

- `PA-00B` : lit `Parametres` ; écrit `Affectations`, `Alternants`, `Candidatures`, `CommunicationsRD`, `ComptesRendus`, `Conventions`, `HistoriqueStatuts`, `Livrables`, `SujetsRD` ; flux enfants PA-00C.
