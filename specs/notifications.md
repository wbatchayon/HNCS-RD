# Sous-spécification — Catalogue des notifications

> Alignée sur `spec.md` § 7.5 et § 8 (qui prévaut). Lue par `tools/spec_extract.py`.

## Règles communes

- **Expéditeur** : boîte partagée `Destinataires.BoiteRD`. **Objet** : `[HNCS-R&D][N-xx] …`.
- **Canal** : `Mail` (courriel), `Teams` (message du bot Flow, uniquement si `Fonction.NotificationsTeams` = Oui et destinataire nominatif), `Mail+Teams`.
- Toute notification contient un **lien vers l'élément SharePoint source** et, si utile, vers le dossier documentaire. **Jamais** de pièce jointe CV ou document confidentiel.
- **Données exposées** : `ID` = identifiants `IdHNCS` et statuts ; `NOM` = nom de la personne concernée (alternant, candidat) ; `COMM` = commentaires de revue destinés à leur auteur. Les notifications vers des groupes larges (G_DIR, comité) sont limitées à `ID` et agrégats.
- Le texte exact des messages au candidat (N-02, N-07) doit être validé avant activation (H-09).
- Les modèles HTML sont livrés dans `flows/templates/` sous le nom `N-xx.html`.

### NOTIFICATIONS

