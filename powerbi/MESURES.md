# Mesures du modèle Power BI HNCS-RD

> Généré à partir du TMDL (`HNCS-RD.SemanticModel/definition/tables/Mesures.tmdl`) : le DAX ci-dessous est celui qui est **implémenté**. Les noms et le DAX sont ceux de `spec.md` [\[9.5\]](../spec.md#95-mesures) (qui prévaut), sans écart (spec v1.7.0). Les définitions et points de vigilance reprennent, en les reformulant, le cadrage (§ 2.4 objectifs, § 8.2 indicateurs recommandés), document source non versionné (H-30).

Conventions communes :

- toutes les dates proviennent de SharePoint en UTC et sont converties en **heure de Paris** dans Power Query (`fnHeureParis`) ; les colonnes « date seule » deviennent la date locale ;
- `TODAY ()` / `NOW ()` sont évalués à l'affichage ; dans le service Power BI ils sont en **UTC** (J−1 entre 00:00 et 01:00/02:00, heure de Paris ; écart toléré, H-48) ;
- `Calendrier` filtre les candidatures (date de réception), les livrables et les comptes rendus (échéance), les communications (date de publication) et les mobilisations (date de mobilisation) ; les autres tables ne sont filtrées que par propagation (voir README.md) ;
- les indicateurs servent le pilotage collectif, jamais l'évaluation individuelle (cadrage § 8.2).

## Recrutement

### [Candidatures reçues]

- **Définition** : Nombre de candidatures enregistrées dans `Candidatures` (filtrées par la date de réception via `Calendrier`).
- **Format** : `#,##0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Inclut doublons signalés et candidatures clôturées ; la période suit `DateReceptionJour` (heure de Paris).

```dax
Candidatures reçues =
    COUNTROWS ( Candidatures )
```

### [Candidatures actives]

- **Définition** : Candidatures dont le statut n'est pas terminal (≠ Intégrée, Non retenue, Clôturée).
- **Format** : `#,##0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Repose sur la colonne calculée `EstActive` ; toute évolution de STATUT_CANDIDATURE impose de la revoir.

```dax
Candidatures actives =
    CALCULATE ( COUNTROWS ( Candidatures ), Candidatures[EstActive] = TRUE () )
```

### [Seuil attente (j)]

- **Définition** : Seuil (jours) au-delà duquel une candidature active est « en attente » : paramètre `Delai.SeuilAttenteCandidatureJours` (10 par défaut).
- **Format** : `0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Repli sur 10 si la clé est absente (valeur vide) ou non numérique. Pour les rôles Direction, RelationEcoles et Referent, la RLS ne laisse voir de `Parametres` que cette clé (RX-04) : la mesure reste juste.

```dax
Seuil attente (j) =
    VAR v = LOOKUPVALUE ( Parametres[Valeur], Parametres[Cle], "Delai.SeuilAttenteCandidatureJours" )
    RETURN IF ( ISBLANK ( v ), 10, IFERROR ( VALUE ( v ), 10 ) )
```

### [Candidatures en attente]

- **Définition** : Candidatures actives restées dans leur statut (depuis `DateStatut`, à défaut `DateReception`) plus longtemps que le seuil.
- **Format** : `#,##0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Cadrage : seuil à décider ; vues détaillées réservées aux acteurs habilités. `NOW ()` est en UTC dans le service (écart d'une à deux heures, sans effet sensible en jours).

```dax
Candidatures en attente =
    VAR Seuil = [Seuil attente (j)]
    RETURN COUNTROWS ( FILTER ( Candidatures, Candidatures[EstActive] && DATEDIFF ( COALESCE ( Candidatures[DateStatut], Candidatures[DateReception] ), NOW (), DAY ) > Seuil ) )
```

### [Délai moyen de présélection (j)]

- **Définition** : Moyenne de `DateDecisionPreselection − DateReception` en jours, sur les candidatures ayant une décision de présélection.
- **Format** : `#,##0.0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Cadrage : définir début et fin exacts ; ne pas mélanger dossiers complets et incomplets. `DATEDIFF ( …, DAY )` compte les changements de jour calendaire.

```dax
Délai moyen de présélection (j) =
    AVERAGE ( Candidatures[DelaiPreselectionJours] )
```

### [Délai moyen de traitement (j)]

- **Définition** : Moyenne de la durée réception → intégration (ou clôture) des candidatures terminées.
- **Format** : `#,##0.0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Les candidatures « Non retenue » sans `DateCloture` sont exclues ; PA-02 renseigne `DateCloture` aussi pour « Non retenue ».

```dax
Délai moyen de traitement (j) =
    AVERAGE ( Candidatures[DelaiTraitementJours] )
```

### [Candidatures analysées]

- **Définition** : Candidatures ayant reçu une décision de présélection (positive ou négative).
- **Format** : `#,##0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Comptée dès la décision de présélection (positive ou négative) ; une candidature encore « En cours d'analyse » n'est pas comptée.

```dax
Candidatures analysées =
    CALCULATE ( COUNTROWS ( Candidatures ), NOT ISBLANK ( Candidatures[DateDecisionPreselection] ) )
```

### [Candidatures présélectionnées]

- **Définition** : Candidatures transmises à l'administration (`DateTransmissionAdmin` renseignée).
- **Format** : `#,##0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Une candidature « Présélectionnée » dont la transmission a échoué (reprise en attente) n'est pas encore comptée.

```dax
Candidatures présélectionnées =
    CALCULATE ( COUNTROWS ( Candidatures ), Candidatures[EstPreselectionnee] = TRUE () )
```

### [Taux de présélection]

- **Définition** : Présélectionnées ÷ analysées.
- **Format** : `0.0%`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Indicateur de pilotage du sourcing, pas d'évaluation individuelle.

```dax
Taux de présélection =
    DIVIDE ( [Candidatures présélectionnées], [Candidatures analysées] )
```

### [Entretiens réalisés]

- **Définition** : Nombre d'entretiens au statut « Réalisé ».
- **Format** : `#,##0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Compte des entretiens, pas des candidatures (une candidature peut en avoir plusieurs) : l'entonnoir utilise [Candidatures avec entretien réalisé].

```dax
Entretiens réalisés =
    CALCULATE ( COUNTROWS ( Entretiens ), Entretiens[Statut] = "Réalisé" )
```

### [Candidatures avec entretien réalisé]

- **Définition** : Nombre de candidatures distinctes ayant au moins un entretien « Réalisé ».
- **Format** : `#,##0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Étape « entretien » de l'entonnoir de recrutement ; suit la date de réception de la candidature (relation Entretiens → Candidatures).

```dax
Candidatures avec entretien réalisé =
    CALCULATE ( DISTINCTCOUNT ( Entretiens[CandidatureId] ), Entretiens[Statut] = "Réalisé" )
```

### [Entretiens à venir]

- **Définition** : Entretiens « Planifié » dont la date est postérieure à maintenant.
- **Format** : `#,##0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : `NOW ()` en UTC dans le service, `DateHeure` en heure de Paris : décalage d'une à deux heures.

```dax
Entretiens à venir =
    CALCULATE ( COUNTROWS ( Entretiens ), Entretiens[Statut] = "Planifié", Entretiens[DateHeure] >= NOW () )
```

### [Candidatures retenues]

- **Définition** : Candidatures ayant fait l'objet d'une décision finale favorable (Retenue, Formalités en cours, Intégrée).
- **Format** : `#,##0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Décision humaine (P-01) ; une réouverture fait sortir la candidature du compte.

```dax
Candidatures retenues =
    CALCULATE ( COUNTROWS ( Candidatures ), Candidatures[Statut] IN { "Retenue", "Formalités en cours", "Intégrée" } )
```

### [Candidatures intégrées]

- **Définition** : Candidatures au statut « Intégrée ».
- **Format** : `#,##0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Double barrière P-02 : ne compte que les intégrations dont les formalités ont été contrôlées par PA-04.

```dax
Candidatures intégrées =
    CALCULATE ( COUNTROWS ( Candidatures ), Candidatures[Statut] = "Intégrée" )
```

### [Taux de transformation]

- **Définition** : Intégrées ÷ reçues, sur la même période de réception.
- **Format** : `0.0%`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Les candidatures récentes non encore traitées font baisser le taux de la période courante.

```dax
Taux de transformation =
    DIVIDE ( [Candidatures intégrées], [Candidatures reçues] )
```

### [Doublons signalés]

- **Définition** : Candidatures marquées `DoublonPotentiel` par PA-01 et non encore vérifiées par la R&D (`DoublonVerifie` = Non).
- **Format** : `#,##0`, dossier d'affichage « Recrutement »
- **Point de vigilance** : Signalement uniquement : aucune fusion automatique ; une candidature cochée « Doublon vérifié » (faux positif) sort de l'indicateur, `DoublonPotentiel` restant tracé.

```dax
Doublons signalés =
    CALCULATE ( COUNTROWS ( Candidatures ), Candidatures[DoublonPotentiel] = TRUE (), Candidatures[DoublonVerifie] = FALSE () )
```

## Effectifs et encadrement

### [Alternants actifs]

- **Définition** : Fiches `Alternants` au statut « Actif » ou « Fin planifiée ».
- **Format** : `#,##0`, dossier d'affichage « Effectifs »
- **Point de vigilance** : Cadrage : ne pas compter les candidats retenus non encore intégrés (statut « À intégrer » exclu). Non filtrée par `Calendrier` (photo à la date du rapport).

```dax
Alternants actifs =
    CALCULATE ( COUNTROWS ( Alternants ), Alternants[Statut] IN { "Actif", "Fin planifiée" } )
```

### [Alternants accueillis]

- **Définition** : Alternants effectivement arrivés (tous statuts sauf « À intégrer »), hors alternances annulées avant leur début (`DateFinReelle` < `DateDebut`).
- **Format** : `#,##0`, dossier d'affichage « Effectifs »
- **Point de vigilance** : Comparée à la cible indicative (3) sans borne de période : cumul depuis l'origine ; non filtrée par `Calendrier`.

```dax
Alternants accueillis =
    COUNTROWS ( FILTER ( Alternants, Alternants[Statut] IN { "Actif", "Suspendu", "Fin planifiée", "Terminé", "Clôturé" } && ( ISBLANK ( Alternants[DateFinReelle] ) || Alternants[DateFinReelle] >= Alternants[DateDebut] ) ) )
```

### [Alternants présents sur la période]

- **Définition** : Alternants arrivés (hors « À intégrer » et hors alternances annulées avant leur début) dont la période [DateDebut ; DateFinReelle ou DateFin] chevauche la période sélectionnée dans `Calendrier`.
- **Format** : `#,##0`, dossier d'affichage « Effectifs »
- **Point de vigilance** : Sans sélection, la période est toute l'étendue du calendrier.

```dax
Alternants présents sur la période =
    VAR DebutP = MIN ( Calendrier[Date] )
    VAR FinP = MAX ( Calendrier[Date] )
    RETURN COUNTROWS ( FILTER ( Alternants, Alternants[Statut] <> "À intégrer" && ( ISBLANK ( Alternants[DateFinReelle] ) || Alternants[DateFinReelle] >= Alternants[DateDebut] ) && Alternants[DateDebut] <= FinP && COALESCE ( Alternants[DateFinReelle], Alternants[DateFin] ) >= DebutP ) )
```

### [Affectations actives]

- **Définition** : Affectations « Active », « À risque » ou « Bloquée ».
- **Format** : `#,##0`, dossier d'affichage « Effectifs »
- **Point de vigilance** : Base du taux de charge des référents.

```dax
Affectations actives =
    CALCULATE ( COUNTROWS ( Affectations ), Affectations[Statut] IN { "Active", "À risque", "Bloquée" } )
```

### [Affectations sans référent]

- **Définition** : Affectations non terminées sans référent.
- **Format** : `#,##0`, dossier d'affichage « Effectifs »
- **Point de vigilance** : Une affectation « Active » sans référent est impossible (G_AFFECTATION_COMPLETE) : concerne surtout « À préparer ».

```dax
Affectations sans référent =
    CALCULATE ( COUNTROWS ( Affectations ), Affectations[Statut] IN { "À préparer", "Active", "À risque", "Bloquée" }, ISBLANK ( Affectations[ReferentId] ) )
```

### [Affectations incomplètes]

- **Définition** : Affectations non terminées sans référent, sans date de fin ou sans livrable rattaché.
- **Format** : `#,##0`, dossier d'affichage « Effectifs »
- **Point de vigilance** : `RELATEDTABLE ( Livrables )` respecte les filtres de page sur les livrables (ex. période d'échéance).

```dax
Affectations incomplètes =
    COUNTROWS (
        FILTER (
            Affectations,
            Affectations[Statut] IN { "À préparer", "Active", "À risque", "Bloquée" }
                && ( ISBLANK ( Affectations[ReferentId] ) || ISBLANK ( Affectations[DateFin] ) || COUNTROWS ( RELATEDTABLE ( Livrables ) ) = 0 )
        )
    )
```

### [Alternants sans affectation active]

- **Définition** : Alternants actifs n'ayant aucune affectation « Active », « À risque » ou « Bloquée ».
- **Format** : `#,##0`, dossier d'affichage « Effectifs »
- **Point de vigilance** : Utile en début d'alternance ; à surveiller au Comité R&D.

```dax
Alternants sans affectation active =
    COUNTROWS ( FILTER ( Alternants, Alternants[Statut] IN { "Actif", "Fin planifiée" } && CALCULATE ( COUNTROWS ( Affectations ), Affectations[Statut] IN { "Active", "À risque", "Bloquée" } ) = 0 ) )
```

### [Taux de charge référent]

- **Définition** : Nombre d'alternants distincts ayant une affectation « Active », « À risque » ou « Bloquée » ÷ somme des capacités indicatives des référents (dans le contexte).
- **Format** : `0.0%`, dossier d'affichage « Effectifs »
- **Point de vigilance** : Un alternant ayant deux affectations concomitantes (H-42) n'est compté qu'une fois ; au total, les affectations sans référent restent au numérateur ; capacité vide = 0.

```dax
Taux de charge référent =
    DIVIDE ( CALCULATE ( DISTINCTCOUNT ( Affectations[AlternantId] ), Affectations[Statut] IN { "Active", "À risque", "Bloquée" } ), SUM ( Referents[CapaciteIndicative] ) )
```

## Projets et livrables

### [Livrables]

- **Définition** : Nombre de livrables.
- **Format** : `#,##0`, dossier d'affichage « Livrables »
- **Point de vigilance** : Filtrés par `Calendrier` via l'échéance (`Echeance`).

```dax
Livrables =
    COUNTROWS ( Livrables )
```

### [Livrables validés]

- **Définition** : Livrables « Validé » ou « Archivé / clôturé ».
- **Format** : `#,##0`, dossier d'affichage « Livrables »
- **Point de vigilance** : Filtré par échéance (et non par date de validation) lorsque `Calendrier` est filtré.

```dax
Livrables validés =
    CALCULATE ( COUNTROWS ( Livrables ), Livrables[Statut] IN { "Validé", "Archivé / clôturé" } )
```

### [Livrables soumis à revue]

- **Définition** : Livrables ayant fait l'objet d'au moins un dépôt (`DatePremierDepot`).
- **Format** : `#,##0`, dossier d'affichage « Livrables »
- **Point de vigilance** : Dénominateur du taux de validation.

```dax
Livrables soumis à revue =
    CALCULATE ( COUNTROWS ( Livrables ), NOT ISBLANK ( Livrables[DatePremierDepot] ) )
```

### [Taux de validation]

- **Définition** : Validés ÷ soumis à revue.
- **Format** : `0.0%`, dossier d'affichage « Livrables »
- **Point de vigilance** : Les livrables soumis mais encore en revue font baisser le taux.

```dax
Taux de validation =
    DIVIDE ( [Livrables validés], [Livrables soumis à revue] )
```

### [Livrables en retard]

- **Définition** : Livrables « À produire », « En cours » ou « Corrections demandées » dont l'échéance est dépassée.
- **Format** : `#,##0`, dossier d'affichage « Livrables »
- **Point de vigilance** : Calcul indépendant de la colonne `EnRetard` (PA-06) ; `TODAY ()` est la date UTC dans le service (de 00:00 à 02:00 heure de Paris, J−1).

```dax
Livrables en retard =
    COUNTROWS ( FILTER ( Livrables, Livrables[Statut] IN { "À produire", "En cours", "Corrections demandées" } && Livrables[Echeance] < TODAY () ) )
```

### [Livrables arrivés à échéance]

- **Définition** : Livrables non suspendus/abandonnés dont l'échéance est atteinte.
- **Format** : `#,##0`, dossier d'affichage « Livrables »
- **Point de vigilance** : Dénominateur du taux de remise à l'heure.

```dax
Livrables arrivés à échéance =
    COUNTROWS ( FILTER ( Livrables, Livrables[Echeance] <= TODAY () && Livrables[Statut] <> "Suspendu / abandonné" ) )
```

### [Taux de remise à l'heure]

- **Définition** : Livrables échus déposés au plus tard à leur échéance ÷ livrables échus (hors suspendus/abandonnés).
- **Format** : `0.0%`, dossier d'affichage « Livrables »
- **Point de vigilance** : Cadrage : définir le traitement des échéances révisées. La mesure compare à l'échéance **courante** (`Echeance`), pas à `EcheanceInitiale`.

```dax
Taux de remise à l'heure =
    DIVIDE (
        COUNTROWS ( FILTER ( Livrables, Livrables[Echeance] <= TODAY () && Livrables[Statut] <> "Suspendu / abandonné" && NOT ISBLANK ( Livrables[DatePremierDepot] ) && Livrables[DatePremierDepotJour] <= Livrables[Echeance] ) ),
        [Livrables arrivés à échéance]
    )
```

### [Taux de validation au premier passage]

- **Définition** : Livrables validés ou archivés sans aucune demande de corrections ÷ livrables soumis à revue (au moins un dépôt).
- **Format** : `0.0%`, dossier d'affichage « Livrables »
- **Point de vigilance** : Cadrage : à utiliser pour améliorer le processus, jamais comme mesure individuelle. Les livrables soumis non encore revus font baisser le taux.

```dax
Taux de validation au premier passage =
    DIVIDE (
        CALCULATE ( COUNTROWS ( Livrables ), Livrables[Statut] IN { "Validé", "Archivé / clôturé" }, Livrables[NbCorrections] = 0 ),
        [Livrables soumis à revue]
    )
```

### [Taux de capitalisation]

- **Définition** : Livrables archivés avec document lié (et DoD complète pour un POC ou un plan) ÷ livrables validés ou archivés.
- **Format** : `0.0%`, dossier d'affichage « Livrables »
- **Point de vigilance** : Cadrage : doit refléter la Definition of Done ; un livrable validé non encore archivé compte comme non capitalisé ; `ADocument` ne contrôle que la présence du lien.

```dax
Taux de capitalisation =
    DIVIDE (
        CALCULATE ( COUNTROWS ( Livrables ), Livrables[Statut] = "Archivé / clôturé", Livrables[CapitalisationComplete] = TRUE () ),
        CALCULATE ( COUNTROWS ( Livrables ), Livrables[Statut] IN { "Validé", "Archivé / clôturé" } )
    )
```

### [Corrections en cours]

- **Définition** : Livrables au statut « Corrections demandées ».
- **Format** : `#,##0`, dossier d'affichage « Livrables »

```dax
Corrections en cours =
    CALCULATE ( COUNTROWS ( Livrables ), Livrables[Statut] = "Corrections demandées" )
```

### [Échéances à 14 jours]

- **Définition** : Livrables non terminés dont l'échéance tombe dans les 14 prochains jours (aujourd'hui inclus).
- **Format** : `#,##0`, dossier d'affichage « Livrables »
- **Point de vigilance** : Alimente le Comité R&D (cohérent avec la synthèse PA-11).

```dax
Échéances à 14 jours =
    COUNTROWS ( FILTER ( Livrables, Livrables[Statut] IN { "À produire", "En cours", "Corrections demandées" } && Livrables[Echeance] >= TODAY () && Livrables[Echeance] <= TODAY () + 14 ) )
```

### [Livrables sans modèle]

- **Définition** : Livrables actifs sans modèle du registre.
- **Format** : `#,##0`, dossier d'affichage « Livrables »
- **Point de vigilance** : Qualité des données / gouvernance des modèles.

```dax
Livrables sans modèle =
    CALCULATE ( COUNTROWS ( Livrables ), ISBLANK ( Livrables[ModeleId] ), Livrables[Statut] <> "Suspendu / abandonné" )
```

### [POC réalisés]

- **Définition** : Livrables de type « POC / démonstrateur » archivés avec DoD complète.
- **Format** : `#,##0`, dossier d'affichage « Livrables »
- **Point de vigilance** : Cible indicative 5 (H-20) ; filtrés par échéance lorsque `Calendrier` est filtré.

```dax
POC réalisés =
    CALCULATE ( COUNTROWS ( Livrables ), Livrables[Statut] = "Archivé / clôturé", Livrables[TypeLivrable] = "POC / démonstrateur", Livrables[DoDComplete] = TRUE () )
```

### [Plans de stratégie formalisés]

- **Définition** : Livrables de type « Plan de stratégie » archivés avec DoD complète.
- **Format** : `#,##0`, dossier d'affichage « Livrables »
- **Point de vigilance** : Cible indicative 4 (H-20).

```dax
Plans de stratégie formalisés =
    CALCULATE ( COUNTROWS ( Livrables ), Livrables[Statut] = "Archivé / clôturé", Livrables[TypeLivrable] = "Plan de stratégie", Livrables[DoDComplete] = TRUE () )
```

### [Couverture des domaines cibles]

- **Définition** : Domaines cibles actifs couverts par au moins un sujet ayant un livrable validé ou archivé ÷ domaines cibles actifs.
- **Format** : `0.0%`, dossier d'affichage « Livrables »
- **Point de vigilance** : Cadrage : le référentiel des domaines doit exister dans SharePoint. La mesure ignore tous les filtres (ALL) : indicateur global ; elle respecte la RLS (0 pour le rôle Administration).

```dax
Couverture des domaines cibles =
    VAR DomCibles = FILTER ( ALL ( DomainesCibles ), DomainesCibles[Cible] = TRUE () && DomainesCibles[Statut] = "Actif" )
    VAR SujetsValides = SELECTCOLUMNS ( FILTER ( ALL ( Livrables ), Livrables[Statut] IN { "Validé", "Archivé / clôturé" } ), "SujetId", RELATED ( Affectations[SujetId] ) )
    VAR Couverts = FILTER ( DomCibles, NOT ISEMPTY ( FILTER ( ALL ( SujetDomaine ), SujetDomaine[DomaineId] = DomainesCibles[Id] && SujetDomaine[SujetId] IN SujetsValides ) ) )
    RETURN DIVIDE ( COUNTROWS ( Couverts ), COUNTROWS ( DomCibles ) )
```

### [Sujets bloqués]

- **Définition** : Sujets au statut « Bloqué » ou « À arbitrer ».
- **Format** : `#,##0`, dossier d'affichage « Livrables »

```dax
Sujets bloqués =
    CALCULATE ( COUNTROWS ( SujetsRD ), SujetsRD[Statut] IN { "Bloqué", "À arbitrer" } )
```

### [Sujets actifs]

- **Définition** : Sujets au statut « Priorisé », « En cours » ou « Bloqué ».
- **Format** : `#,##0`, dossier d'affichage « Livrables »
- **Point de vigilance** : Photo à la date du rapport (non filtrée par `Calendrier`).

```dax
Sujets actifs =
    CALCULATE ( COUNTROWS ( SujetsRD ), SujetsRD[Statut] IN { "Priorisé", "En cours", "Bloqué" } )
```

### [Mobilisations commerciales]

- **Définition** : Nombre de mobilisations d'un livrable (rendez-vous client, appel d'offres…).
- **Format** : `#,##0`, dossier d'affichage « Livrables »
- **Point de vigilance** : Cible indicative 8. Datée par `DateMobilisation` (relation active vers `Calendrier`) ; la relation vers le livrable mobilisé est inactive.

