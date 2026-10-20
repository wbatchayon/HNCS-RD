<#
.SYNOPSIS
    Fonctions communes des tests de bout en bout HNCS-RD (Pester 5 + PnP.PowerShell 2.x, PowerShell 7.4).
.DESCRIPTION
    Dot-sourcé par Access.Tests.ps1, HNCSRD.E2E.Tests.ps1 et reconciliation/Export-HNCSRDDonnees.ps1.
    Analysable par Windows PowerShell 5.1 (aucun opérateur propre à PowerShell 7).
#>

Set-StrictMode -Version 2.0

$script:E2EConnexions = @{}
$script:E2ERang = @{ '-' = 0; 'R' = 1; 'CSS' = 2; 'FC' = 3 }

function Read-E2EJson([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "Fichier introuvable : $Path" }
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Get-E2EConfig {
    <# Charge tests/e2e/config.json (ou HNCSRD_E2E_CONFIG) et résout les chemins relatifs. #>
    param([string]$Path)
    if (-not $Path) { $Path = $env:HNCSRD_E2E_CONFIG }
    if (-not $Path) { $Path = Join-Path $PSScriptRoot 'config.json' }
    $cfg = Read-E2EJson $Path
    $base = Split-Path -Parent (Resolve-Path -LiteralPath $Path)
    foreach ($k in 'PersonasPath', 'ModelPath', 'DataPath') {
        $v = [string]$cfg.$k
        if ($v -and -not [System.IO.Path]::IsPathRooted($v)) { $cfg.$k = [System.IO.Path]::GetFullPath((Join-Path $base $v)) }
    }
    $cfg.SiteUrl = ([string]$cfg.SiteUrl).TrimEnd('/')
    return $cfg
}

function Get-E2EPersonas([string]$Path) {
    $t = @{}
    foreach ($p in (Read-E2EJson $Path).PSObject.Properties) {
        if ($p.MemberType -ne 'NoteProperty' -or $p.Name.StartsWith('$')) { continue }
        $t[$p.Name] = $p.Value
    }
    return $t
}

function Get-E2EData([string]$Path) {
    $d = @{}
    foreach ($f in (Get-ChildItem -LiteralPath $Path -Filter '*.json')) {
        $d[[System.IO.Path]::GetFileNameWithoutExtension($f.Name)] = @(Read-E2EJson $f.FullName)
    }
    return $d
}

function Get-E2EObjet($Model, [string]$Nom) {
    return @($Model.objects | Where-Object { $_.name -eq $Nom })[0]
}

function Get-E2EListUrl($Model, [string]$Nom) {
    $o = Get-E2EObjet $Model $Nom
    if ($o.kind -eq 'library') { return [string]$o.name }
    return ('Lists/' + $o.name)
}

function Get-E2EGroupName($Model, [string]$Code) {
    return [string]@($Model.groups | Where-Object { $_.code -eq $Code })[0].name
}

function Connect-E2EPersona {
    <# Connexion PnP d'une persona (mise en cache). L'utilisateur s'authentifie avec le compte de la persona. #>
    param([Parameter(Mandatory = $true)]$Config, [Parameter(Mandatory = $true)]$Personas, [Parameter(Mandatory = $true)][string]$Cle)
    if ($script:E2EConnexions.ContainsKey($Cle)) { return $script:E2EConnexions[$Cle] }
    if (-not $Personas.ContainsKey($Cle)) { throw "Persona $Cle absente de $($Config.PersonasPath)" }
    Write-Host ("Authentification de la persona {0} ({1})" -f $Cle, $Personas[$Cle].upn) -ForegroundColor Yellow
    $p = @{ Url = $Config.SiteUrl; ClientId = [string]$Config.ClientId; ReturnConnection = $true; ErrorAction = 'Stop' }
    if ([string]$Config.ModeConnexion -eq 'DeviceLogin') { $p['DeviceLogin'] = $true; $p['Tenant'] = [string]$Config.Tenant }
    else { $p['Interactive'] = $true; $p['ForceAuthentication'] = $true }
    $c = Connect-PnPOnline @p
    $script:E2EConnexions[$Cle] = $c
    return $c
}

function Get-E2EServerRelativeUrl([string]$SiteUrl, [string]$ListUrl) {
    return (([uri]$SiteUrl).AbsolutePath.TrimEnd('/') + '/' + $ListUrl)
}

function ConvertTo-E2EPermissions($Low, $High) {
    $lo = [int64]$Low; $hi = [int64]$High
    $bit = { param([int]$n) if ($n -le 32) { return (($lo -band ([int64]1 -shl ($n - 1))) -ne 0) } return (($hi -band ([int64]1 -shl ($n - 33))) -ne 0) }
    $full = ($lo -eq 4294967295 -or $lo -eq -1) -and ($hi -eq 2147483647)
    return [pscustomobject]@{
        Lecture           = $full -or (& $bit 1)
        Ajout             = $full -or (& $bit 2)
        Modification      = $full -or (& $bit 3)
        Suppression       = $full -or (& $bit 4)
        GererPermissions  = $full -or (& $bit 26)
    }
}

function Get-E2EPermissions {
    <# Permissions effectives de l'utilisateur connecté sur une liste ou un élément (API REST EffectiveBasePermissions). #>
    param([Parameter(Mandatory = $true)]$Connection, [Parameter(Mandatory = $true)]$Config, [Parameter(Mandatory = $true)]$Model,
        [Parameter(Mandatory = $true)][string]$Objet, [int]$ItemId = 0)
    $u = Get-E2EServerRelativeUrl $Config.SiteUrl (Get-E2EListUrl $Model $Objet)
    $chemin = "_api/web/GetList(@u)"
    if ($ItemId -gt 0) { $chemin += "/items($ItemId)" }
    $url = $Config.SiteUrl + '/' + $chemin + "/EffectiveBasePermissions?@u='" + $u + "'"
    try {
        $r = Invoke-PnPSPRestMethod -Url $url -Method Get -Connection $Connection -ErrorAction Stop
        $low = $r.Low; $high = $r.High
        if ($null -eq $low -and $r.PSObject.Properties['d']) { $low = $r.d.EffectiveBasePermissions.Low; $high = $r.d.EffectiveBasePermissions.High }
        return (ConvertTo-E2EPermissions $low $high)
    }
    catch {
        return [pscustomobject]@{ Lecture = $false; Ajout = $false; Modification = $false; Suppression = $false; GererPermissions = $false }
    }
}

function Get-E2EAttendu {
    <# Niveau attendu d'une persona sur un objet d'après la matrice § 7.3 : Base (FC/CSS/R/-) et niveaux IL accordables. #>
    param([Parameter(Mandatory = $true)]$Model, [Parameter(Mandatory = $true)]$Persona, [Parameter(Mandatory = $true)][string]$Objet)
    $ligne = $Model.matrix.$Objet
    $base = '-'; $il = @()
    foreach ($g in @($Persona.groupes)) {
        $niveau = [string]$ligne.$g
        # Notations § 7.2 : FC, CSS, R, -, IL(x) et R+IL(x) (lecture de la liste + x sur les éléments dont on est responsable)
        $m = [regex]::Match($niveau, '^(?:(R)\+)?IL\((\w+)\)$')
        if ($m.Success) {
            $il += [pscustomobject]@{ Groupe = $g; Niveau = $m.Groups[2].Value }
            if ($m.Groups[1].Success) { $niveau = 'R' } else { $niveau = '-' }
        }
        if ($script:E2ERang[$niveau] -gt $script:E2ERang[$base]) { $base = $niveau }
    }
    return [pscustomobject]@{ Base = $base; IL = $il }
}

function Get-E2EItem {
    <# Élément par IdHNCS (ou $null s'il est invisible pour la connexion). #>
    param([Parameter(Mandatory = $true)]$Connection, [Parameter(Mandatory = $true)]$Model, [Parameter(Mandatory = $true)][string]$Liste,
        [Parameter(Mandatory = $true)][string]$IdHNCS, [string]$Champ = 'IdHNCS')
    $q = "<View><Query><Where><Eq><FieldRef Name='$Champ' /><Value Type='Text'>$IdHNCS</Value></Eq></Where></Query><RowLimit>5</RowLimit></View>"
    try { $r = @(Get-PnPListItem -List (Get-E2EListUrl $Model $Liste) -Query $q -Connection $Connection -ErrorAction Stop) }
    catch { return $null }
    if ($r.Count -eq 0) { return $null }
    return $r[0]
}

function Get-E2EItemById {
    param([Parameter(Mandatory = $true)]$Connection, [Parameter(Mandatory = $true)]$Model, [Parameter(Mandatory = $true)][string]$Liste, [Parameter(Mandatory = $true)][int]$Id)
    try { return (Get-PnPListItem -List (Get-E2EListUrl $Model $Liste) -Id $Id -Connection $Connection -ErrorAction Stop) }
    catch { return $null }
}

function Get-E2EIdSP {
    <# ID SharePoint d'un élément à partir de son IdHNCS (0 si introuvable), avec cache. #>
    param([Parameter(Mandatory = $true)]$Connection, [Parameter(Mandatory = $true)]$Model, [Parameter(Mandatory = $true)][string]$Liste,
        [Parameter(Mandatory = $true)][string]$IdHNCS)
    if (-not (Test-Path variable:script:E2ECacheIds)) { $script:E2ECacheIds = @{} }
    $k = "$Liste|$IdHNCS"
    if (-not $script:E2ECacheIds.ContainsKey($k)) {
        $it = Get-E2EItem -Connection $Connection -Model $Model -Liste $Liste -IdHNCS $IdHNCS
        if ($it) { $script:E2ECacheIds[$k] = [int]$it.Id } else { $script:E2ECacheIds[$k] = 0 }
    }
    return $script:E2ECacheIds[$k]
}

function Get-E2EChamp($Item, [string]$Nom) {
    if ($null -eq $Item) { return $null }
    return $Item.FieldValues[$Nom]
}

function Get-E2ELookupId($Valeur) {
    if ($null -eq $Valeur) { return $null }
    if ($Valeur -is [Microsoft.SharePoint.Client.FieldLookupValue]) { return [int]$Valeur.LookupId }
    return [int]$Valeur
}

function Wait-E2ECondition {
    <# Interroge une condition jusqu'à ce qu'elle renvoie une valeur non nulle et non fausse ; lève une erreur au délai. #>
    param([Parameter(Mandatory = $true)][scriptblock]$Condition, [Parameter(Mandatory = $true)]$Config, [string]$Message = 'condition', [int]$DelaiSecondes = 0)
    if ($DelaiSecondes -le 0) { $DelaiSecondes = [int]$Config.DelaiFluxSecondes }
    $fin = (Get-Date).AddSeconds($DelaiSecondes)
    do {
        $r = & $Condition
        if ($r) { return $r }
        Start-Sleep -Seconds ([int]$Config.IntervalleSondageSecondes)
    } while ((Get-Date) -lt $fin)
    throw "Délai dépassé ($DelaiSecondes s) en attente de : $Message"
}

function Get-E2EHistorique {
    <# Entrées de HistoriqueStatuts d'un objet (lecture par une persona habilitée : G_DRD, G_RD, G_ADM ou G_PROP). #>
    param([Parameter(Mandatory = $true)]$Connection, [Parameter(Mandatory = $true)]$Model, [Parameter(Mandatory = $true)][string]$IdHNCS)
    $q = "<View><Query><Where><Eq><FieldRef Name='Title' /><Value Type='Text'>$IdHNCS</Value></Eq></Where><OrderBy><FieldRef Name='DateChangement' /></OrderBy></Query></View>"
    return @(Get-PnPListItem -List (Get-E2EListUrl $Model 'HistoriqueStatuts') -Query $q -Connection $Connection)
}

function Get-E2EJournal {
    param([Parameter(Mandatory = $true)]$Connection, [Parameter(Mandatory = $true)]$Model, [Parameter(Mandatory = $true)][string]$IdObjet)
    $q = "<View><Query><Where><Eq><FieldRef Name='IdObjet' /><Value Type='Text'>$IdObjet</Value></Eq></Where><OrderBy><FieldRef Name='DateEvenement' Ascending='FALSE' /></OrderBy></Query></View>"
    return @(Get-PnPListItem -List (Get-E2EListUrl $Model 'JournalFlux') -Query $q -Connection $Connection)
}

function New-E2EMarqueur {
    <# Marqueur unique des éléments créés par un passage de tests (repérage et nettoyage manuel). #>
    return ('E2E-' + (Get-Date).ToString('yyyyMMddHHmmss'))
}

function Get-E2EAccesElementAttendu {
    <# Accès attendu (niveau ou $null) d'une persona à un élément du jeu de test, selon les règles de § 7.4. #>
    param([Parameter(Mandatory = $true)][string]$Objet, [Parameter(Mandatory = $true)][string]$Groupe, [Parameter(Mandatory = $true)][string]$PersonaCle,
        [Parameter(Mandatory = $true)]$Item, [Parameter(Mandatory = $true)]$Data,
        [ValidateSet('Groupe', 'Destinataire')][string]$PartageTransmission = 'Groupe')
    $moi = '@persona:' + $PersonaCle
    $alt = @{}
    foreach ($a in @($Data['Alternants'])) { if ($a.PSObject.Properties['CompteM365']) { $alt[[string]$a.IdHNCS] = [string]$a.CompteM365 } }
    $mesRef = @()
    foreach ($r in @($Data['Referents'])) { if ([string]$r.Compte -eq $moi) { $mesRef += [string]$r.IdHNCS } }
    $champ = {
        param($Objet, [string]$Nom)
        if ($Objet.PSObject.Properties[$Nom]) { return [string]$Objet.$Nom }
        return ''
    }
    $transmis = @("Transmise à l'administration", 'Entretien planifié', 'Entretien réalisé', 'En attente de décision', 'Retenue', 'Formalités en cours', 'Intégrée')
    $cle = "$Objet|$Groupe"
    switch ($cle) {
        'Candidatures|G_ADM' {
            $transmise = $transmis -contains [string]$Item.Statut -or ($Item.PSObject.Properties['DateTransmissionAdmin'] -and $Item.DateTransmissionAdmin)
            if (-not $transmise) { return $null }
            # Recrutement.PartageTransmission (H-45) : Groupe = toute l'administration ; Destinataire = DestinataireAdmin seul
            if ($PartageTransmission -eq 'Destinataire' -and (& $champ $Item 'DestinataireAdmin') -ne $moi) { return $null }
            return 'CSS'
        }
        'Affectations|G_ALT' {
            if ($Item.PSObject.Properties['EmpreinteVerrou'] -and $Item.EmpreinteVerrou -and $alt[[string]$Item.Alternant] -eq $moi) { return 'R' }
            return $null
        }
        'Livrables|G_ALT' { if ([string]$Item.Proprietaire -eq $moi) { return 'CSS' }; return $null }
        'ComptesRendus|G_ALT' { if ($alt[[string]$Item.Alternant] -eq $moi) { return 'CSS' }; return $null }
        'ComptesRendus|G_REF' { if ((& $champ $Item 'Valideur') -eq $moi) { return 'CSS' }; return $null }
        'Alternants|G_REF' {
            if ($mesRef -contains (& $champ $Item 'ReferentPrincipal')) { return 'R' }
            foreach ($f in @($Data['Affectations'])) {
                if ([string]$f.Alternant -eq [string]$Item.IdHNCS -and $mesRef -contains (& $champ $f 'Referent')) { return 'R' }
            }
            return $null
        }
        'ActionsIntegration|G_REF' { if ((& $champ $Item 'Responsable') -eq $moi) { return 'CSS' }; return $null }
        'ActionsIntegration|G_ECO' { if ((& $champ $Item 'Responsable') -eq $moi) { return 'CSS' }; return $null }
        'BilansAlternance|G_REF' { if ($mesRef -contains (& $champ $Item 'Referent')) { return 'CSS' }; return $null }
        'RegistreModeles|G_REF' { if ((& $champ $Item 'Proprietaire') -eq $moi) { return 'CSS' }; return $null }
        'CommunicationsRD|G_ALT' { if ((& $champ $Item 'Auteur') -eq $moi) { return 'CSS' }; return $null }
    }
    throw "Règle § 7.4 non automatisée pour $cle"
}
