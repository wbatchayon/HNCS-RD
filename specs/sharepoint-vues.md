# Sous-spécification — Vues SharePoint

> Alignée sur `spec.md` § 4 et § 5 (qui prévaut). Lue par `tools/spec_extract.py`.

## Grammaire

- **Colonnes** : noms internes séparés par `, ` (`Title` = colonne Titre ; `IdHNCS`, `Statut` disponibles selon la liste).
- **Filtre** : conditions reliées par ` ET ` (pas de « OU » : utiliser `in`). Opérateurs : `=`, `<>`, `<`, `<=`, `>`, `>=`, `in (v1; v2)`, `notin (v1; v2)`, `est vide`, `non vide`.
  Valeurs spéciales : `[Moi]` (utilisateur courant, colonnes personne), `[Aujourd'hui]`, `[Aujourd'hui+N]`, `[Aujourd'hui-N]`. Booléens : `Oui` / `Non`. `—` = aucun filtre.
- **Tri** : `Colonne asc` ou `Colonne desc`, plusieurs séparés par `, `.
- **Regroupement** : une colonne ou `—`.
- Une seule vue « Par défaut » = `Oui` par liste. Toutes les vues sont publiques ; limite de 30 éléments par page sauf mention.
- Rendu : dans une liste, `Title` est affiché sous la forme du titre cliquable (`LinkTitle`) ; une vue qui ne cite pas `Title` reçoit `LinkTitle` en première position, afin que chaque ligne ouvre l'élément. Dans une bibliothèque, les colonnes `DocIcon` et `LinkFilename` (nom de fichier cliquable) sont toujours ajoutées en tête. Les regroupements sont dépliés (`Collapse` = FALSE).

### VUES: Offres

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Offres ouvertes | Oui | IdHNCS, Title, TypeOffre, Pole, DateDebutPeriode, DateFinPeriode, Statut | Statut in (Brouillon; Publiée) | DateDebutPeriode asc | — |
| Toutes les offres | Non | IdHNCS, Title, TypeOffre, Pole, Statut | — | IdHNCS desc | Statut |

### VUES: Candidatures

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Candidatures en cours | Oui | IdHNCS, Title, Canal, DateReception, Offre, PosteVise, ResponsableAnalyse, Statut, DoublonPotentiel | Statut notin (Intégrée; Non retenue; Clôturée) | DateReception asc | Statut |
| Mes analyses | Non | IdHNCS, Title, Canal, DateReception, PosteVise, Statut | ResponsableAnalyse = [Moi] ET Statut in (Reçue; À analyser; En cours d'analyse) | DateReception asc | — |
| À attribuer | Non | IdHNCS, Title, Canal, ModeReception, DateReception, DoublonPotentiel | Statut = Reçue ET ResponsableAnalyse est vide | DateReception asc | — |
| Transmises à l'administration | Non | IdHNCS, Title, PosteVise, DateTransmissionAdmin, DestinataireAdmin, Statut | Statut in (Transmise à l'administration; Entretien planifié; Entretien réalisé; En attente de décision; Retenue; Formalités en cours) | DateTransmissionAdmin asc | Statut |
| Doublons potentiels | Non | IdHNCS, Title, Email, DoublonDe, DateReception, Statut | DoublonPotentiel = Oui ET Statut notin (Non retenue; Clôturée) | DateReception desc | — |
| Candidatures clôturées | Non | IdHNCS, Title, Statut, MotifCode, DateCloture, InformationCandidat | Statut in (Non retenue; Clôturée) | DateCloture desc | MotifCode |
| Candidat à informer | Non | IdHNCS, Title, Statut, MotifCode, DateCloture | Statut in (Non retenue; Clôturée) ET InformationCandidat = Non | DateCloture asc | — |