```dax
Mobilisations commerciales =
    COUNTROWS ( Mobilisations )
```

## Comptes rendus

### [Comptes rendus attendus]

- **Définition** : Comptes rendus dont l'échéance de remise est atteinte.
- **Format** : `#,##0`, dossier d'affichage « Comptes rendus »
- **Point de vigilance** : Dénominateur du taux de remise des comptes rendus.

```dax
Comptes rendus attendus =
    CALCULATE ( COUNTROWS ( ComptesRendus ), ComptesRendus[Echeance] <= TODAY () )
```

### [Comptes rendus manquants]

- **Définition** : Comptes rendus « Non remis », ou « Attendu » / « En rédaction » échus.
- **Format** : `#,##0`, dossier d'affichage « Comptes rendus »
- **Point de vigilance** : Plus réactif que le statut « Non remis » posé par PA-08b après le délai de grâce.

```dax
Comptes rendus manquants =
    COUNTROWS ( FILTER ( ComptesRendus, ComptesRendus[Statut] = "Non remis" || ( ComptesRendus[Statut] IN { "Attendu", "En rédaction" } && ComptesRendus[Echeance] < TODAY () ) ) )
```

### [Taux de remise des comptes rendus]

- **Définition** : Comptes rendus échus remis au plus tard à l'échéance ÷ comptes rendus échus.
- **Format** : `0.0%`, dossier d'affichage « Comptes rendus »
- **Point de vigilance** : `DateRemise` (heure de Paris) est ramenée à la date par `DATE ( YEAR, MONTH, DAY )`.

