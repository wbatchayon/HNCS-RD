<#
.SYNOPSIS
    Crée (ou complète) le projet GitLab d'un sujet R&D à partir de SharePoint (spec § 10.2 et § 10.3, lot 3).

.DESCRIPTION
    Exécuté À LA DEMANDE D'UN HUMAIN (jamais par un flux ni par une planification) :
      1. lit le sujet (-IdSujet SUJ-aaaa-nnnn) dans la liste SujetsRD et ses livrables (liste Livrables :
         colonne Sujet, ou livrables des affectations du sujet) via PnP.PowerShell ;
      2. crée dans GitLab, par l'API REST, le projet suj-aaaa-nnnn-<slug> dans le groupe hncs-rd (ou dans
         le sous-groupe de pôle indiqué), description commençant par l'IdHNCS du sujet ;
      3. crée les labels rd::sujet::SUJ-…, rd::livrable::LIV-…, rd::pole::P1…P4, rd::type::poc/plan/doc ;
      4. crée un jalon par livrable : titre « LIV-aaaa-nnnn — <titre> », échéance = Echeance du livrable ;
      5. (option -DeposerModeles) dépose le README et les modèles d'issues / de MR (gitlab/templates) ;
      6. reporte GitlabProjetUrl et GitlabProjetId sur le sujet (seule écriture SharePoint du script).

    Idempotent : projet, labels, jalons et fichiers existants sont réutilisés, jamais recréés ni écrasés.
    Un jalon existant dont l'échéance diffère du livrable est signalé, pas modifié.
    -WhatIf affiche les créations et la mise à jour prévues sans rien écrire.

    Authentification :
      - GitLab : jeton PERSONNEL de la personne qui exécute le script (portée « api », rôle Maintainer
        au moins sur le groupe cible), dans $env:GITLAB_TOKEN pour la session uniquement ; jamais en
        paramètre, jamais stocké (spec § 10.3).
      - SharePoint : module provisioning/modules/HNCSRD.Provisioning.psm1 s'il existe
        (Get-HNCSRDConfig, Connect-HNCSRD), sinon Connect-PnPOnline -Interactive avec -ClientId.

    PowerShell 7.2+ et PnP.PowerShell 2.x visés ; la syntaxe reste analysable par Windows PowerShell 5.1.

.PARAMETER IdSujet
    Identifiant métier du sujet, ex. SUJ-2026-0003.
.PARAMETER SiteUrl
    URL du site SharePoint (défaut : configuration du module, sinon $env:HNCS_SITE_URL).
.PARAMETER GitlabUrl
    URL de l'instance GitLab (défaut : $env:GITLAB_URL).
.PARAMETER Groupe
    Chemin du groupe GitLab racine (défaut : hncs-rd).
.PARAMETER SousGroupe
    Sous-groupe de pôle facultatif, relatif au groupe (ex. p1-poc => hncs-rd/p1-poc). Il doit exister.
.PARAMETER Slug
    Suffixe du chemin du projet ; par défaut dérivé du titre du sujet (minuscules ASCII, tirets).
.PARAMETER Visibilite
    Visibilité du projet créé : private (défaut) ou internal.
.PARAMETER ExclureLivrable
    Livrables (LIV-…) sans composante technique, pour lesquels aucun jalon ni label n'est créé.
.PARAMETER DeposerModeles
    Dépose README.md et les modèles .gitlab/ manquants (un seul commit, fichiers existants conservés).
.PARAMETER ClientId
    Application Entra utilisée par Connect-PnPOnline -Interactive quand le module de provisioning est absent
    (défaut : $env:HNCS_PNP_CLIENT_ID).
.PARAMETER ConfigPath
    Fichier de configuration transmis à Get-HNCSRDConfig, si cette fonction l'accepte.

.EXAMPLE
    $env:GITLAB_URL = 'https://gitlab.example.com'; $env:GITLAB_TOKEN = '<saisi au clavier, jamais versionné>'
    ./gitlab/scripts/New-GitlabProjetSujet.ps1 -IdSujet SUJ-2026-0003 -SousGroupe p2-strategie -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^SUJ-\d{4}-\d{4,}$')]
    [string]$IdSujet,

    [string]$SiteUrl,

    [string]$GitlabUrl = $env:GITLAB_URL,

    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.\-/]*$')]
    [string]$Groupe = 'hncs-rd',

    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.\-/]*$')]
    [string]$SousGroupe,

    [ValidatePattern('^[a-z0-9][a-z0-9\-]*$')]
    [string]$Slug,

    [ValidateSet('private', 'internal')]
    [string]$Visibilite = 'private',

    [string[]]$ExclureLivrable = @(),

    [switch]$DeposerModeles,

    [string]$ClientId = $env:HNCS_PNP_CLIENT_ID,

    [string]$ConfigPath
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$script:Tiret = [string][char]0x2014          # « — » des titres de jalons (spec § 10.2)
$script:RegexLivrable = 'LIV-\d{4}-\d{4,}'
$script:CouleursLabels = @{ sujet = '#1F6FEB'; livrable = '#D29922'; pole = '#8957E5'; type = '#2DA44E' }

