<#
.SYNOPSIS
    Tests hors ligne de ConvertTo-HNCSRDCaml sur TOUTES les vues du modèle (sans PnP, sans tenant).

.DESCRIPTION
    Exécution autonome (code de sortie 1 en cas d'échec) :
        powershell -NoProfile -File provisioning/tests/ConvertTo-HNCSRDCaml.Tests.ps1
        pwsh -NoProfile -File provisioning/tests/ConvertTo-HNCSRDCaml.Tests.ps1
    Sous Pester (3.4 ou 5) : Invoke-Pester provisioning/tests (un bloc Describe / It, échec par throw).

    Contrôles : XML bien formé pour chaque vue ; une seule vue par défaut par liste ; colonnes, tri et
    regroupement conformes ; aucun <Not> ; chaque <And> a exactement deux enfants ; nombre de comparaisons
    conforme aux opérateurs (in = 1 nœud, notin = n <Neq>) ; [Moi] -> <UserID/> ; [Aujourd'hui±n] ->
    <Today OffsetDays="n"/> ; booléens 1/0 ; résultats exacts sur des vues de référence ; erreurs levées
    pour une colonne inconnue ou un opérateur inconnu.
#>

. (Join-Path $PSScriptRoot 'HNCSRD.TestHelpers.ps1')

$sousPester = @(Get-PSCallStack | Where-Object { $_.Command -eq 'Invoke-Pester' -or ($_.ScriptName -and $_.ScriptName -match '[\\/]Pester[\\/]') }).Count -gt 0
if ($sousPester) {
    Describe 'ConvertTo-HNCSRDCaml' {
        BeforeAll { . (Join-Path $PSScriptRoot 'HNCSRD.TestHelpers.ps1') }
        It 'génère un CAML valide et conforme pour toutes les vues du modèle' {
            $r = Invoke-HNCSRDCamlTests
            if ($r.Echecs.Count -gt 0) { throw ($r.Echecs -join "`n") }
        }
    }
}
else {
    $r = Invoke-HNCSRDCamlTests
    if ($r.Echecs.Count -gt 0) {
        $r.Echecs | ForEach-Object { Write-Host "ÉCHEC $_" -ForegroundColor Red }
        Write-Host ("{0} échec(s) sur {1} vue(s)" -f $r.Echecs.Count, $r.Vues) -ForegroundColor Red
        exit 1
    }
    Write-Host ("OK : {0} vue(s) converties en CAML valide (PowerShell {1})" -f $r.Vues, $PSVersionTable.PSVersion) -ForegroundColor Green
    exit 0
}
