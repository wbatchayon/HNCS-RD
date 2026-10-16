#Requires -Version 5.1
<#
.SYNOPSIS
    Importe la solution Power Platform HNCSRDSuivi (flux Power Automate HNCS-RD), active les flux dans l'ordre
    et partage les flux enfants.

.DESCRIPTION
    1. (option -Build) construit flows/dist/HNCSRDSuivi_<specVersion>.zip avec flows/build/build_solution.py ;
    2. sélectionne ou crée le profil d'authentification pac (pac auth) ;
    3. importe la solution non gérée avec le fichier de paramètres de déploiement
       (pac solution import --settings-file : variables d'environnement et références de connexion) ;
    4. active les flux via l'API Web Dataverse : PA-00A, PA-00B, PA-00C d'abord, puis les autres flux activés
       par défaut ; PA-13 reste désactivé (spec § 8.4, H-10) ;
    5. (option -ShareWith) partage les flux enfants (accès en lecture) avec les comptes indiqués.

    L'activation et le partage utilisent un jeton d'accès obtenu par Get-AzAccessToken (module Az.Accounts) ;
    sans ce module, l'import est réalisé et l'activation doit être faite à la main (ordre indiqué en sortie).

.PARAMETER EnvironmentUrl
    URL de l'environnement Dataverse (ex. https://contoso.crm4.dynamics.com).

.PARAMETER SettingsFile
    Fichier de paramètres de déploiement (copie renseignée de deploymentSettings.sample.json).

.EXAMPLE
    .\Import-HNCSRDFlows.ps1 -EnvironmentUrl https://contoso.crm4.dynamics.com -SettingsFile .\deploymentSettings.json -Build
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$EnvironmentUrl,

    [string]$SettingsFile = (Join-Path $PSScriptRoot 'deploymentSettings.json'),

    [string]$SolutionZip,

    [switch]$Build,

    [string]$AuthProfile,

    [switch]$SkipActivation,

    [string[]]$ShareWith = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$FlowsRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $FlowsRoot
$ChildCodes = @('PA-00A', 'PA-00B', 'PA-00C')

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

# --------------------------------------------------------------------------------------------
# 0. Prérequis
# --------------------------------------------------------------------------------------------
if (-not (Get-Command -Name pac -ErrorAction SilentlyContinue)) {
    throw 'Power Platform CLI (pac) introuvable : installez-la (https://aka.ms/PowerPlatformCLI).'
}
if (-not (Test-Path -LiteralPath $SettingsFile)) {
    throw ('Fichier de paramètres introuvable : ' + $SettingsFile + ' (copier deploymentSettings.sample.json et le renseigner).')
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
# 1. Construction
# --------------------------------------------------------------------------------------------
if ($Build) {
    Write-Step 'Construction de la solution'
    $python = Get-Command -Name python -ErrorAction SilentlyContinue
    if ($null -eq $python) { throw 'python introuvable.' }
    & $python.Source (Join-Path $FlowsRoot 'build\build_solution.py')
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
if ($PSCmdlet.ShouldProcess($EnvironmentUrl, 'Importer ' + (Split-Path -Leaf $SolutionZip))) {
    Write-Step ('Import de ' + (Split-Path -Leaf $SolutionZip))
    Invoke-Pac @('solution', 'import', '--path', $SolutionZip, '--settings-file', $SettingsFile, '--publish-changes', '--async')
}

# --------------------------------------------------------------------------------------------
# 4. Activation (enfants d'abord, PA-13 désactivé)
# --------------------------------------------------------------------------------------------
$children = @($catalog | Where-Object { $_.childFlow })
$others = @($catalog | Where-Object { (-not $_.childFlow) -and $_.enabledByDefault })
$disabled = @($catalog | Where-Object { -not $_.enabledByDefault })
$ordered = @($children) + @($others)

if ($SkipActivation) {
    Write-Warning 'Activation ignorée (-SkipActivation).'
}
else {
    $token = Get-DataverseToken $EnvironmentUrl
    if ($null -eq $token) {
        Write-Warning 'Module Az.Accounts absent ou non connecté : activez les flux à la main, dans cet ordre :'
        foreach ($w in $ordered) { Write-Host ('   ' + $w.displayName) }
    }
    else {
        foreach ($w in $ordered) {
            if ($PSCmdlet.ShouldProcess($w.displayName, 'Activer')) {
                Write-Step ('Activation : ' + $w.displayName)
                Invoke-Dataverse 'PATCH' ('workflows(' + $w.workflowId + ')') @{ statecode = 1; statuscode = 2 } $token | Out-Null
            }
        }
        foreach ($email in $ShareWith) {
            $safe = $email.Replace("'", "''")
            $users = Invoke-Dataverse 'GET' ("systemusers?`$select=systemuserid&`$filter=internalemailaddress eq '" + $safe + "'") $null $token
            if ($users.value.Count -eq 0) {
                Write-Warning ('Utilisateur Dataverse introuvable : ' + $email)
                continue
            }
            $uid = $users.value[0].systemuserid
            foreach ($w in $children) {
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
foreach ($w in $disabled) {
    Write-Host ('Laissé désactivé : ' + $w.displayName + ' (activation après validation, voir flows/README.md)') -ForegroundColor Yellow
}
Write-Step 'Terminé'
