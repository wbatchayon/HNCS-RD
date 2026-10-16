<#
.SYNOPSIS
    Scénarios de bout en bout automatisables de tests/e2e/scenarios.md (spec § 12.1), sur un site de RECETTE.
.DESCRIPTION
    Chaque bloc « Describe » porte le numéro du scénario (S-xx) et des étiquettes :
      - Flux       : nécessite les flux du lot 2 / 3 actifs (attente de l'effet avec délai, DelaiFluxSecondes) ;
      - Planifie   : vérifie l'effet d'un flux planifié ; déclencher d'abord le flux manuellement (« Exécuter ») ;
      - Destructif : modifie des éléments du jeu de test ; relancer ensuite testdata/Import-TestData.ps1 ;
      - Lot1       : exécutable sans flux.
    Les éléments créés portent le marqueur « E2E-<horodatage> » dans leur titre (repérage et nettoyage manuel :
    les utilisateurs métier n'ont pas le droit de supprimer, P-07).
    Exemples :
        $env:HNCSRD_E2E_CONFIG = './tests/e2e/config.json'
        Invoke-Pester ./tests/e2e/HNCSRD.E2E.Tests.ps1 -Output Detailed -ExcludeTagFilter Destructif, Planifie
        Invoke-Pester ./tests/e2e/HNCSRD.E2E.Tests.ps1 -Output Detailed -TagFilter Planifie
#>

BeforeAll {
    . (Join-Path $PSScriptRoot 'HNCSRD.E2E.Common.ps1')
    $script:Cfg = Get-E2EConfig
    $script:Model = Read-E2EJson $script:Cfg.ModelPath
    $script:Personas = Get-E2EPersonas $script:Cfg.PersonasPath
    $script:Marqueur = New-E2EMarqueur
    function Conn([string]$Cle) { return (Connect-E2EPersona -Config $script:Cfg -Personas $script:Personas -Cle $Cle) }
    function Upn([string]$Cle) { return [string]$script:Personas[$Cle].upn }
    function Url([string]$Liste) { return (Get-E2EListUrl $script:Model $Liste) }
    function IdSP([string]$Liste, [string]$IdHNCS) { return (Get-E2EIdSP -Connection (Conn 'IT') -Model $script:Model -Liste $Liste -IdHNCS $IdHNCS) }
    function Lire([string]$Liste, [int]$Id, [string]$Cle = 'IT') { return (Get-E2EItemById -Connection (Conn $Cle) -Model $script:Model -Liste $Liste -Id $Id) }
    function Attendre([scriptblock]$Condition, [string]$Message) { return (Wait-E2ECondition -Condition $Condition -Config $script:Cfg -Message $Message) }
    function Attendre-Statut([string]$Liste, [int]$Id, [string]$Statut) {
        return (Attendre { $i = Lire $Liste $Id; if ($i -and [string]$i['Statut'] -eq $Statut) { $i } } "$Liste/$Id au statut « $Statut »")
    }
    function Historique([string]$IdHNCS) { return @(Get-E2EHistorique -Connection (Conn 'IT') -Model $script:Model -IdHNCS $IdHNCS) }
    function Attendre-Historique([string]$IdHNCS, [string]$Apres, [string]$Resultat) {
        return (Attendre { @(Historique $IdHNCS | Where-Object { [string]$_['StatutApres'] -eq $Apres -and [string]$_['Resultat'] -eq $Resultat }) | Select-Object -Last 1 } "historique $IdHNCS -> $Apres ($Resultat)")
    }
    function Nouvelle-Candidature([string]$Canal, [string]$Mode = 'Saisie manuelle', [switch]$AvecResponsable) {
        $n = Get-Random -Minimum 1000 -Maximum 9999
        $v = @{ Title = "$($script:Marqueur) Candidat $n"; Email = "e2e.$($script:Marqueur.ToLower()).$n@example.org"; Canal = $Canal
            ModeReception = $Mode; DateReception = (Get-Date) }
        if ($AvecResponsable) { $v['ResponsableAnalyse'] = (Upn 'RD1') }
        $it = Add-PnPListItem -List (Url 'Candidatures') -Values $v -Connection (Conn 'RD1')
        return [int]$it.Id
    }
}

Describe 'S-01 Une candidature de chaque canal est enregistrée sans intégration technique' -Tag 'Flux', 'Recrutement' {
    It 'Canal « <_> » : identifiant, dossier CV et historique CAND-T01' -ForEach @('Site HNCS', 'LinkedIn', 'France Travail', 'Candidature spontanée') {
        $id = Nouvelle-Candidature -Canal $_
        $it = Attendre { $i = Lire 'Candidatures' $id; if ($i -and $i['IdHNCS']) { $i } } 'IdHNCS attribué par PA-01'
        [string]$it['IdHNCS'] | Should -Match '^CAND-\d{4}-\d{4,}$'
        [string]$it['Statut'] | Should -Be 'Reçue'
        Attendre { $j = Lire 'Candidatures' $id; if ($j['LienCV']) { $j } } 'LienCV (dossier Recrutement)' | Should -Not -BeNullOrEmpty
        (Attendre-Historique ([string]$it['IdHNCS']) 'Reçue' 'Acceptée')['CodeTransition'] | Should -Be 'CAND-T01'
    }
    It 'Courriel balisé [CANDIDATURE-SITE] reçu dans la boîte R&D (PA-01b)' {
        Set-ItResult -Skipped -Because 'envoi d''un courriel vers la boîte partagée : étape manuelle, voir scenarios.md S-01 (e)'
    }
}

Describe 'S-11 Candidature de plateforme sans identité (G_IDENTITE)' -Tag 'Flux', 'Recrutement' {
    It 'Le passage en analyse est refusé tant que l''identité n''est pas qualifiée' {
        $v = @{ Title = "À qualifier – <$($script:Marqueur)@mail.example.org>"; Canal = 'LinkedIn'; ModeReception = 'Saisie manuelle'; DateReception = (Get-Date) }
        $id = [int](Add-PnPListItem -List (Url 'Candidatures') -Values $v -Connection (Conn 'RD1')).Id
        $it = Attendre { $i = Lire 'Candidatures' $id; if ($i['IdHNCS']) { $i } } 'IdHNCS'
        Set-PnPListItem -List (Url 'Candidatures') -Identity $id -Values @{ ResponsableAnalyse = (Upn 'RD1'); Statut = "En cours d'analyse" } -Connection (Conn 'RD1') | Out-Null
        Attendre-Statut 'Candidatures' $id 'Reçue' | Out-Null
        (Attendre-Historique ([string]$it['IdHNCS']) "En cours d'analyse" 'Refusée — annulée')['Motif'] | Should -Match 'G_IDENTITE'
    }
}

Describe 'S-16 Transition interdite annulée et historisée' -Tag 'Flux', 'Recrutement' {
    It 'Reçue → Intégrée est rétablie à « Reçue » avec historique « Refusée — annulée »' {
        $id = Nouvelle-Candidature -Canal 'Site HNCS'
        $it = Attendre { $i = Lire 'Candidatures' $id; if ($i['IdHNCS']) { $i } } 'IdHNCS'
        Set-PnPListItem -List (Url 'Candidatures') -Identity $id -Values @{ Statut = 'Intégrée'; DateDemarrageConfirmee = (Get-Date).AddDays(10); DateFinPrevue = (Get-Date).AddDays(300) } -Connection (Conn 'RD1') | Out-Null
        Attendre-Statut 'Candidatures' $id 'Reçue' | Out-Null
        $h = Attendre-Historique ([string]$it['IdHNCS']) 'Intégrée' 'Refusée — annulée'
        [string]$h['Motif'] | Should -Not -BeNullOrEmpty
        [string]$h['Origine'] | Should -Be 'Humain'
    }
}

Describe 'S-02 Candidature non présélectionnée : clôture et cloisonnement du CV' -Tag 'Flux', 'Recrutement' {
    BeforeAll {
        $script:S02 = Nouvelle-Candidature -Canal 'LinkedIn' -AvecResponsable
        $script:S02It = Attendre-Statut 'Candidatures' $script:S02 'À analyser'
    }
    It 'La R&D analyse puis écarte avec un motif (CAND-T03, CAND-T06)' {
        Set-PnPListItem -List (Url 'Candidatures') -Identity $script:S02 -Values @{ Statut = "En cours d'analyse" } -Connection (Conn 'RD1') | Out-Null
        Attendre-Historique ([string]$script:S02It['IdHNCS']) "En cours d'analyse" 'Acceptée' | Out-Null
        Set-PnPListItem -List (Url 'Candidatures') -Identity $script:S02 -Values @{ AvisAnalyse = 'Prérequis non satisfaits (E2E).'; MotifCode = 'Prérequis non satisfaits'; Statut = 'Non retenue' } -Connection (Conn 'RD1') | Out-Null
        $h = Attendre-Historique ([string]$script:S02It['IdHNCS']) 'Non retenue' 'Acceptée'
        [string]$h['CodeTransition'] | Should -Be 'CAND-T06'
        $i = Attendre { $x = Lire 'Candidatures' $script:S02; if ($x['DateCloture']) { $x } } 'DateCloture'
        [string]$i['DecisionPreselection'] | Should -Be 'Écartée'
    }
    It 'Ni l''administration ni la Direction ne voient la candidature' {
        Get-E2EItemById -Connection (Conn 'ADMIN_KARINE') -Model $script:Model -Liste 'Candidatures' -Id $script:S02 | Should -BeNullOrEmpty
        Get-E2EItemById -Connection (Conn 'DIRECTION') -Model $script:Model -Liste 'Candidatures' -Id $script:S02 | Should -BeNullOrEmpty
    }
}

Describe 'S-03 / S-04 Parcours : présélection, entretien, décision, formalités, intégration' -Tag 'Flux', 'Recrutement', 'Parcours' {
    BeforeAll {
        $script:P = Nouvelle-Candidature -Canal 'France Travail' -AvecResponsable
        $script:PIt = Attendre-Statut 'Candidatures' $script:P 'À analyser'
        $script:PId = [string]$script:PIt['IdHNCS']
    }
    It 'S-03 Présélection : transmission automatique à l''administration (CAND-T04 puis CAND-T05 par FLUX)' {
        Set-PnPListItem -List (Url 'Candidatures') -Identity $script:P -Values @{ Statut = "En cours d'analyse" } -Connection (Conn 'RD1') | Out-Null
        Attendre-Historique $script:PId "En cours d'analyse" 'Acceptée' | Out-Null
        Set-PnPListItem -List (Url 'Candidatures') -Identity $script:P -Values @{ AvisAnalyse = 'Profil pertinent (E2E).'; Statut = 'Présélectionnée' } -Connection (Conn 'RD1') | Out-Null
        $i = Attendre-Statut 'Candidatures' $script:P "Transmise à l'administration"
        $i['DateTransmissionAdmin'] | Should -Not -BeNullOrEmpty
        [string](Attendre-Historique $script:PId "Transmise à l'administration" 'Acceptée')['Origine'] | Should -Be 'Flux'
    }
    It 'S-03 L''administration voit désormais la candidature, la Direction toujours pas' {
        Get-E2EItemById -Connection (Conn 'ADMIN_KARINE') -Model $script:Model -Liste 'Candidatures' -Id $script:P | Should -Not -BeNullOrEmpty
        Get-E2EItemById -Connection (Conn 'DIRECTION') -Model $script:Model -Liste 'Candidatures' -Id $script:P | Should -BeNullOrEmpty
    }
    It 'S-03 Entretien planifié puis réalisé : la candidature suit (CAND-T07, CAND-T09) et l''entretien est historisé' {
        $e = Add-PnPListItem -List (Url 'Entretiens') -Values @{ Title = "$($script:Marqueur) entretien"; Candidature = $script:P; DateHeure = (Get-Date).AddHours(2)
            TypeEntretien = 'Premier entretien'; Modalite = 'Teams'; Participants = @((Upn 'ADMIN_KARINE')) } -Connection (Conn 'ADMIN_KARINE')
        $script:Ent = [int]$e.Id
        Attendre-Statut 'Candidatures' $script:P 'Entretien planifié' | Out-Null
        Set-PnPListItem -List (Url 'Entretiens') -Identity $script:Ent -Values @{ Statut = 'Réalisé'; Resultat = 'Favorable' } -Connection (Conn 'ADMIN_KARINE') | Out-Null
        Attendre-Statut 'Candidatures' $script:P 'Entretien réalisé' | Out-Null
        $entId = [string](Attendre { $x = Lire 'Entretiens' $script:Ent; if ($x['IdHNCS']) { $x } } 'IdHNCS entretien')['IdHNCS']
        @(Historique $entId | Where-Object { [string]$_['Objet'] -eq 'Entretien' -and [string]$_['StatutApres'] -eq 'Réalisé' }).Count | Should -BeGreaterThan 0
    }
    It 'S-03 Décision finale par l''administration (CAND-T11)' {
        Set-PnPListItem -List (Url 'Candidatures') -Identity $script:P -Values @{ DecideurFinal = (Upn 'ADMIN_KARINE'); Statut = 'Retenue' } -Connection (Conn 'ADMIN_KARINE') | Out-Null
        [string](Attendre-Historique $script:PId 'Retenue' 'Acceptée')['CodeTransition'] | Should -Match '^CAND-T11'
        Attendre { $x = Lire 'Candidatures' $script:P; if ($x['DateDecisionFinale']) { $x } } 'DateDecisionFinale' | Should -Not -BeNullOrEmpty
    }
    It 'S-04 Lancement des formalités : checklist générée depuis ModelesActions (CAND-T13)' {
        Set-PnPListItem -List (Url 'Candidatures') -Identity $script:P -Values @{ Statut = 'Formalités en cours'; Etablissement = (IdSP 'Etablissements' 'ECO-2026-9001')
            PolePressenti = (IdSP 'Poles' 'POL-P1'); ReferentPressenti = (IdSP 'Referents' 'REF-2026-9001')
            DateDemarrageConfirmee = (Get-Date).AddDays(20).Date; DateFinPrevue = (Get-Date).AddDays(380).Date } -Connection (Conn 'ADMIN_KARINE') | Out-Null
        $q = "<View><Query><Where><Eq><FieldRef Name='Candidature' LookupId='TRUE' /><Value Type='Lookup'>$($script:P)</Value></Eq></Where></Query></View>"
        $script:Actions = Attendre { $a = @(Get-PnPListItem -List (Url 'ActionsIntegration') -Query $q -Connection (Conn 'IT')); if ($a.Count -ge 5) { , $a } } 'actions de formalités'
        @($script:Actions | ForEach-Object { [string]$_['CodeModeleAction'] }) | Should -Contain 'FORM-01'
    }
    It 'S-04 / S-17 « Intégrée » est refusée tant que les actions bloquantes ne sont pas terminées avec preuve' {
        Set-PnPListItem -List (Url 'Candidatures') -Identity $script:P -Values @{ Statut = 'Intégrée' } -Connection (Conn 'ADMIN_KARINE') | Out-Null
        Attendre-Statut 'Candidatures' $script:P 'Formalités en cours' | Out-Null
        [string](Attendre-Historique $script:PId 'Intégrée' 'Refusée — annulée')['Motif'] | Should -Match 'G_INTEGRATION|FORM-'
        [string](Lire 'Candidatures' $script:P)['IdAlternant'] | Should -BeNullOrEmpty -Because 'aucune fiche alternant avant confirmation valide'
    }
    It 'S-04 Formalités complètes puis confirmation : l''alternant est créé « À intégrer » (ALT-T01)' {
        foreach ($a in $script:Actions) {
            if ($a['Bloquante']) {
                Set-PnPListItem -List (Url 'ActionsIntegration') -Identity $a.Id -Values @{ Statut = 'Terminée'; Preuve = "$($script:Cfg.SiteUrl)/Administration/e2e-preuve.pdf, preuve" } -Connection (Conn 'ADMIN_KARINE') | Out-Null
            }
        }
        Start-Sleep -Seconds ([int]$script:Cfg.IntervalleSondageSecondes)
        Set-PnPListItem -List (Url 'Candidatures') -Identity $script:P -Values @{ Statut = 'Intégrée' } -Connection (Conn 'ADMIN_KARINE') | Out-Null
        $c = Attendre { $x = Lire 'Candidatures' $script:P; if ($x['IdAlternant']) { $x } } 'IdAlternant renseigné par PA-04'
        [string]$c['Statut'] | Should -Be 'Intégrée'
        $alt = Get-E2EItem -Connection (Conn 'IT') -Model $script:Model -Liste 'Alternants' -IdHNCS ([string]$c['IdAlternant'])
        $alt | Should -Not -BeNullOrEmpty
        [string]$alt['Statut'] | Should -Be 'À intégrer' -Because 'la date de début est future : actif seulement à cette date (ALT-T02)'
        (Get-E2ELookupId $alt['CandidatureSource']) | Should -Be $script:P
        $script:AltParcours = $alt
    }
    It 'S-06 Deux affectations successives : l''ancienne est terminée et datée, jamais écrasée' {
        if (-not $script:AltParcours) { Set-ItResult -Skipped -Because 'alternant du parcours non créé'; return }
        $altId = [int]$script:AltParcours.Id
        $debut = ([datetime]$script:AltParcours['DateDebut']).Date
        $a1 = Add-PnPListItem -List (Url 'Affectations') -Values @{ Alternant = $altId; Sujet = (IdSP 'SujetsRD' 'SUJ-2026-9001'); Referent = (IdSP 'Referents' 'REF-2026-9001')
            DateDebut = $debut; CadenceCR = 'Selon paramètre global' } -Connection (Conn 'RD1')
        Set-PnPListItem -List (Url 'Affectations') -Identity $a1.Id -Values @{ Statut = 'Active' } -Connection (Conn 'RD1') | Out-Null
        $x1 = Attendre { $x = Lire 'Affectations' $a1.Id; if ($x['EmpreinteVerrou']) { $x } } 'EmpreinteVerrou figée'
        $a2 = Add-PnPListItem -List (Url 'Affectations') -Values @{ Alternant = $altId; Sujet = (IdSP 'SujetsRD' 'SUJ-2026-9001'); Referent = (IdSP 'Referents' 'REF-2026-9002')
            DateDebut = $debut.AddDays(10); CadenceCR = 'Selon paramètre global'; AffectationRemplacee = $a1.Id } -Connection (Conn 'RD1')
        Set-PnPListItem -List (Url 'Affectations') -Identity $a2.Id -Values @{ Statut = 'Active' } -Connection (Conn 'RD1') | Out-Null
        $old = Attendre-Statut 'Affectations' $a1.Id 'Terminée'
        ([datetime]$old['DateFin']).Date | Should -Be $debut.AddDays(9)
        [string]$old['MotifFin'] | Should -Match '^Remplacée par AFF-'
        (Get-E2ELookupId $old['Referent']) | Should -Be (IdSP 'Referents' 'REF-2026-9001') -Because 'aucun autre champ de l''ancienne affectation n''est modifié'
        $alt = Attendre { $x = Lire 'Alternants' $altId; if ((Get-E2ELookupId $x['ReferentPrincipal']) -eq (IdSP 'Referents' 'REF-2026-9002')) { $x } } 'référent principal dérivé'
        $alt | Should -Not -BeNullOrEmpty
        $script:AffActive = [int]$a2.Id
    }
    It 'S-06 Modification d''une affectation active annulée (P-03, N-91)' {
        if (-not $script:AffActive) { Set-ItResult -Skipped -Because 'affectation active non créée'; return }
        Set-PnPListItem -List (Url 'Affectations') -Identity $script:AffActive -Values @{ Referent = (IdSP 'Referents' 'REF-2026-9001') } -Connection (Conn 'RD1') | Out-Null
        Attendre { $x = Lire 'Affectations' $script:AffActive; if ((Get-E2ELookupId $x['Referent']) -eq (IdSP 'Referents' 'REF-2026-9002')) { $x } } 'référent rétabli' | Should -Not -BeNullOrEmpty
    }
}

Describe 'S-06 / S-23 Champs protégés sur le jeu de test' -Tag 'Flux', 'Suivi' {
    It 'Le référent d''une affectation active du jeu (AFF-2026-9001) est rétabli et journalisé' {
        $id = IdSP 'Affectations' 'AFF-2026-9001'
        Set-PnPListItem -List (Url 'Affectations') -Identity $id -Values @{ Referent = (IdSP 'Referents' 'REF-2026-9002') } -Connection (Conn 'RD1') | Out-Null
        Attendre { $x = Lire 'Affectations' $id; if ((Get-E2ELookupId $x['Referent']) -eq (IdSP 'Referents' 'REF-2026-9001')) { $x } } 'référent rétabli' | Should -Not -BeNullOrEmpty
        @(Get-E2EJournal -Connection (Conn 'DIR_RD') -Model $script:Model -IdObjet 'AFF-2026-9001' | Where-Object { [string]$_['Niveau'] -eq 'Avertissement' }).Count | Should -BeGreaterThan 0
    }
    It 'Le référent principal d''un alternant (dérivé) modifié à la main est rétabli (P-09)' {
        $id = IdSP 'Alternants' 'ALT-2026-9001'
        Set-PnPListItem -List (Url 'Alternants') -Identity $id -Values @{ ReferentPrincipal = (IdSP 'Referents' 'REF-2026-9002') } -Connection (Conn 'RD1') | Out-Null
        Attendre { $x = Lire 'Alternants' $id; if ((Get-E2ELookupId $x['ReferentPrincipal']) -eq (IdSP 'Referents' 'REF-2026-9001')) { $x } } 'référent principal rétabli' | Should -Not -BeNullOrEmpty
    }
}

Describe 'S-07 / S-13 Livrable retourné en correction puis validé' -Tag 'Flux', 'Livrables' {
    BeforeAll {
        $v = @{ Title = "$($script:Marqueur) livrable"; Affectation = (IdSP 'Affectations' 'AFF-2026-9001'); TypeLivrable = 'Document technique'
            Proprietaire = (Upn 'ALT1'); Reviseur = (Upn 'REF1'); Echeance = (Get-Date).AddDays(10).Date }
        $script:L = [int](Add-PnPListItem -List (Url 'Livrables') -Values $v -Connection (Conn 'RD1')).Id
        $script:LIt = Attendre { $x = Lire 'Livrables' $script:L; if ($x['IdHNCS']) { $x } } 'IdHNCS du livrable'
        $script:LId = [string]$script:LIt['IdHNCS']
    }
    It 'Soumission par l''alternant (LIV-T02, LIV-T03 avec document)' {
        Set-PnPListItem -List (Url 'Livrables') -Identity $script:L -Values @{ Statut = 'En cours' } -Connection (Conn 'ALT1') | Out-Null
        Attendre-Historique $script:LId 'En cours' 'Acceptée' | Out-Null
        Set-PnPListItem -List (Url 'Livrables') -Identity $script:L -Values @{ LienDocument = "$($script:Cfg.SiteUrl)/LivrablesRD/e2e.docx, e2e"; Statut = 'Soumis à revue' } -Connection (Conn 'ALT1') | Out-Null
        Attendre { $x = Lire 'Livrables' $script:L; if ($x['DatePremierDepot']) { $x } } 'DatePremierDepot' | Should -Not -BeNullOrEmpty
    }
    It 'S-13 L''alternant ne peut pas valider son propre livrable (G_VALIDEUR_LEGITIME)' {
        Set-PnPListItem -List (Url 'Livrables') -Identity $script:L -Values @{ Statut = 'Validé' } -Connection (Conn 'ALT1') | Out-Null
        Attendre-Statut 'Livrables' $script:L 'Soumis à revue' | Out-Null
        Attendre-Historique $script:LId 'Validé' 'Refusée — annulée' | Should -Not -BeNullOrEmpty
    }
    It 'S-13 L''alternant ne peut pas se désigner réviseur (P-09, N-92)' {
        Set-PnPListItem -List (Url 'Livrables') -Identity $script:L -Values @{ Reviseur = (Upn 'ALT1') } -Connection (Conn 'ALT1') -ErrorAction SilentlyContinue | Out-Null
        Attendre { $x = Lire 'Livrables' $script:L; if ($x['Reviseur'] -and [string]$x['Reviseur'].Email -eq (Upn 'REF1')) { $x } } 'réviseur rétabli' | Should -Not -BeNullOrEmpty
    }
    It 'Corrections demandées par le réviseur (LIV-T06) : NbCorrections = 1 et action de correction' {
        Set-PnPListItem -List (Url 'Livrables') -Identity $script:L -Values @{ CommentaireRevue = 'Compléter la conclusion (E2E).'; Statut = 'Corrections demandées' } -Connection (Conn 'REF1') | Out-Null
        $x = Attendre { $y = Lire 'Livrables' $script:L; if ([int]$y['NbCorrections'] -eq 1) { $y } } 'NbCorrections = 1'
        [string]$x['DecisionRevue'] | Should -Be 'Corrections demandées'
        $q = "<View><Query><Where><Eq><FieldRef Name='Livrable' LookupId='TRUE' /><Value Type='Lookup'>$($script:L)</Value></Eq></Where></Query></View>"
        @(Get-PnPListItem -List (Url 'ActionsIntegration') -Query $q -Connection (Conn 'IT')).Count | Should -BeGreaterThan 0
    }
    It 'Resoumission puis validation : versions et commentaires conservés' {
        Set-PnPListItem -List (Url 'Livrables') -Identity $script:L -Values @{ Statut = 'Soumis à revue' } -Connection (Conn 'ALT1') | Out-Null
        Attendre-Statut 'Livrables' $script:L 'Soumis à revue' | Out-Null
        Set-PnPListItem -List (Url 'Livrables') -Identity $script:L -Values @{ CommentaireRevue = 'Conforme (E2E).'; Statut = 'Validé' } -Connection (Conn 'REF1') | Out-Null
        $x = Attendre { $y = Lire 'Livrables' $script:L; if ($y['DateValidation']) { $y } } 'DateValidation'
        [int]$x['NbCorrections'] | Should -Be 1
        $versions = @(Get-PnPListItemVersion -List (Url 'Livrables') -Identity $script:L -Connection (Conn 'IT'))
        $versions.Count | Should -BeGreaterThan 3
        @($versions | Where-Object { [string]$_.FieldValues['CommentaireRevue'] -match 'Compléter la conclusion' }).Count | Should -BeGreaterThan 0
    }
}

Describe 'S-14 / S-19 Partenariats : signature et décision réservées' -Tag 'Flux', 'Ecoles' {
    It 'S-19 Une décision de partenariat saisie par la relation écoles est rétablie (CONV-2026-9004)' {
        $id = IdSP 'Conventions' 'CONV-2026-9004'
        Set-PnPListItem -List (Url 'Conventions') -Identity $id -Values @{ DecisionPartenariat = 'Partenariat retenu' } -Connection (Conn 'ECOLES') | Out-Null
        Attendre { $x = Lire 'Conventions' $id; if ([string]$x['DecisionPartenariat'] -eq 'À examiner') { $x } } 'décision rétablie' | Should -Not -BeNullOrEmpty
    }
    It 'S-14 Signature d''une convention de partenariat sans décision : refusée (G_DECISION_PARTENARIAT)' {
        $v = @{ Title = "$($script:Marqueur) partenariat"; Etablissement = (IdSP 'Etablissements' 'ECO-2026-9004'); TypeConvention = 'Convention de partenariat' }
        $id = [int](Add-PnPListItem -List (Url 'Conventions') -Values $v -Connection (Conn 'ECOLES')).Id
        $c = Attendre { $x = Lire 'Conventions' $id; if ($x['IdHNCS']) { $x } } 'IdHNCS convention'
        Set-PnPListItem -List (Url 'Conventions') -Identity $id -Values @{ DateSignature = (Get-Date).Date; PreuveSignature = "$($script:Cfg.SiteUrl)/EcolesPartenariats/e2e.pdf, preuve"; Statut = 'Signée / active' } -Connection (Conn 'ECOLES') | Out-Null
        Attendre { $x = Lire 'Conventions' $id; if ([string]$x['Statut'] -ne 'Signée / active') { $x } } 'statut rétabli' | Should -Not -BeNullOrEmpty
        [string](Attendre-Historique ([string]$c['IdHNCS']) 'Signée / active' 'Refusée — annulée')['Motif'] | Should -Match 'G_DECISION_PARTENARIAT'
    }
}

Describe 'S-22 Arbitrage du portefeuille de sujets' -Tag 'Flux', 'Sujets' {
    It 'Un NO-GO sans motif est refusé ; un référent ne peut pas prioriser' {
        $v = @{ Title = "$($script:Marqueur) sujet"; TypeSujet = 'Autre'; Pole = (IdSP 'Poles' 'POL-P1') }
        $id = [int](Add-PnPListItem -List (Url 'SujetsRD') -Values $v -Connection (Conn 'RD1')).Id
        $s = Attendre { $x = Lire 'SujetsRD' $id; if ($x['IdHNCS']) { $x } } 'IdHNCS sujet'
        Set-PnPListItem -List (Url 'SujetsRD') -Identity $id -Values @{ Statut = 'Priorisé' } -Connection (Conn 'REF1') | Out-Null
        Attendre-Historique ([string]$s['IdHNCS']) 'Priorisé' 'Refusée — annulée' | Should -Not -BeNullOrEmpty
        Set-PnPListItem -List (Url 'SujetsRD') -Identity $id -Values @{ Statut = 'Abandonné' } -Connection (Conn 'DIR_RD') | Out-Null
        [string](Attendre-Historique ([string]$s['IdHNCS']) 'Abandonné' 'Refusée — annulée')['Motif'] | Should -Match 'G_MOTIF_DECISION'
    }
}

Describe 'S-26 Refus d''une création : élément envoyé à la corbeille (§ 6.1-3 bis)' -Tag 'Flux', 'Alternants' {
    It 'Une fiche alternant créée à la main sans reprise autorisée est retirée' {
        $v = @{ Title = "$($script:Marqueur) reprise"; DateDebut = (Get-Date).AddDays(-10).Date; DateFin = (Get-Date).AddDays(200).Date
            Etablissement = (IdSP 'Etablissements' 'ECO-2026-9001'); Pole = (IdSP 'Poles' 'POL-P1') }
        $id = [int](Add-PnPListItem -List (Url 'Alternants') -Values $v -Connection (Conn 'DIR_RD')).Id
        Attendre { if ($null -eq (Lire 'Alternants' $id)) { $true } } 'élément retiré (Fonction.RepriseExistantActive = Non)' | Should -BeTrue
    }
}

Describe 'S-10 Échec de flux visible et reprise maîtrisée' -Tag 'Lot1', 'Exploitation' {
    It 'L''erreur à reprendre du jeu de test est visible de la Direction R&D, invisible de l''équipe R&D' {
        @(Get-E2EJournal -Connection (Conn 'DIR_RD') -Model $script:Model -IdObjet 'CAND-2026-9007' | Where-Object { [string]$_['StatutReprise'] -eq 'À reprendre' }).Count | Should -BeGreaterThan 0
        $vu = @()
        try { $vu = @(Get-E2EJournal -Connection (Conn 'RD1') -Model $script:Model -IdObjet 'CAND-2026-9007') } catch { $vu = @() }
        $vu.Count | Should -Be 0
    }
    It 'Resoumission depuis RunUrl puis « Reprise effectuée » sans doublon' {
        Set-ItResult -Skipped -Because 'resoumission depuis le portail Power Automate : étape manuelle, voir scenarios.md S-10 et S-18'
    }
}

Describe 'S-18 Idempotence de l''import du jeu de test' -Tag 'Lot1', 'Import' {
    It 'Après deux imports successifs, chaque IdHNCS du jeu n''existe qu''une fois dans <_>' -ForEach @('Candidatures', 'Alternants', 'Affectations', 'Livrables', 'ActionsIntegration') {
        $data = Get-E2EData $script:Cfg.DataPath
        $items = @(Get-PnPListItem -List (Url $_) -PageSize 2000 -Fields 'IdHNCS' -Connection (Conn 'IT'))
        foreach ($d in @($data[$_])) {
            @($items | Where-Object { [string]$_['IdHNCS'] -eq [string]$d.IdHNCS }).Count | Should -Be 1 -Because "$($d.IdHNCS) unique"
        }
    }
}

Describe 'S-08 Rappel de retard : seuls les livrables concernés' -Tag 'Planifie', 'Livrables' {
    It 'Après exécution de PA-06 : LIV-2026-9003 en retard et rappelé, LIV-2026-9008 (suspendu) exclu' {
        $retard = Lire 'Livrables' (IdSP 'Livrables' 'LIV-2026-9003')
        $suspendu = Lire 'Livrables' (IdSP 'Livrables' 'LIV-2026-9008')
        [bool]$retard['EnRetard'] | Should -BeTrue
        [string]$retard['DernierRappel'] | Should -Not -BeNullOrEmpty
        [bool]$suspendu['EnRetard'] | Should -BeFalse
        [string]$suspendu['DernierRappel'] | Should -BeNullOrEmpty
    }
}

Describe 'S-20 Compte rendu non remis' -Tag 'Planifie', 'ComptesRendus' {
    It 'Après exécution de PA-08b : CR-2026-9009 (échu de plus de CR.DelaiNonRemisJours) passe « Non remis » par FLUX' {
        [string](Lire 'ComptesRendus' (IdSP 'ComptesRendus' 'CR-2026-9009'))['Statut'] | Should -Be 'Non remis'
        [string](Attendre-Historique 'CR-2026-9009' 'Non remis' 'Acceptée')['CodeTransition'] | Should -Be 'CR-T04-01'
    }
}

Describe 'S-21 Fin d''alternance' -Tag 'Flux', 'Destructif', 'Alternants' {
    It 'Fin effective de ALT-2026-9007 : affectation terminée à la date de fin réelle, checklist et bilan garantis' {
        $id = IdSP 'Alternants' 'ALT-2026-9007'
        $fin = (Get-Date).Date
        Set-PnPListItem -List (Url 'Alternants') -Identity $id -Values @{ DateFinReelle = $fin; Statut = 'Terminé'; MotifFin = 'Fin de contrat (E2E)' } -Connection (Conn 'RD1') | Out-Null
        $aff = Attendre-Statut 'Affectations' (IdSP 'Affectations' 'AFF-2026-9010') 'Terminée'
        ([datetime]$aff['DateFin']).Date | Should -Be $fin
        Set-PnPListItem -List (Url 'Alternants') -Identity $id -Values @{ Statut = 'Clôturé' } -Connection (Conn 'RD1') | Out-Null
        Attendre-Statut 'Alternants' $id 'Terminé' | Out-Null
        [string](Attendre-Historique 'ALT-2026-9007' 'Clôturé' 'Refusée — annulée')['Motif'] | Should -Match 'G_CLOTURE_ALTERNANCE'
    }
}
