#!/usr/bin/env python3
"""Contrôle hors ligne du projet PBIP HNCS-RD (modèle TMDL + rapport PBIR) au regard de la spec.

Usage :
    python powerbi/tools/check_pbip.py            # code de sortie 0 si aucune erreur
    python powerbi/tools/check_pbip.py --quiet    # n'affiche que le bilan

Vérifie (indépendamment du générateur) :
  1. tous les fichiers JSON (.json, .pbip, .pbir, .pbism, .platform) sont valides ;
  2. chaque mesure de model.powerbi.measures existe dans le TMDL (même nom) et son DAX est identique
     à la spec (espaces ignorés), hors divergences déclarées ci-dessous ;
  3. chaque table / colonne importée correspond à PBI_TABLES (colonnes, types, clés) ; les colonnes
     calculées sont exactement celles de § 9.4 ; Calendrier et Objectifs sont conformes ;
  4. les requêtes M ne sélectionnent ($select) que les colonnes autorisées et aucune colonne
     perso / confidentiel (exception : Alternants.Title → NomAffichage) ;
  5. chaque relation de PBI_RELATIONS existe avec le bon état actif, et aucune autre ;
  6. les rôles Direction, PilotageRD, Administration, Referent existent avec la RLS et l'OLS de § 9.6 ;
  7. chaque visuel PBIR ne référence que des mesures / colonnes existantes ; NomAffichage n'apparaît
     que sur les pages 3 et 7 ; les 8 pages de § 9.7 existent ;
  8. le script de publication est compatible Windows PowerShell 5.1 (BOM UTF-8, pas de ?? ni ?.),
     et analysable par le parseur PowerShell si powershell.exe est disponible ;
  9. MESURES.md documente chaque mesure.
Bibliothèque standard uniquement.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PBI = ROOT / "powerbi"
SPEC = ROOT / "spec.md"
MODEL_JSON = ROOT / "provisioning" / "model" / "model.generated.json"
SM = PBI / "HNCS-RD.SemanticModel"
DEF = SM / "definition"
RP = PBI / "HNCS-RD.Report"
RDEF = RP / "definition"
DEPLOY = PBI / "deploy" / "Publish-HNCSRDPowerBI.ps1"
SCHEMA_PREFIX = "https://developer.microsoft.com/json-schemas/fabric/"
MEASURES_TABLE = "Mesures"

# Divergences volontaires avec spec.md § 9.5 (documentées dans README.md § Divergences) : aucune en v1.1.0.
ALLOWED_MEASURE_DIVERGENCES: dict[str, str] = {}
# Mesures hors spec autorisées : aucune en v1.1.0.
ALLOWED_EXTRA_MEASURES: set[str] = set()
FOLDERS = {"Recrutement", "Effectifs", "Livrables", "Comptes rendus", "Écoles", "Communications", "Qualité",
           "Objectifs", "Technique"}
EXPECTED_ROLES = ["Direction", "PilotageRD", "Administration", "RelationEcoles", "Referent"]
NOMAFFICHAGE_PAGES: set[int] = set()  # § 9.2 v1.1.0 : NomAffichage absent de tous les visuels
OPTIONAL_LISTS = {"GitlabSync"}  # § 9.1 : lecture facultative (404 → table vide)
# Références exigées par specs/powerbi-rapport.md sans notation Table[Colonne] explicite.
EXTRA_PAGE_REFS = {
    4: [("Column", "Livrables", "LienDocument"), ("Column", "GitlabSync", "EcartEcheance")],
    6: [("Column", "CommunicationsRD", "Title"), ("Column", "CommunicationsRD", "UrlPublication")],
}
REPORT_SUBSPEC = ROOT / "specs" / "powerbi-rapport.md"
# Rôle Power BI → groupes SharePoint de son public (§ 7.1, § 9.6) ; sert à la règle OLS RX-03.
ROLE_GROUPS = {
    "Direction": ["G_DIR"],
    "PilotageRD": ["G_DRD", "G_RD"],
    "Administration": ["G_ADM"],
    "RelationEcoles": ["G_ECO"],
    "Referent": ["G_REF"],
}
# Filtres de visuel exigés : (page, table, colonne, valeur littérale) : RX-07 : jalons orphelins exclus.
REQUIRED_VISUAL_FILTERS = [(4, "GitlabSync", "Orpheline", "false")]

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def norm(dax: str) -> str:
    return re.sub(r"\s+", "", dax)


# --------------------------------------------------------------------------- TMDL

def parse_name(s: str) -> tuple[str, str]:
    """Lit un nom TMDL (éventuellement entre apostrophes) en tête de s ; renvoie (nom, reste)."""
    s = s.lstrip()
    if s.startswith("'"):
        i, out = 1, []
        while i < len(s):
            if s[i] == "'":
                if i + 1 < len(s) and s[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                return "".join(out), s[i + 1:]
            out.append(s[i])
            i += 1
        raise ValueError(f"Nom non terminé : {s}")
    m = re.match(r"^([^\s=.]+)(.*)$", s)
    return m.group(1), m.group(2)


def level(line: str) -> int:
    return len(line) - len(line.lstrip("\t"))


def read_tmdl(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("\ufeff"):
        err(f"{rel(path)} : BOM inattendu")
    lines = text.splitlines()
    for i, l in enumerate(lines, 1):
        if l.startswith(" "):
            err(f"{rel(path)}:{i} : indentation par espaces (tabulations attendues)")
    return lines


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def collect_expr(lines: list[str], i: int, min_level: int) -> tuple[str, int]:
    """Lignes d'expression multiligne (niveau >= min_level) à partir de lines[i]."""
    out = []
    while i < len(lines) and (not lines[i].strip() or level(lines[i]) >= min_level):
        if lines[i].strip():
            out.append(lines[i][min_level:])
        i += 1
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out), i


