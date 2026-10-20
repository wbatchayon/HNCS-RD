<#
.SYNOPSIS
    Ajoute directement les comptes dans les groupes SharePoint HNCS-RD depuis membres.json (H-14).

.DESCRIPTION
    Les membres sont ajoutés DIRECTEMENT dans les groupes SharePoint (pas de groupe Entra imbriqué),
    pour que PA-00A puisse vérifier les rôles par l'API REST standard (spec § 6.2, H-14). Un groupe Entra
    ou un groupe SharePoint présent dans le fichier est refusé (avertissement).

    Le compte de service (ServiceAccountEmail de tenant.json) est toujours ajouté au groupe propriétaire
    (G_PROP, H-13), même s'il est absent du fichier.

    Mode -Synchroniser : retire des groupes les membres absents du fichier (y compris des groupes Entra
    imbriqués). À utiliser avec -WhatIf pour contrôler la liste des retraits avant de l'appliquer.

    Fichier (contrat partagé, voir config/membres.sample.json) :
      { "G_PROP": ["upn", ...], "G_DRD": [...], ..., "G_ECO": [...] }
    Les clés sont les codes de groupe du modèle ; une clé absente laisse le groupe inchangé.

.PARAMETER MembresPath
    Fichier des membres (défaut provisioning/config/membres.json).

.PARAMETER Synchroniser
    Retire les membres absents du fichier.

.EXAMPLE
    pwsh ./provisioning/Set-HNCSRDMembres.ps1 -Synchroniser -WhatIf
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ConfigPath,
    [string]$MembresPath,
    [string]$ModelPath,
    [switch]$Synchroniser,
    [string]$CertificatePath,
    [string]$Thumbprint,
    [securestring]$CertificatePassword
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

# Valeurs par défaut résolues ici ($PSScriptRoot est vide dans le bloc param sous Windows PowerShell 5.1).
if (-not $ConfigPath) { $ConfigPath = Join-Path $PSScriptRoot 'config/tenant.json' }
if (-not $MembresPath) { $MembresPath = Join-Path $PSScriptRoot 'config/membres.json' }
if (-not $ModelPath) { $ModelPath = Join-Path $PSScriptRoot 'model/model.generated.json' }