# ============================================================================ fonctions pures

function ConvertTo-HNCSSlug {
    <# Titre -> slug ASCII minuscule (accents retirés, séparateurs remplacés par des tirets, 40 car. max). #>
    param([string]$Texte, [int]$Longueur = 40)
    if ([string]::IsNullOrWhiteSpace($Texte)) { return 'sujet' }
    $decompose = $Texte.Normalize([System.Text.NormalizationForm]::FormD)
    $sb = New-Object System.Text.StringBuilder
    foreach ($c in $decompose.ToCharArray()) {
        if ([System.Globalization.CharUnicodeInfo]::GetUnicodeCategory($c) -ne [System.Globalization.UnicodeCategory]::NonSpacingMark) {
            [void]$sb.Append($c)
        }
    }
    $s = $sb.ToString().ToLowerInvariant()
    $s = $s -replace [char]0x0153, 'oe' -replace [char]0x00E6, 'ae'
    $s = ($s -replace '[^a-z0-9]+', '-').Trim('-')
    if ($s.Length -gt $Longueur) {
        $s = $s.Substring(0, $Longueur)
        $coupe = $s.LastIndexOf('-')
        if ($coupe -ge 10) { $s = $s.Substring(0, $coupe) }
        $s = $s.Trim('-')
    }
    if ([string]::IsNullOrEmpty($s)) { return 'sujet' }
    return $s
}

function Get-HNCSIdLivrable {
    <# Premier identifiant LIV-aaaa-nnnn d'un texte (titre de jalon), sinon $null. #>
    param([string]$Texte)
    if ([string]::IsNullOrEmpty($Texte)) { return $null }
    $m = [regex]::Match($Texte, $script:RegexLivrable)
    if ($m.Success) { return $m.Value }
    return $null
}

function Get-HNCSTypeLabel {
    <# Type de livrable / sujet -> suffixe rd::type (poc, plan, doc). #>
    param([string]$Type)
    if ($Type -like 'POC*') { return 'poc' }
    if ($Type -like 'Plan de strat*') { return 'plan' }
    return 'doc'
}

function Get-HNCSTitreJalon {
    param([string]$IdLivrable, [string]$Titre)
    $t = '{0} {1} {2}' -f $IdLivrable, $script:Tiret, $Titre
    if ($t.Length -gt 255) { $t = $t.Substring(0, 255) }
    return $t
}

function ConvertTo-HNCSDateParis {
    <# DateTime renvoyé par SharePoint (UTC pour une colonne « date seule ») -> 'yyyy-MM-dd' heure de Paris. #>
    param($Valeur)
    if ($null -eq $Valeur -or $Valeur -eq '') { return $null }
    if ($Valeur -is [string]) {
        if ($Valeur -match '^\d{4}-\d{2}-\d{2}$') { return $Valeur }
        $Valeur = [datetime]::Parse($Valeur, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::AdjustToUniversal)
        $Valeur = [datetime]::SpecifyKind($Valeur, [System.DateTimeKind]::Utc)
    }
    $dt = [datetime]$Valeur
    if ($dt.Kind -eq [System.DateTimeKind]::Local) { $dt = $dt.ToUniversalTime() }
    if ($dt.Kind -eq [System.DateTimeKind]::Unspecified) { $dt = [datetime]::SpecifyKind($dt, [System.DateTimeKind]::Utc) }
    $fuseau = $null
    foreach ($id in @('Romance Standard Time', 'Europe/Paris')) {
        try { $fuseau = [System.TimeZoneInfo]::FindSystemTimeZoneById($id); break } catch { $fuseau = $null }
    }
    if ($null -eq $fuseau) { throw 'Fuseau horaire de Paris introuvable sur ce poste.' }
    return [System.TimeZoneInfo]::ConvertTimeFromUtc($dt, $fuseau).ToString('yyyy-MM-dd', [System.Globalization.CultureInfo]::InvariantCulture)
}

function Expand-HNCSModele {
    <# Remplace les jetons {{NOM}} d'un modèle. #>
    param([string]$Texte, [hashtable]$Valeurs)
    $r = $Texte
    foreach ($cle in $Valeurs.Keys) { $r = $r.Replace('{{' + $cle + '}}', [string]$Valeurs[$cle]) }
    return $r
}

# ============================================================================ GitLab (API REST v4)

function Get-HNCSStatutHttp {
    param($ErreurRecord)
    $reponse = $null
    try { $reponse = $ErreurRecord.Exception.Response } catch { $reponse = $null }
    if ($null -eq $reponse) { return 0 }
    try { return [int]$reponse.StatusCode } catch { return 0 }
}