def parse_table(path: Path) -> dict:
    lines = read_tmdl(path)
    t = {"name": None, "props": {}, "columns": {}, "measures": {}, "partitions": {}, "order": []}
    i = 0
    cur = None
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        lv = level(line)
        body = line.strip()
        if lv == 0 and body.startswith("table "):
            t["name"], _ = parse_name(body[6:])
            cur = t
            i += 1
            continue
        if lv == 1:
            m = re.match(r"^(column|measure|partition|annotation|hierarchy)\s+(.*)$", body)
            if not m:
                key, _, val = body.partition(":")
                t["props"][key.strip()] = val.strip()
                i += 1
                continue
            kind, rest = m.groups()
            if kind == "annotation":
                i += 1
                cur = None
                continue
            name, rest = parse_name(rest)
            rest = rest.strip()
            obj = {"name": name, "props": {}, "expr": None, "kind": kind}
            if rest.startswith("="):
                e = rest[1:].strip()
                if kind == "partition":
                    obj["ptype"] = e
                elif e:
                    obj["expr"] = e
                else:
                    obj["expr"], i = collect_expr(lines, i + 1, 3)
                    i -= 1
            {"column": t["columns"], "measure": t["measures"], "partition": t["partitions"]}[kind][name] = obj
            if kind == "column":
                t["order"].append(name)
            cur = obj
            i += 1
            continue
        if lv == 2 and cur is not None and cur is not t:
            if body.startswith("annotation "):
                i += 1
                continue
            key, sep, val = body.partition(":")
            key = key.strip()
            if cur["kind"] == "partition" and body.startswith("source"):
                v = body.split("=", 1)[1].strip()
                if v:
                    cur["source"] = v
                    i += 1
                else:
                    cur["source"], i = collect_expr(lines, i + 1, 4)
                continue
            cur["props"][key] = val.strip() if sep else True
            i += 1
            continue
        i += 1
    return t


def parse_relationships(path: Path) -> list[dict]:
    rels, cur = [], None
    for line in read_tmdl(path):
        if not line.strip():
            continue
        if level(line) == 0 and line.startswith("relationship "):
            cur = {"name": line.split(None, 1)[1].strip(), "isActive": True}
            rels.append(cur)
        elif level(line) == 1 and cur is not None:
            k, _, v = line.strip().partition(":")
            v = v.strip()
            if k == "isActive":
                cur["isActive"] = v.lower() != "false"
            elif k in ("fromColumn", "toColumn"):
                tbl, rest = parse_name(v)
                col, _ = parse_name(rest[1:])
                cur[k] = f"{tbl}[{col}]"
            else:
                cur[k] = v
    return rels


def parse_role(path: Path) -> dict:
    lines = read_tmdl(path)
    role = {"name": None, "props": {}, "tables": {}}
    i, curt = 0, None
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        lv, body = level(line), line.strip()
        if lv == 0 and body.startswith("role "):
            role["name"], _ = parse_name(body[5:])
        elif lv == 1 and body.startswith("tablePermission "):
            name, rest = parse_name(body[len("tablePermission "):])
            rest = rest.strip()
            tp = {"filter": None, "columns": {}}
            if rest.startswith("="):
                e = rest[1:].strip()
                if e:
                    tp["filter"] = e
                else:
                    tp["filter"], i = collect_expr(lines, i + 1, 3)
                    role["tables"][name] = tp
                    curt = tp
                    continue
            role["tables"][name] = tp
            curt = tp
        elif lv == 1 and not body.startswith("annotation "):
            k, _, v = body.partition(":")
            role["props"][k.strip()] = v.strip()
            curt = None
        elif lv == 2 and curt is not None and body.startswith("columnPermission "):
            cname, rest = parse_name(body[len("columnPermission "):])
            perm = None
            rest = rest.strip()
            if rest.startswith("="):
                perm = rest[1:].strip()
            j = i + 1
            while j < len(lines) and lines[j].strip() and level(lines[j]) >= 3:
                k, _, v = lines[j].strip().partition(":")
                if k.strip() == "metadataPermission":
                    perm = v.strip()
                j += 1
            curt["columns"][cname] = perm
            i = j
            continue
        i += 1
    return role


# --------------------------------------------------------------------------- spec

def spec_lines() -> list[str]:
    return SPEC.read_text(encoding="utf-8").splitlines()


def spec_measures(dax: str) -> dict[str, str]:
    res, cur = {}, None
    for line in dax.splitlines():
        if not line.strip() or line.startswith("//"):
            cur = None
            continue
        if not line[0].isspace():
            m = re.match(r"^(.+?) =(.*)$", line)
            cur = m.group(1).strip()
            res[cur] = m.group(2)
        elif cur:
            res[cur] += "\n" + line
    return res


