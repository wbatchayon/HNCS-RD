# PA-01b — Nouvelle candidature — boîte mail R&D

> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec (§ 8.4) — ne pas modifier à la main.

| Élément | Valeur |
| --- | --- |
| Lot | 2 |
| Type (spec) | Automatisé |
| Définitions techniques | `PA-01b` |
| Activé par défaut | Oui |

## Objectif

Créer une candidature à partir d'un courriel déposé dans le dossier « Candidatures » de la boîte partagée R&D, puis appliquer le traitement commun de PA-01a.

## Déclencheur(s)

- `PA-01b` : Office 365 Outlook — nouveau courriel dans une boîte partagée (V2), dossier « Candidatures ».

## Entrées

- `PA-01b` : Expéditeur, objet, `Internet-Message-Id`, date de réception et pièces jointes du courriel.

## Traitement pas à pas

1. Idempotence : si une candidature porte déjà ce `RefMessage` et que son dossier CV est posé → fin ; si elle existe sans dossier (exécution interrompue) → reprise sur l'élément existant.
2. Canal déduit par `Canal.Regles` (`motif=canal`) : domaine de l'expéditeur, puis balise d'objet (ex. `[CANDIDATURE-SITE]`) ; valeur hors énumération ou aucune règle → « À qualifier ».
3. Création de l'élément (`ModeReception` = Boîte mail R&D, `Statut` = Reçue, `DateReception`, `RefMessage`) : courriel de plateforme (règle de **domaine** donnant LinkedIn ou France Travail) → `Title` = « À qualifier – {RefMessage} », `Email` vide ; sinon `Email` = adresse de l'expéditeur et `Title` = partie locale de l'adresse (le nom affiché n'est pas exposé par le déclencheur standard, voir divergences).
4. Traitement commun PA-01a (CAND-T01 par FLUX) ; en plus, enregistrement des pièces jointes non incorporées dont l'extension figure dans `Canal.ExtensionsAutorisees` dans le dossier CV, métadonnées `TypeDocument` = CV, `Candidature`, `IdObjet`.
5. Pièce jointe refusée (type) → `JournalFlux` Avertissement (extension seulement, jamais le nom du fichier) ; la candidature est créée quand même.

## Sorties

- `PA-01b` : Candidature créée et complétée, pièces jointes classées, historique CAND-T01 (Origine Flux).

## Transitions

| Code | De | Vers | Acteurs | Contrôles |
| --- | --- | --- | --- | --- |
| CAND-T01 | ∅ | Reçue | RD, FLUX | — |
| CAND-T02 | Reçue | À analyser | RD, FLUX | G_RESP_ANALYSE, G_IDENTITE |

Statuts écrits par le compte de service (rôle `FLUX`, jamais une décision humaine) :

- `Candidatures` : « Reçue », « À analyser »

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

- `PA-01b` : Socle (PA-00C) ; reprise par resoumission sans doublon grâce à `RefMessage`.

## Décision humaine préservée

Aucune : le flux enregistre, il ne juge pas la candidature ; l'identité d'un courriel de plateforme est qualifiée par la R&D.

## Points de test

- Courriel `[CANDIDATURE-SITE]` → canal « Site HNCS », e-mail de l'expéditeur.
- Expéditeur `@linkedin.com` → « LinkedIn », titre « À qualifier – … », e-mail vide, pas de passage automatique à « À analyser ».
- Pièce jointe `.exe` refusée et journalisée.
- Même courriel retraité : aucun doublon.

## Données lues et écrites

- `PA-01b` : lit `Candidatures`, `Parametres` ; écrit `Candidatures`, `Recrutement` ; flux enfants PA-00A, PA-00B, PA-00C.
