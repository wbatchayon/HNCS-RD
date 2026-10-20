# Sous-spécification : Référentiels initiaux

> Alignée sur `spec.md` (qui prévaut). Lue par `tools/spec_extract.py` et injectée par le provisioning (étape « référentiels »).
> Toutes les valeurs ci-dessous sont des **propositions** à valider (spec [13](../spec.md#13-hypothèses-et-décisions-à-confirmer), H-22 à H-24). Le provisioning n'écrase **jamais** une valeur non vide d'une clé existante (idempotence : une valeur modifiée par la Direction R&D est conservée) ; il complète en revanche une valeur **vide** lorsque la configuration la fournit (ex. `Lien.RapportPowerBI` renseigné après le lot 4).

## Paramètres

Les valeurs `<…>` sont des marqueurs remplacés au déploiement à partir de `provisioning/config/tenant.json`.

### PARAMETRES

| Clé | Valeur | Catégorie | Description |
| --- | --- | --- | --- |
| Destinataires.BoiteRD | `<BoiteRD>` | Destinataires | Boîte partagée R&D : réception des candidatures (PA-01b) et expéditeur des notifications |
| Destinataires.Administration | `<EmailAdministration>` | Destinataires | Destinataire des transmissions de profils présélectionnés (Carine, H-05) |
| Destinataires.DirectionRD | `<EmailDirectionRD>` | Destinataires | Destinataire des escalades et synthèses comité |
| Destinataires.Direction | `<EmailDirection>` | Destinataires | Destinataire du Point Direction et de la revue trimestrielle |
| Destinataires.Support | `<EmailSupport>` | Destinataires | Support des flux (erreurs N-98 / N-99) |
| Delai.RelanceAnalyseJours | 5 | Délais | Relance d'une candidature sans traitement (PA-02b) |
| Delai.SeuilAttenteCandidatureJours | 10 | Délais | Seuil « candidatures en attente » (Power BI) |
| Delai.RappelEntretienHeures | 24 | Délais | Rappel avant entretien (PA-03b) |
| Delai.RappelLivrableJours | 7;2 | Délais | Rappels avant échéance de livrable (PA-06) |
| Delai.EscaladeComiteJours | 7 | Délais | Retard au-delà duquel un livrable est remonté au comité |
| Delai.RappelActionJours | 2 | Délais | Rappel avant échéance d'une action de checklist (PA-04b) |
| CR.CadenceGlobale | Quinzaine | Délais | Cadence par défaut des comptes rendus (H-08) : Hebdomadaire, Quinzaine, Mensuelle ou Par jalon |
| CR.DelaiRemiseJours | 2 | Délais | Échéance de remise = fin de période + n jours |
| CR.DelaiNonRemisJours | 3 | Délais | Passage en « Non remis » après échéance + n jours |
| Fin.AnticipationJours | 30 | Délais | Passage en « Fin planifiée » et checklist de clôture n jours avant la fin |
| Convention.AlerteExpirationJours | 60 | Délais | Passage en « À renouveler » n jours avant la fin d'une convention |
| Fonction.AccuseReceptionActif | Non | Fonctionnalités | Accusé de réception automatique au candidat (H-09) |
| Fonction.InformationCandidatAuto | Non | Fonctionnalités | Information automatique du candidat à la clôture (H-09) |
| Fonction.CreationReunionTeams | Non | Fonctionnalités | Création de la réunion Teams par PA-03 |
| Fonction.NotificationsTeams | Oui | Fonctionnalités | Doubler les notifications nominatives par un message Teams |
| Fonction.Lot2Actif | Non | Fonctionnalités | Passé à Oui par l'administrateur à l'activation du lot 2, avant l'exécution manuelle de PA-00D : déclenche l'initialisation des empreintes et l'écriture des entrées `REPRISE` ([6.1](../spec.md#61-règles-générales), point 3 ter) |
| Fonction.RepriseExistantActive | Non | Fonctionnalités | Autorise DIRECTION_RD à créer un alternant sans candidature (reprise de l'existant, `G_SOURCE_ALTERNANT`, H-12) |
| Recrutement.PartageTransmission | Groupe | Fonctionnalités | Portée du partage à la transmission (PA-02) : Groupe (G_ADM) ou Destinataire (`DestinataireAdmin` seul) (H-45) |
| Conservation.CandidatureNonRetenueMois |  | Conservation | Vide tant que la durée n'est pas validée (H-10) ; PA-13 inactif si vide |
| Conservation.ModePurge | Signalement | Conservation | Seule valeur implémentée |
| Lien.RapportPowerBI | `<UrlRapportPowerBI>` | Liens | Lien inséré dans les synthèses |
| Lien.CanalComite | `<UrlCanalTeamsComite>` | Liens | Canal Teams du Comité R&D |
| Gouvernance.ComiteJourHeure | Lundi 08:00 | Gouvernance | Envoi de la synthèse du Comité R&D (PA-11) |
| Canal.Regles | linkedin.com=LinkedIn;francetravail.fr=France Travail;pole-emploi.fr=France Travail;[CANDIDATURE-SITE]=Site HNCS | Canaux | Règles de déduction du canal (PA-01b) : `motif=canal`, testées sur le domaine de l'expéditeur puis sur l'objet |
| Canal.ExtensionsAutorisees | .pdf;.doc;.docx;.odt | Canaux | Pièces jointes enregistrées par PA-01b |

## Pôles

### SEED: Poles

| IdHNCS | CodePole | Title | Mission | Statut |
| --- | --- | --- | --- | --- |
| POL-P1 | P1 | Pôle 1 : POC et démonstrateurs | Concevoir et réaliser des preuves de concept, démonstrateurs et cas d'usage représentatifs. | Actif |
| POL-P2 | P2 | Pôle 2 : Plans de stratégie et méthodologies | Formaliser des démarches types documentées et réutilisables. | Actif |
| POL-P3 | P3 | Pôle 3 : Rayonnement et communication | Valoriser les travaux et la maîtrise de HNCS au moyen de communications régulières. | Actif |
| POL-P4 | P4 | Pôle 4 : Partenariats académiques et talents | Suivre les relations avec les établissements et organiser l'accueil et l'encadrement des stagiaires et alternants. | Actif |

## Domaines cibles (proposition, H-24)

### SEED: DomainesCibles

| IdHNCS | Title | Pole | Cible | Statut |
| --- | --- | --- | --- | --- |
| DOM-2026-0001 | Migration | POL-P2 | Oui | Actif |
| DOM-2026-0002 | Déploiement | POL-P2 | Oui | Actif |
| DOM-2026-0003 | Sauvegarde et PRA | POL-P2 | Oui | Actif |
| DOM-2026-0004 | Réseaux d'entreprise | POL-P2 | Oui | Actif |
| DOM-2026-0005 | Sécurité | POL-P2 | Oui | Actif |
| DOM-2026-0006 | Démonstrateurs d'infrastructure | POL-P1 | Oui | Actif |
| DOM-2026-0007 | Valorisation et communication technique | POL-P3 | Non | Actif |

La colonne `Pole` contient l'`IdHNCS` du pôle ; le provisioning le résout en ID SharePoint. Les `IdHNCS` des référentiels sont **réservés** (spec [2.2](../spec.md#22-conventions-de-nommage)) : recherche par `Title`, identifiant renseigné s'il est vide, erreur s'il est déjà porté par un autre élément.

## Modèles de checklists (proposition, H-23)

### SEED: ModelesActions

| Code | Title | Contexte | Categorie | RoleResponsable | DelaiJours | Bloquante | PreuveAttendue | Ordre | Actif |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FORM-01 | Confirmer la décision et la date de démarrage avec le candidat | Formalités d'intégration | Administratif | ADMIN | 3 | Oui | Courriel de confirmation enregistré dans le dossier administratif | 10 | Oui |
| FORM-02 | Obtenir les informations de l'école (formation, calendrier, contact) | Formalités d'intégration | Convention / école | ADMIN | 7 | Oui | Fiche école ou courriel de l'école | 20 | Oui |
| FORM-03 | Établir le contrat ou la convention et la faire signer | Formalités d'intégration | Convention / école | ADMIN | 14 | Oui | Document signé dans « 02 - Administration » | 30 | Oui |
| FORM-04 | Collecter les pièces administratives requises | Formalités d'intégration | Administratif | ADMIN | 14 | Oui | Pièces déposées dans « 02 - Administration » | 40 | Oui |
| FORM-05 | Confirmer le pôle, le référent pressenti et le sujet pressenti | Formalités d'intégration | Accueil R&D | RD | 10 | Oui | Champs renseignés sur la candidature | 50 | Oui |
| FORM-06 | Informer le référent pressenti de l'arrivée | Formalités d'intégration | Accueil R&D | RD | 10 | Non |  | 60 | Oui |
| ACC-01 | Créer le compte Microsoft 365 et renseigner « Compte Microsoft 365 » sur la fiche | Accueil | Accès et matériel | PROPRIETAIRE | 0 | Non | Compte renseigné sur la fiche alternant | 10 | Oui |
| ACC-02 | Ajouter l'alternant au groupe HNCS-RD-Alternants et au canal Teams R&D | Accueil | Accès et matériel | PROPRIETAIRE | 0 | Non |  | 20 | Oui |
| ACC-03 | Préparer le poste de travail et les accès techniques (GitLab, environnements) | Accueil | Accès et matériel | PROPRIETAIRE | 0 | Non |  | 30 | Oui |
| ACC-04 | Présenter le cadrage du sujet, les modèles et les règles de rédaction | Accueil | Accueil R&D | REFERENT | 5 | Non | Fiche de cadrage déposée | 40 | Oui |
| ACC-05 | Créer l'affectation (alternant, sujet, référent) | Accueil | Accueil R&D | RD | 5 | Non | Affectation « Active » | 50 | Oui |
| CLO-01 | Vérifier la clôture ou la suspension de tous les livrables | Clôture d'alternance | Capitalisation | REFERENT | 0 | Oui | Aucun livrable ouvert | 10 | Oui |
| CLO-02 | Capitaliser la documentation dans « 04 - Livrables R&D » | Clôture d'alternance | Capitalisation | REFERENT | 0 | Oui | Versions de référence présentes | 20 | Oui |
| CLO-03 | Organiser le transfert de connaissances | Clôture d'alternance | Documentation | REFERENT | 0 | Non |  | 30 | Oui |
| CLO-04 | Recueillir le retour d'expérience de l'alternant | Clôture d'alternance | Retour d'expérience | RD | 0 | Non |  | 40 | Oui |
| CLO-05 | Réaliser le bilan d'alternance | Clôture d'alternance | Retour d'expérience | REFERENT | 0 | Oui | Bilan « Réalisé » | 50 | Oui |
| CLO-06 | Retirer les accès selon les règles internes | Clôture d'alternance | Accès et matériel | PROPRIETAIRE | 0 | Oui | Compte désactivé et groupes mis à jour | 60 | Oui |
| CLO-07 | Archiver le dossier administratif | Clôture d'alternance | Administratif | ADMIN | 0 | Non |  | 70 | Oui |
| PART-01 | Évaluer l'intérêt d'un partenariat ou d'un sponsoring avec l'école | Évaluation partenariat | Partenariat | ECOLES | 30 | Non | Note d'évaluation dans « 06 - Écoles et partenariats » | 10 | Oui |

`DelaiJours` = 0 pour les actions de clôture : l'échéance est la date de fin de l'alternance.

## Registre de modèles initial (proposition)

Entrées créées au statut « Brouillon » : les fichiers sont à produire et approuver par leurs propriétaires (cadrage § 9.4). Aucun livrable n'est proposé automatiquement tant qu'un modèle n'est pas « Approuvé ».

### SEED: RegistreModeles

| IdHNCS | Title | TypeModele | TypeLivrableCible | Version | ApplicableA | CreationAuto | DelaiStandardJours | Proprietaire | Statut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MOD-2026-0001 | Fiche de cadrage de sujet | Cadrage de sujet | Fiche de cadrage | 0.1 | POC / démonstrateur;Plan de stratégie;Communication;Partenariat / talents;Autre | Oui | 10 | `<EmailDirectionRD>` | Brouillon |
| MOD-2026-0002 | Rapport d'avancement | Rapport d'avancement | Autre | 0.1 |  | Non |  | `<EmailDirectionRD>` | Brouillon |
| MOD-2026-0003 | Fiche POC | Fiche POC | POC / démonstrateur | 0.1 | POC / démonstrateur | Oui | 90 | `<EmailDirectionRD>` | Brouillon |
| MOD-2026-0004 | Plan de stratégie | Plan de stratégie | Plan de stratégie | 0.1 | Plan de stratégie | Oui | 90 | `<EmailDirectionRD>` | Brouillon |
| MOD-2026-0005 | Fiche méthodologie | Fiche méthodologie | Fiche méthodologie | 0.1 | POC / démonstrateur;Plan de stratégie | Oui | 100 | `<EmailDirectionRD>` | Brouillon |
| MOD-2026-0006 | Support de restitution | Restitution | Restitution | 0.1 | POC / démonstrateur;Plan de stratégie | Oui | 110 | `<EmailDirectionRD>` | Brouillon |
| MOD-2026-0007 | Grille de revue de livrable | Revue de livrable | Autre | 0.1 |  | Non |  | `<EmailDirectionRD>` | Brouillon |
| MOD-2026-0008 | Bilan de clôture d'alternance | Clôture d'alternance | Autre | 0.1 |  | Non |  | `<EmailDirectionRD>` | Brouillon |

Le `Proprietaire` des modèles est la personne `<EmailDirectionRD>` (marqueur résolu au déploiement), à réattribuer ensuite.