| Code | Flux | Destinataires | Canal | Objet | Contenu | Données exposées |
| --- | --- | --- | --- | --- | --- | --- |
| N-01 | PA-01 | Responsable d'analyse, sinon G_RD | Mail+Teams | Nouvelle candidature {IdHNCS} | Canal, date, poste visé, signalement de doublon éventuel, lien | ID ; NOM |
| N-02 | PA-01 | Candidat | Mail | Accusé de réception de votre candidature | Message validé (désactivé par défaut) | NOM |
| N-03 | PA-02 | Responsable d'analyse | Mail+Teams | Candidature {IdHNCS} à analyser | Lien, délai de relance | ID ; NOM |
| N-04 | PA-02 | Destinataires.Administration | Mail | Candidature {IdHNCS} : aucun entretien planifié | Retour au statut « Transmise à l'administration » | ID ; NOM |
| N-05 | PA-02 | Destinataires.Administration | Mail+Teams | Profil présélectionné {IdHNCS} transmis | Lien sécurisé vers la candidature et le dossier CV (accès ouvert par PA-02) ; l'avis de la R&D est consultable dans l'élément, **jamais recopié** dans le message | ID ; NOM |
| N-06 | PA-02 | G_RD (et Destinataires.Administration si après entretien) | Mail | Candidature {IdHNCS} {statut} | Statut, motif codifié, rappel d'informer le candidat | ID |
| N-07 | PA-02 | Candidat | Mail | Suite donnée à votre candidature | Message validé (désactivé par défaut) | NOM |
| N-08 | PA-02 | Responsable d'analyse | Mail | Informer le candidat {IdHNCS} | Tâche : informer le candidat puis cocher « Candidat informé » | ID ; NOM |
| N-09 | PA-02b | Responsable d'analyse, sinon G_RD | Mail | Relance : candidature {IdHNCS} sans traitement | Ancienneté en jours, lien | ID |
| N-10 | PA-03b | Participants de l'entretien | Mail+Teams | Rappel : entretien {IdHNCS} le {date} | Date, modalité, lien de réunion | ID ; NOM |
| N-11 | PA-03 | G_RD, responsable d'analyse | Mail | Entretien réalisé pour {IdHNCS} | Statut de la candidature uniquement, **sans** commentaire d'évaluation | ID |
| N-12 | PA-03 | Destinataires.Administration | Mail | Décision attendue pour {IdHNCS} | Lien vers la candidature | ID ; NOM |
| N-13 | PA-03 | Destinataires.Administration, responsable d'analyse | Mail+Teams | Candidature {IdHNCS} retenue | Rappel : autoriser le lancement des formalités | ID ; NOM |
| N-14 | PA-03b | Destinataires.Administration | Mail | Résultat d'entretien à saisir ({IdHNCS}) | Lien vers l'entretien | ID |
| N-15 | PA-04 | Destinataires.Administration | Mail | Formalités lancées pour {IdHNCS} | Liste des actions, responsables, échéances | ID ; NOM |
| N-16 | PA-04 | G_RD, référent pressenti, Destinataires.Administration | Mail+Teams | Intégration confirmée : {IdAlternant} | Date de début, pôle, référent, liens vers la fiche et le dossier de suivi | ID ; NOM |
| N-17 | PA-04 | Destinataires.Administration | Mail | Formalités complètes pour {IdHNCS} | Invitation à confirmer l'intégration (action humaine) | ID |
| N-18 | PA-04b | Référent principal | Mail+Teams | {IdAlternant} démarre aujourd'hui | Lien vers la fiche | ID ; NOM |
| N-19 | PA-04b | Responsable de l'action | Mail+Teams | Action {IdHNCS} à échéance le {date} | Description, preuve attendue | ID |
| N-20 | PA-05 | Alternant, référent | Mail+Teams | Affectation {IdHNCS} active | Sujet, objectifs, liens GitLab, modèles, dossier de suivi, livrables proposés | ID ; NOM |
| N-21 | PA-05 | G_DRD | Mail | Affectation {IdHNCS} {statut} | Statut, lien | ID |
| N-22 | PA-05 ; PA-09 | Alternant, référent, G_RD | Mail | Affectation {IdHNCS} terminée | Date et motif de fin ; liste des livrables encore ouverts, à poursuivre (nouveau livrable avec « Livrable d'origine »), suspendre ou clore — décision de la R&D | ID |
| N-23 | PA-06 | Propriétaire du livrable | Mail+Teams | Rappel : livrable {IdHNCS} attendu le {date} | Échéance, lien | ID |
| N-24 | PA-06 | Propriétaire, réviseur | Mail+Teams | Livrable {IdHNCS} en retard | Jours de retard, lien | ID |
| N-25 | PA-07 | Réviseur | Mail+Teams | Livrable {IdHNCS} soumis à revue | Lien vers l'élément et le document | ID ; NOM |
| N-26 | PA-07 | Propriétaire | Mail+Teams | Corrections demandées sur {IdHNCS} | Commentaires du réviseur, action de correction et échéance | ID ; COMM |
| N-27 | PA-07 | Propriétaire | Mail+Teams | Livrable {IdHNCS} validé | Valideur, date, version validée | ID |
| N-28 | PA-07 | Réviseur | Mail | Capitalisation incomplète pour {IdHNCS} | Éléments manquants (document, métadonnées, Definition of Done) | ID |
| N-29 | PA-07 | Propriétaire, réviseur | Mail | Livrable {IdHNCS} suspendu ou abandonné | Motif | ID |
| N-30 | PA-08b | Alternant | Mail+Teams | Rappel : compte rendu {IdHNCS} attendu le {date} | Période, lien | ID |
| N-31 | PA-08b | Référent (valideur) | Mail | Compte rendu {IdHNCS} non remis | Période, échéance | ID ; NOM |
| N-32 | PA-08 | Valideur | Mail+Teams | Compte rendu {IdHNCS} remis | État général, avancement, lien | ID ; NOM |
| N-33 | PA-08 | G_DRD | Mail | Blocage signalé ({IdHNCS}) | Lien vers le compte rendu | ID |
| N-34 | PA-08 | Alternant | Mail+Teams | Compte rendu {IdHNCS} à compléter | Commentaire du référent | ID ; COMM |
| N-35 | PA-09 | Référent principal, G_RD, responsable HNCS de l'école | Mail | Fin d'alternance planifiée : {IdAlternant} | Date de fin, checklist de clôture, bilan à réaliser | ID ; NOM |
| N-36 | PA-09 | Référent principal, G_RD | Mail | {IdAlternant} suspendu | Lien | ID ; NOM |
| N-37 | PA-09 | G_RD, référent principal, Destinataires.Administration, Destinataires.Support | Mail | Fin d'alternance enregistrée : {IdAlternant} | Affectations terminées, checklist de clôture (dont retrait des accès, action humaine) | ID ; NOM |
| N-38 | PA-09 | G_DRD, G_ECO | Mail | Bilan {IdHNCS} : partenariat à évaluer | Recommandation (pas une décision), lien vers l'action d'évaluation | ID |
| N-39 | PA-10 | G_ECO, Destinataires.Administration, G_DRD | Mail | Décision de partenariat enregistrée ({IdHNCS}) | Décision, décideur, date | ID |
| N-40 | PA-10b | Responsable de la convention, G_ECO | Mail | Convention {IdHNCS} {statut} | Date de fin, renouvellement | ID |
| N-41 | PA-10b | Responsable HNCS de l'établissement | Mail+Teams | Prochaine action école : {IdHNCS} | Action et échéance | ID |
| N-42 | PA-11 | G_DRD, canal Teams du comité | Mail+Teams | Synthèse Comité R&D du {date} | Synthèse opérationnelle (§ 8.4 PA-11) | ID |
| N-43 | PA-11 | G_DRD (relaie à Destinataires.Direction après relecture) | Mail | Synthèse {Point Direction / Revue trimestrielle} à relire et transmettre | Agrégats et points d'arbitrage, sans nom de personne | ID |
| N-44 | PA-12 | Approbateur, sinon G_DRD | Mail+Teams | Communication {IdHNCS} à valider | Canal, date prévue, autorisations, lien | ID |
| N-45 | PA-12 | Auteur | Mail+Teams | Communication {IdHNCS} {statut} | Décision et commentaire | ID |
| N-47 | PA-14 | G_DRD (À arbitrer, Bloqué) ; référent du sujet et G_RD (Priorisé, Suspendu, Abandonné) | Mail+Teams | Sujet {IdHNCS} {statut} | Décision ou demande d'arbitrage, motif | ID |
| N-46 | PA-13 | G_DRD, G_PROP | Mail | Candidatures arrivées en fin de conservation | Liste d'identifiants, procédure de traitement manuel | ID |
| N-90 | PA-00B | Auteur de la modification | Mail+Teams | Changement de statut refusé ({IdHNCS}) | Statut demandé, motif du refus, statut rétabli, marche à suivre | ID |
| N-91 | PA-05 ; PA-04 | Auteur de la modification | Mail+Teams | {IdHNCS} : modification annulée | Champs verrouillés (affectation active, référent principal dérivé), procédure « nouvelle affectation » | ID |
| N-92 | PA-04 ; PA-07 ; PA-08 ; PA-10 | Auteur de la modification | Mail+Teams | {IdHNCS} : modification d'un champ protégé annulée | Champ concerné, rôle habilité, valeur rétablie (P-09) | ID |
| N-98 | PA-00E | Destinataires.Support, G_PROP | Mail | Erreurs de flux à reprendre ({n}) | Liste des erreurs non reprises avec liens d'exécution | ID |
| N-99 | PA-00C | Destinataires.Support | Mail | Erreur du flux {code} | Message, objet, lien d'exécution, procédure de reprise | ID |
