<#
.SYNOPSIS
    Déploie (ou redéploie) le socle SharePoint HNCS-RD à partir du modèle généré depuis la spec.

.DESCRIPTION
    Point d'entrée idempotent et rejouable de bout en bout. Toutes les listes, colonnes, vues, groupes,
    permissions, paramètres et transitions proviennent de provisioning/model/model.generated.json
    (généré par tools/spec_extract.py depuis spec.md) : rien n'est codé en dur.

    Étapes (exécutées dans cet ordre, filtrables avec -Etapes) et sections de la spec :
      Site                 § 2.2   site d'équipe STS#3 sans groupe M365, LCID 1036, fuseau Paris
      NiveauxAutorisation  § 7.2   niveau « HNCS - Contribution sans suppression »
      Groupes              § 7.1   8 groupes, propriétaire G_PROP, sans membres
      Listes               § 4, 5  listes / bibliothèques (URL = nom interne) + versioning
      Colonnes             § 2.3-2.4, 4, 5  Title et colonnes (hors lookups)
      Lookups              § 2.2   colonnes de recherche (2e passe, ShowField = IdHNCS)
      Validation           § 2.4   règles de validation de liste
      Vues                 specs/sharepoint-vues.md
      Permissions          § 7.2, 7.3  rupture d'héritage + matrice ; site : G_PROP FC, autres R
      Referentiels         specs/referentiels-initiaux.md  paramètres et seeds (jamais écrasés)
      Transitions          § 6     liste TransitionsStatuts
      Navigation           § 4.2   navigation rapide par domaine
      Teams                (optionnel) équipe Teams séparée, Teams.Creer = true

    Le déploiement est CUMULATIF : -Lot n déploie tous les objets de lot <= n, y compris les colonnes
    portant lot <= n.

.PARAMETER ConfigPath
    Configuration du tenant (contrat partagé : provisioning/config/tenant.sample.json).

.PARAMETER Lot
    Lot cible (0 à 5). 0 = cadrage : contrôle du modèle et de la configuration uniquement.

