# Guide utilisateur — Direction (Direction Générale et Direction R&D)

> Public : **Direction Générale** (groupe SharePoint `HNCS-RD-Direction`) et **Direction R&D** (groupe
> `HNCS-RD-DirectionRD`). Les deux rôles sont distincts : chaque section les traite séparément. La Direction R&D, souvent
> membre aussi de l'équipe R&D, lit également le guide [Équipe R&D](equipe-rd.md). Règles communes : voir
> l'[index des guides](README.md#repères-communs-à-tous-les-guides). Référence : `spec.md` 1.3.0.

## Les deux rôles en bref

| | Direction Générale | Direction R&D |
| --- | --- | --- |
| Groupe SharePoint | `HNCS-RD-Direction` (rôle `DIRECTION`) | `HNCS-RD-DirectionRD` (rôle `DIRECTION_RD`) |
| Posture (RACI § 7.6) | Lecture de pilotage, validations de son niveau ; « A » de la cible et du budget, « A* » de la sélection et des communications (à confirmer, H-06, H-11) | Pilotage opérationnel et arbitrages R&D ; « A » du recrutement côté R&D, des affectations, du suivi école ; « A/R » du reporting de gouvernance |
| Données nominatives | **Aucune** dans SharePoint (volontairement) | Accès aux candidatures et aux CV (pas aux entretiens), aux fiches alternants, aux évaluations en lecture |
| Power BI | Rôle `Direction` : pages 1, 3, 4, 5, 6 | Rôle `PilotageRD` : les 8 pages, sans restriction de lignes |
| Décisions propres | Validation des communications externes ; décision de partenariat ou de sponsoring ; arbitrage des sujets | Les mêmes, plus réouverture d'une candidature, reprise de l'existant |
| Synthèses | Point Direction mensuel et revue trimestrielle, **transmis par la Direction R&D** | Comité R&D hebdomadaire (N-42) ; N-43 à relire et transmettre |

## 1. Votre rôle dans le processus

### Direction Générale

- Vous **pilotez** à partir d'indicateurs agrégés (Power BI, synthèses mensuelles et trimestrielles relayées par la Direction
  R&D).
- Vous **validez les communications externes** de la R&D (avec la Direction R&D, H-11).
- Vous pouvez prendre la **décision de partenariat ou de sponsoring** avec une école (avec la Direction R&D, H-37).
- Vous pouvez **arbitrer** un sujet R&D (GO / NO-GO) avec la Direction R&D (SUJ-T03, SUJ-T06, SUJ-T07).
- Vous arbitrez certaines **hypothèses de cadrage** (section 4).

### Direction R&D

- Vous **arbitrez** le portefeuille R&D (priorisation, GO / NO-GO des sujets) en Comité R&D et le tracez dans SharePoint.
- Vous recevez les **escalades** : affectations à risque ou bloquées, blocages signalés dans les comptes rendus, livrables en
  retard au-delà de 7 jours, sujets bloqués ou à arbitrer.
- Vous êtes seule habilitée à **rouvrir** une candidature « Non retenue » ou « Clôturée » (H-07) et à créer une fiche
  alternant sans candidature pour la **reprise de l'existant** (H-12).
- Vous **validez les communications externes** et prenez les **décisions de partenariat ou de sponsoring**.
- Vous **publiez le reporting** de gouvernance : vous relisez la synthèse du Point Direction et de la revue trimestrielle
  avant de la transmettre à la Direction Générale.
- Vous administrez les **paramètres métier** et approuvez les **modèles** R&D.

## 2. Ce que vous voyez et ne voyez pas

### Direction Générale

| Accès | Listes et bibliothèques |
| --- | --- |
| Modification | Communications R&D, Conventions et partenariats, Sujets R&D |
| Lecture seule | Offres, Pôles R&D, Référents, Registre des modèles R&D, Domaines cibles, Mobilisations commerciales, Transitions de statuts, Synchronisation GitLab, « 03 — Modèles R&D », « 04 — Livrables R&D » |
| Aucun accès | Candidatures, « 01 — Recrutement » (CV), Entretiens, Écoles et établissements, Alternants, Affectations, Livrables, Comptes rendus de suivi, Actions d'intégration et checklists, Bilans d'alternance, Échanges avec les écoles, Ressources techniques, Paramètres, Historique des statuts, Journal des flux, « 02 — Administration », « 05 — Suivi des alternants », « 06 — Écoles et partenariats » |