def spec_calc_columns() -> dict[tuple[str, str], str]:
    lines = spec_lines()
    s = next(i for i, l in enumerate(lines) if l.startswith("### 9.4"))
    s = next(i for i in range(s, len(lines)) if lines[i].startswith("```dax"))
    res, table, cur = {}, None, None
    for l in lines[s + 1:]:
        if l.startswith("```"):
            break
        m = re.match(r"^// (.+?) : PoleNom = LOOKUPVALUE \( Poles\[Title\], Poles\[Id\], <table>\[PoleId ou PolePressentiId\] \)", l)
        if m:
            for t in [x.strip() for x in m.group(1).split(",")]:
                k = "PolePressentiId" if t == "Candidatures" else "PoleId"
                res[(t, "PoleNom")] = f"LOOKUPVALUE ( Poles[Title], Poles[Id], {t}[{k}] )"
            continue
        m = re.match(r"^// (\w+)\s*$", l)
        if m:
            table = m.group(1)
            continue
        if l.startswith("//"):
            cur = None
            continue
        if not l.strip():
            continue
        if not l[0].isspace():
            m = re.match(r"^(\w+) =(.*)$", l)
            cur = (table, m.group(1))
            res[cur] = m.group(2)
        else:
            res[cur] += "\n" + l
    return res


def spec_pages() -> list[str]:
    lines = spec_lines()
    s = next(i for i, l in enumerate(lines) if l.startswith("### 9.7"))
    pages = []
    for l in lines[s + 1:]:
        if l.startswith("## ") or l.startswith("### ") and pages:
            break
        m = re.match(r"^\| (\d+) \| ([^|]+?) \|", l)
        if m:
            pages.append((int(m.group(1)), m.group(2).strip()))
    return [p for _, p in sorted(pages)]


def spec_objectifs() -> dict[str, float]:
    text = SPEC.read_text(encoding="utf-8")
    m = re.search(r"La table `Objectifs` contient : (.+?) \(valeurs indicatives", text)
    res = {}
    for part in m.group(1).split(" ; "):
        k, v = part.rsplit(" = ", 1)
        res[k.strip()] = float(v)
    return res


# --------------------------------------------------------------------------- contrôles

def check_json() -> dict[Path, object]:
    docs = {}
    for p in PBI.rglob("*"):
        if p.is_file() and (p.suffix in (".json", ".pbip", ".pbir", ".pbism") or p.name == ".platform"):
            try:
                docs[p] = json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                err(f"{rel(p)} : JSON invalide ({e})")
    return docs


def expected_source(obj: dict, col: dict) -> tuple[str, dict | None, str]:
    """(champ $select attendu, colonne SharePoint, genre attendu) pour une colonne PBI_TABLES."""
    cols = {c["name"]: c for c in obj["columns"]}
    cols["Title"] = obj["titleColumn"]
    src = col["source"]
    if src == "Id":
        return "Id", None, "int64"
    if src in cols:
        c = cols[src]
        t = c["type"]
        if col["transform"] == "bool":
            return src, c, "boolean"
        typ = {"Text": "string", "Choice": "string", "Note": "string", "Number": "int64" if str(c.get("decimals")) == "0"
               else "double", "Boolean": "boolean", "Date": "dateTime", "DateTime": "dateTime", "URL": "string"}.get(t)
        return src, c, typ
    if src.endswith("Id") and cols.get(src[:-2], {}).get("type") in ("Lookup", "LookupMulti"):
        return src, cols[src[:-2]], "int64"
    if src.endswith("Email") and cols.get(src[:-5], {}).get("type") == "User":
        return f"{src[:-5]}/EMail", cols[src[:-5]], "string"
    return src, None, None


def m_strings(s: str) -> list[str]:
    return [x.replace('""', '"') for x in re.findall(r'"((?:[^"]|"")*)"', s)]