function Get-HNCSRetryAfter {
    param($ErreurRecord, [int]$Tentative)
    $delai = [math]::Pow(2, $Tentative - 1)
    try {
        $reponse = $ErreurRecord.Exception.Response
        $valeur = $null
        if ($reponse.Headers -is [System.Net.WebHeaderCollection]) { $valeur = $reponse.Headers['Retry-After'] }
        elseif ($null -ne $reponse.Headers.RetryAfter -and $null -ne $reponse.Headers.RetryAfter.Delta) { $valeur = $reponse.Headers.RetryAfter.Delta.TotalSeconds }
        if ($null -ne $valeur) { $delai = [double]$valeur }
    } catch { }
    return [math]::Min([math]::Max($delai, 1), 120)
}

function Get-HNCSEntete {
    param($Reponse, [string]$Nom)
    $v = $null
    try { $v = $Reponse.Headers[$Nom] } catch { $v = $null }
    if ($v -is [array]) { if ($v.Count -gt 0) { $v = $v[0] } else { $v = $null } }
    if ($null -ne $v -and -not ($v -is [string])) { $v = @($v)[0] }
    return [string]$v
}

function Invoke-HNCSGitlab {
    <#
    Appel de l'API GitLab avec nouvelles tentatives sur 429/5xx.
    -Paginer suit l'en-tête X-Next-Page et renvoie tous les éléments.
    -Autoriser404 renvoie $null au lieu d'échouer sur HTTP 404.
    #>
    param(
        [ValidateSet('GET', 'POST', 'PUT')] [string]$Methode = 'GET',
        [Parameter(Mandatory = $true)] [string]$Chemin,
        $Corps,
        [switch]$Paginer,
        [switch]$Autoriser404
    )
    $entetes = @{ 'PRIVATE-TOKEN' = $script:GitlabToken; 'Accept' = 'application/json' }
    $resultats = New-Object System.Collections.ArrayList
    $page = '1'
    while ($true) {
        $uri = $script:GitlabApi + $Chemin
        if ($Paginer) {
            $sep = '?'
            if ($uri.Contains('?')) { $sep = '&' }
            $uri = '{0}{1}per_page=100&page={2}' -f $uri, $sep, $page
        }
        $parametres = @{ Uri = $uri; Method = $Methode; Headers = $entetes; UseBasicParsing = $true }
        if ($null -ne $Corps) {
            $json = $Corps | ConvertTo-Json -Depth 10 -Compress
            $parametres['Body'] = [System.Text.Encoding]::UTF8.GetBytes($json)
            $parametres['ContentType'] = 'application/json; charset=utf-8'
        }
        $reponse = $null
        for ($tentative = 1; $tentative -le 5; $tentative++) {
            try {
                $reponse = Invoke-WebRequest @parametres
                break
            } catch {
                $statut = Get-HNCSStatutHttp $_
                if ($statut -eq 404 -and $Autoriser404) { return $null }
                if (($statut -eq 429 -or $statut -ge 500) -and $tentative -lt 5) {
                    $delai = Get-HNCSRetryAfter $_ $tentative
                    Write-Warning ("GitLab {0} {1} : HTTP {2}, nouvelle tentative dans {3} s." -f $Methode, $Chemin, $statut, $delai)
                    Start-Sleep -Seconds $delai
                    continue
                }
                throw ("GitLab {0} {1} : échec HTTP {2} ({3})." -f $Methode, $Chemin, $statut, $_.Exception.Message)
            }
        }
        $octets = $reponse.RawContentStream.ToArray()
        $texte = [System.Text.Encoding]::UTF8.GetString($octets)
        $donnees = $null
        if (-not [string]::IsNullOrWhiteSpace($texte)) { $donnees = ConvertFrom-Json -InputObject $texte }
        if (-not $Paginer) { return $donnees }
        foreach ($element in @($donnees)) { if ($null -ne $element) { [void]$resultats.Add($element) } }
        $page = Get-HNCSEntete $reponse 'X-Next-Page'
        if ([string]::IsNullOrWhiteSpace($page)) { break }
    }
    return $resultats.ToArray()
}

function Get-HNCSCheminEncode {
    param([string]$Chemin)
    return [uri]::EscapeDataString($Chemin)
}

# ============================================================================ SharePoint (PnP.PowerShell)

