# Scénarios de recette de bout en bout — HNCS-RD

> Référence : `spec.md` § 12.1 (S-01 à S-15, repris du cadrage § 10.1) et scénarios complémentaires S-16 à S-26.
> Spec en vigueur : v1.3.0. En cas d'écart, la spec prévaut.
> Tous les scénarios s'exécutent sur un **site de recette** (URL contenant « recette », « test », « qualif » ou « dev »),
> avec le jeu de test fictif de `testdata/` et les personas de `testdata/personas.json`.

## 0. Préparation commune

| # | Étape | Commande / action | Preuve |
| --- | --- | --- | --- |
| P1 | Provisionner le site jusqu'au lot visé | `pwsh ./provisioning/Deploy-HNCSRD.ps1 -ConfigPath ./provisioning/config/tenant.json -Lot 3` (lot 4 pour Power BI) | journal `provisioning/logs/deploy-*.log` |
| P2 | Créer les comptes des personas et générer le fichier des membres | `pwsh ./testdata/Import-TestData.ps1 -PersonasPath ./testdata/personas.json -ExporterMembres ./provisioning/config/membres.json` | fichier `membres.json` |
| P3 | Ajouter les membres (directs, H-14) | `pwsh ./provisioning/Set-HNCSRDMembres.ps1 -ConfigPath ./provisioning/config/tenant.json -MembresPath ./provisioning/config/membres.json` | journal `membres-*.log` |
| P4 | Contrôle post-déploiement | `pwsh ./provisioning/Test-HNCSRDDeploiement.ps1 -Lot 3` | code retour 0, rapport d'écarts vide |
| P5 | Importer le jeu de test, **flux désactivés** (ou sous le compte de service) | `pwsh ./testdata/Import-TestData.ps1 -ConfigPath ./provisioning/config/tenant.json -SiteUrl <url de recette> -PermissionsElement` | bilan « Cree / MisAJour / Erreur = 0 » |
| P6 | Paramètre de recette | `Fonction.RepriseExistantActive` = Non (défaut) ; `Recrutement.PartageTransmission` = Groupe (défaut) | capture de la liste `Parametres` |
| P7 | Importer et activer la solution de flux (lot 2 / 3) | voir `docs/installation.md` (solution de flux) | flux « Activé » dans la solution `HNCSRDSuivi` |
| P8 | Configurer les tests automatisés | copier `tests/e2e/config.sample.json` en `tests/e2e/config.json` | — |

Conventions : « J » = jour d'exécution ; les identifiants `…-2026-9xxx` sont ceux du jeu de test (`testdata/README.md`).
Les éléments créés pendant la recette portent le marqueur `E2E-<horodatage>` ou le préfixe `RECETTE` dans leur titre.
Preuves à archiver dans le dossier de recette : captures d'écran, exports de `HistoriqueStatuts` et `JournalFlux`
(vue « Journal complet »), courriels reçus (objet `[HNCS-R&D][N-xx]`), sortie Pester (`-Output Detailed`).

Automatisation : `Invoke-Pester ./tests/e2e/HNCSRD.E2E.Tests.ps1` (scénarios) et `./tests/e2e/Access.Tests.ps1`
(droits) ; la colonne « Pester » indique le bloc correspondant. Étiquettes : `Flux`, `Planifie`, `Destructif`, `Lot1`.