def check_model(model: dict) -> dict[str, dict]:
    pbi = model["powerbi"]
    objs = {o["name"]: o for o in model["objects"]}
    tables: dict[str, dict] = {}
    for p in sorted((DEF / "tables").glob("*.tmdl")):
        t = parse_table(p)
        if t["name"] != p.stem:
            err(f"{rel(p)} : nom de table {t['name']} différent du fichier")
        tables[t["name"]] = t

    # model.tmdl / database.tmdl / expressions.tmdl
    mt = (DEF / "model.tmdl").read_text(encoding="utf-8")
    read_tmdl(DEF / "model.tmdl")
    refs = [parse_name(l[len("ref table "):])[0] for l in mt.splitlines() if l.startswith("ref table ")]
    if set(refs) != set(tables):
        err(f"model.tmdl : ref table {sorted(set(refs) ^ set(tables))} incohérentes avec tables/")
    if "\tculture: fr-FR" not in mt.splitlines():
        err("model.tmdl : culture fr-FR attendue")
    db = (DEF / "database.tmdl").read_text(encoding="utf-8")
    m = re.search(r"compatibilityLevel: (\d+)", db)
    if not m or int(m.group(1)) < 1400:
        err("database.tmdl : compatibilityLevel >= 1400 requis (OLS)")
    ex = (DEF / "expressions.tmdl").read_text(encoding="utf-8")
    read_tmdl(DEF / "expressions.tmdl")
    if not re.search(r'^expression SiteUrl = ".+" meta \[IsParameterQuery = true', ex, re.M):
        err("expressions.tmdl : paramètre M SiteUrl absent")
    for token in ("Web.Contents(", "SiteUrl,", "RelativePath = chemin", "Query = requete", '#"$select"', '#"$top" = "5000"',
                  '#"$expand"', "odata.nextLink", "$skiptoken", 'Accept = "application/json;odata=nometadata"',
                  "_api/web/GetList('", '"/Lists/"', "Uri.Parts(SiteUrl)[Path]", "ManualStatusHandling",
                  "expression fnHeureParis", "fnHeureParis(v)"):
        if token not in ex:
            err(f"expressions.tmdl : élément attendu absent de la lecture SharePoint : {token}")
    if "getbytitle" in ex.lower():
        err("expressions.tmdl : getbytitle interdit (§ 9.1 : listes désignées par leur nom interne via GetList)")
    if len(re.findall(r"Web\.Contents\(", ex)) != 1:
        err("expressions.tmdl : un seul appel Web.Contents attendu (source unique, actualisable dans le service)")

    # tables importées
    calc_spec = spec_calc_columns()
    for t in pbi["tables"]:
        name = t["table"]
        tt = tables.get(name)
        if tt is None:
            err(f"Table {name} (PBI_TABLES) absente du TMDL")
            continue
        if name in ("Calendrier", "Objectifs"):
            continue
        expected_cols = [c["name"] for c in t["columns"]]
        data_cols = [c for c in tt["order"] if tt["columns"][c]["expr"] is None]
        calc_cols = [c for c in tt["order"] if tt["columns"][c]["expr"] is not None]
        if set(data_cols) != set(expected_cols):
            err(f"{name} : colonnes importées {sorted(set(data_cols) ^ set(expected_cols))} hors PBI_TABLES")
        exp_calc = {c for (tb, c) in calc_spec if tb == name}
        if set(calc_cols) != exp_calc:
            err(f"{name} : colonnes calculées {sorted(set(calc_cols) ^ exp_calc)} différentes de § 9.4")
        for c in calc_cols:
            if (name, c) in calc_spec and norm(tt["columns"][c]["expr"]) != norm(calc_spec[(name, c)]):
                err(f"{name}[{c}] : DAX différent de § 9.4")
        for c in data_cols:
            if tt["columns"][c]["props"].get("sourceColumn") != c:
                err(f"{name}[{c}] : sourceColumn attendu = {c}")
        parts = list(tt["partitions"].values())
        if len(parts) != 1 or parts[0].get("ptype") != "m" or parts[0]["props"].get("mode") != "import":
            err(f"{name} : une partition M en mode import attendue")
            continue
        src = parts[0].get("source", "")
        if "Web.Contents" in src or "SharePoint." in src or "OData." in src:
            err(f"{name} : la partition doit passer par fnLireListeSharePoint (aucune autre source)")
        m = re.search(r'fnLireListeSharePoint\(\s*"((?:[^"]|"")*)"\s*,\s*(\{[^}]*\})\s*,\s*(\{[^}]*\})\s*,\s*(true|false)\s*(?:,\s*(true|false)\s*)?\)', src)
        if not m:
            err(f"{name} : appel fnLireListeSharePoint(nomInterne, {{champs}}, {{expansions}}, facultative) introuvable")
            continue
        list_name, selects, expands, optional = m.group(1).replace('""', '"'), m_strings(m.group(2)), m_strings(m.group(3)), m.group(4)
        library = m.group(5) == "true"
        source_list = "SujetsRD" if name == "SujetDomaine" else t["source"]
        obj = objs[source_list]
        if list_name != obj["name"]:
            err(f"{name} : la liste doit être désignée par son nom interne « {obj['name']} » (obtenu « {list_name} »)")
        if library != (obj.get("kind") == "library"):
            err(f"{name} : drapeau bibliothèque incohérent avec le type de {obj['name']} ({obj.get('kind')})")
        # Conversion en heure de Paris : chaque colonne Date / DateTime est typée « date » / « datetime » par fnTyperColonnes.
        schema = dict(re.findall(r'\{"(\w+)", "(\w+)"\}', src.split("fnTyperColonnes(", 1)[1])) if "fnTyperColonnes(" in src else {}
        if (optional == "true") != (source_list in OPTIONAL_LISTS):
            err(f"{name} : caractère facultatif de la liste incohérent")
        if name == "SujetDomaine":
            if selects != ["Id", "DomainesId"]:
                err(f"SujetDomaine : $select attendu Id, DomainesId (obtenu {selects})")
            if obj and next((c for c in obj["columns"] if c["name"] == "Domaines"), {}).get("type") != "LookupMulti":
                err("SujetDomaine : SujetsRD.Domaines doit être une recherche multiple")
            continue
        expected_selects = []
        for c in t["columns"]:
            sel, spcol, typ = expected_source(obj, c)
            if sel not in expected_selects:
                expected_selects.append(sel)
            if spcol and spcol.get("type") in ("Date", "DateTime") and c["transform"] is None:
                want_kind = "date" if spcol["type"] == "Date" else "datetime"
                if schema.get(c["source"]) != want_kind:
                    err(f"{name}[{c['name']}] : conversion en heure de Paris attendue (genre « {want_kind} » dans fnTyperColonnes)")
            if spcol is None and sel != "Id":
                err(f"{name}[{c['name']}] : colonne source {c['source']} inconnue dans {source_list}")
                continue
            if spcol and (spcol.get("perso") or spcol.get("confidentiel")):
                if not (name == "Alternants" and c["source"] == "Title" and c["name"] == "NomAffichage"):
                    err(f"{name}[{c['name']}] : colonne perso/confidentiel {source_list}.{c['source']} importée")
            col = tt["columns"].get(c["name"])
            if col and typ and col["props"].get("dataType") != typ:
                err(f"{name}[{c['name']}] : dataType {col['props'].get('dataType')} ≠ {typ} attendu")
            if c["name"] == "Id" and col and "isKey" not in col["props"]:
                err(f"{name}[Id] : isKey attendu")
        if selects != expected_selects:
            err(f"{name} : $select {selects} ≠ attendu {expected_selects}")
        for s in selects:
            base = s.split("/")[0]
            if "/" in s and base not in expands:
                err(f"{name} : $expand={base} requis pour {s}")
        spcols = {c["name"]: c for c in obj["columns"]}
        spcols["Title"] = obj["titleColumn"]
        for c in selects:
            if c not in expected_selects:
                err(f"{name} : champ {c} sélectionné hors PBI_TABLES")
                base = c.split("/")[0]
                base = base[:-2] if base.endswith("Id") and base[:-2] in spcols else base
                sp = spcols.get(base, {})
                if sp.get("perso") or sp.get("confidentiel"):
                    err(f"{name} : champ {c} marqué perso/confidentiel transmis par la requête M (P-04)")

    # Calendrier
    cal = tables.get("Calendrier")
    if cal:
        exp = next(t for t in pbi["tables"] if t["table"] == "Calendrier")
        if cal["order"] != [c["name"] for c in exp["columns"]]:
            err(f"Calendrier : colonnes {cal['order']} ≠ {[c['name'] for c in exp['columns']]}")
        part = next(iter(cal["partitions"].values()), {})
        src = part.get("source", "")
        if part.get("ptype") != "calculated" or "CALENDAR" not in src:
            err("Calendrier : table calculée DAX (CALENDAR) attendue")
        if "2025" not in src or "2028" not in src:
            err("Calendrier : bornes minimales 2025-01-01 → 2028-12-31 attendues")
        if cal["props"].get("dataCategory") != "Time" or "isKey" not in cal["columns"].get("Date", {}).get("props", {}):
            err("Calendrier : dataCategory Time et Date en clé attendus (table de dates)")
    obj_t = tables.get("Objectifs")
    if obj_t:
        part = next(iter(obj_t["partitions"].values()), {})
        src = part.get("source", "")
        if part.get("ptype") != "calculated" or "DATATABLE" not in src:
            err("Objectifs : table DATATABLE attendue")
        if obj_t["order"] != ["Indicateur", "Cible"]:
            err("Objectifs : colonnes Indicateur ; Cible attendues")
        found = {k: float(v) for k, v in re.findall(r'\{\s*"([^"]+)",\s*([0-9.]+)\s*\}', src)}
        if found != spec_objectifs():
            err(f"Objectifs : cibles {found} ≠ spec {spec_objectifs()}")

    # mesures
    mt = tables.get(MEASURES_TABLE)
    if not mt:
        err("Table de mesures « Mesures » absente")
        return tables
    all_measures = {n: (tn, m) for tn, t in tables.items() for n, m in t["measures"].items()}
    spec_dax = spec_measures(pbi["measuresDax"])
    if list(spec_dax) != pbi["measures"]:
        err("model.generated.json : measuresDax et measures incohérents")
    for name in pbi["measures"]:
        if name not in mt["measures"]:
            err(f"Mesure absente du TMDL : [{name}]")
            continue
        got = mt["measures"][name]["expr"] or ""
        want = ALLOWED_MEASURE_DIVERGENCES.get(name, spec_dax.get(name, ""))
        if norm(got) != norm(want):
            err(f"Mesure [{name}] : DAX différent de la spec (§ 9.5)")
    for name, (tn, ms) in all_measures.items():
        if tn != MEASURES_TABLE:
            err(f"Mesure [{name}] hors de la table Mesures ({tn})")
        if name not in pbi["measures"] and name not in ALLOWED_EXTRA_MEASURES:
            err(f"Mesure [{name}] non prévue par la spec ni déclarée")
        folder = ms["props"].get("displayFolder")
        if folder not in FOLDERS:
            err(f"Mesure [{name}] : dossier d'affichage « {folder} » inattendu")
        if not ms["props"].get("formatString"):
            err(f"Mesure [{name}] : formatString manquant")
    for c in mt["columns"].values():
        if "isHidden" not in c["props"]:
            err(f"Mesures[{c['name']}] : colonne technique non masquée")
    if "DerniereActualisation" not in mt["columns"]:
        err("Mesures[DerniereActualisation] : colonne masquée attendue (§ 9.4)")
    msrc = next(iter(mt["partitions"].values()), {}).get("source", "")
    if "DateTimeZone.FixedUtcNow()" not in msrc or "fnHeureParis(" not in msrc:
        err("Mesures : DerniereActualisation doit être DateTimeZone.FixedUtcNow converti en heure de Paris (§ 9.4)")
    return tables