function Connect-HNCSSharePoint {
    <# Connexion via le module de provisioning s'il existe, sinon Connect-PnPOnline -Interactive. Renvoie l'URL du site. #>
    param([string]$SiteUrl, [string]$ClientId, [string]$ConfigPath)
    $module = Join-Path $PSScriptRoot '../../provisioning/modules/HNCSRD.Provisioning.psm1'
    if (Test-Path -LiteralPath $module) {
        Import-Module $module -Force -DisableNameChecking
        $cmdConfig = Get-Command Get-HNCSRDConfig -ErrorAction SilentlyContinue
        $cmdConnexion = Get-Command Connect-HNCSRD -ErrorAction SilentlyContinue
        if ($null -ne $cmdConfig -and $null -ne $cmdConnexion) {
            $argsConfig = @{}
            if ($ConfigPath) {
                foreach ($nom in @('ConfigPath', 'Path', 'Chemin')) {
                    if ($cmdConfig.Parameters.ContainsKey($nom)) { $argsConfig[$nom] = $ConfigPath; break }
                }
            }
            $config = $null
            try { $config = & $cmdConfig @argsConfig }
            catch {
                if ($ConfigPath) { throw }
                Write-Warning ("Configuration du provisioning indisponible ({0}) : connexion directe." -f $_.Exception.Message)
            }
        }
        if ($null -ne $cmdConfig -and $null -ne $cmdConnexion -and $null -ne $config) {
            $argsConnexion = @{}
            foreach ($nom in @('Config', 'Configuration')) {
                if ($cmdConnexion.Parameters.ContainsKey($nom)) { $argsConnexion[$nom] = $config; break }
            }
            if ($SiteUrl) {
                foreach ($nom in @('Url', 'SiteUrl')) {
                    if ($cmdConnexion.Parameters.ContainsKey($nom)) { $argsConnexion[$nom] = $SiteUrl; break }
                }
            }
            Write-Verbose 'Connexion SharePoint par le module HNCSRD.Provisioning.'
            [void](& $cmdConnexion @argsConnexion)
            if (-not $SiteUrl -and $null -ne $config) {
                foreach ($prop in @('SiteUrl', 'Url')) {
                    if ($config.PSObject.Properties.Name -contains $prop -and $config.$prop) { $SiteUrl = [string]$config.$prop; break }
                }
                if (-not $SiteUrl -and $config.PSObject.Properties.Name -contains 'Site' -and $null -ne $config.Site) {
                    if ($config.Site.PSObject.Properties.Name -contains 'Url') { $SiteUrl = [string]$config.Site.Url }
                }
            }
            if (-not $SiteUrl) { $SiteUrl = $env:HNCS_SITE_URL }
            if (-not $SiteUrl) { throw 'URL du site introuvable : préciser -SiteUrl.' }
            return $SiteUrl.TrimEnd('/')
        }
        if ($null -eq $cmdConfig -or $null -eq $cmdConnexion) {
            Write-Warning 'Module HNCSRD.Provisioning présent sans Get-HNCSRDConfig / Connect-HNCSRD : connexion directe.'
        }
    }
    if (-not $SiteUrl) { $SiteUrl = $env:HNCS_SITE_URL }
    if (-not $SiteUrl) { throw 'Préciser -SiteUrl (ou $env:HNCS_SITE_URL).' }
    if (-not $ClientId) { throw 'Préciser -ClientId (application Entra de PnP.PowerShell) ou $env:HNCS_PNP_CLIENT_ID.' }
    if ($null -eq (Get-Command Connect-PnPOnline -ErrorAction SilentlyContinue)) {
        throw 'Module PnP.PowerShell introuvable : Install-Module PnP.PowerShell -Scope CurrentUser.'
    }
    Connect-PnPOnline -Url $SiteUrl -Interactive -ClientId $ClientId
    return $SiteUrl.TrimEnd('/')
}

function Get-HNCSListe {
    <# Liste par nom interne (URL) : Lists/<Nom>, ou <Nom> pour une bibliothèque. #>
    param([string]$Nom)
    $liste = $null
    try { $liste = Get-PnPList -Identity ('Lists/' + $Nom) } catch { $liste = $null }
    if ($null -eq $liste) { $liste = Get-PnPList -Identity $Nom }
    if ($null -eq $liste) { throw "Liste $Nom introuvable sur le site." }
    return $liste
}

function Get-HNCSValeurChamp {
    param($Element, [string]$Nom)
    try { return $Element.FieldValues[$Nom] } catch { return $null }
}