.PARAMETER Etapes
    Sous-ensemble des étapes à exécuter (toujours exécutées dans l'ordre canonique).

.PARAMETER ModelPath
    Modèle machine (par défaut provisioning/model/model.generated.json).

.PARAMETER CertificatePath
    Certificat .pfx de l'application Entra (mode automatisation) ; remplace CertificatePath de la config.

.PARAMETER Thumbprint
    Empreinte d'un certificat du magasin Windows ; remplace CertificateThumbprint de la config.

.PARAMETER CertificatePassword
    Mot de passe du .pfx (sinon variable d'environnement HNCSRD_CERT_PASSWORD).

.EXAMPLE
    pwsh ./provisioning/Deploy-HNCSRD.ps1 -Lot 1 -WhatIf

.EXAMPLE
    pwsh ./provisioning/Deploy-HNCSRD.ps1 -Lot 3 -Etapes Listes, Colonnes, Lookups, Validation, Vues, Permissions

.NOTES
    Exige PowerShell 7.4+ et PnP.PowerShell 2.12+ (ou 3.x). Code de sortie 1 si au moins une erreur.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ConfigPath,
    [ValidateRange(0, 5)][int]$Lot = 1,
    [ValidateSet('Site', 'NiveauxAutorisation', 'Groupes', 'Listes', 'Colonnes', 'Lookups', 'Validation', 'Vues', 'Permissions', 'Referentiels', 'Transitions', 'Navigation', 'Teams')]
    [string[]]$Etapes,
    [string]$ModelPath,
    [string]$CertificatePath,
    [string]$Thumbprint,
    [securestring]$CertificatePassword
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

# Valeurs par défaut résolues ici ($PSScriptRoot est vide dans le bloc param sous Windows PowerShell 5.1).
if (-not $ConfigPath) { $ConfigPath = Join-Path $PSScriptRoot 'config/tenant.json' }
if (-not $ModelPath) { $ModelPath = Join-Path $PSScriptRoot 'model/model.generated.json' }

$ordreCanonique = @('Site', 'NiveauxAutorisation', 'Groupes', 'Listes', 'Colonnes', 'Lookups', 'Validation', 'Vues', 'Permissions', 'Referentiels', 'Transitions', 'Navigation', 'Teams')
if (-not $Etapes -or $Etapes.Count -eq 0) { $Etapes = $ordreCanonique }
$aExecuter = @($ordreCanonique | Where-Object { $Etapes -contains $_ })

Import-Module (Join-Path $PSScriptRoot 'modules/HNCSRD.Provisioning.psd1') -Force -DisableNameChecking

$horodatage = Get-Date -Format 'yyyyMMdd-HHmmss'
$journal = Join-Path $PSScriptRoot ("logs/deploy-{0}.log" -f $horodatage)
Start-HNCSRDLog -Path $journal
$simulation = [bool]$WhatIfPreference
Set-HNCSRDSimulation -Actif $simulation

$codeSortie = 0
try {
    Set-HNCSRDEtape -Nom 'Prerequis'
    $versionPnP = Assert-HNCSRDPrerequis -VersionPnPMinimale '2.12.0'
    $modele = Get-HNCSRDModel -Path $ModelPath -Force
    $config = Get-HNCSRDConfig -Path $ConfigPath
    Write-HNCSRDLog -Message ("PowerShell {0} ; PnP.PowerShell {1} ; spec {2} ; lot {3} ; étapes : {4} ; simulation : {5}" -f $PSVersionTable.PSVersion, $versionPnP, $modele.specVersion, $Lot, ($aExecuter -join ', '), $simulation)
    Write-HNCSRDLog -Message "Journal : $journal" -Niveau Detail

    if ($Lot -lt 1) {
        Write-HNCSRDLog -Message 'Lot 0 (cadrage) : aucun objet SharePoint à déployer ; modèle et configuration contrôlés.' -Niveau Succes
        $aExecuter = @()
    }

    $objets = @(Get-HNCSRDObjects -Lot $Lot -Model $modele)
    Write-HNCSRDLog -Message ("{0} objet(s) de lot <= {1} : {2}" -f $objets.Count, $Lot, (($objets | ForEach-Object { $_.name }) -join ', ')) -Niveau Detail

    $siteDisponible = $true
    if ($aExecuter -contains 'Site') {
        Set-HNCSRDEtape -Nom 'Site'
        try {
            $admin = Connect-HNCSRD -Config $config -Administration -ReturnConnection -CertificatePath $CertificatePath -Thumbprint $Thumbprint -CertificatePassword $CertificatePassword
            $siteDisponible = Ensure-HNCSRDSite -Config $config -Model $modele -AdminConnection $admin
        }
        catch { Add-HNCSRDResultat -Statut Erreur -Cible 'Site' -Message $_.Exception.Message; $siteDisponible = $false }
    }

    $etapesSite = @($aExecuter | Where-Object { $_ -ne 'Site' })
    if ($etapesSite.Count -gt 0) {
        if (-not $siteDisponible) {
            Set-HNCSRDEtape -Nom 'Site'
            $statut = 'Erreur'; if ($simulation) { $statut = 'Avertissement' }
            Add-HNCSRDResultat -Statut $statut -Cible ([string]$config.SiteUrl) -Message ("Site indisponible : étapes non exécutées : " + ($etapesSite -join ', '))
            $etapesSite = @()
        }
        else {
            Set-HNCSRDEtape -Nom 'Connexion'
            Connect-HNCSRD -Config $config -CertificatePath $CertificatePath -Thumbprint $Thumbprint -CertificatePassword $CertificatePassword | Out-Null
        }
    }

    foreach ($etape in $etapesSite) {
        Set-HNCSRDEtape -Nom $etape
        Write-HNCSRDLog -Message "=== Étape $etape ==="
        try {
            switch ($etape) {
                'NiveauxAutorisation' { Ensure-HNCSRDPermissionLevels -Model $modele }
                'Groupes' { Ensure-HNCSRDGroups -Model $modele }
                'Listes' {
                    foreach ($o in $objets) {
                        try { [void](Ensure-HNCSRDList -Object $o -Model $modele) }
                        catch { Add-HNCSRDResultat -Statut Erreur -Cible $o.name -Message $_.Exception.Message }
                    }
                }
                { $_ -eq 'Colonnes' -or $_ -eq 'Lookups' } {
                    $passeLookups = ($etape -eq 'Lookups')
                    foreach ($o in $objets) {
                        $colonnes = @(Get-HNCSRDColumns -Object $o -Lot $Lot -Lookups $passeLookups)
                        $liste = Get-HNCSRDList -Name $o.name -Model $modele
                        if (-not $liste) {
                            $statut = 'Erreur'; if ($simulation) { $statut = 'Simule' }
                            Add-HNCSRDResultat -Statut $statut -Cible $o.name -Message ("Liste absente : {0} colonne(s) à créer après l'étape Listes" -f $colonnes.Count)
                            continue
                        }
                        try {
                            if (-not $passeLookups) { Ensure-HNCSRDTitleColumn -Object $o -List $liste }
                            $champs = Get-HNCSRDChamps -List $liste
                            foreach ($c in $colonnes) {
                                try { Ensure-HNCSRDColumn -Object $o -Column $c -List $liste -Champs $champs -Model $modele }
                                catch { Add-HNCSRDResultat -Statut Erreur -Cible "$($o.name).$($c.name)" -Message $_.Exception.Message }
                            }
                        }
                        catch { Add-HNCSRDResultat -Statut Erreur -Cible $o.name -Message $_.Exception.Message }
                    }
                }
                'Validation' {
                    foreach ($o in $objets) {
                        $liste = Get-HNCSRDList -Name $o.name -Model $modele
                        if (-not $liste) { if ($o.validation) { Add-HNCSRDResultat -Statut Avertissement -Cible $o.name -Message 'Liste absente : validation non appliquée' }; continue }
                        try { Set-HNCSRDListValidation -Object $o -List $liste }
                        catch { Add-HNCSRDResultat -Statut Erreur -Cible "$($o.name) (validation)" -Message $_.Exception.Message }
                    }
                }
                'Vues' {
                    foreach ($o in $objets) {
                        if (-not ($modele.views.PSObject.Properties.Name -contains $o.name)) { continue }
                        $liste = Get-HNCSRDList -Name $o.name -Model $modele
                        if (-not $liste) { Add-HNCSRDResultat -Statut Avertissement -Cible $o.name -Message 'Liste absente : vues non créées'; continue }
                        foreach ($v in @($modele.views.($o.name))) {
                            try { Ensure-HNCSRDView -Object $o -View $v -List $liste -Lot $Lot }
                            catch { Add-HNCSRDResultat -Statut Erreur -Cible "$($o.name) / $($v.name)" -Message $_.Exception.Message }
                        }
                    }
                }
                'Permissions' {
                    try { Set-HNCSRDSitePermissions -Model $modele }
                    catch { Add-HNCSRDResultat -Statut Erreur -Cible 'Site (permissions)' -Message $_.Exception.Message }
                    foreach ($o in $objets) {
                        $liste = Get-HNCSRDList -Name $o.name -Model $modele
                        if (-not $liste) { Add-HNCSRDResultat -Statut Avertissement -Cible $o.name -Message 'Liste absente : permissions non appliquées'; continue }
                        try { Set-HNCSRDListPermissions -Object $o -List $liste -Model $modele }
                        catch { Add-HNCSRDResultat -Statut Erreur -Cible "$($o.name) (permissions)" -Message $_.Exception.Message }
                    }
                }
                'Referentiels' {
                    try { Ensure-HNCSRDParameters -Model $modele -Config $config }
                    catch { Add-HNCSRDResultat -Statut Erreur -Cible 'Parametres' -Message $_.Exception.Message }
                    try { Ensure-HNCSRDSeeds -Model $modele -Config $config -Lot $Lot }
                    catch { Add-HNCSRDResultat -Statut Erreur -Cible 'Seeds' -Message $_.Exception.Message }
                }
                'Transitions' { Sync-HNCSRDTransitions -Model $modele }
                'Navigation' { Ensure-HNCSRDNavigation -Model $modele -Lot $Lot }
                'Teams' { Ensure-HNCSRDTeam -Config $config -Model $modele }
            }
        }
        catch { Add-HNCSRDResultat -Statut Erreur -Cible $etape -Message $_.Exception.Message }
    }
}
catch {
    Add-HNCSRDResultat -Statut Erreur -Cible $script:MyInvocation.MyCommand.Name -Message $_.Exception.Message
}
finally {
    Set-HNCSRDEtape -Nom 'Resume'
    $resume = @(Get-HNCSRDResume)
    $tableau = ($resume | Format-Table -AutoSize | Out-String).TrimEnd()
    Write-HNCSRDLog -Message ("Résumé par étape :`n" + $tableau)
    $erreurs = 0
    foreach ($r in $resume) { $erreurs += $r.Erreur }
    if ($erreurs -gt 0) {
        $codeSortie = 1
        Write-HNCSRDLog -Message "$erreurs erreur(s) : voir $journal" -Niveau Erreur
    }
    else { Write-HNCSRDLog -Message "Terminé sans erreur. Journal : $journal" -Niveau Succes }
}
exit $codeSortie
