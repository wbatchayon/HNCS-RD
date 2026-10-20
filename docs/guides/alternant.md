# Guide utilisateur : Alternant

> Public : alternants et stagiaires actifs (groupe SharePoint `HNCS-RD-Alternants`). Règles communes (statuts refusés,
> champs protégés, validations, notifications) : voir l'[index des guides](README.md#repères-communs-à-tous-les-guides).
> Référence : `spec.md` 1.6.0.

## 1. Votre rôle dans le processus

Vous travaillez sur un **sujet R&D**, encadré par un **référent**, dans le cadre d'une **affectation** créée par l'équipe R&D.
Votre rôle dans le système :

- produire vos **livrables**, déposer les documents et les **soumettre à revue** ;
- traiter les **corrections** demandées par votre référent ;
- remettre vos **comptes rendus** périodiques ;
- **signaler** vos blocages ;
- travailler dans **GitLab** pour le code, en respectant les conventions de nommage.

Groupe SharePoint : `HNCS-RD-Alternants` (rôle `ALTERNANT`). Sur vos livrables, vos comptes rendus et votre affectation, vous
êtes l'« auteur » (rôle `ITEM_AUTEUR`) : c'est ce qui vous permet de soumettre et de remettre. En revanche, vous ne pouvez
**jamais valider votre propre travail** : la validation revient au référent de votre affectation (`G_VALIDEUR_LEGITIME`).

Votre accès est créé à votre arrivée par les actions d'accueil : compte Microsoft 365, ajout au groupe `HNCS-RD-Alternants` et
au canal Teams « Alternants » de l'équipe « HNCS R&D », poste de travail et accès techniques (GitLab, environnements).

## 2. Ce que vous voyez et ne voyez pas