function Get-HNCSLivrablesDuSujet {
    <# Livrables dont Sujet = le sujet, complétés par les livrables des affectations du sujet (Sujet pas encore copié par PA-07). #>
    param($ListeLivrables, $ListeAffectations, [int]$SujetItemId)
    $champs = '<ViewFields><FieldRef Name="ID"/><FieldRef Name="IdHNCS"/><FieldRef Name="Title"/><FieldRef Name="Echeance"/><FieldRef Name="TypeLivrable"/><FieldRef Name="Statut"/></ViewFields>'
    $parId = @{}
    $caml = '<View><Query><Where><Eq><FieldRef Name="Sujet" LookupId="TRUE"/><Value Type="Lookup">{0}</Value></Eq></Where></Query>{1}</View>' -f $SujetItemId, $champs
    foreach ($l in @(Get-PnPListItem -List $ListeLivrables -Query $caml -PageSize 500)) { if ($null -ne $l) { $parId[[int]$l.Id] = $l } }

    $camlAff = '<View><Query><Where><Eq><FieldRef Name="Sujet" LookupId="TRUE"/><Value Type="Lookup">{0}</Value></Eq></Where></Query><ViewFields><FieldRef Name="ID"/></ViewFields></View>' -f $SujetItemId
    $affectations = @(Get-PnPListItem -List $ListeAffectations -Query $camlAff -PageSize 500 | Where-Object { $null -ne $_ })
    if ($affectations.Count -gt 0) {
        $valeurs = ($affectations | ForEach-Object { '<Value Type="Lookup">{0}</Value>' -f $_.Id }) -join ''
        $camlLiv = '<View><Query><Where><In><FieldRef Name="Affectation" LookupId="TRUE"/><Values>{0}</Values></In></Where></Query>{1}</View>' -f $valeurs, $champs
        foreach ($l in @(Get-PnPListItem -List $ListeLivrables -Query $camlLiv -PageSize 500)) { if ($null -ne $l) { $parId[[int]$l.Id] = $l } }
    }
    $livrables = foreach ($l in $parId.Values) {
        $id = [string](Get-HNCSValeurChamp $l 'IdHNCS')
        if ([string]::IsNullOrWhiteSpace($id)) {
            Write-Warning ("Livrable d'ID SharePoint {0} sans IdHNCS (PA-00D pas encore passé) : ignoré." -f $l.Id)
            continue
        }
        [pscustomobject]@{
            ItemId       = [int]$l.Id
            IdHNCS       = $id.Trim()
            Titre        = [string](Get-HNCSValeurChamp $l 'Title')
            Echeance     = ConvertTo-HNCSDateParis (Get-HNCSValeurChamp $l 'Echeance')
            TypeLivrable = [string](Get-HNCSValeurChamp $l 'TypeLivrable')
            Statut       = [string](Get-HNCSValeurChamp $l 'Statut')
        }
    }
    return @($livrables | Sort-Object IdHNCS)
}

function Get-HNCSUrlListe {
    param($Liste, [string]$SiteUrl, [string]$Repli)
    try {
        $dossier = Get-PnPProperty -ClientObject $Liste -Property RootFolder
        $relatif = [string]$dossier.ServerRelativeUrl
        if ($relatif) {
            $u = [uri]$SiteUrl
            return '{0}://{1}{2}' -f $u.Scheme, $u.Authority, $relatif
        }
    } catch { }
    return '{0}/{1}' -f $SiteUrl, $Repli
}

# ============================================================================ programme principal

# Chargé par « . ./New-GitlabProjetSujet.ps1 -IdSujet … » : fonctions seulement (tests).
if ($MyInvocation.InvocationName -eq '.') { return }

if ([string]::IsNullOrWhiteSpace($GitlabUrl)) { throw 'Préciser -GitlabUrl ou $env:GITLAB_URL.' }
if (-not $GitlabUrl.StartsWith('https://')) { throw 'GitlabUrl doit être une URL https.' }
if ([string]::IsNullOrWhiteSpace($env:GITLAB_TOKEN)) { throw 'Variable d''environnement GITLAB_TOKEN absente (jeton GitLab personnel de portée api, jamais stocké).' }
$script:GitlabApi = $GitlabUrl.TrimEnd('/') + '/api/v4'
$script:GitlabToken = $env:GITLAB_TOKEN
if ($PSVersionTable.PSVersion.Major -lt 6) {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor [System.Net.SecurityProtocolType]::Tls12
    Write-Warning 'Windows PowerShell 5.1 détecté : PowerShell 7.2+ est la cible (PnP.PowerShell 2.x).'
}
$exclus = @($ExclureLivrable | ForEach-Object { $_.Trim().ToUpperInvariant() })

# ---- 1. Lecture SharePoint ---------------------------------------------------------------------------
$SiteUrl = Connect-HNCSSharePoint -SiteUrl $SiteUrl -ClientId $ClientId -ConfigPath $ConfigPath
$listeSujets = Get-HNCSListe 'SujetsRD'
$listeLivrables = Get-HNCSListe 'Livrables'
$listeAffectations = Get-HNCSListe 'Affectations'

$sujet = $null
$cmdResoudre = Get-Command Resolve-HNCSRDLookupId -ErrorAction SilentlyContinue
if ($null -ne $cmdResoudre) {
    # Module de provisioning : résolution IdHNCS -> ID SharePoint (contrôle d'unicité inclus).
    $sujetItemId = $null
    $resolu = $false
    try { $sujetItemId = Resolve-HNCSRDLookupId -List 'SujetsRD' -IdHNCS $IdSujet; $resolu = $true }
    catch { Write-Verbose ("Resolve-HNCSRDLookupId indisponible ({0}) : requête CAML directe." -f $_.Exception.Message) }
    if ($resolu) {
        if ($null -eq $sujetItemId) { throw "Sujet $IdSujet introuvable dans SujetsRD." }
        $sujet = Get-PnPListItem -List $listeSujets -Id $sujetItemId
    }
}
if ($null -eq $sujet) {
    $camlSujet = '<View><Query><Where><Eq><FieldRef Name="IdHNCS"/><Value Type="Text">{0}</Value></Eq></Where></Query><RowLimit>2</RowLimit></View>' -f $IdSujet
    $sujets = @(Get-PnPListItem -List $listeSujets -Query $camlSujet | Where-Object { $null -ne $_ })
    if ($sujets.Count -eq 0) { throw "Sujet $IdSujet introuvable dans SujetsRD." }
    if ($sujets.Count -gt 1) { throw "IdHNCS $IdSujet présent plusieurs fois dans SujetsRD : corriger avant de continuer." }
    $sujet = $sujets[0]
}
$titreSujet = [string](Get-HNCSValeurChamp $sujet 'Title')
$projetIdActuel = Get-HNCSValeurChamp $sujet 'GitlabProjetId'
$urlActuelle = Get-HNCSValeurChamp $sujet 'GitlabProjetUrl'
if ($null -ne $urlActuelle -and -not ($urlActuelle -is [string])) { $urlActuelle = [string]$urlActuelle.Url }