```dax
Taux de remise des comptes rendus =
    DIVIDE (
        COUNTROWS ( FILTER ( ComptesRendus, ComptesRendus[Echeance] <= TODAY () && NOT ISBLANK ( ComptesRendus[DateRemise] ) && DATE ( YEAR ( ComptesRendus[DateRemise] ), MONTH ( ComptesRendus[DateRemise] ), DAY ( ComptesRendus[DateRemise] ) ) <= ComptesRendus[Echeance] ) ),
        [Comptes rendus attendus]
    )
```

### [Blocages signalés]

- **Définition** : Comptes rendus où l'alternant a coché « Blocage signalé ».
- **Format** : `#,##0`, dossier d'affichage « Comptes rendus »
- **Point de vigilance** : Compte des comptes rendus, pas des blocages distincts.

```dax
Blocages signalés =
    CALCULATE ( COUNTROWS ( ComptesRendus ), ComptesRendus[BlocageSignale] = TRUE () )
```

### [Avancement moyen (dernier CR)]

- **Définition** : Moyenne, par affectation, de l'avancement déclaré dans le dernier compte rendu remis, validé ou à compléter.
- **Format** : `#,##0.0`, dossier d'affichage « Comptes rendus »
- **Point de vigilance** : Avancement estimé par l'alternant (0-100) ; une affectation sans compte rendu remis est ignorée.

