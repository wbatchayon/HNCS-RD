<#
.SYNOPSIS
    Fonctions de test hors ligne du module HNCSRD.Provisioning (chargées par les fichiers *.Tests.ps1).
.DESCRIPTION
    Chaque fonction Invoke-* retourne { <compteur> ; Echecs = @(messages) } et ne dépend ni de PnP ni
    d'un tenant. Compatible Windows PowerShell 5.1 et PowerShell 7.
#>

function Invoke-HNCSRDCamlTests {
    $racine = Split-Path -Parent $PSScriptRoot
    Import-Module (Join-Path $racine 'modules/HNCSRD.Provisioning.psd1') -Force -DisableNameChecking
    $modele = Get-HNCSRDModel -Path (Join-Path $racine 'model/model.generated.json') -Force
    $echecs = New-Object System.Collections.Generic.List[string]
    $nbVues = 0
    $echec = { param($m) $echecs.Add($m) }

    foreach ($p in $modele.views.PSObject.Properties) {
        $objet = Get-HNCSRDObject -Name $p.Name -Model $modele
        $types = Get-HNCSRDColumnTypes -Object $objet -Lot 5
        $vues = @($p.Value)
        $defauts = @($vues | Where-Object { $_.default }).Count
        if ($defauts -ne 1) { & $echec "$($p.Name) : $defauts vue(s) par défaut (attendu 1)" }
        $noms = @{}
        foreach ($v in $vues) {
            $nbVues++
            $id = "$($p.Name) / $($v.name)"
            if ($noms.ContainsKey($v.name)) { & $echec "$id : nom de vue en double" }
            $noms[$v.name] = $true
            try { $c = ConvertTo-HNCSRDCaml -View $v -ColumnTypes $types -ListKind $objet.kind }
            catch { & $echec "$id : exception $($_.Exception.Message)"; continue }
            $champs = ($c.ViewFields | ForEach-Object { '<FieldRef Name="' + $_ + '" />' }) -join ''
            $xmlTexte = '<View><Query>' + $c.Query + '</Query><ViewFields>' + $champs + '</ViewFields><RowLimit Paged="TRUE">' + $c.RowLimit + '</RowLimit></View>'
            $doc = New-Object System.Xml.XmlDocument
            try { $doc.LoadXml($xmlTexte) } catch { & $echec "$id : XML mal formé : $($_.Exception.Message)"; continue }
            # Rendu v1.2.0 : bibliothèque -> DocIcon, LinkFilename en tête ; liste -> Title rendu LinkTitle,
            # LinkTitle ajouté en tête si la vue ne cite pas Title.
            $attendus = @()
            if ($objet.kind -eq 'library') { $attendus += 'DocIcon', 'LinkFilename' }
            elseif (@($v.columns) -notcontains 'Title') { $attendus += 'LinkTitle' }
            foreach ($col in @($v.columns)) {
                $att = [string]$col
                if ($att -eq 'Title' -and $objet.kind -eq 'list') { $att = 'LinkTitle' }
                if ($attendus -notcontains $att) { $attendus += $att }
            }
            if (($c.ViewFields -join ',') -cne ($attendus -join ',')) { & $echec "$id : colonnes $($c.ViewFields -join ',') (attendu $($attendus -join ','))" }
            if ($objet.kind -eq 'list' -and $c.ViewFields -notcontains 'LinkTitle') { & $echec "$id : aucune colonne cliquable" }
            if ($objet.kind -eq 'library' -and ($c.ViewFields[0] -ne 'DocIcon' -or $c.ViewFields[1] -ne 'LinkFilename')) { & $echec "$id : DocIcon / LinkFilename absents en tête" }
            $gbn = $doc.SelectSingleNode('/View/Query/GroupBy')
            if ($gbn -and $gbn.GetAttribute('Collapse') -ne 'FALSE') { & $echec "$id : regroupement non déplié" }
            if ($c.RowLimit -ne 30) { & $echec "$id : RowLimit $($c.RowLimit)" }
            if ($doc.SelectNodes('//Not').Count -gt 0) { & $echec "$id : <Not> interdit en CAML SharePoint" }
            foreach ($and in @($doc.SelectNodes('//And'))) {
                if (@($and.ChildNodes | Where-Object { $_.NodeType -eq 'Element' }).Count -ne 2) { & $echec "$id : <And> sans exactement deux enfants" }
            }
            $where = $doc.SelectSingleNode('/View/Query/Where')
            $filtres = @($v.filter)
            if ($filtres.Count -eq 0) { if ($where) { & $echec "$id : <Where> inattendu" } }
            else {
                if (-not $where) { & $echec "$id : <Where> manquant"; continue }
                if (@($where.ChildNodes).Count -ne 1) { & $echec "$id : <Where> doit avoir un seul enfant" }
                $attendues = 0
                foreach ($f in $filtres) { if ($f.op -eq 'notin') { $attendues += @($f.values).Count } else { $attendues += 1 } }
                $feuilles = @($where.SelectNodes('.//Eq|.//Neq|.//Lt|.//Leq|.//Gt|.//Geq|.//In|.//IsNull|.//IsNotNull')).Count
                if ($feuilles -ne $attendues) { & $echec "$id : $feuilles comparaison(s) (attendu $attendues)" }
                if (@($where.SelectNodes('.//And')).Count -ne ($attendues - 1)) { & $echec "$id : nombre de <And> incorrect" }
                foreach ($f in $filtres) {
                    $refs = @($where.SelectNodes(".//FieldRef[@Name='$($f.field)']"))
                    if ($refs.Count -eq 0) { & $echec "$id : FieldRef $($f.field) absent du filtre" }
                    foreach ($val in @($f.values)) {
                        if ($val -eq '[Moi]' -and $where.SelectNodes('.//UserID').Count -eq 0) { & $echec "$id : [Moi] sans <UserID/>" }
                        if ($val -match "^\[Aujourd'hui([+-]\d+)?\]$") {
                            $off = 0; if ($Matches[1]) { $off = [int]$Matches[1] }
                            $tod = @($where.SelectNodes('.//Today'))
                            if ($tod.Count -eq 0) { & $echec "$id : <Today/> absent" }
                            elseif ($off -ne 0 -and $tod[0].GetAttribute('OffsetDays') -ne [string]$off) { & $echec "$id : OffsetDays $($tod[0].GetAttribute('OffsetDays')) (attendu $off)" }
                        }
                        if ($types[$f.field] -eq 'Boolean') {
                            $bv = @($where.SelectNodes(".//Value[@Type='Boolean']") | ForEach-Object { $_.InnerText })
                            $exp = '0'; if ($val -eq 'Oui') { $exp = '1' }
                            if ($bv -notcontains $exp) { & $echec "$id : booléen $val non converti en $exp" }
                        }
                    }
                }
            }
            $ob = @($doc.SelectNodes('/View/Query/OrderBy/FieldRef'))
            if ($ob.Count -ne @($v.sort).Count) { & $echec "$id : tri" }
            for ($i = 0; $i -lt $ob.Count; $i++) {
                $s = @($v.sort)[$i]
                $asc = 'TRUE'; if ($s.dir -eq 'desc') { $asc = 'FALSE' }
                if ($ob[$i].GetAttribute('Name') -ne $s.field -or $ob[$i].GetAttribute('Ascending') -ne $asc) { & $echec "$id : tri $i" }
            }
            $gb = $doc.SelectSingleNode('/View/Query/GroupBy/FieldRef')
            if ($v.groupBy) { if (-not $gb -or $gb.GetAttribute('Name') -ne $v.groupBy) { & $echec "$id : regroupement" } }
            elseif ($gb) { & $echec "$id : regroupement inattendu" }
        }
    }

    # Résultats exacts sur des vues de référence
    $references = @(
        @{ L = 'Candidatures'; V = 'Mes analyses'; W = '<Where><And><Eq><FieldRef Name="ResponsableAnalyse" /><Value Type="Integer"><UserID Type="Integer" /></Value></Eq><In><FieldRef Name="Statut" /><Values><Value Type="Choice">Reçue</Value><Value Type="Choice">À analyser</Value><Value Type="Choice">En cours d''analyse</Value></Values></In></And></Where>' },
        @{ L = 'Candidatures'; V = 'Candidatures en cours'; W = '<Where><And><Neq><FieldRef Name="Statut" /><Value Type="Choice">Intégrée</Value></Neq><And><Neq><FieldRef Name="Statut" /><Value Type="Choice">Non retenue</Value></Neq><Neq><FieldRef Name="Statut" /><Value Type="Choice">Clôturée</Value></Neq></And></And></Where>' },
        @{ L = 'Candidatures'; V = 'À attribuer'; W = '<Where><And><Eq><FieldRef Name="Statut" /><Value Type="Choice">Reçue</Value></Eq><IsNull><FieldRef Name="ResponsableAnalyse" /></IsNull></And></Where>' },
        @{ L = 'Candidatures'; V = 'Doublons potentiels'; W = '<Where><And><Eq><FieldRef Name="DoublonPotentiel" /><Value Type="Boolean">1</Value></Eq><And><Eq><FieldRef Name="DoublonVerifie" /><Value Type="Boolean">0</Value></Eq><And><Neq><FieldRef Name="Statut" /><Value Type="Choice">Non retenue</Value></Neq><Neq><FieldRef Name="Statut" /><Value Type="Choice">Clôturée</Value></Neq></And></And></And></Where>' },
        @{ L = 'ComptesRendus'; V = 'Comptes rendus ouverts'; W = '<Where><Neq><FieldRef Name="Statut" /><Value Type="Choice">Validé</Value></Neq></Where>' },
        @{ L = 'HistoriqueStatuts'; V = 'Historique récent'; W = '<Where><Geq><FieldRef Name="DateChangement" /><Value Type="DateTime"><Today OffsetDays="-30" /></Value></Geq></Where>' },
        @{ L = 'Alternants'; V = 'Fins à venir'; W = '<Where><And><In><FieldRef Name="Statut" /><Values><Value Type="Choice">Actif</Value><Value Type="Choice">Fin planifiée</Value></Values></In><Leq><FieldRef Name="DateFin" /><Value Type="DateTime"><Today OffsetDays="45" /></Value></Leq></And></Where>' },
        @{ L = 'Entretiens'; V = 'Résultats à saisir'; W = '<Where><And><Eq><FieldRef Name="Statut" /><Value Type="Choice">Planifié</Value></Eq><Lt><FieldRef Name="DateHeure" /><Value Type="DateTime"><Today /></Value></Lt></And></Where>' },
        @{ L = 'Conventions'; V = 'Décisions de partenariat'; W = '<Where><IsNotNull><FieldRef Name="DecisionPartenariat" /></IsNotNull></Where>' },
        @{ L = 'Affectations'; V = 'Sans référent'; W = '<Where><And><IsNull><FieldRef Name="Referent" /></IsNull><And><Neq><FieldRef Name="Statut" /><Value Type="Choice">Terminée</Value></Neq><Neq><FieldRef Name="Statut" /><Value Type="Choice">Clôturée</Value></Neq></And></And></Where>' }
    )
    foreach ($r in $references) {
        $objet = Get-HNCSRDObject -Name $r.L -Model $modele
        $v = @($modele.views.($r.L) | Where-Object { $_.name -eq $r.V })
        if ($v.Count -ne 1) { & $echec "Référence introuvable : $($r.L) / $($r.V)"; continue }
        $c = ConvertTo-HNCSRDCaml -View $v[0] -ColumnTypes (Get-HNCSRDColumnTypes -Object $objet) -ListKind $objet.kind
        if ($c.Where -cne $r.W) { & $echec ("Référence $($r.L) / $($r.V) :`n  obtenu  $($c.Where)`n  attendu $($r.W)") }
    }
    $o = Get-HNCSRDObject -Name 'Offres' -Model $modele
    $c = ConvertTo-HNCSRDCaml -View @($modele.views.Offres)[0] -ColumnTypes (Get-HNCSRDColumnTypes -Object $o)
    if ($c.Query -cne ('<OrderBy><FieldRef Name="DateDebutPeriode" Ascending="TRUE" /></OrderBy>' + '<Where><In><FieldRef Name="Statut" /><Values><Value Type="Choice">Brouillon</Value><Value Type="Choice">Publiée</Value></Values></In></Where>')) { & $echec "Offres / Offres ouvertes : requête $($c.Query)" }
    $o = Get-HNCSRDObject -Name 'LivrablesRD' -Model $modele
    $c = ConvertTo-HNCSRDCaml -View @($modele.views.LivrablesRD)[0] -ColumnTypes (Get-HNCSRDColumnTypes -Object $o) -ListKind library
    if (($c.ViewFields -join ',') -cne 'DocIcon,LinkFilename,Title,Livrable,Sujet,TypeDocument,StatutDocument,ResponsableValidation,DateDocument') { & $echec "Bibliothèque LivrablesRD : colonnes $($c.ViewFields -join ',')" }
    $o = Get-HNCSRDObject -Name 'Affectations' -Model $modele
    $c = ConvertTo-HNCSRDCaml -View @($modele.views.Affectations)[0] -ColumnTypes (Get-HNCSRDColumnTypes -Object $o)
    if ($c.ViewFields[0] -ne 'LinkTitle' -or $c.ViewFields[1] -ne 'IdHNCS') { & $echec "Affectations : LinkTitle attendu en première position ($($c.ViewFields -join ','))" }

    # Cas d'erreur
    $types = @{ Title = 'Text'; Statut = 'Choice' }
    $mauvais = @(
        [pscustomobject]@{ name = 'colonne inconnue'; default = $true; columns = @('Inconnue'); filter = @(); sort = @(); groupBy = $null },
        [pscustomobject]@{ name = 'opérateur inconnu'; default = $true; columns = @('Title'); filter = @([pscustomobject]@{ field = 'Statut'; op = 'like'; values = @('x') }); sort = @(); groupBy = $null },
        [pscustomobject]@{ name = '[Moi] sur un choix'; default = $true; columns = @('Title'); filter = @([pscustomobject]@{ field = 'Statut'; op = '='; values = @('[Moi]') }); sort = @(); groupBy = $null }
    )
    foreach ($m in $mauvais) {
        $leve = $false
        try { [void](ConvertTo-HNCSRDCaml -View $m -ColumnTypes $types) } catch { $leve = $true }
        if (-not $leve) { & $echec "Cas d'erreur non détecté : $($m.name)" }
    }
    return [pscustomobject]@{ Vues = $nbVues; Echecs = $echecs.ToArray() }
}


