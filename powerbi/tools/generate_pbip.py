#!/usr/bin/env python3
"""Génère le projet PBIP HNCS-RD (modèle sémantique TMDL + rapport PBIR).

Sources (jamais modifiées) :
  - provisioning/model/model.generated.json : tables, colonnes, relations, mesures, rôles (spec § 9) ;
  - spec.md § 9.4 : colonnes calculées.

Usage :
    python powerbi/tools/generate_pbip.py

Le script réécrit intégralement `powerbi/HNCS-RD.SemanticModel/definition/`, `powerbi/HNCS-RD.Report/`
et les fichiers racine du PBIP. Il est déterministe (identifiants dérivés des noms) : deux exécutions
successives produisent des fichiers identiques. Bibliothèque standard uniquement.

Toute divergence volontaire avec la spec est déclarée dans MEASURE_OVERRIDES / EXTRA_MEASURES
et documentée dans powerbi/README.md (section « Divergences »).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PBI = ROOT / "powerbi"
MODEL_JSON = ROOT / "provisioning" / "model" / "model.generated.json"
SPEC = ROOT / "spec.md"
SM = PBI / "HNCS-RD.SemanticModel"
RP = PBI / "HNCS-RD.Report"
DEF = SM / "definition"
RDEF = RP / "definition"

NS = uuid.UUID("6f1d3c8e-2b7a-4c1e-9a55-48434e532d52")  # espace de noms fixe HNCS-RD

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
S_PBIP = f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json"
S_PBISM = f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json"
S_PBIR = f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json"
S_PLATFORM = f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json"
S_REPORT = f"{SCHEMA}/item/report/definition/report/1.0.0/schema.json"
S_VERSION = f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json"
S_PAGES = f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json"
S_PAGE = f"{SCHEMA}/item/report/definition/page/1.0.0/schema.json"
S_VISUAL = f"{SCHEMA}/item/report/definition/visualContainer/1.0.0/schema.json"

MEASURES_TABLE = "Mesures"
DEFAULT_SITE_URL = "https://VOTRE-TENANT.sharepoint.com/sites/HNCS-RD"

# Dossiers d'affichage : commentaire de section de la spec § 9.5 → dossier.
FOLDERS = {
    "Recrutement": "Recrutement",
    "Effectifs et encadrement": "Effectifs",
    "Projets et livrables": "Livrables",
    "Comptes rendus": "Comptes rendus",
    "Établissements et partenariats": "Écoles",
    "Communications et valorisation": "Communications",
    "Actions et qualité des données": "Qualité",
    "Objectifs indicatifs (cadrage § 2.4)": "Objectifs",
    "Technique": "Technique",  # spec v1.3.0 (E-01)
}

# Corrections de la spec (signalées dans README.md § Divergences). Spec v1.1.0 : aucune
# (D-01 DISTINCTCOUNTNOBLANK et D-05 [Dernière actualisation] ont été intégrées à § 9.5).
MEASURE_OVERRIDES: dict[str, str] = {}

# Mesures techniques hors spec : aucune depuis la v1.1.0.
EXTRA_MEASURES: list[tuple[str, str, str, str]] = []

# Dossier d'affichage imposé par mesure (aucun depuis la v1.3.0).
FOLDER_OVERRIDES: dict[str, str] = {}  # v1.3.0 : section « Technique » dans la spec (E-01)

# Format des mesures non numériques.
FORMAT_OVERRIDES = {"Dernière actualisation": "dd/MM/yyyy HH:mm"}

# Listes facultatives : absence tolérée (HTTP 404 → table vide), car créées à un lot ultérieur au lot 4.
OPTIONAL_LISTS = {"GitlabSync"}  # lot 5


# --------------------------------------------------------------------------- utilitaires

def guid(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


def hexid(*parts: str) -> str:
    return hashlib.sha1("/".join(parts).encode("utf-8")).hexdigest()[:20]


def q(name: str) -> str:
    """Nom TMDL : entre apostrophes si nécessaire, apostrophes internes doublées."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        return name
    return "'" + name.replace("'", "''") + "'"


def tabify(line: str) -> str:
    """Remplace l'indentation par groupes de 4 espaces par des tabulations."""
    m = re.match(r"^( +)", line)
    if not m:
        return line
    n = len(m.group(1))
    return "\t" * (n // 4) + " " * (n % 4) + line[n:]


def block(text: str, level: int) -> list[str]:
    """Bloc multiligne (DAX ou M) indenté au niveau `level` (tabulations)."""
    out = []
    for raw in text.strip("\n").splitlines():
        if not raw.strip():
            continue
        out.append("\t" * level + tabify(raw.rstrip()))
    return out


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, data) -> None:
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


# --------------------------------------------------------------------------- lecture de la spec

def load_model() -> dict:
    return json.loads(MODEL_JSON.read_text(encoding="utf-8"))


def parse_measures(dax: str) -> list[dict]:
    """Découpe le bloc MESURES (§ 9.5) en mesures {name, expr, folder}."""
    measures: list[dict] = []
    folder = None
    cur = None
    for line in dax.splitlines():
        if not line.strip():
            cur = None
            continue
        m = re.match(r"^// -+ (.+?) -+\s*$", line)
        if m:
            folder = FOLDERS[m.group(1)]
            cur = None
            continue
        if line.startswith("//"):
            continue
        if not line[0].isspace():
            m = re.match(r"^(.+?) =(.*)$", line)
            cur = {"name": m.group(1).strip(), "lines": [], "folder": folder}
            if m.group(2).strip():
                cur["lines"].append(m.group(2).strip())
            measures.append(cur)
        else:
            cur["lines"].append(line[4:] if line.startswith("    ") else line.lstrip())
    for ms in measures:
        ms["expr"] = "\n".join(ms.pop("lines"))
    return measures


def parse_calculated_columns() -> dict[str, list[tuple[str, str]]]:
    """Colonnes calculées de spec.md § 9.4 : {table: [(colonne, DAX)]}."""
    lines = SPEC.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("### 9.4"))
    i = next(j for j in range(start, len(lines)) if lines[j].startswith("```dax"))
    body = []
    for l in lines[i + 1:]:
        if l.startswith("```"):
            break
        body.append(l)
    result: dict[str, list] = {}
    table = None
    cur = None
    for line in body:
        m = re.match(r"^// (.+?) : PoleNom = LOOKUPVALUE \( Poles\[Title\], Poles\[Id\], <table>\[PoleId ou PolePressentiId\] \)$", line)
        if m:
            for t in [x.strip() for x in m.group(1).split(",")]:
                key = "PolePressentiId" if t == "Candidatures" else "PoleId"
                result.setdefault(t, []).append(
                    ("PoleNom", f"LOOKUPVALUE ( Poles[Title], Poles[Id], {t}[{key}] )"))
            cur = None
            continue
        m = re.match(r"^// (\w+)\s*$", line)
        if m:
            table = m.group(1)
            cur = None
            continue
        if line.startswith("//"):
            cur = None  # commentaire libre (ex. « // Mesures (table de mesures) : DerniereActualisation … »)
            continue
        if not line.strip():
            continue
        if not line[0].isspace():
            m = re.match(r"^(\w+) =(.*)$", line)
            cur = [m.group(1), [m.group(2).strip()] if m.group(2).strip() else []]
            result.setdefault(table, []).append(cur)
        else:
            cur[1].append(line[4:] if line.startswith("    ") else line.lstrip())
    return {t: [(c[0], c[1]) if isinstance(c, tuple) else (c[0], "\n".join(c[1])) for c in cols]
            for t, cols in result.items()}


