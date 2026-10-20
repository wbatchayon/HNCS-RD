# Guide utilisateur : Équipe R&D

> Public : membres de l'équipe R&D (groupe SharePoint `HNCS-RD-EquipeRD`). La Direction R&D, souvent membre de ce groupe,
> lit aussi le guide [Direction](direction.md). Règles communes (statuts refusés, champs protégés, validations,
> notifications) : voir l'[index des guides](README.md#repères-communs-à-tous-les-guides). Référence : `spec.md` 1.6.0.

## 1. Votre rôle dans le processus

L'équipe R&D est la porte d'entrée et le chef d'orchestre du parcours (RACI [7.6](../../spec.md#76-matrice-raci-et-implémentation) : « R » sur l'enregistrement, l'analyse,
la présélection et l'affectation, sous la responsabilité de la Direction R&D) :

- **Recrutement côté R&D** : vous enregistrez les candidatures reçues, qualifiez l'identité du candidat, les attribuez, les
  analysez et prenez la décision de **présélection** (ou d'écart avec motif). La transmission à l'administration est ensuite
  automatique (PA-02).
- **Affectations** : une fois l'alternant intégré, vous l'affectez à un sujet et à un référent, et vous gérez les
  changements de sujet ou de référent (y compris le sort des livrables encore ouverts).
- **Portefeuille** : vous proposez et suivez les sujets R&D (leur arbitrage revient à la Direction), les livrables, les
  comptes rendus, la fin et l'éventuelle prolongation des alternances.

Groupe SharePoint : `HNCS-RD-EquipeRD` (rôle `RD` dans les transitions de la spec [6](../../spec.md#6-statuts-et-transitions-autorisées)).

## 2. Ce que vous voyez et ne voyez pas

D'après la matrice d'accès (spec [7.3](../../spec.md#73-matrice-daccès)) et les permissions posées par les flux ([7.4](../../spec.md#74-permissions-au-niveau-élément-ou-dossier-posées-par-les-flux)). « Modification » = niveau « HNCS -
Contribution sans suppression » : vous créez et modifiez, vous ne supprimez pas.

| Accès | Listes et bibliothèques |
| --- | --- |
| Modification | Candidatures, « 01 - Recrutement » (CV), Offres, Écoles et établissements, Conventions et partenariats, Échanges avec les écoles, Alternants, Référents, Sujets R&D, Affectations, Livrables, Comptes rendus de suivi, Actions d'intégration et checklists, Bilans d'alternance, Communications R&D, Ressources techniques, Mobilisations commerciales, « 04 - Livrables R&D » |
| Lecture seule | Pôles R&D, Registre des modèles R&D, « 03 - Modèles R&D », Modèles de checklists, Domaines cibles, Paramètres, Transitions de statuts, Historique des statuts, Synchronisation GitLab, « 05 - Suivi des alternants » (hors sous-dossiers `_Evaluations`), « 06 - Écoles et partenariats » |
| Lecture, au cas par cas | Dans « 02 - Administration », le seul sous-dossier `Alternants/ALT-…/Operationnel` (« accès R&D limité aux besoins opérationnels ») ; dans « Entretiens », les entretiens dont vous êtes participant, évaluation comprise (H-28) |
| Aucun accès | Liste Entretiens (en dehors de vos participations), reste de « 02 - Administration », Journal des flux, sous-dossiers d'évaluation `_Evaluations` |

**Pourquoi ces limites ?** Les CV et les données personnelles sont cloisonnés (P-04) :

- la liste **Entretiens** et les grilles d'évaluation restent à l'administration, sauf pour les participants désignés d'un
  entretien, qui le lisent (évaluation comprise) : vous voyez le statut de la candidature et
  recevez N-11 « Entretien réalisé », sans commentaire (H-28) ;
- la bibliothèque **« 02 - Administration »** (contrats, pièces administratives) est réservée à l'administration ;
- les **évaluations** d'un alternant (`05 - Suivi des alternants/ALT-…/_Evaluations`) ne sont visibles que des référents
  concernés et de la Direction R&D ;
- en sens inverse, l'administration ne voit une candidature et son CV **qu'à partir de sa transmission** (H-29).

Les modèles R&D ne sont modifiables que par leur propriétaire et la Direction R&D ([7.4](../../spec.md#74-permissions-au-niveau-élément-ou-dossier-posées-par-les-flux), PA-00F).

## 3. Vos tâches pas à pas

### 3.1 Enregistrer une candidature reçue (site HNCS, LinkedIn, France Travail, spontanée)

Il n'existe **aucune connexion directe** avec LinkedIn ou France Travail (P-06, H-04). Deux façons d'enregistrer :

#### Option A : Saisie manuelle

1. Ouvrez la liste **Candidatures** > **Nouveau**.
2. Renseignez :
   - « Nom et prénom du candidat » (obligatoire) ;
   - « E-mail de contact » : facultatif à la création, mais **obligatoire pour sortir de « Reçue »** ; il sert au contrôle
     anti-doublon, soyez exact ;
   - « Canal d'origine » (obligatoire) : Site HNCS, LinkedIn, France Travail, Candidature spontanée, École / établissement,
     Cooptation, Autre ;
   - « Mode de réception » : laissez « Saisie manuelle » ;
   - « Date de réception » : date réelle de réception (par défaut, la date de saisie).
3. Complétez si possible : « Offre », « Poste ou sujet visé » (si aucune offre), « Type de contrat visé », « École /
   établissement » (choisi dans « Écoles et établissements » ; si l'école n'y figure pas, créez-la d'abord avec son « Nom
   officiel »), « Formation suivie », « Téléphone ».
4. Si vous savez déjà qui analysera, renseignez « Responsable d'analyse ».
5. Enregistrez. Ne touchez pas aux champs remplis par les flux (« Début d'analyse », « Doublon potentiel », dates…).

Ce que fait le système (PA-01a) : il attribue l'identifiant `CAND-AAAA-NNNN`, vérifie les doublons, crée le dossier sécurisé
`01 - Recrutement/AAAA/CAND-…/` (accessible à la R&D et à la Direction R&D uniquement) et y fait pointer « CV (lien
sécurisé) », historise la création (`CAND-T01`) et envoie **N-01** au responsable d'analyse (ou à toute l'équipe R&D). Si un
responsable est renseigné et l'identité complète, la candidature passe d'elle-même à « À analyser » (`CAND-T02`) et le
responsable reçoit **N-03**.

**Dernière étape** : ouvrez le lien « CV (lien sécurisé) » et déposez-y le CV et les pièces, avec « Type de document » = CV
(ou Lettre de motivation, Portfolio…) et « Candidature » = l'identifiant. Ne rangez jamais un CV ailleurs, en particulier
pas dans la bibliothèque « Documents » par défaut du site, lisible par tous (spec [7.2](../../spec.md#72-niveaux-dautorisation)), et ne l'envoyez jamais en pièce
jointe.

#### Option B : Boîte mail R&D

1. Faites arriver le courriel dans le dossier **`Candidatures`** de la boîte partagée R&D : par une règle Outlook (les règles
   sont définies par la R&D) ou en y déplaçant le message. Le formulaire du site HNCS y envoie un courriel balisé
   `[CANDIDATURE-SITE]`.
2. Le flux PA-01b crée la candidature au statut « Reçue », « Mode de réception » = Boîte mail R&D. Le canal est déduit du
   paramètre `Canal.Regles` (linkedin.com → LinkedIn ; francetravail.fr ou pole-emploi.fr → France Travail ;
   `[CANDIDATURE-SITE]` → Site HNCS), sinon « À qualifier ».
3. Identité du candidat :
   - courriel envoyé par le candidat : nom = nom affiché de l'expéditeur, e-mail = son adresse ;
   - **courriel de plateforme (LinkedIn, France Travail)** : l'expéditeur n'est pas le candidat. La fiche est créée avec un nom
     « À qualifier : … » et un e-mail vide, et N-01 vous demande de **qualifier l'identité**.
4. Les pièces jointes `.pdf`, `.doc`, `.docx`, `.odt` sont enregistrées dans le dossier de la candidature (type CV par
   défaut). Une pièce d'un autre format n'est pas enregistrée (la candidature est créée quand même). Un même courriel traité
   deux fois ne crée pas de doublon.
5. **Vérifiez et complétez** la fiche : « Nom et prénom du candidat » et « E-mail de contact » (lus dans le message), « Canal
   d'origine » s'il vaut « À qualifier », « Offre » ou « Poste ou sujet visé », « Responsable d'analyse ».

Tant que l'e-mail est vide ou que le nom commence par « À qualifier », la candidature ne peut pas passer à « À analyser » ni
« En cours d'analyse » (contrôle `G_IDENTITE`, refus N-90). Le contrôle de doublon est refait dès que vous renseignez
l'e-mail.

### 3.2 Attribuer une candidature

1. Ouvrez la vue **« À attribuer »** de la liste Candidatures (statut « Reçue », sans responsable).
2. Vérifiez que l'identité est qualifiée (3.1), puis renseignez « Responsable d'analyse ».
3. Posez le statut « À analyser » (`CAND-T02`) : le responsable reçoit **N-03**. Si vous analysez vous-même, vous pouvez
   passer directement à « En cours d'analyse » (`CAND-T03`).

Sans responsable d'analyse (`G_RESP_ANALYSE`) ou sans identité qualifiée (`G_IDENTITE`), ces deux statuts sont refusés (N-90).

Relance automatique (PA-02b) : une candidature restée en « Reçue », « À analyser » ou « En cours d'analyse » plus de
5 jours (`Delai.RelanceAnalyseJours`) déclenche **N-09** au responsable (ou à l'équipe), une fois par jour au plus, sans
changer le statut.

### 3.3 Traiter un doublon signalé

Le flux compare l'e-mail de la candidature avec les candidatures **en cours** (ni « Intégrée », ni « Non retenue », ni
« Clôturée »). En cas de correspondance, il coche « Doublon potentiel », indique « Doublon de » = l'identifiant de l'autre
candidature et le signale dans N-01. **Il ne fusionne et ne clôture jamais rien** : c'est à vous de décider.

1. Ouvrez la vue **« Doublons potentiels »**.
2. Comparez les deux candidatures (même personne ? même demande ?).
3. Si c'est un vrai doublon : sur la candidature à abandonner, posez « Clôturée » avec « Motif codifié » = Doublon et, dans
   « Commentaire de motif », l'identifiant de la candidature conservée. Si le nouveau message apporte une pièce utile (CV à
   jour), déposez-la dans le dossier de la candidature conservée.
4. Si ce n'est pas un doublon (faux positif) : cochez **« Doublon vérifié (faux positif) »** sur la candidature signalée. Elle
   sort de la vue « Doublons potentiels » et de l'indicateur « Doublons signalés » ; le signalement initial reste tracé.
   Poursuivez normalement l'analyse des deux.

### 3.4 Analyser une candidature

1. Ouvrez la vue **« Mes analyses »** (vos candidatures en « Reçue », « À analyser », « En cours d'analyse »).
2. Posez le statut « En cours d'analyse » : la date « Début d'analyse » est renseignée par le flux.
3. Consultez le CV par le lien « CV (lien sécurisé) ».
4. Rédigez votre « Avis de la R&D » (confidentiel) et, si utile, les « Critères d'évaluation » et la « Prochaine action ».
5. Si vous avez déjà une idée de l'accueil, renseignez « Pôle pressenti », « Référent pressenti », « Sujet pressenti » (ils
   seront exigés plus tard pour l'intégration).

### 3.5 Présélectionner (transmettre à l'administration)

1. Vérifiez que la candidature est en « En cours d'analyse » et que l'« Avis de la R&D » est rempli (`G_AVIS_ANALYSE`).
2. Posez le statut **« Présélectionnée »** (`CAND-T04`). C'est votre décision : le système ne la prend jamais.

Ce que fait le système (PA-02) : il renseigne « Date de décision de présélection » et « Décision de présélection »
(Présélectionnée), ouvre l'accès à l'élément et au dossier CV à l'administration (toute l'équipe ou le seul destinataire,
selon le paramètre `Recrutement.PartageTransmission`, H-45), renseigne « Destinataire administration », envoie **N-05** (lien
sécurisé ; votre avis reste dans l'élément, il n'est jamais recopié dans le message), renseigne « Date de transmission à
l'administration », puis passe automatiquement la candidature à **« Transmise à l'administration »** (`CAND-T05`).

Si la candidature reste bloquée en « Présélectionnée », le partage a échoué : l'erreur est journalisée et le support est
prévenu (N-99) ; la reprise ne crée pas de doublon.

### 3.6 Écarter une candidature avec motif

1. Depuis « En cours d'analyse », remplissez l'« Avis de la R&D ».
2. Choisissez un « Motif codifié » : Profil hors cible, Prérequis non satisfaits, Poste pourvu, Candidature incomplète, Autre…
   et précisez au besoin le « Commentaire de motif » (confidentiel).
3. Posez le statut **« Non retenue »** (`CAND-T06`).

Sans motif, SharePoint refuse l'enregistrement (règle de validation). Sans avis, le statut est rétabli (N-90). Ensuite :
dates, « Décision de présélection » = Écartée, **N-06** à l'équipe R&D et, l'information automatique du candidat étant
désactivée (`Fonction.InformationCandidatAuto` = Non, H-09), **N-08** « Informer le candidat » au responsable d'analyse.

### 3.7 Informer le candidat

Aucun message n'est envoyé automatiquement au candidat tant que les textes et l'information RGPD ne sont pas validés (H-09).

1. Ouvrez la vue **« Candidat à informer »** (candidatures « Non retenue » ou « Clôturée » non encore informées).
2. Informez le candidat par le moyen habituel.
3. Cochez « Candidat informé de l'issue » et renseignez « Date d'information du candidat ». C'est la personne qui informe qui
   coche (H-09). Pour un refus décidé par l'administration, N-08 vous est aussi adressé : convenez avec elle de qui informe.

### 3.8 Clôturer une candidature pour un autre motif

Depuis n'importe quel statut non terminal, posez **« Clôturée »** (`CAND-T15`) avec un « Motif codifié » : Désistement du
candidat, Doublon, Offre annulée, Candidature incomplète, Formalités non abouties, Autre. Le flux renseigne la date de clôture
et envoie N-06. Une candidature « Non retenue » ou « Clôturée » ne peut être rouverte que par la **Direction R&D**
(`CAND-T16`, H-07).

### 3.9 Suivre une candidature après transmission

À partir de « Transmise à l'administration », c'est l'administration qui fait avancer le statut (entretien, décision finale,
y compris un refus sans entretien, formalités, intégration). Vous suivez :

- la vue **« Transmises à l'administration »** (statut, date de transmission, destinataire) ;
- **N-11** quand un entretien est réalisé (statut seulement, sans commentaire) ;
- **N-13** quand la candidature est retenue (si vous êtes responsable d'analyse), **N-06** si elle est non retenue.

Pendant les formalités, deux actions de la checklist vous reviennent en tant que responsable d'analyse (liste « Actions
d'intégration et checklists », vue **« Mes actions »**) :

| Action | Bloquante | Ce qu'il faut faire |
| --- | --- | --- |
| FORM-05 Confirmer le pôle, le référent pressenti et le sujet pressenti | Oui | Renseigner « Pôle pressenti », « Référent pressenti », « Sujet pressenti » sur la candidature, puis passer l'action à « Terminée » avec, dans « Preuve / lien », le lien de la candidature |
| FORM-06 Informer le référent pressenti de l'arrivée | Non | Prévenir le référent, puis passer l'action à « Terminée » |

Pour les formalités, vous pouvez passer votre action à « Terminée » ; en revanche, seule l'administration peut décocher
« Bloquante pour l'étape » ou passer une action bloquante en « Non applicable » (`G_ACTION_FORMALITE`) ; sinon la valeur est
rétablie (N-92). Une action
bloquante non terminée avec preuve empêche l'intégration (`G_INTEGRATION`). Rappel N-19 deux jours avant l'échéance. À
l'intégration, vous recevez **N-16** (date de début, pôle, référent, liens vers la fiche et le dossier de suivi), et l'action
d'accueil **ACC-05 « Créer l'affectation »** est générée.

### 3.10 Proposer un sujet R&D

1. Liste **Sujets R&D** > **Nouveau** : statut initial « Proposé » (`SUJ-T01`).
2. Champs obligatoires : « Titre du sujet », « Type de sujet » (POC / démonstrateur, Plan de stratégie, Communication,
   Partenariat / talents, Autre), « Pôle ».
3. Champs recommandés : « Description et périmètre », « Valeur attendue », « Objectifs », « Livrables attendus »,
   « Priorité », « Référent du sujet », « Validateur », « Jalons », « Critères d'acceptation », « Risques et dépendances »,
   « Début prévu » et « Fin prévue » (la fin doit suivre le début), **« Domaines cibles couverts »** (base de l'indicateur de
   couverture des domaines cibles).
4. Quand le sujet est prêt pour l'arbitrage, posez **« À arbitrer »** (`SUJ-T02`) : la Direction R&D reçoit **N-47**.

L'**arbitrage** est une décision de la Direction R&D ou de la Direction (PA-14) : « Priorisé » (GO), « Suspendu » ou
« Abandonné » (NO-GO, toujours avec « Motif de décision », H-26). Vous recevez N-47 avec la décision. Ensuite, vous pouvez
poser « En cours » (`SUJ-T04`, depuis « Priorisé » ou « Bloqué »), « Bloqué » (`SUJ-T05`, N-47 à la Direction R&D) et
« Terminé » (`SUJ-T08`).

Projet GitLab : à la demande du référent du sujet, un membre de l'équipe R&D propriétaire du groupe GitLab `hncs-rd` lance le
script de création de projet (spec [10.3](../../spec.md#103-composants-livrés)), avec son jeton personnel (jamais stocké) ; il reporte l'URL et l'identifiant dans « Projet GitLab » et « ID projet GitLab ». Nom
du projet : `suj-aaaa-nnnn-<slug>` dans le groupe `hncs-rd`.

### 3.11 Créer et activer une affectation

1. Vérifiez sur la fiche **Alternants** que « Compte Microsoft 365 » est renseigné (action d'accueil ACC-01) : c'est ce compte
   qui reçoit les droits sur le sujet et devient propriétaire des livrables. Sans lui, l'activation est refusée
   (`G_AFFECTATION_COMPLETE`, N-90). S'il change plus tard, les droits sont rejoués automatiquement (PA-04).
2. Liste **Affectations** > **Nouveau** :
   - obligatoires : « Alternant », « Sujet », « Date de début » ; « Référent » est exigé pour activer ;
   - « Date de fin », « Objectifs », « Charge et cadence » (ex. « 3 j/semaine »), « Plan de travail » (lien) ;
   - « Cadence des comptes rendus » : laissez « Selon paramètre global » (Quinzaine, H-08) ou choisissez Hebdomadaire,
     Mensuelle, Par jalon ;
   - laissez « Affectation remplacée » vide pour une première affectation.
3. Enregistrez : statut « À préparer » (`AFF-T01`), libellé automatique `ALT-…, SUJ-…`.
4. Posez **« Active »** (`AFF-T02`). Contrôle `G_AFFECTATION_COMPLETE` : alternant, sujet, référent, date de début
   renseignés ; alternant « À intégrer » ou « Actif » avec « Compte Microsoft 365 » renseigné ; référent « Actif » dans la
   liste Référents.

Ce que fait le système (PA-05) : il **verrouille** l'alternant, le sujet, le référent et la date de début ; crée le dossier
`04 - Livrables R&D/SUJ-…/` et y donne accès à l'alternant ; lui donne la lecture sur l'affectation ; donne au référent l'accès
au dossier de suivi et à la fiche ; met à jour le **« Référent principal »** de la fiche alternant (dérivé de l'affectation
active la plus récente, ne le modifiez pas à la main, la modification serait annulée avec N-91) ; propose les livrables « À
produire » issus des modèles **approuvés** du registre (propriétaire = compte de l'alternant, réviseur = référent) ; crée le premier compte rendu « Attendu » (à partir du lot 3, sauf
cadence « Par jalon ») ; envoie **N-20** à l'alternant et au référent.

Aucun livrable n'est proposé tant que les modèles du « Registre des modèles R&D » ne sont pas « Approuvé » (registre initial en
« Brouillon »). En attendant, créez les livrables vous-même (un alternant ne peut pas en créer, H-49) : liste **Livrables** >
**Nouveau** (« Titre du livrable », « Affectation », « Type de livrable », « Propriétaire (auteur) » = l'alternant,
« Échéance »). Le « Réviseur » est par défaut le référent de l'affectation ; seul ce référent ou un membre de la Direction R&D
peut être désigné : toute autre désignation est refusée dès l'enregistrement (P-09, N-92).

### 3.12 Remplacer une affectation (changement de sujet ou de référent)

Règle P-03 : un changement de sujet ou de référent **crée une nouvelle affectation** et n'écrase jamais l'ancienne. Si vous
modifiez l'alternant, le sujet, le référent ou la date de début d'une affectation active, le flux rétablit les valeurs et vous
envoie **N-91** « modification annulée ».

1. Liste **Affectations** > **Nouveau** : même alternant, nouveau sujet et/ou nouveau référent, « Date de début » = date du
   changement, **« Affectation remplacée »** = l'identifiant de l'affectation actuelle.
2. Posez « Active ».
3. Le système termine l'ancienne : « Date de fin » = veille du début de la nouvelle (jamais avant le début de l'ancienne),
   « Motif de fin » = « Remplacée par
   AFF-… », statut « Terminée » (`AFF-T05`). Aucun autre champ de l'ancienne n'est modifié. Le référent principal de la fiche
   est mis à jour. **N-22** (ancienne affectation, à l'alternant, au référent et à vous) liste les livrables encore ouverts ;
   **N-20** annonce la nouvelle.
4. **Décidez pour chaque livrable encore ouvert** de l'ancienne affectation (décision humaine, aucun transfert automatique,
   H-51) :
   - **le poursuivre** : créez un livrable dans la nouvelle affectation avec **« Livrable d'origine »** = l'ancien livrable,
     puis passez l'ancien à « Suspendu / abandonné » avec le motif « Transféré vers LIV-… » ;
   - **le clore** normalement (revue et validation, ou suspension motivée).
5. L'ancienne affectation ne peut passer à « Clôturée » (`AFF-T06`) que lorsqu'aucun de ses livrables n'est ouvert
   (`G_LIVRABLES_CLOS`).

La vue **« Historique des affectations »** montre la succession (colonne « Affectation remplacée »).

Autres changements d'état d'une affectation :

| Statut | Qui | Condition / effet |
| --- | --- | --- |
| « À risque » / « Bloquée » (`AFF-T03`) | Vous ou le référent | N-21 à la Direction R&D |
| Retour à « Active » (`AFF-T04`) | Vous ou le référent | - |
| « Terminée » (`AFF-T05`) | Vous | « Date de fin » obligatoire (`G_DATE_FIN`) ; N-22 avec les livrables encore ouverts |
| « Clôturée » (`AFF-T06`) | Vous | Aucun livrable ouvert (`G_LIVRABLES_CLOS`) |
| « À préparer » → « Clôturée » (`AFF-T07`) | Vous | Affectation abandonnée avant activation |

### 3.13 Suivre les livrables et les comptes rendus

- **Livrables** : vues « Livrables en cours » et « En retard » (case « En retard » recalculée chaque jour par PA-06).
  Vous pouvez suspendre ou abandonner un livrable : statut « Suspendu / abandonné » (`LIV-T09`) avec « Motif de suspension /
  abandon » (obligatoire) et « Impacts et suite envisagée » ; N-29 au propriétaire et au réviseur ; réactivation possible
  (`LIV-T10`). Avec la Direction R&D, vous êtes seuls habilités à modifier les champs protégés d'un livrable (affectation,
  propriétaire, réviseur, échéance…, P-09 ; le réviseur légitime peut aussi changer l'échéance et la Definition of Done). La **validation** reste réservée au référent de l'affectation désigné réviseur.
- **Comptes rendus de suivi** : vues « Comptes rendus ouverts », « Non remis » et « Blocages signalés ». Pour une affectation à
  cadence « Par jalon », aucun compte rendu n'est créé automatiquement : c'est à vous de les créer (`CR-T01`).

### 3.14 Suivre le portefeuille

| Besoin | Où regarder |
| --- | --- |
| Sujets en cours, par pôle et priorité | Sujets R&D, vue « Portefeuille » |
| Sujets à arbitrer ou bloqués | Sujets R&D, vue « À arbitrer » |
| Affectations en cours, sans référent | Affectations, vues « Affectations en cours » et « Sans référent » |
| Alternants actifs, fins à venir (45 jours) | Alternants, vues « Alternants actifs » et « Fins à venir » |
| Actions de checklist en retard | Actions d'intégration et checklists, vue « En retard » |
| Transitions refusées | Historique des statuts, vue « Transitions refusées » |
| Indicateurs | Power BI, pages 3, 4, 7 et 8 (section 6) |

### 3.15 Fin d'alternance et prolongation

1. Trente jours avant la date de fin (`Fin.AnticipationJours`), PA-09b passe l'alternant en « Fin planifiée », génère la
   checklist « Clôture d'alternance » (CLO-01 à CLO-07), crée le bilan « À réaliser » et vous envoie **N-35**. Vous pouvez
   aussi poser « Fin planifiée » à la main (`ALT-T04`).
2. Votre action : **CLO-04 « Recueillir le retour d'expérience de l'alternant »**.
3. À la fin effective : sur la fiche **Alternants**, renseignez « Date de fin réelle » et « Motif de fin », puis posez
   **« Terminé »** (`ALT-T05`, décision humaine, avec l'administration). Sans date de fin réelle, l'enregistrement est refusé.
   Le système termine les affectations encore actives (N-22) et envoie N-37.
4. « Clôturé » (`ALT-T06`) n'est accepté que si les actions bloquantes de clôture sont terminées (ou non applicables
   justifiées) et si un bilan « Réalisé » existe (`G_CLOTURE_ALTERNANCE`).

**Prolongation** : si l'alternance est prolongée alors que l'alternant est en « Fin planifiée », reportez « Date de fin
prévue » sur la fiche puis reposez **« Actif »** (`ALT-T08`). Le statut n'est accepté que si la nouvelle date de fin est à
plus de 30 jours (`G_DATE_FIN_REPORTEE`). Les actions de clôture encore ouvertes voient leur échéance recalculée sur la
nouvelle date de fin ; le bilan « À réaliser » est conservé ; la fin sera de nouveau détectée 30 jours avant la nouvelle date.

Le **retrait des accès** n'est jamais automatique : c'est l'action CLO-06 de la checklist (H-18). Suspension : « Suspendu »
(`ALT-T03`, N-36), reprise par « Actif ».

### 3.16 Communications et mobilisations

- **Communications R&D** : créez l'élément (« Titre de la communication », « Canal », « Auteur », un alternant peut être
  auteur -, « Communication externe », « Livrable source », « Sujet », « Date prévue », « Approbateur proposé »,
  « Autorisations des tiers »). Parcours : Idée / À préparer → En rédaction → **En revue** (N-44 à l'approbateur proposé s'il
  est membre de la Direction R&D ou de la Direction, sinon à la Direction R&D) → **Validée** (Direction R&D ou Direction
  Générale uniquement, H-11) → Programmée (« Date prévue » obligatoire) → Publiée (« Date de publication » et, pour une
  communication externe, « URL de publication » obligatoires). Aucune validation sans autorisations des tiers « Obtenue » ou
  « Non requise ».
- **Mobilisations commerciales** (lot 4) : chaque fois qu'un livrable est utilisé en rendez-vous client, appel d'offres,
  avant-vente ou démonstration, créez un élément (« Contexte de la mobilisation », « Livrable mobilisé », « Date », « Type »).
  Il alimente l'indicateur « Mobilisations commerciales ».

### 3.17 Erreurs fréquentes

| Ce que vous voyez | Cause | Que faire |
| --- | --- | --- |
| Message à l'enregistrement « Motif obligatoire pour « Non retenue » ou « Clôturée »… » | Règle de validation de la liste Candidatures | Choisir un « Motif codifié », enregistrer à nouveau |
| « À analyser » ou « En cours d'analyse » refusé (N-90) | Identité non qualifiée (`G_IDENTITE`) ou responsable manquant | Renseigner nom réel et e-mail, puis le responsable |
| Le statut revient tout seul à l'ancien et vous recevez N-90 | Transition refusée : chemin non prévu (ex. « À analyser » → « Présélectionnée » : il faut passer par « En cours d'analyse »), avis manquant, statut réservé à un autre rôle (ex. « Retenue » = administration, « Priorisé » = Direction) | Lire le motif dans N-90, corriger, reposer le statut |
| N-91 « modification annulée » | Champ verrouillé d'une affectation active, ou « Référent principal » modifié à la main | Créer une nouvelle affectation (3.12) |
| N-92 « modification d'un champ protégé annulée » | Champ réservé à un autre rôle (ex. clôture d'une formalité dont vous n'êtes pas responsable) | Demander à la personne habilitée |
| Message « La date de fin doit suivre la date de début » | Règle de validation (affectation, alternant, sujet) | Corriger les dates |
| Le statut affiché change puis revient en quelques secondes | Contrôle a posteriori (H-17) | Actualiser la page ; consulter N-90 |
| Pas de bouton « Supprimer » | Niveau « Contribution sans suppression » (P-07) | Clôturer avec un motif |

## 4. Vos décisions humaines

| Décision | Statut posé | Trace |
| --- | --- | --- |
| Pertinence du CV (présélection) | Candidature « Présélectionnée » (`CAND-T04`) | « Date de décision de présélection », « Décision de présélection », « Avis de la R&D », historique |
| Refus après analyse | Candidature « Non retenue » (`CAND-T06`) | Motif codifié, avis, dates |
| Clôture pour un autre motif | Candidature « Clôturée » (`CAND-T15`) | Motif codifié, « Date de clôture » |
| Affectation d'un alternant à un sujet et un référent, remplacement | Affectation « Active » (`AFF-T02`) | Empreinte de verrouillage, « Affectation remplacée », historique (y compris le changement de référent principal) |
| Sort des livrables ouverts lors d'un remplacement | Nouveau livrable avec « Livrable d'origine », ancien « Suspendu / abandonné » | Motif « Transféré vers LIV-… », historique |
| Suspension ou abandon d'un livrable | Livrable « Suspendu / abandonné » (`LIV-T09`) | Motif, impacts et suite envisagée |
| Fin effective d'une alternance (avec l'administration) ; prolongation | Alternant « Terminé » (`ALT-T05`) ; « Actif » depuis « Fin planifiée » (`ALT-T08`) | « Date de fin réelle », « Motif de fin », nouvelle date de fin |

Vous **proposez** les sujets ; leur **arbitrage** (Priorisé, Suspendu, Abandonné) appartient à la Direction R&D ou à la
Direction. Chaque décision est inscrite dans **« Historique des statuts »** (identifiant, statut avant / demandé, acteur, date,
origine « Humain », résultat), en plus du versioning de l'élément. Vous consultez cet historique en lecture (vues
« Historique récent » et « Transitions refusées »).

## 5. Notifications que vous recevez

| Code | Quand | Que faire |
| --- | --- | --- |
| N-01 | Nouvelle candidature (à vous si responsable, sinon à l'équipe) ; pour un courriel de plateforme, demande de qualification | Qualifier l'identité, vérifier le canal, attribuer, traiter le doublon signalé |
| N-03 | Une candidature vous est attribuée (ou rouverte) | L'analyser (3.4) |
| N-06 | Candidature non retenue ou clôturée | Informer le candidat si besoin (3.7) |
| N-08 | Tâche « Informer le candidat » (responsable d'analyse) | Informer, cocher « Candidat informé de l'issue » |
| N-09 | Relance : candidature sans traitement depuis 5 jours | Faire avancer l'analyse |
| N-11 | Entretien réalisé (statut seulement) | Aucune action ; suivre la décision |
| N-13 | Candidature retenue (responsable d'analyse) | Préparer les actions FORM-05 et FORM-06 |
| N-16 | Intégration confirmée | Préparer l'affectation (ACC-05) |
| N-19 | Action de checklist à échéance (si vous en êtes responsable) | Terminer l'action avec sa preuve |
| N-22 | Affectation terminée, avec la liste des livrables encore ouverts | Décider pour chaque livrable (3.12) |
| N-47 | Sujet « Priorisé », « Suspendu » ou « Abandonné » (décision de la Direction, avec motif) | Lancer ou réorienter les travaux |
| N-35 | Fin d'alternance planifiée | Lancer le retour d'expérience (CLO-04) |
| N-36 | Alternant suspendu | Prendre note, adapter les affectations |
| N-37 | Fin d'alternance enregistrée | Suivre la checklist de clôture |
| N-45 | Décision sur une communication dont vous êtes l'auteur (validée, refusée ou renvoyée « En rédaction ») | Programmer, publier ou retravailler |
| N-90 | Changement de statut refusé | Lire le motif, corriger |
| N-91 / N-92 | Modification annulée (champ verrouillé ou protégé) | Passer par la bonne procédure |

## 6. Vos vues Power BI

Rôle Power BI **PilotageRD** (Direction R&D et équipe R&D) : aucune restriction de lignes, accès aux 8 pages (spec [9.7](../../spec.md#97-pages-du-rapport)).

| Page | Usage pour vous |
| --- | --- |
| 1. Vue exécutive | Indicateurs clés, sujets actifs, objectifs indicatifs, date de dernière actualisation |
| 2. Recrutement | Candidatures par canal, statut, mois ; délais de présélection et de traitement ; entonnoir ; candidatures en attente (plus de 10 jours) ; motifs agrégés |
| 3. Effectifs et encadrement | Alternants actifs, affectations sans référent ou incomplètes, charge des référents |
| 4. Projets et livrables | Livrables par statut, retards, remise à l'heure, validation au premier passage, capitalisation, comptes rendus manquants, écarts GitLab |
| 5. Établissements et partenariats | Écoles, bilans, partenariats à évaluer, conventions à renouveler, prochaines actions école |
| 6. Communications et valorisation | Communications externes publiées, livrables valorisés, mobilisations |
| 7. Comité R&D | Échéances à 14 jours, blocages, affectations à risque, sujets bloqués, actions en retard |
| 8. Qualité des données | Affectations incomplètes, livrables sans modèle, doublons signalés, transitions refusées |

Le rapport n'importe aucune donnée personnelle, hormis le nom de l'alternant, absent de tous les visuels et masqué pour les publics sans
accès SharePoint aux fiches alternants (Direction, Relation écoles), ni aucune donnée confidentielle (pas de CV, d'avis, de
commentaire) ; aucun visuel n'affiche de nom : les tableaux montrent des identifiants (`ALT-…`, `AFF-…`). Pour les noms, utilisez les vues SharePoint. Actualisation
quotidienne à 06:00.

## 7. Rituels de gouvernance

| Rituel | Fréquence | Ce que prépare le système | Votre contribution |
| --- | --- | --- | --- |
| Comité R&D (Direction R&D, équipe R&D, référents, H-53) | Hebdomadaire (lundi 08:00, `Gouvernance.ComiteJourHeure`) | Synthèse PA-11 (N-42) envoyée à la Direction R&D et publiée dans le canal Teams « Comité R&D », dont vous êtes membre : livrables en retard escaladés (plus de 7 jours), échéances à 14 jours, comptes rendus non remis, blocages, affectations à risque ou bloquées, sujets bloqués ou à arbitrer, conventions à renouveler, écoles à évaluer, communications en revue, candidatures en attente (en nombre par statut) | Mettre à jour statuts et échéances **avant** le lundi matin (la synthèse est calculée à l'envoi) ; préparer les sujets « À arbitrer » ; page Power BI 7 |
| Point Direction | Mensuel (1er lundi) | Synthèse agrégée N-43 envoyée à la Direction R&D, qui la relit et la transmet à la Direction Générale | Fiabiliser les données (page 8 « Qualité des données ») |
| Revue de gouvernance | Trimestrielle (1er lundi du trimestre) | Synthèse agrégée N-43, même circuit | Idem |

## 8. FAQ

### Peut-on récupérer automatiquement les candidatures LinkedIn ou France Travail ?

Non. Aucune API n'est utilisée (P-06, H-04). Saisissez la candidature (3.1, option A) avec le bon « Canal d'origine », ou
faites arriver le courriel dans le dossier `Candidatures` de la boîte R&D (option B) puis qualifiez l'identité.

### Pourquoi une candidature reçue de LinkedIn s'appelle-t-elle « À qualifier : … » ?

Le courriel vient de la plateforme, pas du candidat : le système ne devine pas son identité. Lisez le message, renseignez le
nom et l'e-mail du candidat ; l'analyse est bloquée tant que ce n'est pas fait (`G_IDENTITE`).

### J'ai posé « Présélectionnée » et la candidature est revenue à son statut précédent. Pourquoi ?

Soit la candidature n'était pas en « En cours d'analyse » (seul point de départ autorisé), soit l'« Avis de la R&D » était
vide. Le motif est indiqué dans N-90. Votre avis saisi est conservé : corrigez et reposez le statut.

### L'administration me dit ne pas voir une candidature : pourquoi ?

C'est normal tant qu'elle n'est pas transmise (H-29). Vérifiez qu'elle est bien en « Transmise à l'administration ». Si elle
est restée en « Présélectionnée », le partage a échoué et le support a été prévenu automatiquement (N-99).

### Puis-je lire le compte rendu d'entretien ?

Seulement si vous y avez participé : les participants désignés lisent l'entretien, évaluation comprise (H-28). Les autres
entretiens restent réservés à l'administration. Vous voyez le statut de la candidature et recevez N-11.

### Je me suis trompé de statut ou de candidat. Puis-je supprimer ?

Non (P-07). Clôturez avec le motif adapté (« Doublon », « Autre » + commentaire). Pour rouvrir une candidature « Non retenue »
ou « Clôturée », demandez à la Direction R&D (`CAND-T16`).

### Pourquoi aucun livrable n'a été proposé à l'activation de l'affectation ?

Seuls les modèles « Approuvé », marqués « Livrable proposé automatiquement » et applicables au type du sujet génèrent des
livrables. Tant que le registre est en « Brouillon », créez les livrables manuellement (3.11).

### Comment changer le référent d'un alternant ?

Jamais en modifiant l'affectation active ni le « Référent principal » de la fiche (N-91). Créez une nouvelle affectation qui
remplace l'ancienne (3.12) : le référent principal suit automatiquement.

### Puis-je passer moi-même un sujet en « Priorisé » ?

Non : l'arbitrage (Priorisé, Suspendu, Abandonné) est réservé à la Direction R&D et à la Direction (`SUJ-T03`, `SUJ-T06`,
`SUJ-T07`). Posez « À arbitrer » pour le leur soumettre.

### Un candidat déjà refusé postule de nouveau : que faire ?

Le contrôle de doublon ignore les candidatures terminées : enregistrez une nouvelle candidature. Si vous préférez reprendre
l'ancienne, seule la Direction R&D peut la rouvrir.