function Invoke-HNCSRDPureTests {
    $racine = Split-Path -Parent $PSScriptRoot
    Import-Module (Join-Path $racine 'modules/HNCSRD.Provisioning.psd1') -Force -DisableNameChecking
    $modele = Get-HNCSRDModel -Path (Join-Path $racine 'model/model.generated.json') -Force
    $echecs = New-Object System.Collections.Generic.List[string]
    $echec = { param($m) $echecs.Add($m) }
    $nbColonnes = 0
    $guid = '11111111-2222-3333-4444-555555555555'
    $nomsObjets = @($modele.objects | ForEach-Object { $_.name })
    $nomsGroupes = @($modele.groups | ForEach-Object { $_.name })

    foreach ($o in $modele.objects) {
        # URL = nom interne
        $url = Get-HNCSRDListUrl -Name $o.name -Model $modele
        if ($o.kind -eq 'library' -and $url -ne $o.name) { & $echec "$($o.name) : URL $url" }
        if ($o.kind -eq 'list' -and $url -ne ('Lists/' + $o.name)) { & $echec "$($o.name) : URL $url" }
        # Colonnes : XML bien formé, nom interne exact, auto-comparaison sans écart
        foreach ($c in $o.columns) {
            $nbColonnes++
            $id = "$($o.name).$($c.name)"
            if ((Test-HNCSRDLookupType -Type $c.type) -and $nomsObjets -notcontains $c.lookup) { & $echec "$id : cible $($c.lookup) hors modèle" }
            try {
                $x = ConvertTo-HNCSRDFieldXml -Column $c -LookupListId $guid -Model $modele
                $xi = ConvertTo-HNCSRDFieldXml -Column $c -LookupListId $guid -DisplayNameInterne -Model $modele
            }
            catch { & $echec "$id : exception $($_.Exception.Message)"; continue }
            $e = ([xml]$x).DocumentElement
            $ei = ([xml]$xi).DocumentElement
            if ($e.GetAttribute('Name') -cne $c.name -or $e.GetAttribute('StaticName') -cne $c.name) { & $echec "$id : Name/StaticName" }
            if ($ei.GetAttribute('DisplayName') -cne $c.name) { & $echec "$id : DisplayName de création" }
            if ($e.GetAttribute('DisplayName') -cne $c.label) { & $echec "$id : DisplayName" }
            $req = 'FALSE'; if ($c.required) { $req = 'TRUE' }
            if ($e.GetAttribute('Required') -ne $req) { & $echec "$id : Required" }
            if (($c.indexed -or $c.unique) -and $e.GetAttribute('Indexed') -ne 'TRUE') { & $echec "$id : Indexed" }
            if ($c.unique -and $e.GetAttribute('EnforceUniqueValues') -ne 'TRUE') { & $echec "$id : EnforceUniqueValues" }
            if ($c.hidden -and $e.GetAttribute('ShowInEditForm') -ne 'FALSE') { & $echec "$id : hidden" }
            if (-not $c.hidden -and $e.HasAttribute('ShowInEditForm')) { & $echec "$id : colonne non masquée marquée ShowInEditForm" }
            switch ($c.type) {
                'Date' { if ($e.GetAttribute('Type') -ne 'DateTime' -or $e.GetAttribute('Format') -ne 'DateOnly') { & $echec "$id : Date" } }
                'DateTime' { if ($e.GetAttribute('Format') -ne 'DateTime') { & $echec "$id : DateTime" } }
                'User' { if ($e.GetAttribute('UserSelectionMode') -ne 'PeopleOnly') { & $echec "$id : PeopleOnly" } }
                'UserMulti' { if ($e.GetAttribute('Mult') -ne 'TRUE') { & $echec "$id : UserMulti" } }
                'URL' { if ($e.GetAttribute('Format') -ne 'Hyperlink') { & $echec "$id : Hyperlink" } }
                'Note' {
                    $ao = 'FALSE'; if ($c.PSObject.Properties.Name -contains 'appendOnly' -and $c.appendOnly) { $ao = 'TRUE' }
                    if ($e.GetAttribute('AppendOnly') -ne $ao -or $e.GetAttribute('RichText') -ne 'FALSE') { & $echec "$id : Note (AppendOnly attendu $ao)" }
                }
                'Lookup' { if ($e.GetAttribute('ShowField') -ne 'IdHNCS' -or $e.HasAttribute('Mult')) { & $echec "$id : Lookup" } }
                'LookupMulti' { if ($e.GetAttribute('ShowField') -ne 'IdHNCS' -or $e.GetAttribute('Mult') -ne 'TRUE') { & $echec "$id : LookupMulti" } }
                'Boolean' {
                    $d = $e.SelectSingleNode('Default')
                    if ($c.default) {
                        $exp = '0'; if ($c.default -eq 'Oui') { $exp = '1' }
                        if (-not $d -or $d.InnerText -ne $exp) { & $echec "$id : défaut booléen" }
                    }
                }
                'Number' {
                    if ($null -ne $c.decimals -and $e.GetAttribute('Decimals') -ne [string][int]$c.decimals) { & $echec "$id : Decimals" }
                    if ($null -ne $c.max -and [double]$e.GetAttribute('Max') -ne [double]$c.max) { & $echec "$id : Max" }
                }
            }
            if ($c.type -eq 'Choice' -or $c.type -eq 'MultiChoice') {
                $choix = @($e.SelectNodes('CHOICES/CHOICE') | ForEach-Object { $_.InnerText })
                if (($choix -join '|') -cne (@($modele.enums.($c.enum)) -join '|')) { & $echec "$id : choix ordonnés" }
                if ($c.default -and $e.SelectSingleNode('Default').InnerText -cne $c.default) { & $echec "$id : défaut" }
            }
            $ecarts = @(Compare-HNCSRDFieldSchema -SchemaActuel $x -SchemaAttendu $x)
            if ($ecarts.Count -gt 0) { & $echec "$id : auto-comparaison : $(($ecarts | ForEach-Object { $_.Propriete }) -join ', ')" }
            $ecartsCreation = @(Compare-HNCSRDFieldSchema -SchemaActuel $xi -SchemaAttendu $x | Where-Object { $_.Propriete -ne 'DisplayName' })
            if ($ecartsCreation.Count -gt 0) { & $echec "$id : XML de création différent hors libellé" }
        }
        # Validation : colonnes référencées présentes (hors Note/URL/Lookup, § 2.4), traduction
        if ($o.validation) {
            $noms = @{ 'Title' = [string]$o.titleLabel }
            foreach ($c in $o.columns) { $noms[$c.name] = [string]$c.label }
            foreach ($ref in (Get-HNCSRDValidationColumns -Formula $o.validation)) {
                $col = @($o.columns | Where-Object { $_.name -eq $ref })
                if ($col.Count -eq 0) { & $echec "$($o.name) : validation référence $ref absente"; continue }
                if (@('Note', 'URL', 'Lookup', 'LookupMulti') -contains $col[0].type) { & $echec "$($o.name) : validation sur colonne $($col[0].type) $ref" }
                if ($col[0].lot -and [int]$col[0].lot -gt [int]$o.lot) { & $echec "$($o.name) : validation sur colonne de lot ultérieur $ref" }
            }
            try {
                $f = ConvertTo-HNCSRDValidationFormula -Formula $o.validation -NomsAffiches $noms
                if ($f -notmatch '^=') { & $echec "$($o.name) : formule traduite sans =" }
                if (([regex]::Matches($f, '\[')).Count -ne ([regex]::Matches($o.validation, '\[')).Count) { & $echec "$($o.name) : nombre de références" }
            }
            catch { & $echec "$($o.name) : traduction de formule : $($_.Exception.Message)" }
        }
        # Versioning
        try {
            $v = Get-HNCSRDVersioningSpec -Object $o
            if ($o.kind -eq 'list' -and ($v.MajorVersions -ne 50 -or $v.EnableMinorVersions)) { & $echec "$($o.name) : versioning liste" }
        }
        catch { & $echec "$($o.name) : versioning : $($_.Exception.Message)" }
        # Matrice
        try {
            $a = Get-HNCSRDAttributionsAttendues -ObjectName $o.name -Model $modele
            foreach ($k in $a.Keys) { if ($nomsGroupes -notcontains $k) { & $echec "$($o.name) : groupe $k hors modèle" } }
            $prop = Get-HNCSRDGroupName -Code (Get-HNCSRDOwnerGroupCode -Model $modele) -Model $modele
            if ($a[$prop] -ne 'FC') { & $echec "$($o.name) : $prop doit avoir FC" }
            foreach ($g in $modele.groups) {
                $val = [string]$modele.matrix.($o.name).($g.code)
                if ($val -match '^IL\(' -and $a.Contains([string]$g.name)) { & $echec "$($o.name) : IL() ne doit rien attribuer au niveau liste" }
            }
        }
        catch { & $echec "$($o.name) : matrice : $($_.Exception.Message)" }
    }
    $v = Get-HNCSRDVersioningSpec -Object (Get-HNCSRDObject -Name 'LivrablesRD' -Model $modele)
    if (-not $v.EnableMinorVersions -or $v.MajorVersions -ne 100 -or $v.MinorVersions -ne 20) { & $echec 'LivrablesRD : versioning 100/20' }
    $v = Get-HNCSRDVersioningSpec -Object (Get-HNCSRDObject -Name 'Recrutement' -Model $modele)
    if ($v.EnableMinorVersions -or $v.MajorVersions -ne 50) { & $echec 'Recrutement : versioning 50' }
    $a = Get-HNCSRDAttributionsAttendues -ObjectName 'Candidatures' -Model $modele
    if ($a.Count -ne 3 -or $a.Contains('HNCS-RD-Administration')) { & $echec 'Candidatures : attendu G_PROP FC, G_DRD CSS, G_RD CSS (G_ADM = IL(CSS))' }
    # Notation R+IL(x) (spec v1.1.0) : R au niveau liste, aucun ajout pour l'IL
    foreach ($o in $modele.objects) {
        $a = Get-HNCSRDAttributionsAttendues -ObjectName $o.name -Model $modele
        foreach ($g in $modele.groups) {
            $val = [string]$modele.matrix.($o.name).($g.code)
            if ($val -match '^R\+IL\(') { if ($a[[string]$g.name] -ne 'R') { & $echec "$($o.name) / $($g.code) : R+IL doit donner R" } }
            elseif ($val -match '^(FC|CSS|R)$') { if ($a[[string]$g.name] -ne $val) { & $echec "$($o.name) / $($g.code) : attendu $val" } }
            elseif ($a.Contains([string]$g.name)) { & $echec "$($o.name) / $($g.code) : aucune attribution attendue pour « $val »" }
        }
    }
    $ao = @($modele.objects | ForEach-Object { $o = $_; $o.columns | Where-Object { $_.PSObject.Properties.Name -contains 'appendOnly' -and $_.appendOnly } | ForEach-Object { "$($o.name).$($_.name)" } })
    if ($ao.Count -eq 0) { & $echec 'Aucune colonne appendOnly dans le modèle (attendu au moins Livrables.CommentaireRevue)' }
    # v1.2.0 : IdHNCS indexé sans unicité ; Titre des bibliothèques non modifié
    foreach ($o in $modele.objects) {
        foreach ($c in @($o.columns | Where-Object { $_.name -eq 'IdHNCS' })) {
            $xe = ([xml](ConvertTo-HNCSRDFieldXml -Column $c -Model $modele)).DocumentElement
            if ($xe.GetAttribute('Indexed') -ne 'TRUE' -or $xe.HasAttribute('EnforceUniqueValues')) { & $echec "$($o.name).IdHNCS : indexé sans unicité attendu" }
        }
        if ($o.kind -eq 'library' -and ($o.titleLabel -or $o.titleRequired)) { & $echec "$($o.name) : le Titre des bibliothèques ne doit pas être redéfini" }
    }
    $s = Get-HNCSRDAttributionsSite -Model $modele
    if ($s.Count -ne @($modele.groups).Count -or @($s.Values | Where-Object { $_ -eq 'FC' }).Count -ne 1) { & $echec 'Site : G_PROP FC, autres R' }

    # Détection d'écarts par la comparaison de schémas
    $col = @((Get-HNCSRDObject -Name 'Candidatures' -Model $modele).columns | Where-Object { $_.name -eq 'Canal' })[0]
    $x = ConvertTo-HNCSRDFieldXml -Column $col -Model $modele
    $doc = [xml]$x
    $choices = $doc.DocumentElement.SelectSingleNode('CHOICES')
    $premier = $choices.FirstChild
    [void]$choices.RemoveChild($premier); [void]$choices.AppendChild($premier)
    $doc.DocumentElement.SetAttribute('Indexed', 'FALSE')
    $ec = @(Compare-HNCSRDFieldSchema -SchemaActuel $doc.OuterXml -SchemaAttendu $x)
    if (@($ec | Where-Object { $_.Propriete -eq 'CHOICES' }).Count -ne 1 -or @($ec | Where-Object { $_.Propriete -eq 'Indexed' }).Count -ne 1) { & $echec 'Comparaison : ordre des choix / index non détectés' }
    $doc.DocumentElement.SetAttribute('Type', 'Text')
    $ec = @(Compare-HNCSRDFieldSchema -SchemaActuel $doc.OuterXml -SchemaAttendu $x)
    if ($ec.Count -ne 1 -or $ec[0].Corrigeable) { & $echec 'Comparaison : changement de type non bloquant' }

    # Formule de validation traduite
    $f = ConvertTo-HNCSRDValidationFormula -Formula '=OR(ISBLANK([DateFin]),[DateFin]>=[DateDebut])' -NomsAffiches @{ DateFin = 'Date de fin'; DateDebut = 'Date de début' }
    if ($f -cne '=OR(ISBLANK([Date de fin]),[Date de fin]>=[Date de début])') { & $echec "Traduction de formule : $f" }

    # Marqueurs et configuration d'exemple
    $cfg = [System.IO.File]::ReadAllText((Join-Path $racine 'config/tenant.sample.json'), [System.Text.Encoding]::UTF8) | ConvertFrom-Json
    foreach ($p in $modele.parameters) {
        $r = Resolve-HNCSRDMarqueurs -Valeur $p.value -Config $cfg
        if ($r.NonResolus.Count -gt 0) { & $echec "Paramètre $($p.key) : marqueur(s) sans clé dans tenant.sample.json : $($r.NonResolus -join ', ')" }
        if ([string]$r.Valeur -match '<[A-Za-z]+>') { & $echec "Paramètre $($p.key) : marqueur restant" }
    }
    $r = Resolve-HNCSRDMarqueurs -Valeur '<BoiteRD>' -Config $cfg
    if ($r.Valeur -ne 'rd@contoso.onmicrosoft.com') { & $echec 'Résolution <BoiteRD>' }
    $membres = [System.IO.File]::ReadAllText((Join-Path $racine 'config/membres.sample.json'), [System.Text.Encoding]::UTF8) | ConvertFrom-Json
    $cles = @($membres.PSObject.Properties.Name)
    $codes = @($modele.groups | ForEach-Object { $_.code })
    if ((($cles | Sort-Object) -join ',') -ne (($codes | Sort-Object) -join ',')) { & $echec 'membres.sample.json : clés différentes des codes de groupes du modèle' }

    # Seeds : colonnes existantes, lookups résolubles dans les seeds, valeurs d'énumération
    foreach ($sp in $modele.seeds.PSObject.Properties) {
        $o = Get-HNCSRDObject -Name $sp.Name -Model $modele
        $types = Get-HNCSRDColumnTypes -Object $o
        foreach ($ligne in @($sp.Value)) {
            foreach ($n in $ligne.PSObject.Properties.Name) {
                if (-not $types.ContainsKey($n)) { & $echec "Seed $($sp.Name) : colonne $n absente"; continue }
                $val = [string]$ligne.$n
                if (-not $val) { continue }
                $rm = Resolve-HNCSRDMarqueurs -Valeur $val -Config $cfg
                if ($rm.NonResolus.Count -gt 0 -or -not $rm.Valeur) { & $echec "Seed $($sp.Name) : $n = $val non résolu par tenant.sample.json" }
                $val = [string]$rm.Valeur
                $cs = @($o.columns | Where-Object { $_.name -eq $n })
                if ($cs.Count -eq 0) { continue }
                $c = $cs[0]
                if ($c.type -eq 'Lookup') {
                    $cible = @($modele.seeds.($c.lookup) | Where-Object { $_.IdHNCS -eq $val })
                    if ($cible.Count -ne 1) { & $echec "Seed $($sp.Name) : $n = $val non résolu dans les seeds $($c.lookup)" }
                }
                elseif ($c.type -eq 'Choice' -or $c.type -eq 'MultiChoice') {
                    try { [void](ConvertTo-HNCSRDValeurChamp -Type $c.type -Column $c -Valeur $val -Model $modele) } catch { & $echec "Seed $($sp.Name) : $($_.Exception.Message)" }
                }
                elseif ($c.type -eq 'Boolean') { try { [void](ConvertTo-HNCSRDBoolean -Valeur $val) } catch { & $echec "Seed $($sp.Name) : $n = $val" } }
            }
        }
    }

    # Transitions : codes uniques, valeurs dans les énumérations
    $roles = @($modele.enums.ROLE); $objetsT = @($modele.enums.OBJET_TRANSITION)
    $vus = @{}
    foreach ($t in $modele.transitions) {
        if ($vus.ContainsKey($t.code)) { & $echec "Transition en double : $($t.code)" }
        $vus[$t.code] = $true
        $val = Get-HNCSRDTransitionValeurs -Transition $t
        foreach ($a in $val.Acteurs) { if ($roles -notcontains $a) { & $echec "$($t.code) : rôle $a" } }
        if ($objetsT -notcontains $val.Objet) { & $echec "$($t.code) : objet $($val.Objet)" }
    }

    # Navigation
    $plan = Get-HNCSRDNavigationPlan -Lot 5 -Model $modele
    $titres = @($plan | ForEach-Object { $_.Titre })
    $attendus = @('A. Recrutement', 'B. Gestion des alternants', 'C. Production R&D', 'D. Écoles et partenariats', 'Bibliothèques', 'Technique')
    if (($titres -join '|') -cne ($attendus -join '|')) { & $echec "Navigation : en-têtes $($titres -join ' | ')" }
    $liens = 0; foreach ($e in $plan) { $liens += @($e.Liens).Count }
    if ($liens -ne @($modele.objects).Count) { & $echec "Navigation : $liens liens pour $(@($modele.objects).Count) objets" }
    $plan1 = Get-HNCSRDNavigationPlan -Lot 1 -Model $modele
    $liens1 = 0; foreach ($e in $plan1) { $liens1 += @($e.Liens).Count }
    if ($liens1 -ne @(Get-HNCSRDObjects -Lot 1 -Model $modele).Count) { & $echec 'Navigation lot 1' }

    # Lots cumulatifs et colonnes de lot ultérieur
    $l1 = @(Get-HNCSRDObjects -Lot 1 -Model $modele | ForEach-Object { $_.name })
    if ($l1 -contains 'Conventions' -or $l1 -notcontains 'Candidatures') { & $echec 'Filtrage par lot' }
    $ep = Get-HNCSRDObject -Name 'EcolesPartenariats' -Model $modele
    if (@(Get-HNCSRDColumns -Object $ep -Lot 1 | Where-Object { $_.name -eq 'Convention' }).Count -ne 0) { & $echec 'Colonne lot=3 déployée au lot 1' }
    if (@(Get-HNCSRDColumns -Object $ep -Lot 3 | Where-Object { $_.name -eq 'Convention' }).Count -ne 1) { & $echec 'Colonne lot=3 absente au lot 3' }
    foreach ($o in (Get-HNCSRDObjects -Lot 5 -Model $modele)) {
        foreach ($c in (Get-HNCSRDColumns -Object $o -Lot 5 -Lookups $true)) {
            $cible = Get-HNCSRDObject -Name $c.lookup -Model $modele
            $lotCol = [int]$o.lot; if ($c.lot) { $lotCol = [int]$c.lot }
            if ([int]$cible.lot -gt $lotCol) { & $echec "$($o.name).$($c.name) : cible $($c.lookup) de lot $($cible.lot) > $lotCol" }
            if (-not $cible.prefix) { & $echec "$($o.name).$($c.name) : la cible $($c.lookup) n'a pas d'IdHNCS" }
        }
    }
    return [pscustomobject]@{ Colonnes = $nbColonnes; Echecs = $echecs.ToArray() }
}