CALC_TYPES = {
    "DateReceptionJour": ("dateTime", "date"),
    "EstPreselectionnee": ("boolean", None),
    "EstActive": ("boolean", None),
    "DelaiPreselectionJours": ("int64", None),
    "DelaiTraitementJours": ("int64", None),
    "EstPOCouPlan": ("boolean", None),
    "DoDComplete": ("boolean", None),
    "CapitalisationComplete": ("boolean", None),
    "DatePremierDepotJour": ("dateTime", "date"),
    "PoleNom": ("string", None),
}


# --------------------------------------------------------------------------- résolution des colonnes

def resolve_column(obj: dict, col: dict) -> dict:
    """Associe une colonne PBI_TABLES à sa colonne SharePoint : champ $select, genre M, type TMDL."""
    name, src, transform = col["name"], col["source"], col["transform"]
    cols = {c["name"]: c for c in obj["columns"]}
    cols["Title"] = obj["titleColumn"]
    if src == "Id":
        return {"name": name, "select": "Id", "raw": "Id", "kind": "int", "fk": False, "sp": None}
    if src in cols:
        sp = cols[src]
        select = src
    elif src.endswith("Id") and cols.get(src[:-2], {}).get("type") in ("Lookup", "LookupMulti"):
        sp = cols[src[:-2]]
        return {"name": name, "select": src, "raw": src, "kind": "int", "fk": True, "sp": sp}
    elif src.endswith("Email") and cols.get(src[:-5], {}).get("type") == "User":
        sp = cols[src[:-5]]
        return {"name": name, "select": f"{src[:-5]}/EMail", "raw": src[:-5], "kind": "user",
                "expand": src[:-5], "fk": False, "sp": sp}
    else:
        raise SystemExit(f"Colonne source inconnue : {obj['name']}.{src}")
    t = sp["type"]
    if transform == "bool":
        if t != "URL":
            raise SystemExit(f"Transformation booléenne attendue sur une URL : {obj['name']}.{src}")
        kind = "lien"
    elif t == "URL":
        kind = "url"
    elif t in ("Text", "Choice", "Note"):
        kind = "text"
    elif t == "Number":
        kind = "int" if str(sp.get("decimals")) == "0" else "num"
    elif t == "Boolean":
        kind = "bool"
    elif t == "Date":
        kind = "date"
    elif t == "DateTime":
        kind = "datetime"
    else:
        raise SystemExit(f"Type non pris en charge pour Power BI : {obj['name']}.{src} ({t})")
    return {"name": name, "select": select, "raw": src, "kind": kind, "fk": False, "sp": sp}


TMDL_TYPE = {"int": "int64", "num": "double", "text": "string", "bool": "boolean",
             "date": "dateTime", "datetime": "dateTime", "user": "string", "lien": "boolean", "url": "string"}
FORMAT = {"int": "0", "num": "#,##0.##", "date": "dd/MM/yyyy", "datetime": "dd/MM/yyyy HH:mm"}


def m_list(items: list[str]) -> str:
    return "{" + ", ".join('"' + i.replace('"', '""') + '"' for i in items) + "}"


# --------------------------------------------------------------------------- M (Power Query)

M_LIRE_LISTE = r'''
(nomInterne as text, champs as list, optional expansions as nullable list, optional facultative as nullable logical, optional bibliotheque as nullable logical) as table =>
let
    // Lecture paginée de l'API REST SharePoint : seules les colonnes de `champs` sont demandées ($select).
    // La liste est désignée par son nom interne (URL), stable, et non par son titre affiché (spec § 9.1) :
    // listes GetList('<chemin du site>/Lists/<NomInterne>'), bibliothèques GetList('<chemin du site>/<NomInterne>').
    cheminSite = Text.TrimEnd(Uri.Parts(SiteUrl)[Path], "/"),
    urlServeur = cheminSite & (if bibliotheque = true then "/" else "/Lists/") & nomInterne,
    chemin = "_api/web/GetList('" & Text.Replace(urlServeur, "'", "''") & "')/items",
    requeteBase = [#"$select" = Text.Combine(champs, ","), #"$top" = "5000"]
        & (if expansions = null or List.IsEmpty(expansions) then [] else [#"$expand" = Text.Combine(expansions, ",")]),
    statutsGeres = if facultative = true then {404} else {},
    lirePage = (jeton as nullable text) as record =>
        let
            requete = if jeton = null then requeteBase else requeteBase & [#"$skiptoken" = jeton],
            reponse = Web.Contents(
                SiteUrl,
                [
                    RelativePath = chemin,
                    Query = requete,
                    Headers = [Accept = "application/json;odata=nometadata"],
                    ManualStatusHandling = statutsGeres
                ]
            ),
            statut = Value.Metadata(reponse)[Response.Status],
            json = if statut = 404 then [value = {}] else Json.Document(reponse, 65001),
            suivant = Record.FieldOrDefault(json, "odata.nextLink", null),
            parametres = if suivant = null then [] else Uri.Parts(suivant)[Query],
            jetonSuivant = Record.FieldOrDefault(parametres, "$skiptoken", Record.FieldOrDefault(parametres, "%24skiptoken", null))
        in
            [Lignes = json[value], Jeton = jetonSuivant],
    pages = List.Generate(
        () => lirePage(null),
        (page) => page <> null,
        (page) => if page[Jeton] = null then null else lirePage(page[Jeton]),
        (page) => page[Lignes]
    ),
    lignes = List.Combine(pages),
    colonnes = List.Distinct(List.Transform(champs, (c) => Text.BeforeDelimiter(c, "/"))),
    table = Table.FromRows(
        List.Transform(lignes, (ligne) => List.Transform(colonnes, (c) => Record.FieldOrDefault(ligne, c, null))),
        colonnes
    )
in
    table
'''

M_HEURE_PARIS = r'''
(valeur as any) as nullable datetime =>
let
    // SharePoint renvoie les dates en UTC (y compris les colonnes « date seule », à minuit heure de Paris).
    // Conversion explicite en heure de Paris (UTC+1, UTC+2 du dernier dimanche de mars au dernier dimanche d'octobre),
    // indépendante du fuseau de la machine qui actualise (le service Power BI est en UTC).
    horodatage =
        if valeur = null then null
        else if Value.Is(valeur, type text) then DateTimeZone.FromText(valeur, "en-US")
        else DateTimeZone.From(valeur),
    utc = if horodatage = null then null else DateTimeZone.RemoveZone(DateTimeZone.SwitchZone(horodatage, 0, 0)),
    dernierDimanche = (annee as number, mois as number) as datetime =>
        let
            fin = Date.EndOfMonth(#date(annee, mois, 1)),
            dimanche = Date.AddDays(fin, -Date.DayOfWeek(fin, Day.Sunday))
        in
            DateTime.From(dimanche) + #duration(0, 1, 0, 0),
    decalage =
        if utc = null then 0
        else if utc >= dernierDimanche(Date.Year(utc), 3) and utc < dernierDimanche(Date.Year(utc), 10) then 2
        else 1,
    resultat = if utc = null then null else utc + #duration(0, decalage, 0, 0)
in
    resultat
'''

