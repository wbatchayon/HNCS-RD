<#
.SYNOPSIS
    Publie le modèle sémantique et le rapport Power BI HNCS-RD (PBIP) via l'API REST Fabric.

.DESCRIPTION
    Idempotent : crée l'espace de travail s'il n'existe pas, crée le modèle sémantique et le rapport
    s'ils n'existent pas, sinon met à jour leur définition (updateDefinition). Le paramètre M SiteUrl
    est injecté dans expressions.tmdl au moment de l'envoi (le fichier local n'est pas modifié).
    Le rapport est relié au modèle publié (definition.pbir réécrit en byConnection pour l'API).
    Déclenche ensuite une actualisation et, sur demande, configure l'actualisation planifiée
    quotidienne de 07:45 (heure de Paris).

    Étapes qui restent MANUELLES dans le service Power BI (spec § 9.1, H-16) :
      1. Identifiants de la source : Paramètres du modèle > Informations d'identification de la source
         de données > SharePoint (Web) > Modifier > OAuth2, compte de service, confidentialité
         « Organisationnel ». Sans cette étape l'actualisation échoue.
      2. Actualisation planifiée quotidienne 07:45 (Romance Standard Time) si -ConfigurerPlanification
         n'a pas pu l'appliquer (elle exige des identifiants valides).
      3. Sécurité : affecter les groupes Entra / personnes aux rôles Direction, PilotageRD,
         Administration, RelationEcoles et Referent (Modèle > Sécurité). Ne jamais mettre une même personne dans
         Direction (OLS) et dans un rôle à filtre RLS (Administration, RelationEcoles, Referent).
      4. Accès à l'espace de travail : membres en « Lecteur » pour les publics du rapport ;
         aucun alternant (H-19).

    Alternative manuelle : ouvrir powerbi/HNCS-RD.pbip dans Power BI Desktop, renseigner le paramètre
    SiteUrl (Transformer les données > Modifier les paramètres), actualiser, puis Fichier > Publier
    vers l'espace « HNCS-R&D Pilotage » ; effectuer ensuite les étapes manuelles ci-dessus.

    Compatible Windows PowerShell 5.1 et PowerShell 7.

.PARAMETER SiteUrl
    URL du site SharePoint (ex. https://contoso.sharepoint.com/sites/HNCS-RD).

.PARAMETER WorkspaceName
    Nom de l'espace de travail (défaut : « HNCS-R&D Pilotage », H-16).

.PARAMETER CapacityId
    Capacité Fabric / Premium à associer à l'espace créé (facultatif).

.PARAMETER Auth
    Az (Az.Accounts, défaut), PowerBIMgmt (MicrosoftPowerBIMgmt) ou Token (jeton fourni par -AccessToken).

.PARAMETER PreparationSeule
    Construit les définitions (parts base64) dans -DossierSortie sans appeler aucune API.

.EXAMPLE
    .\Publish-HNCSRDPowerBI.ps1 -SiteUrl https://contoso.sharepoint.com/sites/HNCS-RD -ConfigurerPlanification

.EXAMPLE
    .\Publish-HNCSRDPowerBI.ps1 -SiteUrl https://contoso.sharepoint.com/sites/HNCS-RD -PreparationSeule -DossierSortie .\out
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https://[^/]+\.sharepoint\.com/sites/[^/]+/?$')]
    [string] $SiteUrl,

    [string] $WorkspaceName = 'HNCS-R&D Pilotage',

    [string] $CapacityId,

    [string] $ModelName = 'HNCS-RD',

    [string] $ReportName = 'HNCS-RD',

    [string] $ProjectRoot,

    [ValidateSet('Az', 'PowerBIMgmt', 'Token')]
    [string] $Auth = 'Az',

    [string] $AccessToken,

    [switch] $SkipRefresh,

    [switch] $ConfigurerPlanification,

    [switch] $PreparationSeule,

    [string] $DossierSortie
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$FabricApi = 'https://api.fabric.microsoft.com/v1'
$PowerBIApi = 'https://api.powerbi.com/v1.0/myorg'
$PowerBIResource = 'https://analysis.windows.net/powerbi/api'
$Utf8SansBom = New-Object System.Text.UTF8Encoding($false)

if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
$ModelFolder = Join-Path $ProjectRoot 'HNCS-RD.SemanticModel'
$ReportFolder = Join-Path $ProjectRoot 'HNCS-RD.Report'
$SiteUrl = $SiteUrl.TrimEnd('/')

# --------------------------------------------------------------------------- authentification

function Get-HncsAccessToken {
    if ($Auth -eq 'Token') {
        if (-not $AccessToken) { throw 'Le mode -Auth Token exige -AccessToken.' }
        return ($AccessToken -replace '^Bearer\s+', '')
    }
    if ($Auth -eq 'PowerBIMgmt') {
        if (-not (Get-Module -ListAvailable -Name MicrosoftPowerBIMgmt.Profile)) {
            throw 'Module MicrosoftPowerBIMgmt absent : Install-Module MicrosoftPowerBIMgmt -Scope CurrentUser'
        }
        Import-Module MicrosoftPowerBIMgmt.Profile
        try {
            $jeton = Get-PowerBIAccessToken -AsString
        }
        catch {
            Connect-PowerBIServiceAccount | Out-Null
            $jeton = Get-PowerBIAccessToken -AsString
        }
        return ($jeton -replace '^Bearer\s+', '')
    }
    if (-not (Get-Module -ListAvailable -Name Az.Accounts)) {
        throw 'Module Az.Accounts absent : Install-Module Az.Accounts -Scope CurrentUser (ou utiliser -Auth PowerBIMgmt).'
    }
    Import-Module Az.Accounts
    if (-not (Get-AzContext)) {
        Connect-AzAccount | Out-Null
    }
    $resultat = Get-AzAccessToken -ResourceUrl $PowerBIResource
    $valeur = $resultat.Token
    if ($valeur -is [System.Security.SecureString]) {
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($valeur)
        try { $valeur = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    }
    return $valeur
}

# --------------------------------------------------------------------------- appels REST

function Read-ErrorBody {
    param($Exception)
    try {
        $reponse = $Exception.Response
        if ($null -eq $reponse) { return $Exception.Message }
        $flux = $reponse.GetResponseStream()
        $lecteur = New-Object System.IO.StreamReader($flux)
        return $lecteur.ReadToEnd()
    }
    catch {
        return $Exception.Message
    }
}

function Invoke-HncsApi {
    <# Appel REST avec gestion des opérations longues (202 + Location) et des limitations (429). #>
    param(
        [Parameter(Mandatory = $true)] [string] $Method,
        [Parameter(Mandatory = $true)] [string] $Uri,
        $Body,
        [switch] $ReturnOperationResult
    )
    $entetes = @{ Authorization = "Bearer $script:Jeton" }
    $parametres = @{ Method = $Method; Uri = $Uri; Headers = $entetes; UseBasicParsing = $true }
    if ($null -ne $Body) {
        $json = $Body | ConvertTo-Json -Depth 30 -Compress
        $parametres['Body'] = $Utf8SansBom.GetBytes($json)
        $parametres['ContentType'] = 'application/json; charset=utf-8'
    }
    for ($tentative = 1; $tentative -le 5; $tentative++) {
        try {
            $reponse = Invoke-WebRequest @parametres
            break
        }
        catch {
            $code = 0
            if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
            if ($code -eq 429 -and $tentative -lt 5) {
                $attente = 30
                $retry = $_.Exception.Response.Headers['Retry-After']
                if ($retry) { $attente = [int]$retry }
                Write-Warning "Limitation de l'API (429) : nouvelle tentative dans $attente s."
                Start-Sleep -Seconds $attente
                continue
            }
            throw "Échec $Method $Uri (HTTP $code) : $(Read-ErrorBody $_.Exception)"
        }
    }
    if ($reponse.StatusCode -eq 202 -and $reponse.Headers['Location']) {
        $operation = [string]$reponse.Headers['Location']
        $etat = $null
        do {
            $attente = 5
            if ($reponse.Headers['Retry-After']) { $attente = [int]([string]$reponse.Headers['Retry-After']) }
            Start-Sleep -Seconds $attente
            $reponse = Invoke-WebRequest -Method Get -Uri $operation -Headers $entetes -UseBasicParsing
            $etat = ($reponse.Content | ConvertFrom-Json)
            Write-Verbose "Opération $operation : $($etat.status)"
        } while ($etat.status -in @('NotStarted', 'Running', 'Undefined'))
        if ($etat.status -ne 'Succeeded') {
            throw "Opération longue en échec ($($etat.status)) : $($reponse.Content)"
        }
        if ($ReturnOperationResult) {
            $resultat = Invoke-WebRequest -Method Get -Uri ($operation.TrimEnd('/') + '/result') -Headers $entetes -UseBasicParsing
            if ($resultat.Content) { return ($resultat.Content | ConvertFrom-Json) }
        }
        return $null
    }
    if ($reponse.Content) {
        $texte = $reponse.Content
        if ($texte -is [byte[]]) { $texte = [System.Text.Encoding]::UTF8.GetString($texte) }
        if ($texte.Trim()) { return ($texte | ConvertFrom-Json) }
    }
    return $null
}

function Get-HncsAll {
    <# Liste paginée (continuationUri) d'une collection Fabric. #>
    param([string] $Uri)
    $elements = @()
    $suivant = $Uri
    while ($suivant) {
        $page = Invoke-HncsApi -Method Get -Uri $suivant
        if ($page -and $page.PSObject.Properties['value'] -and $page.value) { $elements += @($page.value) }
        $suivant = $null
        if ($page.PSObject.Properties['continuationUri'] -and $page.continuationUri) { $suivant = $page.continuationUri }
    }
    return $elements
}

# --------------------------------------------------------------------------- définitions (parts)

function ConvertTo-InlinePart {
    param([string] $Path, [byte[]] $Bytes)
    return [ordered]@{ path = $Path; payload = [Convert]::ToBase64String($Bytes); payloadType = 'InlineBase64' }
}

function Get-DefinitionParts {
    <# Parts d'un dossier d'élément PBIP (hors .platform et caches .pbi). $Overrides : chemin relatif -> contenu texte. #>
    param([string] $Folder, [hashtable] $Overrides)
    $racine = (Resolve-Path $Folder).Path.TrimEnd('\', '/')
    $parts = @()
    $fichiers = Get-ChildItem -Path $racine -Recurse -File -Force | Sort-Object FullName
    foreach ($fichier in $fichiers) {
        $relatif = $fichier.FullName.Substring($racine.Length + 1).Replace('\', '/')
        if ($relatif -eq '.platform' -or $relatif -like '.pbi/*' -or $relatif -like '*/.pbi/*') { continue }
        if ($Overrides -and $Overrides.ContainsKey($relatif)) {
            $octets = $Utf8SansBom.GetBytes([string]$Overrides[$relatif])
        }
        else {
            $octets = [System.IO.File]::ReadAllBytes($fichier.FullName)
        }
        $parts += (ConvertTo-InlinePart -Path $relatif -Bytes $octets)
    }
    return ,$parts
}

function Get-ModelOverrides {
    $chemin = Join-Path $ModelFolder 'definition\expressions.tmdl'
    $texte = [System.IO.File]::ReadAllText($chemin, [System.Text.Encoding]::UTF8)
    $motif = '(?m)^(expression SiteUrl = )"[^"]*"'
    if ($texte -notmatch $motif) { throw "Paramètre SiteUrl introuvable dans $chemin" }
    $texte = [regex]::Replace($texte, $motif, ('$1"' + $SiteUrl + '"'))
    return @{ 'definition/expressions.tmdl' = $texte }
}

function Get-ReportOverrides {
    param([string] $ModelId, [string] $WorkspaceDisplayName)
    $pbir = [ordered]@{
        '$schema'        = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json'
        version          = '4.0'
        datasetReference = [ordered]@{
            byConnection = [ordered]@{
                connectionString = "Data Source=powerbi://api.powerbi.com/v1.0/myorg/$WorkspaceDisplayName;Initial Catalog=$ModelName;Integrated Security=ClaimsToken;semanticmodelid=$ModelId"
            }
        }
    }
    return @{ 'definition.pbir' = ($pbir | ConvertTo-Json -Depth 10) }
}

function Save-Parts {
    param([string] $Name, [string] $Kind, $Parts)
    $dossier = Join-Path $DossierSortie "$Name.$Kind"
    New-Item -ItemType Directory -Force -Path $dossier | Out-Null
    $corps = [ordered]@{ displayName = $Name; definition = [ordered]@{ parts = $Parts } }
    $fichier = Join-Path $dossier 'definition.json'
    [System.IO.File]::WriteAllText($fichier, ($corps | ConvertTo-Json -Depth 30), $Utf8SansBom)
    Write-Host "  $($Parts.Count) parts écrites dans $fichier"
}

# --------------------------------------------------------------------------- publication

function Get-OrCreateWorkspace {
    $existants = Get-HncsAll -Uri "$FabricApi/workspaces"
    $ws = $existants | Where-Object { $_.displayName -eq $WorkspaceName } | Select-Object -First 1
    if ($ws) {
        Write-Host "Espace de travail existant : $WorkspaceName ($($ws.id))"
        return $ws
    }
    if (-not $PSCmdlet.ShouldProcess($WorkspaceName, "Créer l'espace de travail")) { return $null }
    $corps = [ordered]@{ displayName = $WorkspaceName; description = 'Pilotage du système de suivi R&D HNCS (spec § 9, H-16)' }
    if ($CapacityId) { $corps['capacityId'] = $CapacityId }
    $ws = Invoke-HncsApi -Method Post -Uri "$FabricApi/workspaces" -Body $corps
    Write-Host "Espace de travail créé : $WorkspaceName ($($ws.id))"
    return $ws
}

function Publish-Item {
    <# Crée l'élément s'il n'existe pas, sinon met à jour sa définition. Renvoie son identifiant. #>
    param([string] $WorkspaceId, [string] $Collection, [string] $Name, $Parts)
    $existants = Get-HncsAll -Uri "$FabricApi/workspaces/$WorkspaceId/$Collection"
    $item = $existants | Where-Object { $_.displayName -eq $Name } | Select-Object -First 1
    if ($item) {
        if ($PSCmdlet.ShouldProcess("$Collection/$Name", 'Mettre à jour la définition')) {
            Invoke-HncsApi -Method Post -Uri "$FabricApi/workspaces/$WorkspaceId/$Collection/$($item.id)/updateDefinition" `
                -Body ([ordered]@{ definition = [ordered]@{ parts = $Parts } }) | Out-Null
            Write-Host "Définition mise à jour : $Collection/$Name ($($item.id))"
        }
        return $item.id
    }
    if (-not $PSCmdlet.ShouldProcess("$Collection/$Name", 'Créer')) { return $null }
    $corps = [ordered]@{ displayName = $Name; description = 'HNCS-RD, généré depuis powerbi/ (spec § 9)'; definition = [ordered]@{ parts = $Parts } }
    $cree = Invoke-HncsApi -Method Post -Uri "$FabricApi/workspaces/$WorkspaceId/$Collection" -Body $corps -ReturnOperationResult
    if (-not $cree) {
        $cree = Get-HncsAll -Uri "$FabricApi/workspaces/$WorkspaceId/$Collection" | Where-Object { $_.displayName -eq $Name } | Select-Object -First 1
    }
    Write-Host "Élément créé : $Collection/$Name ($($cree.id))"
    return $cree.id
}

function Set-RefreshSchedule {
    param([string] $WorkspaceId, [string] $ModelId)
    $corps = [ordered]@{
        value = [ordered]@{
            enabled         = $true
            days            = @('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
            times           = @('07:45')
            localTimeZoneId = 'Romance Standard Time'
            notifyOption    = 'MailOnFailure'
        }
    }
    try {
        Invoke-HncsApi -Method Patch -Uri "$PowerBIApi/groups/$WorkspaceId/datasets/$ModelId/refreshSchedule" -Body $corps | Out-Null
        Write-Host 'Actualisation planifiée : tous les jours à 07:45 (heure de Paris).'
    }
    catch {
        Write-Warning "Planification non appliquée (identifiants de la source probablement non renseignés) : $($_.Exception.Message)"
        Write-Warning 'À faire dans le service : Paramètres du modèle > Actualisation planifiée > quotidienne 07:45.'
    }
}

function Start-ModelRefresh {
    param([string] $WorkspaceId, [string] $ModelId)
    try {
        Invoke-HncsApi -Method Post -Uri "$PowerBIApi/groups/$WorkspaceId/datasets/$ModelId/refreshes" -Body ([ordered]@{ notifyOption = 'MailOnFailure' }) | Out-Null
        Write-Host 'Actualisation demandée (suivi : historique d''actualisation du modèle dans le service).'
    }
    catch {
        Write-Warning "Actualisation non déclenchée : $($_.Exception.Message)"
        Write-Warning 'Renseigner les identifiants OAuth2 de la source SharePoint puis relancer avec ce script ou depuis le service.'
    }
}

# --------------------------------------------------------------------------- principal

foreach ($dossier in @($ModelFolder, $ReportFolder)) {
    if (-not (Test-Path $dossier)) { throw "Dossier introuvable : $dossier" }
}

$partsModele = Get-DefinitionParts -Folder $ModelFolder -Overrides (Get-ModelOverrides)

if ($PreparationSeule) {
    if (-not $DossierSortie) { throw '-PreparationSeule exige -DossierSortie.' }
    Write-Host "Préparation hors ligne (aucun appel d'API), SiteUrl = $SiteUrl"
    Save-Parts -Name $ModelName -Kind 'SemanticModel' -Parts $partsModele
    $partsRapport = Get-DefinitionParts -Folder $ReportFolder -Overrides (Get-ReportOverrides -ModelId '00000000-0000-0000-0000-000000000000' -WorkspaceDisplayName $WorkspaceName)
    Save-Parts -Name $ReportName -Kind 'Report' -Parts $partsRapport
    return
}

$script:Jeton = Get-HncsAccessToken
$ws = Get-OrCreateWorkspace
if (-not $ws) { return }

$modelId = Publish-Item -WorkspaceId $ws.id -Collection 'semanticModels' -Name $ModelName -Parts $partsModele
if (-not $modelId) { return }

$partsRapport = Get-DefinitionParts -Folder $ReportFolder -Overrides (Get-ReportOverrides -ModelId $modelId -WorkspaceDisplayName $WorkspaceName)
$reportId = Publish-Item -WorkspaceId $ws.id -Collection 'reports' -Name $ReportName -Parts $partsRapport

if ($ConfigurerPlanification) {
    Set-RefreshSchedule -WorkspaceId $ws.id -ModelId $modelId
}
if (-not $SkipRefresh) {
    Start-ModelRefresh -WorkspaceId $ws.id -ModelId $modelId
}

Write-Host ''
Write-Host 'Publication terminée. Étapes manuelles restantes (README.md § Publication) :'
Write-Host '  1. Identifiants OAuth2 de la source SharePoint (compte de service, confidentialité Organisationnel).'
Write-Host '  2. Actualisation planifiée quotidienne 07:45 si elle n''a pas été appliquée ci-dessus.'
Write-Host '  3. Affectation des membres aux rôles RLS / OLS (Direction, PilotageRD, Administration, RelationEcoles, Referent), une personne dans un seul rôle, H-16.'
Write-Host "  4. Accès à l'espace « $WorkspaceName » en lecture pour les publics du rapport (aucun alternant, H-19)."
Write-Host "Modèle : $modelId, Rapport : $reportId"