| Scénario | Titre | Lot | Pester |
| --- | --- | --- | --- |
| S-01 | Candidature de chaque canal | 2 | `S-01` (sauf courriel PA-01b : manuel) |
| S-02 | Candidature non présélectionnée clôturée, CV non transmis | 2 | `S-02` |
| S-03 | Présélection, transmission, entretien, décision | 2 | `S-03 / S-04` |
| S-04 | Formalités puis création de l'alternant après confirmation | 2 | `S-03 / S-04` |
| S-05 | École rattachée à plusieurs alternants, convention avec son statut | 1 | manuel (+ `tests/offline`) |
| S-06 | Changement de référent / sujet, anciennes affectations conservées | 2 | `S-03 / S-04`, `S-06 / S-23` |
| S-07 | Livrable corrigé puis validé, versions et commentaires conservés | 2 | `S-07 / S-13` |
| S-08 | Rappel de retard aux seuls acteurs concernés | 2 | `S-08` (Planifie) |
| S-09 | Power BI cohérent et sans donnée sensible | 4 | manuel + `reconciliation/` |
| S-10 | Échec de flux visible, notifié, repris | 2 | `S-10` (partiel) |
| S-11 | Candidature de plateforme sans identité | 2 | `S-11` |
| S-12 | Échéance de livrable déplacée | 2 | manuel |
| S-13 | Alternant réviseur de son propre livrable | 2 | `S-07 / S-13` |
| S-14 | Signature d'une convention de partenariat sans décision | 3 | `S-14 / S-19` |
| S-15 | Droits d'accès persona par persona | 1 | `Access.Tests.ps1` |
| S-16 | Transition interdite annulée et historisée | 2 | `S-16` |
| S-17 | « Intégrée » sans formalités complètes | 2 | `S-03 / S-04` |
| S-18 | Idempotence (resoumission, réimport) | 1-2 | `S-18` (import) + manuel |
| S-19 | Décision de partenariat refusée à un non-habilité | 3 | `S-14 / S-19` |
| S-20 | Compte rendu non remis | 3 | `S-20` (Planifie) |
| S-21 | Fin d'alternance | 3 | `S-21` (Destructif) |
| S-22 | Arbitrage du portefeuille de sujets | 3 | `S-22` |
| S-23 | Champs protégés (P-09) : référent principal, réviseur, échéance | 2 | `S-06 / S-23`, `S-07 / S-13` |
| S-24 | Permissions de dossiers des bibliothèques | 2 | manuel |
| S-25 | Lot 1 sans flux : procédure manuelle de partage (H-50) | 1 | manuel |
| S-26 | Refus d'une création (corbeille, § 6.1-3 bis) | 2 | `S-26` |

---

## S-01 — Une candidature de chaque canal est enregistrée sans intégration technique directe

- **Références** : P-06, H-04, CAND-T01, PA-01a / PA-01b, `Canal.Regles`, N-01.
- **Persona** : RD1 (saisie), boîte partagée R&D (courriels), IT (contrôle).
- **Préconditions** : P1 à P7 ; règles Outlook de la boîte R&D déposant les candidatures dans le dossier `Candidatures`.

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | RD1 crée dans « Candidatures » une candidature canal **Site HNCS** (saisie manuelle), sans responsable | `IdHNCS` = `CAND-AAAA-NNNN` ; statut « Reçue » ; dossier `01 — Recrutement/AAAA/CAND-…` créé ; `LienCV` renseigné ; historique CAND-T01 « Acceptée » ; N-01 à G_RD |
| b | Idem canal **LinkedIn**, **France Travail**, **Candidature spontanée** | mêmes effets ; canal conservé |
| c | Idem avec `ResponsableAnalyse` = RD1 | passage automatique « À analyser » (CAND-T02, Origine Flux) et N-03 à RD1 |
| d | Saisir une 2ᵉ candidature avec le même e-mail qu'une candidature active | `DoublonPotentiel` = Oui, `DoublonDe` renseigné ; aucune fusion, aucune clôture |
| e | Envoyer depuis une boîte externe fictive un courriel d'objet `[CANDIDATURE-SITE] Candidature RECETTE` avec un PDF | élément créé (`ModeReception` = Boîte mail R&D, canal Site HNCS, `RefMessage` renseigné) ; PDF dans le dossier CV |
| f | Renvoyer **le même** courriel (même `Internet-Message-Id`, par ex. en le redéplaçant dans le dossier) | aucune seconde candidature (idempotence PA-01b) |
| g | Envoyer un courriel avec une pièce jointe `.exe` | candidature créée ; `JournalFlux` Avertissement « Pièce jointe refusée » ; aucun fichier `.exe` stocké |

- **Preuves** : vue « Candidatures en cours », historique filtré sur les `IdHNCS`, courriels N-01 / N-03, contenu du dossier CV.
- **Aucune** API LinkedIn / France Travail n'est sollicitée (contrôler l'absence de connecteur tiers dans la solution).

## S-02 — Candidature non présélectionnée clôturée ; aucun CV transmis à un non-habilité