M_TYPER = r'''
(source as table, schema as list) as table =>
let
    // schema : liste de paires {colonne, genre} ; genre ∈ int, num, text, bool, date, datetime, user, lien (URL → booléen), url (URL → texte).
    convertir = (genre as text) as function =>
        if genre = "int" then ((v) => if v = null then null else Int64.From(v))
        else if genre = "num" then ((v) => if v = null then null else Number.From(v))
        else if genre = "bool" then ((v) => if v = null then false else Logical.From(v))
        else if genre = "datetime" then ((v) => fnHeureParis(v))
        else if genre = "date" then ((v) => if v = null then null else DateTime.Date(fnHeureParis(v)))
        else if genre = "user" then ((v) =>
            let
                courriel = if v = null then null else if Value.Is(v, type record) then Record.FieldOrDefault(v, "EMail", null) else Text.From(v)
            in
                if courriel = null or courriel = "" then null else Text.Lower(courriel))
        else if genre = "lien" then ((v) =>
            let
                url = if v = null then null else if Value.Is(v, type record) then Record.FieldOrDefault(v, "Url", null) else Text.From(v)
            in
                url <> null and url <> "")
        else if genre = "url" then ((v) =>
            let
                url = if v = null then null else if Value.Is(v, type record) then Record.FieldOrDefault(v, "Url", null) else Text.From(v)
            in
                if url = null or url = "" then null else url)
        else ((v) => if v = null then null else Text.From(v)),
    typeM = (genre as text) as type =>
        if genre = "int" then Int64.Type
        else if genre = "num" then type number
        else if genre = "bool" or genre = "lien" then type logical
        else if genre = "datetime" then type datetime
        else if genre = "date" then type date
        else type text,
    resultat = Table.TransformColumns(source, List.Transform(schema, (s) => {s{0}, convertir(s{1}), typeM(s{1})}))
in
    resultat
'''


def partition_m(list_name: str, cols: list[dict], optional: bool) -> str:
    selects = []
    expands = []
    for c in cols:
        if c["select"] not in selects:
            selects.append(c["select"])
        if c.get("expand") and c["expand"] not in expands:
            expands.append(c["expand"])
    # Colonnes booléennes dérivées d'une URL (ADocument, AGitlab) : copie de la colonne brute, puis typage,
    # afin que la même colonne SharePoint puisse être importée à la fois en clair et en booléen (LienDocument).
    copies = [(c["raw"], c["name"]) for c in cols if c["kind"] == "lien"]
    for c in cols:
        if c["kind"] == "lien":
            c["typed"] = c["name"]
        else:
            c["typed"] = c["raw"]
    schema = "{" + ", ".join('{"%s", "%s"}' % (c["typed"], c["kind"]) for c in cols) + "}"
    renames = [(c["raw"], c["name"]) for c in cols if c["kind"] != "lien" and c["raw"] != c["name"]]
    lines = [
        "let",
        f'    Source = fnLireListeSharePoint("{list_name}", {m_list(selects)}, {m_list(expands)}, {"true" if optional else "false"}),',
    ]
    prev = "Source"
    for i, (raw, name) in enumerate(copies, 1):
        lines.append(f'    Copie{i} = Table.DuplicateColumn({prev}, "{raw}", "{name}"),')
        prev = f"Copie{i}"
    lines.append(f"    Typee = fnTyperColonnes({prev}, {schema}),")
    prev = "Typee"
    if renames:
        lines.append("    Renommee = Table.RenameColumns(Typee, {" +
                     ", ".join('{"%s", "%s"}' % r for r in renames) + "}),")
        prev = "Renommee"
    lines.append(f"    Resultat = Table.SelectColumns({prev}, {m_list([c['name'] for c in cols])})")
    lines += ["in", "    Resultat"]
    return "\n".join(lines)


M_SUJET_DOMAINE = '''
let
    Source = fnLireListeSharePoint("{name}", {{"Id", "DomainesId"}}, {{}}, false),
    // DomainesId : tableau JSON d'identifiants (format nometadata) ou enregistrement [results] (format verbose).
    Listes = Table.TransformColumns(Source, {{{{"DomainesId", (v) => if v = null then {{}} else if Value.Is(v, type record) then Record.FieldOrDefault(v, "results", {{}}) else v, type list}}}}),
    Developpee = Table.ExpandListColumn(Listes, "DomainesId"),
    NonVides = Table.SelectRows(Developpee, each [DomainesId] <> null),
    Renommee = Table.RenameColumns(NonVides, {{{{"Id", "SujetId"}}, {{"DomainesId", "DomaineId"}}}}),
    Typee = Table.TransformColumnTypes(Renommee, {{{{"SujetId", Int64.Type}}, {{"DomaineId", Int64.Type}}}}),
    Resultat = Table.Distinct(Table.SelectColumns(Typee, {{"SujetId", "DomaineId"}}))
in
    Resultat
'''

M_MESURES = '''
let
    // Table de mesures : une seule ligne portant l'horodatage de l'actualisation (heure de Paris).
    Source = #table(type table [DerniereActualisation = datetime], {{fnHeureParis(DateTimeZone.FixedUtcNow())}})
in
    Source
'''

DAX_CALENDRIER = '''
VAR DebutDonnees =
    MINX (
        FILTER (
            {
                MIN ( Candidatures[DateReception] ),
                MIN ( Livrables[Echeance] ),
                MIN ( ComptesRendus[Echeance] ),
                MIN ( Alternants[DateDebut] ),
                MIN ( CommunicationsRD[DateEffective] ),
                MIN ( Mobilisations[DateMobilisation] )
            },
            NOT ISBLANK ( [Value] )
        ),
        [Value]
    )
VAR FinDonnees =
    MAXX (
        FILTER (
            {
                MAX ( Candidatures[DateReception] ),
                MAX ( Livrables[Echeance] ),
                MAX ( ComptesRendus[Echeance] ),
                MAX ( Alternants[DateFin] ),
                MAX ( Alternants[DateFinReelle] ),
                MAX ( CommunicationsRD[DateEffective] ),
                MAX ( Mobilisations[DateMobilisation] )
            },
            NOT ISBLANK ( [Value] )
        ),
        [Value]
    )
// Bornes : années complètes couvrant les données, au moins 2025-2028, plafonnées à 2020-2035 (saisies aberrantes).
VAR AnneeDebut = IF ( ISBLANK ( DebutDonnees ), 2025, MAX ( MIN ( YEAR ( DebutDonnees ), 2025 ), 2020 ) )
VAR AnneeFin = IF ( ISBLANK ( FinDonnees ), 2028, MIN ( MAX ( YEAR ( FinDonnees ), 2028 ), 2035 ) )
RETURN
    ADDCOLUMNS (
        CALENDAR ( DATE ( AnneeDebut, 1, 1 ), DATE ( AnneeFin, 12, 31 ) ),
        "Annee", YEAR ( [Date] ),
        "Mois", FORMAT ( [Date], "mmmm" ),
        "NumMois", MONTH ( [Date] ),
        "Trimestre", "T" & QUARTER ( [Date] ),
        "Semaine",
            VAR AnneeIso = YEAR ( [Date] - WEEKDAY ( [Date], 2 ) + 4 )
            RETURN AnneeIso & "-S" & FORMAT ( WEEKNUM ( [Date], 21 ), "00" ),
        "AnneeMois", FORMAT ( [Date], "yyyy-mm" )
    )
'''

