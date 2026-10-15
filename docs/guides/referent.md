# Guide utilisateur — Référent

> Public : experts référents des pôles (groupe SharePoint `HNCS-RD-Referents`). Règles communes (statuts refusés, champs
> protégés, validations, notifications) : voir l'[index des guides](README.md#repères-communs-à-tous-les-guides). Référence :
> `spec.md` 1.3.0.

## 1. Votre rôle dans le processus

Le référent encadre un ou plusieurs alternants sur un sujet R&D. Au RACI (§ 7.6), vous êtes « A/R » de la production et de la
validation des livrables. Concrètement :

- vous êtes désigné sur une **affectation** (alternant + sujet + référent) par l'équipe R&D ;
- vous êtes le **réviseur** des livrables de cette affectation : vous les passez en revue, demandez des corrections ou les
  validez ;
- vous **validez les comptes rendus** périodiques ou demandez un complément ;
- vous **signalez** une affectation « À risque » ou « Bloquée » ;
- vous pouvez **proposer** des sujets R&D et en suivre l'avancement ;
- en fin d'alternance, vous réalisez le **bilan** et formulez une **recommandation** de partenariat avec l'école.

Groupe SharePoint : `HNCS-RD-Referents` (rôle `REFERENT`). La validation d'un livrable ou d'un compte rendu est réservée au
**référent de l'affectation** (ou à un membre de la Direction R&D désigné réviseur), et jamais à l'auteur du travail (contrôle
`G_VALIDEUR_LEGITIME`). Votre fiche dans la liste « Référents » (compte Microsoft 365, pôles, capacité, disponibilité) doit
être au statut « Actif » pour qu'une affectation puisse être activée.

## 2. Ce que vous voyez et ne voyez pas

D'après la matrice d'accès (spec § 7.3) et les permissions posées par les flux (§ 7.4).

| Accès | Listes et bibliothèques |
| --- | --- |
| Modification | Sujets R&D, Affectations, Livrables (hors champs protégés), Communications R&D, Ressources techniques, « 04 — Livrables R&D » |
| Modification, élément par élément | Comptes rendus dont vous êtes valideur ; bilans d'alternance dont vous êtes le référent ; actions de checklist dont vous êtes responsable ; modèles R&D dont vous êtes propriétaire (registre et fichiers) ; dossiers `05 — Suivi des alternants/ALT-…/` des alternants que vous encadrez, **y compris** leur sous-dossier `_Evaluations` |
| Lecture, élément par élément | Fiches « Alternants » des alternants dont vous êtes référent principal ou référent d'une affectation |
| Lecture seule | Offres, Écoles et établissements, Pôles R&D, Référents, Registre des modèles R&D, « 03 — Modèles R&D », Actions d'intégration et checklists, Modèles de checklists, Domaines cibles, Mobilisations commerciales, Transitions de statuts, Synchronisation GitLab |
| Aucun accès | Candidatures, « 01 — Recrutement » (CV), Entretiens, « 02 — Administration », Conventions et partenariats, Échanges avec les écoles, Paramètres, Historique des statuts, Journal des flux, « 06 — Écoles et partenariats » |

**Pourquoi ?** Les CV, les avis d'analyse et les évaluations d'entretien restent cloisonnés au recrutement (P-04) : vous
découvrez l'alternant à son intégration (N-16), pas pendant la sélection. Le sous-dossier `_Evaluations` du dossier de suivi
vous est accessible, mais **pas à l'alternant** : c'est là que se rangent les évaluations confidentielles.

## 3. Vos tâches pas à pas

### 3.1 Préparer l'arrivée d'un alternant

1. **N-16 « Intégration confirmée »** (si vous êtes référent pressenti) : date de début, pôle, liens vers la fiche et le
   dossier de suivi. **N-18** le jour du démarrage.
