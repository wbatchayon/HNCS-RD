# Bilan du projet HNCS-RD

| Propriété | Valeur |
| --- | --- |
| Version de la spec | 1.7.0 |
| Branche | `feature/systeme-suivi-rd` |
| Statut global | Réalisation complète des lots 0 à 5 ; validation sur un tenant Microsoft 365 et arbitrage des décisions ouvertes à mener |

Ce document distingue clairement ce qui est **terminé et vérifié hors ligne**, ce qui **reste à valider sur un tenant** et les **décisions encore ouvertes**. Aucun élément n'a pu être exécuté contre un tenant Microsoft 365, un environnement Power Platform, un espace Power BI ou une instance GitLab réels : toutes les vérifications décrites ci-dessous sont des vérifications hors ligne.

## 1. Ce qui est terminé

### 1.1 Spécification (lot 0)

- `spec.md` et ses sous-spécifications fixent le modèle de données (26 listes, 6 bibliothèques, colonnes, types, lookups, identifiants), les statuts et 170 transitions contrôlées, les groupes et la matrice d'accès, le contrat des 28 flux, le modèle Power BI et ses 60 mesures, l'intégration GitLab et le découpage en lots ([4](spec.md#4-modèle-de-données--listes-sharepoint) à [11](spec.md#11-découpage-en-lots-0-à-5)).
- La spec est lue par machine : `tools/spec_extract.py` génère `provisioning/model/model.generated.json` et refuse toute incohérence interne (énumérations, lookups entre lots, transitions, partition des statuts, décisions humaines jamais confiées à un flux, matrice, Power BI).
- Deux revues ont été intégrées : la revue de conformité aux documents sources (RC-01 à RC-39) et la revue croisée des livrables (RX-01 à RX-09). Le journal des versions est tenu au [14.3](spec.md#143-journal).

### 1.2 Réalisation par lot

| Lot | Livrables | Vérifications hors ligne |
| --- | --- | --- |
| 1. Socle SharePoint | `provisioning/` : déploiement idempotent et cumulatif par lot, gestion des membres, contrôle du compte de service, contrôle post-déploiement en lecture seule | Analyse syntaxique PowerShell 5.1 sans erreur ; 61 vues converties en CAML valide ; 438 colonnes et fonctions pures contrôlées ; cmdlets PnP.PowerShell 2.12 vérifiés |
| 2 et 3. Automatisations | `flows/` : 33 définitions couvrant les flux PA-00 à PA-14, solution non gérée `HNCSRDSuivi`, script d'import, 52 modèles de notification, fiches par flux | Contrôleur des flux à 0 erreur (listes, champs, statuts, transitions, partition, absence de décision humaine automatisée, absence de pièce jointe) ; construction de la solution vérifiée |
| 4. Power BI | `powerbi/` : projet PBIP (TMDL et PBIR), 25 tables, 60 mesures, 5 rôles, 8 pages, 123 visuels, publication scriptée | Contrôleur PBIP à 0 erreur : mesures identiques à la spec, aucune colonne personnelle importée hors exception masquée, relations, sécurité par rôle |
| 5. GitLab et stabilisation | `gitlab/` : synchronisation GitLab vers SharePoint, création de projet par sujet, modèles, pipeline ; intégration continue du dépôt | 41 tests unitaires de synchronisation sans réseau ; analyse syntaxique du script de création |
| Transverse | `testdata/` (jeu fictif couvrant 100 % des statuts), `tests/` (tests hors ligne et de bout en bout), `docs/` (installation, exploitation, architecture, guides par rôle) | Suite de tests hors ligne au vert ; mutations ciblées du jeu de test détectées |

### 1.3 Principes du cadrage et leur garantie

| Principe | Garantie technique | Vérifié par |
| --- | --- | --- |
| Décisions humaines jamais automatisées | Le rôle `FLUX` est absent de toute transition de décision humaine ([6.1](spec.md#61-règles-générales)) | Extracteur, contrôleur des flux, tests hors ligne |
| « Intégrée » seulement après les formalités | Règle de validation de liste et contrôle `G_INTEGRATION` ([6.6](spec.md#66-catalogue-des-contrôles)) | Tests du jeu de test, scénarios S-04 |
| Nouvelle affectation, jamais d'écrasement | Verrou `EmpreinteVerrou`, succession `AffectationRemplacee` ([8.4](spec.md#84-contrats-détaillés)) | Tests du jeu de test, scénario S-06 |
| CV et données personnelles cloisonnés | Matrice d'accès, permissions par élément, aucune colonne personnelle dans Power BI, OLS ([7](spec.md#7-sécurité--groupes-niveaux-dautorisation-matrice-daccès), [9.6](spec.md#96-sécurité-du-modèle-rls--ols)) | Tests de matrice, contrôleur PBIP |
| Champs protégés et colonnes techniques non falsifiables | Statut de référence tiré de l'historique, rétablissement des colonnes techniques, rapprochement quotidien ([6.5](spec.md#65-formats-des-empreintes-p-09), [8.1](spec.md#81-socle-commun-sapplique-à-tous-les-flux)) | Contrôleur des flux, tests de contrat |

## 2. Ce qui reste à valider

### 2.1 Sur un tenant de recette

| Composant | Points à valider |
| --- | --- |
| Provisionnement | Déroulé complet du lot 1 puis rejeu entièrement « inchangé » ; création du site `STS#3` ; colonnes créées par XML ; traduction des règles de validation sur un site en français ; vues ; rupture d'héritage et retrait des attributions non prévues ; niveau d'autorisation personnalisé ; procédure de changement de type des colonnes d'empreinte sur un site déjà déployé |
| Flux | Import de la solution (`pac solution import`) et liaison des connexions ; paramètres exacts des actions SharePoint et des appels REST (permissions, versions, corbeille) ; déclencheur de boîte partagée ; création de réunion Teams ; comportement réel des colonnes personne, date seule et lien hypertexte |
| Power BI | Ouverture du PBIP dans Power BI Desktop (TMDL, OLS, schémas PBIR) ; lecture par `GetList` et pagination sur le site réel ; identifiants OAuth, actualisation planifiée, affectation des membres aux rôles et audiences de l'application |
| GitLab | Octroi `Lists.SelectedOperations.Selected` (disponibilité en `v1.0` ou `beta` selon le tenant) ; jalons dont le titre contient des caractères accentués ; pipeline planifié |
| Tests de bout en bout | Exécution de `tests/e2e/Access.Tests.ps1` (droits persona par persona) et de `tests/e2e/HNCSRD.E2E.Tests.ps1` ; scénarios manuels S-01 à S-15 ; réconciliation des mesures Power BI avec SharePoint |

### 2.2 Limites connues

- Contrôle des transitions a posteriori : un statut non autorisé reste visible quelques secondes avant d'être rétabli ([13](spec.md#13-hypothèses-et-décisions-à-confirmer), H-17).
- Une exécution de flux resoumise peut renvoyer une notification déjà envoyée lorsqu'aucun marqueur n'est prévu (H-56).
- Une première modification non autorisée d'un élément jamais initialisé est acceptée comme valeur initiale ; l'initialisation horaire des empreintes réduit cette fenêtre (H-55).
- PA-00D déduit l'activation du lot 2 de la présence d'un historique écrit par un flux : un jeu de test importé dès le lot 1 déclenche plus tôt l'initialisation des empreintes, sans autre effet que cette initialisation.
- La lecture des documents des livrables par la Direction est acceptée (H-54).

## 3. Décisions encore ouvertes

Toutes les hypothèses implémentées en attente d'arbitrage sont tenues au [13](spec.md#13-hypothèses-et-décisions-à-confirmer) (H-01 à H-56). Les plus structurantes, à traiter en atelier de validation du lot 0 :

| Thème | Hypothèses | Responsable attendu |
| --- | --- | --- |
| Responsable final de la sélection et confirmation d'intégration | H-06, H-40 | Direction Générale, Administration |
| Validation des communications externes et décision de partenariat ou de sponsoring | H-11, H-37 | Direction Générale |
| Conservation des candidatures (RGPD) : durée et modalités, aucune durée inventée | H-10 | DPO, juridique, RH |
| Information des candidats : accusé de réception et message de clôture | H-09 | Direction R&D, juridique |
| Canaux LinkedIn, France Travail et site HNCS : aucune API présumée, étude de faisabilité séparée | H-04 | DSI, Direction R&D |
| Cadence des comptes rendus (Quinzaine par défaut, paramétrable) | H-08 | Direction R&D |
| Compte de service, appartenance directe aux groupes, licences | H-13, H-14, H-15 | DSI |
| Permissions de la synchronisation GitLab | H-31 | DSI, Direction R&D |
| Valeurs contrôlées proposées hors sources (statuts secondaires, motifs) | H-38 | Atelier lot 0 |
| Acteurs support RH, Juridique, Finance ; trajectoire M0 à M12 | H-32, H-34 | Direction Générale |

Décision tranchée depuis le cadrage : l'interlocutrice administrative est Carine (H-05).

## 4. Prochaines étapes recommandées

1. Tenir l'atelier de validation du lot 0 sur les décisions ci-dessus et mettre à jour la spec.
2. Déployer le lot 1 sur un tenant de recette, rejouer le déploiement, exécuter les tests d'accès.
3. Importer la solution de flux, puis dérouler les scénarios S-01 à S-15 avec le jeu de test.
4. Publier le rapport Power BI et réconcilier les mesures avec SharePoint.
5. Activer la synchronisation GitLab après acceptation des permissions (H-31).
6. Rendre le dépôt privé, les documents de cadrage étant confidentiels (H-30).
