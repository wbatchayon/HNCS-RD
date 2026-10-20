<#
.SYNOPSIS
    Module de provisionnement SharePoint du système de suivi R&D HNCS (HNCS-RD).

.DESCRIPTION
    Fonctions réutilisables, idempotentes et pilotées par le modèle machine
    provisioning/model/model.generated.json (généré depuis spec.md par tools/spec_extract.py).

    Aucune liste, colonne, vue, groupe ou permission n'est codé en dur : tout est lu dans le modèle.
    Les seules constantes du module sont des conventions techniques documentées dans la spec
    (§ 2.2 : lookups affichant IdHNCS ; § 7.2 : site G_PROP = FC, autres groupes = R ;
    brief Teams : canaux de l'équipe).

    Les fonctions « pures » (Get-HNCSRDModel, ConvertTo-HNCSRDCaml, ConvertTo-HNCSRDFieldXml,
    Compare-HNCSRDFieldSchema, ConvertTo-HNCSRDValidationFormula, Get-HNCSRDVersioningSpec,
    Get-HNCSRDAttributionsAttendues, Get-HNCSRDNavigationPlan, Resolve-HNCSRDMarqueurs) ne
    dépendent pas de PnP.PowerShell et fonctionnent sous Windows PowerShell 5.1 (tests hors ligne).
    Les autres fonctions exigent PowerShell 7.4+ et PnP.PowerShell 2.12+ et une connexion
    établie par Connect-HNCSRD.

    Mode simulation : Set-HNCSRDSimulation -Actif $true (positionné par Deploy-HNCSRD.ps1 -WhatIf),
    ou -WhatIf sur une fonction Ensure-*/Set-* : aucune écriture n'est faite, chaque modification
    prévue est journalisée avec le statut « Simule ».

.NOTES
    Le verbe « Ensure » n'est pas un verbe approuvé PowerShell : importer avec -DisableNameChecking.
#>

Set-StrictMode -Version 2.0

#region État du module ---------------------------------------------------------------------------

$script:HNCSRD = @{
    LogPath        = $null
    Simulation     = $false
    EtapeCourante  = 'General'
    Resultats      = New-Object System.Collections.Generic.List[object]
    Modele         = $null
    ModelePath     = $null
    CacheLookup    = @{}
    CacheRoles     = $null
}

# Convention spec § 2.2 : les colonnes de recherche affichent toujours IdHNCS de la cible.
$script:ChampAffichageLookup = 'IdHNCS'

# Correspondance nom Windows du fuseau (modèle) -> identifiant SharePoint.
$script:FuseauxSharePoint = @{ 'Romance Standard Time' = 3 }

# Colonnes ajoutées en tête des vues de bibliothèque (specs/sharepoint-vues.md, « Rendu », v1.2.0).
$script:ColonnesTeteBibliotheque = @('DocIcon', 'LinkFilename')

# Équipe Teams optionnelle (brief de provisionnement ; ce n'est pas le référentiel).
$script:CanauxTeams = @('Comité R&D', 'Alternants')

# En-têtes de navigation hors domaines métier.
$script:EnteteBibliotheques = 'Bibliothèques'

$script:EnteteSansLien = 'http://linkless.header/'

#endregion

#region Journalisation et résultats --------------------------------------------------------------

function Start-HNCSRDLog {
    <#
    .SYNOPSIS
        Initialise le journal (fichier UTF-8) et réinitialise les résultats.
    .PARAMETER Path
        Chemin complet du fichier journal (le dossier est créé si besoin).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Path)
    $dossier = Split-Path -Parent $Path
    if ($dossier -and -not (Test-Path -LiteralPath $dossier)) {
        [void][System.IO.Directory]::CreateDirectory($dossier)
    }
    [System.IO.File]::WriteAllText($Path, '', (New-Object System.Text.UTF8Encoding($true)))
    $script:HNCSRD.LogPath = $Path
    $script:HNCSRD.Resultats.Clear()
    $script:HNCSRD.EtapeCourante = 'General'
}

function Write-HNCSRDLog {
    <#
    .SYNOPSIS
        Écrit une ligne horodatée à l'écran et dans le journal.
    .PARAMETER Niveau
        Info, Succes, Avertissement, Erreur, Simulation ou Detail.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)][AllowEmptyString()][string]$Message,
        [ValidateSet('Info', 'Succes', 'Avertissement', 'Erreur', 'Simulation', 'Detail')][string]$Niveau = 'Info'
    )
    $ligne = '{0} [{1}] [{2}] {3}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Niveau.ToUpperInvariant(), $script:HNCSRD.EtapeCourante, $Message
    $couleur = 'Gray'
    switch ($Niveau) {
        'Succes'        { $couleur = 'Green' }
        'Avertissement' { $couleur = 'Yellow' }
        'Erreur'        { $couleur = 'Red' }
        'Simulation'    { $couleur = 'Cyan' }
        'Detail'        { $couleur = 'DarkGray' }
    }
    Write-Host $ligne -ForegroundColor $couleur
    if ($script:HNCSRD.LogPath) {
        [System.IO.File]::AppendAllText($script:HNCSRD.LogPath, $ligne + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))
    }
}

function Set-HNCSRDEtape {
    <#
    .SYNOPSIS
        Déclare l'étape courante (utilisée par le journal et le résumé).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Nom)
    $script:HNCSRD.EtapeCourante = $Nom
}

function Add-HNCSRDResultat {
    <#
    .SYNOPSIS
        Enregistre le résultat d'une opération (Cree, MisAJour, Inchange, Retire, Simule, Avertissement, Erreur).
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidateSet('Cree', 'MisAJour', 'Inchange', 'Retire', 'Simule', 'Avertissement', 'Erreur')][string]$Statut,
        [Parameter(Mandatory)][string]$Cible,
        [string]$Message = ''
    )
    $script:HNCSRD.Resultats.Add([pscustomobject]@{
            Horodatage = Get-Date
            Etape      = $script:HNCSRD.EtapeCourante
            Statut     = $Statut
            Cible      = $Cible
            Message    = $Message
        })
    $texte = '{0} : {1}' -f $Statut, $Cible
    if ($Message) { $texte = $texte + ' - ' + $Message }
    $niveau = 'Info'
    switch ($Statut) {
        'Cree'          { $niveau = 'Succes' }
        'MisAJour'      { $niveau = 'Succes' }
        'Retire'        { $niveau = 'Avertissement' }
        'Inchange'      { $niveau = 'Detail' }
        'Simule'        { $niveau = 'Simulation' }
        'Avertissement' { $niveau = 'Avertissement' }
        'Erreur'        { $niveau = 'Erreur' }
    }
    Write-HNCSRDLog -Message $texte -Niveau $niveau
}

function Get-HNCSRDResultats {
    <#
    .SYNOPSIS
        Retourne la liste brute des résultats enregistrés depuis Start-HNCSRDLog.
    #>
    [CmdletBinding()]
    param()
    return $script:HNCSRD.Resultats.ToArray()
}

function Get-HNCSRDResume {
    <#
    .SYNOPSIS
        Retourne, par étape, le nombre d'éléments créés / mis à jour / inchangés / retirés / simulés / avertissements / erreurs.
    #>
    [CmdletBinding()]
    param()
    $resume = New-Object System.Collections.Generic.List[object]
    $etapes = New-Object System.Collections.Generic.List[string]
    foreach ($r in $script:HNCSRD.Resultats) { if (-not $etapes.Contains($r.Etape)) { $etapes.Add($r.Etape) } }
    foreach ($e in $etapes) {
        $lignes = @($script:HNCSRD.Resultats | Where-Object { $_.Etape -eq $e })
        $resume.Add([pscustomobject]@{
                Etape         = $e
                Cree          = @($lignes | Where-Object { $_.Statut -eq 'Cree' }).Count
                MisAJour      = @($lignes | Where-Object { $_.Statut -eq 'MisAJour' }).Count
                Inchange      = @($lignes | Where-Object { $_.Statut -eq 'Inchange' }).Count
                Retire        = @($lignes | Where-Object { $_.Statut -eq 'Retire' }).Count
                Simule        = @($lignes | Where-Object { $_.Statut -eq 'Simule' }).Count
                Avertissement = @($lignes | Where-Object { $_.Statut -eq 'Avertissement' }).Count
                Erreur        = @($lignes | Where-Object { $_.Statut -eq 'Erreur' }).Count
            })
    }
    return $resume.ToArray()
}

function Set-HNCSRDSimulation {
    <#
    .SYNOPSIS
        Active ou désactive le mode simulation (aucune écriture SharePoint).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][bool]$Actif)
    $script:HNCSRD.Simulation = $Actif
}

function Test-HNCSRDSimulation {
    <#
    .SYNOPSIS
        Indique si les écritures doivent être simulées (mode simulation du module ou -WhatIf de l'appelant).
    #>
    [CmdletBinding()]
    param()
    if ($script:HNCSRD.Simulation) { return $true }
    # $WhatIfPreference est hérité dynamiquement de la fonction appelante du module (paramètre -WhatIf).
    $wi = Get-Variable -Name WhatIfPreference -ValueOnly -ErrorAction SilentlyContinue
    return [bool]$wi
}

#endregion

#region Modèle et configuration (fonctions pures) ------------------------------------------------

function Get-HNCSRDModel {
    <#
    .SYNOPSIS
        Charge le modèle machine généré depuis la spec (model.generated.json).
    .DESCRIPTION
        Le modèle est mis en cache pour la session. Vérifie la présence de specVersion et des sections
        attendues. Compatible Windows PowerShell 5.1 (aucune dépendance PnP).
    .PARAMETER Path
        Chemin du modèle. Par défaut : provisioning/model/model.generated.json (relatif au module).
    .PARAMETER Force
        Recharge le fichier même s'il est en cache.
    .EXAMPLE
        $modele = Get-HNCSRDModel
        $modele.objects | Select-Object name, kind, lot
    #>
    [CmdletBinding()]
    param([string]$Path, [switch]$Force)
    if (-not $Path) { $Path = Join-Path (Split-Path -Parent $PSScriptRoot) 'model/model.generated.json' }
    if (-not (Test-Path -LiteralPath $Path)) { throw "Modèle introuvable : $Path (exécuter « python tools/spec_extract.py »)." }
    $complet = (Resolve-Path -LiteralPath $Path).ProviderPath
    if (-not $Force -and $script:HNCSRD.Modele -and $script:HNCSRD.ModelePath -eq $complet) { return $script:HNCSRD.Modele }
    $json = [System.IO.File]::ReadAllText($complet, [System.Text.Encoding]::UTF8)
    $modele = $json | ConvertFrom-Json
    if (-not ($modele.PSObject.Properties.Name -contains 'specVersion') -or -not $modele.specVersion) {
        throw "Le modèle $complet ne contient pas « specVersion »."
    }
    foreach ($section in @('site', 'enums', 'objects', 'groups', 'roleToGroupCode', 'permissionLevels', 'matrix', 'transitions', 'views', 'parameters', 'seeds')) {
        if (-not ($modele.PSObject.Properties.Name -contains $section)) { throw "Section « $section » absente du modèle $complet." }
    }
    $script:HNCSRD.Modele = $modele
    $script:HNCSRD.ModelePath = $complet
    $script:HNCSRD.CacheLookup = @{}
    return $modele
}

function Get-HNCSRDConfig {
    <#
    .SYNOPSIS
        Charge et contrôle la configuration du tenant (provisioning/config/tenant.json).
    .DESCRIPTION
        Contrat partagé avec les autres lots : voir provisioning/config/tenant.sample.json.
    .PARAMETER Path
        Chemin du fichier. Par défaut : provisioning/config/tenant.json (relatif au module).
    #>
    [CmdletBinding()]
    param([string]$Path)
    if (-not $Path) { $Path = Join-Path (Split-Path -Parent $PSScriptRoot) 'config/tenant.json' }
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Configuration introuvable : $Path. Copier provisioning/config/tenant.sample.json en tenant.json et le compléter."
    }
    $json = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $Path).ProviderPath, [System.Text.Encoding]::UTF8)
    $config = $json | ConvertFrom-Json
    $manquants = @()
    foreach ($cle in @('TenantName', 'TenantAdminUrl', 'SiteUrl', 'SiteOwner', 'PnPClientId', 'ServiceAccountEmail', 'Parametres')) {
        if (-not ($config.PSObject.Properties.Name -contains $cle) -or $null -eq $config.$cle -or ([string]$config.$cle) -eq '') { $manquants += $cle }
    }
    if ($manquants.Count -gt 0) { throw ("Clés obligatoires absentes ou vides dans {0} : {1}" -f $Path, ($manquants -join ', ')) }
    if ($config.SiteUrl -notmatch '^https://[^/]+\.sharepoint\.com/sites/[^/]+/?$') { throw "SiteUrl invalide : $($config.SiteUrl)" }
    if ($config.TenantAdminUrl -notmatch '^https://[^/]+-admin\.sharepoint\.com/?$') { throw "TenantAdminUrl invalide : $($config.TenantAdminUrl)" }
    $guid = [guid]::Empty
    if (-not [guid]::TryParse([string]$config.PnPClientId, [ref]$guid)) { throw "PnPClientId n'est pas un GUID : $($config.PnPClientId)" }
    foreach ($cle in @('CertificatePath', 'CertificateThumbprint')) {
        if (-not ($config.PSObject.Properties.Name -contains $cle)) { $config | Add-Member -NotePropertyName $cle -NotePropertyValue '' }
    }
    if (-not ($config.PSObject.Properties.Name -contains 'Teams') -or $null -eq $config.Teams) {
        $config | Add-Member -NotePropertyName 'Teams' -NotePropertyValue ([pscustomobject]@{ Creer = $false; NomEquipe = 'HNCS R&D' }) -Force
    }
    return $config
}

function Get-HNCSRDObject {
    <#
    .SYNOPSIS
        Retourne la définition d'une liste ou bibliothèque du modèle par son nom interne.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Name, $Model)
    if (-not $Model) { $Model = Get-HNCSRDModel }
    $o = @($Model.objects | Where-Object { $_.name -eq $Name })
    if ($o.Count -ne 1) { throw "Objet « $Name » absent du modèle." }
    return $o[0]
}

function Get-HNCSRDObjects {
    <#
    .SYNOPSIS
        Retourne les objets (listes et bibliothèques) du modèle de lot inférieur ou égal à -Lot (déploiement cumulatif).
    .PARAMETER Kind
        Filtre facultatif : list ou library.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][int]$Lot, $Model, [ValidateSet('list', 'library')][string]$Kind)
    if (-not $Model) { $Model = Get-HNCSRDModel }
    $r = @($Model.objects | Where-Object { [int]$_.lot -le $Lot })
    if ($Kind) { $r = @($r | Where-Object { $_.kind -eq $Kind }) }
    return $r
}

function Test-HNCSRDLookupType {
    <#
    .SYNOPSIS
        Vrai si le type de colonne du modèle est Lookup ou LookupMulti.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Type)
    return ($Type -eq 'Lookup' -or $Type -eq 'LookupMulti')
}

function Get-HNCSRDColumns {
    <#
    .SYNOPSIS
        Retourne les colonnes d'un objet déployables pour le lot (colonnes sans « lot » ou de lot <= -Lot).
    .PARAMETER Lookups
        $true : uniquement les lookups ; $false : uniquement les autres colonnes ; absent : toutes.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Object, [Parameter(Mandatory)][int]$Lot, $Lookups)
    $r = @($Object.columns | Where-Object { $null -eq $_.lot -or [int]$_.lot -le $Lot })
    if ($null -ne $Lookups) {
        if ([bool]$Lookups) { $r = @($r | Where-Object { Test-HNCSRDLookupType -Type $_.type }) }
        else { $r = @($r | Where-Object { -not (Test-HNCSRDLookupType -Type $_.type) }) }
    }
    return $r
}

function Get-HNCSRDColumnTypes {
    <#
    .SYNOPSIS
        Table nom interne -> type du modèle pour un objet (Title inclus), restreinte au lot.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Object, [int]$Lot = 5)
    $types = @{ 'Title' = 'Text' }
    foreach ($c in (Get-HNCSRDColumns -Object $Object -Lot $Lot)) { $types[$c.name] = [string]$c.type }
    return $types
}