2. Action d'accueil **ACC-04 « Présenter le cadrage du sujet, les modèles et les règles de rédaction »** : elle vous est
   assignée (référent principal de l'alternant) et vous pouvez la modifier. Une fois la présentation faite, passez-la à
   « Terminée » avec, dans « Preuve / lien », le lien de la fiche de cadrage déposée.
3. Avec l'équipe R&D, **créez les livrables du cadrage** si aucun n'est proposé automatiquement (3.7) : un alternant ne peut
   pas en créer (H-49).
4. **N-20 « Affectation active »** quand l'équipe R&D active l'affectation : sujet, objectifs, liens GitLab, modèles, dossier de
   suivi, livrables proposés. Vous êtes ajouté sur le dossier de suivi et sur la fiche de l'alternant, et vous devenez son
   **référent principal** (valeur dérivée de l'affectation active la plus récente).

Les champs « Alternant », « Sujet », « Référent » et « Date de début » d'une affectation active sont **verrouillés** (P-03) :
toute modification est annulée avec **N-91**. Un changement de sujet ou de référent passe par une nouvelle affectation créée
par l'équipe R&D.

### 3.2 Passer un livrable en revue

1. Vous recevez **N-25 « Livrable soumis à revue »** (lien vers l'élément et le document). Ouvrez la liste **Livrables**, vue
   **« À revoir »** (livrables dont vous êtes réviseur, en « Soumis à revue » ou « En revue »).
2. Facultatif : posez **« En revue »** (`LIV-T05`) pour signaler que vous avez commencé. Aucune notification n'est envoyée.
3. Ouvrez le document par « Document (SharePoint) » ; consultez « Critères de validation » et, le cas échéant, « Lien
   GitLab ».
4. Prenez votre décision :

#### Demander des corrections

1. Ajoutez un nouveau **« Commentaires de revue »** : ce qui doit être corrigé, de façon précise. Le champ est en ajout seul :
   vos commentaires précédents restent visibles.
2. Posez **« Corrections demandées »** (`LIV-T06`).

Un **nouveau** commentaire est obligatoire (`G_COMMENTAIRE_REVUE`) : sans lui, le statut est rétabli (N-90). Ce que fait le
système (PA-07) : date de revue, décision « Corrections demandées », compteur de corrections + 1 (indicateur de validation au
premier passage), action « Correction livrable » assignée au propriétaire, **N-26** à l'alternant avec vos commentaires. La
version précédente du document est conservée par le versioning.

#### Valider

1. Pour un **POC / démonstrateur** ou un **plan de stratégie**, vérifiez et cochez d'abord la **Definition of Done**
   (section 3.3).
2. Posez **« Validé »** (`LIV-T07`).

Seul le référent de l'affectation, désigné réviseur, peut le faire (ou un membre de la Direction R&D désigné réviseur) ; un
alternant ne peut jamais valider son propre travail (`G_VALIDEUR_LEGITIME`). Ce que fait le système (PA-07) : il trace « Validé
par » (vous), « Date de validation », « Version validée du document » ; passe le document en « Validé » ; clôt les actions de
correction ouvertes ; envoie **N-27** à l'alternant ; puis tente la **capitalisation automatique** (section 3.4).

#### Suspendre ou abandonner

« Suspendu / abandonné » (`LIV-T09`) avec « Motif de suspension / abandon » (obligatoire, sinon l'enregistrement est refusé) et
« Impacts et suite envisagée » ; N-29 au propriétaire et à vous. Réactivation possible (`LIV-T10`).

### 3.3 Definition of Done (POC et plans de stratégie)

Un livrable de type « POC / démonstrateur » ou « Plan de stratégie » ne peut être **archivé** que si les cinq cases sont
cochées sur l'élément :

| Case | Critère |
| --- | --- |
| « DoD 1 — Fonctionnel et démontrable (POC) ou applicable (plan) » | Le démonstrateur fonctionne et peut être présenté ; pour un plan, il est applicable (H-36) |
| « DoD 2 — Fiche méthodologie rangée » | Fiche méthodologie rangée dans « 04 — Livrables R&D », dossier du sujet |
| « DoD 3 — Restitution présentée » | Restitution faite au référent ou au Comité R&D |
| « DoD 4 — Support de communication prêt » | Support réutilisable pour la valorisation |
| « DoD 5 — Enseignements et limites documentés » | Retour d'expérience, limites, suites possibles |

Ces cases sont des **champs protégés** (P-09) : seuls vous (réviseur légitime), l'équipe R&D et la Direction R&D pouvez les
cocher ; une case cochée par l'alternant est décochée et signalée (N-92). Si une case manque, SharePoint refuse l'archivage
avec le message « Un POC ou un plan de stratégie ne peut être clôturé qu'avec les 5 critères de la Definition of Done ». Les
cases d'une issue GitLab ne sont qu'un aide-mémoire : **seules celles de l'élément SharePoint font foi**. Seuls les POC et
plans archivés avec la Definition of Done complète comptent dans les indicateurs « POC réalisés » et « Plans de stratégie
formalisés ». Pour les autres types de livrables, appuyez-vous sur « Critères de validation ».

### 3.4 Capitalisation après validation

Juste après votre validation, le système vérifie le contrôle `G_CAPITALISATION` :

- « Document (SharePoint) » renseigné ;
- si le document est dans « 04 — Livrables R&D » : « Sujet » et « Type de document » renseignés sur le document ;
- Definition of Done complète pour un POC ou un plan de stratégie.

**Si tout est conforme** : le livrable passe seul en **« Archivé / clôturé »** (`LIV-T08`), le document devient « Référence »
(version capitalisée, visible dans la vue « Versions de référence » de la bibliothèque et « Capitalisés » de la liste).

**Sinon** : le livrable reste « Validé » et vous recevez **N-28 « Capitalisation incomplète »** listant les manques. Complétez
(ou faites compléter par l'alternant), puis posez vous-même **« Archivé / clôturé »** : les mêmes contrôles et effets
s'appliquent.

### 3.5 Valider un compte rendu

Les comptes rendus sont créés automatiquement au statut « Attendu » selon la cadence de l'affectation (par défaut tous les
14 jours, H-08) ; pour une cadence « Par jalon », c'est l'équipe R&D qui les crée. Vous êtes leur « Valideur ».

1. **N-32 « Compte rendu remis »** (état général, avancement). Ouvrez **Comptes rendus de suivi**, vue **« À valider »**.
2. Lisez « Réalisations de la période », « Prochaines étapes », « Avancement estimé (%) », « Risques », « Blocages »,
   « Décisions requises », « Soutien attendu du référent ».
3. Décidez :
   - **« Validé »** (`CR-T05`) : la date de validation est renseignée et l'alternant reçoit **N-34** ;
   - **« À compléter »** (`CR-T06`) : ajoutez d'abord un **« Commentaire du référent »** (obligatoire, sinon N-90 ; champ en
     ajout seul) ; l'alternant reçoit **N-34** avec votre commentaire.

Comme pour les livrables, seul le référent de l'affectation peut valider (`G_VALIDEUR_LEGITIME`). Sur un compte rendu, vous ne
modifiez que « Commentaire du référent » : l'affectation, le valideur, la période, l'échéance et les dates sont protégés (seules
l'équipe R&D et la Direction R&D peuvent les changer, P-09). Un compte rendu non remis
3 jours après son échéance (`CR.DelaiNonRemisJours`) passe en « Non remis » et vous recevez **N-31**. Si l'alternant coche
« Blocage signalé », la Direction R&D reçoit N-33 : voyez la vue « Blocages signalés ».

### 3.6 Signaler une affectation « À risque » ou « Bloquée »

1. Liste **Affectations**, ouvrez l'affectation concernée.
2. Posez **« À risque »** ou **« Bloquée »** (`AFF-T03`). La Direction R&D reçoit **N-21** ; l'affectation apparaît ensuite
   dans la synthèse du Comité R&D, puis au Point Direction si besoin (escalade § 7.7).
3. Quand la situation est rétablie, reposez **« Active »** (`AFF-T04`).

Seuls l'équipe R&D et le référent de l'affectation peuvent poser ces statuts.

### 3.7 Créer un livrable, ajuster une échéance

- **Livrable** : liste Livrables > Nouveau (`LIV-T01`) : « Titre du livrable », « Affectation », « Type de livrable », « Modèle
  utilisé » (modèle en vigueur du registre), « Propriétaire (auteur) » = l'alternant, « Échéance », « Critères de
  validation ». Le « Réviseur » est par défaut le référent de l'affectation ; c'est un champ protégé : seul vous-même ou un membre de la Direction R&D pouvez être désigné, et seules l'équipe R&D et la
  Direction R&D peuvent le changer).
- **Projet GitLab** : demandez sa création à l'équipe R&D ; un de ses membres, propriétaire du groupe `hncs-rd`, lance le
  script de création à votre demande (§ 10.3).
- **Échéance** : c'est un champ protégé ; en tant que réviseur légitime, vous pouvez la déplacer (comme l'équipe R&D et la
  Direction R&D), pas l'alternant ; « Échéance initiale » garde la valeur d'origine. S'il existe un jalon GitLab
  `LIV-…`, alignez-le **après** la modification SharePoint ; l'outillage ne modifie jamais un jalon, il signale l'écart.

### 3.8 Proposer et suivre un sujet

Vous pouvez créer un sujet (« Proposé », `SUJ-T01`), le soumettre à l'arbitrage (« À arbitrer », `SUJ-T02`, N-47 à la
Direction R&D), le passer « En cours » une fois priorisé (`SUJ-T04`) ou le déclarer « Bloqué » (`SUJ-T05`, N-47 à la
Direction R&D). L'**arbitrage** (Priorisé, Suspendu, Abandonné) est réservé à la Direction R&D et à la Direction ; en tant que
référent du sujet, vous recevez **N-47** avec la décision et son motif.

### 3.9 Suivre l'alternant

- **Fiche alternant** (lecture) : dates, école, pôle, référent principal.
- **Dossier de suivi** `05 — Suivi des alternants/ALT-…/` : plan de travail, consignes, bilans de mission (partagés avec
  l'alternant). Rangez les **évaluations confidentielles** dans `_Evaluations` (« Type de document » = Évaluation
  (confidentielle)) : l'alternant n'y a pas accès. Ne déposez aucun document métier dans la bibliothèque « Documents » par
  défaut du site ni dans les fichiers de l'équipe Teams : ils ne sont pas protégés par les droits du système (spec § 7.2).
- **Livrables** : vues « Livrables en cours », « En retard ». En cas de retard, vous recevez **N-24** avec l'alternant.

### 3.10 Fin d'alternance, bilan et recommandation

1. Trente jours avant la fin, **N-35 « Fin d'alternance planifiée »** : checklist de clôture et bilan à réaliser.
2. Actions de clôture qui vous sont assignées (vous pouvez les modifier) :

   | Code | Action | Bloquante | Preuve attendue |
   | --- | --- | --- | --- |
   | CLO-01 | Vérifier la clôture ou la suspension de tous les livrables | Oui | Aucun livrable ouvert |
   | CLO-02 | Capitaliser la documentation dans « 04 — Livrables R&D » | Oui | Versions de référence présentes |
   | CLO-03 | Organiser le transfert de connaissances | Non | — |
   | CLO-05 | Réaliser le bilan d'alternance | Oui | Bilan « Réalisé » |

3. **Bilan** : liste **Bilans d'alternance**, ouvrez le bilan « À réaliser » créé par le système (alternant, école, référent
   déjà renseignés ; vous seul, avec la R&D et la Direction R&D, pouvez le modifier). Passez-le en « En cours » puis
   remplissez :
   - « Date du bilan » ;
   - « Synthèse du parcours » (confidentielle) ;
   - « Livrables clôturés », « Documentation capitalisée » (cases) ;
   - « Retour d'expérience » ;
   - « Qualité de la collaboration avec l'école » (Très satisfaisante, Satisfaisante, À améliorer, Insatisfaisante) ;
   - **« Recommandation de partenariat »** (Recommandé, À étudier, Non recommandé) et sa « Justification » ;
   - « Contributeurs ».
