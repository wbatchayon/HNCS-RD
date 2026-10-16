# Flux Power Automate — HNCS-RD

Flux du système de suivi R&D (spec § 8), livrés comme définitions exportables d'une solution Power Platform **non gérée** `HNCSRDSuivi` (éditeur `hncs`, préfixe `hncs`). La source de vérité reste [`spec.md`](../spec.md) ; ce dossier en est l'implémentation.

## Contenu

| Chemin | Rôle |
| --- | --- |
| `src/<IdTechnique>/workflow.json` | Une définition technique par flux (format « Workflows » de solution). **Générées** : ne pas les modifier à la main |
| `manifest.json` | Description exacte de chaque définition (déclencheur, statuts cibles, listes, colonnes, statuts écrits, transitions, notifications, flux enfants) |
| `templates/N-xx.html` | Modèles des notifications du catalogue `specs/notifications.md` (variables `{{Var}}`, liens uniquement, jamais de pièce jointe) |
| `docs/PA-xx.md` | Une fiche par code PA (générée) |
| `tools/generate_flows.py` | Générateur : `workflow.json`, manifeste et fiches à partir du modèle (`provisioning/model/model.generated.json`) et des modèles HTML |
| `tools/flowlib.py`, `tools/gen_common.py`, `tools/defs_*.py` | Bibliothèque de construction (actions, socle, contrôles `G_*`, empreintes) et définitions des flux par domaine |
| `tools/check_flows.py` | Vérification hors ligne (structure, manifeste, partition, décisions humaines, notifications, sécurité) |
| `build/build_solution.py` | Assemblage de `dist/HNCSRDSuivi_<specVersion>.zip` (ignoré par git) ; `--check` valide sans écrire |
| `deploy/deploymentSettings.sample.json` | Paramètres de déploiement (`pac solution create-settings`) : variables d'environnement et références de connexion |
| `deploy/Import-HNCSRDFlows.ps1` | Import (`pac auth`, `pac solution import --settings-file`), activation ordonnée et partage des flux enfants |

```powershell
python flows/tools/generate_flows.py            # régénère src/, manifest.json et docs/
python flows/tools/generate_flows.py --check    # vérifie que les fichiers versionnés sont à jour
python flows/tools/check_flows.py               # 0 erreur attendue
python flows/build/build_solution.py --check    # valide la solution
python flows/build/build_solution.py            # produit flows/dist/HNCSRDSuivi_<version>.zip
```

## Architecture

- **Socle** : PA-00A (vérifier une transition), PA-00B (appliquer ou annuler, historiser), PA-00C (journaliser, N-99) sont des flux enfants (« Déclencher manuellement un flux » + « Répondre à une application ou à un flux »), appelés par l'action « Exécuter un flux enfant » via leur `WorkflowId`. PA-00D attribue les `IdHNCS` manquants, PA-00E rappelle les erreurs non reprises, PA-00F pose les droits des propriétaires de modèles.
- **Flux métier** : une définition par liste écoutée (§ 8.3) — `PA-03-ent` / `PA-03-cand`, `PA-04-cand` / `PA-04-alt` / `PA-04-act`, `PA-09-alt` / `PA-09-bil`, `PA-10-conv` / `PA-10-int` partagent le code PA et le contrat. Les flux planifiés portent le suffixe `b` du catalogue.
- **Identifiants** : `WorkflowId` = `uuid5(NAMESPACE_URL, "urn:hncs-rd:flow:<IdTechnique>")`, stable d'un build à l'autre.
- **Connexions** : références `hncs_sharepoint`, `hncs_outlook`, `hncs_teams`, `hncs_o365users` (connecteurs standard uniquement, P-08), toutes au nom du compte de service (H-13). Aucune action HTTP générique : les permissions, groupes, versions et la corbeille passent par « Envoyer une requête HTTP à SharePoint ».
- **Variables d'environnement** : `hncs_SiteUrl` (sans barre finale), `hncs_ServiceAccountEmail`, `hncs_SupportEmail`, plus `hncs_BoiteRDEmail` et `hncs_BoiteRDDossierCandidatures` exigées par le déclencheur « boîte partagée » de PA-01b (écart signalé à la spec).
- **Listes** : désignées par leur titre affiché (paramètre `table`) ; les requêtes REST utilisent l'URL relative `/Lists/<NomInterne>` (bibliothèques : `/<NomInterne>`).

## Socle commun appliqué (§ 8.1)