```dax
Avancement moyen (dernier CR) =
    AVERAGEX (
        VALUES ( Affectations[Id] ),
        VAR DernierePeriode = CALCULATE ( MAX ( ComptesRendus[PeriodeFin] ), ComptesRendus[Statut] IN { "Remis", "Validé", "À compléter" } )
        RETURN CALCULATE ( MAX ( ComptesRendus[Avancement] ), ComptesRendus[PeriodeFin] = DernierePeriode )
    )
```

## Établissements et partenariats

### [Partenariats académiques actifs]

- **Définition** : Conventions de partenariat ou de sponsoring au statut « Signée / active » (H-25).
- **Format** : `#,##0`, dossier d'affichage « Écoles »
- **Point de vigilance** : Cadrage : une école ayant accueilli un alternant n'est pas automatiquement partenaire. Cible indicative 3.

```dax
Partenariats académiques actifs =
    CALCULATE ( COUNTROWS ( Conventions ), Conventions[Statut] = "Signée / active", Conventions[TypeConvention] IN { "Convention de partenariat", "Sponsoring" } )
```

### [Conventions à renouveler]

- **Définition** : Conventions au statut « À renouveler » (PA-10b).
- **Format** : `#,##0`, dossier d'affichage « Écoles »

```dax
Conventions à renouveler =
    CALCULATE ( COUNTROWS ( Conventions ), Conventions[Statut] = "À renouveler" )
```