def balanced(text: str, lang: str) -> str | None:
    """Contrôle d'équilibre ( ) { } [ ] hors chaînes et commentaires ; renvoie un message ou None."""
    pairs = {")": "(", "}": "{", "]": "["}
    stack: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            i += 1
            while i < n:
                if text[i] == '"':
                    if i + 1 < n and text[i + 1] == '"':
                        i += 2
                        continue
                    break
                i += 1
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif lang == "dax" and ch == "[":
            j = text.find("]", i)
            if j < 0:
                return "crochet non fermé"
            i = j
        elif lang == "dax" and ch == "'":
            j = text.find("'", i + 1)
            if j < 0:
                return "apostrophe non fermée"
            i = j
        elif ch in "({[":
            stack.append(ch)
        elif ch in ")}]":
            if not stack or stack[-1] != pairs[ch]:
                return f"« {ch} » inattendu"
            stack.pop()
        i += 1
    return f"« {stack[-1]} » non fermé" if stack else None


def check_syntax(tables: dict) -> None:
    for tn, t in tables.items():
        for kind in ("measures", "columns"):
            for name, o in t[kind].items():
                if o.get("expr"):
                    msg = balanced(o["expr"], "dax")
                    if msg:
                        err(f"{tn}[{name}] : DAX mal formé ({msg})")
        for name, part in t["partitions"].items():
            lang = "m" if part.get("ptype") == "m" else "dax"
            msg = balanced(part.get("source", ""), lang)
            if msg:
                err(f"{tn} partition {name} : {lang.upper()} mal formé ({msg})")
    ex = (DEF / "expressions.tmdl").read_text(encoding="utf-8")
    for blockm in re.split(r"^expression ", ex, flags=re.M)[1:]:
        body = "\n".join(l for l in blockm.splitlines()[1:] if l.startswith("\t\t"))
        msg = balanced(body, "m")
        if msg:
            err(f"expressions.tmdl : M mal formé dans {blockm.split()[0]} ({msg})")
    for p in sorted((DEF / "roles").glob("*.tmdl")):
        for tname, tp in parse_role(p)["tables"].items():
            if tp["filter"]:
                msg = balanced(tp["filter"], "dax")
                if msg:
                    err(f"{rel(p)} : filtre {tname} mal formé ({msg})")


