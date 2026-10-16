<#
.SYNOPSIS
    Charge le jeu de test fictif HNCS-RD (testdata/data/*.json) dans un site SharePoint de RECETTE.

.DESCRIPTION
    - Ordre d'import topologique calculé depuis les lookups du modèle généré (provisioning/model/model.generated.json),
      les colonnes de recherche vers la même liste (ex. Affectations.AffectationRemplacee) étant posées en seconde passe.
    - Jetons résolus : "@persona:CLE" (personas.json), "@J+7" / "@J-30T09:00" (date relative au jour d'import ou à
      -DateReference), "@site:/chemin" (URL du site), "@id:IDHNCS" (ID SharePoint de l'élément, nombre ou texte),
      "@empreinte" (Affectations.EmpreinteVerrou {"AlternantId","SujetId","ReferentId","DateDebut"} ;
      ActionsIntegration.EmpreinteAction {"Bloquante","Statut"}).
    - Idempotent : un élément est retrouvé par sa clé (IdHNCS ; à défaut FluxRunId pour HistoriqueStatuts, RunUrl pour
      JournalFlux, CleSynchro pour GitlabSync) puis mis à jour, sinon créé. StatutPrecedent est toujours égal à Statut.
    - -Reset supprime (corbeille) UNIQUEMENT les éléments dont la clé figure dans le jeu de test, puis s'arrête.
    - Refuse de s'exécuter si l'URL du site ne contient aucun marqueur de recette, sauf -Force.
    - -PermissionsElement reproduit les permissions par élément de la spec § 7.4 sur les éléments importés
      (en production, elles sont posées par les flux).
    - -ExporterMembres écrit un fichier au format provisioning/config/membres.json à partir des personas, puis s'arrête.

    Cible : PowerShell 7.4 + PnP.PowerShell 2.x. Le fichier reste analysable par Windows PowerShell 5.1.
    Exécuter avec un compte membre de HNCS-RD-Proprietaires, flux désactivés ou sous le compte de service
    (les écritures du compte de service ne déclenchent aucun flux, spec § 8.1).

.EXAMPLE
    ./testdata/Import-TestData.ps1 -ConfigPath ./provisioning/config/tenant.json -SiteUrl https://contoso.sharepoint.com/sites/HNCS-RD-Recette
.EXAMPLE
    ./testdata/Import-TestData.ps1 -SiteUrl https://contoso.sharepoint.com/sites/HNCS-RD-Recette -ClientId <guid> -Reset
.EXAMPLE
    ./testdata/Import-TestData.ps1 -ExporterMembres ./provisioning/config/membres.json
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ConfigPath,
    [string]$SiteUrl,
    [string]$ClientId,
    [string]$PersonasPath,
    [string]$DataPath,
    [string]$ModelPath,
    [ValidateRange(1, 5)][int]$Lot = 5,
    [string[]]$Listes,
    [datetime]$DateReference = (Get-Date).Date,
    [string[]]$MarqueursRecette = @('recette', 'test', 'qualif', 'dev'),
    [switch]$Reset,
    [switch]$PermissionsElement,
    [ValidateSet('Groupe', 'Destinataire')][string]$PartageTransmission = 'Groupe',
    [string]$ExporterMembres,
    [switch]$Force
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$racine = Split-Path -Parent $PSScriptRoot
if (-not $PersonasPath) { $PersonasPath = Join-Path $PSScriptRoot 'personas.json' }
if (-not $DataPath) { $DataPath = Join-Path $PSScriptRoot 'data' }
if (-not $ModelPath) { $ModelPath = Join-Path $racine 'provisioning/model/model.generated.json' }
$moduleProvisioning = Join-Path $racine 'provisioning/modules/HNCSRD.Provisioning.psd1'

$ClesNaturelles = @{ HistoriqueStatuts = 'FluxRunId'; JournalFlux = 'RunUrl'; GitlabSync = 'CleSynchro' }
$script:Stats = @{}

#region Utilitaires ----------------------------------------------------------------------------

function Write-Etape([string]$Message) { Write-Host ('== ' + $Message) -ForegroundColor Cyan }

function Add-Stat([string]$Liste, [string]$Type) {
    if (-not $script:Stats.ContainsKey($Liste)) { $script:Stats[$Liste] = @{ Cree = 0; MisAJour = 0; Supprime = 0; Erreur = 0 } }
    $script:Stats[$Liste][$Type]++
}

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "Fichier introuvable : $Path" }
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Get-Props($Objet) {
    if ($null -eq $Objet) { return @() }
    return @($Objet.PSObject.Properties | Where-Object { $_.MemberType -eq 'NoteProperty' })
}

function Get-Personas([string]$Path) {
    $table = @{}
    foreach ($p in (Get-Props (Read-JsonFile $Path))) {
        if ($p.Name.StartsWith('$')) { continue }
        $table[$p.Name] = $p.Value
    }
    return $table
}

function Resolve-DateRelative([string]$Valeur, [datetime]$Reference) {
    $m = [regex]::Match($Valeur, '^@J(?:([+-])(\d{1,4}))?(?:T(\d{2}):(\d{2}))?$')
    if ($m.Success) {
        $jours = 0
        if ($m.Groups[2].Success) { $jours = [int]$m.Groups[2].Value; if ($m.Groups[1].Value -eq '-') { $jours = -$jours } }
        $d = $Reference.Date.AddDays($jours)
        if ($m.Groups[3].Success) { $d = $d.AddHours([int]$m.Groups[3].Value).AddMinutes([int]$m.Groups[4].Value) }
        return $d
    }
    return [datetime]::Parse($Valeur, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Resolve-Persona([string]$Valeur) {
    $m = [regex]::Match($Valeur, '^@persona:([A-Z][A-Z0-9_]*)$')
    if (-not $m.Success) { return $Valeur }
    $cle = $m.Groups[1].Value
    if (-not $script:Personas.ContainsKey($cle)) { throw "Persona inconnue : $cle (voir $PersonasPath)" }
    return [string]$script:Personas[$cle].upn
}

function Get-ObjetModele([string]$Nom) {
    $o = @($script:Model.objects | Where-Object { $_.name -eq $Nom })
    if ($o.Count -ne 1) { throw "Liste inconnue du modèle : $Nom" }
    return $o[0]
}

function Get-UrlListe([string]$Nom) {
    $o = Get-ObjetModele $Nom
    if ($o.kind -eq 'library') { return [string]$o.name }
    return ('Lists/' + $o.name)
}

function Get-Colonnes([string]$Nom) {
    $o = Get-ObjetModele $Nom
    $cols = @{}
    foreach ($c in $o.columns) { $cols[[string]$c.name] = $c }
    $cols['Title'] = $o.titleColumn
    return $cols
}

function Get-CleListe([string]$Nom) {
    $o = Get-ObjetModele $Nom
    if ($o.prefix) { return 'IdHNCS' }
    if ($ClesNaturelles.ContainsKey($Nom)) { return $ClesNaturelles[$Nom] }
    throw "Aucune clé d'idempotence pour la liste $Nom"
}

function Get-ListePourId([string]$IdHNCS) {
    $prefixe = ($IdHNCS -split '-')[0]
    foreach ($o in $script:Model.objects) { if ($o.prefix -eq $prefixe) { return [string]$o.name } }
    throw "Préfixe inconnu : $IdHNCS"
}

function Get-CarteIds([string]$Liste) {
    <# IdHNCS (ou clé naturelle) -> ID SharePoint, mis en cache. #>
    if ($script:Cartes.ContainsKey($Liste)) { return $script:Cartes[$Liste] }
    $cle = Get-CleListe $Liste
    $carte = @{}
    $items = Get-PnPListItem -List (Get-UrlListe $Liste) -PageSize 2000 -Fields 'ID', $cle
    foreach ($it in $items) {
        $v = $it[$cle]
        if ($v -is [Microsoft.SharePoint.Client.FieldUrlValue]) { $v = $v.Url }
        if ($v) { $carte[[string]$v] = [int]$it.Id }
    }
    $script:Cartes[$Liste] = $carte
    return $carte
}

function Resolve-IdSharePoint([string]$Liste, [string]$IdHNCS) {
    $carte = Get-CarteIds $Liste
    if (-not $carte.ContainsKey($IdHNCS)) { throw "Élément $IdHNCS introuvable dans $Liste (import ou provisioning manquant)" }
    return [int]$carte[$IdHNCS]
}

function Get-ValeurCle($Item, [string]$Cle) {
    $p = $Item.PSObject.Properties[$Cle]
    if ($null -eq $p) { return $null }
    $v = [string]$p.Value
    if ($v.StartsWith('@site:')) { $v = $script:SiteUrl.TrimEnd('/') + $v.Substring(6) }
    return $v
}

function ConvertTo-ValeurSharePoint($Colonne, $Valeur, [string]$Liste) {
    if ($null -eq $Valeur) { return $null }
    $type = [string]$Colonne.type
    switch ($type) {
        'Lookup' { return (Resolve-IdSharePoint ([string]$Colonne.lookup) ([string]$Valeur)) }
        'LookupMulti' {
            $ids = @(); foreach ($v in @($Valeur)) { $ids += (Resolve-IdSharePoint ([string]$Colonne.lookup) ([string]$v)) }
            return , ([int[]]$ids)
        }
        'User' { return (Resolve-Persona ([string]$Valeur)) }
        'UserMulti' {
            $u = @(); foreach ($v in @($Valeur)) { $u += (Resolve-Persona ([string]$v)) }
            return , ([string[]]$u)
        }
        'Date' { return (Resolve-DateRelative ([string]$Valeur) $DateReference).ToString('yyyy-MM-dd') }
        'DateTime' { return (Resolve-DateRelative ([string]$Valeur) $DateReference) }
        'Boolean' { return [bool]$Valeur }
        'Number' {
            $s = [string]$Valeur
            if ($s.StartsWith('@id:')) { $id = $s.Substring(4); return (Resolve-IdSharePoint (Get-ListePourId $id) $id) }
            return [double]$Valeur
        }
        'MultiChoice' { return , ([string[]]@($Valeur)) }
        'URL' {
            $u = [string]$Valeur
            if ($u.StartsWith('@site:')) { $u = $script:SiteUrl.TrimEnd('/') + $u.Substring(6) }
            $desc = ($u.TrimEnd('/') -split '/')[-1]
            return ($u + ', ' + $desc)
        }
        default {
            $s = [string]$Valeur
            if ($s.StartsWith('@persona:')) { return (Resolve-Persona $s) }
            if ($s.StartsWith('@id:')) { $id = $s.Substring(4); return [string](Resolve-IdSharePoint (Get-ListePourId $id) $id) }
            return $s
        }
    }
}

function Get-Empreinte([string]$Liste, [string]$Colonne, [hashtable]$Valeurs) {
    <# Empreintes calculées à l'import (format documenté dans testdata/README.md). #>
    if ($Liste -eq 'Affectations' -and $Colonne -eq 'EmpreinteVerrou') {
        $o = [ordered]@{ AlternantId = $Valeurs['Alternant']; SujetId = $Valeurs['Sujet']; ReferentId = $Valeurs['Referent']; DateDebut = $Valeurs['DateDebut'] }
    }
    elseif ($Liste -eq 'ActionsIntegration' -and $Colonne -eq 'EmpreinteAction') {
        $o = [ordered]@{ Bloquante = [bool]$Valeurs['Bloquante']; Statut = $Valeurs['Statut'] }
    }
    else { throw "Empreinte non prise en charge : $Liste.$Colonne" }
    return (ConvertTo-Json -InputObject $o -Compress)
}

function Get-OrdreTopologique([string[]]$Noms) {
    $deps = @{}
    foreach ($n in $Noms) {
        $deps[$n] = New-Object System.Collections.Generic.HashSet[string]
        foreach ($c in (Get-ObjetModele $n).columns) {
            if (($c.type -eq 'Lookup' -or $c.type -eq 'LookupMulti') -and $c.lookup -ne $n -and $Noms -contains $c.lookup) { [void]$deps[$n].Add([string]$c.lookup) }
        }
        foreach ($it in $script:Data[$n]) {
            foreach ($p in (Get-Props $it)) {
                $s = [string]$p.Value
                if ($s.StartsWith('@id:')) { $cible = Get-ListePourId $s.Substring(4); if ($cible -ne $n -and $Noms -contains $cible) { [void]$deps[$n].Add($cible) } }
            }
        }
    }
    $ordre = New-Object System.Collections.Generic.List[string]
    $restants = New-Object System.Collections.Generic.List[string]
    foreach ($n in ($Noms | Sort-Object)) { $restants.Add($n) }
    while ($restants.Count -gt 0) {
        $prets = @($restants | Where-Object { @($deps[$_] | Where-Object { -not $ordre.Contains($_) }).Count -eq 0 })
        if ($prets.Count -eq 0) { throw ('Cycle de lookups entre : ' + ($restants -join ', ')) }
        foreach ($p in $prets) { $ordre.Add($p); [void]$restants.Remove($p) }
    }
    return $ordre.ToArray()
}

#endregion

#region Chargement -------------------------------------------------------------------------------

$script:Model = Read-JsonFile $ModelPath
if ($ExporterMembres) {
    $script:Personas = Get-Personas $PersonasPath
    $membres = [ordered]@{}
    foreach ($g in $script:Model.groups) { $membres[[string]$g.code] = @() }
    foreach ($k in ($script:Personas.Keys | Sort-Object)) {
        foreach ($g in @($script:Personas[$k].groupes)) { $membres[[string]$g] += [string]$script:Personas[$k].upn }
    }
    $json = ConvertTo-Json -InputObject $membres -Depth 4
    if ($PSCmdlet.ShouldProcess($ExporterMembres, 'Écrire le fichier des membres')) {
        [System.IO.File]::WriteAllText($ExporterMembres, $json, (New-Object System.Text.UTF8Encoding($false)))
        Write-Host "Membres écrits : $ExporterMembres"
    }
    return
}

$script:Personas = Get-Personas $PersonasPath
$script:Data = @{}
foreach ($f in (Get-ChildItem -LiteralPath $DataPath -Filter '*.json' | Sort-Object Name)) {
    $nom = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
    $o = Get-ObjetModele $nom
    if ([int]$o.lot -gt $Lot) { Write-Verbose "$nom (lot $($o.lot)) ignorée : -Lot $Lot"; continue }
    if ($Listes -and $Listes -notcontains $nom) { continue }
    $script:Data[$nom] = @(Read-JsonFile $f.FullName)
}

#endregion

#region Connexion --------------------------------------------------------------------------------

$config = $null
if ($ConfigPath) {
    if (Test-Path -LiteralPath $moduleProvisioning) {
        Import-Module $moduleProvisioning -Force
        $config = Get-HNCSRDConfig -Path $ConfigPath
    }
    else { $config = Read-JsonFile $ConfigPath }
    if (-not $SiteUrl) { $SiteUrl = [string]$config.SiteUrl }
    if (-not $ClientId) { $ClientId = [string]$config.PnPClientId }
}
if (-not $SiteUrl) { throw 'SiteUrl obligatoire (paramètre ou configuration).' }
$script:SiteUrl = $SiteUrl.TrimEnd('/')

$estRecette = $false
foreach ($mq in $MarqueursRecette) { if ($script:SiteUrl.ToLowerInvariant().Contains($mq.ToLowerInvariant())) { $estRecette = $true } }
if (-not $estRecette -and -not $Force) {
    throw ("Refus : l'URL $($script:SiteUrl) ne contient aucun marqueur de recette (" + ($MarqueursRecette -join ', ') + '). Utiliser -Force en connaissance de cause.')
}

Write-Etape "Connexion à $($script:SiteUrl)"
if ($config -and (Get-Command -Name Connect-HNCSRD -ErrorAction SilentlyContinue)) {
    Connect-HNCSRD -Config $config -Url $script:SiteUrl | Out-Null
}
else {
    if (-not $ClientId) { throw 'ClientId (application Entra PnP) obligatoire sans fichier de configuration.' }
    Connect-PnPOnline -Url $script:SiteUrl -Interactive -ClientId $ClientId
}

$presentes = @()
foreach ($n in $script:Data.Keys) {
    $l = Get-PnPList -Identity (Get-UrlListe $n) -ErrorAction SilentlyContinue
    if ($null -eq $l) { Write-Warning "Liste $n absente du site (lot non déployé ?) : ignorée." } else { $presentes += $n }
}
$ordre = @(Get-OrdreTopologique $presentes)
$script:Cartes = @{}
Write-Host ('Ordre d''import : ' + ($ordre -join ' > '))

#endregion

#region Réinitialisation -------------------------------------------------------------------------

if ($Reset) {
    Write-Etape 'Suppression des seuls éléments du jeu de test'
    [array]::Reverse($ordre)
    foreach ($n in $ordre) {
        $cle = Get-CleListe $n
        $carte = Get-CarteIds $n
        foreach ($it in $script:Data[$n]) {
            $k = Get-ValeurCle $it $cle
            if ($k -and $carte.ContainsKey($k)) {
                if ($PSCmdlet.ShouldProcess("$n/$k", 'Supprimer (corbeille)')) {
                    Remove-PnPListItem -List (Get-UrlListe $n) -Identity $carte[$k] -Recycle -Force | Out-Null
                    Add-Stat $n 'Supprime'
                }
            }
        }
    }
}
else {

#endregion

#region Import ----------------------------------------------------------------------------------

    $differes = New-Object System.Collections.Generic.List[object]
    foreach ($n in $ordre) {
        Write-Etape "Import de $n ($(@($script:Data[$n]).Count) éléments)"
        $cols = Get-Colonnes $n
        $obj = Get-ObjetModele $n
        $cle = Get-CleListe $n
        $carte = Get-CarteIds $n
        foreach ($it in $script:Data[$n]) {
            $k = Get-ValeurCle $it $cle
            try {
                $valeurs = @{}
                $self = @{}
                $empreintes = @()
                foreach ($p in (Get-Props $it)) {
                    $col = $cols[$p.Name]
                    if ($null -eq $col) { throw "Colonne inconnue $($p.Name)" }
                    if ($null -eq $p.Value) { continue }
                    if ([string]$p.Value -eq '@empreinte') { $empreintes += $p.Name; continue }
                    if (($col.type -eq 'Lookup' -or $col.type -eq 'LookupMulti') -and $col.lookup -eq $n) { $self[$p.Name] = $p.Value; continue }
                    $valeurs[$p.Name] = ConvertTo-ValeurSharePoint $col $p.Value $n
                }
                if ($obj.statusEnum -and $valeurs.ContainsKey('Statut')) { $valeurs['StatutPrecedent'] = $valeurs['Statut'] }
                foreach ($ce in $empreintes) { $valeurs[$ce] = Get-Empreinte $n $ce $valeurs }
                if ($PSCmdlet.ShouldProcess("$n/$k", 'Créer ou mettre à jour')) {
                    if ($carte.ContainsKey($k)) {
                        Set-PnPListItem -List (Get-UrlListe $n) -Identity $carte[$k] -Values $valeurs | Out-Null
                        Add-Stat $n 'MisAJour'
                    }
                    else {
                        $nouv = Add-PnPListItem -List (Get-UrlListe $n) -Values $valeurs
                        $carte[$k] = [int]$nouv.Id
                        Add-Stat $n 'Cree'
                    }
                    if ($self.Count -gt 0) { $differes.Add(@{ Liste = $n; Cle = $k; Valeurs = $self }) }
                }
            }
            catch {
                Add-Stat $n 'Erreur'
                Write-Warning "$n/$k : $($_.Exception.Message)"
            }
        }
    }

    if ($differes.Count -gt 0) {
        Write-Etape 'Seconde passe : lookups vers la même liste'
        foreach ($d in $differes) {
            $cols = Get-Colonnes $d.Liste
            $v = @{}
            foreach ($nomCol in $d.Valeurs.Keys) { $v[$nomCol] = ConvertTo-ValeurSharePoint $cols[$nomCol] $d.Valeurs[$nomCol] $d.Liste }
            Set-PnPListItem -List (Get-UrlListe $d.Liste) -Identity (Resolve-IdSharePoint $d.Liste $d.Cle) -Values $v | Out-Null
        }
    }

#endregion

#region Permissions par élément (spec § 7.4) -----------------------------------------------------

    if ($PermissionsElement) {
        Write-Etape 'Permissions par élément (émulation de § 7.4)'
        $nomCSS = [string]$script:Model.permissionLevels.CSS.name
        $lecteur = @(Get-PnPRoleDefinition | Where-Object { [string]$_.RoleTypeKind -eq 'Reader' })[0].Name
        $grpADM = @($script:Model.groups | Where-Object { $_.code -eq 'G_ADM' })[0].name
        $transmis = @("Transmise à l'administration", 'Entretien planifié', 'Entretien réalisé', 'En attente de décision', 'Retenue', 'Formalités en cours', 'Intégrée')
        $compteAlt = @{}
        foreach ($a in @($script:Data['Alternants'])) { if ($a -and $a.PSObject.Properties['CompteM365'] -and $a.CompteM365) { $compteAlt[[string]$a.IdHNCS] = Resolve-Persona ([string]$a.CompteM365) } }
        $accorder = {
            param([string]$Liste, [string]$Id, [string]$Principal, [string]$Role, [switch]$Groupe)
            $p = @{ List = (Get-UrlListe $Liste); Identity = (Resolve-IdSharePoint $Liste $Id); AddRole = $Role }
            if ($Groupe) { $p['Group'] = $Principal } else { $p['User'] = $Principal }
            if ($PSCmdlet.ShouldProcess("$Liste/$Id", "Accorder $Role à $Principal")) { Set-PnPListItemPermission @p | Out-Null }
        }
        foreach ($c in @($script:Data['Candidatures'])) {
            if ($null -eq $c) { continue }
            $aEteTransmise = $transmis -contains [string]$c.Statut -or ($c.PSObject.Properties['DateTransmissionAdmin'] -and $c.DateTransmissionAdmin)
            if (-not $aEteTransmise) { continue }
            # Recrutement.PartageTransmission (H-45) : Groupe (défaut) ou Destinataire seul
            if ($PartageTransmission -eq 'Destinataire' -and $c.PSObject.Properties['DestinataireAdmin'] -and $c.DestinataireAdmin) {
                & $accorder 'Candidatures' $c.IdHNCS (Resolve-Persona ([string]$c.DestinataireAdmin)) $nomCSS
            }
            else { & $accorder 'Candidatures' $c.IdHNCS $grpADM $nomCSS -Groupe }
        }
        foreach ($a in @($script:Data['Affectations'])) {
            if ($null -eq $a) { continue }
            if ($a.PSObject.Properties['EmpreinteVerrou'] -and $a.EmpreinteVerrou -and $compteAlt.ContainsKey([string]$a.Alternant)) {
                & $accorder 'Affectations' $a.IdHNCS $compteAlt[[string]$a.Alternant] $lecteur
            }
        }
        foreach ($l in @($script:Data['Livrables'])) {
            if ($null -eq $l) { continue }
            $proprietaire = Resolve-Persona ([string]$l.Proprietaire)
            if ($compteAlt.Values -contains $proprietaire) { & $accorder 'Livrables' $l.IdHNCS $proprietaire $nomCSS }
        }
        foreach ($cr in @($script:Data['ComptesRendus'])) {
            if ($null -eq $cr) { continue }
            if ($compteAlt.ContainsKey([string]$cr.Alternant)) { & $accorder 'ComptesRendus' $cr.IdHNCS $compteAlt[[string]$cr.Alternant] $nomCSS }
            if ($cr.PSObject.Properties['Valideur'] -and $cr.Valideur) { & $accorder 'ComptesRendus' $cr.IdHNCS (Resolve-Persona ([string]$cr.Valideur)) $nomCSS }
        }
        foreach ($co in @($script:Data['CommunicationsRD'])) {
            if ($null -eq $co) { continue }
            $auteur = Resolve-Persona ([string]$co.Auteur)
            if ($compteAlt.Values -contains $auteur) { & $accorder 'CommunicationsRD' $co.IdHNCS $auteur $nomCSS }
        }
        $compteRef = @{}
        foreach ($r in @($script:Data['Referents'])) { if ($r) { $compteRef[[string]$r.IdHNCS] = Resolve-Persona ([string]$r.Compte) } }
        $champ = { param($o, [string]$n) if ($o.PSObject.Properties[$n] -and $o.$n) { return [string]$o.$n } return '' }
        foreach ($a in @($script:Data['Alternants'])) {
            if ($null -eq $a) { continue }
            $refs = @()
            $rp = & $champ $a 'ReferentPrincipal'
            if ($rp -and $compteRef.ContainsKey($rp)) { $refs += $compteRef[$rp] }
            foreach ($f in @($script:Data['Affectations'])) {
                $rf = & $champ $f 'Referent'
                if ($f -and [string]$f.Alternant -eq [string]$a.IdHNCS -and $rf -and $compteRef.ContainsKey($rf)) { $refs += $compteRef[$rf] }
            }
            foreach ($u in ($refs | Select-Object -Unique)) { & $accorder 'Alternants' $a.IdHNCS $u $lecteur }
        }
        foreach ($ac in @($script:Data['ActionsIntegration'])) {
            if ($ac -and (& $champ $ac 'Responsable')) { & $accorder 'ActionsIntegration' $ac.IdHNCS (Resolve-Persona ([string]$ac.Responsable)) $nomCSS }
        }
        foreach ($b in @($script:Data['BilansAlternance'])) {
            $rb = & $champ $b 'Referent'
            if ($b -and $rb -and $compteRef.ContainsKey($rb)) { & $accorder 'BilansAlternance' $b.IdHNCS $compteRef[$rb] $nomCSS }
        }
        foreach ($mo in @($script:Data['RegistreModeles'])) {
            if ($mo -and (& $champ $mo 'Proprietaire')) { & $accorder 'RegistreModeles' $mo.IdHNCS (Resolve-Persona ([string]$mo.Proprietaire)) $nomCSS }
        }
        foreach ($e in @($script:Data['Entretiens'])) {
            if ($null -eq $e -or -not $e.PSObject.Properties['Participants']) { continue }
            foreach ($pt in @($e.Participants)) { & $accorder 'Entretiens' $e.IdHNCS (Resolve-Persona ([string]$pt)) $lecteur }
        }
        Write-Warning 'Les permissions de dossiers (Recrutement, Administration, SuiviAlternants, LivrablesRD, ModelesRD) ne sont pas émulées : elles sont posées par les flux PA-01, PA-02, PA-04, PA-05 et PA-00F (ou par la procédure manuelle du lot 1, docs/exploitation.md).'
    }
}

#endregion

Write-Etape 'Bilan'
$bilan = foreach ($n in ($script:Stats.Keys | Sort-Object)) {
    [pscustomobject]@{ Liste = $n; Cree = $script:Stats[$n].Cree; MisAJour = $script:Stats[$n].MisAJour; Supprime = $script:Stats[$n].Supprime; Erreur = $script:Stats[$n].Erreur }
}
$bilan | Format-Table -AutoSize | Out-String | Write-Host
$erreurs = 0
foreach ($b in @($bilan)) { if ($b) { $erreurs += $b.Erreur } }
if ($erreurs -gt 0) { Write-Error "$erreurs élément(s) en erreur : voir les avertissements ci-dessus." }