CALENDRIER_COLUMNS = [
    # nom, type, format, sortBy
    ("Date", "dateTime", "dd/MM/yyyy", None),
    ("Annee", "int64", "0", None),
    ("Mois", "string", None, "NumMois"),
    ("NumMois", "int64", "0", None),
    ("Trimestre", "string", None, None),
    ("Semaine", "string", None, None),
    ("AnneeMois", "string", None, None),
]

DAX_OBJECTIFS = '''
DATATABLE (
    "Indicateur", STRING,
    "Cible", DOUBLE,
    {
        { "POC réalisés", 5 },
        { "Plans de stratégie formalisés", 4 },
        { "Mobilisations commerciales", 8 },
        { "Communications publiées", 30 },
        { "Partenariats académiques actifs", 3 },
        { "Alternants accueillis", 3 },
        { "Couverture des domaines cibles", 1 }
    }
)
'''


# --------------------------------------------------------------------------- TMDL

def tmdl_column(table: str, name: str, dtype: str, *, source: str | None = None, expr: str | None = None,
                fmt: str | None = None, hidden: bool = False, key: bool = False, sort_by: str | None = None,
                inferred_name: bool = False, date_only: bool = False, category: str | None = None) -> list[str]:
    out = []
    if expr is not None:
        if "\n" in expr:
            out.append(f"\tcolumn {q(name)} =")
            out += block(expr, 3)
        else:
            out.append(f"\tcolumn {q(name)} = {expr}")
    else:
        out.append(f"\tcolumn {q(name)}")
    out.append(f"\t\tdataType: {dtype}")
    if inferred_name:
        out.append("\t\tisNameInferred")
    if category:
        out.append(f"\t\tdataCategory: {category}")
    if key:
        out.append("\t\tisKey")
    if hidden:
        out.append("\t\tisHidden")
    if fmt:
        out.append(f"\t\tformatString: {fmt}")
    out.append(f"\t\tlineageTag: {guid('col', table, name)}")
    out.append("\t\tsummarizeBy: none")
    if source is not None:
        out.append(f"\t\tsourceColumn: {source}")
    if sort_by:
        out.append(f"\t\tsortByColumn: {sort_by}")
    out.append("")
    out.append("\t\tannotation SummarizationSetBy = Automatic")
    if date_only:
        out.append("")
        out.append("\t\tannotation UnderlyingDateTimeDataType = Date")
    out.append("")
    return out


def tmdl_partition(name: str, kind: str, source: str) -> list[str]:
    out = [f"\tpartition {q(name)} = {kind}", "\t\tmode: import", "\t\tsource ="]
    out += block(source, 4)
    out.append("")
    return out


def measure_format(name: str) -> str:
    if name.startswith("Taux") or name.startswith("Couverture"):
        return "0.0%"
    if name.startswith("Délai") or name.startswith("Avancement"):
        return "#,##0.0"
    if name == "Seuil attente (j)":
        return "0"
    if name == "Cible":
        return "#,##0.##"
    return "#,##0"


def tmdl_measure(table: str, name: str, expr: str, fmt: str, folder: str) -> list[str]:
    out = []
    if "\n" in expr:
        out.append(f"\tmeasure {q(name)} =")
        out += block(expr, 3)
    else:
        out.append(f"\tmeasure {q(name)} = {expr}")
    out.append(f"\t\tformatString: {fmt}")
    out.append(f"\t\tdisplayFolder: {folder}")
    out.append(f"\t\tlineageTag: {guid('measure', name)}")
    out.append("")
    return out


def build_model(model: dict) -> dict:
    objs = {o["name"]: o for o in model["objects"]}
    calc = parse_calculated_columns()
    pbi = model["powerbi"]
    tables_out: dict[str, list[str]] = {}
    query_order = ["SiteUrl", "fnLireListeSharePoint", "fnHeureParis", "fnTyperColonnes"]

    for t in pbi["tables"]:
        name = t["table"]
        if name in ("Calendrier", "Objectifs"):
            continue
        lines = [f"table {q(name)}", f"\tlineageTag: {guid('table', name)}", ""]
        if name == "SujetDomaine":
            src = objs["SujetsRD"]
            for c in t["columns"]:
                lines += tmdl_column(name, c["name"], "int64", source=c["name"], fmt="0", hidden=True)
            lines += tmdl_partition(name, "m", M_SUJET_DOMAINE.format(name=src["name"]))
        else:
            obj = objs[t["source"]]
            cols = [resolve_column(obj, c) for c in t["columns"]]
            for c in cols:
                lines += tmdl_column(
                    name, c["name"], TMDL_TYPE[c["kind"]], source=c["name"], fmt=FORMAT.get(c["kind"]),
                    hidden=c["fk"], key=(c["name"] == "Id"), date_only=(c["kind"] == "date"),
                    category="WebUrl" if c["kind"] == "url" else None)
            for cname, expr in calc.get(name, []):
                dtype, special = CALC_TYPES[cname]
                lines += tmdl_column(name, cname, dtype, expr=expr,
                                     fmt="dd/MM/yyyy" if special == "date" else ("0" if dtype == "int64" else None),
                                     date_only=(special == "date"))
            lines += tmdl_partition(name, "m", partition_m(obj["name"], cols, t["source"] in OPTIONAL_LISTS))
        lines += [f"\tannotation PBI_ResultType = Table", ""]
        tables_out[name] = lines
        query_order.append(name)

    # Calendrier (table calculée DAX)
    lines = ["table Calendrier", "\tdataCategory: Time", f"\tlineageTag: {guid('table', 'Calendrier')}", ""]
    for cname, dtype, fmt, sort_by in CALENDRIER_COLUMNS:
        lines += tmdl_column("Calendrier", cname, dtype, source=f"[{cname}]", fmt=fmt, key=(cname == "Date"),
                             sort_by=sort_by, inferred_name=True, date_only=(cname == "Date"))
    lines += tmdl_partition("Calendrier", "calculated", DAX_CALENDRIER)
    tables_out["Calendrier"] = lines

    # Objectifs (DATATABLE)
    lines = ["table Objectifs", f"\tlineageTag: {guid('table', 'Objectifs')}", ""]
    lines += tmdl_column("Objectifs", "Indicateur", "string", source="[Indicateur]", inferred_name=True)
    lines += tmdl_column("Objectifs", "Cible", "double", source="[Cible]", fmt="#,##0.##", inferred_name=True)
    lines += tmdl_partition("Objectifs", "calculated", DAX_OBJECTIFS)
    tables_out["Objectifs"] = lines

    # Mesures
    measures = parse_measures(pbi["measuresDax"])
    names = [m["name"] for m in measures]
    if names != pbi["measures"]:
        raise SystemExit("Le découpage des mesures ne correspond pas à model.powerbi.measures")
    lines = [f"table {MEASURES_TABLE}", f"\tlineageTag: {guid('table', MEASURES_TABLE)}", ""]
    for ms in measures:
        expr = MEASURE_OVERRIDES.get(ms["name"], ms["expr"])
        lines += tmdl_measure(MEASURES_TABLE, ms["name"], expr,
                              FORMAT_OVERRIDES.get(ms["name"], measure_format(ms["name"])),
                              FOLDER_OVERRIDES.get(ms["name"], ms["folder"]))
    for name, expr, fmt, folder in EXTRA_MEASURES:
        lines += tmdl_measure(MEASURES_TABLE, name, expr, fmt, folder)
    lines += tmdl_column(MEASURES_TABLE, "DerniereActualisation", "dateTime", source="DerniereActualisation",
                         fmt="dd/MM/yyyy HH:mm", hidden=True)
    lines += tmdl_partition(MEASURES_TABLE, "m", M_MESURES)
    lines += ["\tannotation PBI_ResultType = Table", ""]
    tables_out[MEASURES_TABLE] = lines
    query_order.append(MEASURES_TABLE)

    return {"tables": tables_out, "query_order": query_order}