**Absence volontaire de données nominatives** (P-04, § 7.5) : la Direction Générale n'accède à aucune liste nominative dans
SharePoint (candidatures, entretiens, alternants, livrables, établissements, bilans). Son accès aux indicateurs passe par
Power BI, qui n'importe aucune donnée personnelle ou confidentielle et n'affiche aucun nom ; les synthèses qui lui sont
transmises ne contiennent que des identifiants, des statuts et des agrégats. Vous voyez donc **des nombres** (candidatures
reçues, alternants actifs…), jamais un CV, un avis d'analyse ni un commentaire d'entretien. La lecture de « 04 — Livrables R&D »
est volontaire : ce sont des travaux, sans donnée personnelle, dont les colonnes de recherche affichent des identifiants (H-54).

### Direction R&D

| Accès | Listes et bibliothèques |
| --- | --- |
| Modification | Offres, Candidatures, « 01 — Recrutement », Écoles et établissements, Conventions et partenariats, Alternants, Pôles R&D, Référents, Sujets R&D, Affectations, Livrables (y compris les champs protégés), Comptes rendus de suivi, Registre des modèles R&D, Actions d'intégration et checklists, Modèles de checklists, Bilans d'alternance, Communications R&D, Domaines cibles, Ressources techniques, Mobilisations commerciales, Paramètres, « 03 — Modèles R&D », « 04 — Livrables R&D », « 06 — Écoles et partenariats » |
| Lecture seule | Échanges avec les écoles, Transitions de statuts, Historique des statuts, Journal des flux, Synchronisation GitLab, « 05 — Suivi des alternants » (y compris les sous-dossiers `_Evaluations`) |
| Aucun accès | Entretiens, « 02 — Administration » |

Les commentaires d'entretien et les pièces administratives restent à l'administration (H-28).

## 3. Vos tâches pas à pas

### 3.1 Lire la vue exécutive Power BI (les deux rôles)

1. Ouvrez le rapport « HNCS-RD » dans l'espace « HNCS-R&D Pilotage » (lien aussi présent dans les synthèses,
   `Lien.RapportPowerBI`).
2. Page **1. Vue exécutive** : choisissez l'année ou le trimestre (filtre de page) ; vérifiez la **date de dernière
   actualisation** affichée.
3. Lisez les cartes, les jauges « indicateur / cible », la répartition des candidatures par statut (agrégée) et
   l'histogramme des livrables par statut.

| Indicateur | Définition (spec § 9.5) | Objectif indicatif à un an |
| --- | --- | --- |
| Alternants actifs | Alternants « Actif » ou « Fin planifiée » (les suspendus sont exclus, H-41) | — |
| Alternants accueillis | Alternants passés par l'accueil (Actif, Suspendu, Fin planifiée, Terminé, Clôturé) | 3 |
| Candidatures reçues | Nombre de candidatures enregistrées | — |
| Sujets actifs | Sujets « Priorisé », « En cours » ou « Bloqué » | — |
| Livrables validés | Livrables « Validé » ou « Archivé / clôturé » | — |
| Livrables en retard | Livrables non soumis dont l'échéance est passée | — |
| POC réalisés | POC **archivés** avec les 5 critères de la Definition of Done | 5 |
| Plans de stratégie formalisés | Plans **archivés** avec les 5 critères | 4 |
| Communications publiées | Communications **externes** au statut « Publiée » | 30 |
| Partenariats académiques actifs | Conventions « Convention de partenariat » ou « Sponsoring » au statut « Signée / active » (H-25) | 3 |
| Mobilisations commerciales | Utilisations d'un livrable en rendez-vous client, appel d'offres, avant-vente, démonstration | 8 |
| Couverture des domaines cibles | Part des domaines cibles ayant au moins un sujet avec un livrable validé | 100 % |

À savoir pour bien lire :

- les **objectifs sont indicatifs** (cadrage § 2.4, H-20) : ce ne sont pas des engagements contractuels ;
- un POC validé mais pas encore archivé (capitalisation incomplète) **ne compte pas** encore comme « POC réalisé » ;
- les données sont actualisées **chaque jour à 06:00** : ce qui a été saisi dans la journée apparaît le lendemain ; entre minuit
  et 2 heures, « aujourd'hui » peut être décalé d'un jour (H-48).

### 3.2 Valider ou refuser une communication externe (les deux rôles)

