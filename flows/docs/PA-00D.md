# PA-00D : Attribuer les identifiants et initialiser les empreintes

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec ([8.4](../../spec.md#84-contrats-détaillés)) : ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 1 |
| Type (spec) | Planifié (toutes les heures) + manuel |
| Définitions techniques | `PA-00D` |
| Activé par défaut | Oui |

## Objectif

Filet de sécurité : attribuer `IdHNCS` aux éléments qui n'en ont pas (listes sans flux de création, créations hors flux) et, à partir du lot 2, initialiser les empreintes vides ([6.5](../../spec.md#65-formats-des-empreintes-p-09), H-55).

## Déclencheur(s)

- `PA-00D` : Récurrence : Toutes les heures (exécution manuelle possible par « Exécuter »).

## Entrées

- `PA-00D` : Toutes les listes ayant un préfixe d'identifiant ([4.3](../../spec.md#43-listes)) ; les listes des lots ≥ 3 ne sont traitées que si elles sont déployées.

## Traitement pas à pas

1. Pour chaque liste : éléments dont `IdHNCS` est vide.
2. `IdHNCS` = `{PREFIXE}-{année de Created, heure de Paris}-{ID sur 4 chiffres}` ; Pôles : `POL-{CodePole}`.
3. Une portée par liste : l'échec d'une liste est journalisé (PA-00C, Erreur) sans bloquer les autres.
4. Nombre d'identifiants attribués → `JournalFlux` niveau Info.
5. À partir du lot 2 (au moins une transition historisée par un flux, Origine = Flux) : empreintes vides initialisées à partir des valeurs courantes, sans rien rétablir : `EmpreinteVerrou` des affectations déjà validées (actives ou au-delà), `EmpreinteRevue` des livrables et comptes rendus, `EmpreinteAction`, `EmpreinteReferent` (référent renseigné), `EmpreinteDecision` (décideur déjà tracé, H-55) ; une portée par liste, liste ou colonne absente ignorée sans erreur ; nombre initialisé → `JournalFlux` Info.

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
- Lot 1 seul (aucun historique Origine = Flux) : aucune empreinte écrite.
- Livrable importé sans empreinte → `EmpreinteRevue` au format [6.5](../../spec.md#65-formats-des-empreintes-p-09) dans l'heure, aucune valeur rétablie.

## Données lues et écrites

- `PA-00D` : lit `ActionsIntegration`, `Affectations`, `Alternants`, `BilansAlternance`, `Candidatures`, `CommunicationsRD`, `ComptesRendus`, `Conventions`, `DomainesCibles`, `Entretiens`, `Etablissements`, `HistoriqueStatuts`, `InteractionsEcoles`, `Livrables`, `Mobilisations`, `Offres`, `Parametres`, `Poles`, `Referents`, `RegistreModeles`, `RessourcesTechniques`, `SujetsRD` ; écrit `ActionsIntegration`, `Affectations`, `Alternants`, `BilansAlternance`, `Candidatures`, `CommunicationsRD`, `ComptesRendus`, `Conventions`, `DomainesCibles`, `Entretiens`, `Etablissements`, `InteractionsEcoles`, `Livrables`, `Mobilisations`, `Offres`, `Poles`, `Referents`, `RegistreModeles`, `RessourcesTechniques`, `SujetsRD` ; flux enfants PA-00C.