def build_relationships(model: dict) -> str:
    out = []
    for r in model["powerbi"]["relations"]:
        ft, fc = re.match(r"^(\w+)\[(\w+)\]$", r["from"]).groups()
        tt, tc = re.match(r"^(\w+)\[(\w+)\]$", r["to"]).groups()
        out.append(f"relationship {guid('rel', r['from'], r['to'])}")
        if not r["active"]:
            out.append("\tisActive: false")
        out.append(f"\tfromColumn: {q(ft)}.{q(fc)}")
        out.append(f"\ttoColumn: {q(tt)}.{q(tc)}")
        out.append("")
    return "\n".join(out)


def build_roles(model: dict) -> dict[str, str]:
    roles = {}
    for r in model["powerbi"]["roles"]:
        name = r["role"]
        lines = [f"role {q(name)}", "\tmodelPermission: read", ""]
        filters = re.findall(r"`(\w+)` : `([^`]+)`", r["filters"]) if r["filters"].strip() != "aucun" else []
        ols = re.findall(r"`(\w+)\[(\w+)\]` : aucun accès", r["ols"]) if r["ols"].strip() != "aucune" else []
        if r["filters"].strip() != "aucun" and not filters:
            raise SystemExit(f"Filtres RLS illisibles pour {name}")
        if r["ols"].strip() != "aucune" and not ols:
            raise SystemExit(f"OLS illisible pour {name}")
        tables = list(dict.fromkeys([t for t, _ in filters] + [t for t, _ in ols]))
        for t in tables:
            f = next((e for tt, e in filters if tt == t), None)
            if f is None:
                lines.append(f"\ttablePermission {q(t)}")
            elif len(f) > 90:
                lines.append(f"\ttablePermission {q(t)} =")
                lines += block(pretty_dax(f), 3)
            else:
                lines.append(f"\ttablePermission {q(t)} = {f}")
            for tt, c in ols:
                if tt == t:
                    lines.append(f"\t\tcolumnPermission {q(c)}")
                    lines.append("\t\t\tmetadataPermission: none")
            lines.append("")
        lines.append(f"\tannotation HNCS_Membres = {r['members']} (affectation dans le service Power BI, H-16)")
        lines.append("")
        roles[name] = "\n".join(lines)
    return roles


def pretty_dax(expr: str) -> str:
    """Mise en forme du filtre RLS Referent sur plusieurs lignes (contenu inchangé)."""
    if expr.startswith("Alternants[Id] IN CALCULATETABLE"):
        return ("Alternants[Id]\n"
                "    IN CALCULATETABLE (\n"
                "        VALUES ( Affectations[AlternantId] ),\n"
                "        FILTER (\n"
                "            ALL ( Affectations ),\n"
                "            Affectations[ReferentId]\n"
                "                IN CALCULATETABLE ( VALUES ( Referents[Id] ), Referents[CompteEmail] = USERPRINCIPALNAME () )\n"
                "        )\n"
                "    )")
    return expr


def build_expressions(site_url: str) -> str:
    lines = [
        f'expression SiteUrl = "{site_url}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]',
        f"\tlineageTag: {guid('expr', 'SiteUrl')}",
        "",
        "\tannotation PBI_ResultType = Text",
        "",
    ]
    for name, body in (("fnLireListeSharePoint", M_LIRE_LISTE), ("fnHeureParis", M_HEURE_PARIS),
                       ("fnTyperColonnes", M_TYPER)):
        lines.append(f"expression {name} =")
        lines += block(body, 2)
        lines.append(f"\tlineageTag: {guid('expr', name)}")
        lines.append("")
        lines.append("\tannotation PBI_ResultType = Function")
        lines.append("")
    return "\n".join(lines)


def build_model_tmdl(table_names: list[str], role_names: list[str], query_order: list[str]) -> str:
    lines = [
        "model Model",
        "\tculture: fr-FR",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tdiscourageImplicitMeasures",
        "\tsourceQueryCulture: fr-FR",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        "annotation PBI_QueryOrder = " + json.dumps(query_order, ensure_ascii=False),
        "",
    ]
    for t in table_names:
        lines.append(f"ref table {q(t)}")
    lines.append("")
    for r in role_names:
        lines.append(f"ref role {q(r)}")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- PBIR (rapport)

def col(t: str, c: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}


def mea(n: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": MEASURES_TABLE}}, "Property": n}}


def lit(v) -> dict:
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}


def proj(field: dict, display: str | None = None) -> dict:
    kind = "Column" if "Column" in field else "Measure"
    e = field[kind]["Expression"]["SourceRef"]["Entity"]
    p = field[kind]["Property"]
    d = {"field": field, "queryRef": f"{e}.{p}"}
    if display:
        d["displayName"] = display
    return d


def f_in(t: str, c: str, values: list[str], name: str) -> dict:
    alias = t[0].lower()
    return {
        "name": name,
        "field": col(t, c),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": t, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": c}}],
                "Values": [[{"Literal": {"Value": "'" + v.replace("'", "''") + "'"}}] for v in values],
            }}}],
        },
        "howCreated": "User",
    }


def f_bool(t: str, c: str, value: bool, name: str) -> dict:
    """Filtre de visuel « colonne booléenne = valeur »."""
    alias = t[0].lower()
    return {
        "name": name,
        "field": col(t, c),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": t, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": c}}],
                "Values": [[{"Literal": {"Value": "true" if value else "false"}}]],
            }}}],
        },
        "howCreated": "User",
    }


def f_not_blank(t: str, c: str, name: str) -> dict:
    alias = t[0].lower()
    return {
        "name": name,
        "field": col(t, c),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": t, "Type": 0}],
            "Where": [{"Condition": {"Not": {"Expression": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": c}}],
                "Values": [[{"Literal": {"Value": "null"}}]],
            }}}}}],
        },
        "howCreated": "User",
    }