| Thème | Mise en œuvre |
| --- | --- |
| Anti-boucle | Condition de déclenchement exacte de la spec sur `Editor` ≠ compte de service, sur tous les déclencheurs SharePoint |
| Détection d'une transition | Conditions `Statut` ≠ `StatutPrecedent` et statut cible ∈ partition ; pour les flux à champs protégés (P-09 : PA-07, PA-08, PA-10-conv), déclenchement sur toute modification et garde `Si_aucune_transition_a_traiter` dans le flux |
| Structure | Portées `Principal` → `Erreur` (si échec ou expiration : PA-00C puis fin en échec) → `Terminer` |
| Transition humaine | Lecture fraîche, événement obsolète ignoré, `IdHNCS`, protections P-09, PA-00A, contrôles `G_*` (code inconnu = refus), refus → PA-00B (annulation ou corbeille pour une création, N-90) et fin ; sinon effets, PA-00B, post-traitements reprenables |
| Transition par un flux | PA-00A (rôle FLUX), contrôles, écriture du statut, PA-00B (Origine Flux), puis effets du statut cible (§ 6.1-8) ; refus = avertissement, rien n'est écrit |
| Paramètres | Liste `Parametres` lue au début de chaque exécution, filtrée par catégorie, avec valeurs par défaut de `specs/referentiels-initiaux.md` |
| Dates | « Aujourd'hui » et dates seules en heure de Paris ; dates-heures écrites en UTC |
| Notifications | Boîte partagée `Destinataires.BoiteRD` ; Teams (bot Flow) aux personnes nommées si `Fonction.NotificationsTeams` = Oui, échec Teams non bloquant ; groupes résolus par REST (H-14) |
| Idempotence | Dates déjà posées, `CodeModeleAction`, dossiers existants, `DernierRappel`, `RefMessage`, marqueurs `JournalFlux` (N-17), comparaison de `DateRevue` à la modification déclenchante |
| Empreintes (P-09, § 6.5) | JSON compact dans l'ordre de la spec, comparées clé par clé ; empreinte vide = initialisation sans rétablissement |

## Ordre d'activation

1. **PA-00A, PA-00B, PA-00C** (flux enfants) : à activer en premier ; les parents échouent tant qu'ils sont inactifs.
2. PA-00D (dès le lot 1 : identifiants des saisies manuelles), PA-00E, PA-00F.
3. Flux du lot 2, puis du lot 3 une fois les listes de lot 3 déployées.
4. **PA-13 reste désactivé** : ne l'activer qu'après validation de `Conservation.CandidatureNonRetenueMois` (H-10).

`deploy/Import-HNCSRDFlows.ps1` applique cet ordre (via l'API Web Dataverse, jeton `Get-AzAccessToken`) et laisse PA-13 désactivé ; il peut partager les flux enfants (`-ShareWith`). Les données de test sont à importer **flux désactivés** (spec § 12).

## Procédure de reprise

1. Lire l'élément `JournalFlux` (Niveau Erreur, « À reprendre ») ou le courriel N-99 / la synthèse N-98.
2. Corriger la cause (droits, paramètre, colonne, connexion).
3. Ouvrir `RunUrl` et « Resoumettre » l'exécution : chaque étape vérifie d'abord ce qui est déjà fait.
4. Passer `StatutReprise` à « Reprise effectuée » (commentaire dans `CommentaireReprise`).

Les flux planifiés se rattrapent seuls au passage suivant. Une notification peut être renvoyée lors d'une resoumission quand la spec ne prévoit pas de marqueur (limite connue).

## À valider sur un tenant de recette

- Import de la solution (format des `environmentvariabledefinitions` et `connectionreferences` dans `customizations.xml`), liaison des connexions, activation.
- Paramètres des opérations du connecteur SharePoint (`GetItemChanges`, `CreateNewFolder`, `CreateFile`, `PatchFileItem`), sortie `{VersionNumber}`, format des colonnes date seule et lien hypertexte.
- Requêtes REST : `breakroleinheritance`, `addroleassignment`, `ensureuser`, `GetFolderByServerRelativeUrl(...)?$select=Exists`, `recycle()`, `MERGE` avec `ListItemEntityTypeFullName`.
- Teams : `CreateTeamsMeeting` (`calendarid` = `Calendar`), publication dans le canal du comité à partir de `Lien.CanalComite`.
- Déclencheur boîte partagée (identifiant du dossier « Candidatures ») et nom affiché de l'expéditeur.
