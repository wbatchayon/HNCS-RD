# PA-00E : Supervision quotidienne des flux

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec ([8.4](../../spec.md#84-contrats-détaillés)) : ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 2 |
| Type (spec) | Planifié (quotidien 07:30) |
| Définitions techniques | `PA-00E` |
| Activé par défaut | Oui |

## Objectif

Rapprocher chaque jour les statuts de l'historique validé (filet de sécurité) et rappeler les erreurs de flux non reprises.

## Déclencheur(s)

- `PA-00E` : Récurrence : Quotidien 07:30 (heure de Paris).

## Entrées

- `PA-00E` : Listes à statut contrôlé ([8.2](../../spec.md#82-partition-des-statuts-cibles)) et `HistoriqueStatuts` ; `JournalFlux` : Niveau = Erreur et `StatutReprise` = « À reprendre ».

## Traitement pas à pas

1. Rapprochement des statuts : pour chaque élément dont `Statut` diffère du dernier `StatutApres` accepté dans `HistoriqueStatuts` (entrées `REF-PRINCIPAL` exclues), sans exécution en cours (éléments modifiés depuis moins de 30 minutes ignorés), rétablissement par PA-00B (refus, Origine Flux, motif « Rapprochement quotidien », N-90 à l'auteur de la dernière modification) et `JournalFlux` Avertissement. Les éléments sans aucune transition acceptée sont laissés à PA-00D (entrée `REPRISE`, [6.1](../../spec.md#61-règles-générales), règle 3 ter). Une portée par liste ; les listes du lot 3 ne sont traitées que si elles sont déployées.
2. Lister les erreurs à reprendre.
3. Si la liste n'est pas vide, ou si l'étape 1 a rétabli des statuts : N-98 (synthèse avec liens d'exécution et tableau des rapprochements) au support (`hncs_SupportEmail`) et aux membres de G_PROP.

## Sorties

- `PA-00E` : Statuts rétablis, historique, courriel de synthèse.

## Transitions

Aucune transition de statut.

## Notifications

| Code | Destinataires | Canal | Objet | Modèle |
| --- | --- | --- | --- | --- |
| N-98 | `hncs_SupportEmail` (variable d'environnement), G_PROP | Mail | Erreurs de flux à reprendre ({n}) | `flows/templates/N-98.html` |

## Contrôles

Aucun contrôle `G_*`.

## Erreurs et reprise

- `PA-00E` : Socle (PA-00C) ; échec d'une liste journalisé sans bloquer les autres.

## Décision humaine préservée

Le rapprochement ne prend aucune décision : il rétablit le dernier statut validé par une transition acceptée.

## Points de test

- Aucune erreur ni écart : aucun courriel.
- Deux erreurs à reprendre : N-98 avec deux lignes ; après « Reprise effectuée », plus de rappel.
- Statut d'un livrable modifié par l'API sans transition acceptée → rétabli au statut validé, N-90, mention dans N-98.

## Données lues et écrites

- `PA-00E` : lit `Affectations`, `Alternants`, `Candidatures`, `CommunicationsRD`, `ComptesRendus`, `Conventions`, `HistoriqueStatuts`, `JournalFlux`, `Livrables`, `Parametres`, `SujetsRD` ; écrit - ; flux enfants PA-00B, PA-00C.