$codePole = $null
$pole = Get-HNCSValeurChamp $sujet 'Pole'
if ($null -ne $pole) {
    if ([string]$pole.LookupValue -match '^POL-(P\d+)$') { $codePole = $Matches[1] }
    else {
        $elementPole = Get-PnPListItem -List (Get-HNCSListe 'Poles') -Id $pole.LookupId
        $codePole = [string](Get-HNCSValeurChamp $elementPole 'CodePole')
    }
}
if (-not $codePole) { Write-Warning "Sujet $IdSujet sans pôle : label rd::pole non associé." }

$livrables = @(Get-HNCSLivrablesDuSujet -ListeLivrables $listeLivrables -ListeAffectations $listeAffectations -SujetItemId ([int]$sujet.Id))
$livrablesJalons = @($livrables | Where-Object { $exclus -notcontains $_.IdHNCS.ToUpperInvariant() })
Write-Host ("Sujet {0} « {1} » (pôle {2}) : {3} livrable(s), {4} jalon(s) attendu(s)." -f $IdSujet, $titreSujet, $codePole, $livrables.Count, $livrablesJalons.Count)

# ---- 2. Groupe et projet GitLab ----------------------------------------------------------------------
$cheminGroupe = $Groupe.Trim('/')
if ($SousGroupe) { $cheminGroupe = '{0}/{1}' -f $cheminGroupe, $SousGroupe.Trim('/') }
$groupeGitlab = Invoke-HNCSGitlab -Chemin ('/groups/' + (Get-HNCSCheminEncode $cheminGroupe)) -Autoriser404
if ($null -eq $groupeGitlab) { throw "Groupe GitLab $cheminGroupe introuvable (le script ne crée pas de groupe)." }

$prefixe = $IdSujet.ToLowerInvariant()
if (-not $Slug) { $Slug = ConvertTo-HNCSSlug $titreSujet }
$cheminProjet = '{0}-{1}' -f $prefixe, $Slug
$projet = $null

if ($null -ne $projetIdActuel -and [string]$projetIdActuel -ne '') {
    $projet = Invoke-HNCSGitlab -Chemin ('/projects/{0}' -f [int]$projetIdActuel) -Autoriser404
    if ($null -eq $projet) { Write-Warning "GitlabProjetId $projetIdActuel du sujet introuvable dans GitLab : recherche par nom." }
}
if ($null -eq $projet) {
    $racine = Invoke-HNCSGitlab -Chemin ('/groups/' + (Get-HNCSCheminEncode $Groupe.Trim('/'))) -Autoriser404
    if ($null -eq $racine) { $racine = $groupeGitlab }
    $trouves = @(Invoke-HNCSGitlab -Chemin ('/groups/{0}/projects?include_subgroups=true&simple=true&search={1}' -f $racine.id, [uri]::EscapeDataString($prefixe)) -Paginer |
        Where-Object { $_.path -eq $prefixe -or $_.path.StartsWith($prefixe + '-') })
    if ($trouves.Count -gt 1) {
        throw ("Plusieurs projets GitLab correspondent à {0} : {1}. Renseigner GitlabProjetId sur le sujet." -f $IdSujet, (($trouves | ForEach-Object { $_.path_with_namespace }) -join ', '))
    }
    if ($trouves.Count -eq 1) {
        $projet = Invoke-HNCSGitlab -Chemin ('/projects/{0}' -f $trouves[0].id)
        Write-Host ("Projet existant réutilisé : {0}" -f $projet.path_with_namespace)
    }
}
if ($null -eq $projet) {
    $description = '{0} {1} {2}. Sujet R&D HNCS (fiche SharePoint : {3}/Lists/SujetsRD/DispForm.aspx?ID={4}).' -f $IdSujet, $script:Tiret, $titreSujet, $SiteUrl, $sujet.Id
    if ($PSCmdlet.ShouldProcess(('{0}/{1}' -f $groupeGitlab.full_path, $cheminProjet), 'Créer le projet GitLab')) {
        $projet = Invoke-HNCSGitlab -Methode POST -Chemin '/projects' -Corps @{
            name                   = $cheminProjet
            path                   = $cheminProjet
            namespace_id           = $groupeGitlab.id
            description            = $description
            visibility             = $Visibilite
            initialize_with_readme = $false
        }
        Write-Host ("Projet créé : {0} (ID {1})" -f $projet.web_url, $projet.id)
    }
} elseif ($projet.path -ne $cheminProjet) {
    Write-Verbose ("Chemin existant {0} conservé (chemin calculé : {1})." -f $projet.path, $cheminProjet)
}
if ($null -eq $projet -and -not $WhatIfPreference) {
    Write-Warning 'Projet GitLab non créé (création refusée) : arrêt sans autre modification.'
    return
}
# En simulation sans projet existant, les étapes suivantes ne font qu'annoncer les créations (ShouldProcess).