function Get-HNCSRDListUrl {
    <#
    .SYNOPSIS
        URL relative au site d'une liste (« Lists/<Nom> ») ou d'une bibliothèque (« <Nom> »).
    .DESCRIPTION
        Convention spec § 2.2 : nom interne = URL. Les listes sont créées sous /Lists/ (usage SharePoint),
        les bibliothèques à la racine du site.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Name, $Model)
    $o = Get-HNCSRDObject -Name $Name -Model $Model
    if ($o.kind -eq 'library') { return $o.name }
    return ('Lists/' + $o.name)
}

function Get-HNCSRDGroupName {
    <#
    .SYNOPSIS
        Nom exact du groupe SharePoint pour un code (G_PROP, G_DRD…).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Code, $Model)
    if (-not $Model) { $Model = Get-HNCSRDModel }
    $g = @($Model.groups | Where-Object { $_.code -eq $Code })
    if ($g.Count -ne 1) { throw "Groupe « $Code » absent du modèle." }
    return [string]$g[0].name
}

function Get-HNCSRDOwnerGroupCode {
    <#
    .SYNOPSIS
        Code du groupe propriétaire (rôle PROPRIETAIRE du modèle, soit G_PROP).
    #>
    [CmdletBinding()]
    param($Model)
    if (-not $Model) { $Model = Get-HNCSRDModel }
    return [string]$Model.roleToGroupCode.PROPRIETAIRE
}

function Get-HNCSRDEnumValues {
    <#
    .SYNOPSIS
        Valeurs ordonnées d'une énumération du modèle.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Code, $Model)
    if (-not $Model) { $Model = Get-HNCSRDModel }
    if (-not ($Model.enums.PSObject.Properties.Name -contains $Code)) { throw "Énumération « $Code » absente du modèle." }
    return @($Model.enums.$Code)
}

function Resolve-HNCSRDMarqueurs {
    <#
    .SYNOPSIS
        Remplace les marqueurs <Nom> d'une valeur par Config.Parametres.Nom.
    .OUTPUTS
        PSCustomObject { Valeur ; NonResolus (noms des marqueurs absents de la configuration) }.
    #>
    [CmdletBinding()]
    param([AllowNull()][AllowEmptyString()][string]$Valeur, [Parameter(Mandatory)]$Config)
    $nonResolus = @()
    if ($null -eq $Valeur) { return [pscustomobject]@{ Valeur = $null; NonResolus = $nonResolus } }
    $resultat = $Valeur
    foreach ($m in [regex]::Matches($Valeur, '<([A-Za-z][A-Za-z0-9]*)>')) {
        $nom = $m.Groups[1].Value
        $params = $Config.Parametres
        if ($params -and ($params.PSObject.Properties.Name -contains $nom)) {
            $resultat = $resultat.Replace($m.Value, [string]$params.$nom)
        }
        else { $nonResolus += $nom }
    }
    return [pscustomobject]@{ Valeur = $resultat; NonResolus = $nonResolus }
}

function Get-HNCSRDPropriete {
    <#
    .SYNOPSIS
        Valeur d'une propriété facultative d'un objet du modèle ($null si absente ; compatible StrictMode).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Objet, [Parameter(Mandatory)][string]$Nom)
    if ($null -eq $Objet) { return $null }
    if ($Objet.PSObject.Properties.Name -contains $Nom) { return $Objet.$Nom }
    return $null
}

function ConvertTo-HNCSRDXmlText {
    <#
    .SYNOPSIS
        Échappe une valeur pour un attribut ou un texte XML.
    #>
    [CmdletBinding()]
    param([AllowNull()][AllowEmptyString()][string]$Valeur)
    if ($null -eq $Valeur) { return '' }
    # Échappement XML minimal (texte et attributs entre guillemets) ; l'apostrophe reste littérale.
    return $Valeur.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;').Replace('"', '&quot;')
}

function Format-HNCSRDNombre {
    <#
    .SYNOPSIS
        Formate un nombre en culture invariante (sans décimales inutiles).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Valeur)
    return ([double]$Valeur).ToString('0.############', [System.Globalization.CultureInfo]::InvariantCulture)
}

function ConvertTo-HNCSRDBoolean {
    <#
    .SYNOPSIS
        Convertit Oui/Non (spec) en booléen.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Valeur)
    switch ($Valeur.Trim()) {
        'Oui' { return $true }
        'Non' { return $false }
    }
    throw "Valeur booléenne invalide (attendu Oui / Non) : « $Valeur »"
}

#endregion

#region Génération : XML de champ, CAML, formules, versioning, matrice, navigation (pures) -------

function Get-HNCSRDDefaultValue {
    <#
    .SYNOPSIS
        Valeur par défaut SharePoint (chaîne) d'une colonne du modèle, ou $null.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Column, $Model)
    if ($null -eq $Column.default -or [string]$Column.default -eq '') { return $null }
    $d = [string]$Column.default
    switch ([string]$Column.type) {
        'Boolean' { if (ConvertTo-HNCSRDBoolean -Valeur $d) { return '1' } else { return '0' } }
        'Number' { return (Format-HNCSRDNombre -Valeur ([double]::Parse($d, [System.Globalization.CultureInfo]::InvariantCulture))) }
        'Choice' {
            $valeurs = Get-HNCSRDEnumValues -Code $Column.enum -Model $Model
            if (-not ($valeurs -contains $d)) { throw "Défaut « $d » absent de l'énumération $($Column.enum) (colonne $($Column.name))." }
            return $d
        }
        'Text' { return $d }
        default { throw "Valeur par défaut non gérée pour le type $($Column.type) (colonne $($Column.name))." }
    }
}

function ConvertTo-HNCSRDFieldXml {
    <#
    .SYNOPSIS
        Génère le XML de définition SharePoint (CAML Field) d'une colonne du modèle.
    .DESCRIPTION
        Name et StaticName = nom interne (ASCII). Par défaut DisplayName = libellé ; avec
        -DisplayNameInterne, DisplayName = nom interne (création : garantit le nom interne, le libellé
        est appliqué ensuite). Choix ordonnés depuis l'énumération, défauts (Boolean Oui/Non -> 1/0),
        Required, Indexed, EnforceUniqueValues (+ Indexed), Min/Max/Decimals, Date = DateOnly,
        User = PeopleOnly, URL = Hyperlink, Lookup ShowField="IdHNCS", LookupMulti Mult="TRUE".
        « hidden » = masquée des formulaires (ShowInNewForm/EditForm/DisplayForm = FALSE).
    .PARAMETER LookupListId
        GUID de la liste cible (obligatoire pour Lookup / LookupMulti).
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]$Column,
        [string]$LookupListId,
        [switch]$DisplayNameInterne,
        $Model
    )
    if (-not $Model) { $Model = Get-HNCSRDModel }
    $nom = [string]$Column.name
    if ($nom -notmatch '^[A-Za-z][A-Za-z0-9]{0,31}$') { throw "Nom interne invalide (PascalCase ASCII <= 32) : $nom" }
    $attrs = New-Object System.Collections.Specialized.OrderedDictionary
    $enfants = ''
    $type = [string]$Column.type
    switch ($type) {
        'Text' { $attrs['Type'] = 'Text'; $attrs['MaxLength'] = '255' }
        'Note' {
            $attrs['Type'] = 'Note'; $attrs['NumLines'] = '6'; $attrs['RichText'] = 'FALSE'; $attrs['RichTextMode'] = 'Compatible'
            # « appendonly » (spec § 2.4, v1.1.0) : ajout uniquement, historique conservé par le versioning.
            if ([bool](Get-HNCSRDPropriete -Objet $Column -Nom 'appendOnly')) { $attrs['AppendOnly'] = 'TRUE' } else { $attrs['AppendOnly'] = 'FALSE' }
        }
        'Choice' { $attrs['Type'] = 'Choice'; $attrs['Format'] = 'Dropdown'; $attrs['FillInChoice'] = 'FALSE' }
        'MultiChoice' { $attrs['Type'] = 'MultiChoice'; $attrs['FillInChoice'] = 'FALSE' }
        'Number' { $attrs['Type'] = 'Number' }
        'Boolean' { $attrs['Type'] = 'Boolean' }
        'Date' { $attrs['Type'] = 'DateTime'; $attrs['Format'] = 'DateOnly' }
        'DateTime' { $attrs['Type'] = 'DateTime'; $attrs['Format'] = 'DateTime' }
        'User' { $attrs['Type'] = 'User'; $attrs['List'] = 'UserInfo'; $attrs['ShowField'] = 'ImnName'; $attrs['UserSelectionMode'] = 'PeopleOnly'; $attrs['UserSelectionScope'] = '0' }
        'UserMulti' { $attrs['Type'] = 'UserMulti'; $attrs['Mult'] = 'TRUE'; $attrs['List'] = 'UserInfo'; $attrs['ShowField'] = 'ImnName'; $attrs['UserSelectionMode'] = 'PeopleOnly'; $attrs['UserSelectionScope'] = '0' }
        'URL' { $attrs['Type'] = 'URL'; $attrs['Format'] = 'Hyperlink' }
        'Lookup' { $attrs['Type'] = 'Lookup' }
        'LookupMulti' { $attrs['Type'] = 'LookupMulti'; $attrs['Mult'] = 'TRUE' }
        default { throw "Type de colonne inconnu : $type (colonne $nom)" }
    }
    if (Test-HNCSRDLookupType -Type $type) {
        if (-not $LookupListId) { throw "LookupListId obligatoire pour la colonne de recherche $nom." }
        $g = [guid]::Empty
        if (-not [guid]::TryParse($LookupListId, [ref]$g)) { throw "LookupListId invalide pour $nom : $LookupListId" }
        $attrs['List'] = '{' + $g.ToString() + '}'
        $attrs['ShowField'] = $script:ChampAffichageLookup
    }
    $attrs['Name'] = $nom
    $attrs['StaticName'] = $nom
    if ($DisplayNameInterne) { $attrs['DisplayName'] = $nom } else { $attrs['DisplayName'] = [string]$Column.label }
    if ($Column.required) { $attrs['Required'] = 'TRUE' } else { $attrs['Required'] = 'FALSE' }
    if ($Column.indexed -or $Column.unique) {
        if (@('Note', 'MultiChoice', 'LookupMulti', 'UserMulti') -contains $type) { throw "Indexation impossible sur une colonne $type ($nom)." }
        $attrs['Indexed'] = 'TRUE'
    }
    if ($Column.unique) { $attrs['EnforceUniqueValues'] = 'TRUE' }
    if ($type -eq 'Number') {
        if ($null -ne $Column.min) { $attrs['Min'] = Format-HNCSRDNombre -Valeur $Column.min }
        if ($null -ne $Column.max) { $attrs['Max'] = Format-HNCSRDNombre -Valeur $Column.max }
        if ($null -ne $Column.decimals) { $attrs['Decimals'] = [string][int]$Column.decimals }
    }
    $description = [string]$Column.description
    if ($description) {
        $description = $description.Replace('`', '')
        if ($description.Length -gt 255) { $description = $description.Substring(0, 255) }
        $attrs['Description'] = $description
    }
    if ($Column.hidden) {
        $attrs['ShowInNewForm'] = 'FALSE'
        $attrs['ShowInEditForm'] = 'FALSE'
        $attrs['ShowInDisplayForm'] = 'FALSE'
    }
    if ($type -eq 'Choice' -or $type -eq 'MultiChoice') {
        if (-not $Column.enum) { throw "Énumération absente pour la colonne de choix $nom." }
        $sb = New-Object System.Text.StringBuilder
        [void]$sb.Append('<CHOICES>')
        foreach ($v in (Get-HNCSRDEnumValues -Code $Column.enum -Model $Model)) { [void]$sb.Append('<CHOICE>' + (ConvertTo-HNCSRDXmlText $v) + '</CHOICE>') }
        [void]$sb.Append('</CHOICES>')
        $enfants += $sb.ToString()
    }
    $defaut = Get-HNCSRDDefaultValue -Column $Column -Model $Model
    if ($null -ne $defaut) { $enfants += '<Default>' + (ConvertTo-HNCSRDXmlText $defaut) + '</Default>' }
    $sbA = New-Object System.Text.StringBuilder
    [void]$sbA.Append('<Field')
    foreach ($k in $attrs.Keys) { [void]$sbA.Append(' ' + $k + '="' + (ConvertTo-HNCSRDXmlText ([string]$attrs[$k])) + '"') }
    if ($enfants) { [void]$sbA.Append('>' + $enfants + '</Field>') } else { [void]$sbA.Append(' />') }
    return $sbA.ToString()
}

function Get-HNCSRDXmlAttribut {
    # Lecture d'un attribut avec valeur sémantique par défaut (usage interne).
    param([System.Xml.XmlElement]$Element, [string]$Nom, [string]$ParDefaut)
    if ($Element.HasAttribute($Nom)) { return $Element.GetAttribute($Nom) }
    return $ParDefaut
}

function Compare-HNCSRDFieldSchema {
    <#
    .SYNOPSIS
        Compare le SchemaXml d'un champ SharePoint au XML attendu (ConvertTo-HNCSRDFieldXml).
    .DESCRIPTION
        Fonction pure. Retourne la liste des écarts : { Propriete ; Attendu ; Constate ; Corrigeable ; Mode }.
        Mode : « Base » (propriété CSOM Field), « Formulaire » (SetShowIn*Form), « Schema » (patch SchemaXml)
        ou « Aucun » (non corrigeable : type, liste cible de recherche, nom interne).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$SchemaActuel, [Parameter(Mandatory)][string]$SchemaAttendu)
    $act = ([xml]$SchemaActuel).DocumentElement
    $att = ([xml]$SchemaAttendu).DocumentElement
    $ecarts = New-Object System.Collections.Generic.List[object]
    $ajout = {
        param($p, $a, $c, $mode)
        $ecarts.Add([pscustomobject]@{ Propriete = $p; Attendu = $a; Constate = $c; Corrigeable = ($mode -ne 'Aucun'); Mode = $mode })
    }
    $typeAtt = $att.GetAttribute('Type')
    $typeAct = $act.GetAttribute('Type')
    if ($typeAtt -ne $typeAct) { & $ajout 'Type' $typeAtt $typeAct 'Aucun'; return $ecarts.ToArray() }
    if ($att.GetAttribute('StaticName') -ne (Get-HNCSRDXmlAttribut $act 'StaticName' $act.GetAttribute('Name'))) {
        & $ajout 'NomInterne' $att.GetAttribute('StaticName') $act.GetAttribute('StaticName') 'Aucun'
    }
    $base = @(
        @{ N = 'DisplayName'; D = '' }, @{ N = 'Required'; D = 'FALSE' }, @{ N = 'Indexed'; D = 'FALSE' },
        @{ N = 'EnforceUniqueValues'; D = 'FALSE' }, @{ N = 'Description'; D = '' }
    )
    foreach ($b in $base) {
        $va = Get-HNCSRDXmlAttribut $att $b.N $b.D
        $vc = Get-HNCSRDXmlAttribut $act $b.N $b.D
        if ($b.D -eq 'FALSE') { $va = $va.ToUpperInvariant(); $vc = $vc.ToUpperInvariant() }
        if ($va -cne $vc) { & $ajout $b.N $va $vc 'Base' }
    }
    foreach ($f in @('ShowInNewForm', 'ShowInEditForm', 'ShowInDisplayForm')) {
        $va = (Get-HNCSRDXmlAttribut $att $f 'TRUE').ToUpperInvariant()
        $vc = (Get-HNCSRDXmlAttribut $act $f 'TRUE').ToUpperInvariant()
        if ($va -ne $vc) { & $ajout $f $va $vc 'Formulaire' }
    }
    if ($typeAtt -eq 'Lookup' -or $typeAtt -eq 'LookupMulti') {
        $la = Get-HNCSRDXmlAttribut $att 'List' ''
        $lc = Get-HNCSRDXmlAttribut $act 'List' ''
        $ga = [guid]::Empty; $gc = [guid]::Empty
        $okA = [guid]::TryParse($la, [ref]$ga); $okC = [guid]::TryParse($lc, [ref]$gc)
        if (-not ($okA -and $okC -and $ga -eq $gc)) { & $ajout 'List' $la $lc 'Aucun' }
    }
    $schema = @(
        @{ N = 'Format'; D = '' }, @{ N = 'Min'; D = '' }, @{ N = 'Max'; D = '' }, @{ N = 'Decimals'; D = '' },
        @{ N = 'ShowField'; D = '' }, @{ N = 'Mult'; D = 'FALSE' }, @{ N = 'UserSelectionMode'; D = '' }, @{ N = 'AppendOnly'; D = 'FALSE' }
    )
    foreach ($s in $schema) {
        $va = Get-HNCSRDXmlAttribut $att $s.N $s.D
        $vc = Get-HNCSRDXmlAttribut $act $s.N $s.D
        if ($s.N -eq 'Format' -and $typeAtt -eq 'DateTime' -and $vc -eq '') { $vc = 'DateTime' }
        if ($s.N -eq 'Format' -and $typeAtt -eq 'URL' -and $vc -eq '') { $vc = 'Hyperlink' }
        if ($s.N -eq 'Format' -and $typeAtt -eq 'Choice' -and $vc -eq '') { $vc = 'Dropdown' }
        if ($s.N -eq 'UserSelectionMode') { if ($vc -eq '0') { $vc = 'PeopleOnly' } elseif ($vc -eq '1') { $vc = 'PeopleAndGroups' } }
        if ($s.N -eq 'ShowField' -and ($typeAtt -eq 'User' -or $typeAtt -eq 'UserMulti')) { continue }
        if ($s.N -eq 'Mult' -or $s.N -eq 'AppendOnly') { $va = $va.ToUpperInvariant(); $vc = $vc.ToUpperInvariant() }
        if ($s.N -eq 'AppendOnly' -and $typeAtt -ne 'Note') { continue }
        if (($s.N -eq 'Min' -or $s.N -eq 'Max') -and $va -ne '' -and $vc -ne '') {
            $da = [double]::Parse($va, [System.Globalization.CultureInfo]::InvariantCulture)
            $dc = 0.0
            if ([double]::TryParse($vc, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$dc) -and $da -eq $dc) { continue }
        }
        if ($va -cne $vc) { & $ajout $s.N $va $vc 'Schema' }
    }
    $choixA = @($att.SelectNodes('CHOICES/CHOICE') | ForEach-Object { $_.InnerText })
    $choixC = @($act.SelectNodes('CHOICES/CHOICE') | ForEach-Object { $_.InnerText })
    if (($choixA -join "`n") -cne ($choixC -join "`n")) { & $ajout 'CHOICES' ($choixA -join ' ; ') ($choixC -join ' ; ') 'Schema' }
    $defA = ''; $defC = ''
    $n = $att.SelectSingleNode('Default'); if ($n) { $defA = $n.InnerText }
    $n = $act.SelectSingleNode('Default'); if ($n) { $defC = $n.InnerText }
    if ($typeAtt -eq 'Number' -and $defA -ne '' -and $defC -ne '') {
        $x = 0.0
        if ([double]::TryParse($defC, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$x)) { $defC = Format-HNCSRDNombre -Valeur $x }
    }
    if ($defA -cne $defC) { & $ajout 'DefaultValue' $defA $defC 'Base' }
    return $ecarts.ToArray()
}