D'après la matrice d'accès (spec [7.3](../../spec.md#73-matrice-daccès)) et les permissions posées pour vous par les flux ([7.4](../../spec.md#74-permissions-au-niveau-élément-ou-dossier-posées-par-les-flux)).

| Accès | Ce que c'est |
| --- | --- |
| **Votre** affectation (lecture) | Liste « Affectations » : seulement la vôtre, ouverte à son activation |
| **Vos** livrables (modification) | Liste « Livrables » : seulement ceux dont vous êtes propriétaire |
| **Vos** comptes rendus (modification) | Liste « Comptes rendus de suivi » : seulement les vôtres |
| Dossier du sujet (modification) | `04 - Livrables R&D/SUJ-…/` du sujet de votre affectation |
| Votre dossier de suivi (modification) | `05 - Suivi des alternants/ALT-…/` (plan de travail, consignes), **sans** le sous-dossier `_Evaluations` |
| Vos actions de correction (modification) | Dans « Actions d'intégration et checklists », les actions « Correction livrable » dont vous êtes responsable |
| Vos communications (modification) | Dans « Communications R&D », celles dont vous êtes l'auteur |
| Lecture seule | Offres, Pôles R&D, Référents, Sujets R&D, Registre des modèles R&D, « 03 - Modèles R&D », Communications R&D, Domaines cibles, Ressources techniques, Transitions de statuts |
| Aucun accès | Candidatures et CV, Entretiens, Alternants (fiches), Écoles, Conventions, autres actions de checklist, Bilans d'alternance, Paramètres, Historiques, « 02 - Administration », « 06 - Écoles et partenariats », rapport Power BI |

**Pourquoi ?** Chacun ne voit que ce dont il a besoin (P-04) : les dossiers de recrutement, les données administratives et les
évaluations sont cloisonnés, y compris vis-à-vis de vous. Les autres alternants ne voient pas vos éléments « Livrables » ni
vos comptes rendus ; un alternant affecté au même sujet a en revanche accès au même dossier documentaire du sujet.

Sur vos livrables, certains champs sont **protégés** (P-09) : « Affectation », « Propriétaire (auteur) », « Réviseur
(référent) », **« Échéance »**, cases de la Definition of Done, décision et dates de revue. Sur vos comptes rendus, vous ne
modifiez que les champs de contenu (réalisations, étapes, avancement, risques, blocages…), pas l'affectation, la période,
l'échéance ni les dates. Vous pouvez les lire mais pas les modifier : une
modification est annulée et signalée par **N-92**. Vous ne pouvez pas non plus créer de livrable : ils sont créés par votre
référent ou l'équipe R&D, ou proposés par le système (H-49).

## 3. Vos tâches pas à pas

### 3.1 Trouver votre sujet et votre affectation

1. À l'activation de votre affectation, vous recevez **N-20 « Affectation AFF-… active »** : sujet, objectifs, liens GitLab,
   modèles, dossier de suivi, livrables proposés. Gardez ce message.
2. **Votre affectation** : liste **Affectations** (vous ne voyez que la vôtre) : sujet, référent, dates, objectifs, charge et
   cadence, cadence des comptes rendus, plan de travail.
3. **Votre sujet** : liste **Sujets R&D** (identifiant `SUJ-…`) : description et périmètre, valeur attendue, jalons, critères
   d'acceptation, risques, lien vers le projet GitLab.
4. **Les modèles** : liste « Registre des modèles R&D », vue « Modèles en vigueur », et bibliothèque « 03 - Modèles R&D ».

### 3.2 Voir vos livrables

Liste **Livrables**, vue **« Mes livrables »** : vos livrables non archivés, avec type, échéance, statut et
« Commentaires de revue ». Les statuts possibles :

| Statut | Signification | Qui le pose |
| --- | --- | --- |
| À produire | Prévu, pas commencé | Créé par l'équipe R&D, le référent ou le système |
| En cours | Vous y travaillez | **Vous** (ou le référent) |
| Soumis à revue | Vous demandez la revue | **Vous** |
| En revue | Le référent a commencé sa revue | Référent |
| Corrections demandées | Le référent attend des corrections | Référent |
| Validé | Le référent a validé | Référent |
| Archivé / clôturé | Capitalisé (version de référence) | Système ou référent |
| Suspendu / abandonné | Mis en pause ou arrêté, avec motif | Équipe R&D ou référent |

Rappels automatiques (PA-06) : **N-23** 7 jours puis 2 jours avant l'échéance ; **N-24** dès le lendemain d'une échéance
dépassée (à vous et au référent). Un livrable soumis à revue n'est plus considéré en retard.

### 3.3 Déposer un document

1. Ouvrez la bibliothèque **« 04 - Livrables R&D »**, dossier de votre sujet `SUJ-…`.
2. Déposez votre fichier, puis renseignez ses propriétés :
   - **« Livrable »** : l'identifiant `LIV-…` concerné (indispensable : c'est ce qui rattache le document au livrable) ;
   - **« Type de document »** (POC / démonstrateur, Plan de stratégie, Fiche méthodologie, Document technique…) : nécessaire à
     la capitalisation ;
   - « Date du document ». Laissez « Statut du document » à « Brouillon » : il évolue tout seul (Soumis, Validé, Référence).
3. Pour une nouvelle version, **remplacez le fichier en gardant le même nom** : le versioning conserve les versions
   précédentes (et la version validée est tracée).

Ne déposez **jamais** un document de travail dans la bibliothèque « Documents » créée par défaut avec le site, ni dans les
fichiers de l'équipe Teams : elles ne sont pas protégées par les droits du système et ne doivent contenir aucune donnée
métier (spec [7.2](../../spec.md#72-niveaux-dautorisation), H-44). Votre seul espace de dépôt est le dossier de votre sujet dans « 04 - Livrables R&D » (et votre
dossier de suivi dans « 05 - Suivi des alternants »).

Ce que fait le système (PA-07b) : il complète l'identifiant et le sujet du document et, si le champ « Document (SharePoint) »
du livrable est vide, il le renseigne. **Le dépôt ne soumet pas le livrable** : votre référent n'est pas prévenu tant que vous
n'avez pas posé « Soumis à revue ».

### 3.4 Soumettre à revue

1. Ouvrez le livrable (vue « Mes livrables »). S'il est « À produire », passez-le d'abord en « En cours ».
2. Vérifiez qu'un document est rattaché : « Document (SharePoint) » renseigné ou document déposé avec la colonne « Livrable »
   (contrôle `G_DOCUMENT`).
3. Si le livrable a une composante technique, renseignez « Lien GitLab » (dépôt, merge request, issue ou jalon).
4. Posez **« Soumis à revue »** (`LIV-T03`).

Ce que fait le système (PA-07) : date de dépôt (et de premier dépôt, base du taux de remise à l'heure), document en
« Soumis », **N-25** à votre référent. Sans document, le statut est rétabli et vous recevez **N-90**.

### 3.5 Traiter des corrections

1. Vous recevez **N-26 « Corrections demandées »** avec les commentaires du référent (aussi visibles dans « Commentaires de
   revue », vue « Mes livrables » ; les commentaires successifs s'ajoutent les uns aux autres). Une action « Correction
   livrable » vous est assignée avec une échéance (celle du livrable, ou 5 jours si elle est dépassée) : vous en recevez les
   rappels N-19 et pouvez la consulter, mais vous n'avez pas à la fermer.
2. Repassez le livrable en « En cours » (`LIV-T04`) pendant votre travail (facultatif).
3. Déposez la version corrigée (même nom de fichier, 3.3).
4. Reposez **« Soumis à revue »**.

À la validation, vous recevez **N-27** (valideur, date, version validée) et l'action de correction se ferme toute seule. Pour
un POC ou un plan de stratégie, l'archivage exige les cinq critères de la Definition of Done : fonctionnel et démontrable,
fiche méthodologie rangée, restitution présentée, support de communication prêt, enseignements et limites documentés
(pour un plan, le premier critère est « applicable », H-36). Préparez-les avec votre référent : c'est lui qui coche ces cases,
vous ne pouvez pas le faire (champs protégés, N-92).

### 3.6 Remplir un compte rendu

Les comptes rendus sont créés pour vous au statut « Attendu », selon la cadence de votre affectation (par défaut tous les
14 jours, H-08). L'échéance de remise est la fin de période + 2 jours (`CR.DelaiRemiseJours`). **N-30** vous le rappelle la
veille.

1. Liste **Comptes rendus de suivi**, ouvrez le compte rendu attendu ; posez « En rédaction » (`CR-T02`, facultatif).
2. Remplissez :
   - **« Réalisations de la période »** (obligatoire pour remettre) ;
   - **« Prochaines étapes »** (obligatoire) ;
   - **« Avancement estimé (%) »** (obligatoire, de 0 à 100) ;
   - « État général » (Conforme au plan, Vigilance, En difficulté), « Livrables attendus », « Risques », « Blocages »,
     « Décisions requises », « Soutien attendu du référent ».
3. Posez **« Remis »** (`CR-T03`).

Si l'un des trois champs obligatoires est vide, le statut « Remis » est rétabli et vous recevez **N-90** (contrôle
`G_CR_COMPLET`) : complétez et reposez « Remis ». Votre référent reçoit N-32. S'il pose « À compléter », vous recevez **N-34**
avec son commentaire : complétez puis reposez « Remis ». Quand il valide, vous recevez aussi **N-34** (« Validé »).

Sans remise 3 jours après l'échéance, le compte rendu passe en « Non remis » et votre référent est prévenu (N-31). Vous pouvez
encore le remplir et le remettre.

### 3.7 Signaler un blocage

Dans votre compte rendu, décrivez le problème dans « Blocages », précisez « Soutien attendu du référent » et cochez **« Blocage
signalé »**, puis posez « Remis ». La Direction R&D reçoit **N-33** et le blocage est remonté au Comité R&D. En cas d'urgence,
prévenez aussi directement votre référent : c'est lui (ou l'équipe R&D) qui peut passer l'affectation « À risque » ou
« Bloquée ».

### 3.8 Travailler dans GitLab

GitLab est la référence du code, des issues, des merge requests et des jalons ; SharePoint reste la référence des livrables et
des validations (P-05).

| Élément | Convention |
| --- | --- |
| Projet | Un projet par sujet, dans le groupe `hncs-rd`, nommé `suj-aaaa-nnnn-<slug>` |
| Jalon | Un jalon par livrable technique, titré `LIV-aaaa-nnnn : <titre>`, échéance = échéance du livrable |
| Issue | Modèles « Tache-RD », « Anomalie » ou « Livrable » ; la description cite l'identifiant `LIV-aaaa-nnnn` du livrable concerné |
| Merge request | Modèle « MR-RD » ; la description cite `LIV-aaaa-nnnn` |
| Étiquettes | `rd::sujet::SUJ-aaaa-nnnn`, `rd::livrable::LIV-aaaa-nnnn`, `rd::pole::P1` à `P4`, `rd::type::poc` / `plan` / `doc` |
| Branches et commits | Branches `feature/<objet>` ; messages de commit à l'impératif, en français |

Règles importantes :

- **fusionner une merge request ne valide pas le livrable** : la soumission et la validation se font dans SharePoint ;
- une échéance se modifie **d'abord** dans SharePoint, puis dans le jalon ; la synchronisation quotidienne (lot 5) signale les
  écarts ;
- **aucun secret** (mot de passe, jeton, clé), aucun identifiant d'infrastructure ni donnée personnelle dans le code, les
  issues, les merge requests ou les journaux. Les environnements de démonstration (Proxmox, OVH) sont référencés dans la
  liste « Ressources techniques », sans identifiant.

### 3.9 Proposer une communication

Vous ne créez pas vous-même l'élément : proposez votre idée à votre référent ou à l'équipe R&D, qui crée la communication en
vous désignant « Auteur » (publication LinkedIn HNCS, article…). Vous obtenez alors le droit de la modifier et de la passer
« En revue ». La validation d'une communication externe est réservée à la Direction R&D ou à la Direction Générale ; vous recevez
**N-45** avec la décision.

### 3.10 Fin d'alternance

- Trente jours avant la fin, une checklist de clôture est lancée côté référent et R&D. Attendez-vous à :
  - finaliser, soumettre ou faire suspendre **tous vos livrables** (aucun ne doit rester ouvert) ;
  - ranger votre documentation dans « 04 - Livrables R&D » pour qu'elle soit capitalisée ;
  - un **transfert de connaissances** et un **retour d'expérience** recueilli par la R&D ;
  - le **bilan d'alternance** réalisé par votre référent.
- À la fin effective, vous recevez **N-22 « Affectation terminée »**. Si votre alternance est prolongée, l'équipe R&D ou
  l'administration reporte la date de fin et vous restez « Actif » (`ALT-T08`).
- Vos accès sont retirés selon les règles internes : c'est une action humaine de la checklist de clôture, jamais un retrait
  automatique (H-18).

### 3.11 Erreurs fréquentes

| Ce que vous voyez | Cause | Que faire |
| --- | --- | --- |
| « Soumis à revue » revient à l'ancien statut + N-90 | Aucun document rattaché, ou vous n'êtes pas le propriétaire du livrable | Déposer le document avec la colonne « Livrable », ou renseigner « Document (SharePoint) » |
| « Remis » revient à l'ancien statut + N-90 | « Réalisations », « Prochaines étapes » ou « Avancement » vide | Compléter les trois champs |
| Votre référent n'a rien reçu après votre dépôt | Le dépôt ne soumet pas | Poser « Soumis à revue » |
| Vous ne trouvez pas un livrable dans « Mes livrables » | Vous n'êtes pas indiqué comme « Propriétaire (auteur) » | Demander à votre référent ou à l'équipe R&D |
| Pas de bouton « Supprimer » | Niveau « Contribution sans suppression » (P-07) | Déposer une nouvelle version à la place |
| N-92 « modification d'un champ protégé annulée » | Vous avez modifié le réviseur, une case DoD ou un autre champ protégé | Demander à votre référent |
| « Validé » refusé sur votre propre livrable | Un auteur ne valide jamais son travail (`G_VALIDEUR_LEGITIME`) | Laisser votre référent valider |

## 4. Vos décisions humaines

Vous ne validez rien vous-même, mais deux actions n'appartiennent qu'à vous : **soumettre** un livrable à revue (`LIV-T03`) et
**remettre** un compte rendu (`CR-T03`). Aucun flux ne le fait à votre place : le dépôt d'un document ne soumet jamais le
livrable (PA-07b). Les décisions qui vous concernent (validation, corrections, validation de compte rendu, bilan) sont prises
par votre référent et historisées avec son nom et la date.

## 5. Notifications que vous recevez

| Code | Quand | Que faire |
| --- | --- | --- |
| N-20 | Votre affectation est active | Lire le sujet, les objectifs et les livrables proposés |
| N-23 | Livrable attendu dans 7 puis 2 jours | Préparer la soumission |
| N-24 | Livrable en retard | Soumettre ou voir avec le référent |
| N-26 | Corrections demandées | Corriger et resoumettre (3.5) |
| N-27 | Livrable validé | Aucune action |
| N-29 | Livrable suspendu ou abandonné | Prendre connaissance du motif |
| N-30 | Compte rendu attendu demain | Le remplir et le remettre (3.6) |
| N-34 | Compte rendu à compléter, ou validé | Compléter selon le commentaire du référent ; aucune action s'il est validé |
| N-22 | Affectation terminée | Prendre note (changement de sujet ou fin) |
| N-45 | Décision sur votre communication (validée, refusée ou renvoyée « En rédaction ») | Selon la décision |
| N-19 | Action de correction à échéance | Terminer la correction et resoumettre |
| N-90 | Changement de statut refusé | Lire le motif, corriger |
| N-92 | Modification d'un champ protégé annulée | Laisser le référent agir |

## 6. Vos vues Power BI

Aucune : les alternants n'ont pas accès au rapport Power BI (H-19). Vos repères sont les vues SharePoint « Mes livrables » et
« Comptes rendus de suivi ».

## 7. Rituels de gouvernance

Vous ne recevez pas les synthèses de gouvernance. En revanche, vos blocages signalés, vos livrables en retard et vos comptes
rendus non remis figurent dans la synthèse du **Comité R&D hebdomadaire** (lundi 08:00). La **restitution** d'un POC ou d'un
plan de stratégie (critère DoD 3) peut être présentée à votre référent ou au Comité R&D.

## 8. FAQ

### J'ai déposé mon document, pourquoi mon référent n'a-t-il rien reçu ?

Le dépôt ne soumet pas le livrable. Ouvrez le livrable et posez « Soumis à revue ».

### Puis-je consulter le tableau de bord Power BI ?

Non, ce n'est pas prévu pour les alternants (H-19).

### Comment savoir que mon compte rendu est validé ?

Son statut passe à « Validé » et vous recevez N-34.

### J'ai raté l'échéance d'un compte rendu : est-il trop tard ?

Non : même « Non remis », vous pouvez le remplir et poser « Remis ».

### Mon sujet ou mon référent change : que se passe-t-il ?

L'équipe R&D crée une nouvelle affectation. Vous recevez N-22 pour l'ancienne et N-20 pour la nouvelle. L'historique de
l'ancienne affectation est conservé.

### Où ranger les identifiants de ma machine virtuelle de démonstration ?

Nulle part dans SharePoint, GitLab ou les documents : aucun secret n'y est stocké (spec [10.1](../../spec.md#101-principes)). Suivez les consignes de
l'équipe technique.

### Qui voit mes comptes rendus ?

Votre référent (valideur), l'équipe R&D et la Direction R&D. Pas la Direction Générale, ni les autres alternants.

### Je me suis trompé de fichier : puis-je le supprimer ?

Non (P-07). Déposez la bonne version sous le même nom, ou corrigez la colonne « Livrable » du document.

### Puis-je cocher moi-même les cases de la Definition of Done ?

Non : ce sont des champs protégés, réservés à votre référent (et à l'équipe R&D). Votre case cochée serait décochée (N-92).

### Puis-je ranger mes documents dans « Documents » ou dans l'équipe Teams ?

Non. Ces espaces ne sont pas la référence et ne doivent contenir aucune donnée métier. Utilisez « 04 - Livrables R&D ».

### Comment dois-je nommer ma merge request ?

Utilisez le modèle « MR-RD » et citez l'identifiant `LIV-aaaa-nnnn` du livrable dans la description, avec l'étiquette
`rd::livrable::LIV-aaaa-nnnn`.