### [Établissements collaborants]

- **Définition** : Établissements « Établissement d'accueil », « Partenariat à évaluer » ou « Partenaire actif ».
- **Format** : `#,##0`, dossier d'affichage « Écoles »

```dax
Établissements collaborants =
    CALCULATE ( COUNTROWS ( Etablissements ), Etablissements[Statut] IN { "Établissement d'accueil", "Partenariat à évaluer", "Partenaire actif" } )
```

### [Partenariats à évaluer]

- **Définition** : Établissements signalés « Partenariat à évaluer » (bilan favorable, PA-09).
- **Format** : `#,##0`, dossier d'affichage « Écoles »
- **Point de vigilance** : Signal de revue, pas une décision (P-01).

```dax
Partenariats à évaluer =
    CALCULATE ( COUNTROWS ( Etablissements ), Etablissements[Statut] = "Partenariat à évaluer" )
```

### [Bilans réalisés]

- **Définition** : Bilans d'alternance au statut « Réalisé ».
- **Format** : `#,##0`, dossier d'affichage « Écoles »

```dax
Bilans réalisés =
    CALCULATE ( COUNTROWS ( BilansAlternance ), BilansAlternance[Statut] = "Réalisé" )
```

## Communications et valorisation

### [Communications publiées]

- **Définition** : Communications **externes** au statut « Publiée ».
- **Format** : `#,##0`, dossier d'affichage « Communications »
- **Point de vigilance** : Cible indicative 30 (publications valorisant HNCS). Datée par `DateEffective` (relation active vers `Calendrier`) ; les synthèses internes publiées ne sont pas comptées.