function ConvertTo-HNCSRDCamlValue {
    # Valeur CAML (<Value ...>) d'une condition de vue (usage interne).
    param([string]$Champ, [string]$Type, [string]$Valeur)
    if ($Valeur -match '^\[Moi\]$') {
        if ($Type -ne 'User' -and $Type -ne 'UserMulti') { throw "[Moi] n'est valable que sur une colonne personne ($Champ)." }
        return '<Value Type="Integer"><UserID Type="Integer" /></Value>'
    }
    if ($Valeur -match "^\[Aujourd['’]hui(?:\s*([+-])\s*(\d+))?\]$") {
        if ($Type -ne 'Date' -and $Type -ne 'DateTime') { throw "[Aujourd'hui] n'est valable que sur une colonne date ($Champ)." }
        $decalage = 0
        if ($Matches[1]) { $decalage = [int]$Matches[2]; if ($Matches[1] -eq '-') { $decalage = - $decalage } }
        if ($decalage -eq 0) { return '<Value Type="DateTime"><Today /></Value>' }
        return ('<Value Type="DateTime"><Today OffsetDays="{0}" /></Value>' -f $decalage)
    }
    switch ($Type) {
        'Boolean' {
            if (ConvertTo-HNCSRDBoolean -Valeur $Valeur) { return '<Value Type="Boolean">1</Value>' }
            return '<Value Type="Boolean">0</Value>'
        }
        'Number' {
            $d = [double]::Parse($Valeur, [System.Globalization.CultureInfo]::InvariantCulture)
            return '<Value Type="Number">' + (Format-HNCSRDNombre -Valeur $d) + '</Value>'
        }
        'Date' { return '<Value Type="DateTime">' + (ConvertTo-HNCSRDXmlText $Valeur) + '</Value>' }
        'DateTime' { return '<Value Type="DateTime" IncludeTimeValue="TRUE">' + (ConvertTo-HNCSRDXmlText $Valeur) + '</Value>' }
    }
    $camlType = $Type
    switch ($Type) {
        'UserMulti' { $camlType = 'User' }
        'LookupMulti' { $camlType = 'Lookup' }
    }
    return '<Value Type="' + $camlType + '">' + (ConvertTo-HNCSRDXmlText $Valeur) + '</Value>'
}

function Join-HNCSRDCamlAnd {
    # Combine des conditions CAML en <And> binaires imbriqués (usage interne).
    param([string[]]$Noeuds)
    $n = @($Noeuds | Where-Object { $_ })
    if ($n.Count -eq 0) { return '' }
    if ($n.Count -eq 1) { return $n[0] }
    $reste = Join-HNCSRDCamlAnd -Noeuds ($n[1..($n.Count - 1)])
    return '<And>' + $n[0] + $reste + '</And>'
}

function ConvertTo-HNCSRDCaml {
    <#
    .SYNOPSIS
        Convertit une vue du modèle (grammaire specs/sharepoint-vues.md) en définition CAML.
    .DESCRIPTION
        Fonction pure (aucune dépendance PnP). Opérateurs : = (Eq), <> (Neq), < (Lt), <= (Leq), > (Gt),
        >= (Geq), in (In ; Eq si une seule valeur), notin (chaîne de <Neq> combinés par <And> ; CAML
        SharePoint ne connaît pas <Not>), isnull (IsNull), isnotnull (IsNotNull). Valeurs spéciales :
        [Moi] -> <UserID/>, [Aujourd'hui±n] -> <Today OffsetDays="n"/>, booléens Oui/Non -> 1/0.
        Les conditions sont reliées par des <And> binaires correctement imbriqués.
        Rendu (specs/sharepoint-vues.md, v1.2.0) : dans une liste, Title est affiché sous la forme
        LinkTitle (titre cliquable) et une vue qui ne cite pas Title reçoit LinkTitle en première position ;
        dans une bibliothèque, DocIcon et LinkFilename sont ajoutés en tête. Le tri, le filtre et le
        regroupement utilisent les noms du modèle. Regroupements dépliés (Collapse = FALSE).
    .PARAMETER View
        Objet vue du modèle : { name ; default ; columns ; filter ; sort ; groupBy }.
    .PARAMETER ColumnTypes
        Table nom interne -> type du modèle (voir Get-HNCSRDColumnTypes).
    .PARAMETER ListKind
        list (défaut) ou library.
    .OUTPUTS
        PSCustomObject { Name ; Default ; ViewFields ; Where ; OrderBy ; GroupBy ; Query ; RowLimit ; Paged }.
        Query = contenu de <Query> (GroupBy + OrderBy + Where), utilisable par Add-PnPView -Query et
        ViewQuery.
    .EXAMPLE
        $types = Get-HNCSRDColumnTypes -Object (Get-HNCSRDObject Candidatures)
        ConvertTo-HNCSRDCaml -View $modele.views.Candidatures[0] -ColumnTypes $types
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]$View,
        [Parameter(Mandatory)][hashtable]$ColumnTypes,
        [ValidateSet('list', 'library')][string]$ListKind = 'list',
        [int]$RowLimit = 30
    )
    $verifier = {
        param($champ, $contexte)
        if (-not $ColumnTypes.ContainsKey($champ)) { throw "Vue « $($View.name) » : colonne inconnue ou non déployée « $champ » ($contexte)." }
    }
    $champs = New-Object System.Collections.Generic.List[string]
    if ($ListKind -eq 'library') { foreach ($t in $script:ColonnesTeteBibliotheque) { $champs.Add($t) } }
    elseif (@($View.columns) -notcontains 'Title') { $champs.Add('LinkTitle') }
    foreach ($c in @($View.columns)) {
        & $verifier $c 'colonnes'
        $nomAffiche = [string]$c
        if ($c -eq 'Title' -and $ListKind -eq 'list') { $nomAffiche = 'LinkTitle' }
        if (-not $champs.Contains($nomAffiche)) { $champs.Add($nomAffiche) }
    }
    $conditions = New-Object System.Collections.Generic.List[string]
    foreach ($f in @($View.filter)) {
        $champ = [string]$f.field
        & $verifier $champ 'filtre'
        $type = [string]$ColumnTypes[$champ]
        $ref = '<FieldRef Name="' + $champ + '" />'
        $valeurs = @($f.values)
        $op = [string]$f.op
        switch ($op) {
            'isnull' { $conditions.Add('<IsNull>' + $ref + '</IsNull>'); continue }
            'isnotnull' { $conditions.Add('<IsNotNull>' + $ref + '</IsNotNull>'); continue }
        }
        if ($op -eq 'isnull' -or $op -eq 'isnotnull') { continue }
        if ($valeurs.Count -eq 0) { throw "Vue « $($View.name) » : opérateur $op sans valeur sur $champ." }
        $balises = @{ '=' = 'Eq'; '<>' = 'Neq'; '<' = 'Lt'; '<=' = 'Leq'; '>' = 'Gt'; '>=' = 'Geq' }
        if ($balises.ContainsKey($op)) {
            if ($valeurs.Count -ne 1) { throw "Vue « $($View.name) » : l'opérateur $op attend une seule valeur ($champ)." }
            $b = $balises[$op]
            $conditions.Add('<' + $b + '>' + $ref + (ConvertTo-HNCSRDCamlValue -Champ $champ -Type $type -Valeur $valeurs[0]) + '</' + $b + '>')
        }
        elseif ($op -eq 'in') {
            if ($valeurs.Count -eq 1) {
                $conditions.Add('<Eq>' + $ref + (ConvertTo-HNCSRDCamlValue -Champ $champ -Type $type -Valeur $valeurs[0]) + '</Eq>')
            }
            else {
                $sb = New-Object System.Text.StringBuilder
                [void]$sb.Append('<In>' + $ref + '<Values>')
                foreach ($v in $valeurs) { [void]$sb.Append((ConvertTo-HNCSRDCamlValue -Champ $champ -Type $type -Valeur $v)) }
                [void]$sb.Append('</Values></In>')
                $conditions.Add($sb.ToString())
            }
        }
        elseif ($op -eq 'notin') {
            $neqs = @()
            foreach ($v in $valeurs) { $neqs += '<Neq>' + $ref + (ConvertTo-HNCSRDCamlValue -Champ $champ -Type $type -Valeur $v) + '</Neq>' }
            $conditions.Add((Join-HNCSRDCamlAnd -Noeuds $neqs))
        }
        else { throw "Vue « $($View.name) » : opérateur inconnu « $op »." }
    }
    $where = ''
    if ($conditions.Count -gt 0) { $where = '<Where>' + (Join-HNCSRDCamlAnd -Noeuds $conditions.ToArray()) + '</Where>' }
    $orderBy = ''
    $tris = @($View.sort)
    if ($tris.Count -gt 0) {
        $sb = New-Object System.Text.StringBuilder
        [void]$sb.Append('<OrderBy>')
        foreach ($t in $tris) {
            & $verifier ([string]$t.field) 'tri'
            $asc = 'TRUE'
            if ([string]$t.dir -eq 'desc') { $asc = 'FALSE' } elseif ([string]$t.dir -ne 'asc') { throw "Vue « $($View.name) » : sens de tri inconnu « $($t.dir) »." }
            [void]$sb.Append('<FieldRef Name="' + $t.field + '" Ascending="' + $asc + '" />')
        }
        [void]$sb.Append('</OrderBy>')
        $orderBy = $sb.ToString()
    }
    $groupBy = ''
    if ($View.groupBy) {
        & $verifier ([string]$View.groupBy) 'regroupement'
        $groupBy = '<GroupBy Collapse="FALSE" GroupLimit="30"><FieldRef Name="' + $View.groupBy + '" /></GroupBy>'
    }
    return [pscustomobject]@{
        Name       = [string]$View.name
        Default    = [bool]$View.default
        ViewFields = $champs.ToArray()
        Where      = $where
        OrderBy    = $orderBy
        GroupBy    = $groupBy
        Query      = $groupBy + $orderBy + $where
        RowLimit   = $RowLimit
        Paged      = $true
    }
}

function Format-HNCSRDCamlNormalise {
    <#
    .SYNOPSIS
        Normalise un fragment CAML (espaces, guillemets) pour comparaison.
    #>
    [CmdletBinding()]
    param([AllowEmptyString()][AllowNull()][string]$Caml)
    if (-not $Caml) { return '' }
    $doc = New-Object System.Xml.XmlDocument
    $doc.PreserveWhitespace = $false
    $doc.LoadXml('<Q>' + $Caml + '</Q>')
    return $doc.DocumentElement.InnerXml
}

function ConvertTo-HNCSRDValidationFormula {
    <#
    .SYNOPSIS
        Traduit une formule de validation du modèle ([NomInterne]) en références [Nom affiché].
    .DESCRIPTION
        Fonction pure. La spec écrit les formules avec les noms internes (syntaxe invariante, fonctions
        anglaises, séparateur virgule) ; l'analyseur de formules SharePoint résout les colonnes par leur
        nom affiché. Toute référence inconnue lève une erreur.
    .PARAMETER NomsAffiches
        Table nom interne -> nom affiché (champs de la liste).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Formula, [Parameter(Mandatory)][hashtable]$NomsAffiches)
    $sb = New-Object System.Text.StringBuilder
    $pos = 0
    foreach ($m in [regex]::Matches($Formula, '\[([^\[\]]+)\]')) {
        [void]$sb.Append($Formula.Substring($pos, $m.Index - $pos))
        $nom = $m.Groups[1].Value
        if (-not $NomsAffiches.ContainsKey($nom)) { throw "Formule de validation : colonne inconnue « $nom »." }
        $affiche = [string]$NomsAffiches[$nom]
        if ($affiche -match '[\[\]]') { throw "Formule de validation : le nom affiché « $affiche » contient un crochet." }
        [void]$sb.Append('[' + $affiche + ']')
        $pos = $m.Index + $m.Length
    }
    [void]$sb.Append($Formula.Substring($pos))
    return $sb.ToString()
}

function Get-HNCSRDValidationColumns {
    <#
    .SYNOPSIS
        Noms internes référencés par une formule de validation.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Formula)
    $noms = @()
    foreach ($m in [regex]::Matches($Formula, '\[([^\[\]]+)\]')) { if ($noms -notcontains $m.Groups[1].Value) { $noms += $m.Groups[1].Value } }
    return $noms
}

function Get-HNCSRDVersioningSpec {
    <#
    .SYNOPSIS
        Paramètres de versioning attendus pour un objet.
    .DESCRIPTION
        Listes : versions majeures (50). Bibliothèques : propriété « versioning » du modèle,
        « Majeures (n) » ou « Majeures et mineures (n/m) » (m = nombre de versions majeures conservant
        leurs brouillons, MajorWithMinorVersionsLimit).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Object)
    if ($Object.kind -ne 'library') {
        return [pscustomobject]@{ EnableVersioning = $true; MajorVersions = 50; EnableMinorVersions = $false; MinorVersions = $null }
    }
    $texte = [string]$Object.versioning
    if ($texte -match '^\s*Majeures et mineures\s*\(\s*(\d+)\s*/\s*(\d+)\s*\)\s*$') {
        return [pscustomobject]@{ EnableVersioning = $true; MajorVersions = [int]$Matches[1]; EnableMinorVersions = $true; MinorVersions = [int]$Matches[2] }
    }
    if ($texte -match '^\s*Majeures\s*\(\s*(\d+)\s*\)\s*$') {
        return [pscustomobject]@{ EnableVersioning = $true; MajorVersions = [int]$Matches[1]; EnableMinorVersions = $false; MinorVersions = $null }
    }
    throw "Versioning non reconnu pour $($Object.name) : « $texte »."
}

