# Guide utilisateur — Administration

> Public : équipe administrative habilitée, par exemple **Karine** (groupe SharePoint `HNCS-RD-Administration`). Règles communes
> (statuts refusés, champs protégés, validations, notifications) : voir l'[index des guides](README.md#repères-communs-à-tous-les-guides).
> Référence : `spec.md` 1.6.0.

## 1. Votre rôle dans le processus

L'administration prend le relais de la R&D dès qu'un profil est **présélectionné** et transmis (RACI § 7.6 : « R » sur les
entretiens, la sélection et les formalités) :

- elle **planifie les entretiens** et **saisit leur résultat** ;
- elle enregistre la **décision finale** de sélection (en indiquant le « Décideur final »), y compris un refus avant tout
  entretien ;
- elle **autorise le lancement des formalités**, suit la checklist et ses preuves ;
- elle **confirme l'intégration**, qui crée la fiche alternant (H-40) ;
- elle gère les **conventions** avec les écoles et constate leur signature avec preuve.

Groupe SharePoint : `HNCS-RD-Administration` (rôle `ADMIN` dans la spec). Le destinataire par défaut des transmissions est
l'adresse du paramètre `Destinataires.Administration` (Karine, H-05). Les acteurs support (RH, juridique, finance)
interviennent hors outil ou par l'intermédiaire de l'administration (H-32).

## 2. Ce que vous voyez et ne voyez pas

D'après la matrice d'accès (spec § 7.3) et les permissions posées par les flux (§ 7.4).

| Accès | Listes et bibliothèques |
| --- | --- |
| Modification | Entretiens, « 02 — Administration », Écoles et établissements, Conventions et partenariats, Échanges avec les écoles, Alternants, Actions d'intégration et checklists, Modèles de checklists, « 06 — Écoles et partenariats » |
| Modification, **élément par élément** | Candidatures et leur dossier CV dans « 01 — Recrutement » : uniquement les candidatures **transmises**. Selon le paramètre `Recrutement.PartageTransmission`, l'accès est ouvert à toute l'équipe administrative (valeur initiale « Groupe ») ou au seul destinataire de la transmission (« Destinataire », H-45) |
| Lecture seule | Offres, Pôles R&D, Référents, Sujets R&D, Affectations, Registre des modèles R&D, Communications R&D, Domaines cibles, Paramètres, Transitions de statuts, Historique des statuts, « 03 — Modèles R&D » |
| Aucun accès | Livrables, Comptes rendus de suivi, Bilans d'alternance, Ressources techniques, Mobilisations commerciales, Journal des flux, Synchronisation GitLab, « 04 — Livrables R&D », « 05 — Suivi des alternants » |

**Pourquoi ?** Cloisonnement des CV et des données personnelles (P-04) :

- vous ne voyez une candidature et son CV **qu'à partir de sa transmission** (H-29) : les candidatures en cours d'analyse
  restent à la R&D ;