# ---- 3. Labels ---------------------------------------------------------------------------------------
$labelsVoulus = New-Object System.Collections.ArrayList
[void]$labelsVoulus.Add(@{ name = "rd::sujet::$IdSujet"; color = $script:CouleursLabels.sujet; description = "Sujet R&D $IdSujet" })
foreach ($p in @('P1', 'P2', 'P3', 'P4')) { [void]$labelsVoulus.Add(@{ name = "rd::pole::$p"; color = $script:CouleursLabels.pole; description = "Pôle $p" }) }
foreach ($t in @('poc', 'plan', 'doc')) { [void]$labelsVoulus.Add(@{ name = "rd::type::$t"; color = $script:CouleursLabels.type; description = "Type $t" }) }
foreach ($l in $livrablesJalons) { [void]$labelsVoulus.Add(@{ name = 'rd::livrable::' + $l.IdHNCS; color = $script:CouleursLabels.livrable; description = $l.Titre }) }

$labelsExistants = @()
if ($null -ne $projet) {
    $labelsExistants = @(Invoke-HNCSGitlab -Chemin ('/projects/{0}/labels?include_ancestor_groups=true' -f $projet.id) -Paginer | ForEach-Object { $_.name })
}
foreach ($label in $labelsVoulus) {
    if ($labelsExistants -contains $label.name) { Write-Verbose ("Label existant : {0}" -f $label.name); continue }
    if ($PSCmdlet.ShouldProcess($label.name, 'Créer le label GitLab')) {
        [void](Invoke-HNCSGitlab -Methode POST -Chemin ('/projects/{0}/labels' -f $projet.id) -Corps $label)
        Write-Host ("Label créé : {0}" -f $label.name)
    }
}

# ---- 4. Jalons (un par livrable) ---------------------------------------------------------------------
$jalonsParLivrable = @{}
if ($null -ne $projet) {
    foreach ($j in @(Invoke-HNCSGitlab -Chemin ('/projects/{0}/milestones' -f $projet.id) -Paginer)) {
        $id = Get-HNCSIdLivrable $j.title
        if ($id -and -not $jalonsParLivrable.ContainsKey($id)) { $jalonsParLivrable[$id] = $j }
    }
}
foreach ($l in $livrablesJalons) {
    if ($jalonsParLivrable.ContainsKey($l.IdHNCS)) {
        $j = $jalonsParLivrable[$l.IdHNCS]
        if ([string]$j.due_date -ne [string]$l.Echeance) {
            Write-Warning ("Jalon « {0} » : échéance {1} différente de celle du livrable ({2}). Non modifié." -f $j.title, $j.due_date, $l.Echeance)
        } else { Write-Verbose ("Jalon existant : {0}" -f $j.title) }
        continue
    }
    $titreJalon = Get-HNCSTitreJalon $l.IdHNCS $l.Titre
    if ($PSCmdlet.ShouldProcess($titreJalon, ('Créer le jalon GitLab (échéance {0})' -f $l.Echeance))) {
        $corps = @{ title = $titreJalon; description = ('Livrable SharePoint {0} (sujet {1}). Échéance de référence : liste Livrables.' -f $l.IdHNCS, $IdSujet) }
        if ($l.Echeance) { $corps['due_date'] = $l.Echeance }
        $j = Invoke-HNCSGitlab -Methode POST -Chemin ('/projects/{0}/milestones' -f $projet.id) -Corps $corps
        $jalonsParLivrable[$l.IdHNCS] = $j
        Write-Host ("Jalon créé : {0}" -f $titreJalon)
    }
}

