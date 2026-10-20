#Requires -Version 5.1
<#
.SYNOPSIS
    Importe la solution Power Platform HNCSRDSuivi (flux Power Automate HNCS-RD) et active les flux du lot demandé.

.DESCRIPTION
    1. (option -Build) construit flows/dist/HNCSRDSuivi_<specVersion>.zip avec flows/build/build_solution.py --brouillon :
       tous les flux sont importés à l'état Brouillon, aucun ne s'active pendant l'import ;
    2. sélectionne ou crée le profil d'authentification pac (pac auth) ;
    3. importe la solution non gérée avec le fichier de paramètres de déploiement (pac solution import --settings-file) ;
    4. active les flux de lot inférieur ou égal à -Lot (colonne Lot du catalogue, reprise dans flows/manifest.json),
       via l'API Web Dataverse, en deux phases :
         - phase Socle : PA-00A, PA-00B, PA-00C, puis les autres flux PA-00x du lot ;
         - à partir du lot 2 : pause pour passer le paramètre Fonction.Lot2Actif à Oui (liste Parametres), exécuter PA-00D
           manuellement (« Exécuter ») et vérifier les entrées REPRISE de la reprise de l'existant (spec 6.1, point 3 ter ; H-57) ;
         - phase Listes : les autres flux du lot ;
       PA-13 n'est jamais activé (activation manuelle après validation de la durée de conservation, H-10) ;
       les flux de lot supérieur à -Lot sont laissés ou remis à l'état Brouillon ;
    5. (option -ShareWith) partage les flux enfants (accès en lecture) avec les comptes indiqués.

    L'activation et le partage utilisent un jeton d'accès obtenu par Get-AzAccessToken (module Az.Accounts) ;
    sans ce module, l'import est réalisé et l'activation doit être faite à la main (ordre indiqué en sortie).

.PARAMETER EnvironmentUrl
    URL de l'environnement Dataverse (ex. https://contoso.crm4.dynamics.com).

.PARAMETER Lot
    Lot déployé (1 à 5). Seuls les flux de lot inférieur ou égal sont activés (colonne Lot du catalogue, manifeste des flux).

.PARAMETER SettingsFile
    Fichier de paramètres de déploiement : copie renseignée de deploymentSettings.sample.json. Le chemin par défaut
    flows/deploy/deploymentSettings.json est ignoré par git (il contient des adresses et des identifiants de connexion).

.PARAMETER Phase
    Tout (défaut), Socle (flux PA-00x uniquement) ou Listes (autres flux du lot, après l'exécution manuelle de PA-00D).

.PARAMETER SansPause
    Enchaîne les phases sans attendre la confirmation de l'exécution manuelle de PA-00D (à réserver à une recette sans données reprises).

.EXAMPLE
    .\Import-HNCSRDFlows.ps1 -EnvironmentUrl https://contoso.crm4.dynamics.com -Lot 2 -Build
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$EnvironmentUrl,

    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 5)]
    [int]$Lot,

    [string]$SettingsFile = (Join-Path $PSScriptRoot 'deploymentSettings.json'),

    [string]$SolutionZip,

    [switch]$Build,

    [string]$AuthProfile,

    [ValidateSet('Tout', 'Socle', 'Listes')]
    [string]$Phase = 'Tout',

    [switch]$SansPause,

    [switch]$SkipActivation,

    [string[]]$ShareWith = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$FlowsRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $FlowsRoot
$ChildCodes = @('PA-00A', 'PA-00B', 'PA-00C')
$NeverActivate = @('PA-13')

function Write-Step([string]$Message) {
    Write-Host ('==> ' + $Message) -ForegroundColor Cyan
}

function Get-SpecVersion {
    $modelPath = Join-Path $RepoRoot 'provisioning\model\model.generated.json'
    $model = Get-Content -LiteralPath $modelPath -Raw -Encoding UTF8 | ConvertFrom-Json
    return [string]$model.specVersion
}

function Invoke-Pac([string[]]$Arguments) {
    Write-Verbose ('pac ' + ($Arguments -join ' '))
    & pac @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw ('Échec de la commande pac ' + ($Arguments -join ' ') + ' (code ' + $LASTEXITCODE + ')')
    }
}

function Get-DataverseToken([string]$Url) {
    if (-not (Get-Command -Name Get-AzAccessToken -ErrorAction SilentlyContinue)) {
        return $null
    }
    try {
        $tok = Get-AzAccessToken -ResourceUrl $Url
        if ($tok.Token -is [System.Security.SecureString]) {
            $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($tok.Token)
            try { return [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr) }
            finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
        }
        return [string]$tok.Token
    }
    catch {
        Write-Warning ('Jeton Dataverse indisponible (Connect-AzAccount requis) : ' + $_.Exception.Message)
        return $null
    }
}