function Get-HNCSRDAttributionsAttendues {
    <#
    .SYNOPSIS
        Attributions attendues au niveau d'une liste/bibliothèque d'après la matrice (§ 7.3).
    .DESCRIPTION
        Fonction pure. Retourne une table ordonnée nom du groupe -> code de niveau (FC, CSS, R).
        «, » et « IL(x) » ne donnent aucune attribution au niveau de la liste (les permissions par
        élément ou dossier sont posées par les flux, § 7.4) ; « R+IL(x) » donne R au niveau de la liste
        (le complément x par élément est posé par les flux).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$ObjectName, $Model)
    if (-not $Model) { $Model = Get-HNCSRDModel }
    if (-not ($Model.matrix.PSObject.Properties.Name -contains $ObjectName)) { throw "Objet « $ObjectName » absent de la matrice d'accès." }
    $ligne = $Model.matrix.$ObjectName
    $niveaux = @($Model.permissionLevels.PSObject.Properties.Name)
    $r = New-Object System.Collections.Specialized.OrderedDictionary
    foreach ($g in $Model.groups) {
        if (-not ($ligne.PSObject.Properties.Name -contains $g.code)) { throw "Matrice : groupe $($g.code) absent pour $ObjectName." }
        $v = ([string]$ligne.($g.code)).Trim()
        if ($niveaux -contains $v) { $r[[string]$g.name] = $v }
        elseif ($v -match '^(\w+)\+IL\((\w+)\)$') {
            # « R+IL(x) » (spec § 7.2, v1.1.0) : niveau de base au niveau de la liste ; l'IL(x) est posé par les flux.
            if ($niveaux -notcontains $Matches[1] -or $niveaux -notcontains $Matches[2]) { throw "Matrice : niveau inconnu « $v » ($ObjectName / $($g.code))." }
            $r[[string]$g.name] = $Matches[1]
        }
        elseif ($v -match '^IL\((\w+)\)$') { if ($niveaux -notcontains $Matches[1]) { throw "Matrice : niveau inconnu « $v » ($ObjectName / $($g.code))." } }
        elseif ($v -eq [string][char]0x2014 -or $v -eq '-' -or $v -eq '') { }
        else { throw "Matrice : valeur inconnue « $v » ($ObjectName / $($g.code))." }
    }
    return $r
}

function Get-HNCSRDAttributionsSite {
    <#
    .SYNOPSIS
        Attributions attendues au niveau du site (§ 7.2) : groupe propriétaire = FC, autres groupes = R.
    #>
    [CmdletBinding()]
    param($Model)
    if (-not $Model) { $Model = Get-HNCSRDModel }
    $prop = Get-HNCSRDOwnerGroupCode -Model $Model
    $r = New-Object System.Collections.Specialized.OrderedDictionary
    foreach ($g in $Model.groups) { if ($g.code -eq $prop) { $r[[string]$g.name] = 'FC' } else { $r[[string]$g.name] = 'R' } }
    return $r
}

function Get-HNCSRDNavigationPlan {
    <#
    .SYNOPSIS
        Plan de navigation rapide : en-têtes par domaine (ordre alphabétique des domaines métier),
        puis « Bibliothèques », puis le domaine technique (« T. Technique » -> « Technique »).
    .OUTPUTS
        Tableau de { Titre ; Liens = @({ Titre ; Objet }) }.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][int]$Lot, $Model)
    if (-not $Model) { $Model = Get-HNCSRDModel }
    $objets = Get-HNCSRDObjects -Lot $Lot -Model $Model
    $metier = @{}; $technique = @{}; $biblio = New-Object System.Collections.Generic.List[object]
    foreach ($o in $objets) {
        $lien = [pscustomobject]@{ Titre = [string]$o.title; Objet = [string]$o.name }
        if ($o.kind -eq 'library') { $biblio.Add($lien); continue }
        $dom = [string]$o.domain
        if ($dom -match '^T\.\s*(.+)$') {
            $titre = $Matches[1]
            if (-not $technique.ContainsKey($titre)) { $technique[$titre] = New-Object System.Collections.Generic.List[object] }
            $technique[$titre].Add($lien)
        }
        else {
            if (-not $dom) { $dom = 'Autres' }
            if (-not $metier.ContainsKey($dom)) { $metier[$dom] = New-Object System.Collections.Generic.List[object] }
            $metier[$dom].Add($lien)
        }
    }
    $plan = New-Object System.Collections.Generic.List[object]
    foreach ($d in ($metier.Keys | Sort-Object)) { $plan.Add([pscustomobject]@{ Titre = $d; Liens = $metier[$d].ToArray() }) }
    if ($biblio.Count -gt 0) { $plan.Add([pscustomobject]@{ Titre = $script:EnteteBibliotheques; Liens = $biblio.ToArray() }) }
    foreach ($d in ($technique.Keys | Sort-Object)) { $plan.Add([pscustomobject]@{ Titre = $d; Liens = $technique[$d].ToArray() }) }
    return $plan.ToArray()
}

function Get-HNCSRDTimeZoneId {
    <#
    .SYNOPSIS
        Identifiant SharePoint du fuseau horaire du modèle (Romance Standard Time -> 3, Paris).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$TimeZone)
    if (-not $script:FuseauxSharePoint.ContainsKey($TimeZone)) { throw "Fuseau horaire sans correspondance SharePoint : $TimeZone" }
    return [int]$script:FuseauxSharePoint[$TimeZone]
}

#endregion

#region Prérequis et connexion -------------------------------------------------------------------

function Assert-HNCSRDPrerequis {
    <#
    .SYNOPSIS
        Vérifie PowerShell 7.4+ et PnP.PowerShell (version minimale), puis importe PnP.PowerShell.
    .OUTPUTS
        Version de PnP.PowerShell chargée.
    #>
    [CmdletBinding()]
    param([version]$VersionPnPMinimale = '2.12.0')
    $v = $PSVersionTable.PSVersion
    if ($v.Major -lt 7 -or ($v.Major -eq 7 -and $v.Minor -lt 4)) {
        throw "PowerShell 7.4 ou supérieur est requis (version courante : $v). Lancer le script avec « pwsh »."
    }
    $pnp = Get-Module -Name PnP.PowerShell -ListAvailable | Sort-Object Version -Descending | Select-Object -First 1
    if (-not $pnp) { throw "Module PnP.PowerShell introuvable : Install-Module PnP.PowerShell -Scope CurrentUser" }
    if ($pnp.Version -lt $VersionPnPMinimale) { throw "PnP.PowerShell $VersionPnPMinimale ou supérieur requis (installé : $($pnp.Version)) : Update-Module PnP.PowerShell" }
    $charge = Get-Module -Name PnP.PowerShell
    if (-not $charge) { Import-Module $pnp.Path -ErrorAction Stop -DisableNameChecking }
    return $pnp.Version
}

function Get-HNCSRDTenantDomain {
    <#
    .SYNOPSIS
        Domaine du tenant pour l'authentification par certificat (« <TenantName>.onmicrosoft.com »).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Config)
    $t = [string]$Config.TenantName
    if ($t -match '\.') { return $t }
    return ($t + '.onmicrosoft.com')
}

function Connect-HNCSRD {
    <#
    .SYNOPSIS
        Se connecte au site HNCS-RD (ou au centre d'administration) avec PnP.PowerShell.
    .DESCRIPTION
        Mode interactif : Connect-PnPOnline -Interactive -ClientId <PnPClientId> (application Entra
        obligatoire depuis 2024, voir Register-PnPEntraIDAppForInteractiveLogin).
        Mode certificat (automatisation) : si un chemin de certificat (.pfx) ou une empreinte est fourni
        (paramètres ou CertificatePath / CertificateThumbprint de la configuration) :
        Connect-PnPOnline -ClientId -Tenant <tenant>.onmicrosoft.com -CertificatePath|-Thumbprint.
        Le mot de passe du .pfx est lu dans -CertificatePassword ou la variable d'environnement
        HNCSRD_CERT_PASSWORD.
    .PARAMETER Administration
        Connexion au centre d'administration SharePoint (TenantAdminUrl).
    .PARAMETER ReturnConnection
        Retourne l'objet connexion sans remplacer la connexion courante.
    .EXAMPLE
        $config = Get-HNCSRDConfig
        Connect-HNCSRD -Config $config
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]$Config,
        [string]$Url,
        [switch]$Administration,
        [switch]$ReturnConnection,
        [string]$CertificatePath,
        [string]$Thumbprint,
        [securestring]$CertificatePassword
    )
    if (-not $Url) {
        if ($Administration) { $Url = [string]$Config.TenantAdminUrl } else { $Url = [string]$Config.SiteUrl }
    }
    if (-not $CertificatePath) { $CertificatePath = [string]$Config.CertificatePath }
    if (-not $Thumbprint) { $Thumbprint = [string]$Config.CertificateThumbprint }
    $p = @{ Url = $Url; ClientId = [string]$Config.PnPClientId; ErrorAction = 'Stop' }
    if ($Thumbprint -or $CertificatePath) {
        $p['Tenant'] = Get-HNCSRDTenantDomain -Config $Config
        if ($Thumbprint) { $p['Thumbprint'] = $Thumbprint }
        else {
            if (-not (Test-Path -LiteralPath $CertificatePath)) { throw "Certificat introuvable : $CertificatePath" }
            $p['CertificatePath'] = $CertificatePath
            if ($CertificatePassword) { $p['CertificatePassword'] = $CertificatePassword }
            elseif ($env:HNCSRD_CERT_PASSWORD) { $p['CertificatePassword'] = ConvertTo-SecureString -String $env:HNCSRD_CERT_PASSWORD -AsPlainText -Force }
        }
        Write-HNCSRDLog -Message "Connexion par certificat à $Url" -Niveau Detail
    }
    else {
        $p['Interactive'] = $true
        Write-HNCSRDLog -Message "Connexion interactive à $Url" -Niveau Detail
    }
    if ($ReturnConnection) { $p['ReturnConnection'] = $true }
    return (Connect-PnPOnline @p)
}

#endregion

#region Lecture SharePoint (utilitaires) ---------------------------------------------------------

function Get-HNCSRDList {
    <#
    .SYNOPSIS
        Retourne la liste SharePoint d'un objet du modèle (par URL), ou $null si absente.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Name, $Model, $Connection)
    $url = Get-HNCSRDListUrl -Name $Name -Model $Model
    $p = @{ Identity = $url; ErrorAction = 'SilentlyContinue' }
    if ($Connection) { $p['Connection'] = $Connection }
    $l = $null
    try { $l = Get-PnPList @p } catch { $l = $null }
    if ($l) {
        $racine = Get-PnPProperty -ClientObject $l -Property RootFolder
        $sru = [string]$racine.ServerRelativeUrl
        if (-not $sru.EndsWith('/' + $url, [System.StringComparison]::OrdinalIgnoreCase)) { return $null }
    }
    return $l
}

function Get-HNCSRDChamps {
    <#
    .SYNOPSIS
        Champs d'une liste SharePoint indexés par nom interne.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$List)
    $t = @{}
    foreach ($f in @(Get-PnPField -List $List)) { $t[[string]$f.InternalName] = $f }
    return $t
}

function Get-HNCSRDSchemaXml {
    # SchemaXml d'un champ (chargé si nécessaire, usage interne).
    param($Field)
    try { $s = $Field.SchemaXml; if ($s) { return [string]$s } } catch { }
    [void](Get-PnPProperty -ClientObject $Field -Property SchemaXml)
    return [string]$Field.SchemaXml
}

function Get-HNCSRDRoleDefinitionName {
    <#
    .SYNOPSIS
        Nom (localisé) du niveau d'autorisation d'un code du modèle (FC, R, CSS).
    .DESCRIPTION
        Les niveaux natifs sont résolus par RoleTypeKind (jamais par leur nom localisé) ; le niveau
        personnalisé par son nom exact.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Code, $Model, [switch]$Rafraichir)
    if (-not $Model) { $Model = Get-HNCSRDModel }
    if ($Rafraichir -or -not $script:HNCSRD.CacheRoles) { $script:HNCSRD.CacheRoles = @(Get-PnPRoleDefinition) }
    $niv = $Model.permissionLevels.$Code
    if (-not $niv) { throw "Niveau d'autorisation « $Code » absent du modèle." }
    if ($niv.PSObject.Properties.Name -contains 'roleTypeKind') {
        $d = @($script:HNCSRD.CacheRoles | Where-Object { [string]$_.RoleTypeKind -eq [string]$niv.roleTypeKind } | Select-Object -First 1)
    }
    else {
        $d = @($script:HNCSRD.CacheRoles | Where-Object { $_.Name -eq [string]$niv.name } | Select-Object -First 1)
    }
    if ($d.Count -eq 0) { return $null }
    return [string]$d[0].Name
}

function Get-HNCSRDPermissionKinds {
    <#
    .SYNOPSIS
        Liste des PermissionKind accordés par une définition de rôle CSOM.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$RoleDefinition)
    $type = [Microsoft.SharePoint.Client.PermissionKind]
    $r = @()
    foreach ($n in [Enum]::GetNames($type)) {
        if ($n -eq 'EmptyMask' -or $n -eq 'FullMask') { continue }
        if ($RoleDefinition.BasePermissions.Has([Enum]::Parse($type, $n))) { $r += $n }
    }
    return $r
}

function Get-HNCSRDEtatAttributions {
    <#
    .SYNOPSIS
        Attributions de rôles d'un objet sécurisable (site ou liste), niveaux masqués (Accès limité) exclus.
    .OUTPUTS
        Tableau de { Nom ; Type ; Roles (noms visibles) ; RolesMasques ; Attribution (objet CSOM) }.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Securable)
    $ras = Get-PnPProperty -ClientObject $Securable -Property RoleAssignments
    $r = New-Object System.Collections.Generic.List[object]
    foreach ($ra in @($ras)) {
        [void](Get-PnPProperty -ClientObject $ra -Property Member, RoleDefinitionBindings)
        $visibles = @(); $masques = @()
        foreach ($b in @($ra.RoleDefinitionBindings)) {
            if ($b.Hidden -or [string]$b.RoleTypeKind -eq 'Guest') { $masques += [string]$b.Name } else { $visibles += [string]$b.Name }
        }
        $r.Add([pscustomobject]@{
                Nom          = [string]$ra.Member.Title
                Type         = [string]$ra.Member.PrincipalType
                Roles        = $visibles
                RolesMasques = $masques
                Attribution  = $ra
            })
    }
    return $r.ToArray()
}

function Compare-HNCSRDAttributions {
    <#
    .SYNOPSIS
        Compare l'état des attributions (Get-HNCSRDEtatAttributions) aux attributions attendues.
    .PARAMETER Attendues
        Table nom de groupe SharePoint -> nom (localisé) du niveau attendu.
    .OUTPUTS
        { AAjouter = @({Nom;Role}) ; ARetirer = @({Nom;Type;Role}) }.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][AllowEmptyCollection()][object[]]$Etat, [Parameter(Mandatory)]$Attendues)
    $ajouts = New-Object System.Collections.Generic.List[object]
    $retraits = New-Object System.Collections.Generic.List[object]
    foreach ($e in $Etat) {
        $attendu = $null
        if ($e.Type -eq 'SharePointGroup' -and $Attendues.Contains($e.Nom)) { $attendu = [string]$Attendues[$e.Nom] }
        foreach ($role in $e.Roles) { if ($role -ne $attendu) { $retraits.Add([pscustomobject]@{ Nom = $e.Nom; Type = $e.Type; Role = $role }) } }
    }
    foreach ($nom in $Attendues.Keys) {
        $role = [string]$Attendues[$nom]
        $present = @($Etat | Where-Object { $_.Type -eq 'SharePointGroup' -and $_.Nom -eq $nom -and ($_.Roles -contains $role) })
        if ($present.Count -eq 0) { $ajouts.Add([pscustomobject]@{ Nom = $nom; Role = $role }) }
    }
    return [pscustomobject]@{ AAjouter = $ajouts.ToArray(); ARetirer = $retraits.ToArray() }
}

#endregion

#region Étapes SharePoint (Ensure-* / Set-*) -----------------------------------------------------