- à l'inverse, vos **commentaires d'entretien** et grilles d'évaluation ne sont visibles que de l'administration : la R&D n'a
  pas accès à la liste Entretiens (hormis les participants désignés, qui lisent l'entretien concerné, évaluation comprise) et reçoit seulement
  le statut (N-11, sans commentaire, H-28) ;
- la bibliothèque **« 02 — Administration »** (contrats, conventions, pièces administratives, grilles d'entretien) vous est
  réservée ; seul le sous-dossier `Alternants/ALT-…/Operationnel` est lisible par la R&D, pour ses besoins opérationnels ;
- le travail de production R&D (livrables, comptes rendus, bilans) ne relève pas de votre rôle.

## 3. Vos tâches pas à pas

### 3.1 Recevoir un profil transmis (N-05)

1. Vous recevez **N-05 « Profil présélectionné CAND-… transmis »** : lien sécurisé vers la candidature et le dossier CV. Aucun
   CV n'est joint et l'avis de la R&D n'est pas recopié dans le message.
2. La candidature est en **« Transmise à l'administration »**. Retrouvez toutes vos candidatures dans la vue **« Transmises à
   l'administration »** de la liste Candidatures.
3. Consultez dans l'élément l'« Avis de la R&D », et le CV par le lien « CV (lien sécurisé) ».

### 3.2 Planifier un entretien

1. Liste **Entretiens** > **Nouveau** :
   - « Objet de l'entretien » ;
   - « Candidature » : l'identifiant `CAND-…` ;
   - « Date et heure », « Type d'entretien » (Premier entretien, Entretien technique, Entretien final, Autre), « Modalité »
     (Présentiel, Teams, Téléphone) ;
   - « Participants HNCS » : ils obtiennent la lecture de cet entretien ;
   - « Lien de réunion » : créez l'invitation Teams / Outlook et collez son lien (la création automatique de réunion est
     désactivée par défaut, `Fonction.CreationReunionTeams` = Non).
2. Enregistrez : statut « Planifié ».

Ce que fait le système (PA-03) : la candidature passe automatiquement à **« Entretien planifié »** (`CAND-T07`, depuis
« Transmise à l'administration », « Entretien réalisé » ou « En attente de décision »). Vous n'avez pas à changer ce statut
vous-même. **N-10** rappelle l'entretien aux participants 24 heures avant (`Delai.RappelEntretienHeures`). Chaque changement
de statut ou de résultat d'un entretien est historisé.

**Reporter ou annuler** : pour décaler, modifiez « Date et heure » (l'entretien reste « Planifié », le rappel est réarmé). Pour
renoncer, posez « Reporté » ou « Annulé » : s'il ne reste aucun entretien planifié, la candidature revient à « Transmise à
l'administration » (`CAND-T08`) et vous recevez **N-04**.

### 3.3 Saisir le résultat d'un entretien

1. Ouvrez la vue **« Résultats à saisir »** (entretiens planifiés dont la date est passée). Deux heures après l'heure prévue,
   **N-14** vous le rappelle.
2. Sur l'entretien : posez le statut **« Réalisé »** et choisissez le **« Résultat »** : Favorable, Défavorable, Réservé —
   entretien complémentaire. Sans résultat, SharePoint refuse l'enregistrement (« Le résultat est obligatoire lorsque
   l'entretien est réalisé »).
3. Complétez « Prochaine action », « Commentaire (restreint) » et « Grille d'évaluation » (lien vers le document déposé dans
   « 02 — Administration », « Type de document » = Grille d'évaluation d'entretien, dans le dossier
   `Candidatures/CAND-…/` créé dès la transmission). Les participants désignés liront aussi l'entretien et son évaluation
   (H-28) : rédigez en conséquence.

Ce que fait le système : il trace « Résultat saisi par » et « Date de saisie du résultat », passe la candidature à
**« Entretien réalisé »** (`CAND-T09`) et envoie **N-11** à la R&D (statut seulement). Le résultat saisi n'est jamais modifié
par un flux. Pour un résultat « Réservé », planifiez un nouvel entretien (la candidature repasse en « Entretien planifié »).

### 3.4 Enregistrer la décision finale

1. Sur la candidature, renseignez **« Décideur final »** : la personne qui a pris la décision (H-06). Si la décision a été
   prise par une autre personne (par exemple de la Direction), c'est elle que vous indiquez.
2. Facultatif : posez « En attente de décision » (`CAND-T10`) pendant la réflexion ; **N-12** rappelle à l'administration
   qu'une décision est attendue.
3. Posez la décision :
   - **« Retenue »** (`CAND-T11`) : la date de décision finale est renseignée et **N-13** est envoyé à l'administration et au
     responsable d'analyse (« lancer les formalités ») ;
   - **« Non retenue »** après entretien (`CAND-T12`) avec un « Motif codifié » (ex. Avis défavorable après entretien) : **N-06**
     à la R&D et à l'administration, et tâche **N-08** « informer le candidat » au responsable d'analyse.

Contrôle `G_DECISION_FINALE` : « Décideur final » renseigné **et** au moins un entretien « Réalisé ». À défaut, le statut est
rétabli (N-90).

**Refus sans entretien** (`CAND-T17`) : depuis « Transmise à l'administration » ou « Entretien planifié », vous pouvez poser
« Non retenue » sans entretien réalisé (désistement constaté, profil écarté à la relecture). Renseignez le « Décideur final »
(contrôle `G_DECIDEUR`) et le « Motif codifié ». Un désistement peut aussi se traiter par « Clôturée » avec le motif
« Désistement du candidat » (`CAND-T15`).

Convenez avec la R&D de qui informe le candidat ; la personne qui l'informe coche « Candidat informé de l'issue » et la date
(H-09).

### 3.5 Lancer les formalités

Posez **« Formalités en cours »** (`CAND-T13`) sur une candidature « Retenue ». C'est l'autorisation de lancer les formalités
(décision humaine).

Ce que fait le système (PA-04) : il génère la checklist « Formalités d'intégration » à partir des modèles de checklists, vérifie
le dossier `02 — Administration/Candidatures/CAND-…/` (créé dès la transmission) et vous envoie **N-15** (liste des actions, responsables, échéances).
Chaque responsable obtient le droit de modifier son action.

| Code | Action | Responsable | Échéance | Bloquante | Preuve attendue |
| --- | --- | --- | --- | --- | --- |
| FORM-01 | Confirmer la décision et la date de démarrage avec le candidat | Administration | J+3 | Oui | Courriel de confirmation enregistré dans le dossier administratif |
| FORM-02 | Obtenir les informations de l'école (formation, calendrier, contact) | Administration | J+7 | Oui | Fiche école ou courriel de l'école |
| FORM-03 | Établir le contrat ou la convention et la faire signer | Administration | J+14 | Oui | Document signé dans « 02 — Administration » |
| FORM-04 | Collecter les pièces administratives requises | Administration | J+14 | Oui | Pièces déposées dans « 02 — Administration » |
| FORM-05 | Confirmer le pôle, le référent pressenti et le sujet pressenti | Responsable d'analyse (R&D) | J+10 | Oui | Champs renseignés sur la candidature |
| FORM-06 | Informer le référent pressenti de l'arrivée | Responsable d'analyse (R&D) | J+10 | Non | — |

Ce contenu est une proposition à valider par l'administration et la Direction R&D (H-23). Vous pouvez l'ajuster vous-même dans
la liste **« Modèles de checklists »** (droit de modification), sans développement ; une modification vaut pour les checklists
générées ensuite.

### 3.6 Tenir la checklist et ses preuves

1. Liste **Actions d'intégration et checklists**, vue **« Mes actions »** (ou « Actions ouvertes », regroupée par contexte).
2. Pour chaque action : passez le statut à « En cours » puis :
   - **« Terminée »** : pour une action **bloquante**, renseignez **« Preuve / lien »** (lien vers le document déposé dans
     `02 — Administration/Candidatures/CAND-…/`) ;
   - **« Non applicable »** : pour une action bloquante, renseignez obligatoirement « Commentaire » (justification) ;
   - « Bloquée » si vous êtes empêché.
3. Déposez les pièces dans « 02 — Administration » (« Type de document » : Contrat, Convention, Pièce administrative…). La
   « Description » d'une action ne contient **aucune donnée sensible** : les pièces restent dans la bibliothèque. Ne déposez
   jamais de pièce dans la bibliothèque « Documents » par défaut du site, lisible par tous les groupes (spec § 7.2).

**Champs protégés** (`G_ACTION_FORMALITE`, P-09) : pour les formalités d'intégration, **seule l'administration** peut décocher
« Bloquante pour l'étape » ou passer une action bloquante en « Non applicable » ; le passage à « Terminée » est possible par
l'administration ou par le responsable désigné. Toute autre modification est rétablie et signalée (N-92).

Rappels : **N-19** deux jours avant l'échéance (`Delai.RappelActionJours`) puis chaque jour en cas de retard (au-delà, l'action
apparaît dans la synthèse du Comité R&D, § 7.7). Quand toutes les actions bloquantes sont terminées ou justifiées, **N-17**
vous invite à confirmer l'intégration. Aucun statut ne change automatiquement : la confirmation reste votre décision.

### 3.7 Confirmer l'intégration

1. Sur la candidature, vérifiez :
   - « Date de démarrage confirmée » et « Date de fin prévue » (la fin doit suivre le démarrage) ;
   - « École / établissement » et « Pôle pressenti » (et si possible « Référent pressenti », « Sujet pressenti »).
2. Posez **« Intégrée »** (`CAND-T14`).

**Pourquoi le passage à « Intégrée » peut être refusé** — double barrière (P-02) :

| Barrière | Moment | Ce qui est vérifié | Ce que vous voyez |
| --- | --- | --- | --- |
| Règle de validation de la liste | À l'enregistrement | Les deux dates sont renseignées et cohérentes | L'élément n'est pas enregistré ; message « … dates de démarrage et de fin (cohérentes) obligatoires pour « Intégrée » » |
| Contrôle `G_INTEGRATION` (PA-04) | Quelques secondes après | (a) date de décision finale renseignée (la candidature est passée par « Retenue ») ; (b) dates de démarrage et de fin ; (c) établissement et pôle pressenti ; (d) une checklist « Formalités d'intégration » existe ; (e) **toutes** les actions bloquantes sont « Terminée » **avec preuve**, ou « Non applicable » **avec commentaire** | Statut rétabli à « Formalités en cours » et **N-90** détaillant les éléments manquants |

Cas le plus fréquent : une action bloquante terminée sans lien de preuve. Complétez, puis reposez « Intégrée ».

Ce que fait le système si tout est conforme (PA-04) : il crée la fiche **Alternants** (statut « À intégrer », dates, école,
pôle, référent principal = référent pressenti), renseigne « Identifiant alternant » et « Date d'intégration » sur la
candidature, crée les dossiers `05 — Suivi des alternants/ALT-…/` (et `_Evaluations`) et `02 — Administration/Alternants/ALT-…/`
(avec son sous-dossier `Operationnel` lisible par la R&D), donne au référent la lecture de la fiche, génère la checklist
« Accueil » (création du compte, groupes, poste, présentation du cadrage, affectation), passe l'école à « Établissement
d'accueil » si elle était « Prospect » ou « Contact établi » (simple constat, pas un partenariat, H-39) et envoie **N-16** à
la R&D, au référent pressenti et à vous. À la date de début, l'alternant passe seul en « Actif » (PA-04b).

### 3.8 Suivre la fiche alternant, la prolongation et la clôture

- Vous pouvez compléter la fiche **Alternants** (« Rythme d'alternance », « E-mail professionnel »…). Le « Référent
  principal » est **dérivé** des affectations : ne le modifiez pas (modification annulée, N-91).
- Statuts que vous pouvez poser : « Suspendu » (`ALT-T03`), « Terminé » (`ALT-T05`, avec « Date de fin réelle »
  obligatoire), « Clôturé » depuis « À intégrer » (`ALT-T07`, par exemple désistement avant le démarrage).
- **Prolongation** : si un alternant en « Fin planifiée » est prolongé, reportez « Date de fin prévue » puis reposez
  « Actif » (`ALT-T08`) ; la nouvelle date de fin doit être à plus de 30 jours (`G_DATE_FIN_REPORTEE`). Les échéances des
  actions de clôture encore ouvertes sont recalculées (dont CLO-07) ; le bilan est conservé.
- À la fin d'alternance, **N-37** vous est envoyé ; l'action **CLO-07 « Archiver le dossier administratif »** vous revient.

### 3.9 Écoles, conventions et preuve de signature

**Échanges avec les écoles** : enregistrez chaque échange (« Objet de l'échange », « Établissement », « Date »,
« Interlocuteur », « Type d'échange », « Résumé », « Prochaine action » et son échéance, « Document associé » rangé dans
« 06 — Écoles et partenariats »). Le flux PA-10 met à jour « Dernière interaction » et la prochaine action de l'école ; **N-41**
prévient le responsable HNCS à l'échéance.

**Conventions et partenariats** :

1. **Nouveau** (`CONV-T01`) : « Objet de la convention », « Établissement », « Type » (Convention de stage, Contrat
   d'alternance — volet école, Convention de partenariat, Sponsoring, Autre), « Alternant concerné », « Début », « Fin »,
   « Responsable HNCS », « Renouvellement ».
2. Faites avancer le statut : À préparer → En discussion → En validation → À signer (`CONV-T02`).
3. Pour **« Signée / active »** (`CONV-T03`) :
   - renseignez **« Date de signature »** et **« Preuve de signature »** (lien vers le document signé) : sans date,
     SharePoint refuse l'enregistrement ; sans preuve, le statut est rétabli (N-90), car « aucun document n'est considéré signé
     sans preuve » (`G_PREUVE_SIGNATURE`) ;
   - pour une **convention de partenariat ou de sponsoring**, la **décision de partenariat** doit avoir été prise **avant** :
     « Décision de partenariat » = Partenariat retenu ou Sponsoring retenu, avec un « Décideur » tracé (`G_DECISION_PARTENARIAT`).
     Sinon, la signature est refusée (N-90) : demandez la décision à la Direction R&D ou à la Direction Générale.
4. Une convention de partenariat ou de sponsoring signée fait passer l'école en « Partenaire actif ».

Ensuite, le système passe la convention en « À renouveler » 60 jours avant la fin (`Convention.AlerteExpirationJours`) puis en
« Expirée », avec **N-40** au responsable. Vues utiles : « Conventions en cours », « À renouveler », « Décisions de
partenariat ».

> **Ne modifiez pas « Décision de partenariat ».** Ce champ protégé est réservé à la Direction R&D et à la Direction
> Générale : toute modification par une autre personne est rétablie et signalée (N-92). Une fois la décision prise, vous recevez
> **N-39**. De même, ne posez pas vous-même le statut « Partenaire actif » sur une école : il découle d'une convention signée.

### 3.10 Erreurs fréquentes

| Ce que vous voyez | Cause | Que faire |
| --- | --- | --- |
| La candidature est revenue à « Formalités en cours » + N-90 | `G_INTEGRATION` non satisfait | Lire la liste des manques dans N-90 (souvent une preuve manquante), compléter |
| Message « dates de démarrage et de fin (cohérentes) obligatoires » | Règle de validation de la liste | Renseigner les deux dates, fin après démarrage |
| « Retenue » ou « Non retenue » refusé (N-90) | « Décideur final » vide, ou aucun entretien « Réalisé » pour « Retenue » | Compléter puis reposer |
| « Le résultat est obligatoire lorsque l'entretien est réalisé » | Règle de validation de la liste Entretiens | Choisir un « Résultat » |
| Vous avez posé « Entretien planifié » à la main et il est refusé | Aucun entretien « Planifié » lié (`G_ENTRETIEN_PLANIFIE`) | Créer l'entretien : le statut suit tout seul |
| « Signée / active » refusé | Preuve ou date de signature manquante ; pour un partenariat ou sponsoring, décision préalable absente | Compléter ; demander la décision à la Direction |
| N-92 | Modification d'un champ protégé (formalité dont vous n'êtes pas responsable, décision de partenariat…) | Laisser la personne habilitée agir |
| Vous ne trouvez pas une candidature | Elle n'est pas encore transmise (H-29), ou le partage est limité au seul destinataire (H-45) | Attendre N-05 ou voir avec la R&D |

## 4. Vos décisions humaines

| Décision | Statut posé | Trace |
| --- | --- | --- |
| Résultat d'entretien | Entretien « Réalisé » + « Résultat » | « Résultat saisi par », « Date de saisie du résultat », historique |
| Décision finale de sélection | Candidature « Retenue » (`CAND-T11`) ou « Non retenue » (`CAND-T12`, `CAND-T17`) | « Décideur final », « Date de décision finale », motif |
| Autorisation de lancer les formalités | « Formalités en cours » (`CAND-T13`) | Historique, checklist générée |
| Confirmation de l'intégration | « Intégrée » (`CAND-T14`) | « Date d'intégration », « Identifiant alternant » |
| Clôture pour un autre motif | « Clôturée » (`CAND-T15`) | Motif codifié |
| Constat de signature avec preuve | Convention « Signée / active » (`CONV-T03`) | « Date de signature », « Preuve de signature » |
| Fin effective de l'alternance (avec la R&D) ; prolongation | Alternant « Terminé » (`ALT-T05`) ; « Actif » depuis « Fin planifiée » (`ALT-T08`) | « Date de fin réelle » ; nouvelle date de fin |

Le caractère définitif de la sélection reste à confirmer par la Direction Générale (« A* » du RACI, H-06). Chaque décision est
historisée dans **« Historique des statuts »** (lecture pour vous), en plus du versioning des éléments.

## 5. Notifications que vous recevez

| Code | Quand | Que faire |
| --- | --- | --- |
| N-05 | Profil présélectionné transmis | Consulter la candidature, planifier un entretien |
| N-04 | Plus aucun entretien planifié pour une candidature | Replanifier ou décider |
| N-10 | Rappel d'entretien (si vous êtes participant) | Préparer l'entretien |
| N-14 | Résultat d'entretien à saisir | Saisir statut « Réalisé » et « Résultat » |
| N-12 | Décision attendue | Enregistrer la décision finale |
| N-13 | Candidature retenue | Lancer les formalités |
| N-06 | Candidature non retenue après entretien | Convenir avec la R&D de l'information du candidat |
| N-15 | Formalités lancées | Traiter la checklist |
| N-19 | Action de checklist à échéance | Terminer l'action avec sa preuve |
| N-17 | Formalités complètes | Confirmer l'intégration |
| N-16 | Intégration confirmée | Compléter la fiche alternant si besoin |
| N-37 | Fin d'alternance enregistrée | Action CLO-07 |
| N-39 | Décision de partenariat enregistrée | Préparer ou faire signer la convention correspondante |
| N-40 | Convention à renouveler ou expirée (si vous en êtes responsable) | Lancer le renouvellement ou clôturer |
| N-41 | Prochaine action école à échéance (si vous êtes responsable HNCS de l'école) | Réaliser l'action, enregistrer l'échange |
| N-90 | Changement de statut refusé | Lire le motif, corriger |
| N-91 / N-92 | Modification annulée (référent principal, champ protégé) | Passer par la personne habilitée |

## 6. Vos vues Power BI

Rôle Power BI **Administration** : pages 2, 3 et 5 (audience de l'application, spec § 9.7). Les candidatures sont limitées à celles qui vous ont été
**transmises** ; les données de livrables, comptes rendus, mobilisations et GitLab sont masquées pour ce rôle.

| Page | Usage pour vous |
| --- | --- |
| 2. Recrutement | Entonnoir, délais de traitement, entretiens à venir, candidatures en attente, motifs agrégés |
| 3. Effectifs et encadrement | Alternants actifs, présents sur la période, répartition par pôle et par école (identifiants, sans nom) |
| 5. Établissements et partenariats | Écoles collaborantes, conventions à renouveler, partenariats à évaluer, bilans réalisés, prochaines actions école |

Le rapport n'importe aucune donnée personnelle, hormis le nom de l'alternant, absent de tous les visuels et masqué pour les publics sans
accès SharePoint aux fiches alternants (Direction, Relation écoles), ni aucune donnée confidentielle (pas de CV, de commentaire, de
grille) ; aucun visuel n'affiche de nom. Actualisation quotidienne à 06:00.

## 7. Rituels de gouvernance

Vous n'êtes pas destinataire des synthèses automatiques PA-11. Les points qui vous concernent y figurent en agrégé : au Comité
R&D hebdomadaire (lundi 08:00) les conventions « À renouveler », les actions de checklist en retard et les candidatures en
attente (en nombre par statut) ; au Point Direction mensuel et à la revue trimestrielle (synthèse relayée par la Direction R&D),
les indicateurs de recrutement et de partenariats. Vous pouvez y être consultée (« C » du RACI). Tenez à jour les statuts et
les preuves avant ces échéances pour que les synthèses soient justes.

## 8. FAQ

### Pourquoi ne vois-je pas une candidature dont la R&D me parle ?

Vous n'y avez accès qu'à partir de sa transmission (H-29). Tant qu'elle est en analyse, elle reste à la R&D. Si le partage est
configuré « au seul destinataire » (H-45), seule la personne destinataire la voit.

### J'ai posé « Intégrée » et le statut est revenu à « Formalités en cours ». Que faire ?

Le contrôle `G_INTEGRATION` a trouvé un manque, détaillé dans N-90 : le plus souvent une action bloquante « Terminée » sans
« Preuve / lien », ou un champ (établissement, pôle pressenti) vide. Complétez et reposez « Intégrée ».

### Une action de la checklist ne s'applique pas à ce candidat : comment faire ?

Posez « Non applicable » et justifiez dans « Commentaire » (obligatoire pour une action bloquante). Pour une action
bloquante, vous seule (administration) pouvez le faire. Vous ne pouvez pas supprimer l'action.

### Le candidat se désiste avant l'entretien. Que dois-je saisir ?

Avant l'intégration : « Non retenue » (`CAND-T17`, avec « Décideur final » et motif) ou « Clôturée » avec le motif
« Désistement du candidat ». Si la fiche alternant existe déjà (« À intégrer ») : posez « Clôturé » sur la fiche (`ALT-T07`).

### La R&D peut-elle lire mes commentaires d'entretien ?

Seuls les participants désignés d'un entretien le lisent, évaluation comprise (H-28). Les autres membres de la R&D n'ont pas
accès à la liste Entretiens ; N-11 ne leur transmet que le statut.

### La décision finale a été prise par quelqu'un d'autre que moi : qui dois-je indiquer ?

Indiquez cette personne dans « Décideur final » ; c'est vous qui saisissez le statut (H-06).

### Puis-je signer une convention de partenariat sans décision de la Direction ?

Non : « Signée / active » est refusé tant que « Décision de partenariat » ne vaut pas Partenariat retenu ou Sponsoring retenu
avec un décideur tracé (`G_DECISION_PARTENARIAT`). Seules la Direction R&D et la Direction Générale peuvent saisir cette
décision.

### Comment prouver la signature d'une convention ?

Déposez le document signé (dans « 06 — Écoles et partenariats » ou « 02 — Administration » selon le cas) et collez son lien
dans « Preuve de signature », avec la « Date de signature ».

### Un entretien est décalé d'une semaine : faut-il en créer un nouveau ?

Non : modifiez « Date et heure » de l'entretien existant ; il reste « Planifié » et le rappel est réarmé.

### L'alternance est prolongée de trois mois : que faire ?

Reportez « Date de fin prévue » sur la fiche Alternants, puis reposez « Actif » si l'alternant était en « Fin planifiée »
(`ALT-T08`).