```dax
Communications publiées =
    CALCULATE ( COUNTROWS ( CommunicationsRD ), CommunicationsRD[Statut] = "Publiée", CommunicationsRD[Externe] = TRUE () )
```

### [Communications en préparation]

- **Définition** : Communications de l'idée à la programmation (hors publiées et suspendues/refusées).
- **Format** : `#,##0`, dossier d'affichage « Communications »

```dax
Communications en préparation =
    CALCULATE ( COUNTROWS ( CommunicationsRD ), CommunicationsRD[Statut] IN { "Idée", "À préparer", "En rédaction", "En revue", "Validée", "Programmée" } )
```

### [Livrables valorisés]

- **Définition** : Nombre de livrables distincts ayant au moins une communication publiée (interne ou externe).
- **Format** : `#,##0`, dossier d'affichage « Communications »
- **Point de vigilance** : `DISTINCTCOUNTNOBLANK` : une communication sans livrable source n'est pas comptée. La relation vers `Livrables` est inactive : les segments sur les livrables ne filtrent pas cette mesure.

```dax
Livrables valorisés =
    CALCULATE ( DISTINCTCOUNTNOBLANK ( CommunicationsRD[LivrableSourceId] ), CommunicationsRD[Statut] = "Publiée" )
```

## Actions et qualité des données