class Page:
    def __init__(self, order: int, display: str, height: int = 720):
        self.order = order
        self.display = display
        self.name = hexid("page", display)
        self.height = height
        self.visuals: list[dict] = []

    def add(self, key: str, vtype: str, pos: tuple, roles: dict | None = None, *, title: str | None = None,
            objects: dict | None = None, filters: list | None = None, sort: list | None = None) -> None:
        x, y, w, h = pos
        name = hexid("visual", self.display, key)
        visual: dict = {"visualType": vtype}
        if roles:
            qs = {}
            for role, fields in roles.items():
                qs[role] = {"projections": [f if "field" in f else proj(f) for f in fields]}
            visual["query"] = {"queryState": qs}
            if sort:
                visual["query"]["sortDefinition"] = {
                    "sort": [{"field": f, "direction": d} for f, d in sort], "isDefaultSort": False}
        if objects:
            visual["objects"] = objects
        if title:
            visual["visualContainerObjects"] = {"title": [{"properties": {"show": lit(True), "text": lit(title)}}]}
        visual["drillFilterOtherVisuals"] = True
        container = {
            "$schema": S_VISUAL,
            "name": name,
            "position": {"x": x, "y": y, "z": len(self.visuals) * 1000, "height": h, "width": w,
                         "tabOrder": len(self.visuals) * 1000},
            "visual": visual,
        }
        if filters:
            container["filterConfig"] = {"filters": filters}
        self.visuals.append(container)

    # gabarits ---------------------------------------------------------
    def header(self, slicers: list[tuple]) -> None:
        self.add("titre", "textbox", (16, 8, 900, 44), objects={"general": [{"properties": {"paragraphs": [
            {"textRuns": [{"value": f"{self.order}. {self.display}",
                           "textStyle": {"fontWeight": "bold", "fontSize": "20pt"}}]}]}}]})
        self.add("actualisation", "card", (1064, 4, 200, 60), {"Values": [mea("Dernière actualisation")]})
        for i, (t, c, label, mode) in enumerate(slicers):
            self.add(f"segment-{t}-{c}", "slicer", (16 + i * 208, 58, 200, 56), {"Values": [proj(col(t, c), label)]},
                     title=label, objects={"data": [{"properties": {"mode": lit(mode)}}]})

    def cards(self, measures: list[str], y: int = 122, h: int = 84) -> None:
        n = len(measures)
        w = (1248 - (n - 1) * 8) // n
        for i, m in enumerate(measures):
            self.add(f"carte-{m}", "card", (16 + i * (w + 8), y, w, h), {"Values": [mea(m)]})


def gauge_filter(indicator: str) -> list:
    return [f_in("Objectifs", "Indicateur", [indicator], hexid("filtre", indicator))]


