<#
.SYNOPSIS
    Exporte les listes du site de recette au format du jeu de test, pour recalculer les mesures Power BI
    (tests/e2e/reconciliation/reconcilier.py).
.DESCRIPTION
    - Une sortie JSON par liste (nom interne) : lookups convertis en IdHNCS de la cible, personnes en adresse e-mail,
      dates en ISO 8601 (heure locale de la machine : exécuter sur un poste réglé sur Paris, spec § 9.1 / H-48).
    - Comme Power BI (§ 9.2, P-04), AUCUNE colonne « perso » ou « confidentiel » n'est exportée.
    - Lecture seule. Compte conseillé : membre de HNCS-RD-DirectionRD ou HNCS-RD-Proprietaires.
.EXAMPLE
    $env:HNCSRD_E2E_CONFIG = './tests/e2e/config.json'
    ./tests/e2e/reconciliation/Export-HNCSRDDonnees.ps1 -Sortie ./TestResults/export -Persona IT
    python tests/e2e/reconciliation/reconcilier.py --source TestResults/export --comparer rapport.json
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Sortie,
    [string]$ConfigPath,
    [string]$Persona = 'IT',
    [string[]]$Listes = @('Poles', 'Referents', 'Etablissements', 'Offres', 'DomainesCibles', 'SujetsRD', 'RegistreModeles',
        'Candidatures', 'Entretiens', 'Alternants', 'Affectations', 'Livrables', 'ComptesRendus', 'ActionsIntegration',
        'Conventions', 'BilansAlternance', 'CommunicationsRD', 'Mobilisations', 'HistoriqueStatuts', 'GitlabSync')
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path -Parent $PSScriptRoot) 'HNCSRD.E2E.Common.ps1')

$cfg = Get-E2EConfig -Path $ConfigPath
$model = Read-E2EJson $cfg.ModelPath
$personas = Get-E2EPersonas $cfg.PersonasPath
$conn = Connect-E2EPersona -Config $cfg -Personas $personas -Cle $Persona
if (-not (Test-Path -LiteralPath $Sortie)) { New-Item -ItemType Directory -Path $Sortie | Out-Null }

$cartes = @{}
function Get-CarteIdHNCS([string]$Liste) {
    if (-not $cartes.ContainsKey($Liste)) {
        $c = @{}
        foreach ($it in @(Get-PnPListItem -List (Get-E2EListUrl $model $Liste) -PageSize 2000 -Fields 'ID', 'IdHNCS' -Connection $conn)) {
            $c[[int]$it.Id] = [string]$it['IdHNCS']
        }
        $cartes[$Liste] = $c
    }
    return $cartes[$Liste]
}

function ConvertTo-Export($Colonne, $Valeur) {
    if ($null -eq $Valeur) { return $null }
    switch ([string]$Colonne.type) {
        'Lookup' { return (Get-CarteIdHNCS ([string]$Colonne.lookup))[[int]$Valeur.LookupId] }
        'LookupMulti' { $o = @(); foreach ($v in @($Valeur)) { $o += (Get-CarteIdHNCS ([string]$Colonne.lookup))[[int]$v.LookupId] }; return , $o }
        'User' { return [string]$Valeur.Email }
        'UserMulti' { $o = @(); foreach ($v in @($Valeur)) { $o += [string]$v.Email }; return , $o }
        'Date' { return ([datetime]$Valeur).ToLocalTime().ToString('yyyy-MM-dd') }
        'DateTime' { return ([datetime]$Valeur).ToLocalTime().ToString('yyyy-MM-ddTHH:mm:ss') }
        'Boolean' { return [bool]$Valeur }
        'Number' { return [double]$Valeur }
        'MultiChoice' { return , ([string[]]@($Valeur)) }
        'URL' { return [string]$Valeur.Url }
        default { return [string]$Valeur }
    }
}

foreach ($nom in $Listes) {
    $obj = Get-E2EObjet $model $nom
    if ($null -eq $obj) { Write-Warning "Liste inconnue du modèle : $nom"; continue }
    if ($null -eq (Get-PnPList -Identity (Get-E2EListUrl $model $nom) -Connection $conn -ErrorAction SilentlyContinue)) {
        Write-Warning "$nom absente du site : ignorée"; continue
    }
    $cols = @($obj.columns | Where-Object { -not $_.perso -and -not $_.confidentiel })
    if (-not ($obj.titleColumn.perso -or $obj.titleColumn.confidentiel)) { $cols += $obj.titleColumn }
    $lignes = New-Object System.Collections.Generic.List[object]
    foreach ($it in @(Get-PnPListItem -List (Get-E2EListUrl $model $nom) -PageSize 2000 -Connection $conn)) {
        $o = [ordered]@{}
        foreach ($c in $cols) {
            $v = ConvertTo-Export $c $it[[string]$c.name]
            if ($null -ne $v -and [string]$v -ne '') { $o[[string]$c.name] = $v }
        }
        $lignes.Add($o)
    }
    $json = ConvertTo-Json -InputObject @($lignes.ToArray()) -Depth 5
    [System.IO.File]::WriteAllText((Join-Path $Sortie "$nom.json"), $json, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host ("{0,-20} {1,5} éléments" -f $nom, $lignes.Count)
}