def check_relationships(model: dict, tables: dict) -> None:
    rels = parse_relationships(DEF / "relationships.tmdl")
    got = {(r.get("fromColumn"), r.get("toColumn")): r["isActive"] for r in rels}
    want = {(r["from"], r["to"]): r["active"] for r in model["powerbi"]["relations"]}
    for k, active in want.items():
        if k not in got:
            err(f"Relation absente : {k[0]} → {k[1]}")
        elif got[k] != active:
            err(f"Relation {k[0]} → {k[1]} : active={got[k]} ≠ {active} attendu")
    for k in got:
        if k not in want:
            err(f"Relation hors spec : {k[0]} → {k[1]}")
    for r in rels:
        if r.get("crossFilteringBehavior", "oneDirection") != "oneDirection":
            err(f"Relation {r.get('fromColumn')} : filtrage simple attendu")
        for side in ("fromColumn", "toColumn"):
            m = re.match(r"^(\w+)\[(\w+)\]$", r.get(side, ""))
            if not m or m.group(2) not in tables.get(m.group(1), {}).get("columns", {}):
                err(f"Relation : colonne inexistante {r.get(side)}")
    if len(rels) != len(got):
        err("relationships.tmdl : relations en double")


def check_roles(model: dict, tables: dict) -> None:
    roles = {}
    for p in sorted((DEF / "roles").glob("*.tmdl")):
        r = parse_role(p)
        roles[r["name"]] = r
    mt = (DEF / "model.tmdl").read_text(encoding="utf-8")
    for name in EXPECTED_ROLES:
        if name not in roles:
            err(f"Rôle {name} absent")
        elif f"ref role {name}" not in mt:
            err(f"model.tmdl : ref role {name} manquant")
    for spec_role in model["powerbi"]["roles"]:
        name = spec_role["role"]
        r = roles.get(name)
        if not r:
            continue
        if r["props"].get("modelPermission") != "read":
            err(f"Rôle {name} : modelPermission: read attendu")
        want_f = dict(re.findall(r"`(\w+)` : `([^`]+)`", spec_role["filters"]))
        got_f = {t: tp["filter"] for t, tp in r["tables"].items() if tp["filter"]}
        if set(want_f) != set(got_f):
            err(f"Rôle {name} : tables filtrées {sorted(got_f)} ≠ {sorted(want_f)}")
        for t, f in want_f.items():
            if t in got_f and norm(got_f[t]) != norm(f):
                err(f"Rôle {name} : filtre RLS sur {t} différent de § 9.6")
        want_ols = set(re.findall(r"`(\w+)\[(\w+)\]` : aucun accès", spec_role["ols"]))
        got_ols = {(t, c) for t, tp in r["tables"].items() for c, perm in tp["columns"].items() if perm == "none"}
        if want_ols != got_ols:
            err(f"Rôle {name} : OLS {sorted(got_ols)} ≠ {sorted(want_ols)} attendu")
        for t, tp in r["tables"].items():
            if t not in tables:
                err(f"Rôle {name} : table inconnue {t}")
            for c in tp["columns"]:
                if c not in tables.get(t, {}).get("columns", {}):
                    err(f"Rôle {name} : colonne inconnue {t}[{c}]")
    if set(roles) - set(EXPECTED_ROLES):
        err(f"Rôles hors spec : {sorted(set(roles) - set(EXPECTED_ROLES))}")
    # RX-03 : NomAffichage masqué (OLS) pour tout rôle dont un groupe SharePoint n'a aucun accès à Alternants (§ 7.3).
    matrix = model["matrix"].get("Alternants", {})
    for name, groups in ROLE_GROUPS.items():
        r = roles.get(name)
        if not r:
            continue
        no_access = any(matrix.get(g, "-") in ("-", "", None) for g in groups)
        masked = r["tables"].get("Alternants", {}).get("columns", {}).get("NomAffichage") == "none"
        if no_access and not masked:
            err(f"Rôle {name} : groupe sans accès SharePoint à Alternants ({', '.join(groups)}) → "
                "columnPermission NomAffichage metadataPermission: none requis (P-04, RX-03)")
    for name in ("Direction", "RelationEcoles"):
        d = roles.get(name)
        if d and d["tables"].get("Alternants", {}).get("columns", {}).get("NomAffichage") != "none":
            err(f"Rôle {name} : columnPermission NomAffichage metadataPermission: none requis (P-04)")


