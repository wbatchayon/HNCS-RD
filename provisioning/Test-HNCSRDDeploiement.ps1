<#
.SYNOPSIS
    Contrôle post-déploiement en LECTURE SEULE : compare le site SharePoint au modèle généré de la spec.

.DESCRIPTION
    Vérifie, pour les objets de lot <= -Lot :
      - site (titre, langue, fuseau) ; niveau d'autorisation CSS (permissions exactes) ; groupes
        (existence, propriétaire G_PROP) ; attributions du site (G_PROP FC, autres R) ;
      - listes et bibliothèques : URL, titre, versioning, héritage rompu, attributions = matrice § 7.3
        (les niveaux masqués « Accès limité » posés par les permissions d'éléments sont ignorés) ;
      - colonnes : existence, nom interne, type, libellé, obligatoire, index, unicité, choix ordonnés,
        défaut, format, min/max/décimales, liste cible et ShowField des lookups, visibilité formulaires ;
        colonne Title (libellé, obligatoire, index, unicité) ;
      - règles de validation ; vues (existence, colonnes, requête CAML, pagination, vue par défaut) ;
      - paramètres (clés présentes, marqueurs non résolus) ; seeds (clés présentes) ;
      - TransitionsStatuts (chaque code du modèle conforme et actif ; codes hors modèle inactifs).
    Produit un rapport d'écarts (écran, journal provisioning/logs/test-*.log et, avec -RapportPath, JSON).
    Code de sortie 1 si au moins un écart de gravité Erreur.

.EXAMPLE
    pwsh ./provisioning/Test-HNCSRDDeploiement.ps1 -Lot 1 -RapportPath ./provisioning/logs/ecarts.json
#>
[CmdletBinding()]
param(
    [string]$ConfigPath,
    [string]$ModelPath,
    [ValidateRange(1, 5)][int]$Lot = 1,
    [string]$RapportPath,
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
Start-HNCSRDLog -Path (Join-Path $PSScriptRoot ("logs/test-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss')))
# Lecture seule : toute écriture accidentelle d'une fonction du module serait simulée.
Set-HNCSRDSimulation -Actif $true

$script:Ecarts = New-Object System.Collections.Generic.List[object]
$script:Controles = 0
function Add-Ecart {
    param([string]$Categorie, [string]$Objet, [string]$Element, $Attendu, $Constate, [ValidateSet('Erreur', 'Avertissement')][string]$Gravite = 'Erreur')
    $script:Ecarts.Add([pscustomobject]@{ Gravite = $Gravite; Categorie = $Categorie; Objet = $Objet; Element = $Element; Attendu = [string]$Attendu; Constate = [string]$Constate })
    $niveau = 'Erreur'; if ($Gravite -eq 'Avertissement') { $niveau = 'Avertissement' }
    Write-HNCSRDLog -Message ("ÉCART {0} / {1} / {2} : attendu « {3} », constaté « {4} »" -f $Categorie, $Objet, $Element, $Attendu, $Constate) -Niveau $niveau
}
function Test-Egal {
    param([string]$Categorie, [string]$Objet, [string]$Element, $Attendu, $Constate, [string]$Gravite = 'Erreur')
    $script:Controles++
    if ([string]$Attendu -cne [string]$Constate) { Add-Ecart -Categorie $Categorie -Objet $Objet -Element $Element -Attendu $Attendu -Constate $Constate -Gravite $Gravite }
}
function Test-Attributions {
    param($Securable, $AttenduesCodes, [string]$Objet, $Modele)
    $noms = New-Object System.Collections.Specialized.OrderedDictionary
    foreach ($k in $AttenduesCodes.Keys) {
        $n = Get-HNCSRDRoleDefinitionName -Code ([string]$AttenduesCodes[$k]) -Model $Modele
        if (-not $n) { $n = '(niveau ' + $AttenduesCodes[$k] + ' introuvable)' }
        $noms[$k] = $n
    }
    $cmp = Compare-HNCSRDAttributions -Etat @(Get-HNCSRDEtatAttributions -Securable $Securable) -Attendues $noms
    $script:Controles++
    foreach ($a in $cmp.AAjouter) { Add-Ecart -Categorie 'Permissions' -Objet $Objet -Element $a.Nom -Attendu $a.Role -Constate '(absente)' }
    foreach ($r in $cmp.ARetirer) { Add-Ecart -Categorie 'Permissions' -Objet $Objet -Element "$($r.Nom) ($($r.Type))" -Attendu '(aucune)' -Constate $r.Role }
}

$codeSortie = 0
$modele = $null
$config = $null
try {
    Set-HNCSRDEtape -Nom 'Prerequis'
    [void](Assert-HNCSRDPrerequis)
    $modele = Get-HNCSRDModel -Path $ModelPath -Force
    $config = Get-HNCSRDConfig -Path $ConfigPath
    Connect-HNCSRD -Config $config -CertificatePath $CertificatePath -Thumbprint $Thumbprint -CertificatePassword $CertificatePassword | Out-Null

    # --- Site -------------------------------------------------------------------------------
    Set-HNCSRDEtape -Nom 'Site'
    $web = Get-PnPWeb -Includes Title, Language, RegionalSettings.TimeZone
    Test-Egal 'Site' 'Site' 'Titre' $modele.site.title $web.Title
    Test-Egal 'Site' 'Site' 'Langue (LCID)' $modele.site.lcid $web.Language
    Test-Egal 'Site' 'Site' 'Fuseau horaire (ID)' (Get-HNCSRDTimeZoneId -TimeZone $modele.site.timeZone) $web.RegionalSettings.TimeZone.Id

    # --- Niveaux d'autorisation ------------------------------------------------------------
    Set-HNCSRDEtape -Nom 'NiveauxAutorisation'
    $defs = @(Get-PnPRoleDefinition)
    foreach ($p in $modele.permissionLevels.PSObject.Properties) {
        $niv = $p.Value
        if ($niv.PSObject.Properties.Name -contains 'roleTypeKind') {
            Test-Egal 'Niveaux' $p.Name 'RoleTypeKind présent' 'Oui' $(if (@($defs | Where-Object { [string]$_.RoleTypeKind -eq [string]$niv.roleTypeKind }).Count) { 'Oui' } else { 'Non' })
            continue
        }
        $existant = @($defs | Where-Object { $_.Name -eq [string]$niv.name })
        if ($existant.Count -eq 0) { $script:Controles++; Add-Ecart 'Niveaux' $niv.name 'Existence' 'présent' 'absent'; continue }
        $base = @($defs | Where-Object { [string]$_.RoleTypeKind -eq [string]$niv.basedOn })[0]
        $attendues = @(Get-HNCSRDPermissionKinds -RoleDefinition $base | Where-Object { @($niv.remove) -notcontains $_ }) -join ','
        Test-Egal 'Niveaux' $niv.name 'Permissions' $attendues ((Get-HNCSRDPermissionKinds -RoleDefinition $existant[0]) -join ',')
    }

    # --- Groupes -----------------------------------------------------------------------------
    Set-HNCSRDEtape -Nom 'Groupes'
    $nomProp = Get-HNCSRDGroupName -Code (Get-HNCSRDOwnerGroupCode -Model $modele) -Model $modele
    foreach ($g in $modele.groups) {
        $grp = $null
        try { $grp = Get-PnPGroup -Identity $g.name -ErrorAction Stop } catch { $grp = $null }
        if (-not $grp) { $script:Controles++; Add-Ecart 'Groupes' $g.name 'Existence' 'présent' 'absent'; continue }
        $owner = Get-PnPProperty -ClientObject $grp -Property Owner
        Test-Egal 'Groupes' $g.name 'Propriétaire' $nomProp $owner.Title
        foreach ($m in @(Get-PnPGroupMember -Group $g.name)) {
            if ([string]$m.PrincipalType -ne 'User') { Add-Ecart 'Groupes' $g.name "Membre $($m.Title)" 'compte utilisateur direct (H-14)' $m.PrincipalType 'Avertissement' }
        }
    }
    Set-HNCSRDEtape -Nom 'GroupesParDefaut'
    # § 7.2 (v1.2.0) : les groupes créés par défaut avec le site restent vides et sans attribution.
    foreach ($gd in @(Get-HNCSRDGroupesParDefaut -Model $modele)) {
        $nbMembres = @(Get-PnPGroupMember -Group $gd.Title).Count
        Test-Egal 'Groupes' $gd.Title 'Membres (groupe par défaut)' 0 $nbMembres
    }
    Set-HNCSRDEtape -Nom 'PermissionsSite'
    Test-Attributions -Securable (Get-PnPWeb) -AttenduesCodes (Get-HNCSRDAttributionsSite -Model $modele) -Objet 'Site' -Modele $modele

    # --- Listes, colonnes, validation, vues, permissions ------------------------------------
    foreach ($o in (Get-HNCSRDObjects -Lot $Lot -Model $modele)) {
        Set-HNCSRDEtape -Nom $o.name
        $liste = Get-HNCSRDList -Name $o.name -Model $modele
        $script:Controles++
        if (-not $liste) { Add-Ecart 'Listes' $o.name 'Existence' ('/' + (Get-HNCSRDListUrl -Name $o.name -Model $modele)) 'absente'; continue }
        [void](Get-PnPProperty -ClientObject $liste -Property Title, BaseTemplate, EnableVersioning, MajorVersionLimit, EnableMinorVersions, MajorWithMinorVersionsLimit, HasUniqueRoleAssignments, ValidationFormula, ValidationMessage)
        Test-Egal 'Listes' $o.name 'Titre' $o.title $liste.Title
        $gabarit = 100; if ($o.kind -eq 'library') { $gabarit = 101 }
        Test-Egal 'Listes' $o.name 'Modèle (BaseTemplate)' $gabarit ([int]$liste.BaseTemplate)
        $v = Get-HNCSRDVersioningSpec -Object $o
        Test-Egal 'Versioning' $o.name 'Versions activées' $v.EnableVersioning $liste.EnableVersioning
        Test-Egal 'Versioning' $o.name 'Versions majeures' $v.MajorVersions $liste.MajorVersionLimit
        if ($o.kind -eq 'library') {
            Test-Egal 'Versioning' $o.name 'Versions mineures' $v.EnableMinorVersions $liste.EnableMinorVersions
            if ($v.EnableMinorVersions) { Test-Egal 'Versioning' $o.name 'Majeures avec mineures' $v.MinorVersions $liste.MajorWithMinorVersionsLimit }
        }
        Test-Egal 'Permissions' $o.name 'Héritage rompu' $true $liste.HasUniqueRoleAssignments
        Test-Attributions -Securable $liste -AttenduesCodes (Get-HNCSRDAttributionsAttendues -ObjectName $o.name -Model $modele) -Objet $o.name -Modele $modele

        $champs = Get-HNCSRDChamps -List $liste
        if ($o.prefix -and $champs.ContainsKey('IdHNCS')) {
            # § 2.2 (v1.2.0) : IdHNCS sans contrainte d'unicité SharePoint ; aucun doublon non vide toléré.
            $vus = @{}
            foreach ($it in @(Get-PnPListItem -List $liste -PageSize 2000 -Fields 'ID', 'IdHNCS')) {
                $idm = [string]$it['IdHNCS']
                if (-not $idm) { continue }
                if ($vus.ContainsKey($idm)) { $vus[$idm] += [int]$it.Id } else { $vus[$idm] = @([int]$it.Id) }
            }
            $script:Controles++
            foreach ($k in $vus.Keys) {
                if (@($vus[$k]).Count -gt 1) { Add-Ecart 'Donnees' $o.name "IdHNCS $k" 'unique' ('doublon (ID ' + (@($vus[$k]) -join ', ') + ')') }
            }
        }
        if ($o.titleLabel) {
            $t = $champs['Title']
            Test-Egal 'Colonnes' $o.name 'Title / libellé' $o.titleLabel $t.Title
            Test-Egal 'Colonnes' $o.name 'Title / obligatoire' ([bool]$o.titleRequired) ([bool]$t.Required)
            Test-Egal 'Colonnes' $o.name 'Title / index' ([bool]$o.titleColumn.indexed -or [bool]$o.titleColumn.unique) ([bool]$t.Indexed)
            Test-Egal 'Colonnes' $o.name 'Title / unique' ([bool]$o.titleColumn.unique) ([bool]$t.EnforceUniqueValues)
        }
        foreach ($c in (Get-HNCSRDColumns -Object $o -Lot $Lot)) {
            $script:Controles++
            if (-not $champs.ContainsKey([string]$c.name)) { Add-Ecart 'Colonnes' $o.name $c.name 'présente' 'absente'; continue }
            $idCible = $null
            if (Test-HNCSRDLookupType -Type $c.type) {
                $lc = Get-HNCSRDList -Name $c.lookup -Model $modele
                if ($lc) { $idCible = [string]$lc.Id } else { $idCible = [guid]::Empty.ToString() }
            }
            $attendu = ConvertTo-HNCSRDFieldXml -Column $c -LookupListId $idCible -Model $modele
            $champ = $champs[[string]$c.name]
            $actuel = $null
            try { $actuel = [string]$champ.SchemaXml } catch { $actuel = $null }
            if (-not $actuel) { [void](Get-PnPProperty -ClientObject $champ -Property SchemaXml); $actuel = [string]$champ.SchemaXml }
            foreach ($e in @(Compare-HNCSRDFieldSchema -SchemaActuel $actuel -SchemaAttendu $attendu)) {
                Add-Ecart 'Colonnes' $o.name "$($c.name) / $($e.Propriete)" $e.Attendu $e.Constate
            }
        }
        if ($o.validation) {
            $noms = @{}; foreach ($k in $champs.Keys) { $noms[$k] = [string]$champs[$k].Title }
            $attendue = $null
            try { $attendue = ConvertTo-HNCSRDValidationFormula -Formula $o.validation -NomsAffiches $noms } catch { $attendue = $o.validation }
            $script:Controles++
            if ([string]$liste.ValidationFormula -cne $attendue -and [string]$liste.ValidationFormula -cne [string]$o.validation) {
                Add-Ecart 'Validation' $o.name 'Formule' $attendue $liste.ValidationFormula
            }
            Test-Egal 'Validation' $o.name 'Message' $o.validationMessage $liste.ValidationMessage
        }
        elseif ($liste.ValidationFormula) { Add-Ecart 'Validation' $o.name 'Formule' '(aucune)' $liste.ValidationFormula 'Avertissement' }

        if ($modele.views.PSObject.Properties.Name -contains $o.name) {
            $vues = @(Get-PnPView -List $liste)
            $types = Get-HNCSRDColumnTypes -Object $o -Lot $Lot
            foreach ($vm in @($modele.views.($o.name))) {
                $script:Controles++
                $caml = ConvertTo-HNCSRDCaml -View $vm -ColumnTypes $types -ListKind $o.kind
                $vs = @($vues | Where-Object { $_.Title -eq $caml.Name }) | Select-Object -First 1
                if (-not $vs) { Add-Ecart 'Vues' $o.name $caml.Name 'présente' 'absente'; continue }
                [void](Get-PnPProperty -ClientObject $vs -Property ViewFields, ViewQuery, RowLimit, DefaultView, Paged)
                Test-Egal 'Vues' $o.name "$($caml.Name) / colonnes" ($caml.ViewFields -join ', ') (@($vs.ViewFields) -join ', ')
                Test-Egal 'Vues' $o.name "$($caml.Name) / requête" (Format-HNCSRDCamlNormalise $caml.Query) (Format-HNCSRDCamlNormalise $vs.ViewQuery)
                Test-Egal 'Vues' $o.name "$($caml.Name) / éléments par page" $caml.RowLimit $vs.RowLimit
                Test-Egal 'Vues' $o.name "$($caml.Name) / par défaut" $caml.Default ([bool]$vs.DefaultView)
            }
        }
    }

    # --- Paramètres et seeds -----------------------------------------------------------------
    Set-HNCSRDEtape -Nom 'Referentiels'
    $lp = Get-HNCSRDList -Name 'Parametres' -Model $modele
    if ($lp) {
        $items = Get-HNCSRDItemsParCle -List $lp -Champ 'Title'
        foreach ($p in $modele.parameters) {
            $script:Controles++
            if (-not $items.ContainsKey([string]$p.key)) { Add-Ecart 'Parametres' 'Parametres' $p.key 'présent' 'absent'; continue }
            Test-Egal 'Parametres' 'Parametres' "$($p.key) / catégorie" $p.category $items[[string]$p.key]['Categorie']
            if ([string]$items[[string]$p.key]['Valeur'] -match '<[A-Za-z]+>') { Add-Ecart 'Parametres' 'Parametres' $p.key 'valeur résolue' $items[[string]$p.key]['Valeur'] 'Avertissement' }
        }
    }
    foreach ($s in $modele.seeds.PSObject.Properties) {
        $obj = Get-HNCSRDObject -Name $s.Name -Model $modele
        if ([int]$obj.lot -gt $Lot) { continue }
        $ls = Get-HNCSRDList -Name $s.Name -Model $modele
        if (-not $ls) { continue }
        $lignes = @($s.Value)
        if ($lignes.Count -eq 0) { continue }
        $cle = 'Title'
        if ($lignes[0].PSObject.Properties.Name -contains 'IdHNCS') { $cle = 'IdHNCS' } elseif ($lignes[0].PSObject.Properties.Name -contains 'Code') { $cle = 'Code' }
        $items = Get-HNCSRDItemsParCle -List $ls -Champ $cle
        foreach ($l in $lignes) {
            $script:Controles++
            if (-not $items.ContainsKey([string]$l.$cle)) { Add-Ecart 'Seeds' $s.Name ([string]$l.$cle) 'présent' 'absent' 'Avertissement' }
        }
    }

    # --- Transitions ---------------------------------------------------------------------------
    Set-HNCSRDEtape -Nom 'Transitions'
    $lt = Get-HNCSRDList -Name 'TransitionsStatuts' -Model $modele
    if ($lt) {
        $items = Get-HNCSRDItemsParCle -List $lt -Champ 'Title'
        $codes = @{}
        foreach ($t in $modele.transitions) {
            $codes[[string]$t.code] = $true
            $script:Controles++
            if (-not $items.ContainsKey([string]$t.code)) { Add-Ecart 'Transitions' 'TransitionsStatuts' $t.code 'présente' 'absente'; continue }
            $attendu = Get-HNCSRDTransitionValeurs -Transition $t
            $diffs = Compare-HNCSRDTransitionItem -Item $items[[string]$t.code] -Attendu $attendu
            foreach ($k in $diffs.Keys) {
                $constate = $items[[string]$t.code][$k]
                if ($constate -is [array]) { $constate = $constate -join ';' }
                $att = $attendu[$k]; if ($att -is [array]) { $att = $att -join ';' }
                Add-Ecart 'Transitions' 'TransitionsStatuts' "$($t.code) / $k" $att $constate
            }
        }
        foreach ($code in $items.Keys) {
            if (-not $codes.ContainsKey($code) -and [bool]$items[$code]['Actif']) { Add-Ecart 'Transitions' 'TransitionsStatuts' "$code / Actif" 'Non (absente du modèle)' 'Oui' }
        }
    }
}
catch {
    $script:Ecarts.Add([pscustomobject]@{ Gravite = 'Erreur'; Categorie = 'Execution'; Objet = 'Test-HNCSRDDeploiement'; Element = ''; Attendu = ''; Constate = $_.Exception.Message })
    Write-HNCSRDLog -Message $_.Exception.Message -Niveau Erreur
}
finally {
    Set-HNCSRDEtape -Nom 'Rapport'
    $erreurs = @($script:Ecarts | Where-Object { $_.Gravite -eq 'Erreur' }).Count
    $avert = @($script:Ecarts | Where-Object { $_.Gravite -eq 'Avertissement' }).Count
    if ($script:Ecarts.Count -gt 0) {
        Write-HNCSRDLog -Message ("Écarts :`n" + (($script:Ecarts | Format-Table Gravite, Categorie, Objet, Element, Attendu, Constate -AutoSize -Wrap | Out-String).TrimEnd()))
    }
    Write-HNCSRDLog -Message ("{0} contrôle(s), {1} écart(s) bloquant(s), {2} avertissement(s)" -f $script:Controles, $erreurs, $avert) -Niveau $(if ($erreurs) { 'Erreur' } else { 'Succes' })
    if ($RapportPath) {
        $dossier = Split-Path -Parent $RapportPath
        if ($dossier -and -not (Test-Path -LiteralPath $dossier)) { [void][System.IO.Directory]::CreateDirectory($dossier) }
        $rapport = [pscustomobject]@{ Date = (Get-Date).ToString('o'); SiteUrl = $(if ($config) { $config.SiteUrl } else { '' }); Lot = $Lot; Controles = $script:Controles; Erreurs = $erreurs; Avertissements = $avert; Ecarts = $script:Ecarts.ToArray() }
        [System.IO.File]::WriteAllText($RapportPath, ($rapport | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding($false)))
    }
    if ($erreurs -gt 0) { $codeSortie = 1 }
}
exit $codeSortie