Import-Module (Join-Path $PSScriptRoot 'modules/HNCSRD.Provisioning.psd1') -Force -DisableNameChecking
Start-HNCSRDLog -Path (Join-Path $PSScriptRoot ("logs/membres-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss')))
Set-HNCSRDSimulation -Actif ([bool]$WhatIfPreference)

function ConvertTo-UpnNormalise {
    param([string]$Valeur)
    $v = ([string]$Valeur).Trim()
    if ($v -match '\|') { $v = $v.Substring($v.LastIndexOf('|') + 1) }
    return $v.ToLowerInvariant()
}

$codeSortie = 0
try {
    Set-HNCSRDEtape -Nom 'Prerequis'
    [void](Assert-HNCSRDPrerequis)
    $modele = Get-HNCSRDModel -Path $ModelPath -Force
    $config = Get-HNCSRDConfig -Path $ConfigPath
    if (-not (Test-Path -LiteralPath $MembresPath)) { throw "Fichier des membres introuvable : $MembresPath (copier config/membres.sample.json)." }
    $membres = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $MembresPath).ProviderPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
    $codes = @($modele.groups | ForEach-Object { [string]$_.code })
    foreach ($cle in $membres.PSObject.Properties.Name) {
        if ($codes -notcontains $cle) { Add-HNCSRDResultat -Statut Avertissement -Cible $cle -Message 'Clé inconnue du modèle (ignorée)' }
    }
    Connect-HNCSRD -Config $config -CertificatePath $CertificatePath -Thumbprint $Thumbprint -CertificatePassword $CertificatePassword | Out-Null
    $codeProp = Get-HNCSRDOwnerGroupCode -Model $modele
    $service = ConvertTo-UpnNormalise ([string]$config.ServiceAccountEmail)

    foreach ($g in $modele.groups) {
        $code = [string]$g.code; $nom = [string]$g.name
        Set-HNCSRDEtape -Nom $code
        if (-not ($membres.PSObject.Properties.Name -contains $code) -and $code -ne $codeProp) {
            Write-HNCSRDLog -Message "$nom : absent du fichier, inchangé" -Niveau Detail
            continue
        }
        $voulus = @()
        if ($membres.PSObject.Properties.Name -contains $code) { $voulus = @($membres.$code | ForEach-Object { ConvertTo-UpnNormalise $_ } | Where-Object { $_ }) }
        if ($code -eq $codeProp -and $voulus -notcontains $service) { $voulus += $service }
        $voulus = @($voulus | Select-Object -Unique)
        try { [void](Get-PnPGroup -Identity $nom -ErrorAction Stop) }
        catch { Add-HNCSRDResultat -Statut Erreur -Cible $nom -Message 'Groupe absent (exécuter Deploy-HNCSRD.ps1 -Etapes Groupes)'; continue }
        $actuels = @(Get-PnPGroupMember -Group $nom)
        $actuelsUpn = @{}
        foreach ($m in $actuels) {
            $cle = ConvertTo-UpnNormalise $m.LoginName
            if ($m.Email) { $cle = ([string]$m.Email).ToLowerInvariant() }
            $actuelsUpn[$cle] = $m
            if ([string]$m.PrincipalType -ne 'User') {
                Add-HNCSRDResultat -Statut Avertissement -Cible "$nom / $($m.Title)" -Message "Membre de type $($m.PrincipalType) : contraire à H-14 (membres directs uniquement)"
            }
        }
        foreach ($upn in $voulus) {
            $present = $actuelsUpn.ContainsKey($upn) -or @($actuels | Where-Object { (ConvertTo-UpnNormalise $_.LoginName) -eq $upn }).Count -gt 0
            if ($present) { Add-HNCSRDResultat -Statut Inchange -Cible "$nom / $upn"; continue }
            if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible "$nom / $upn" -Message 'Ajout'; continue }
            try {
                $u = New-PnPUser -LoginName $upn -ErrorAction Stop
                if ([string]$u.PrincipalType -ne 'User') {
                    Add-HNCSRDResultat -Statut Avertissement -Cible "$nom / $upn" -Message "Principal de type $($u.PrincipalType) refusé (H-14 : comptes utilisateurs uniquement)"
                    continue
                }
                Add-PnPGroupMember -Group $nom -LoginName $u.LoginName -ErrorAction Stop
                Add-HNCSRDResultat -Statut Cree -Cible "$nom / $upn" -Message 'Ajouté'
            }
            catch { Add-HNCSRDResultat -Statut Erreur -Cible "$nom / $upn" -Message $_.Exception.Message }
        }
        if ($Synchroniser) {
            foreach ($m in $actuels) {
                $upn = ConvertTo-UpnNormalise $m.LoginName
                $mail = ''
                if ($m.Email) { $mail = ([string]$m.Email).ToLowerInvariant() }
                if ($voulus -contains $upn -or ($mail -and $voulus -contains $mail)) { continue }
                if ($code -eq $codeProp -and ($upn -eq $service -or $mail -eq $service)) { continue }
                $libelle = "$nom / $($m.LoginName)"
                if ($PSCmdlet.ShouldProcess($libelle, 'Retirer du groupe (absent du fichier)')) {
                    try {
                        Remove-PnPGroupMember -Group $nom -LoginName $m.LoginName -ErrorAction Stop
                        Add-HNCSRDResultat -Statut Retire -Cible $libelle -Message 'Absent du fichier'
                    }
                    catch { Add-HNCSRDResultat -Statut Erreur -Cible $libelle -Message $_.Exception.Message }
                }
                else { Add-HNCSRDResultat -Statut Simule -Cible $libelle -Message 'Serait retiré (absent du fichier)' }
            }
        }
    }
}
catch { Add-HNCSRDResultat -Statut Erreur -Cible 'Set-HNCSRDMembres' -Message $_.Exception.Message }
finally {
    Set-HNCSRDEtape -Nom 'Resume'
    $resume = @(Get-HNCSRDResume)
    Write-HNCSRDLog -Message ("Résumé :`n" + (($resume | Format-Table -AutoSize | Out-String).TrimEnd()))
    $erreurs = 0; foreach ($r in $resume) { $erreurs += $r.Erreur }
    if ($erreurs -gt 0) { $codeSortie = 1 }
}
exit $codeSortie
