# PA-00F : Droits des propriétaires de modèles

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec ([8.4](../../spec.md#84-contrats-détaillés)) : ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 2 |
| Type (spec) | Automatisé |
| Définitions techniques | `PA-00F` |
| Activé par défaut | Oui |

## Objectif

Réserver la modification d'un modèle à son propriétaire ([7.4](../../spec.md#74-permissions-au-niveau-élément-ou-dossier-posées-par-les-flux)) : élément du registre et fichiers de « 03 : Modèles R&D » liés.

## Déclencheur(s)

- `PA-00F` : SharePoint : élément de la liste « Registre des modèles R&D » (création ou modification).
  - condition de déclenchement : `@not(equals(toLower(triggerOutputs()?['body/Editor/Email']), toLower(parameters('hncs_ServiceAccountEmail (hncs_ServiceAccountEmail)'))))`

## Entrées

- `PA-00F` : Élément `RegistreModeles` créé ou modifié (création, changement de `Proprietaire` ou de `LienFichier`, détectés par « Obtenir les modifications »).

## Traitement pas à pas

1. `IdHNCS` (`MOD-…`) si vide.
2. Rompre l'héritage de l'élément (copie) et donner CSS au `Proprietaire`.
3. Même attribution sur chaque fichier de `ModelesRD` dont la colonne `Modele` désigne l'élément.
4. L'ancien propriétaire n'est pas retiré automatiquement (revue des accès, [7.1](../../spec.md#71-groupes-sharepoint)) ; `JournalFlux` Info.

## Sorties

- `PA-00F` : Permissions ; `JournalFlux` Info.

## Transitions

Aucune transition de statut.

## Notifications

| Code | Destinataires | Canal | Objet | Modèle |
| --- | --- | --- | --- | --- |
| N-92 | Auteur de la modification | Mail+Teams | {IdHNCS} : modification d'un champ protégé annulée | `flows/templates/N-92.html` |

## Contrôles

Aucun contrôle `G_*`.

## Erreurs et reprise

- `PA-00F` : Socle (PA-00C) ; attributions idempotentes.

## Décision humaine préservée

Sans objet (droits techniques) ; l'approbation d'un modèle reste humaine.

## Points de test

- Changement de propriétaire → le nouveau propriétaire peut modifier le modèle et ses fichiers ; l'ancien conserve ses droits jusqu'à la revue.
- Modification d'un autre champ → aucune action.

## Données lues et écrites

- `PA-00F` : lit `ModelesRD`, `Parametres`, `RegistreModeles` ; écrit `RegistreModeles` ; flux enfants PA-00C.
