# PA-08b — Création et relance des comptes rendus

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec (§ 8.4) — ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 3 |
| Type (spec) | Planifié (quotidien 06:45) |
| Définitions techniques | `PA-08b` |
| Activé par défaut | Oui |

## Objectif

Créer les comptes rendus attendus selon la cadence, rappeler l'échéance et constater les non-remises.

## Déclencheur(s)

- `PA-08b` : Récurrence — Quotidien 06:45 (heure de Paris).

## Entrées

- `PA-08b` : Affectations « Active », « À risque », « Bloquée » ; comptes rendus « Attendu » / « En rédaction » ; `CR.CadenceGlobale`, `CR.DelaiRemiseJours`, `CR.DelaiNonRemisJours`.

## Traitement pas à pas

1. Cadence « Par jalon » : aucune création automatique (les rappels et le constat « Non remis » s'appliquent aux comptes rendus créés à la main). Cadence effective (`CadenceCR`, sinon `CR.CadenceGlobale`) ≠ « Par jalon » : période courante ancrée sur le début de l'affectation (Hebdomadaire 7 j, Quinzaine 14 j, Mensuelle = mois calendaire) ; aucun compte rendu ne la couvre → création « Attendu » (`Echeance` = fin + `CR.DelaiRemiseJours`, effets de création de PA-08, CR-T01 FLUX) et `ProchaineEcheanceCR`.
2. Veille de l'échéance → N-30 à l'alternant (une fois, `DernierRappel`).
3. `G_CR_ECHU` (aujourd'hui > échéance + `CR.DelaiNonRemisJours`) → « Non remis » (CR-T04, FLUX) et N-31 au valideur.

## Sorties

- `PA-08b` : Comptes rendus, rappels, statuts « Non remis ».

## Transitions

| Code | De | Vers | Acteurs | Contrôles |
| --- | --- | --- | --- | --- |
| CR-T01 | ∅ | Attendu | FLUX, RD | — |
| CR-T04-01 | Attendu | Non remis | FLUX | G_CR_ECHU |
| CR-T04-02 | En rédaction | Non remis | FLUX | G_CR_ECHU |

Statuts écrits par le compte de service (rôle `FLUX`, jamais une décision humaine) :

- `ComptesRendus` : « Attendu », « Non remis »

## Notifications

| Code | Destinataires | Canal | Objet | Modèle |
| --- | --- | --- | --- | --- |
| N-30 | Alternant | Mail+Teams | Rappel : compte rendu {IdHNCS} attendu le {date} | `flows/templates/N-30.html` |
| N-31 | Référent (valideur) | Mail | Compte rendu {IdHNCS} non remis | `flows/templates/N-31.html` |

## Contrôles

- `G_CR_ECHU` : Aujourd'hui > Echeance + CR.DelaiNonRemisJours

## Erreurs et reprise

- `PA-08b` : Socle (PA-00C) ; rattrapage le lendemain.

## Décision humaine préservée

« Non remis » est un constat de date ; la validation reste au référent.

## Points de test

- Affectation quinzaine sans CR courant → un CR créé, aucun doublon le lendemain.
- Échéance + 3 j dépassée → « Non remis » et N-31.

## Données lues et écrites

- `PA-08b` : lit `Affectations`, `Alternants`, `ComptesRendus`, `Parametres`, `Referents` ; écrit `Affectations`, `ComptesRendus` ; flux enfants PA-00A, PA-00B, PA-00C.