def build_pages() -> list[Page]:
    """Pages et visuels de spec.md § 9.7 et specs/powerbi-rapport.md (v1.1.0).

    `NomAffichage` n'est utilisé par aucun visuel (§ 9.2) : les tableaux identifient les alternants par IdHNCS.
    """
    pages: list[Page] = []
    dd, between = "Dropdown", "Between"
    alternant = proj(col("Alternants", "IdHNCS"), "Alternant")

    # 1. Vue exécutive -------------------------------------------------
    p = Page(1, "Vue exécutive")
    p.header([("Calendrier", "Annee", "Année", dd), ("Calendrier", "Trimestre", "Trimestre", dd)])
    p.cards(["Alternants actifs", "Candidatures reçues", "Sujets actifs", "Livrables validés", "Livrables en retard",
             "POC réalisés", "Plans de stratégie formalisés", "Communications publiées",
             "Partenariats académiques actifs", "Mobilisations commerciales"])
    gauges = ["Alternants accueillis", "POC réalisés", "Plans de stratégie formalisés", "Mobilisations commerciales",
              "Communications publiées", "Partenariats académiques actifs"]
    w = (1248 - 5 * 8) // 6
    for i, m in enumerate(gauges):
        p.add(f"jauge-{m}", "gauge", (16 + i * (w + 8), 214, w, 188),
              {"Y": [mea(m)], "TargetValue": [mea("Cible")]}, title=f"{m} / cible", filters=gauge_filter(m))
    p.add("livrables-statut", "clusteredColumnChart", (16, 410, 410, 300),
          {"Category": [col("Livrables", "Statut")], "Y": [mea("Livrables")]}, title="Livrables par statut")
    p.add("candidatures-statut", "clusteredBarChart", (434, 410, 410, 300),
          {"Category": [col("Candidatures", "Statut")], "Y": [mea("Candidatures reçues")]},
          title="Candidatures par statut (agrégé)")
    p.add("jauge-couverture", "gauge", (852, 410, 412, 300),
          {"Y": [mea("Couverture des domaines cibles")], "TargetValue": [mea("Cible")]},
          title="Couverture des domaines cibles / cible",
          objects={"axis": [{"properties": {"min": lit(0), "max": lit(1)}}]},
          filters=gauge_filter("Couverture des domaines cibles"))
    pages.append(p)

    # 2. Recrutement ---------------------------------------------------
    p = Page(2, "Recrutement")
    p.header([("Candidatures", "Canal", "Canal", dd), ("Offres", "Title", "Offre", dd),
              ("Calendrier", "Date", "Période (réception)", between), ("Candidatures", "Statut", "Statut", dd)])
    p.cards(["Candidatures reçues", "Candidatures actives", "Candidatures en attente",
             "Délai moyen de présélection (j)", "Délai moyen de traitement (j)", "Taux de présélection",
             "Taux de transformation", "Doublons signalés"])
    p.add("entonnoir", "funnel", (16, 214, 400, 248),
          {"Y": [mea(m) for m in ["Candidatures reçues", "Candidatures analysées", "Candidatures présélectionnées",
                                  "Candidatures avec entretien réalisé", "Candidatures retenues",
                                  "Candidatures intégrées"]]},
          title="Entonnoir de recrutement")
    p.add("candidatures-mois-canal", "columnChart", (424, 214, 840, 248),
          {"Category": [col("Calendrier", "AnneeMois")], "Series": [col("Candidatures", "Canal")],
           "Y": [mea("Candidatures reçues")]},
          title="Candidatures reçues par mois et par canal",
          sort=[(col("Calendrier", "AnneeMois"), "Ascending")])
    p.add("motifs", "clusteredBarChart", (16, 470, 400, 240),
          {"Category": [col("Candidatures", "MotifCode")], "Y": [mea("Candidatures reçues")]},
          title="Motifs de clôture (agrégés)", filters=[f_not_blank("Candidatures", "MotifCode", hexid("f", "motif"))])
    p.add("entretiens-a-venir", "tableEx", (424, 470, 840, 240),
          {"Values": [col("Entretiens", "IdHNCS"), col("Entretiens", "DateHeure"), col("Entretiens", "TypeEntretien"),
                      col("Entretiens", "Modalite"), mea("Entretiens à venir")]},
          title="Entretiens à venir", sort=[(col("Entretiens", "DateHeure"), "Ascending")])
    pages.append(p)

    # 3. Effectifs et encadrement -------------------------------------
    p = Page(3, "Effectifs et encadrement")
    p.header([("Poles", "Title", "Pôle", dd), ("Etablissements", "Title", "Établissement", dd),
              ("Referents", "Title", "Référent", dd), ("Calendrier", "Date", "Période", between)])
    p.cards(["Alternants actifs", "Alternants présents sur la période", "Affectations actives",
             "Affectations sans référent", "Affectations incomplètes", "Alternants sans affectation active"])
    p.add("alternants-pole", "clusteredBarChart", (16, 214, 404, 238),
          {"Category": [proj(col("Poles", "Title"), "Pôle")], "Y": [mea("Alternants actifs")]},
          title="Alternants actifs par pôle")
    p.add("charge-referents", "clusteredBarChart", (428, 214, 404, 238),
          {"Category": [proj(col("Referents", "Title"), "Référent")], "Y": [mea("Taux de charge référent")]},
          title="Taux de charge des référents")
    p.add("matrice-etab-pole", "pivotTable", (840, 214, 424, 238),
          {"Rows": [proj(col("Etablissements", "Title"), "Établissement")],
           "Columns": [proj(col("Poles", "Title"), "Pôle")], "Values": [mea("Alternants actifs")]},
          title="Alternants actifs : établissement × pôle")
    p.add("affectations", "tableEx", (16, 460, 1248, 250),
          {"Values": [proj(col("Affectations", "IdHNCS"), "Affectation"), alternant,
                      proj(col("SujetsRD", "Title"), "Sujet"), proj(col("Referents", "Title"), "Référent"),
                      col("Affectations", "DateDebut"), col("Affectations", "DateFin"), col("Affectations", "Statut")]},
          title="Affectations")
    pages.append(p)

    # 4. Projets et livrables -----------------------------------------
    p = Page(4, "Projets et livrables")
    p.header([("SujetsRD", "PoleNom", "Pôle", dd), ("SujetsRD", "Title", "Sujet", dd),
              ("Livrables", "TypeLivrable", "Type de livrable", dd), ("Calendrier", "Date", "Période (échéance)", between)])
    p.cards(["Livrables validés", "Taux de validation", "Livrables en retard", "Taux de remise à l'heure",
             "Taux de validation au premier passage", "Taux de capitalisation", "Corrections en cours",
             "Comptes rendus manquants", "Écarts d'échéance GitLab"])
    p.add("livrables-type-statut", "barChart", (16, 214, 616, 238),
          {"Category": [col("Livrables", "TypeLivrable")], "Series": [col("Livrables", "Statut")],
           "Y": [mea("Livrables")]}, title="Livrables par type et statut")
    p.add("echeances-semaine", "lineChart", (640, 214, 624, 238),
          {"Category": [col("Calendrier", "Semaine")], "Y": [mea("Livrables")]},
          title="Échéances des livrables par semaine", sort=[(col("Calendrier", "Semaine"), "Ascending")])
    p.add("sujets", "tableEx", (16, 460, 410, 250),
          {"Values": [col("SujetsRD", "IdHNCS"), proj(col("SujetsRD", "Title"), "Sujet"), col("SujetsRD", "Statut"),
                      mea("Livrables"), mea("Livrables validés"), mea("Avancement moyen (dernier CR)")]},
          title="Avancement par sujet")
    p.add("livrables-documents", "tableEx", (434, 460, 410, 250),
          {"Values": [col("Livrables", "IdHNCS"), proj(col("Livrables", "Title"), "Livrable"),
                      col("Livrables", "Echeance"), col("Livrables", "Statut"),
                      proj(col("Livrables", "LienDocument"), "Document")]},
          title="Livrables et documents", sort=[(col("Livrables", "Echeance"), "Ascending")])
    p.add("gitlab", "tableEx", (852, 460, 412, 250),
          {"Values": [col("SujetsRD", "IdHNCS"), col("GitlabSync", "Milestone"), col("GitlabSync", "MilestoneEcheance"),
                      col("GitlabSync", "MilestoneEtat"), col("GitlabSync", "IssuesOuvertes"),
                      col("GitlabSync", "MRsOuvertes"), proj(col("GitlabSync", "EcartEcheance"), "Écart d'échéance")]},
          title="Jalons GitLab", sort=[(col("GitlabSync", "MilestoneEcheance"), "Ascending")],
          # RX-07 : les lignes orphelines (jalon supprimé, sujet détaché) sont exclues des indicateurs et du tableau.
          filters=[f_bool("GitlabSync", "Orpheline", False, hexid("f", "gitlab-orpheline"))])
    pages.append(p)

    # 5. Établissements et partenariats -------------------------------
    p = Page(5, "Établissements et partenariats")
    p.header([("Etablissements", "Title", "Établissement", dd),
              ("Conventions", "TypeConvention", "Type de convention", dd)])
    p.cards(["Établissements collaborants", "Partenariats académiques actifs", "Partenariats à évaluer",
             "Conventions à renouveler", "Bilans réalisés"])
    p.add("alternants-ecole", "clusteredBarChart", (16, 214, 616, 238),
          {"Category": [proj(col("Etablissements", "Title"), "Établissement")], "Y": [mea("Alternants accueillis")]},
          title="Alternants accueillis par établissement")
    p.add("recommandations", "donutChart", (640, 214, 624, 238),
          {"Category": [col("BilansAlternance", "RecommandationPartenariat")], "Y": [mea("Bilans réalisés")]},
          title="Recommandations de partenariat (bilans réalisés)")
    p.add("conventions", "tableEx", (16, 460, 616, 250),
          {"Values": [col("Conventions", "IdHNCS"), proj(col("Etablissements", "Title"), "Établissement"),
                      col("Conventions", "TypeConvention"), col("Conventions", "DateFin"), col("Conventions", "Statut")]},
          title="Conventions")
    p.add("prochaines-interactions", "tableEx", (640, 460, 624, 250),
          {"Values": [col("Etablissements", "IdHNCS"), proj(col("Etablissements", "Title"), "Établissement"),
                      proj(col("Etablissements", "DateProchaineAction"), "Prochaine action"),
                      col("Etablissements", "Statut")]},
          title="Prochaines interactions",
          filters=[f_not_blank("Etablissements", "DateProchaineAction", hexid("f", "prochaine-action"))],
          sort=[(col("Etablissements", "DateProchaineAction"), "Ascending")])
    pages.append(p)

    # 6. Communications et valorisation -------------------------------
    p = Page(6, "Communications et valorisation")
    p.header([("CommunicationsRD", "Canal", "Canal", dd), ("Calendrier", "Date", "Période", between)])
    p.cards(["Communications publiées", "Communications en préparation", "Livrables valorisés",
             "Mobilisations commerciales"])
    p.add("publications-mois", "clusteredColumnChart", (16, 214, 616, 238),
          {"Category": [col("Calendrier", "AnneeMois")], "Y": [mea("Communications publiées")]},
          title="Publications externes par mois", sort=[(col("Calendrier", "AnneeMois"), "Ascending")])
    p.add("communications-canal", "clusteredColumnChart", (640, 214, 624, 238),
          {"Category": [col("CommunicationsRD", "Canal")],
           "Y": [mea("Communications publiées"), mea("Communications en préparation")]},
          title="Communications par canal et état")
    p.add("communications-publiees", "tableEx", (16, 460, 1248, 250),
          {"Values": [col("CommunicationsRD", "IdHNCS"), proj(col("CommunicationsRD", "Title"), "Titre"),
                      col("CommunicationsRD", "Canal"), proj(col("CommunicationsRD", "DateEffective"), "Date"),
                      col("CommunicationsRD", "Externe"),
                      proj(col("CommunicationsRD", "UrlPublication"), "Lien public")]},
          title="Communications publiées",
          filters=[f_in("CommunicationsRD", "Statut", ["Publiée"], hexid("f", "publiee"))],
          sort=[(col("CommunicationsRD", "DateEffective"), "Descending")])
    pages.append(p)

    # 7. Comité R&D ----------------------------------------------------
    p = Page(7, "Comité R&D")
    p.header([("SujetsRD", "PoleNom", "Pôle", dd), ("Referents", "Title", "Référent", dd)])
    p.cards(["Échéances à 14 jours", "Livrables en retard", "Blocages signalés", "Sujets bloqués",
             "Comptes rendus manquants", "Actions en retard"])
    p.add("livrables-comite", "tableEx", (16, 214, 616, 238),
          {"Values": [col("Livrables", "IdHNCS"), proj(col("Livrables", "Title"), "Livrable"), alternant,
                      col("Livrables", "Echeance"), col("Livrables", "Statut"),
                      mea("Échéances à 14 jours"), mea("Livrables en retard")]},
          title="Livrables : échéances à 14 jours et retards", sort=[(col("Livrables", "Echeance"), "Ascending")])
    p.add("affectations-risque", "tableEx", (640, 214, 624, 238),
          {"Values": [proj(col("Affectations", "IdHNCS"), "Affectation"), alternant,
                      proj(col("SujetsRD", "Title"), "Sujet"), col("Affectations", "Statut"),
                      mea("Affectations actives")]},
          title="Affectations à risque ou bloquées",
          filters=[f_in("Affectations", "Statut", ["À risque", "Bloquée"], hexid("f", "risque"))])
    p.add("sujets-bloques", "tableEx", (16, 460, 616, 250),
          {"Values": [col("SujetsRD", "IdHNCS"), proj(col("SujetsRD", "Title"), "Sujet"), col("SujetsRD", "PoleNom"),
                      col("SujetsRD", "Statut"), mea("Sujets bloqués")]},
          title="Sujets bloqués ou à arbitrer")
    p.add("cr-manquants", "tableEx", (640, 460, 624, 250),
          {"Values": [col("ComptesRendus", "IdHNCS"), alternant,
                      col("ComptesRendus", "Echeance"), col("ComptesRendus", "Statut"), mea("Comptes rendus manquants")]},
          title="Comptes rendus manquants")
    pages.append(p)

    # 8. Qualité des données ------------------------------------------
    p = Page(8, "Qualité des données")
    p.header([])
    p.cards(["Affectations incomplètes", "Livrables sans modèle", "Doublons signalés", "Transitions refusées"])
    p.add("refus-objet", "clusteredBarChart", (16, 214, 616, 496),
          {"Category": [col("HistoriqueStatuts", "Objet")], "Y": [mea("Transitions refusées")]},
          title="Transitions refusées par objet")
    p.add("refus-detail", "tableEx", (640, 214, 624, 496),
          {"Values": [proj(col("HistoriqueStatuts", "Title"), "IdHNCS"), col("HistoriqueStatuts", "Objet"),
                      proj(col("HistoriqueStatuts", "StatutApres"), "Statut demandé"),
                      col("HistoriqueStatuts", "DateChangement"), mea("Transitions refusées")]},
          title="Transitions refusées", sort=[(col("HistoriqueStatuts", "DateChangement"), "Descending")])
    pages.append(p)
    return pages