function Ensure-HNCSRDSite {
    <#
    .SYNOPSIS
        Crée le site d'équipe sans groupe Microsoft 365 (STS#3, langue et fuseau du modèle) s'il n'existe pas.
    .DESCRIPTION
        Exige une connexion au centre d'administration (-AdminConnection). Si le site existe, rien n'est
        modifié (un écart de modèle ou de langue est signalé). Un site présent dans la corbeille des sites
        est signalé en erreur (restaurer ou purger manuellement).
    .OUTPUTS
        $true si le site existe (ou vient d'être créé), $false sinon.
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Config, [Parameter(Mandatory)]$Model, [Parameter(Mandatory)]$AdminConnection)
    $url = ([string]$Config.SiteUrl).TrimEnd('/')
    $site = $null
    try { $site = Get-PnPTenantSite -Identity $url -Connection $AdminConnection -ErrorAction Stop } catch { $site = $null }
    if ($site) {
        $msg = @()
        if ($site.Template -and [string]$site.Template -ne [string]$Model.site.template) { $msg += "modèle $($site.Template) (attendu $($Model.site.template))" }
        if ($site.LocaleId -and [int]$site.LocaleId -ne [int]$Model.site.lcid) { $msg += "langue $($site.LocaleId) (attendu $($Model.site.lcid))" }
        if ($msg.Count -gt 0) { Add-HNCSRDResultat -Statut Avertissement -Cible $url -Message ('Site existant non conforme : ' + ($msg -join ' ; ') + ' (non modifié)') }
        else { Add-HNCSRDResultat -Statut Inchange -Cible $url -Message 'Site existant' }
        return $true
    }
    $supprime = $null
    try { $supprime = Get-PnPTenantDeletedSite -Identity $url -Connection $AdminConnection -ErrorAction Stop } catch { $supprime = $null }
    if ($supprime) {
        Add-HNCSRDResultat -Statut Erreur -Cible $url -Message 'Le site est dans la corbeille des sites : le restaurer (Restore-PnPTenantDeletedSite) ou le purger avant de relancer.'
        return $false
    }
    $tz = Get-HNCSRDTimeZoneId -TimeZone ([string]$Model.site.timeZone)
    if (Test-HNCSRDSimulation) {
        Add-HNCSRDResultat -Statut Simule -Cible $url -Message ("Création du site « {0} » ({1}, LCID {2}, fuseau {3})" -f $Model.site.title, $Model.site.template, $Model.site.lcid, $tz)
        return $false
    }
    New-PnPTenantSite -Title ([string]$Model.site.title) -Url $url -Owner ([string]$Config.SiteOwner) -Lcid ([int]$Model.site.lcid) `
        -Template ([string]$Model.site.template) -TimeZone $tz -Wait -Connection $AdminConnection -ErrorAction Stop | Out-Null
    Add-HNCSRDResultat -Statut Cree -Cible $url -Message ("Site « {0} » ({1}, LCID {2}, fuseau {3})" -f $Model.site.title, $Model.site.template, $Model.site.lcid, $tz)
    return $true
}

function Ensure-HNCSRDPermissionLevels {
    <#
    .SYNOPSIS
        Crée ou corrige les niveaux d'autorisation personnalisés du modèle (CSS : Contributor moins
        DeleteListItems et DeleteVersions). Les niveaux natifs (FC, R) sont seulement vérifiés.
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Model)
    $defs = @(Get-PnPRoleDefinition)
    foreach ($p in $Model.permissionLevels.PSObject.Properties) {
        $code = $p.Name; $niv = $p.Value
        if ($niv.PSObject.Properties.Name -contains 'roleTypeKind') {
            $d = @($defs | Where-Object { [string]$_.RoleTypeKind -eq [string]$niv.roleTypeKind })
            if ($d.Count -eq 0) { Add-HNCSRDResultat -Statut Erreur -Cible $code -Message "Niveau natif RoleTypeKind=$($niv.roleTypeKind) introuvable" }
            else { Add-HNCSRDResultat -Statut Inchange -Cible $code -Message ("Niveau natif « {0} » (RoleTypeKind {1})" -f $d[0].Name, $niv.roleTypeKind) }
            continue
        }
        $base = @($defs | Where-Object { [string]$_.RoleTypeKind -eq [string]$niv.basedOn })
        if ($base.Count -eq 0) { Add-HNCSRDResultat -Statut Erreur -Cible $niv.name -Message "Niveau de base RoleTypeKind=$($niv.basedOn) introuvable"; continue }
        $retirer = @($niv.remove)
        $attendues = @(Get-HNCSRDPermissionKinds -RoleDefinition $base[0] | Where-Object { $retirer -notcontains $_ })
        $existant = @($defs | Where-Object { $_.Name -eq [string]$niv.name })
        $description = ("Permissions de {0} sans {1} (spec § 7.2)" -f $niv.basedOn, ($retirer -join ', '))
        if ($existant.Count -eq 0) {
            if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $niv.name -Message "Création (clone de $($base[0].Name) sans $($retirer -join ', '))"; continue }
            Add-PnPRoleDefinition -RoleName ([string]$niv.name) -Clone $base[0] -Exclude $retirer -Description $description -ErrorAction Stop | Out-Null
            Add-HNCSRDResultat -Statut Cree -Cible $niv.name -Message "Clone de $($base[0].Name) sans $($retirer -join ', ')"
            continue
        }
        $actuelles = @(Get-HNCSRDPermissionKinds -RoleDefinition $existant[0])
        $manquantes = @($attendues | Where-Object { $actuelles -notcontains $_ })
        $enTrop = @($actuelles | Where-Object { $attendues -notcontains $_ })
        if ($manquantes.Count -eq 0 -and $enTrop.Count -eq 0) { Add-HNCSRDResultat -Statut Inchange -Cible $niv.name; continue }
        $msg = ('ajout : {0} ; retrait : {1}' -f ($manquantes -join ', '), ($enTrop -join ', '))
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $niv.name -Message "Correction des permissions ($msg)"; continue }
        $sp = @{ Identity = [string]$niv.name; ErrorAction = 'Stop' }
        if ($manquantes.Count -gt 0) { $sp['Select'] = $manquantes }
        if ($enTrop.Count -gt 0) { $sp['Clear'] = $enTrop }
        Set-PnPRoleDefinition @sp | Out-Null
        Add-HNCSRDResultat -Statut MisAJour -Cible $niv.name -Message $msg
    }
    $script:HNCSRD.CacheRoles = $null
}

function Ensure-HNCSRDGroups {
    <#
    .SYNOPSIS
        Crée les groupes SharePoint du modèle (noms exacts), propriétaire = groupe PROPRIETAIRE (G_PROP),
        sans membres (les membres sont gérés par Set-HNCSRDMembres.ps1).
    .DESCRIPTION
        À la création, le compte qui exécute le script, ajouté automatiquement par SharePoint, est retiré
        du groupe. Les groupes existants ne voient pas leurs membres modifiés.
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Model)
    $nomProp = Get-HNCSRDGroupName -Code (Get-HNCSRDOwnerGroupCode -Model $Model) -Model $Model
    $ordre = @($Model.groups | Where-Object { $_.name -eq $nomProp }) + @($Model.groups | Where-Object { $_.name -ne $nomProp })
    foreach ($g in $ordre) {
        $nom = [string]$g.name
        $grp = $null
        try { $grp = Get-PnPGroup -Identity $nom -ErrorAction Stop } catch { $grp = $null }
        if (-not $grp) {
            if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $nom -Message "Création (propriétaire $nomProp)"; continue }
            $grp = New-PnPGroup -Title $nom -Description ([string]$g.description) -ErrorAction Stop
            foreach ($m in @(Get-PnPGroupMember -Group $nom)) {
                Remove-PnPGroupMember -Group $nom -LoginName $m.LoginName -ErrorAction Stop
                Write-HNCSRDLog -Message "Membre ajouté automatiquement retiré de $nom : $($m.LoginName)" -Niveau Detail
            }
            Add-HNCSRDResultat -Statut Cree -Cible $nom
        }
        else {
            [void](Get-PnPProperty -ClientObject $grp -Property Description)
            if ([string]$grp.Description -ne [string]$g.description) {
                if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $nom -Message 'Mise à jour de la description' }
                else { $grp.Description = [string]$g.description; $grp.Update(); Invoke-PnPQuery; Add-HNCSRDResultat -Statut MisAJour -Cible $nom -Message 'Description' }
            }
            else { Add-HNCSRDResultat -Statut Inchange -Cible $nom }
        }
    }
    foreach ($g in $ordre) {
        $nom = [string]$g.name
        $grp = $null
        try { $grp = Get-PnPGroup -Identity $nom -ErrorAction Stop } catch { $grp = $null }
        if (-not $grp) { continue }
        $owner = Get-PnPProperty -ClientObject $grp -Property Owner
        if ([string]$owner.Title -ne $nomProp) {
            if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $nom -Message "Propriétaire -> $nomProp"; continue }
            Set-PnPGroup -Identity $nom -Owner $nomProp -ErrorAction Stop | Out-Null
            Add-HNCSRDResultat -Statut MisAJour -Cible $nom -Message "Propriétaire : $($owner.Title) -> $nomProp"
        }
    }
}

function Set-HNCSRDVersioning {
    <#
    .SYNOPSIS
        Applique le versioning attendu (listes : majeures 50 ; bibliothèques : selon le modèle).
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Object, [Parameter(Mandatory)]$List)
    $v = Get-HNCSRDVersioningSpec -Object $Object
    [void](Get-PnPProperty -ClientObject $List -Property EnableVersioning, MajorVersionLimit, EnableMinorVersions, MajorWithMinorVersionsLimit)
    $ok = ($List.EnableVersioning -eq $v.EnableVersioning -and [int]$List.MajorVersionLimit -eq $v.MajorVersions)
    if ($Object.kind -eq 'library') {
        $ok = $ok -and ($List.EnableMinorVersions -eq $v.EnableMinorVersions)
        if ($v.EnableMinorVersions) { $ok = $ok -and ([int]$List.MajorWithMinorVersionsLimit -eq $v.MinorVersions) }
    }
    $cible = "$($Object.name) (versioning)"
    $texte = "majeures $($v.MajorVersions)"
    if ($v.EnableMinorVersions) { $texte += " ; mineures sur $($v.MinorVersions) versions majeures" }
    if ($ok) { Add-HNCSRDResultat -Statut Inchange -Cible $cible -Message $texte; return }
    if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cible -Message $texte; return }
    $p = @{ Identity = $List; EnableVersioning = $true; MajorVersions = [uint32]$v.MajorVersions; ErrorAction = 'Stop' }
    if ($Object.kind -eq 'library') {
        $p['EnableMinorVersions'] = [bool]$v.EnableMinorVersions
        if ($v.EnableMinorVersions) { $p['MinorVersions'] = [uint32]$v.MinorVersions }
    }
    Set-PnPList @p | Out-Null
    Add-HNCSRDResultat -Statut MisAJour -Cible $cible -Message $texte
}

function Ensure-HNCSRDList {
    <#
    .SYNOPSIS
        Crée la liste ou bibliothèque d'un objet (URL = nom interne, titre affiché = title) et applique
        le versioning. Idempotent : le titre est corrigé s'il diffère.
    .OUTPUTS
        La liste CSOM, ou $null (simulation d'une création).
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Object, $Model)
    $url = Get-HNCSRDListUrl -Name $Object.name -Model $Model
    $liste = Get-HNCSRDList -Name $Object.name -Model $Model
    if (-not $liste) {
        $modele = 'GenericList'
        if ($Object.kind -eq 'library') { $modele = 'DocumentLibrary' }
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $Object.name -Message "Création ($modele, /$url, « $($Object.title) »)"; return $null }
        $liste = New-PnPList -Title ([string]$Object.name) -Url $url -Template $modele -ErrorAction Stop
        Set-PnPList -Identity $liste -Title ([string]$Object.title) -ErrorAction Stop | Out-Null
        $liste = Get-HNCSRDList -Name $Object.name -Model $Model
        Add-HNCSRDResultat -Statut Cree -Cible $Object.name -Message "$modele /$url « $($Object.title) »"
    }
    elseif ([string]$liste.Title -ne [string]$Object.title) {
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $Object.name -Message "Titre « $($liste.Title) » -> « $($Object.title) »" }
        else {
            Set-PnPList -Identity $liste -Title ([string]$Object.title) -ErrorAction Stop | Out-Null
            Add-HNCSRDResultat -Statut MisAJour -Cible $Object.name -Message "Titre -> « $($Object.title) »"
        }
    }
    else { Add-HNCSRDResultat -Statut Inchange -Cible $Object.name }
    Set-HNCSRDVersioning -Object $Object -List $liste
    return $liste
}

function Ensure-HNCSRDTitleColumn {
    <#
    .SYNOPSIS
        Renomme la colonne Title native et applique obligation, index et unicité (titleColumn du modèle).
    .DESCRIPTION
        Ne s'applique qu'aux objets dont le modèle définit un libellé Title (listes). Le Title natif des
        bibliothèques n'est pas modifié (aucune définition dans la spec).
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Object, [Parameter(Mandatory)]$List)
    if (-not $Object.titleLabel) { Write-HNCSRDLog -Message "$($Object.name) : aucun libellé Title dans le modèle, colonne Titre native conservée" -Niveau Detail; return }
    $tc = $Object.titleColumn
    $champ = Get-PnPField -List $List -Identity 'Title' -ErrorAction Stop
    $diffs = @()
    if ([string]$champ.Title -cne [string]$Object.titleLabel) { $diffs += "libellé « $($Object.titleLabel) »" }
    if ([bool]$champ.Required -ne [bool]$Object.titleRequired) { $diffs += "obligatoire=$([bool]$Object.titleRequired)" }
    $indexAttendu = [bool]$tc.indexed -or [bool]$tc.unique
    if ([bool]$champ.Indexed -ne $indexAttendu) { $diffs += "index=$indexAttendu" }
    if ([bool]$champ.EnforceUniqueValues -ne [bool]$tc.unique) { $diffs += "unique=$([bool]$tc.unique)" }
    $cible = "$($Object.name).Title"
    if ($diffs.Count -eq 0) { Add-HNCSRDResultat -Statut Inchange -Cible $cible; return }
    if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cible -Message ($diffs -join ' ; '); return }
    $champ.Title = [string]$Object.titleLabel
    $champ.Required = [bool]$Object.titleRequired
    if ($indexAttendu) { $champ.Indexed = $true }
    $champ.Update(); Invoke-PnPQuery
    if ([bool]$champ.EnforceUniqueValues -ne [bool]$tc.unique) { $champ.EnforceUniqueValues = [bool]$tc.unique; $champ.Update(); Invoke-PnPQuery }
    if (-not $indexAttendu -and $champ.Indexed) { $champ.Indexed = $false; $champ.Update(); Invoke-PnPQuery }
    Add-HNCSRDResultat -Statut MisAJour -Cible $cible -Message ($diffs -join ' ; ')
}

function Ensure-HNCSRDColumn {
    <#
    .SYNOPSIS
        Crée ou met à jour une colonne (ou un lookup) d'une liste à partir du modèle.
    .DESCRIPTION
        Création : XML de champ avec Name/StaticName = nom interne et DisplayName = nom interne
        (AddFieldInternalNameHint), puis libellé appliqué ; le nom interne obtenu est contrôlé.
        Mise à jour : comparaison du SchemaXml (Compare-HNCSRDFieldSchema) et correction des écarts
        corrigeables (libellé, obligatoire, index, unicité, description, défaut, choix ordonnés, format,
        min/max/décimales, visibilité formulaires). Type et liste cible d'un lookup ne sont jamais modifiés
        (erreur signalée).
    .PARAMETER Champs
        Table nom interne -> champ (Get-HNCSRDChamps), mise à jour en cas de création.
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)]$Object,
        [Parameter(Mandatory)]$Column,
        [Parameter(Mandatory)]$List,
        [Parameter(Mandatory)][hashtable]$Champs,
        $Model
    )
    if (-not $Model) { $Model = Get-HNCSRDModel }
    $cible = "$($Object.name).$($Column.name)"
    $idCible = $null
    if (Test-HNCSRDLookupType -Type $Column.type) {
        $listeCible = Get-HNCSRDList -Name ([string]$Column.lookup) -Model $Model
        if (-not $listeCible) {
            if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cible -Message "Lookup vers $($Column.lookup) (liste cible à créer)"; return }
            Add-HNCSRDResultat -Statut Erreur -Cible $cible -Message "Liste cible $($Column.lookup) absente"; return
        }
        $champsCible = Get-HNCSRDChamps -List $listeCible
        if (-not $champsCible.ContainsKey($script:ChampAffichageLookup)) {
            Add-HNCSRDResultat -Statut Erreur -Cible $cible -Message "La cible $($Column.lookup) n'a pas de colonne $($script:ChampAffichageLookup) (exécuter l'étape Colonnes)"; return
        }
        $idCible = [string]$listeCible.Id
    }
    if (-not $Champs.ContainsKey([string]$Column.name)) {
        $xml = ConvertTo-HNCSRDFieldXml -Column $Column -LookupListId $idCible -DisplayNameInterne -Model $Model
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cible -Message "Création ($($Column.type))"; return }
        $champ = $List.Fields.AddFieldAsXml($xml, $false, [Microsoft.SharePoint.Client.AddFieldOptions]::AddFieldInternalNameHint)
        [void](Get-PnPProperty -ClientObject $champ -Property InternalName, Title)
        if ([string]$champ.InternalName -cne [string]$Column.name) {
            Add-HNCSRDResultat -Statut Erreur -Cible $cible -Message "Nom interne obtenu « $($champ.InternalName) » différent de « $($Column.name) » (conflit avec un champ existant) : supprimer la colonne et corriger"
            return
        }
        $champ.Title = [string]$Column.label
        $champ.Update(); Invoke-PnPQuery
        $Champs[[string]$Column.name] = $champ
        Add-HNCSRDResultat -Statut Cree -Cible $cible -Message "$($Column.type) « $($Column.label) »"
        return
    }
    $champ = $Champs[[string]$Column.name]
    $attendu = ConvertTo-HNCSRDFieldXml -Column $Column -LookupListId $idCible -Model $Model
    $ecarts = @(Compare-HNCSRDFieldSchema -SchemaActuel (Get-HNCSRDSchemaXml -Field $champ) -SchemaAttendu $attendu)
    if ($ecarts.Count -eq 0) { Add-HNCSRDResultat -Statut Inchange -Cible $cible; return }
    $bloquants = @($ecarts | Where-Object { -not $_.Corrigeable })
    foreach ($b in $bloquants) { Add-HNCSRDResultat -Statut Erreur -Cible $cible -Message ("{0} : attendu « {1} », constaté « {2} » (non modifiable par le script : supprimer puis recréer la colonne, voir README « Changement de type d'une colonne »)" -f $b.Propriete, $b.Attendu, $b.Constate) }
    if ($bloquants.Count -gt 0) { return }
    $texte = ($ecarts | ForEach-Object { '{0} « {1} » -> « {2} »' -f $_.Propriete, $_.Constate, $_.Attendu }) -join ' ; '
    if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cible -Message $texte; return }
    $schema = @($ecarts | Where-Object { $_.Mode -eq 'Schema' })
    if ($schema.Count -gt 0) {
        $docAct = [xml](Get-HNCSRDSchemaXml -Field $champ)
        $docAtt = [xml]$attendu
        $el = $docAct.DocumentElement
        foreach ($e in $schema) {
            if ($e.Propriete -eq 'CHOICES') {
                $ancien = $el.SelectSingleNode('CHOICES'); if ($ancien) { [void]$el.RemoveChild($ancien) }
                $nouveau = $docAtt.DocumentElement.SelectSingleNode('CHOICES')
                if ($nouveau) { [void]$el.AppendChild($docAct.ImportNode($nouveau, $true)) }
            }
            elseif ($e.Attendu -eq '') { $el.RemoveAttribute($e.Propriete) }
            else { $el.SetAttribute($e.Propriete, [string]$e.Attendu) }
        }
        $champ.SchemaXml = $el.OuterXml
        $champ.Update(); Invoke-PnPQuery
        [void](Get-PnPProperty -ClientObject $champ -Property Title, Required, Indexed, EnforceUniqueValues, Description, DefaultValue)
    }
    $base = @($ecarts | Where-Object { $_.Mode -eq 'Base' })
    if ($base.Count -gt 0) {
        $indexAttendu = [bool]$Column.indexed -or [bool]$Column.unique
        $champ.Title = [string]$Column.label
        $champ.Required = [bool]$Column.required
        $desc = ([string]$Column.description).Replace('`', ''); if ($desc.Length -gt 255) { $desc = $desc.Substring(0, 255) }
        $champ.Description = $desc
        $defaut = Get-HNCSRDDefaultValue -Column $Column -Model $Model
        if ($null -eq $defaut) { $champ.DefaultValue = $null } else { $champ.DefaultValue = $defaut }
        if ($indexAttendu) { $champ.Indexed = $true }
        $champ.Update(); Invoke-PnPQuery
        if ([bool]$champ.EnforceUniqueValues -ne [bool]$Column.unique) { $champ.EnforceUniqueValues = [bool]$Column.unique; $champ.Update(); Invoke-PnPQuery }
        if (-not $indexAttendu -and $champ.Indexed) { $champ.Indexed = $false; $champ.Update(); Invoke-PnPQuery }
    }
    $formulaires = @($ecarts | Where-Object { $_.Mode -eq 'Formulaire' })
    if ($formulaires.Count -gt 0) {
        $visible = -not [bool]$Column.hidden
        $champ.SetShowInNewForm($visible); $champ.SetShowInEditForm($visible); $champ.SetShowInDisplayForm($visible)
        $champ.Update(); Invoke-PnPQuery
    }
    Add-HNCSRDResultat -Statut MisAJour -Cible $cible -Message $texte
}