1. **N-44 « Communication à valider »** est envoyé à l'« Approbateur proposé » s'il est membre de la Direction R&D ou de la
   Direction, sinon à la Direction R&D. Liste **Communications R&D**, vue **« À valider »** (statut « En revue »).
2. Vérifiez le contenu, le « Canal », la « Date prévue » et les **« Autorisations des tiers »**.
3. Décidez :
   - **« Validée »** (`COM-T05`) : possible seulement si « Autorisations des tiers » vaut « Non requise » ou « Obtenue »
     (`G_AUTORISATIONS`, aussi vérifié par la liste) ; la date de validation est tracée, l'« Approbateur proposé » est
     renseigné à votre nom s'il était vide, l'auteur reçoit **N-45** ;
   - **« Suspendue / refusée »** (`COM-T08`) : indiquez la raison dans « Commentaire » ; l'auteur reçoit N-45 ;
   - renvoyer « En rédaction » (`COM-T03`) pour des retouches : possible pour la Direction R&D et pour l'approbateur proposé.
     L'auteur reçoit **N-45**.

La suite (programmation, publication avec « Date de publication » et « URL de publication ») est faite par l'auteur ou la R&D.

### 3.3 Décider d'un partenariat ou d'un sponsoring (les deux rôles)

Le signal vient en général d'un bilan d'alternance : à chaque bilan « Réalisé », une action d'évaluation **PART-01** est créée
pour le responsable HNCS de l'école (note d'évaluation dans « 06 — Écoles et partenariats ») ; si la recommandation est
« Recommandé » ou « À étudier », l'école passe en **« Partenariat à évaluer »** et **N-38** est envoyé à la Direction R&D et à
la relation écoles. **Ce signal n'est pas une décision** (H-39).

1. Repérez les écoles concernées : Power BI page 5 ; pour la Direction R&D, liste « Écoles et établissements », vue
   « Partenariats à évaluer ».
2. La fiche de convention correspondante est créée par l'administration, la relation écoles, l'équipe R&D ou la Direction R&D
   (`CONV-T01`),
   avec le type « Convention de partenariat » ou « Sponsoring ».
3. Sur cette convention, renseignez **« Décision de partenariat »** : À examiner, Partenariat retenu, Sponsoring retenu, Pas
   de partenariat, Décision reportée.
4. Le système (PA-10) trace automatiquement **« Décideur »** (vous) et **« Date de décision »**, et envoie **N-39** à la
   relation écoles, à l'administration et à la Direction R&D. Ce champ est protégé : toute modification par une autre personne
   est rétablie et signalée (N-92).
5. La décision doit précéder la signature : une convention de partenariat ou de sponsoring ne peut passer à « Signée /
   active » que si la décision vaut « Partenariat retenu » ou « Sponsoring retenu » (`G_DECISION_PARTENARIAT`). L'école ne
   devient « Partenaire actif » qu'à la **signature**, avec preuve, constatée par l'administration ou la relation écoles.

Vue de suivi : « Conventions et partenariats », vue **« Décisions de partenariat »**. Les critères de décision restent à
définir (H-37).

### 3.4 Arbitrer un sujet R&D

L'arbitrage du portefeuille est une décision humaine réservée à la Direction R&D et à la Direction (PA-14) :

| Décision | Statut à poser | Depuis | Condition |
| --- | --- | --- | --- |
| GO | « Priorisé » (`SUJ-T03`) | Proposé, À arbitrer, Suspendu | — |
| NO-GO provisoire (report, reformulation) | « Suspendu » (`SUJ-T06`) | Proposé, À arbitrer, Priorisé, En cours, Bloqué | « Motif de décision » obligatoire (`G_MOTIF_DECISION`) |
| NO-GO définitif | « Abandonné » (`SUJ-T07`) | Tout statut sauf Terminé et Abandonné | « Motif de décision » obligatoire |
| Réexamen d'un sujet suspendu | « À arbitrer » (`SUJ-T09`) | Suspendu | — |

1. Liste **Sujets R&D**, vue **« À arbitrer »** (Proposé, À arbitrer, Bloqué) ; Power BI page 7. **N-47** prévient la Direction
   R&D quand un sujet passe « À arbitrer » ou « Bloqué ».
2. Renseignez si besoin « Motif de décision », puis posez le statut. Le référent du sujet et l'équipe R&D reçoivent **N-47**
   avec la décision et le motif.

### 3.5 Exploiter les synthèses de gouvernance