function Invoke-Dataverse([string]$Method, [string]$Path, $Body, [string]$Token) {
    $headers = @{
        'Authorization'    = 'Bearer ' + $Token
        'OData-MaxVersion' = '4.0'
        'OData-Version'    = '4.0'
        'Accept'           = 'application/json'
        'Content-Type'     = 'application/json; charset=utf-8'
    }
    $uri = $EnvironmentUrl.TrimEnd('/') + '/api/data/v9.2/' + $Path
    if ($null -ne $Body) {
        $json = $Body | ConvertTo-Json -Depth 10
        return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -Body ([Text.Encoding]::UTF8.GetBytes($json))
    }
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
}

function Set-FlowState($Flow, [bool]$Enabled, [string]$Token) {
    if ($Enabled) {
        $etat = @{ statecode = 1; statuscode = 2 }
        $verbe = 'Activer'
    }
    else {
        $etat = @{ statecode = 0; statuscode = 1 }
        $verbe = 'Laisser en brouillon'
    }
    if ($PSCmdlet.ShouldProcess($Flow.displayName, $verbe)) {
        Write-Step ($verbe + ' : ' + $Flow.displayName)
        Invoke-Dataverse 'PATCH' ('workflows(' + $Flow.workflowId + ')') $etat $Token | Out-Null
    }
}

# --------------------------------------------------------------------------------------------
# 0. Prérequis
# --------------------------------------------------------------------------------------------
if (-not (Get-Command -Name pac -ErrorAction SilentlyContinue)) {
    throw 'Power Platform CLI (pac) introuvable : installez-la (https://aka.ms/PowerPlatformCLI).'
}
if (-not (Test-Path -LiteralPath $SettingsFile)) {
    throw ('Fichier de paramètres introuvable : ' + $SettingsFile + ' (copier deploymentSettings.sample.json et le renseigner ; ce fichier est ignoré par git).')
}
$settings = Get-Content -LiteralPath $SettingsFile -Raw -Encoding UTF8 | ConvertFrom-Json
$incomplete = @()
foreach ($ev in $settings.EnvironmentVariables) {
    if ([string]::IsNullOrWhiteSpace([string]$ev.Value) -or ([string]$ev.Value).StartsWith('<')) { $incomplete += $ev.SchemaName }
}
foreach ($cr in $settings.ConnectionReferences) {
    if ([string]::IsNullOrWhiteSpace([string]$cr.ConnectionId) -or ([string]$cr.ConnectionId).StartsWith('<')) { $incomplete += $cr.LogicalName }
}
if ($incomplete.Count -gt 0) {
    throw ('Paramètres de déploiement à renseigner : ' + ($incomplete -join ', '))
}


$version = Get-SpecVersion
if ([string]::IsNullOrWhiteSpace($SolutionZip)) {
    $SolutionZip = Join-Path $FlowsRoot ('dist\HNCSRDSuivi_' + $version + '.zip')
}

