<#
.SYNOPSIS
    Tests hors ligne des fonctions pures du module HNCSRD.Provisioning (sans PnP, sans tenant).

.DESCRIPTION
    XML de champ pour toutes les colonnes du modèle (nom interne, types, choix ordonnés, défauts, index,
    unicité, lookups), comparaison de schémas, formules de validation, versioning, matrice d'accès,
    navigation, lots cumulatifs, marqueurs de paramètres, seeds et transitions.
    Exécution autonome (code 1 en cas d'échec) ou sous Pester 3.4 / 5.
#>

. (Join-Path $PSScriptRoot 'HNCSRD.TestHelpers.ps1')

$sousPester = @(Get-PSCallStack | Where-Object { $_.Command -eq 'Invoke-Pester' -or ($_.ScriptName -and $_.ScriptName -match '[\\/]Pester[\\/]') }).Count -gt 0
if ($sousPester) {
    Describe 'HNCSRD.Provisioning (fonctions pures)' {
        BeforeAll { . (Join-Path $PSScriptRoot 'HNCSRD.TestHelpers.ps1') }
        It 'génère et contrôle colonnes, formules, permissions, navigation et référentiels depuis le modèle' {
            $r = Invoke-HNCSRDPureTests
            if ($r.Echecs.Count -gt 0) { throw ($r.Echecs -join "`n") }
        }
    }
}
else {
    $r = Invoke-HNCSRDPureTests
    if ($r.Echecs.Count -gt 0) {
        $r.Echecs | ForEach-Object { Write-Host "ÉCHEC $_" -ForegroundColor Red }
        Write-Host ("{0} échec(s) ({1} colonnes contrôlées)" -f $r.Echecs.Count, $r.Colonnes) -ForegroundColor Red
        exit 1
    }
    Write-Host ("OK : {0} colonnes et toutes les fonctions pures contrôlées (PowerShell {1})" -f $r.Colonnes, $PSVersionTable.PSVersion) -ForegroundColor Green
    exit 0
}