- **Direction R&D** : N-42 (Comité R&D, chaque lundi) ; N-43 (Point Direction, revue trimestrielle) **à relire puis transmettre
  à la Direction Générale** (§ 8.4 PA-11, RACI « A/R » de la publication du reporting).
- **Direction Générale** : vous recevez la synthèse N-43 par la Direction R&D (agrégats et points d'arbitrage, sans nom de
  personne). Utilisez-la avec la vue exécutive (3.1).

### 3.6 Tâches propres à la Direction R&D

#### Traiter les escalades

| Signal | Où agir |
| --- | --- |
| N-21 : affectation « À risque » ou « Bloquée » | Liste Affectations ; voir avec le référent ; si non résolu, Comité R&D puis Point Direction (§ 7.7) |
| N-33 : blocage signalé dans un compte rendu | Comptes rendus de suivi, vue « Blocages signalés » ; Point Direction si un arbitrage est requis |
| N-47 : sujet « Bloqué » ou « À arbitrer » | Sujets R&D, vue « À arbitrer » (3.4) |
| Livrables en retard de plus de 7 jours (`Delai.EscaladeComiteJours`) | Synthèse du Comité R&D ; Livrables, vue « En retard » |

#### Rouvrir une candidature

Sur une candidature « Non retenue » ou « Clôturée », posez **« À analyser »** (`CAND-T16`). La date de clôture est vidée et le
responsable d'analyse reçoit N-03. Vous seule pouvez le faire (H-07).

#### Reprendre un alternant déjà présent

Pour un alternant arrivé avant la mise en service, créez sa fiche dans **Alternants** sans « Candidature d'origine »
(`ALT-T01`, H-12) : « Nom et prénom », « Date de début », « Date de fin prévue », « Établissement », « Pôle ». Cette création
n'est acceptée que si le paramètre `Fonction.RepriseExistantActive` vaut Oui (`G_SOURCE_ALTERNANT`) ; sinon la fiche est
placée dans la corbeille du site et vous recevez N-90. Activez ce paramètre le temps de la reprise.

#### Revoir un livrable

Vous pouvez être désignée réviseur d'un livrable et le valider (`G_VALIDEUR_LEGITIME` admet un membre de la Direction R&D
désigné réviseur). Avec l'équipe R&D, vous êtes seule à pouvoir modifier les champs protégés d'un livrable (propriétaire,
réviseur, affectation…).

#### Approuver les modèles R&D

Liste **Registre des modèles R&D** : un modèle passe à **« Approuvé »** avec « Date d'approbation » et « Date d'entrée en
vigueur » (exigées par la liste). Seuls les modèles approuvés, marqués « Livrable proposé automatiquement » et applicables au
type de sujet génèrent des livrables à l'activation d'une affectation. Chaque propriétaire de modèle reçoit le droit de
modifier son modèle (PA-00F) ; les modèles initiaux vous sont attribués au déploiement, à réattribuer.

#### Ajuster les paramètres métier

Liste **Paramètres** : délais de relance et de rappel, cadence des comptes rendus (`CR.CadenceGlobale`), anticipation de fin
d'alternance, alerte d'expiration des conventions, portée du partage à la transmission (`Recrutement.PartageTransmission`,
H-45)… Une modification prend effet à la prochaine exécution des flux, sans développement. N'activez pas
`Fonction.AccuseReceptionActif` ni `Fonction.InformationCandidatAuto` tant que les textes au candidat et l'information RGPD ne
sont pas validés (H-09) ; laissez vide `Conservation.CandidatureNonRetenueMois` tant que la durée n'est pas validée (H-10).

#### Superviser

« Historique des statuts », vue « Transitions refusées » ; « Journal des flux », vue « Erreurs à reprendre » (la reprise est
faite par le support) ; à partir du lot 5, **N-46** liste les candidatures arrivées en fin de conservation, pour traitement
manuel (aucune suppression automatique). Rappelez aux équipes qu'aucun document métier ne doit être déposé dans la
bibliothèque « Documents » par défaut du site (spec § 7.2).

## 4. Vos décisions humaines

| Décision | Direction Générale | Direction R&D | Trace |
| --- | --- | --- | --- |
| Validation d'une communication externe (`COM-T05`) | Oui | Oui | « Date de validation », « Approbateur proposé », historique |
| Refus ou suspension d'une communication (`COM-T08`) | Oui | Oui | Historique, commentaire |
| Décision de partenariat ou de sponsoring | Oui | Oui | « Décideur », « Date de décision » (PA-10), N-39 |
| Arbitrage d'un sujet (`SUJ-T03`, `SUJ-T06`, `SUJ-T07`, `SUJ-T09`) | Oui | Oui | Statut, « Motif de décision », historique, N-47 |
| Réouverture d'une candidature (`CAND-T16`) | Non | Oui | Historique |
| Reprise d'un alternant existant (`ALT-T01`) | Non | Oui | Historique |