### [Actions en retard]

- **Définition** : Actions d'intégration / checklists non terminées dont l'échéance est dépassée.
- **Format** : `#,##0`, dossier d'affichage « Qualité »
- **Point de vigilance** : La relation `ActionsIntegration[AlternantId]` → `Alternants` est active : un filtre sur les alternants (pôle, établissement) écarte les actions rattachées à une seule candidature. RLS : le rôle Referent ne voit que les actions des alternants de ses affectations (RX-05) ; RelationEcoles n'en voit aucune.

```dax
Actions en retard =
    COUNTROWS ( FILTER ( ActionsIntegration, ActionsIntegration[Statut] IN { "À faire", "En cours", "Bloquée" } && ActionsIntegration[Echeance] < TODAY () ) )
```

### [Transitions refusées]

- **Définition** : Transitions de statut annulées par les flux (`Refusée et annulée` dans `HistoriqueStatuts`).
- **Format** : `#,##0`, dossier d'affichage « Qualité »
- **Point de vigilance** : Indicateur de qualité du processus, pas de faute individuelle (H-17). Vide pour les rôles Direction, RelationEcoles et Referent (`HistoriqueStatuts` : `FALSE ()`, RX-04).

```dax
Transitions refusées =
    CALCULATE ( COUNTROWS ( HistoriqueStatuts ), HistoriqueStatuts[Resultat] = "Refusée et annulée" )
```