function Set-HNCSRDListValidation {
    <#
    .SYNOPSIS
        Applique ValidationFormula et ValidationMessage de liste (après création de toutes les colonnes).
    .DESCRIPTION
        La formule du modèle (noms internes, syntaxe invariante) est traduite en noms affichés de la liste
        (ConvertTo-HNCSRDValidationFormula). Une formule présente sur SharePoint mais absente du modèle est
        signalée (non supprimée).
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Object, [Parameter(Mandatory)]$List)
    [void](Get-PnPProperty -ClientObject $List -Property ValidationFormula, ValidationMessage)
    $cible = "$($Object.name) (validation)"
    if (-not $Object.validation) {
        if ($List.ValidationFormula) { Add-HNCSRDResultat -Statut Avertissement -Cible $cible -Message "Formule présente mais absente du modèle (conservée) : $($List.ValidationFormula)" }
        return
    }
    $champs = Get-HNCSRDChamps -List $List
    $noms = @{}
    foreach ($k in $champs.Keys) { $noms[$k] = [string]$champs[$k].Title }
    foreach ($ref in (Get-HNCSRDValidationColumns -Formula ([string]$Object.validation))) {
        if (-not $noms.ContainsKey($ref)) { Add-HNCSRDResultat -Statut Erreur -Cible $cible -Message "Colonne $ref absente (exécuter l'étape Colonnes)"; return }
    }
    $formule = ConvertTo-HNCSRDValidationFormula -Formula ([string]$Object.validation) -NomsAffiches $noms
    $message = [string]$Object.validationMessage
    $actuelle = [string]$List.ValidationFormula
    if (($actuelle -ceq $formule -or $actuelle -ceq [string]$Object.validation) -and [string]$List.ValidationMessage -ceq $message) { Add-HNCSRDResultat -Statut Inchange -Cible $cible; return }
    if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cible -Message $formule; return }
    $List.ValidationFormula = $formule
    $List.ValidationMessage = $message
    $List.Update(); Invoke-PnPQuery
    Add-HNCSRDResultat -Statut MisAJour -Cible $cible -Message $formule
}

function Ensure-HNCSRDView {
    <#
    .SYNOPSIS
        Crée ou met à jour une vue (même nom) à partir du modèle ; positionne la vue par défaut.
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Object, [Parameter(Mandatory)]$View, [Parameter(Mandatory)]$List, [int]$Lot = 5)
    $cible = "$($Object.name) / $($View.name)"
    $types = Get-HNCSRDColumnTypes -Object $Object -Lot $Lot
    try { $caml = ConvertTo-HNCSRDCaml -View $View -ColumnTypes $types -ListKind ([string]$Object.kind) }
    catch { Add-HNCSRDResultat -Statut Erreur -Cible $cible -Message $_.Exception.Message; return }
    $vues = @(Get-PnPView -List $List)
    $existante = @($vues | Where-Object { $_.Title -eq $caml.Name }) | Select-Object -First 1
    if (-not $existante) {
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cible -Message 'Création'; return }
        $p = @{ List = $List; Title = $caml.Name; Fields = $caml.ViewFields; Query = $caml.Query; RowLimit = $caml.RowLimit; Paged = $true; ErrorAction = 'Stop' }
        if ($caml.Default) { $p['SetAsDefault'] = $true }
        Add-PnPView @p | Out-Null
        Add-HNCSRDResultat -Statut Cree -Cible $cible
        return
    }
    [void](Get-PnPProperty -ClientObject $existante -Property ViewFields, ViewQuery, RowLimit, DefaultView, Paged)
    $diffs = @()
    if ((@($existante.ViewFields) -join ',') -ne ($caml.ViewFields -join ',')) { $diffs += 'colonnes' }
    if ((Format-HNCSRDCamlNormalise $existante.ViewQuery) -ne (Format-HNCSRDCamlNormalise $caml.Query)) { $diffs += 'requête' }
    if ([int]$existante.RowLimit -ne $caml.RowLimit -or -not $existante.Paged) { $diffs += 'pagination' }
    if ($caml.Default -and -not $existante.DefaultView) { $diffs += 'vue par défaut' }
    if ($diffs.Count -eq 0) { Add-HNCSRDResultat -Statut Inchange -Cible $cible; return }
    if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cible -Message ($diffs -join ', '); return }
    $valeurs = @{ ViewQuery = $caml.Query; RowLimit = [uint32]$caml.RowLimit; Paged = $true }
    if ($caml.Default) { $valeurs['DefaultView'] = $true }
    Set-PnPView -List $List -Identity $existante.Id -Fields $caml.ViewFields -Values $valeurs -ErrorAction Stop | Out-Null
    Add-HNCSRDResultat -Statut MisAJour -Cible $cible -Message ($diffs -join ', ')
}

function Sync-HNCSRDAttributions {
    <#
    .SYNOPSIS
        Rend les attributions d'un objet sécurisable (site ou liste) strictement égales aux attendues.
    .DESCRIPTION
        Ajoute les attributions manquantes, retire les attributions non prévues (journalisées « Retire »).
        Les niveaux masqués (Accès limité, posés automatiquement par SharePoint pour les permissions par
        élément ou dossier des flux) ne sont jamais retirés.
    .PARAMETER Attendues
        Table nom de groupe -> code de niveau (FC, CSS, R).
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Securable, [Parameter(Mandatory)]$Attendues, [Parameter(Mandatory)][string]$Cible, $Model)
    $noms = New-Object System.Collections.Specialized.OrderedDictionary
    foreach ($k in $Attendues.Keys) {
        $nomRole = Get-HNCSRDRoleDefinitionName -Code ([string]$Attendues[$k]) -Model $Model
        if (-not $nomRole) {
            if (Test-HNCSRDSimulation) { $nomRole = [string]$Attendues[$k] }
            else { Add-HNCSRDResultat -Statut Erreur -Cible $Cible -Message "Niveau $($Attendues[$k]) introuvable (exécuter l'étape NiveauxAutorisation)"; return }
        }
        $noms[$k] = $nomRole
    }
    $etat = @(Get-HNCSRDEtatAttributions -Securable $Securable)
    $cmp = Compare-HNCSRDAttributions -Etat $etat -Attendues $noms
    if ($cmp.AAjouter.Count -eq 0 -and $cmp.ARetirer.Count -eq 0) { Add-HNCSRDResultat -Statut Inchange -Cible $Cible; return }
    $ctx = Get-PnPContext
    foreach ($a in $cmp.AAjouter) {
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $Cible -Message "Ajout $($a.Nom) : $($a.Role)"; continue }
        $grp = Get-PnPGroup -Identity $a.Nom -ErrorAction SilentlyContinue
        if (-not $grp) { Add-HNCSRDResultat -Statut Erreur -Cible $Cible -Message "Groupe $($a.Nom) introuvable (exécuter l'étape Groupes)"; continue }
        $rd = Get-PnPRoleDefinition -Identity $a.Role -ErrorAction Stop
        $liaisons = New-Object Microsoft.SharePoint.Client.RoleDefinitionBindingCollection($ctx)
        $liaisons.Add($rd)
        [void]$Securable.RoleAssignments.Add($grp, $liaisons)
        Invoke-PnPQuery
        Add-HNCSRDResultat -Statut MisAJour -Cible $Cible -Message "Ajout $($a.Nom) : $($a.Role)"
    }
    if ($cmp.ARetirer.Count -gt 0) {
        $etat = @(Get-HNCSRDEtatAttributions -Securable $Securable)
        foreach ($r in $cmp.ARetirer) {
            $msg = "Attribution non prévue retirée : $($r.Nom) ($($r.Type)) : $($r.Role)"
            if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $Cible -Message $msg; continue }
            $e = @($etat | Where-Object { $_.Nom -eq $r.Nom -and $_.Type -eq $r.Type }) | Select-Object -First 1
            if (-not $e) { continue }
            $ra = $e.Attribution
            $liaison = @($ra.RoleDefinitionBindings | Where-Object { $_.Name -eq $r.Role }) | Select-Object -First 1
            if (-not $liaison) { continue }
            $restantes = @($ra.RoleDefinitionBindings).Count - 1
            if ($restantes -le 0) { $ra.DeleteObject() }
            else { $ra.RoleDefinitionBindings.Remove($liaison); $ra.Update() }
            Invoke-PnPQuery
            $etat = @(Get-HNCSRDEtatAttributions -Securable $Securable)
            Add-HNCSRDResultat -Statut Retire -Cible $Cible -Message $msg
        }
    }
}

function Set-HNCSRDListPermissions {
    <#
    .SYNOPSIS
        Rompt l'héritage d'une liste/bibliothèque sans copier les attributions puis applique exactement la
        matrice d'accès (§ 7.3).
    .DESCRIPTION
        L'héritage n'est rompu qu'une fois (les permissions uniques des éléments et dossiers posées par les
        flux ne sont jamais effacées : clearSubscopes = false).
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Object, [Parameter(Mandatory)]$List, $Model)
    if (-not $Model) { $Model = Get-HNCSRDModel }
    $cible = "$($Object.name) (permissions)"
    [void](Get-PnPProperty -ClientObject $List -Property HasUniqueRoleAssignments)
    if (-not $List.HasUniqueRoleAssignments) {
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cible -Message "Rupture d'héritage sans copie" }
        else {
            $List.BreakRoleInheritance($false, $false)
            Invoke-PnPQuery
            Add-HNCSRDResultat -Statut MisAJour -Cible $cible -Message "Héritage rompu sans copie des attributions"
        }
    }
    $attendues = Get-HNCSRDAttributionsAttendues -ObjectName $Object.name -Model $Model
    Sync-HNCSRDAttributions -Securable $List -Attendues $attendues -Cible $cible -Model $Model
}

function Set-HNCSRDSitePermissions {
    <#
    .SYNOPSIS
        Attributions du site : groupe propriétaire = FC, autres groupes = R (§ 7.2) ; retire les autres.
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Model)
    $web = Get-PnPWeb -ErrorAction Stop
    Sync-HNCSRDAttributions -Securable $web -Attendues (Get-HNCSRDAttributionsSite -Model $Model) -Cible 'Site (permissions)' -Model $Model
    Clear-HNCSRDGroupesParDefaut -Model $Model
}

function Get-HNCSRDGroupesParDefaut {
    <#
    .SYNOPSIS
        Groupes SharePoint créés par défaut avec le site (propriétaires, membres et visiteurs associés),
        hors groupes du modèle.
    #>
    [CmdletBinding()]
    param($Model)
    if (-not $Model) { $Model = Get-HNCSRDModel }
    $noms = @($Model.groups | ForEach-Object { [string]$_.name })
    $r = New-Object System.Collections.Generic.List[object]
    foreach ($bascule in @('AssociatedOwnerGroup', 'AssociatedMemberGroup', 'AssociatedVisitorGroup')) {
        $p = @{ ErrorAction = 'SilentlyContinue' }
        $p[$bascule] = $true
        $g = $null
        try { $g = Get-PnPGroup @p } catch { $g = $null }
        if (-not $g) { continue }
        if ($noms -contains [string]$g.Title) { continue }
        if (@($r | Where-Object { $_.Id -eq $g.Id }).Count -gt 0) { continue }
        $r.Add($g)
    }
    return $r.ToArray()
}