4. Posez **« Réalisé »**. Sans date ni recommandation, l'enregistrement est refusé (« Un bilan réalisé doit être daté et
   comporter une recommandation »).

Ce que fait le système (PA-09) : il crée dans tous les cas l'action **PART-01 « Évaluation partenariat »** assignée au
responsable HNCS de l'école ; si la recommandation est « Recommandé » ou « À étudier » et que l'école n'est pas déjà partenaire,
l'école passe en **« Partenariat à évaluer »** (signal de revue) ; **N-38** est envoyé à la Direction R&D et à la relation
écoles.

> **Une recommandation n'est pas une décision.** La décision de partenariat ou de sponsoring est prise ensuite par la Direction
> R&D ou la Direction Générale, et tracée dans la liste « Conventions et partenariats » (PA-10), avant toute signature.

### 3.11 Communications

Vous pouvez créer une communication (`COM-T01`) et la porter jusqu'à « En revue ». Si vous êtes désigné **« Approbateur
proposé »**, vous pouvez la renvoyer « En rédaction » (`COM-T03`) ; la **validation** d'une communication externe reste réservée
à la Direction R&D et à la Direction Générale (H-11), qui reçoivent la demande N-44.

### 3.12 Erreurs fréquentes

| Ce que vous voyez | Cause | Que faire |
| --- | --- | --- |
| « Corrections demandées » revient à l'ancien statut + N-90 | Aucun nouveau commentaire de revue | Ajouter un commentaire, reposer le statut |
| « Validé » refusé (N-90) | Vous n'êtes pas le référent de l'affectation (`G_VALIDEUR_LEGITIME`) | Vérifier l'affectation et le « Réviseur » avec l'équipe R&D |
| N-92 « champ protégé » | Modification du réviseur, du propriétaire… réservée à la R&D | Demander à l'équipe R&D |
| Message sur les 5 critères de la Definition of Done | Archivage d'un POC / plan sans les 5 cases | Cocher les cases (après vérification) |
| N-28 après validation | Capitalisation incomplète | Compléter document et métadonnées, poser « Archivé / clôturé » |
| « À compléter » refusé | « Commentaire du référent » vide | Le remplir |
| N-91 | Champ verrouillé modifié sur l'affectation | Demander une nouvelle affectation à l'équipe R&D |