Hypothèses de cadrage à confirmer (spec § 13) — ce qui est implémenté en attendant :

| Arbitre | Hypothèses |
| --- | --- |
| Direction Générale | H-05 (Karine et l'équipe administrative = rôle Administration), H-06 (décision finale saisie par l'administration avec « Décideur final »), H-11 (validation des communications par Direction R&D ou Direction), H-20 (objectifs indicatifs), H-25 (définition d'un partenariat actif), H-27 (aucune exception au parcours de recrutement), H-32 (acteurs support hors outil), H-33 (budget et licences hors outil), H-34 (trajectoire M0–M12 non modélisée), H-37 (décision de partenariat), H-54 (lecture de « 04 — Livrables R&D » par la Direction) |
| Direction R&D | H-01 (numérotation des flux), H-02 et H-03 (statuts), H-07 (réouverture), H-08 (cadence quinzaine), H-09 (information du candidat), H-12 (reprise de l'existant), H-17 (contrôle a posteriori), H-19 (pas de Power BI pour les alternants), H-22 à H-24 (délais, checklists, domaines cibles), H-26 (GO/NO-GO), H-28 (entretiens invisibles pour la R&D), H-36 (critères par type de livrable), H-39 (statuts d'école dérivés), H-40 (confirmation d'intégration par l'administration), H-41 (calcul des indicateurs), H-42 (affectations concomitantes), H-43 (composition de la relation écoles), H-46 (propriétaires des flux), H-49 (création des livrables), H-51 (livrables ouverts lors d'un remplacement), H-52 (publics Power BI), H-53 (composition du Comité R&D) |

## 5. Notifications que vous recevez

### Direction Générale

| Code | Quand | Que faire |
| --- | --- | --- |
| N-43 (relayée par la Direction R&D) | Point Direction (mensuel) et revue trimestrielle | Lire la synthèse, ouvrir la vue exécutive |
| N-44 | Communication à valider (si vous êtes l'approbateur proposé) | Valider ou refuser (3.2) |
| N-45 | Décision sur une communication dont vous êtes l'auteur | Prendre note |
| N-90 / N-92 | Changement de statut ou de champ protégé refusé | Lire le motif |

### Direction R&D

| Code | Quand | Que faire |
| --- | --- | --- |
| N-42 | Synthèse du Comité R&D (chaque lundi) | Préparer le comité |
| N-43 | Point Direction et revue trimestrielle | Relire, compléter les points d'arbitrage, transmettre à la Direction Générale |
| N-21 | Affectation « À risque » ou « Bloquée » | Traiter l'escalade |
| N-33 | Blocage signalé dans un compte rendu | Traiter l'escalade |
| N-47 | Sujet « À arbitrer » ou « Bloqué » | Arbitrer (3.4) |
| N-38 | Bilan : partenariat à évaluer | Organiser l'évaluation, puis décider (3.3) |
| N-39 | Décision de partenariat enregistrée | Vérifier |
| N-44 | Communication à valider | Valider ou refuser |
| N-46 | Candidatures en fin de conservation (lot 5, si activé) | Traitement manuel |
| N-90 / N-91 / N-92 | Changement refusé, modification annulée | Lire le motif |

Si vous êtes aussi membre de l'équipe R&D, vous recevez en plus les notifications du guide [Équipe R&D](equipe-rd.md).

## 6. Vos vues Power BI

| Page | Direction Générale (rôle `Direction`) | Direction R&D (rôle `PilotageRD`) |
| --- | --- | --- |
| 1. Vue exécutive | Oui | Oui |
| 2. Recrutement | Non (hors audience) | Oui |
| 3. Effectifs et encadrement | Oui | Oui |
| 4. Projets et livrables | Oui | Oui |
| 5. Établissements et partenariats | Oui | Oui |
| 6. Communications et valorisation | Oui | Oui |
| 7. Comité R&D | Non (hors audience) | Oui |
| 8. Qualité des données | Non (hors audience) | Oui |

Les pages sont restreintes par les **audiences de l'application Power BI** (la sécurité au niveau des lignes et des objets
protège les données, pas les pages, § 9.7). Sur la page 4, les liens vers les documents des livrables vous sont visibles (H-54).
Aucun visuel n'affiche de nom de personne, quel que soit le rôle : les tableaux montrent des identifiants (`ALT-…`, `AFF-…`).
Pour le rôle `Direction`, la colonne des noms d'alternants est en outre inaccessible (sécurité au niveau objet). Une personne
ne relève que d'un seul rôle Power BI (§ 9.6) : un membre de la Direction R&D qui siège aussi à la Direction Générale doit être
rattaché à l'un ou l'autre.

## 7. Rituels de gouvernance

| Rituel | Fréquence | Synthèse automatique (PA-11) | Circuit |
| --- | --- | --- | --- |
| Comité R&D (Direction R&D, équipe R&D, référents, H-53) | Hebdomadaire, lundi 08:00 (`Gouvernance.ComiteJourHeure`) | N-42 : livrables en retard escaladés, échéances à 14 jours, comptes rendus « Non remis », blocages signalés, affectations « À risque » / « Bloquée », sujets « Bloqué » / « À arbitrer », conventions « À renouveler », écoles « Partenariat à évaluer », communications « En revue », candidatures en attente en nombre par statut, lien vers Power BI | Direction R&D ; publiée dans le canal Teams « Comité R&D », dont les membres du comité font partie |
| Point Direction | Mensuel, 1er lundi à 08:00 | N-43 : version agrégée, sans nom de personne, avec les points d'arbitrage | Envoyée à la Direction R&D, qui la relit et la transmet à la Direction Générale |
| Revue de gouvernance | Trimestrielle, 1er lundi du trimestre | N-43 : version agrégée | Même circuit |

Supports : page Power BI 7 « Comité R&D » pour le comité ; page 1 « Vue exécutive » pour le Point Direction et la revue
trimestrielle. Le Point Direction est le dernier niveau d'escalade (§ 7.7) pour les blocages et les affectations à risque non
résolus. Les décisions prises en séance (arbitrage d'un sujet, validation d'une communication, décision de partenariat) se
saisissent ensuite dans SharePoint pour être tracées.

## 8. FAQ

### Pourquoi la Direction Générale ne voit-elle aucun candidat ni aucun alternant nommé ?

C'est voulu (P-04) : la Direction n'a accès à aucune liste nominative dans SharePoint, et Power BI n'affiche aucun nom. Vous
disposez des volumes, des délais et des indicateurs agrégés.

### Pourquoi n'ai-je pas reçu directement la synthèse du Point Direction ?

Depuis la spec 1.1.0, la synthèse est envoyée à la Direction R&D, qui la relit et vous la transmet (RACI : Direction R&D
« A/R » du reporting).

### Les chiffres de Power BI ne correspondent pas à ce que je vois dans SharePoint ce matin : est-ce une erreur ?

Le rapport est actualisé une fois par jour à 06:00 (date affichée sur la vue exécutive) ; une saisie faite depuis apparaîtra
demain.

### Les objectifs affichés sont-ils des engagements ?

Non, ce sont des cibles indicatives à un an issues du cadrage (H-20), modifiables sur décision de la Direction Générale.

### Puis-je valider une communication dont les autorisations des tiers sont « Demandée » ?

Non : la validation exige « Non requise » ou « Obtenue ». Attendez l'autorisation, ou refusez avec un commentaire.

### Une école est « Partenariat à évaluer » : est-ce un partenariat ?

Non, c'est un signal de revue issu d'un bilan. Seule une décision tracée dans « Conventions et partenariats », puis une
convention signée avec preuve, font d'une école un partenaire.

### Peut-on signer une convention de partenariat avant notre décision ?

Non : la signature est refusée tant que « Décision de partenariat » ne vaut pas « Partenariat retenu » ou « Sponsoring retenu »
(`G_DECISION_PARTENARIAT`).

### (Direction R&D) Comment rouvrir une candidature écartée par erreur ?

Posez « À analyser » sur la candidature (`CAND-T16`) : le responsable d'analyse est prévenu (N-03).

### (Direction R&D) Comment allonger le délai de relance des candidatures ?

Modifiez la valeur de `Delai.RelanceAnalyseJours` dans la liste Paramètres (5 jours au départ, H-22).

### (Direction R&D) Pourquoi aucun livrable n'est proposé automatiquement ?

Les modèles du registre sont encore en « Brouillon ». Approuvez-les (avec dates d'approbation et d'entrée en vigueur).