function Clear-HNCSRDGroupesParDefaut {
    <#
    .SYNOPSIS
        Vide les groupes SharePoint par défaut du site (spec § 7.2, v1.2.0 : « restent vides et sans
        attribution ») ; ils ne sont jamais supprimés. Leurs attributions au site sont retirées par
        Sync-HNCSRDAttributions (Set-HNCSRDSitePermissions).
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param($Model)
    foreach ($g in @(Get-HNCSRDGroupesParDefaut -Model $Model)) {
        $cible = "Groupe par défaut $($g.Title)"
        $membres = @(Get-PnPGroupMember -Group $g.Title)
        if ($membres.Count -eq 0) { Add-HNCSRDResultat -Statut Inchange -Cible $cible -Message 'Vide'; continue }
        foreach ($m in $membres) {
            if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cible -Message "Retrait de $($m.LoginName)"; continue }
            Remove-PnPGroupMember -Group $g.Title -LoginName $m.LoginName -ErrorAction Stop
            Add-HNCSRDResultat -Statut Retire -Cible $cible -Message "Membre retiré : $($m.LoginName) (groupe par défaut laissé vide)"
        }
    }
}

function Get-HNCSRDItemsParCle {
    <#
    .SYNOPSIS
        Éléments d'une liste indexés par la valeur d'un champ clé (chaîne).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$List, [Parameter(Mandatory)][string]$Champ)
    $t = @{}
    foreach ($i in @(Get-PnPListItem -List $List -PageSize 500)) {
        $v = [string]$i[$Champ]
        if ($v -and -not $t.ContainsKey($v)) { $t[$v] = $i }
    }
    return $t
}

function Resolve-HNCSRDLookupId {
    <#
    .SYNOPSIS
        Résout l'ID SharePoint d'un élément à partir de son IdHNCS.
    .PARAMETER List
        Nom interne de la liste du modèle (ex. Poles).
    .PARAMETER IdHNCS
        Identifiant métier (ex. POL-P1).
    .OUTPUTS
        ID (int) ou $null si l'élément n'existe pas.
    .EXAMPLE
        Resolve-HNCSRDLookupId -List Poles -IdHNCS POL-P2
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$List, [Parameter(Mandatory)][string]$IdHNCS, [switch]$SansCache, $Connection)
    $cle = "$List|$IdHNCS"
    if (-not $SansCache -and $script:HNCSRD.CacheLookup.ContainsKey($cle)) { return $script:HNCSRD.CacheLookup[$cle] }
    $url = Get-HNCSRDListUrl -Name $List
    $q = "<View><Query><Where><Eq><FieldRef Name='IdHNCS' /><Value Type='Text'>" + (ConvertTo-HNCSRDXmlText $IdHNCS) + "</Value></Eq></Where></Query><RowLimit>2</RowLimit></View>"
    $p = @{ List = $url; Query = $q; ErrorAction = 'Stop' }
    if ($Connection) { $p['Connection'] = $Connection }
    $items = @(Get-PnPListItem @p)
    if ($items.Count -eq 0) { return $null }
    if ($items.Count -gt 1) { throw "IdHNCS non unique dans $List : $IdHNCS" }
    $id = [int]$items[0].Id
    $script:HNCSRD.CacheLookup[$cle] = $id
    return $id
}

function ConvertTo-HNCSRDValeurChamp {
    <#
    .SYNOPSIS
        Convertit une valeur texte de seed (spec) en valeur PnP selon le type de la colonne.
    .DESCRIPTION
        Lookup : IdHNCS -> ID SharePoint ; Boolean : Oui/Non ; Number : invariant ; MultiChoice : « ; » ;
        Choice / MultiChoice : valeurs contrôlées par l'énumération.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Type, $Column, [AllowEmptyString()][string]$Valeur, $Model)
    switch ($Type) {
        'Lookup' {
            $id = Resolve-HNCSRDLookupId -List ([string]$Column.lookup) -IdHNCS $Valeur
            if ($null -eq $id) { throw "Élément $Valeur introuvable dans $($Column.lookup)" }
            return $id
        }
        'LookupMulti' {
            $ids = @()
            foreach ($v in ($Valeur -split ';')) { if ($v.Trim()) { $ids += (ConvertTo-HNCSRDValeurChamp -Type 'Lookup' -Column $Column -Valeur $v.Trim() -Model $Model) } }
            return , $ids
        }
        'Boolean' { return (ConvertTo-HNCSRDBoolean -Valeur $Valeur) }
        'Number' { return [double]::Parse($Valeur, [System.Globalization.CultureInfo]::InvariantCulture) }
        'Choice' {
            if ($Column -and $Column.enum -and -not ((Get-HNCSRDEnumValues -Code $Column.enum -Model $Model) -contains $Valeur)) { throw "Valeur « $Valeur » hors énumération $($Column.enum)" }
            return $Valeur
        }
        'MultiChoice' {
            $vals = @($Valeur -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
            if ($Column -and $Column.enum) {
                $enum = Get-HNCSRDEnumValues -Code $Column.enum -Model $Model
                foreach ($v in $vals) { if ($enum -notcontains $v) { throw "Valeur « $v » hors énumération $($Column.enum)" } }
            }
            return , ([string[]]$vals)
        }
    }
    return $Valeur
}

function Ensure-HNCSRDParameters {
    <#
    .SYNOPSIS
        Injecte les paramètres du modèle dans la liste Parametres (clé = Title). Une valeur non vide n'est
        jamais écrasée ; une valeur vide est complétée lorsque la configuration la fournit
        (specs/referentiels-initiaux.md, v1.2.0). Les marqueurs <BoiteRD>, <EmailAdministration>… sont
        remplacés depuis Config.Parametres.
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Model, [Parameter(Mandatory)]$Config)
    $liste = Get-HNCSRDList -Name 'Parametres' -Model $Model
    if (-not $liste) {
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible 'Parametres' -Message "$(@($Model.parameters).Count) paramètres (liste à créer)"; return }
        Add-HNCSRDResultat -Statut Erreur -Cible 'Parametres' -Message 'Liste absente'; return
    }
    $existants = Get-HNCSRDItemsParCle -List $liste -Champ 'Title'
    $categories = Get-HNCSRDEnumValues -Code ((Get-HNCSRDObject -Name 'Parametres' -Model $Model).columns | Where-Object { $_.name -eq 'Categorie' }).enum -Model $Model
    foreach ($p in $Model.parameters) {
        $cle = [string]$p.key
        $r = Resolve-HNCSRDMarqueurs -Valeur ([string]$p.value) -Config $Config
        if ($existants.ContainsKey($cle)) {
            $valeurActuelle = [string]$existants[$cle]['Valeur']
            if ($valeurActuelle -eq '' -and $r.Valeur -and $r.NonResolus.Count -eq 0) {
                if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cle -Message "Valeur vide complétée : « $($r.Valeur) »"; continue }
                Set-PnPListItem -List $liste -Identity $existants[$cle].Id -Values @{ Valeur = [string]$r.Valeur } -ErrorAction Stop | Out-Null
                Add-HNCSRDResultat -Statut MisAJour -Cible $cle -Message "Valeur vide complétée depuis la configuration : « $($r.Valeur) »"
                continue
            }
            $msg = 'Valeur existante conservée (jamais écrasée)'
            if ($valeurActuelle -eq '') { $msg = 'Valeur vide (aucune valeur fournie par la configuration)' }
            elseif ($valeurActuelle -match '<[A-Za-z]+>') { $msg += ' ; contient encore un marqueur non résolu : corriger à la main' }
            Add-HNCSRDResultat -Statut Inchange -Cible $cle -Message $msg
            continue
        }
        if ($categories -notcontains [string]$p.category) { Add-HNCSRDResultat -Statut Erreur -Cible $cle -Message "Catégorie hors énumération : $($p.category)"; continue }
        if ($r.NonResolus.Count -gt 0) { Add-HNCSRDResultat -Statut Avertissement -Cible $cle -Message ("Marqueur(s) absent(s) de la configuration : " + ($r.NonResolus -join ', ')) }
        elseif (([string]$p.value) -match '<' -and -not $r.Valeur) { Add-HNCSRDResultat -Statut Avertissement -Cible $cle -Message 'Valeur vide dans la configuration (à renseigner dans la liste)' }
        $valeurs = @{ Title = $cle; Categorie = [string]$p.category; Description = ([string]$p.description).Replace('`', '') }
        if ($r.Valeur) { $valeurs['Valeur'] = [string]$r.Valeur }
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cle -Message "Valeur « $($r.Valeur) »"; continue }
        Add-PnPListItem -List $liste -Values $valeurs -ErrorAction Stop | Out-Null
        Add-HNCSRDResultat -Statut Cree -Cible $cle -Message "Valeur « $($r.Valeur) »"
    }
}

function Get-HNCSRDSeedCle {
    <#
    .SYNOPSIS
        Clé de rapprochement d'un référentiel initial (spec § 2.2, v1.6.0 ; fonction pure).
    .DESCRIPTION
        Recherche de l'existant par Code si les lignes en portent un (ModelesActions), sinon par Title.
        ChampReserve = IdHNCS si les lignes portent un identifiant réservé (Poles : POL-Px ; autres : plage
        0001-0099 de 2026), sinon $null.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][AllowEmptyCollection()][object[]]$Lignes)
    $champs = @()
    if ($Lignes.Count -gt 0) { $champs = @($Lignes[0].PSObject.Properties.Name) }
    $recherche = 'Title'
    if ($champs -contains 'Code') { $recherche = 'Code' }
    $reserve = $null
    if ($champs -contains 'IdHNCS') { $reserve = 'IdHNCS' }
    return [pscustomobject]@{ ChampRecherche = $recherche; ChampReserve = $reserve }
}

function Resolve-HNCSRDSeedAction {
    <#
    .SYNOPSIS
        Décide du traitement d'une ligne de référentiel initial (fonction pure, spec § 2.2, v1.6.0).
    .PARAMETER ParRecherche
        Table valeur de la clé de recherche (Title ou Code) -> { Id ; IdHNCS } des éléments existants.
    .PARAMETER ParIdHNCS
        Table IdHNCS non vide -> { Id ; Cle } des éléments existants.
    .OUTPUTS
        { Action = Creer | Inchange | RenseignerId | Erreur ; ItemId ; Message }.
        L'existant n'est jamais écrasé : seul un IdHNCS vide est complété par l'identifiant réservé ; un
        identifiant réservé déjà porté par un autre élément est une erreur.
    #>
    [CmdletBinding()]
    param(
        [AllowEmptyString()][string]$Cle,
        [AllowEmptyString()][string]$IdReserve,
        [Parameter(Mandatory)][hashtable]$ParRecherche,
        [Parameter(Mandatory)][hashtable]$ParIdHNCS
    )
    $resultat = { param($a, $i, $m) [pscustomobject]@{ Action = $a; ItemId = $i; Message = $m } }
    $autre = $null
    if ($IdReserve -and $ParIdHNCS.ContainsKey($IdReserve)) { $autre = $ParIdHNCS[$IdReserve] }
    if ($ParRecherche.ContainsKey($Cle)) {
        $ex = $ParRecherche[$Cle]
        $idActuel = [string]$ex.IdHNCS
        if (-not $IdReserve -or $idActuel -ceq $IdReserve) { return (& $resultat 'Inchange' $ex.Id 'Existant conservé (jamais écrasé)') }
        if ($idActuel) { return (& $resultat 'Erreur' $ex.Id ("L'élément existant (ID {0}) porte l'identifiant {1} au lieu de l'identifiant réservé {2}" -f $ex.Id, $idActuel, $IdReserve)) }
        if ($autre -and [int]$autre.Id -ne [int]$ex.Id) { return (& $resultat 'Erreur' $ex.Id ("Identifiant réservé {0} déjà porté par un autre élément (ID {1}, « {2} »)" -f $IdReserve, $autre.Id, $autre.Cle)) }
        return (& $resultat 'RenseignerId' $ex.Id ("IdHNCS vide complété par l'identifiant réservé {0}" -f $IdReserve))
    }
    if ($autre) { return (& $resultat 'Erreur' $autre.Id ("Identifiant réservé {0} déjà porté par un autre élément (ID {1}, « {2} »)" -f $IdReserve, $autre.Id, $autre.Cle)) }
    return (& $resultat 'Creer' $null 'Création')
}

function Ensure-HNCSRDSeeds {
    <#
    .SYNOPSIS
        Injecte les référentiels initiaux (seeds du modèle : Poles, DomainesCibles, ModelesActions,
        RegistreModeles) sans jamais écraser un élément existant.
    .DESCRIPTION
        Identifiants réservés (spec § 2.2, v1.6.0) : l'existant est recherché par Title (Code pour
        ModelesActions) ; un IdHNCS vide reçoit l'identifiant réservé ; un identifiant réservé déjà porté par
        un autre élément est une erreur (Resolve-HNCSRDSeedAction).
        Les marqueurs <…> sont résolus depuis Config.Parametres (ex. RegistreModeles.Proprietaire =
        <EmailDirectionRD>) ; les lookups sont résolus par IdHNCS (ex. POL-P2 -> ID du pôle). Les éléments
        créés avec un Statut reçoivent StatutPrecedent = Statut et DateStatut = date du déploiement
        (spec § 11, v1.2.0).
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Model, [Parameter(Mandatory)]$Config, [int]$Lot = 5)
    foreach ($s in $Model.seeds.PSObject.Properties) {
        $nomListe = $s.Name
        $objet = Get-HNCSRDObject -Name $nomListe -Model $Model
        if ([int]$objet.lot -gt $Lot) { Write-HNCSRDLog -Message "Seeds $nomListe ignorés (lot $($objet.lot) > $Lot)" -Niveau Detail; continue }
        $liste = Get-HNCSRDList -Name $nomListe -Model $Model
        $lignes = @($s.Value)
        if ($lignes.Count -eq 0) { continue }
        $champsLigne = @($lignes[0].PSObject.Properties.Name)
        $seedCle = Get-HNCSRDSeedCle -Lignes $lignes
        $champCle = $seedCle.ChampRecherche
        if (-not $liste) {
            if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $nomListe -Message "$($lignes.Count) éléments (liste à créer)"; continue }
            Add-HNCSRDResultat -Statut Erreur -Cible $nomListe -Message 'Liste absente'; continue
        }
        $types = Get-HNCSRDColumnTypes -Object $objet -Lot $Lot
        $parRecherche = @{}; $parId = @{}
        foreach ($it in @(Get-PnPListItem -List $liste -PageSize 500)) {
            $vc = [string]$it[$champCle]
            $vi = ''
            if ($seedCle.ChampReserve) { $vi = [string]$it['IdHNCS'] }
            if ($vc) {
                if ($parRecherche.ContainsKey($vc)) { Add-HNCSRDResultat -Statut Avertissement -Cible "$nomListe / $vc" -Message "Plusieurs éléments portent ce $champCle (ID $($parRecherche[$vc].Id) retenu, ID $($it.Id) ignoré)" }
                else { $parRecherche[$vc] = [pscustomobject]@{ Id = [int]$it.Id; IdHNCS = $vi } }
            }
            if ($vi -and -not $parId.ContainsKey($vi)) { $parId[$vi] = [pscustomobject]@{ Id = [int]$it.Id; Cle = $vc } }
        }
        $dateDeploiement = Get-Date
        foreach ($ligne in $lignes) {
            $cle = [string]$ligne.$champCle
            $idReserve = ''
            if ($seedCle.ChampReserve) { $idReserve = [string]$ligne.IdHNCS }
            $cible = "$nomListe / $cle"
            if ($idReserve) { $cible = "$cible ($idReserve)" }
            $decision = Resolve-HNCSRDSeedAction -Cle $cle -IdReserve $idReserve -ParRecherche $parRecherche -ParIdHNCS $parId
            if ($decision.Action -eq 'Inchange') { Add-HNCSRDResultat -Statut Inchange -Cible $cible -Message $decision.Message; continue }
            if ($decision.Action -eq 'Erreur') { Add-HNCSRDResultat -Statut Erreur -Cible $cible -Message $decision.Message; continue }
            if ($decision.Action -eq 'RenseignerId') {
                if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cible -Message $decision.Message; continue }
                try {
                    Set-PnPListItem -List $liste -Identity $decision.ItemId -Values @{ IdHNCS = $idReserve } -ErrorAction Stop | Out-Null
                    $parId[$idReserve] = [pscustomobject]@{ Id = [int]$decision.ItemId; Cle = $cle }
                    $script:HNCSRD.CacheLookup.Remove("$nomListe|$idReserve")
                    Add-HNCSRDResultat -Statut MisAJour -Cible $cible -Message $decision.Message
                }
                catch { Add-HNCSRDResultat -Statut Erreur -Cible $cible -Message $_.Exception.Message }
                continue
            }
            try {
                $valeurs = @{}
                foreach ($nomChamp in $champsLigne) {
                    $brut = [string]$ligne.$nomChamp
                    if ($brut -eq '') { continue }
                    $rm = Resolve-HNCSRDMarqueurs -Valeur $brut -Config $Config
                    if ($rm.NonResolus.Count -gt 0) { throw ("Marqueur(s) absent(s) de la configuration pour {0} : {1}" -f $nomChamp, ($rm.NonResolus -join ', ')) }
                    $brut = [string]$rm.Valeur
                    if ($brut -eq '') { throw "Valeur vide dans la configuration pour $nomChamp" }
                    if (-not $types.ContainsKey($nomChamp)) { throw "Colonne $nomChamp absente de $nomListe" }
                    $col = $null
                    if ($nomChamp -ne 'Title') { $col = @($objet.columns | Where-Object { $_.name -eq $nomChamp })[0] }
                    if ((Test-HNCSRDSimulation) -and (Test-HNCSRDLookupType -Type $types[$nomChamp])) { $valeurs[$nomChamp] = $brut; continue }
                    $valeurs[$nomChamp] = ConvertTo-HNCSRDValeurChamp -Type $types[$nomChamp] -Column $col -Valeur $brut -Model $Model
                }
                if ($valeurs.ContainsKey('Statut') -and $types.ContainsKey('StatutPrecedent')) { $valeurs['StatutPrecedent'] = [string]$valeurs['Statut'] }
                if ($valeurs.ContainsKey('Statut') -and $types.ContainsKey('DateStatut')) { $valeurs['DateStatut'] = $dateDeploiement }
                if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cible -Message 'Création'; continue }
                Add-PnPListItem -List $liste -Values $valeurs -ErrorAction Stop | Out-Null
                Add-HNCSRDResultat -Statut Cree -Cible $cible
            }
            catch { Add-HNCSRDResultat -Statut Erreur -Cible $cible -Message $_.Exception.Message }
        }
    }
}