## 4. Vos décisions humaines

| Décision | Statut posé | Trace |
| --- | --- | --- |
| Validation d'un livrable | « Validé » (`LIV-T07`) | « Validé par », « Date de validation », « Version validée du document » |
| Demande de corrections | « Corrections demandées » (`LIV-T06`) | « Commentaires de revue » (historique conservé), « Nombre de demandes de corrections » |
| Respect de la Definition of Done | Cases DoD 1 à DoD 5 | Versioning, champs protégés |
| Suspension / abandon d'un livrable | « Suspendu / abandonné » (`LIV-T09`) | Motif, impacts et suite envisagée |
| Validation d'un compte rendu / demande de complément | « Validé » (`CR-T05`) / « À compléter » (`CR-T06`) | « Date de validation », « Commentaire du référent » |
| Signalement de risque ou de blocage | Affectation « À risque » / « Bloquée » (`AFF-T03`) | Historique, N-21 |
| Bilan et recommandation de partenariat | Bilan « Réalisé » | « Recommandation de partenariat », « Justification » |

Le système enregistre et notifie, il ne décide jamais à votre place (P-01). Chaque transition est historisée (acteur, date,
résultat) et chaque élément est versionné.

## 5. Notifications que vous recevez

| Code | Quand | Que faire |
| --- | --- | --- |
| N-16 | Intégration confirmée (référent pressenti) | Préparer l'accueil (ACC-04) |
| N-18 | L'alternant démarre aujourd'hui | Accueillir |
| N-19 | Action de checklist à échéance (ACC-04, CLO-…) | Réaliser l'action, la terminer avec sa preuve |
| N-20 | Affectation active | Prendre connaissance du sujet et des livrables proposés |
| N-22 | Affectation terminée (avec les livrables encore ouverts) | Aider la R&D à décider de leur sort |
| N-25 | Livrable soumis à revue | Le passer en revue (3.2) |
| N-24 | Livrable en retard | Faire le point avec l'alternant |
| N-28 | Capitalisation incomplète | Compléter puis archiver (3.4) |
| N-29 | Livrable suspendu ou abandonné | Prendre note |
| N-32 | Compte rendu remis | Le valider ou demander un complément (3.5) |
| N-31 | Compte rendu non remis | Relancer l'alternant |
| N-47 | Décision d'arbitrage sur un sujet dont vous êtes référent | Adapter le travail |
| N-35 | Fin d'alternance planifiée | Actions de clôture et bilan (3.10) |
| N-36 | Alternant suspendu | Adapter le suivi |
| N-37 | Fin d'alternance enregistrée | Finaliser la clôture |
| N-45 | Décision sur une communication dont vous êtes l'auteur | Selon la décision |
| N-90 | Changement de statut refusé | Lire le motif, corriger |
| N-91 / N-92 | Modification annulée (champ verrouillé ou protégé) | Passer par l'équipe R&D |

