<#
.SYNOPSIS
    Contrôle (et, avec -Corriger, accorde) les droits SharePoint du compte de service des flux.

.DESCRIPTION
    Spec § 8.1 et H-13 : toutes les connexions Power Automate utilisent le compte de service
    (ServiceAccountEmail de tenant.json), membre du groupe propriétaire G_PROP (Contrôle total sur le
    site et sur toutes les listes et bibliothèques via la matrice § 7.3).

    Contrôles effectués (lecture seule par défaut) :
      1. le compte existe dans le site (résolution du compte) ;
      2. il est membre direct de G_PROP (H-14) ;
      3. ses permissions effectives sur le site et sur chaque liste / bibliothèque déployée
         comprennent ManagePermissions, EditListItems, DeleteListItems et AddListItems
         (rupture d'héritage par élément et dossier, rétablissement de statut, journalisation) ;
      4. rappel des prérequis hors SharePoint, non vérifiables par PnP.PowerShell :
         licence Microsoft 365 avec Power Automate (connecteurs standard), droit « Envoyer en tant que »
         sur la boîte partagée R&D (Destinataires.BoiteRD), MFA / accès conditionnel compatibles avec
         des connexions de flux, mot de passe sans expiration ou procédure de renouvellement.

    -Corriger ajoute le compte à G_PROP (avec -WhatIf : simulation). Aucun autre droit n'est accordé :
    les droits découlent uniquement de l'appartenance à G_PROP.

.EXAMPLE
    pwsh ./provisioning/Grant-HNCSRDServiceAccount.ps1 -Lot 1
.EXAMPLE
    pwsh ./provisioning/Grant-HNCSRDServiceAccount.ps1 -Corriger
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ConfigPath,
    [string]$ModelPath,
    [ValidateRange(1, 5)][int]$Lot = 1,
    [switch]$Corriger,
    [string]$CertificatePath,
    [string]$Thumbprint,
    [securestring]$CertificatePassword
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

# Valeurs par défaut résolues ici ($PSScriptRoot est vide dans le bloc param sous Windows PowerShell 5.1).
if (-not $ConfigPath) { $ConfigPath = Join-Path $PSScriptRoot 'config/tenant.json' }
if (-not $ModelPath) { $ModelPath = Join-Path $PSScriptRoot 'model/model.generated.json' }

Import-Module (Join-Path $PSScriptRoot 'modules/HNCSRD.Provisioning.psd1') -Force -DisableNameChecking
Start-HNCSRDLog -Path (Join-Path $PSScriptRoot ("logs/compte-service-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss')))
Set-HNCSRDSimulation -Actif ([bool]$WhatIfPreference)

$permissionsRequises = @('ManagePermissions', 'AddListItems', 'EditListItems', 'DeleteListItems', 'ViewListItems')
$codeSortie = 0
try {
    Set-HNCSRDEtape -Nom 'Prerequis'
    [void](Assert-HNCSRDPrerequis)
    $modele = Get-HNCSRDModel -Path $ModelPath -Force
    $config = Get-HNCSRDConfig -Path $ConfigPath
    Connect-HNCSRD -Config $config -CertificatePath $CertificatePath -Thumbprint $Thumbprint -CertificatePassword $CertificatePassword | Out-Null
    $email = ([string]$config.ServiceAccountEmail).Trim()
    $nomProp = Get-HNCSRDGroupName -Code (Get-HNCSRDOwnerGroupCode -Model $modele) -Model $modele

    Set-HNCSRDEtape -Nom 'Compte'
    $utilisateur = $null
    try { $utilisateur = New-PnPUser -LoginName $email -ErrorAction Stop } catch { $utilisateur = $null }
    if (-not $utilisateur) { throw "Compte de service introuvable dans l'annuaire : $email" }
    Add-HNCSRDResultat -Statut Inchange -Cible $email -Message "Compte résolu : $($utilisateur.LoginName)"

    Set-HNCSRDEtape -Nom 'G_PROP'
    $membres = @(Get-PnPGroupMember -Group $nomProp)
    $estMembre = @($membres | Where-Object { $_.LoginName -eq $utilisateur.LoginName }).Count -gt 0
    if ($estMembre) { Add-HNCSRDResultat -Statut Inchange -Cible $nomProp -Message "$email est membre direct" }
    elseif ($Corriger) {
        if ($PSCmdlet.ShouldProcess($nomProp, "Ajouter $email")) {
            Add-PnPGroupMember -Group $nomProp -LoginName $utilisateur.LoginName -ErrorAction Stop
            Add-HNCSRDResultat -Statut Cree -Cible $nomProp -Message "$email ajouté"
            $estMembre = $true
        }
        else { Add-HNCSRDResultat -Statut Simule -Cible $nomProp -Message "$email serait ajouté" }
    }
    else { Add-HNCSRDResultat -Statut Erreur -Cible $nomProp -Message "$email n'est pas membre (relancer avec -Corriger ou Set-HNCSRDMembres.ps1)" }

    Set-HNCSRDEtape -Nom 'PermissionsEffectives'
    $cibles = New-Object System.Collections.Generic.List[object]
    $cibles.Add([pscustomobject]@{ Nom = 'Site'; Objet = (Get-PnPWeb) })
    foreach ($o in (Get-HNCSRDObjects -Lot $Lot -Model $modele)) {
        $l = Get-HNCSRDList -Name $o.name -Model $modele
        if ($l) { $cibles.Add([pscustomobject]@{ Nom = $o.name; Objet = $l }) }
        else { Add-HNCSRDResultat -Statut Avertissement -Cible $o.name -Message 'Liste absente' }
    }
    $type = [Microsoft.SharePoint.Client.PermissionKind]
    foreach ($c in $cibles) {
        $perm = $c.Objet.GetUserEffectivePermissions($utilisateur.LoginName)
        Invoke-PnPQuery
        $manquantes = @($permissionsRequises | Where-Object { -not $perm.Value.Has([Enum]::Parse($type, $_)) })
        if ($manquantes.Count -eq 0) { Add-HNCSRDResultat -Statut Inchange -Cible $c.Nom -Message 'Permissions requises présentes' }
        else {
            $statut = 'Erreur'
            if (-not $estMembre) { $statut = 'Avertissement' }
            Add-HNCSRDResultat -Statut $statut -Cible $c.Nom -Message ('Permissions manquantes : ' + ($manquantes -join ', '))
        }
    }

    Set-HNCSRDEtape -Nom 'HorsSharePoint'
    Write-HNCSRDLog -Message "À vérifier manuellement (H-13) : licence Power Automate du compte $email ; droit « Envoyer en tant que » sur $($config.Parametres.BoiteRD) ; politique MFA / accès conditionnel compatible avec les connexions de flux ; renouvellement du mot de passe." -Niveau Avertissement
}
catch { Add-HNCSRDResultat -Statut Erreur -Cible 'Grant-HNCSRDServiceAccount' -Message $_.Exception.Message }
finally {
    Set-HNCSRDEtape -Nom 'Resume'
    $resume = @(Get-HNCSRDResume)
    Write-HNCSRDLog -Message ("Résumé :`n" + (($resume | Format-Table -AutoSize | Out-String).TrimEnd()))
    $erreurs = 0; foreach ($r in $resume) { $erreurs += $r.Erreur }
    if ($erreurs -gt 0) { $codeSortie = 1 }
}
exit $codeSortie