### [Écarts d'échéance GitLab]

- **Définition** : Jalons GitLab non orphelins dont l'échéance diffère de celle du livrable rattaché (lot 5).
- **Format** : `#,##0`, dossier d'affichage « Qualité »
- **Point de vigilance** : Les lignes orphelines (jalon supprimé, sujet détaché : `Orpheline` = Oui) sont conservées dans `GitlabSync` mais exclues (RX-07) ; vide tant que la synchronisation GitLab (lot 5) n'est pas déployée.

```dax
Écarts d'échéance GitLab =
    CALCULATE ( COUNTROWS ( GitlabSync ), GitlabSync[EcartEcheance] = TRUE (), GitlabSync[Orpheline] = FALSE () )
```

## Objectifs indicatifs

### [Cible]

- **Définition** : Valeur cible de la table `Objectifs` pour l'indicateur sélectionné.
- **Format** : `#,##0.##`, dossier d'affichage « Objectifs »
- **Point de vigilance** : Vide si plusieurs indicateurs sont dans le contexte : chaque jauge filtre `Objectifs[Indicateur]`.

```dax
Cible =
    SELECTEDVALUE ( Objectifs[Cible] )
```

## Mesures techniques

### [Dernière actualisation]

- **Définition** : Horodatage (heure de Paris) de la dernière actualisation du modèle : maximum de la colonne masquée `Mesures[DerniereActualisation]`, calculée en Power Query (`DateTimeZone.FixedUtcNow` converti en heure de Paris).
- **Format** : `dd/MM/yyyy HH:mm`, dossier d'affichage « Technique »
- **Point de vigilance** : Affichée sur chaque page (specs/powerbi-rapport.md) ; section « Technique » de [\[9.5\]](../spec.md#95-mesures).

```dax
Dernière actualisation =
    MAX ( Mesures[DerniereActualisation] )
```