function Get-HNCSRDTransitionValeurs {
    <#
    .SYNOPSIS
        Valeurs attendues d'un élément TransitionsStatuts pour une transition du modèle (fonction pure).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Transition)
    return [ordered]@{
        Title           = [string]$Transition.code
        Objet           = [string]$Transition.object
        StatutDe        = [string]$Transition.from
        StatutVers      = [string]$Transition.to
        Acteurs         = [string[]]@($Transition.actors)
        Controle        = (@($Transition.controls) -join ';')
        FluxResponsable = [string]$Transition.flow
        Actif           = $true
    }
}

function Compare-HNCSRDTransitionItem {
    <#
    .SYNOPSIS
        Champs d'un élément TransitionsStatuts qui diffèrent des valeurs attendues.
    .OUTPUTS
        Table nom de champ -> valeur attendue (vide si conforme).
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Item, [Parameter(Mandatory)]$Attendu)
    $diffs = @{}
    foreach ($k in $Attendu.Keys) {
        if ($k -eq 'Title') { continue }
        $a = $Attendu[$k]; $c = $Item[$k]
        if ($k -eq 'Acteurs') {
            if ((@($c) | Where-Object { $_ }) -join ';' -cne (@($a) -join ';')) { $diffs[$k] = $a }
        }
        elseif ($k -eq 'Actif') { if ([bool]$c -ne [bool]$a) { $diffs[$k] = $a } }
        else { if ([string]$c -cne [string]$a) { $diffs[$k] = $a } }
    }
    return $diffs
}

function Sync-HNCSRDTransitions {
    <#
    .SYNOPSIS
        Synchronise la liste TransitionsStatuts avec les transitions du modèle (clé = code).
    .DESCRIPTION
        Ajoute les codes manquants, met à jour les écarts, passe Actif = Non pour les codes disparus du
        modèle. Aucun élément n'est jamais supprimé.
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Model)
    $liste = Get-HNCSRDList -Name 'TransitionsStatuts' -Model $Model
    if (-not $liste) {
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible 'TransitionsStatuts' -Message "$(@($Model.transitions).Count) transitions (liste à créer)"; return }
        Add-HNCSRDResultat -Statut Erreur -Cible 'TransitionsStatuts' -Message 'Liste absente'; return
    }
    $roles = Get-HNCSRDEnumValues -Code 'ROLE' -Model $Model
    $objetsEnum = Get-HNCSRDEnumValues -Code 'OBJET_TRANSITION' -Model $Model
    $existants = Get-HNCSRDItemsParCle -List $liste -Champ 'Title'
    $codes = @{}
    foreach ($t in $Model.transitions) {
        $code = [string]$t.code
        $codes[$code] = $true
        $attendu = Get-HNCSRDTransitionValeurs -Transition $t
        $horsEnum = @($attendu.Acteurs | Where-Object { $roles -notcontains $_ })
        if ($horsEnum.Count -gt 0 -or $objetsEnum -notcontains $attendu.Objet) { Add-HNCSRDResultat -Statut Erreur -Cible $code -Message 'Rôle ou objet hors énumération'; continue }
        if (-not $existants.ContainsKey($code)) {
            if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $code -Message 'Création'; continue }
            $v = @{}; foreach ($k in $attendu.Keys) { $v[$k] = $attendu[$k] }
            if (-not $v['Controle']) { $v.Remove('Controle') }
            Add-PnPListItem -List $liste -Values $v -ErrorAction Stop | Out-Null
            Add-HNCSRDResultat -Statut Cree -Cible $code
            continue
        }
        $diffs = Compare-HNCSRDTransitionItem -Item $existants[$code] -Attendu $attendu
        if ($diffs.Count -eq 0) { Add-HNCSRDResultat -Statut Inchange -Cible $code; continue }
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $code -Message ('Mise à jour : ' + (@($diffs.Keys) -join ', ')); continue }
        Set-PnPListItem -List $liste -Identity $existants[$code].Id -Values $diffs -ErrorAction Stop | Out-Null
        Add-HNCSRDResultat -Statut MisAJour -Cible $code -Message (@($diffs.Keys) -join ', ')
    }
    foreach ($code in $existants.Keys) {
        if ($codes.ContainsKey($code)) { continue }
        if (-not [bool]$existants[$code]['Actif']) { Add-HNCSRDResultat -Statut Inchange -Cible $code -Message 'Absente du modèle, déjà inactive'; continue }
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $code -Message 'Absente du modèle : Actif = Non'; continue }
        Set-PnPListItem -List $liste -Identity $existants[$code].Id -Values @{ Actif = $false } -ErrorAction Stop | Out-Null
        Add-HNCSRDResultat -Statut MisAJour -Cible $code -Message 'Absente du modèle : Actif = Non (jamais supprimée)'
    }
}

function Ensure-HNCSRDNavigation {
    <#
    .SYNOPSIS
        Navigation rapide du site regroupée par domaine (Get-HNCSRDNavigationPlan) ; idempotente.
    .DESCRIPTION
        Les en-têtes sont des nœuds sans lien ; les liens pointent vers la vue par défaut de chaque liste.
        Les nœuds existants hors plan ne sont pas supprimés.
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Model, [Parameter(Mandatory)][int]$Lot)
    $plan = Get-HNCSRDNavigationPlan -Lot $Lot -Model $Model
    $racine = @(Get-PnPNavigationNode -Location QuickLaunch)
    foreach ($entete in $plan) {
        $noeud = @($racine | Where-Object { $_.Title -eq $entete.Titre }) | Select-Object -First 1
        if (-not $noeud) {
            if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible "Navigation / $($entete.Titre)" -Message 'Création de l''en-tête'; continue }
            $noeud = Add-PnPNavigationNode -Location QuickLaunch -Title $entete.Titre -Url $script:EnteteSansLien -ErrorAction Stop
            Add-HNCSRDResultat -Statut Cree -Cible "Navigation / $($entete.Titre)"
        }
        $enfants = @(Get-PnPProperty -ClientObject $noeud -Property Children)
        foreach ($lien in $entete.Liens) {
            $cible = "Navigation / $($entete.Titre) / $($lien.Titre)"
            $liste = Get-HNCSRDList -Name $lien.Objet -Model $Model
            if (-not $liste) { Add-HNCSRDResultat -Statut Avertissement -Cible $cible -Message 'Liste absente, lien non créé'; continue }
            [void](Get-PnPProperty -ClientObject $liste -Property DefaultViewUrl)
            $url = [string]$liste.DefaultViewUrl
            $existant = @($enfants | Where-Object { $_.Title -eq $lien.Titre }) | Select-Object -First 1
            if ($existant -and ([string]$existant.Url).TrimEnd('/') -ieq $url.TrimEnd('/')) { Add-HNCSRDResultat -Statut Inchange -Cible $cible; continue }
            if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible $cible -Message $url; continue }
            if ($existant) { Remove-PnPNavigationNode -Identity $existant.Id -Force -ErrorAction Stop }
            Add-PnPNavigationNode -Location QuickLaunch -Title $lien.Titre -Url $url -Parent $noeud.Id -ErrorAction Stop | Out-Null
            if ($existant) { Add-HNCSRDResultat -Statut MisAJour -Cible $cible -Message $url } else { Add-HNCSRDResultat -Statut Cree -Cible $cible -Message $url }
        }
    }
}

function Ensure-HNCSRDTeam {
    <#
    .SYNOPSIS
        Crée (si Teams.Creer = true) une équipe Teams séparée avec les canaux Comité R&D et Alternants et un
        onglet « site web » vers le site HNCS-RD dans le canal Général. Ce n'est PAS le référentiel.
    .DESCRIPTION
        Exige des permissions Microsoft Graph sur l'application Entra (Group.ReadWrite.All,
        Channel.Create, TeamsTab.Create ou équivalents délégués).
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Config, [Parameter(Mandatory)]$Model)
    if (-not ($Config.Teams -and [bool]$Config.Teams.Creer)) { Add-HNCSRDResultat -Statut Inchange -Cible 'Teams' -Message 'Teams.Creer = false : étape ignorée'; return }
    $nom = [string]$Config.Teams.NomEquipe
    if (-not $nom) { $nom = 'HNCS R&D' }
    $equipe = $null
    try { $equipe = Get-PnPTeamsTeam -Identity $nom -ErrorAction Stop } catch { $equipe = $null }
    if (-not $equipe) {
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible "Teams / $nom" -Message ("Création (canaux : {0})" -f ($script:CanauxTeams -join ', ')); return }
        $p = @{ DisplayName = $nom; Description = "Espace de collaboration R&D HNCS (référentiel : $($Config.SiteUrl))"; Visibility = 'Private'; ErrorAction = 'Stop' }
        if ($Config.SiteOwner) { $p['Owners'] = @([string]$Config.SiteOwner) }
        New-PnPTeamsTeam @p | Out-Null
        $equipe = Get-PnPTeamsTeam -Identity $nom -ErrorAction Stop
        Add-HNCSRDResultat -Statut Cree -Cible "Teams / $nom"
    }
    else { Add-HNCSRDResultat -Statut Inchange -Cible "Teams / $nom" }
    $idEquipe = [string]$equipe.GroupId
    if (-not $idEquipe) { $idEquipe = [string]$equipe.Id }
    $canaux = @(Get-PnPTeamsChannel -Team $idEquipe)
    foreach ($c in $script:CanauxTeams) {
        if (@($canaux | Where-Object { $_.DisplayName -eq $c }).Count -gt 0) { Add-HNCSRDResultat -Statut Inchange -Cible "Teams / $nom / $c"; continue }
        if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible "Teams / $nom / $c"; continue }
        Add-PnPTeamsChannel -Team $idEquipe -DisplayName $c -ErrorAction Stop | Out-Null
        Add-HNCSRDResultat -Statut Cree -Cible "Teams / $nom / $c"
    }
    $general = Get-PnPTeamsPrimaryChannel -Team $idEquipe -ErrorAction Stop
    $titreOnglet = [string]$Model.site.title
    $onglets = @(Get-PnPTeamsTab -Team $idEquipe -Channel $general.Id)
    if (@($onglets | Where-Object { $_.DisplayName -eq $titreOnglet }).Count -gt 0) { Add-HNCSRDResultat -Statut Inchange -Cible "Teams / $nom / onglet $titreOnglet"; return }
    if (Test-HNCSRDSimulation) { Add-HNCSRDResultat -Statut Simule -Cible "Teams / $nom / onglet $titreOnglet"; return }
    Add-PnPTeamsTab -Team $idEquipe -Channel $general.Id -DisplayName $titreOnglet -Type WebSite -ContentUrl ([string]$Config.SiteUrl) -ErrorAction Stop | Out-Null
    Add-HNCSRDResultat -Statut Cree -Cible "Teams / $nom / onglet $titreOnglet" -Message ([string]$Config.SiteUrl)
}

#endregion

Export-ModuleMember -Function @(
    'Start-HNCSRDLog', 'Write-HNCSRDLog', 'Set-HNCSRDEtape', 'Add-HNCSRDResultat', 'Get-HNCSRDResultats', 'Get-HNCSRDResume',
    'Set-HNCSRDSimulation', 'Test-HNCSRDSimulation',
    'Get-HNCSRDModel', 'Get-HNCSRDConfig', 'Get-HNCSRDObject', 'Get-HNCSRDObjects', 'Test-HNCSRDLookupType', 'Get-HNCSRDColumns',
    'Get-HNCSRDColumnTypes', 'Get-HNCSRDListUrl', 'Get-HNCSRDGroupName', 'Get-HNCSRDOwnerGroupCode', 'Get-HNCSRDEnumValues',
    'Resolve-HNCSRDMarqueurs', 'Get-HNCSRDPropriete', 'ConvertTo-HNCSRDXmlText', 'Format-HNCSRDNombre', 'ConvertTo-HNCSRDBoolean',
    'Get-HNCSRDDefaultValue', 'ConvertTo-HNCSRDFieldXml', 'Compare-HNCSRDFieldSchema', 'ConvertTo-HNCSRDCaml', 'Format-HNCSRDCamlNormalise',
    'ConvertTo-HNCSRDValidationFormula', 'Get-HNCSRDValidationColumns', 'Get-HNCSRDVersioningSpec', 'Get-HNCSRDAttributionsAttendues',
    'Get-HNCSRDAttributionsSite', 'Get-HNCSRDNavigationPlan', 'Get-HNCSRDTimeZoneId',
    'Assert-HNCSRDPrerequis', 'Get-HNCSRDTenantDomain', 'Connect-HNCSRD',
    'Get-HNCSRDList', 'Get-HNCSRDChamps', 'Get-HNCSRDRoleDefinitionName', 'Get-HNCSRDPermissionKinds', 'Get-HNCSRDEtatAttributions',
    'Compare-HNCSRDAttributions', 'Get-HNCSRDItemsParCle', 'Resolve-HNCSRDLookupId', 'ConvertTo-HNCSRDValeurChamp',
    'Get-HNCSRDTransitionValeurs', 'Compare-HNCSRDTransitionItem',
    'Ensure-HNCSRDSite', 'Ensure-HNCSRDPermissionLevels', 'Ensure-HNCSRDGroups', 'Set-HNCSRDVersioning', 'Ensure-HNCSRDList',
    'Ensure-HNCSRDTitleColumn', 'Ensure-HNCSRDColumn', 'Set-HNCSRDListValidation', 'Ensure-HNCSRDView', 'Sync-HNCSRDAttributions',
    'Get-HNCSRDSeedCle', 'Resolve-HNCSRDSeedAction',
    'Set-HNCSRDListPermissions', 'Set-HNCSRDSitePermissions', 'Get-HNCSRDGroupesParDefaut', 'Clear-HNCSRDGroupesParDefaut', 'Ensure-HNCSRDParameters', 'Ensure-HNCSRDSeeds', 'Sync-HNCSRDTransitions',
    'Ensure-HNCSRDNavigation', 'Ensure-HNCSRDTeam'
)
