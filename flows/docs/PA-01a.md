# PA-01a : Nouvelle candidature : saisie ou formulaire

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec ([\[8.4\]](../../spec.md#84-contrats-détaillés)) : ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 2 |
| Type (spec) | Automatisé |
| Définitions techniques | `PA-01a` |
| Activé par défaut | Oui |

## Objectif

Enregistrer proprement toute nouvelle candidature (saisie manuelle, formulaire ou boîte mail R&D) : identifiant, signalement de doublon, dossier CV cloisonné, historique et notification de la R&D.

## Déclencheur(s)

- `PA-01a` : SharePoint : élément de la liste « Candidatures » (création).
  - condition de déclenchement : `@not(equals(toLower(triggerOutputs()?['body/Editor/Email']), toLower(parameters('hncs_ServiceAccountEmail (hncs_ServiceAccountEmail)'))))`
  - statuts cibles (partition [\[8.2\]](../../spec.md#82-partition-des-statuts-cibles)) : « Reçue »

## Entrées

- `PA-01a` : Élément `Candidatures` saisi par la R&D (statut « Reçue »).

## Traitement pas à pas

1. `IdHNCS` (`CAND-AAAA-NNNN`) s'il est vide ; statut validé = dernière transition acceptée de `HistoriqueStatuts` : l'exécution ne continue que pour une création (aucune transition acceptée) au statut « Reçue ».
2. Socle : PA-00A sur CAND-T01 (∅ → Reçue, acteurs RD ou FLUX) ; refus → règle [\[6.1\]](../../spec.md#61-règles-générales), règle 3 bis : PA-00B envoie l'élément à la corbeille du site, historise « Refusée et annulée » et notifie N-90 ; fin.
3. Contrôle doublon si `Email` est renseigné : autre candidature non terminale (≠ Intégrée, Non retenue, Clôturée) avec le même `Email` (comparaison SharePoint insensible à la casse) → `DoublonPotentiel` = Oui et `DoublonDe` ; jamais de fusion ni de clôture.
4. Dossier `01 : Recrutement/{AAAA}/{IdHNCS}` (AAAA = année de création, heure de Paris) créé s'il est absent ; héritage rompu avec copie (G_PROP FC, G_DRD et G_RD CSS ajoutés explicitement) ; `LienCV` = lien du dossier.
5. PA-00B : historiser CAND-T01 si aucune transition n'est encore acceptée pour l'élément (`StatutPrecedent` = Reçue, copie de commodité).
6. Si `ResponsableAnalyse` est renseigné **et** `G_IDENTITE` satisfait : CAND-T02 (Reçue → À analyser, rôle FLUX, exception documentée) via PA-00A, contrôles `G_RESP_ANALYSE` et `G_IDENTITE`, écriture du statut, PA-00B, puis N-03 au responsable (règle [\[6.1\]](../../spec.md#61-règles-générales), règle 8).
7. N-01 au responsable d'analyse, sinon aux membres de G_RD (Teams au responsable) ; pour une candidature « À qualifier », N-01 demande la qualification de l'identité.
8. Si `Fonction.AccuseReceptionActif` = Oui, identité qualifiée et `AccuseReceptionEnvoye` = Non : N-02 au candidat puis `AccuseReceptionEnvoye` = Oui.

## Sorties

- `PA-01a` : Élément complété, dossier CV, historique, notifications.

## Transitions

| Code | De | Vers | Acteurs | Contrôles |
| --- | --- | --- | --- | --- |
| CAND-T01 | ∅ | Reçue | RD, FLUX | - |
| CAND-T02 | Reçue | À analyser | RD, FLUX | G_RESP_ANALYSE, G_IDENTITE |

Statuts écrits par le compte de service (rôle `FLUX`, jamais une décision humaine) :

- `Candidatures` : « À analyser »

## Notifications

| Code | Destinataires | Canal | Objet | Modèle |
| --- | --- | --- | --- | --- |
| N-01 | Responsable d'analyse, sinon G_RD | Mail+Teams | Nouvelle candidature {IdHNCS} | `flows/templates/N-01.html` |
| N-02 | Candidat | Mail | Accusé de réception de votre candidature | `flows/templates/N-02.html` |
| N-03 | Responsable d'analyse | Mail+Teams | Candidature {IdHNCS} à analyser | `flows/templates/N-03.html` |

## Contrôles

- `G_IDENTITE` : Email renseigné et Title ne commence pas par « À qualifier » (identité du candidat qualifiée par la R&D)
- `G_RESP_ANALYSE` : ResponsableAnalyse renseigné

## Erreurs et reprise

- `PA-01a` : Socle : portée `Erreur` → PA-00C (N-99) puis échec ; la resoumission est idempotente (identifiant, doublon, dossier, historique et accusé déjà posés ne sont pas refaits). N-01 peut être renvoyée lors d'une resoumission (aucun marqueur prévu par la spec).

## Décision humaine préservée

Aucune décision : le doublon est **signalé**, jamais fusionné ni clôturé ; la présélection reste une décision de la R&D.

## Points de test

- Saisie manuelle par un membre RD : identifiant, dossier, historique CAND-T01, N-01 à G_RD.
- Création par un membre ADMIN (hors acteurs de CAND-T01) : élément en corbeille, historique « Refusée et annulée », N-90.
- Saisie avec responsable : passage à « À analyser » par FLUX, historisé, N-03.
- Même e-mail qu'une candidature ouverte : doublon signalé, aucune autre modification.
- Accusé de réception désactivé par défaut : aucun courriel au candidat.

## Données lues et écrites

- `PA-01a` : lit `Candidatures`, `HistoriqueStatuts`, `Parametres` ; écrit `Candidatures`, `Recrutement` ; flux enfants PA-00A, PA-00B, PA-00C.