BASE_THEME = {
    "name": "CY24SU10",
    "dataColors": ["#118DFF", "#12239E", "#E66C37", "#6B007B", "#E044A7", "#744EC2", "#D9B300", "#D64550"],
    "foreground": "#252423",
    "background": "#FFFFFF",
    "tableAccent": "#118DFF",
}

CUSTOM_THEME = {
    "name": "HNCS-RD",
    "dataColors": ["#2E7D32", "#F57C00", "#C62828", "#757575", "#1565C0", "#6A1B9A", "#00838F", "#AD1457"],
    "good": "#2E7D32",
    "neutral": "#F57C00",
    "bad": "#C62828",
    "foreground": "#252423",
    "background": "#FFFFFF",
    "tableAccent": "#1565C0",
}


def build_report(pages: list[Page]) -> None:
    if RP.exists():
        shutil.rmtree(RP)
    write_json(RP / ".platform", {
        "$schema": S_PLATFORM,
        "metadata": {"type": "Report", "displayName": "HNCS-RD"},
        "config": {"version": "2.0", "logicalId": guid("item", "report")},
    })
    write_json(RP / "definition.pbir", {
        "$schema": S_PBIR,
        "version": "4.0",
        "datasetReference": {"byPath": {"path": "../HNCS-RD.SemanticModel"}},
    })
    write_json(RDEF / "version.json", {"$schema": S_VERSION, "version": "2.0.0"})
    write_json(RDEF / "report.json", {
        "$schema": S_REPORT,
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.59", "type": "SharedResources"},
            "customTheme": {"name": "HNCS-RD.json", "reportVersionAtImport": "5.59", "type": "RegisteredResources"},
        },
        "layoutOptimization": "None",
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "HNCS-RD.json", "path": "HNCS-RD.json", "type": "CustomTheme"}]},
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useDefaultAggregateDisplayName": True,
        },
    })
    write_json(RP / "StaticResources" / "SharedResources" / "BaseThemes" / "CY24SU10.json", BASE_THEME)
    write_json(RP / "StaticResources" / "RegisteredResources" / "HNCS-RD.json", CUSTOM_THEME)
    write_json(RDEF / "pages" / "pages.json", {
        "$schema": S_PAGES,
        "pageOrder": [p.name for p in pages],
        "activePageName": pages[0].name,
    })
    for p in pages:
        base = RDEF / "pages" / p.name
        write_json(base / "page.json", {
            "$schema": S_PAGE,
            "name": p.name,
            "displayName": p.display,
            "displayOption": "FitToPage",
            "height": p.height,
            "width": 1280,
        })
        for v in p.visuals:
            write_json(base / "visuals" / v["name"] / "visual.json", v)


# --------------------------------------------------------------------------- assemblage

def main() -> int:
    model = load_model()
    built = build_model(model)
    roles = build_roles(model)

    if DEF.exists():
        shutil.rmtree(DEF)
    write_json(SM / ".platform", {
        "$schema": S_PLATFORM,
        "metadata": {"type": "SemanticModel", "displayName": "HNCS-RD"},
        "config": {"version": "2.0", "logicalId": guid("item", "semanticModel")},
    })
    write_json(SM / "definition.pbism", {"$schema": S_PBISM, "version": "4.2", "settings": {}})
    write(DEF / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n\n")
    order = [t["table"] for t in model["powerbi"]["tables"]] + [MEASURES_TABLE]
    write(DEF / "model.tmdl", build_model_tmdl(order, list(roles), built["query_order"]))
    write(DEF / "expressions.tmdl", build_expressions(DEFAULT_SITE_URL))
    write(DEF / "relationships.tmdl", build_relationships(model))
    for name, lines in built["tables"].items():
        write(DEF / "tables" / f"{name}.tmdl", "\n".join(lines) + "\n")
    for name, text in roles.items():
        write(DEF / "roles" / f"{name}.tmdl", text + "\n")

    build_report(build_pages())

    write_json(PBI / "HNCS-RD.pbip", {
        "$schema": S_PBIP,
        "version": "1.0",
        "artifacts": [{"report": {"path": "HNCS-RD.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    write(PBI / ".gitignore", "# Caches locaux de Power BI Desktop\n**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    print(f"PBIP généré : {len(built['tables'])} tables, {len(roles)} rôles, "
          f"{len(model['powerbi']['relations'])} relations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