# --------------------------------------------------------------------------------------------
# 1. Construction (tous les flux en brouillon : aucune activation pendant l'import)
# --------------------------------------------------------------------------------------------
if ($Build) {
    Write-Step 'Construction de la solution (flux en brouillon)'
    $python = Get-Command -Name python -ErrorAction SilentlyContinue
    if ($null -eq $python) { throw 'python introuvable.' }
    & $python.Source (Join-Path $FlowsRoot 'build\build_solution.py') '--brouillon'
    if ($LASTEXITCODE -ne 0) { throw 'Échec de build_solution.py' }
}
if (-not (Test-Path -LiteralPath $SolutionZip)) {
    throw ('Solution introuvable : ' + $SolutionZip + ' (utiliser -Build).')
}
$catalogPath = Join-Path $FlowsRoot 'dist\workflows.json'
if (-not (Test-Path -LiteralPath $catalogPath)) {
    throw ('Catalogue des flux introuvable : ' + $catalogPath + ' (produit par build_solution.py).')
}
$catalog = @(Get-Content -LiteralPath $catalogPath -Raw -Encoding UTF8 | ConvertFrom-Json)
$manifest = @(Get-Content -LiteralPath (Join-Path $FlowsRoot 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json)
$lots = @{}
foreach ($m in $manifest) { $lots[$m.id] = [int]$m.lot }
foreach ($w in $catalog) {
    if ($w.PSObject.Properties.Name -notcontains 'lot') {
        $w | Add-Member -NotePropertyName lot -NotePropertyValue $lots[$w.id]
    }
}
$draftBuild = $false
if ($catalog.Count -gt 0 -and ($catalog[0].PSObject.Properties.Name -contains 'brouillon')) { $draftBuild = [bool]$catalog[0].brouillon }
if (-not $draftBuild) {
    Write-Warning 'La solution n''a pas été construite en brouillon : des flux peuvent s''activer pendant l''import. Utiliser -Build (ou build_solution.py --brouillon).'
}

# --------------------------------------------------------------------------------------------
# 2. Authentification pac
# --------------------------------------------------------------------------------------------
Write-Step 'Authentification Power Platform'
if (-not [string]::IsNullOrWhiteSpace($AuthProfile)) {
    Invoke-Pac @('auth', 'select', '--name', $AuthProfile)
}
else {
    Invoke-Pac @('auth', 'create', '--environment', $EnvironmentUrl)
}

# --------------------------------------------------------------------------------------------
# 3. Import
# --------------------------------------------------------------------------------------------
if ($Phase -ne 'Listes') {
    if ($PSCmdlet.ShouldProcess($EnvironmentUrl, 'Importer ' + (Split-Path -Leaf $SolutionZip) + ' (lot ' + $Lot + ')')) {
        Write-Step ('Import de ' + (Split-Path -Leaf $SolutionZip))
        Invoke-Pac @('solution', 'import', '--path', $SolutionZip, '--settings-file', $SettingsFile, '--publish-changes')
    }
}

# --------------------------------------------------------------------------------------------
# 4. Activation par lot
# --------------------------------------------------------------------------------------------
$inLot = @($catalog | Where-Object { ($_.lot -le $Lot) -and $_.enabledByDefault -and ($NeverActivate -notcontains $_.code) })
$outLot = @($catalog | Where-Object { -not (($_.lot -le $Lot) -and $_.enabledByDefault -and ($NeverActivate -notcontains $_.code)) })
$socle = @($inLot | Where-Object { $ChildCodes -contains $_.code }) + @($inLot | Where-Object { ($_.code -like 'PA-00*') -and ($ChildCodes -notcontains $_.code) })
$listes = @($inLot | Where-Object { $_.code -notlike 'PA-00*' })

if ($SkipActivation) {
    Write-Warning 'Activation ignorée (-SkipActivation).'
}
else {
    $token = Get-DataverseToken $EnvironmentUrl
    if ($null -eq $token) {
        Write-Warning 'Module Az.Accounts absent ou non connecté : activez les flux à la main, dans cet ordre :'
        foreach ($w in $socle) { Write-Host ('   ' + $w.displayName) }
        if ($Lot -ge 2) { Write-Host '   (passer Fonction.Lot2Actif à Oui, exécuter PA-00D manuellement et vérifier les entrées REPRISE)' -ForegroundColor Yellow }
        foreach ($w in $listes) { Write-Host ('   ' + $w.displayName) }
    }
    else {
        if ($Phase -ne 'Listes') {
            foreach ($w in $outLot) { Set-FlowState $w $false $token }
            foreach ($w in $socle) { Set-FlowState $w $true $token }
        }
        $continuer = ($Phase -ne 'Socle')
        if ($continuer -and ($Phase -eq 'Tout') -and ($Lot -ge 2) -and ($listes.Count -gt 0) -and (-not $SansPause)) {
            Write-Host ''
            Write-Host 'Avant d''activer les flux des listes : passez le paramètre Fonction.Lot2Actif à Oui (liste Parametres),' -ForegroundColor Yellow
            Write-Host 'exécutez PA-00D manuellement (« Exécuter ») et vérifiez dans' -ForegroundColor Yellow
            Write-Host 'HistoriqueStatuts les entrées REPRISE de la reprise de l''existant (spec 6.1, point 3 ter ; H-57).' -ForegroundColor Yellow
            $reponse = Read-Host 'Saisir OUI pour activer les flux des listes, toute autre réponse pour arrêter'
            if ($reponse -ne 'OUI') {
                $continuer = $false
                Write-Warning 'Flux des listes non activés : relancer avec -Phase Listes après l''exécution de PA-00D.'
            }
        }
        if ($continuer) {
            foreach ($w in $listes) { Set-FlowState $w $true $token }
        }
        foreach ($email in $ShareWith) {
            $safe = $email.Replace("'", "''")
            $users = Invoke-Dataverse 'GET' ("systemusers?`$select=systemuserid&`$filter=internalemailaddress eq '" + $safe + "'") $null $token
            if ($users.value.Count -eq 0) {
                Write-Warning ('Utilisateur Dataverse introuvable : ' + $email)
                continue
            }
            $uid = $users.value[0].systemuserid
            foreach ($w in @($catalog | Where-Object { $_.childFlow })) {
                if ($PSCmdlet.ShouldProcess($w.displayName, 'Partager avec ' + $email)) {
                    Write-Step ('Partage de ' + $w.displayName + ' avec ' + $email)
                    $body = @{
                        Target          = @{ '@odata.type' = 'Microsoft.Dynamics.CRM.workflow'; workflowid = $w.workflowId }
                        PrincipalAccess = @{
                            Principal  = @{ '@odata.type' = 'Microsoft.Dynamics.CRM.systemuser'; systemuserid = $uid }
                            AccessMask = 'ReadAccess'
                        }
                    }
                    Invoke-Dataverse 'POST' 'GrantAccess' $body $token | Out-Null
                }
            }
        }
    }
}
foreach ($w in @($catalog | Where-Object { $NeverActivate -contains $_.code })) {
    Write-Host ('Jamais activé par ce script : ' + $w.displayName + ' (activation manuelle après validation, voir flows/README.md)') -ForegroundColor Yellow
}
Write-Step 'Terminé'
