# PA-00A — Vérifier une transition

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec (§ 8.4) — ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 2 |
| Type (spec) | Flux enfant |
| Définitions techniques | `PA-00A` |
| Activé par défaut | Oui |

## Objectif

Vérifier qu'une transition de statut est autorisée : couple (De, Vers) actif dans `TransitionsStatuts` et rôle de l'acteur.

## Déclencheur(s)

- `PA-00A` : Déclenchement manuel par un flux parent (action « Exécuter un flux enfant »).

## Entrées

- `PA-00A` : `Objet`, `StatutAvant` (`∅` pour une création), `StatutApres`, `ActeurEmail`, `ItemAuteurEmail`, `ItemValideurEmail` (facultatifs).

## Traitement pas à pas

1. Lire les lignes actives de `TransitionsStatuts` (Objet, StatutDe, StatutVers).
2. Aucune ligne → `Autorise` = false, motif « Transition non autorisée ».
3. Acteur = compte de service → rôle `FLUX` uniquement.
4. Sinon, pour chaque rôle autorisé : appartenance au groupe SharePoint par REST (`sitegroups/getbyname/users`), ou comparaison en minuscules à `ItemAuteurEmail` / `ItemValideurEmail`.
5. Aucun rôle satisfait → motif « Rôle non autorisé ». Sinon `Autorise` = true, `CodeTransition`, `Controles` (codes `G_*`).

## Sorties

- `PA-00A` : `Autorise`, `CodeTransition`, `Controles`, `Motif`.

## Transitions

Aucune transition de statut.

## Notifications

Aucune.

## Contrôles

Aucun contrôle `G_*`.

## Erreurs et reprise

- `PA-00A` : Portée `Erreur_controle` : toute erreur technique répond `Autorise` = false et « Erreur technique de contrôle » (fail-safe) ; l'appelant journalise via PA-00C.

## Décision humaine préservée

Aucune : le flux ne fait que vérifier ; il n'existe aucun rôle `FLUX` sur une décision humaine (hors CAND-T02).

## Points de test

- Transition inexistante (ex. Reçue → Intégrée) refusée.
- Acteur hors groupe refusé ; membre direct du groupe accepté (H-14).
- ITEM_VALIDEUR : casse de l'adresse ignorée.
- Groupe absent → réponse « Erreur technique de contrôle ».

## Données lues et écrites

- `PA-00A` : lit `TransitionsStatuts` ; écrit — ; flux enfants —.
