# Flux Power Automate : HNCS-RD

Flux du système de suivi R&D ([\[8\]](../spec.md#8-flux-power-automate--contrats)), livrés comme définitions exportables d'une solution Power Platform **non gérée** `HNCSRDSuivi` (éditeur `hncs`, préfixe `hncs`). La source de vérité reste [`spec.md`](../spec.md) ; ce dossier en est l'implémentation.

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
python flows/build/build_solution.py --brouillon  # même solution, tous les flux en brouillon (activation par lot)
```

## Architecture

- **Socle** : PA-00A (vérifier une transition), PA-00B (appliquer ou annuler, historiser), PA-00C (journaliser, N-99) sont des flux enfants (« Déclencher manuellement un flux » + « Répondre à une application ou à un flux »), appelés par l'action « Exécuter un flux enfant » via leur `WorkflowId`. PA-00D attribue les `IdHNCS` manquants, PA-00E rappelle les erreurs non reprises, PA-00F pose les droits des propriétaires de modèles.
- **Flux métier** : une définition par liste écoutée ([\[8.3\]](../spec.md#83-catalogue-des-flux)) : `PA-03-ent` / `PA-03-cand`, `PA-04-cand` / `PA-04-alt` / `PA-04-act`, `PA-09-alt` / `PA-09-bil`, `PA-10-conv` / `PA-10-int` partagent le code PA et le contrat. Les flux planifiés portent le suffixe `b` du catalogue.
- **Identifiants** : `WorkflowId` = `uuid5(NAMESPACE_URL, "urn:hncs-rd:flow:<IdTechnique>")`, stable d'un build à l'autre.
- **Connexions** : références `hncs_sharepoint`, `hncs_outlook`, `hncs_teams`, `hncs_o365users` (connecteurs standard uniquement, P-08), toutes au nom du compte de service (H-13). Aucune action HTTP générique : les permissions, groupes, versions et la corbeille passent par « Envoyer une requête HTTP à SharePoint ».
- **Variables d'environnement** : `hncs_SiteUrl` (sans barre finale), `hncs_ServiceAccountEmail`, `hncs_SupportEmail`, plus `hncs_BoiteRDEmail` et `hncs_BoiteRDDossierCandidatures` exigées par le déclencheur « boîte partagée » de PA-01b (écart signalé à la spec).
- **Listes** : désignées par leur titre affiché (paramètre `table`) ; les requêtes REST utilisent l'URL relative `/Lists/<NomInterne>` (bibliothèques : `/<NomInterne>`).

## Socle commun appliqué ([\[8.1\]](../spec.md#81-socle-commun-sapplique-à-tous-les-flux))

| Thème | Mise en œuvre |
| --- | --- |
| Anti-boucle | Condition de déclenchement exacte de la spec sur `Editor` ≠ compte de service, sur tous les déclencheurs SharePoint |
| Détection d'une transition | Sur les listes à statut contrôlé, condition de déclenchement = anti-boucle seule (RX-02) ; chaque flux filtre ensuite sur ses statuts cibles ([\[8.2\]](../spec.md#82-partition-des-statuts-cibles)). Le statut validé de référence est le dernier `StatutApres` accepté de `HistoriqueStatuts` (à défaut `∅`) ; `StatutPrecedent` n'est qu'une copie de commodité, jamais lue. Garde `Si_aucune_transition_a_traiter` dans le flux |
| Structure | Portées `Principal` → `Erreur` (si échec ou expiration : PA-00C puis fin en échec) → `Terminer` |
| Colonnes techniques | Au début de chaque déclenchement humain (un seul flux par liste servie par plusieurs flux : PA-02 pour `Candidatures`, PA-04 pour `Alternants`), si la dernière version n'est pas du compte de service et qu'une colonne `flux` a changé depuis la version précédente (« Obtenir les modifications »), toutes les colonnes `flux` reprennent leur valeur de la version précédente (API des versions), Avertissement, N-92, puis traitement sur les valeurs rétablies |
| Transition humaine | Colonnes techniques rétablies, lecture fraîche, événement obsolète ignoré, `IdHNCS`, protections P-09, PA-00A, contrôles `G_*` (code inconnu = refus), refus → PA-00B (rétablissement du statut validé lu dans l'historique ou corbeille pour une création, N-90) et fin ; sinon effets, PA-00B, post-traitements reprenables |
| Transition par un flux | PA-00A (rôle FLUX), contrôles, écriture du statut, PA-00B (Origine Flux), puis effets du statut cible ([\[6.1\]](../spec.md#61-règles-générales), règle 8) ; refus = avertissement, rien n'est écrit |
| Paramètres | Liste `Parametres` lue au début de chaque exécution, filtrée par catégorie, avec valeurs par défaut de `specs/referentiels-initiaux.md` |
| Dates | « Aujourd'hui » et dates seules en heure de Paris ; dates-heures écrites en UTC |
| Notifications | Boîte partagée `Destinataires.BoiteRD` ; Teams (bot Flow) aux personnes nommées si `Fonction.NotificationsTeams` = Oui, échec Teams non bloquant ; groupes résolus par REST (H-14) |
| Idempotence | Dates déjà posées, `CodeModeleAction`, dossiers existants, `DernierRappel`, `RefMessage`, marqueurs `JournalFlux` (N-17), comparaison de `DateRevue` à la modification déclenchante |
| Empreintes (P-09, [\[6.5\]](../spec.md#65-formats-des-empreintes-p-09)) | JSON compact dans l'ordre de la spec, comparées clé par clé ; empreinte vide = initialisation sans rétablissement |
| Rapprochement quotidien | PA-00E rétablit chaque jour, via PA-00B (motif « Rapprochement quotidien »), tout statut différent du dernier statut accepté de l'historique (éléments non modifiés depuis 30 minutes) et le signale dans N-98 |
| Reprise de l'existant | Sans transition acceptée, un élément n'est une création que s'il est à sa première version (`Created` = `Modified` de l'événement déclencheur) ; sinon son statut courant devient le statut de référence par une entrée `HistoriqueStatuts` `REPRISE` (`StatutAvant` = `∅`, Origine Flux, Acceptée, motif « Reprise de l'existant »), écrite par le flux propriétaire de la liste ou, en amont, par PA-00D ([\[6.1\]](../spec.md#61-règles-générales), règle 3 ter, H-57). Les entrées `REPRISE` comptent comme transitions acceptées, `REF-PRINCIPAL` non. Un élément qui a plus d'une version n'est jamais envoyé à la corbeille |

## Ordre d'activation

`deploy/Import-HNCSRDFlows.ps1 -Lot <n>` importe la solution (construite en brouillon avec `-Build` : aucun flux ne s'active pendant l'import) et n'active que les flux de lot inférieur ou égal à `n` (colonne Lot du catalogue [\[8.3\]](../spec.md#83-catalogue-des-flux), reprise dans `manifest.json`), via l'API Web Dataverse (jeton `Get-AzAccessToken`). Les flux de lot supérieur sont laissés en brouillon. `-SkipActivation` importe sans rien activer ; `-ShareWith` partage les flux enfants.

1. **Phase Socle** : PA-00A, PA-00B, PA-00C (flux enfants, à activer en premier : les parents échouent tant qu'ils sont inactifs), puis PA-00D, PA-00E, PA-00F selon le lot (au lot 1 : PA-00C et PA-00D seuls).
2. **À partir du lot 2, avant les flux des listes** : passer le paramètre `Fonction.Lot2Actif` à Oui (liste `Parametres`), **exécuter PA-00D manuellement** (« Exécuter »), vérifier dans `HistoriqueStatuts` les entrées `REPRISE` et les empreintes initialisées ([\[6.5\]](../spec.md#65-formats-des-empreintes-p-09)). Le script s'arrête à cette étape et attend la saisie de OUI (sinon relancer avec `-Phase Listes`).
3. **Phase Listes** : les autres flux du lot (lot 2, puis lot 3 une fois les listes de lot 3 déployées).
4. **PA-13 n'est jamais activé par le script** : l'activer à la main après validation de `Conservation.CandidatureNonRetenueMois` (H-10).

Le fichier de paramètres par défaut `deploy/deploymentSettings.json` (copie renseignée de `deploymentSettings.sample.json`, avec adresses et identifiants de connexion) est **ignoré par git** (`.gitignore`) : il ne doit jamais être versionné. Les données de test sont importées avec leur historique et **flux désactivés** ([\[12\]](../spec.md#12-stratégie-de-test-et-critères-dacceptation)).

## Solution gérée (production)

La solution non gérée construite depuis ce dépôt est importée dans l'environnement de **recette** ; la production reçoit une solution **gérée**, exportée de la recette ([\[8.1\]](../spec.md#81-socle-commun-sapplique-à-tous-les-flux), « Conditionnement ») :

```powershell
pac auth select --name <profil-recette>
pac solution export --name HNCSRDSuivi --path .\HNCSRDSuivi_<version>_managed.zip --managed
pac auth select --name <profil-production>
pac solution import --path .\HNCSRDSuivi_<version>_managed.zip --settings-file <dossier hors du dépôt>\deploymentSettings.production.json
```

Le fichier de paramètres de production suit le même modèle que `deploymentSettings.sample.json` (connexions de production) ; il est conservé **hors du dépôt**, seul `deploy/deploymentSettings.json` étant couvert par `.gitignore`. L'activation par lot se fait ensuite avec `Import-HNCSRDFlows.ps1 -Lot <n> -SolutionZip <zip géré>` ou à la main, dans le même ordre ; une solution gérée ne se modifie pas en production : toute évolution passe par ce dépôt, la recette, puis un nouvel export.

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