- **Références** : CAND-T03, CAND-T06, `G_AVIS_ANALYSE`, validation de liste (motif), N-06, N-08, P-04, H-29.
- **Personas** : RD1, ADMIN_KARINE, DIRECTION.
- **Préconditions** : une candidature « À analyser » (S-01 c) ou CAND-2026-9002 du jeu.

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | RD1 passe « En cours d'analyse » | `DateAnalyse` renseignée ; historique CAND-T03 |
| b | RD1 passe « Non retenue » **sans** motif | enregistrement refusé par la règle de validation de liste (message « Motif obligatoire… ») |
| c | RD1 passe « Non retenue » **sans** avis de la R&D (motif renseigné) | statut rétabli (G_AVIS_ANALYSE), historique « Refusée — annulée », N-90 à RD1 |
| d | RD1 renseigne `AvisAnalyse` et `MotifCode`, passe « Non retenue » | historique CAND-T06 ; `DateCloture`, `DateDecisionPreselection`, `DecisionPreselection` = Écartée ; N-06 à G_RD **sans pièce jointe** ; tâche N-08 « informer le candidat » (H-09) |
| e | ADMIN_KARINE et DIRECTION ouvrent l'URL de l'élément et du dossier CV | accès refusé (aucune permission par élément pour G_ADM) |

- **Preuves** : message de validation, historique, courriel N-06 (vérifier : aucun CV joint, aucun nom dans un courriel de groupe large), captures d'accès refusé.

## S-03 — Présélection transmise à l'administration ; entretien et décision traçables

