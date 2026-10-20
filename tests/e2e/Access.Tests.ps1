<#
.SYNOPSIS
    Droits d'accès persona par persona, PILOTÉS PAR LA MATRICE du modèle généré (spec § 7.3 et § 7.4).
.DESCRIPTION
    Pour chaque persona de testdata/personas.json et chaque objet de « matrix » (provisioning/model/model.generated.json) :
      - niveau de base attendu = maximum des niveaux des groupes de la persona (FC > CSS > R > -) ;
      - FC  : lecture, ajout, modification, gestion des permissions ;
      - CSS : lecture, ajout, modification, PAS de suppression ;
      - R   : lecture, ni ajout ni modification (tentative d'ajout refusée) ;
      - « - » : aucune lecture au niveau liste (aucun élément visible hors IL) ;
      - IL(x) : pour chaque élément du jeu de test, accès x si la règle § 7.4 l'accorde à la persona, sinon aucun accès ;
      - R+IL(x) : lecture de toute la liste, écriture x seulement sur les éléments dont la persona est responsable.
    Prérequis : site de recette provisionné, membres ajoutés (Set-HNCSRDMembres.ps1 avec le fichier produit par
    Import-TestData.ps1 -ExporterMembres), jeu de test importé avec -PermissionsElement (ou flux actifs).
    Exécution (PowerShell 7.4, Pester 5, PnP.PowerShell 2.x) :
        $env:HNCSRD_E2E_CONFIG = './tests/e2e/config.json'
        Invoke-Pester ./tests/e2e/Access.Tests.ps1 -Output Detailed
#>

BeforeDiscovery {
    . (Join-Path $PSScriptRoot 'HNCSRD.E2E.Common.ps1')
    $cfgD = Get-E2EConfig
    $modelD = Read-E2EJson $cfgD.ModelPath
    $personasD = Get-E2EPersonas $cfgD.PersonasPath
    $ignorees = @($cfgD.PersonasIgnorees)
    $casBase = @()
    $casIL = @()
    foreach ($cle in ($personasD.Keys | Sort-Object)) {
        if ($ignorees -contains $cle) { continue }
        foreach ($objet in $modelD.matrix.PSObject.Properties.Name) {
            $att = Get-E2EAttendu -Model $modelD -Persona $personasD[$cle] -Objet $objet
            $kind = [string](Get-E2EObjet $modelD $objet).kind
            $casBase += @{ Persona = $cle; Objet = $objet; Base = $att.Base; AvecIL = (@($att.IL).Count -gt 0); Kind = $kind }
            foreach ($il in @($att.IL)) {
                $casIL += @{ Persona = $cle; Objet = $objet; Groupe = $il.Groupe; Niveau = $il.Niveau; Kind = $kind; Base = $att.Base }
            }
        }
    }
}

BeforeAll {
    . (Join-Path $PSScriptRoot 'HNCSRD.E2E.Common.ps1')
    $script:Cfg = Get-E2EConfig
    $script:Model = Read-E2EJson $script:Cfg.ModelPath
    $script:Personas = Get-E2EPersonas $script:Cfg.PersonasPath
    $script:Data = Get-E2EData $script:Cfg.DataPath
    $script:IdsSP = @{}
    $script:Partage = 'Groupe'
    if ($script:Cfg.PSObject.Properties['PartageTransmission'] -and $script:Cfg.PartageTransmission) { $script:Partage = [string]$script:Cfg.PartageTransmission }
    $proprio = @($script:Personas.Keys | Where-Object { $script:Personas[$_].groupes -contains 'G_PROP' -and -not $script:Personas[$_].PSObject.Properties['compteService'] })[0]
    $script:ConnProprio = Connect-E2EPersona -Config $script:Cfg -Personas $script:Personas -Cle $proprio
    function Get-IdSP([string]$Liste, [string]$IdHNCS) {
        $k = "$Liste|$IdHNCS"
        if (-not $script:IdsSP.ContainsKey($k)) {
            $it = Get-E2EItem -Connection $script:ConnProprio -Model $script:Model -Liste $Liste -IdHNCS $IdHNCS
            $script:IdsSP[$k] = if ($it) { [int]$it.Id } else { 0 }
        }
        return $script:IdsSP[$k]
    }
}

Describe 'Matrice § 7.3 : niveau de base par persona et par objet' -Tag 'Acces' {
    It '<Persona> / <Objet> : niveau de base <Base>' -ForEach $casBase {
        $conn = Connect-E2EPersona -Config $script:Cfg -Personas $script:Personas -Cle $Persona
        $perm = Get-E2EPermissions -Connection $conn -Config $script:Cfg -Model $script:Model -Objet $Objet
        switch ($Base) {
            'FC' {
                $perm.Lecture | Should -BeTrue
                $perm.Modification | Should -BeTrue
                $perm.GererPermissions | Should -BeTrue
            }
            'CSS' {
                $perm.Lecture | Should -BeTrue -Because 'CSS donne la lecture'
                $perm.Ajout | Should -BeTrue -Because 'CSS donne l''ajout'
                $perm.Modification | Should -BeTrue -Because 'CSS donne la modification'
                $perm.Suppression | Should -BeFalse -Because 'CSS = contribution SANS suppression (P-07)'
                $perm.GererPermissions | Should -BeFalse
            }
            'R' {
                $perm.Lecture | Should -BeTrue
                $perm.Ajout | Should -BeFalse
                $perm.Modification | Should -BeFalse
                if ($Kind -eq 'list') {
                    { Add-PnPListItem -List (Get-E2EListUrl $script:Model $Objet) -Values @{ Title = 'E2E-SONDE-ECRITURE' } -Connection $conn -ErrorAction Stop } |
                        Should -Throw -Because 'une écriture doit être refusée en lecture seule'
                }
            }
            default {
                $perm.Lecture | Should -BeFalse -Because 'aucun accès au niveau liste'
                $perm.Ajout | Should -BeFalse
                if (-not $AvecIL -and $Kind -eq 'list') {
                    $visibles = @()
                    try { $visibles = @(Get-PnPListItem -List (Get-E2EListUrl $script:Model $Objet) -PageSize 10 -Connection $conn -ErrorAction Stop) } catch { $visibles = @() }
                    $visibles.Count | Should -Be 0 -Because 'aucun élément ne doit être visible'
                }
            }
        }
    }
}

Describe 'Matrice § 7.3 / § 7.4 : accès au niveau élément (IL)' -Tag 'Acces', 'Element' {
    It '<Persona> / <Objet> : IL(<Niveau>) via <Groupe> (base <Base>)' -ForEach $casIL {
        if ($Kind -eq 'library') {
            Set-ItResult -Skipped -Because 'permissions de dossiers posées par les flux : voir scenarios.md S-24'
            return
        }
        $items = @($script:Data[$Objet])
        if ($items.Count -eq 0) { Set-ItResult -Skipped -Because "aucun élément $Objet dans le jeu de test"; return }
        $conn = Connect-E2EPersona -Config $script:Cfg -Personas $script:Personas -Cle $Persona
        $verifies = 0
        foreach ($it in $items) {
            $id = Get-IdSP $Objet ([string]$it.IdHNCS)
            if ($id -eq 0) { continue }
            $attendu = Get-E2EAccesElementAttendu -Objet $Objet -Groupe $Groupe -PersonaCle $Persona -Item $it -Data $script:Data -PartageTransmission $script:Partage
            $perm = Get-E2EPermissions -Connection $conn -Config $script:Cfg -Model $script:Model -Objet $Objet -ItemId $id
            if ($attendu) {
                $perm.Lecture | Should -BeTrue -Because "$($it.IdHNCS) doit être visible pour $Persona (§ 7.4)"
                $perm.Modification | Should -Be ($attendu -eq 'CSS') -Because "$($it.IdHNCS) : niveau $attendu"
                $perm.Suppression | Should -BeFalse
            }
            elseif ($Base -eq '-') {
                $perm.Lecture | Should -BeFalse -Because "$($it.IdHNCS) ne doit pas être visible pour $Persona"
            }
            else {
                # R+IL(x) : lecture de la liste, écriture réservée aux éléments dont la persona est responsable
                $perm.Lecture | Should -BeTrue
                $perm.Modification | Should -Be ($script:E2ERang[$Base] -ge 2) -Because "$($it.IdHNCS) : niveau de base $Base"
            }
            $verifies++
        }
        $verifies | Should -BeGreaterThan 0 -Because 'le jeu de test doit être importé'
    }
}

Describe 'Cloisonnement des données personnelles (P-04)' -Tag 'Acces' {
    It 'La Direction ne voit aucune liste nominative ni aucun CV (§ 7.5)' {
        $dir = @($script:Personas.Keys | Where-Object { @($script:Personas[$_].groupes) -contains 'G_DIR' })[0]
        $conn = Connect-E2EPersona -Config $script:Cfg -Personas $script:Personas -Cle $dir
        foreach ($objet in 'Candidatures', 'Entretiens', 'Recrutement', 'Administration', 'Alternants', 'SuiviAlternants', 'Livrables', 'Etablissements', 'BilansAlternance') {
            (Get-E2EPermissions -Connection $conn -Config $script:Cfg -Model $script:Model -Objet $objet).Lecture | Should -BeFalse -Because $objet
        }
    }
    It 'L''administration ne voit pas une candidature non transmise (H-29)' {
        $adm = @($script:Personas.Keys | Where-Object { @($script:Personas[$_].groupes) -contains 'G_ADM' })[0]
        $conn = Connect-E2EPersona -Config $script:Cfg -Personas $script:Personas -Cle $adm
        Get-E2EItem -Connection $conn -Model $script:Model -Liste 'Candidatures' -IdHNCS 'CAND-2026-9003' | Should -BeNullOrEmpty
        Get-E2EItem -Connection $conn -Model $script:Model -Liste 'Candidatures' -IdHNCS 'CAND-2026-9008' | Should -Not -BeNullOrEmpty
    }
    It 'Un ancien alternant (accès retirés) n''accède à rien' {
        $anciens = @($script:Personas.Keys | Where-Object { @($script:Personas[$_].groupes).Count -eq 0 })
        if ($anciens.Count -eq 0) { Set-ItResult -Skipped -Because 'aucune persona sans groupe'; return }
        $conn = $null
        try { $conn = Connect-E2EPersona -Config $script:Cfg -Personas $script:Personas -Cle $anciens[0] } catch { $conn = $null }
        if ($null -eq $conn) { return }
        foreach ($objet in $script:Model.matrix.PSObject.Properties.Name) {
            (Get-E2EPermissions -Connection $conn -Config $script:Cfg -Model $script:Model -Objet $objet).Lecture | Should -BeFalse -Because $objet
        }
    }
}