## 6. Vos vues Power BI

Rôle Power BI **Referent** : les données sont **limitées aux affectations et aux alternants que vous encadrez** ; aucune donnée
de recrutement (candidatures, entretiens, actions d'intégration) n'est visible. Pages de votre audience dans l'application
(spec § 9.7) :

| Page | Usage pour vous |
| --- | --- |
| 3. Effectifs et encadrement | Vos alternants (par identifiant), vos affectations, votre charge |
| 4. Projets et livrables | Livrables par statut, retards, remise à l'heure, validation au premier passage, capitalisation, comptes rendus manquants, avancement par sujet, écarts GitLab, lien vers les documents |
| 7. Comité R&D | Échéances à 14 jours, livrables en retard, affectations à risque, blocages, comptes rendus manquants |

Aucun visuel n'affiche de nom de personne. Actualisation quotidienne à 06:00.

## 7. Rituels de gouvernance

| Rituel | Ce qui vous concerne |
| --- | --- |
| Comité R&D hebdomadaire (lundi 08:00) | Vous en êtes membre avec la Direction R&D et l'équipe R&D (H-53). La synthèse PA-11 (N-42, envoyée à la Direction R&D et publiée dans le canal Teams « Comité R&D ») reprend vos livrables en retard de plus de 7 jours, les comptes rendus non remis, les blocages, les affectations « À risque » / « Bloquée » et les sujets bloqués ou à arbitrer. Mettez vos revues et statuts à jour avant le lundi matin ; préparez-vous avec la page Power BI 7. La restitution d'un POC ou d'un plan (DoD 3) peut s'y tenir. |
| Point Direction mensuel, revue trimestrielle | Synthèses agrégées préparées par la Direction R&D pour la Direction Générale ; vos validations et bilans alimentent les indicateurs (livrables validés, capitalisation, partenariats). |

## 8. FAQ

### Quelle différence entre « Soumis à revue » et « En revue » ?

« Soumis à revue » est posé par l'alternant quand il demande votre revue. « En revue » est facultatif : il indique que vous avez
commencé. Vous pouvez valider ou demander des corrections depuis l'un ou l'autre.

### J'ai validé, mais le livrable n'est pas « Archivé / clôturé ». Est-ce normal ?

Oui si la capitalisation est incomplète : N-28 liste les manques (document, « Sujet » ou « Type de document » du document,
Definition of Done). Complétez puis posez « Archivé / clôturé ».

### On m'a désigné réviseur d'un livrable d'une affectation qui n'est pas la mienne : puis-je le valider ?

Cela ne peut plus arriver : une désignation comme réviseur d'une personne qui n'est ni le référent de l'affectation ni un membre
de la Direction R&D est refusée dès l'enregistrement (P-09, N-92), et la validation le serait aussi (`G_VALIDEUR_LEGITIME`).

### Fusionner la merge request GitLab valide-t-elle le livrable ?

Non. La validation se fait uniquement dans SharePoint, par le réviseur légitime (P-05).

### Je ne reçois pas les notifications de soumission d'un livrable. Pourquoi ?

N-25 n'est envoyé qu'au « Réviseur (référent) » du livrable. Vérifiez avec l'équipe R&D que c'est bien votre compte.

### L'alternant peut-il lire mes évaluations ?

Non, si elles sont rangées dans le sous-dossier `_Evaluations` de son dossier de suivi, dont il est exclu.

### Ma recommandation « Recommandé » crée-t-elle un partenariat ?

Non. Elle déclenche une évaluation (PART-01) et fait passer l'école en « Partenariat à évaluer » ; la décision appartient à la
Direction R&D ou à la Direction Générale.

### Je ne peux plus encadrer cet alternant. Que faire ?

Prévenez l'équipe R&D : elle crée une nouvelle affectation avec un autre référent, qui termine la vôtre sans l'effacer.

### Puis-je voir le CV de l'alternant que j'encadre ?

Non : les CV et le dossier de recrutement restent cloisonnés (P-04). Les informations utiles vous parviennent à l'intégration.