### VUES: Entretiens

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Entretiens à venir | Oui | IdHNCS, Title, Candidature, DateHeure, TypeEntretien, Modalite, Participants, Statut | Statut = Planifié | DateHeure asc | — |
| Résultats à saisir | Non | IdHNCS, Title, Candidature, DateHeure, Statut | Statut = Planifié ET DateHeure < [Aujourd'hui] | DateHeure asc | — |
| Tous les entretiens | Non | IdHNCS, Candidature, DateHeure, TypeEntretien, Statut, Resultat, SaisiPar | — | DateHeure desc | Candidature |

### VUES: Etablissements

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Tous les établissements | Oui | IdHNCS, Title, Ville, TypeEtablissement, ResponsableHNCS, DateDerniereInteraction, ProchaineAction, DateProchaineAction, Statut | — | Title asc | Statut |
| Actions à venir | Non | IdHNCS, Title, ResponsableHNCS, ProchaineAction, DateProchaineAction | DateProchaineAction <= [Aujourd'hui+14] | DateProchaineAction asc | — |
| Partenariats à évaluer | Non | IdHNCS, Title, ResponsableHNCS, Statut | Statut = Partenariat à évaluer | Title asc | — |

### VUES: Conventions

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Conventions en cours | Oui | IdHNCS, Title, Etablissement, TypeConvention, DateDebut, DateFin, Responsable, Statut | Statut notin (Expirée; Clôturée) | DateFin asc | Statut |
| À renouveler | Non | IdHNCS, Title, Etablissement, DateFin, Renouvellement, Statut | Statut = À renouveler | DateFin asc | — |
| Décisions de partenariat | Non | IdHNCS, Etablissement, TypeConvention, DecisionPartenariat, DecideurPartenariat, DateDecisionPartenariat | DecisionPartenariat non vide | DateDecisionPartenariat desc | — |

### VUES: InteractionsEcoles

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Historique des échanges | Oui | IdHNCS, Title, Etablissement, DateInteraction, TypeInteraction, ResponsableHNCS, ProchaineAction, DateProchaineAction | — | DateInteraction desc | Etablissement |

### VUES: Alternants

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Alternants actifs | Oui | IdHNCS, Title, Pole, ReferentPrincipal, Etablissement, DateDebut, DateFin, Statut | Statut in (À intégrer; Actif; Suspendu; Fin planifiée) | DateFin asc | Pole |
| Fins à venir | Non | IdHNCS, Title, ReferentPrincipal, DateFin, Statut | Statut in (Actif; Fin planifiée) ET DateFin <= [Aujourd'hui+45] | DateFin asc | — |
| Historique des alternants | Non | IdHNCS, Title, Pole, Etablissement, DateDebut, DateFin, DateFinReelle, Statut | — | DateDebut desc | Statut |

### VUES: Poles

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Pôles | Oui | IdHNCS, CodePole, Title, Responsable, Statut | — | CodePole asc | — |

### VUES: Referents

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Référents actifs | Oui | IdHNCS, Title, Compte, Poles, CapaciteIndicative, Disponibilite | Statut = Actif | Title asc | — |

### VUES: SujetsRD

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Portefeuille | Oui | IdHNCS, Title, TypeSujet, Pole, Priorite, Referent, DateFinPrevue, Statut | Statut notin (Terminé; Abandonné) | Priorite asc | Pole |
| À arbitrer | Non | IdHNCS, Title, TypeSujet, Pole, Priorite, Statut | Statut in (Proposé; À arbitrer; Bloqué) | Priorite asc | Statut |
| Tous les sujets | Non | IdHNCS, Title, TypeSujet, Pole, Statut, GitlabProjetUrl | — | IdHNCS desc | Statut |

### VUES: Affectations

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Affectations en cours | Oui | IdHNCS, Alternant, Sujet, Referent, DateDebut, DateFin, CadenceCR, Statut | Statut in (À préparer; Active; À risque; Bloquée) | DateDebut desc | Statut |
| Sans référent | Non | IdHNCS, Alternant, Sujet, DateDebut, Statut | Referent est vide ET Statut notin (Terminée; Clôturée) | DateDebut asc | — |
| Historique des affectations | Non | IdHNCS, Alternant, Sujet, Referent, DateDebut, DateFin, AffectationRemplacee, MotifFin, Statut | — | DateDebut desc | Alternant |

### VUES: Livrables

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Livrables en cours | Oui | IdHNCS, Title, Affectation, TypeLivrable, Proprietaire, Reviseur, Echeance, EnRetard, Statut | Statut notin (Archivé / clôturé; Suspendu / abandonné) | Echeance asc | Statut |
| Mes livrables | Non | IdHNCS, Title, TypeLivrable, Echeance, Statut, CommentaireRevue | Proprietaire = [Moi] ET Statut notin (Archivé / clôturé) | Echeance asc | — |
| À revoir | Non | IdHNCS, Title, Proprietaire, DateDepot, Statut, LienDocument | Reviseur = [Moi] ET Statut in (Soumis à revue; En revue) | DateDepot asc | — |
| En retard | Non | IdHNCS, Title, Proprietaire, Reviseur, Echeance, Statut | EnRetard = Oui | Echeance asc | — |
| Capitalisés | Non | IdHNCS, Title, TypeLivrable, Sujet, Valideur, DateValidation, DateArchivage, LienDocument, LienGitlab | Statut = Archivé / clôturé | DateArchivage desc | TypeLivrable |

### VUES: ComptesRendus

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Comptes rendus ouverts | Oui | IdHNCS, Title, Affectation, Alternant, PeriodeDebut, PeriodeFin, Echeance, Statut | Statut notin (Validé) | Echeance asc | Statut |
| À valider | Non | IdHNCS, Title, Alternant, DateRemise, EtatGeneral, Avancement, BlocageSignale | Valideur = [Moi] ET Statut = Remis | DateRemise asc | — |
| Blocages signalés | Non | IdHNCS, Alternant, PeriodeFin, EtatGeneral, Blocages, SoutienRequis, Statut | BlocageSignale = Oui | PeriodeFin desc | — |
| Non remis | Non | IdHNCS, Alternant, Affectation, Echeance | Statut = Non remis | Echeance asc | — |

### VUES: RegistreModeles

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Modèles en vigueur | Oui | IdHNCS, Title, TypeModele, Version, Proprietaire, DateEntreeVigueur, LienFichier, Statut | Statut = Approuvé | TypeModele asc | — |
| Tous les modèles | Non | IdHNCS, Title, TypeModele, Version, Statut, DateApprobation | — | TypeModele asc | Statut |

### VUES: ActionsIntegration

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Actions ouvertes | Oui | IdHNCS, Title, Contexte, Candidature, Alternant, Responsable, Echeance, Bloquante, Statut | Statut in (À faire; En cours; Bloquée) | Echeance asc | Contexte |
| Mes actions | Non | IdHNCS, Title, Contexte, Echeance, Bloquante, PreuveAttendue, Statut | Responsable = [Moi] ET Statut in (À faire; En cours; Bloquée) | Echeance asc | — |
| En retard | Non | IdHNCS, Title, Contexte, Responsable, Echeance, Statut | Statut in (À faire; En cours; Bloquée) ET Echeance < [Aujourd'hui] | Echeance asc | — |

### VUES: ModelesActions

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Modèles de checklists | Oui | Code, Title, Contexte, Categorie, RoleResponsable, DelaiJours, Bloquante, Actif | — | Ordre asc | Contexte |

### VUES: BilansAlternance

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Bilans | Oui | IdHNCS, Alternant, Etablissement, Referent, DateBilan, RecommandationPartenariat, Statut | — | DateBilan desc | Statut |

### VUES: CommunicationsRD

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Calendrier éditorial | Oui | IdHNCS, Title, Canal, Auteur, DatePrevue, AutorisationsTiers, Statut | Statut notin (Publiée; Suspendue / refusée) | DatePrevue asc | Statut |
| À valider | Non | IdHNCS, Title, Canal, Auteur, LivrableSource, AutorisationsTiers | Statut = En revue | DatePrevue asc | — |
| Publiées | Non | IdHNCS, Title, Canal, DateEffective, UrlPublication, LivrableSource | Statut = Publiée | DateEffective desc | Canal |

### VUES: DomainesCibles

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Domaines | Oui | IdHNCS, Title, Pole, Cible, Statut | — | Title asc | Pole |

### VUES: RessourcesTechniques

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Ressources | Oui | IdHNCS, Title, TypeRessource, Url, Sujet, Responsable, Statut | — | Title asc | TypeRessource |

### VUES: Mobilisations

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Mobilisations | Oui | IdHNCS, Title, Livrable, DateMobilisation, TypeMobilisation, Responsable | — | DateMobilisation desc | — |

### VUES: Parametres

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Paramètres | Oui | Title, Valeur, Categorie, Description | — | Title asc | Categorie |

### VUES: TransitionsStatuts

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Transitions | Oui | Title, Objet, StatutDe, StatutVers, Acteurs, Controle, FluxResponsable, Actif | — | Title asc | Objet |

### VUES: HistoriqueStatuts

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Historique récent | Oui | Title, Objet, StatutAvant, StatutApres, Acteur, DateChangement, Origine, Resultat | DateChangement >= [Aujourd'hui-30] | DateChangement desc | — |
| Transitions refusées | Non | Title, Objet, StatutAvant, StatutApres, Acteur, DateChangement, Motif | Resultat = Refusée — annulée | DateChangement desc | — |

### VUES: JournalFlux

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Erreurs à reprendre | Oui | Title, Niveau, IdObjet, Message, RunUrl, DateEvenement, StatutReprise | StatutReprise = À reprendre | DateEvenement desc | Title |
| Journal complet | Non | Title, Niveau, Liste, IdObjet, Message, DateEvenement, StatutReprise | — | DateEvenement desc | — |

### VUES: GitlabSync

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Jalons GitLab | Oui | Title, Sujet, Milestone, MilestoneEcheance, MilestoneEtat, IssuesOuvertes, IssuesFermees, IdLivrable, EcartEcheance, DateSynchro | — | MilestoneEcheance asc | Sujet |

### VUES: LivrablesRD

| Vue | Par défaut | Colonnes | Filtre | Tri | Regroupement |
| --- | --- | --- | --- | --- | --- |
| Tous les documents | Oui | Title, Livrable, Sujet, TypeDocument, StatutDocument, ResponsableValidation, DateDocument | — | DateDocument desc | — |
| Versions de référence | Non | Title, Livrable, Sujet, TypeDocument, DateDocument | StatutDocument = Référence | DateDocument desc | Sujet |