def iter_refs(node, aliases=None):
    """Références (genre, table, colonne/mesure) d'un document PBIR."""
    aliases = dict(aliases or {})
    if isinstance(node, dict):
        if "From" in node and isinstance(node["From"], list):
            for f in node["From"]:
                if isinstance(f, dict) and "Name" in f and "Entity" in f:
                    aliases[f["Name"]] = f["Entity"]
        for kind in ("Column", "Measure"):
            v = node.get(kind)
            if isinstance(v, dict) and "Property" in v:
                sr = v.get("Expression", {}).get("SourceRef", {})
                ent = sr.get("Entity") or aliases.get(sr.get("Source"))
                yield kind, ent, v["Property"]
        for v in node.values():
            yield from iter_refs(v, aliases)
    elif isinstance(node, list):
        for v in node:
            yield from iter_refs(v, aliases)


def check_report(docs: dict, tables: dict) -> None:
    pbip = docs.get(PBI / "HNCS-RD.pbip")
    if not pbip:
        err("HNCS-RD.pbip absent")
    else:
        for a in pbip.get("artifacts", []):
            p = a.get("report", {}).get("path")
            if not p or not (PBI / p).is_dir():
                err(f"HNCS-RD.pbip : artefact introuvable {p}")
    pbir = docs.get(RP / "definition.pbir")
    if not pbir:
        err("definition.pbir absent")
    else:
        path = pbir.get("datasetReference", {}).get("byPath", {}).get("path")
        if not path or (RP / path).resolve() != SM.resolve():
            err(f"definition.pbir : byPath doit référencer ../HNCS-RD.SemanticModel (obtenu {path})")
        if float(pbir.get("version", "0")) < 4.0:
            err("definition.pbir : version >= 4.0 requise pour le format PBIR")
    if not docs.get(SM / "definition.pbism"):
        err("definition.pbism absent")
    for p, d in docs.items():
        if RDEF in p.parents or p.suffix in (".pbir", ".pbism", ".pbip"):
            sch = d.get("$schema", "") if isinstance(d, dict) else ""
            if not sch.startswith(SCHEMA_PREFIX):
                err(f"{rel(p)} : $schema officiel attendu")
    rep = docs.get(RDEF / "report.json")
    if rep:
        for pkg in rep.get("resourcePackages", []):
            for it in pkg.get("items", []):
                f = RP / "StaticResources" / pkg["name"] / it["path"]
                if not f.is_file():
                    err(f"report.json : ressource introuvable {rel(f)}")
    if not docs.get(RDEF / "version.json"):
        err("definition/version.json absent")

    pages_meta = docs.get(RDEF / "pages" / "pages.json")
    folders = sorted(p.name for p in (RDEF / "pages").iterdir() if p.is_dir()) if (RDEF / "pages").is_dir() else []
    if not pages_meta:
        err("pages/pages.json absent")
        return
    order = pages_meta.get("pageOrder", [])
    if sorted(order) != folders:
        err("pages.json : pageOrder ≠ dossiers de pages")
    expected = spec_pages()
    required = subspec_requirements()
    if sorted(required) != list(range(1, len(expected) + 1)):
        err(f"specs/powerbi-rapport.md : pages {sorted(required)} illisibles ou incomplètes")
    displays = []
    for idx, pid in enumerate(order, 1):
        page_refs = set()
        page = docs.get(RDEF / "pages" / pid / "page.json")
        if not page:
            err(f"Page {pid} : page.json absent")
            continue
        if page.get("name") != pid:
            err(f"Page {pid} : name ≠ dossier")
        displays.append(page.get("displayName"))
        vdir = RDEF / "pages" / pid / "visuals"
        vnames = set()
        for vf in sorted(vdir.glob("*/visual.json")):
            v = docs.get(vf)
            if v is None:
                continue
            if v.get("name") != vf.parent.name:
                err(f"{rel(vf)} : name ≠ dossier")
            if v["name"] in vnames:
                err(f"{rel(vf)} : nom de visuel en double")
            vnames.add(v["name"])
            for fpage, ftable, fcol, fval in REQUIRED_VISUAL_FILTERS:
                if idx != fpage or v.get("visual", {}).get("visualType") != "tableEx":
                    continue
                if not any(e == ftable for _, e, _ in iter_refs(v.get("visual", {}).get("query", {}))):
                    continue
                ok = False
                for f in v.get("filterConfig", {}).get("filters", []):
                    fld = f.get("field", {}).get("Column", {})
                    if fld.get("Property") == fcol and fld.get("Expression", {}).get("SourceRef", {}).get("Entity") == ftable:
                        cond = f.get("filter", {}).get("Where", [{}])[0].get("Condition", {})
                        vals = [x.get("Literal", {}).get("Value")
                                for row in cond.get("In", {}).get("Values", []) for x in row]
                        ok = vals == [fval]
                if not ok:
                    err(f"{rel(vf)} : filtre de visuel {ftable}[{fcol}] = {fval} requis (RX-07)")
            if not v.get("visual", {}).get("visualType"):
                err(f"{rel(vf)} : visualType manquant")
            for kind, ent, prop in iter_refs(v):
                page_refs.add((kind, ent, prop))
                t = tables.get(ent)
                if t is None:
                    err(f"{rel(vf)} : table inconnue {ent}")
                elif kind == "Measure" and prop not in t["measures"]:
                    err(f"{rel(vf)} : mesure inconnue {ent}[{prop}]")
                elif kind == "Column" and prop not in t["columns"]:
                    err(f"{rel(vf)} : colonne inconnue {ent}[{prop}]")
                if ent == "Alternants" and prop == "NomAffichage" and idx not in NOMAFFICHAGE_PAGES:
                    err(f"{rel(vf)} : NomAffichage utilisé dans un visuel (interdit, § 9.2 v1.1.0)")
            for proj in iter_projections(v):
                if proj.get("queryRef") and "field" in proj:
                    f = proj["field"]
                    k = "Column" if "Column" in f else "Measure"
                    ref = f"{f[k]['Expression']['SourceRef'].get('Entity')}.{f[k]['Property']}"
                    if proj["queryRef"] != ref:
                        err(f"{rel(vf)} : queryRef {proj['queryRef']} ≠ {ref}")
        if not vnames:
            err(f"Page {page.get('displayName')} : aucun visuel")
        for ref in required.get(idx, []) + [("Measure", MEASURES_TABLE, "Dernière actualisation")]:
            if ref not in page_refs:
                err(f"Page {idx} ({page.get('displayName')}) : {ref[1]}[{ref[2]}] exigé par specs/powerbi-rapport.md absent")
    if displays != expected:
        err(f"Pages {displays} ≠ § 9.7 {expected}")