# ---- 5. Modèles (facultatif) -------------------------------------------------------------------------
if ($DeposerModeles) {
    $dossierModeles = Join-Path $PSScriptRoot '../templates'
    $urlLivrables = Get-HNCSUrlListe $listeLivrables $SiteUrl 'Lists/Livrables'
    $bibliotheque = $null
    try { $bibliotheque = Get-HNCSListe 'LivrablesRD' } catch { $bibliotheque = $null }
    $urlBibliotheque = '{0}/LivrablesRD' -f $SiteUrl
    if ($null -ne $bibliotheque) { $urlBibliotheque = Get-HNCSUrlListe $bibliotheque $SiteUrl 'LivrablesRD' }
    $lignes = @('| Livrable | Titre | Échéance | Étiquettes |', '| --- | --- | --- | --- |')
    foreach ($l in $livrablesJalons) {
        $lignes += ('| {0} | {1} | {2} | `rd::livrable::{0}`, `rd::type::{3}` |' -f $l.IdHNCS, ($l.Titre -replace '\|', '/'), $l.Echeance, (Get-HNCSTypeLabel $l.TypeLivrable))
    }
    if ($livrablesJalons.Count -eq 0) { $lignes = @('_Aucun livrable rattaché au sujet à la création du projet._') }
    $valeurs = @{
        ID_SUJET              = $IdSujet
        TITRE_SUJET           = $titreSujet
        CODE_POLE             = $codePole
        URL_SITE              = $SiteUrl
        URL_SUJET             = ('{0}/DispForm.aspx?ID={1}' -f (Get-HNCSUrlListe $listeSujets $SiteUrl 'Lists/SujetsRD'), $sujet.Id)
        URL_LIVRABLES         = ('{0}/AllItems.aspx?FilterField1=Sujet&FilterValue1={1}' -f $urlLivrables, $IdSujet)
        URL_DOSSIER_LIVRABLES = ('{0}/{1}' -f $urlBibliotheque, $IdSujet)
        LISTE_LIVRABLES       = ($lignes -join "`n")
    }
    $fichiers = [ordered]@{ 'README.md' = (Join-Path $dossierModeles 'README-projet-RD.md') }
    foreach ($sous in @('issue_templates', 'merge_request_templates')) {
        foreach ($f in @(Get-ChildItem -LiteralPath (Join-Path $dossierModeles ".gitlab/$sous") -Filter '*.md' -File)) {
            $fichiers[('.gitlab/{0}/{1}' -f $sous, $f.Name)] = $f.FullName
        }
    }
    if ($null -eq $projet) {
        foreach ($cible in $fichiers.Keys) { [void]$PSCmdlet.ShouldProcess($cible, 'Déposer le modèle dans le projet GitLab') }
    } else {
        $branche = [string]$projet.default_branch
        $vide = (-not $branche)
        if ($projet.PSObject.Properties.Name -contains 'empty_repo' -and $projet.empty_repo) { $vide = $true }
        if (-not $branche) { $branche = 'main' }
        $actions = New-Object System.Collections.ArrayList
        foreach ($cible in $fichiers.Keys) {
            if (-not $vide) {
                $existe = Invoke-HNCSGitlab -Chemin ('/projects/{0}/repository/files/{1}?ref={2}' -f $projet.id, (Get-HNCSCheminEncode $cible), [uri]::EscapeDataString($branche)) -Autoriser404
                if ($null -ne $existe) { Write-Verbose ("Fichier existant conservé : {0}" -f $cible); continue }
            }
            $contenu = [System.IO.File]::ReadAllText($fichiers[$cible], [System.Text.Encoding]::UTF8)
            [void]$actions.Add(@{ action = 'create'; file_path = $cible; content = (Expand-HNCSModele $contenu $valeurs) })
        }
        if ($actions.Count -gt 0 -and $PSCmdlet.ShouldProcess(('{0} fichier(s) sur {1}' -f $actions.Count, $branche), 'Déposer les modèles R&D')) {
            [void](Invoke-HNCSGitlab -Methode POST -Chemin ('/projects/{0}/repository/commits' -f $projet.id) -Corps @{
                branch         = $branche
                commit_message = "Ajouter le README et les modèles R&D du sujet $IdSujet"
                actions        = $actions.ToArray()
            })
            Write-Host ("Modèles déposés : {0}" -f (($actions | ForEach-Object { $_.file_path }) -join ', '))
        }
    }
}

# ---- 6. Report sur le sujet SharePoint ---------------------------------------------------------------
if ($null -eq $projet) {
    Write-Host 'Simulation : GitlabProjetUrl et GitlabProjetId seraient reportés sur le sujet après création du projet.'
    return
}
$valeursSujet = @{}
if ($null -eq $projetIdActuel -or [string]$projetIdActuel -eq '' -or [int]$projetIdActuel -ne [int]$projet.id) { $valeursSujet['GitlabProjetId'] = [int]$projet.id }
if ([string]$urlActuelle -ne [string]$projet.web_url) { $valeursSujet['GitlabProjetUrl'] = ('{0}, {1}' -f $projet.web_url, $projet.path_with_namespace) }
if ($valeursSujet.Count -eq 0) {
    Write-Host 'Sujet déjà à jour (GitlabProjetUrl, GitlabProjetId).'
} elseif ($PSCmdlet.ShouldProcess("$IdSujet (SujetsRD)", ('Reporter {0}' -f (($valeursSujet.Keys | Sort-Object) -join ', ')))) {
    [void](Set-PnPListItem -List $listeSujets -Identity $sujet.Id -Values $valeursSujet)
    Write-Host ("Sujet {0} mis à jour : {1}" -f $IdSujet, (($valeursSujet.Keys | Sort-Object) -join ', '))
}
Write-Host ("Terminé : {0}" -f $projet.web_url)