- **Références** : CAND-T04, CAND-T05 (FLUX), CAND-T07, CAND-T09, CAND-T10, CAND-T11, N-05, N-11, N-12, N-13, § 7.4, H-45.
- **Personas** : RD1, ADMIN_KARINE, DIRECTION, RD2 (participant d'un entretien).

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | RD1 renseigne l'avis et passe « Présélectionnée » | quelques secondes plus tard « Transmise à l'administration » (CAND-T05, Origine Flux) ; `DateTransmissionAdmin`, `DestinataireAdmin` ; N-05 à l'administration avec **liens** (élément, dossier CV), sans pièce jointe ni recopie de l'avis |
| b | ADMIN_KARINE ouvre l'élément et le dossier CV | accès accordé (CSS) ; DIRECTION toujours refusée |
| c | ADMIN_KARINE crée un entretien « Planifié » lié, participants ADMIN_KARINE et RD2 | candidature « Entretien planifié » (CAND-T07) ; RD2 lit l'entretien (Participants : R, H-28), pas les autres |
| d | Passer l'entretien « Réalisé » **sans** résultat | refusé par la règle de validation de liste |
| e | Saisir `Resultat` = Favorable et « Réalisé » | candidature « Entretien réalisé » (CAND-T09) ; `SaisiPar`, `DateSaisieResultat` ; historique Objet = Entretien ; N-11 à G_RD **sans** commentaire d'évaluation |
| f | ADMIN_KARINE passe « En attente de décision », puis renseigne `DecideurFinal` et « Retenue » | historiques CAND-T10, CAND-T11 ; `DateDecisionFinale` ; N-12, N-13 |
| g | Variante : `Recrutement.PartageTransmission` = Destinataire | seul `DestinataireAdmin` reçoit l'accès à l'élément et au dossier |

- **Preuves** : historique complet de la candidature et de l'entretien, courriels N-05 / N-11 / N-13, permissions de l'élément (« Gérer l'accès »).

## S-04 — Formalités : tâches créées ; alternant créé, puis actif, seulement après confirmation

- **Références** : CAND-T13, CAND-T14, `G_INTEGRATION`, ModelesActions FORM-01 à FORM-06, ALT-T01, ALT-T02, PA-04, PA-04b, N-15, N-16, N-17, N-18.
- **Persona** : ADMIN_KARINE ; RD1 (actions RD) ; REF1.
- **Préconditions** : candidature « Retenue » (fin de S-03) avec établissement, pôle et référent pressentis.

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | ADMIN_KARINE passe « Formalités en cours » | actions FORM-01 à FORM-06 créées (une par code, `CodeModeleAction`), échéances calculées, responsables résolus ; dossier `02 — Administration/Candidatures/CAND-…` ; N-15 |
| b | Rejouer l'étape a (repasser le même statut, ou resoumettre l'exécution) | aucune action en double |
| c | Renseigner les dates de démarrage et de fin, passer « Intégrée » alors que des actions bloquantes sont ouvertes | retour « Formalités en cours », historique « Refusée — annulée » citant `G_INTEGRATION` et les actions manquantes ; N-90 ; **aucune** fiche alternant (S-17) |
| d | Terminer chaque action bloquante **avec preuve** (ou « Non applicable » + commentaire, par ADMIN uniquement) | N-17 « formalités complètes » ; aucun changement de statut automatique |
| e | ADMIN_KARINE passe « Intégrée » | fiche `Alternants` « À intégrer » (ALT-T01 par FLUX) avec `CandidatureSource`, dates, pôle, référent principal ; `IdAlternant`, `DateIntegration` ; dossiers `SuiviAlternants/ALT-…` et `_Evaluations`, `Administration/Alternants/ALT-…/Operationnel` ; actions d'accueil ACC-01 à ACC-05 ; école « Établissement d'accueil » si elle était « Prospect » / « Contact établi » ; N-16 |
| f | Le jour de `DateDebut` (ou exécuter PA-04b manuellement) | alternant « Actif » (ALT-T02, Origine Flux), N-18 au référent |

- **Preuves** : liste des actions, historique de la candidature et de l'alternant, journal Info de PA-04.

## S-05 — Une école rattachée à plusieurs alternants sans doublon ; convention avec son propre statut

- **Références** : § 4 (lookup `Etablissement`), CONV-T01 à CONV-T05, `G_PREUVE_SIGNATURE`.
- **Persona** : ECOLES, ADMIN_KARINE ; jeu : ECO-2026-9001 (4 alternants), CONV-2026-9001 / 9002.

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | Ouvrir ECO-2026-9001 puis la vue « Alternants actifs » groupée par établissement | un seul établissement, quatre alternants qui le référencent ; `tests/offline` vérifie l'absence de doublon de nom |
| b | Comparer CONV-2026-9001 (« Signée / active ») et CONV-2026-9002 (« À signer ») | deux conventions du même établissement avec des statuts différents |
| c | ECOLES passe CONV-2026-9002 en « Signée / active » sans preuve | statut rétabli (validation de liste puis `G_PREUVE_SIGNATURE`), N-90 |
| d | Renseigner `DateSignature` + `PreuveSignature` puis « Signée / active » | accepté (CONV-T03) ; le statut de l'établissement n'est pas modifié (convention d'alternance, pas de partenariat) |

## S-06 — Changement de référent ou de sujet : anciennes affectations visibles et datées

- **Références** : P-03, AFF-T02, AFF-T05 (FLUX), `EmpreinteVerrou`, `AffectationRemplacee`, N-91, N-22, H-51 ; jeu : chaîne AFF-2026-9003 → 9004 → 9005 (ALT-2026-9003).
- **Persona** : RD1.

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | Vue « Historique des affectations », groupée par alternant, pour ALT-2026-9003 | trois affectations datées, sans chevauchement ; `MotifFin` « Remplacée par AFF-… » ; référent principal = REF-2026-9002 (affectation active la plus récente) |
| b | RD1 modifie le `Referent` de AFF-2026-9001 (active) | valeur rétablie, `JournalFlux` Avertissement, N-91 « créez une nouvelle affectation » |
| c | RD1 crée une nouvelle affectation pour ALT-2026-9001 (autre référent) avec `AffectationRemplacee` = AFF-2026-9001 et l'active | AFF-2026-9001 « Terminée », `DateFin` = début de la nouvelle − 1 jour, **aucun autre champ modifié** ; référent principal mis à jour et historisé (« Changement de référent principal ») ; N-22 listant les livrables encore ouverts |
| d | Pour un livrable ouvert de l'ancienne affectation, RD1 crée un livrable dans la nouvelle avec `LivrableOrigine`, puis suspend l'ancien (motif « Transféré vers LIV-… ») | décision humaine tracée (modèle : LIV-2026-9015 → LIV-2026-9016) |
| e | Activer une affectation dont l'alternant n'a pas de `CompteM365` | refusée (`G_AFFECTATION_COMPLETE`, v1.3.0) |

- **Destructif** pour le jeu (c, d) : réimporter ensuite.

## S-07 — Livrable retourné en correction puis validé ; versions et commentaires conservés

- **Références** : LIV-T02, LIV-T03 (`G_DOCUMENT`), LIV-T06 (`G_COMMENTAIRE_REVUE`), LIV-T07 (`G_VALIDEUR_LEGITIME`), PA-07, PA-07b, N-25, N-26, N-27 ; colonnes `CommentaireRevue` en ajout seul.
- **Personas** : RD1 (création), ALT1 (propriétaire), REF1 (réviseur).

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | RD1 crée un livrable sur AFF-2026-9001 (propriétaire ALT1) | `Sujet` copié, `Reviseur` = REF1, `EcheanceInitiale` ; ALT1 reçoit CSS sur l'élément |
| b | ALT1 dépose un document dans `04 — Livrables R&D/SUJ-2026-9001` (colonne `Livrable` renseignée) | PA-07b : `LienDocument` renseigné, **pas** de changement de statut |
| c | ALT1 passe « En cours » puis « Soumis à revue » | `DatePremierDepot`, `DateDepot` ; N-25 à REF1 avec liens |
| d | REF1 passe « Corrections demandées » **sans** commentaire | refusé (`G_COMMENTAIRE_REVUE`), N-90 |
| e | REF1 ajoute un commentaire et passe « Corrections demandées » | `NbCorrections` = 1, `DecisionRevue` ; action « Correction livrable » ; N-26 avec le commentaire |
| f | ALT1 dépose une nouvelle version et resoumet ; REF1 valide | « Validé » : `Valideur` = REF1, `DateValidation`, `VersionValidee` ; N-27 ; tentative d'archivage (`G_CAPITALISATION`) ou N-28 listant les manques |
| g | Ouvrir l'historique des versions de l'élément et du document | les deux commentaires et les deux versions du document sont conservés |

## S-08 — Rappel de retard aux seuls acteurs concernés ; éléments suspendus exclus

- **Références** : PA-06, `Delai.RappelLivrableJours`, N-23, N-24, `DernierRappel`, `EnRetard` ; jeu : LIV-2026-9003, 9004, 9014 (en retard), LIV-2026-9008 et 9015 (suspendus), LIV-2026-9010 (échéance J+7).
- **Persona** : IT (exécution manuelle de PA-06), boîtes des propriétaires / réviseurs.

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | Après import (rappels vides), exécuter PA-06 (« Exécuter » dans la solution) | `EnRetard` = Oui et `DernierRappel` renseigné pour 9003, 9004, 9014 ; N-24 envoyé **uniquement** au propriétaire et au réviseur de chacun ; N-23 pour LIV-2026-9010 (J-7) |
| b | Vérifier 9008, 9015 et les livrables validés / archivés | aucun rappel, `EnRetard` = Non |
| c | Exécuter PA-06 une seconde fois le même jour | aucun nouveau courriel (palier déjà envoyé) |
| d | LIV-2026-9014 : retard de plus de `Delai.EscaladeComiteJours` | présent dans la synthèse du comité (PA-11, N-42) |

- **Pester** : `-TagFilter Planifie` après l'étape a.

## S-09 — Power BI cohérent avec SharePoint, sans CV ni commentaire d'entretien pour les non-habilités

- **Références** : § 9.2, § 9.5, § 9.6, P-04, H-16, H-48 ; `tests/e2e/reconciliation/`.
- **Personas** : DIR_RD (PilotageRD), DIRECTION (Direction), ADMIN_KARINE (Administration), REF1 (Referent), ECOLES (RelationEcoles).

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | Valeurs attendues du jeu : `python tests/e2e/reconciliation/reconcilier.py --source testdata/data --date <jour d'import>` | tableau de référence (aussi figé dans `tests/offline/test_reconciliation.py`) |
| b | Export du site : `pwsh ./tests/e2e/reconciliation/Export-HNCSRDDonnees.ps1 -Sortie ./TestResults/export` puis `python tests/e2e/reconciliation/reconcilier.py --source TestResults/export` | mêmes valeurs qu'en a (site contenant uniquement le jeu de test) |
| c | Après actualisation du modèle, relever les cartes du rapport dans `rapport.json` et lancer `reconcilier.py --source TestResults/export --comparer rapport.json` | 0 écart (tolérance 0,001) ; écart possible entre 00:00 et 02:00 (H-48) |
| d | « Afficher en tant que » chaque rôle | Direction : aucune colonne `NomAffichage` ; Administration : seules les candidatures transmises, aucun livrable ; Referent : ses alternants uniquement ; RelationEcoles : aucune candidature ni livrable |
| e | Inspecter le modèle (liste des colonnes de chaque table) | aucune colonne `perso` / `confidentiel` (contrôlé aussi par `tests/offline/test_powerbi_contract.py`) |

## S-10 — Un flux échoue : échec visible, responsable notifié, reprise maîtrisée

- **Références** : § 8.1 (gestion d'erreur, reprise), PA-00C, PA-00E, N-98, N-99 ; jeu : `JournalFlux` « À reprendre » sur CAND-2026-9007.
- **Personas** : IT, DIR_RD (lecture du journal), RD1 (aucun accès au journal).

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | DIR_RD ouvre la vue « Erreurs à reprendre » | l'erreur PA-02 de CAND-2026-9007 apparaît avec `RunUrl` ; RD1 n'a pas accès à la liste |
| b | Provoquer une erreur réelle : révoquer temporairement le droit « Envoyer en tant que » du compte de service sur la boîte R&D (ou rendre la connexion `hncs_outlook` invalide), puis présélectionner une candidature | candidature reste « Présélectionnée » ; `JournalFlux` Erreur « À reprendre » avec `RunUrl` ; N-99 tenté vers le support (s'il échoue faute de connexion courriel, l'élément de journal fait foi) |
| c | Le lendemain 07:30 (ou exécution manuelle de PA-00E) | N-98 au support et à G_PROP listant l'erreur |
| d | Rétablir la cause, « Resoumettre » depuis `RunUrl`, puis `StatutReprise` = Reprise effectuée | transmission effectuée **une seule fois** (pas de doublon de permissions, de dates ni de courriel) |

## S-11 — Candidature incomplète (courriel de plateforme sans identité)

- **Références** : `G_IDENTITE`, PA-01b (domaine de plateforme), CAND-T02 / T03, N-90 ; jeu : CAND-2026-9023.

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | Envoyer à la boîte R&D un courriel d'un expéditeur `…@linkedin.com` (domaine de plateforme, adresse fictive) | `Title` = « À qualifier – {RefMessage} », `Email` vide, canal LinkedIn, statut « Reçue » ; N-01 demande la qualification |
| b | RD1 attribue un responsable et passe « En cours d'analyse » sans qualifier l'identité | statut rétabli, historique refusé citant `G_IDENTITE`, N-90 |
| c | RD1 renseigne nom et e-mail du candidat puis rejoue l'étape b | accepté ; contrôle de doublon refait sur l'e-mail |

## S-12 — Échéance de livrable déplacée

- **Références** : `EcheanceInitiale`, `EnRetard`, PA-06, champ protégé `Echeance` (v1.3.0) ; jeu : LIV-2026-9014 (échéance initiale J-20, échéance J-12).

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | ALT5 (propriétaire) tente de reporter `Echeance` de LIV-2026-9014 | valeur rétablie (P-09), N-92 |
| b | REF2 (réviseur légitime) ou RD1 reporte l'échéance à J+10 | accepté ; `EcheanceInitiale` inchangée (J-20) |
| c | Exécuter PA-06 | `EnRetard` = Non ; rappels recalculés sur la nouvelle échéance (N-23 à J-7) |

## S-13 — Un alternant se désigne réviseur de son propre livrable et tente de le valider

- **Références** : `G_VALIDEUR_LEGITIME`, P-09, N-92, N-90.
- **Personas** : ALT1, REF1.

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | ALT1 remplace le `Reviseur` de son livrable par lui-même | valeur rétablie, N-92 |
| b | ALT1 passe son livrable soumis à « Validé » | statut rétabli, historique « Refusée — annulée » (rôle / valideur illégitime), N-90 |
| c | REF1 valide | accepté ; `Valideur` = REF1 (jamais le propriétaire ; contrôlé sur le jeu par `tests/offline`) |

## S-14 — Signature d'une convention de partenariat sans décision de partenariat

- **Références** : CONV-T03, `G_DECISION_PARTENARIAT`, H-37 ; jeu : CONV-2026-9004 (« À examiner »), CONV-2026-9003 (signée avec décision).
- **Personas** : ECOLES, DIR_RD.

| # | Étape | Résultat attendu |
| --- | --- | --- |
| a | ECOLES crée une convention de partenariat, renseigne signature et preuve, passe « Signée / active » | statut rétabli, refus citant `G_DECISION_PARTENARIAT`, N-90 |
| b | DIR_RD renseigne `DecisionPartenariat` = Partenariat retenu | `DecideurPartenariat`, `DateDecisionPartenariat`, `EmpreinteDecision` ; N-39 |
| c | ECOLES repasse « Signée / active » | accepté ; établissement « Partenaire actif » (constat de signature) |

## S-15 — Droits d'accès persona par persona

- **Références** : § 7.2 à § 7.5, H-14, H-18, H-28, H-29, H-45, H-54.
- **Automatisation** : `Invoke-Pester ./tests/e2e/Access.Tests.ps1 -Output Detailed` (une authentification par persona).
- **Principe** : pour chaque persona × objet de la matrice (`model.generated.json`, clé `matrix`), le niveau attendu est le
  maximum des niveaux de ses groupes ; le test lit les permissions effectives (`EffectiveBasePermissions`) au niveau
  liste puis, pour `IL(x)` / `R+IL(x)`, au niveau de chaque élément du jeu de test (règles § 7.4).

| Persona | Points de contrôle manuels complémentaires |
| --- | --- |
| RD1 / RD2 (équipe R&D) | candidatures et CV : CSS ; entretiens : aucun accès sauf ceux dont il est participant ; journal des flux : aucun accès |
| ADMIN_KARINE (administration) | candidatures transmises seulement (CAND-2026-9008 visible, 9003 invisible) ; « 02 — Administration » : CSS |
| REF1 / REF2 (référents) | fiches alternants de leurs affectations seulement (IL(R)) ; comptes rendus dont ils sont valideurs ; actions et bilans dont ils sont responsables |
| ALT1 … ALT5 (alternants) | leurs affectations (R), livrables et comptes rendus (CSS) ; aucun autre alternant ; `_Evaluations` invisible |
| ALT_ANCIEN (accès retirés) | aucun accès, y compris à la page d'accueil |
| DIRECTION (Direction Générale) | aucune liste nominative (Candidatures, Entretiens, Alternants, Livrables, Établissements, Bilans) ; sujets : CSS (v1.3.0) ; « 04 — Livrables R&D » : lecture (H-54) |
| ECOLES (relation écoles) | établissements, conventions, échanges : CSS ; bilans : lecture |
| IT (propriétaires) | contrôle total partout |

- **Preuves** : sortie Pester, captures « Vérifier les autorisations » pour un échantillon d'éléments.

---

## Scénarios complémentaires

### S-16 — Transition interdite annulée et historisée

Persona RD1 ; candidature « Reçue » (S-01 ou CAND-2026-9001). RD1 passe directement « Intégrée » (avec des dates
valides pour franchir la validation de liste). Attendu : statut rétabli à « Reçue » en quelques secondes (H-17),
historique « Refusée — annulée » sans code de transition (« Transition non autorisée »), N-90 à RD1, aucun effet métier.
Le jeu contient déjà ce cas (CAND-2026-9001) pour la mesure « Transitions refusées ».

### S-17 — Tentative de passer « Intégrée » sans formalités

Persona ADMIN_KARINE ; jeu : CAND-2026-9013 (FORM-03 « En cours », FORM-04 « Bloquée », FORM-05 « À faire »).
Renseigner les dates, passer « Intégrée ». Attendu : retour « Formalités en cours », refus citant `G_INTEGRATION`
et les actions manquantes, N-90, aucune fiche alternant. Rejouable (l'élément revient à son état).

### S-18 — Idempotence

1. Exécuter deux fois `Import-TestData.ps1` : le second bilan ne contient que des « MisAJour », aucun doublon
   d'`IdHNCS` (`Invoke-Pester … -TagFilter Import`, et `Test-HNCSRDDeploiement.ps1` contrôle les doublons).
2. Resoumettre une exécution réussie de PA-02 (transmission) et de PA-04 (formalités) depuis l'historique des
   exécutions : aucune permission, date, action ni notification en double.
3. Repasser un statut déjà atteint : historique éventuel, mais aucun effet dupliqué.

### S-19 — Décision de partenariat refusée à un non-habilité

Persona ECOLES ; CONV-2026-9004. Modifier `DecisionPartenariat` en « Partenariat retenu ». Attendu : valeur rétablie
à « À examiner » (`EmpreinteDecision`), N-90 ; aucune notification N-39. Puis DIR_RD fait la même modification :
acceptée, tracée.

### S-20 — Compte rendu non remis

Jeu : CR-2026-9009 (« Attendu », échéance J-7, au-delà de `CR.DelaiNonRemisJours`). Exécuter PA-08b. Attendu :
« Non remis » (CR-T04, Origine Flux), N-31 au référent (REF2), rappel N-30 non renvoyé ; la mesure « Comptes rendus
manquants » reste inchangée (4). Puis ALT2 rédige et remet le compte rendu (CR-T02, CR-T03 avec `G_CR_COMPLET`).

### S-21 — Fin d'alternance

Persona RD1 ; jeu : ALT-2026-9007 (« Fin planifiée », checklist CLO-01 à CLO-07, bilan BIL-2026-9002).

1. Renseigner `DateFinReelle` et passer « Terminé » : AFF-2026-9010 « Terminée » au `DateFinReelle` (AFF-T05 par FLUX),
   N-22 et N-37 ; aucun accès retiré automatiquement (H-18).
2. Passer « Clôturé » : refusé tant que les actions bloquantes et le bilan ne sont pas faits (`G_CLOTURE_ALTERNANCE`).
3. Réaliser le bilan (« Réalisé » avec recommandation) : action PART-01 créée ; établissement « Partenariat à
   évaluer » si recommandation favorable et établissement non encore partenaire ; N-38.
4. Terminer CLO-06 (retrait des accès, action humaine) puis clôturer : accepté.

Variante : prolongation — passer « Actif » depuis « Fin planifiée » après report de `DateFin` (ALT-T08, `G_DATE_FIN_REPORTEE`).

**Destructif** : réimporter le jeu ensuite.

### S-22 — Arbitrage du portefeuille de sujets

Personas RD1, REF1, DIR_RD, DIRECTION. Créer un sujet (« Proposé »), le passer « À arbitrer » (N-47 à G_DRD).
REF1 tente « Priorisé » : refusé. DIR_RD passe « Abandonné » sans motif : refusé (`G_MOTIF_DECISION`) ; avec motif :
accepté, N-47. DIRECTION peut prioriser (CSS sur SujetsRD, v1.3.0). Jeu : SUJ-2026-9008 contient un refus historisé.

### S-23 — Champs protégés (P-09)

| Champ | Tentative non habilitée | Attendu |
| --- | --- | --- |
| `Alternants.ReferentPrincipal` | RD1 le modifie à la main | rétabli depuis `EmpreinteReferent`, N-91 |
| `Livrables.Reviseur`, `Echeance`, `DoD1..5` | le propriétaire alternant les modifie | rétablis depuis `EmpreinteRevue`, N-92 |
| `ComptesRendus.Echeance`, `PeriodeDebut/Fin`, `Valideur` | l'alternant les modifie | rétablis, N-92 |
| `ActionsIntegration.Bloquante` (formalités) | RD1 la décoche | rétablie depuis `EmpreinteAction`, N-92 |
| `ActionsIntegration` bloquante → « Non applicable » | le responsable non ADMIN | rétabli (`G_ACTION_FORMALITE`, v1.3.0) |
| `Conventions.DecisionPartenariat` | ECOLES | rétablie (S-19) |

### S-24 — Permissions des dossiers des bibliothèques

Après les parcours S-01 à S-07 (flux actifs) : `01 — Recrutement/AAAA/CAND-…` (G_PROP, G_DRD, G_RD ; + G_ADM après
transmission) ; `02 — Administration/Alternants/ALT-…/Operationnel` (G_RD : lecture) ; `05 — Suivi des alternants/ALT-…`
(alternant et référents CSS) et `_Evaluations` (sans l'alternant) ; `04 — Livrables R&D/SUJ-…` (alternant CSS après
activation de l'affectation). Vérifier avec « Gérer l'accès » sur chaque dossier et en ouvrant les URL avec ALT1, REF1, ADMIN_KARINE.
Les permissions de dossiers ne sont pas émulées par `Import-TestData.ps1 -PermissionsElement`.

### S-25 — Lot 1 sans automatisation : procédure manuelle de partage (H-50)

Site au lot 1, **sans** flux (hors PA-00C / PA-00D). Dérouler la procédure manuelle provisoire du lot 1 décrite dans `docs/exploitation.md` (H-50) :
transmission manuelle d'une candidature à l'administration par G_PROP, création manuelle des dossiers de suivi.
Attendu : l'administration accède à la seule candidature partagée ; aucune autre ; l'historique est porté par le
versioning (pas de `HistoriqueStatuts` sans flux). Les contrôles P-01 à P-03 et P-09 ne sont **pas** effectifs : le
consigner dans le procès-verbal de recette du lot 1.

### S-26 — Refus d'une création (§ 6.1-3 bis)

Persona DIR_RD, `Fonction.RepriseExistantActive` = Non. Créer une fiche `Alternants` sans candidature source.
Attendu : l'élément est envoyé à la **corbeille du site** par le compte de service (récupérable), historique
« Refusée — annulée » (∅ → « À intégrer »), N-90. Avec le paramètre à Oui : création acceptée (reprise de l'existant, H-12).
