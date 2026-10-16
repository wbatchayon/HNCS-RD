# PA-00D — Attribuer les identifiants manquants

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec (§ 8.4) — ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 2 |
| Type (spec) | Planifié (toutes les heures) + manuel |
| Définitions techniques | `PA-00D` |
| Activé par défaut | Oui |

## Objectif

Filet de sécurité : attribuer `IdHNCS` aux éléments qui n'en ont pas (listes sans flux de création, créations hors flux).

## Déclencheur(s)

- `PA-00D` : Récurrence — Toutes les heures (exécution manuelle possible par « Exécuter »).

## Entrées

- `PA-00D` : Toutes les listes ayant un préfixe d'identifiant (§ 4.3) ; les listes des lots ≥ 3 ne sont traitées que si elles sont déployées.

## Traitement pas à pas

1. Pour chaque liste : éléments dont `IdHNCS` est vide.
2. `IdHNCS` = `{PREFIXE}-{année de Created, heure de Paris}-{ID sur 4 chiffres}` ; Pôles : `POL-{CodePole}`.
3. Une portée par liste : l'échec d'une liste est journalisé (PA-00C, Erreur) sans bloquer les autres.
4. Nombre d'identifiants attribués → `JournalFlux` niveau Info.

## Sorties

- `PA-00D` : `IdHNCS` renseigné.

## Transitions

Aucune transition de statut.

## Notifications

Aucune.

## Contrôles

Aucun contrôle `G_*`.

## Erreurs et reprise

- `PA-00D` : PA-00C par liste en échec ; rattrapage automatique au passage suivant.

## Décision humaine préservée

Sans objet.

## Points de test

- Élément créé sans identifiant → identifiant au format attendu en moins d'une heure.
- Pôle P3 → `POL-P3`.
- Liste de lot 3 absente : aucune erreur.

## Données lues et écrites

- `PA-00D` : lit `ActionsIntegration`, `Affectations`, `Alternants`, `BilansAlternance`, `Candidatures`, `CommunicationsRD`, `ComptesRendus`, `Conventions`, `DomainesCibles`, `Entretiens`, `Etablissements`, `InteractionsEcoles`, `Livrables`, `Mobilisations`, `Offres`, `Parametres`, `Poles`, `Referents`, `RegistreModeles`, `RessourcesTechniques`, `SujetsRD` ; écrit `ActionsIntegration`, `Affectations`, `Alternants`, `BilansAlternance`, `Candidatures`, `CommunicationsRD`, `ComptesRendus`, `Conventions`, `DomainesCibles`, `Entretiens`, `Etablissements`, `InteractionsEcoles`, `Livrables`, `Mobilisations`, `Offres`, `Poles`, `Referents`, `RegistreModeles`, `RessourcesTechniques`, `SujetsRD` ; flux enfants PA-00C.