def subspec_requirements() -> dict[int, list[tuple[str, str, str]]]:
    """Mesures `[X]` et colonnes `Table[Colonne]` citées par page dans specs/powerbi-rapport.md."""
    req: dict[int, list] = {}
    for line in REPORT_SUBSPEC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (\d+)\. [^|]+\|(.*)\|\s*$", line)
        if not m:
            continue
        n, rest = int(m.group(1)), m.group(2)
        refs = [("Measure", MEASURES_TABLE, x) for x in re.findall(r"`\[([^\]]+)\]`", rest)]
        refs += [("Column", a, b) for a, b in re.findall(r"`(\w+)\[(\w+)\]`", rest)]
        req[n] = refs + EXTRA_PAGE_REFS.get(n, [])
    return req


def iter_projections(v):
    qs = v.get("visual", {}).get("query", {}).get("queryState", {})
    for role in qs.values():
        yield from role.get("projections", [])


def check_deploy() -> None:
    if not DEPLOY.is_file():
        err(f"{rel(DEPLOY)} absent")
        return
    raw = DEPLOY.read_bytes()
    if not raw.startswith(b"\xef\xbb\xbf"):
        err(f"{rel(DEPLOY)} : BOM UTF-8 requis (Windows PowerShell 5.1 lit sinon le fichier en ANSI)")
    text = raw.decode("utf-8-sig")
    code = "\n".join(l.split("#", 1)[0] if not l.lstrip().startswith("#") else "" for l in text.splitlines())
    code = re.sub(r"<#.*?#>", "", code, flags=re.S)
    code = re.sub(r"'[^'\n]*'", "''", code)
    code = re.sub(r'"[^"\n]*"', '""', code)
    for tok, label in ((r"\?\?", "??"), (r"\?\.", "?."), (r"\s\?\s.*\s:\s", "ternaire")):
        if re.search(tok, code):
            err(f"{rel(DEPLOY)} : opérateur {label} incompatible avec Windows PowerShell 5.1")
    for needle in ("api.fabric.microsoft.com", "'semanticModels'", "'reports'", "/workspaces", "updateDefinition", "InlineBase64",
                   "SiteUrl", "refreshes"):
        if needle not in text:
            err(f"{rel(DEPLOY)} : élément attendu absent ({needle})")
    exe = shutil.which("powershell.exe") or shutil.which("powershell")
    if exe:
        ps = ("$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile("
              f"'{DEPLOY}',[ref]$t,[ref]$e);if($e.Count){{$e|%{{$_.Message}};exit 1}}")
        r = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True)
        if r.returncode != 0:
            err(f"{rel(DEPLOY)} : erreurs du parseur Windows PowerShell : {r.stdout.strip()} {r.stderr.strip()}")


def check_docs(model: dict) -> None:
    for f in ("README.md", "MESURES.md"):
        if not (PBI / f).is_file():
            err(f"powerbi/{f} absent")
    md = PBI / "MESURES.md"
    if md.is_file():
        text = md.read_text(encoding="utf-8")
        for name in model["powerbi"]["measures"]:
            if f"[{name}]" not in text:
                err(f"MESURES.md : mesure [{name}] non documentée")
    gi = PBI / ".gitignore"
    if not gi.is_file() or "localSettings.json" not in gi.read_text(encoding="utf-8") \
            or "cache.abf" not in gi.read_text(encoding="utf-8"):
        err("powerbi/.gitignore : .pbi/localSettings.json et .pbi/cache.abf doivent être ignorés")


def main() -> int:
    quiet = "--quiet" in sys.argv
    model = json.loads(MODEL_JSON.read_text(encoding="utf-8"))
    docs = check_json()
    tables = check_model(model)
    check_syntax(tables)
    check_relationships(model, tables)
    check_roles(model, tables)
    check_report(docs, tables)
    check_deploy()
    check_docs(model)
    if errors and not quiet:
        for e in errors:
            print(f"ERREUR : {e}")
    n_measures = len(tables.get(MEASURES_TABLE, {}).get("measures", {}))
    n_visuals = len(list(RDEF.glob("pages/*/visuals/*/visual.json")))
    print(f"check_pbip : {len(tables)} tables, {n_measures} mesures, {n_visuals} visuels, "
          f"{len(docs)} fichiers JSON, {len(errors)} erreur(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
