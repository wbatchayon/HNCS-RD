#!/usr/bin/env python3
"""Extrait le modèle machine de spec.md (et des sous-specs) vers provisioning/model/model.generated.json.

Usage :
    python tools/spec_extract.py            # génère le fichier
    python tools/spec_extract.py --check    # échoue si le fichier généré n'est pas à jour

Le script vérifie aussi la cohérence interne de la spec (énumérations, lookups, lots, transitions,
partition des statuts, décisions humaines, matrice d'accès, Power BI) et s'arrête au premier lot d'erreurs.
Bibliothèque standard uniquement.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec.md"
SUBSPECS = [
    ROOT / "specs" / "sharepoint-vues.md",
    ROOT / "specs" / "referentiels-initiaux.md",
    ROOT / "specs" / "notifications.md",
]
OUTPUT = ROOT / "provisioning" / "model" / "model.generated.json"

COLUMN_TYPES = {
    "Text", "Note", "Choice", "MultiChoice", "Number", "Boolean", "Date", "DateTime",
    "User", "UserMulti", "Lookup", "LookupMulti", "URL",
}
PERMISSION_LEVELS = {"FC", "CSS", "R", "—"}
GROUP_ROLES = {
    "PROPRIETAIRE": "G_PROP", "DIRECTION_RD": "G_DRD", "RD": "G_RD", "ADMIN": "G_ADM",
    "REFERENT": "G_REF", "ALTERNANT": "G_ALT", "DIRECTION": "G_DIR", "ECOLES": "G_ECO",
}
FLUX_EXCEPTIONS = {"CAND-T02"}
EMPTY = {"", "—", "-"}


class SpecError(Exception):
    pass


# --------------------------------------------------------------------------- lecture

def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def unquote(cell: str) -> str:
    cell = cell.strip()
    if len(cell) >= 2 and cell.startswith("`") and cell.endswith("`"):
        cell = cell[1:-1]
    return cell.strip()


def is_heading(line: str) -> bool:
    return bool(re.match(r"^#{1,4} ", line))


def tables_after(lines: list[str], start: int) -> list[list[dict]]:
    """Tables markdown situées entre la ligne start (exclue) et le titre suivant."""
    tables: list[list[dict]] = []
    i = start + 1
    while i < len(lines) and not is_heading(lines[i]):
        if lines[i].lstrip().startswith("|"):
            block = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                block.append(lines[i])
                i += 1
            header = split_row(block[0])
            rows = []
            for raw in block[2:]:
                cells = split_row(raw)
                if len(cells) != len(header):
                    raise SpecError(f"Ligne de tableau mal formée ({len(cells)} cellules pour {len(header)}) : {raw}")
                rows.append(dict(zip(header, cells)))
            tables.append(rows)
            continue
        i += 1
    return tables


def code_block_after(lines: list[str], start: int) -> list[str]:
    i = start + 1
    while i < len(lines) and not lines[i].startswith("```"):
        if is_heading(lines[i]):
            raise SpecError(f"Bloc de code attendu après la ligne {start + 1}")
        i += 1
    j = i + 1
    while j < len(lines) and not lines[j].startswith("```"):
        j += 1
    return lines[i + 1:j]


def find_headings(lines: list[str], pattern: str) -> list[tuple[int, re.Match]]:
    rx = re.compile(pattern)
    return [(i, m) for i, l in enumerate(lines) if (m := rx.match(l))]


def single(lines: list[str], tag: str) -> int:
    found = find_headings(lines, rf"^### {re.escape(tag)}\s*$")
    if len(found) != 1:
        raise SpecError(f"Section « ### {tag} » attendue une fois, trouvée {len(found)} fois")
    return found[0][0]


def split_values(cell: str, sep: str = ";") -> list[str]:
    cell = unquote(cell)
    if cell in EMPTY:
        return []
    return [v.strip() for v in cell.split(sep) if v.strip()]


# --------------------------------------------------------------------------- parsing

def parse_enums(lines):
    tables = tables_after(lines, single(lines, "ENUM"))
    return {row["Code"]: split_values(row["Valeurs"]) for row in tables[0]}


def parse_params(cell: str) -> dict:
    out: dict = {}
    for token in split_values(cell, ";"):
        if "=" in token:
            k, v = token.split("=", 1)
            out[k.strip()] = v.strip()
        else:
            out[token.strip()] = True
    return out


def parse_column(row: dict) -> dict:
    p = parse_params(row["Paramètres"])
    col = {
        "name": row["Nom interne"],
        "label": row["Libellé"],
        "type": row["Type"],
        "required": row["Oblig."] == "Oui",
        "description": row.get("Description", ""),
        "enum": p.get("enum"),
        "lookup": p.get("lookup"),
        "default": p.get("default"),
        "indexed": bool(p.get("indexed")),
        "unique": bool(p.get("unique")),
        "hidden": bool(p.get("hidden")),
        "flux": bool(p.get("flux")),
        "perso": bool(p.get("perso")),
        "confidentiel": bool(p.get("confidentiel")),
        "min": float(p["min"]) if "min" in p else None,
        "max": float(p["max"]) if "max" in p else None,
        "decimals": int(p["decimals"]) if "decimals" in p else None,
        "lot": int(p["lot"]) if "lot" in p else None,
        "implicit": False,
    }
    unknown = set(p) - {"enum", "lookup", "default", "indexed", "unique", "hidden", "flux", "perso",
                        "confidentiel", "min", "max", "decimals", "lot"}
    if unknown:
        raise SpecError(f"Paramètres inconnus {unknown} sur la colonne {col['name']}")
    return col


def parse_lists(lines):
    objects = []
    for idx, m in find_headings(lines, r"^### (LST|LIB): (\w+)\s*$"):
        kind = "list" if m.group(1) == "LST" else "library"
        name = m.group(2)
        tables = tables_after(lines, idx)
        if len(tables) < 2:
            raise SpecError(f"{name} : tableau de propriétés et tableau de colonnes attendus")
        props = {r["Propriété"]: unquote(r["Valeur"]) for r in tables[0]}
        prefix = props.get("Préfixe ID", "—")
        status_enum = props.get("Énumération de statut", "—")
        obj = {
            "name": name,
            "kind": kind,
            "title": props["Titre affiché"],
            "lot": int(props["Lot"]),
            "domain": props.get("Domaine"),
            "prefix": None if prefix in EMPTY else prefix,
            "statusEnum": None if status_enum in EMPTY else status_enum,
            "initialStatus": props.get("Statut initial"),
            "personalData": props.get("Données personnelles") == "Oui",
            "titleLabel": props.get("Libellé Title"),
            "titleRequired": props.get("Title obligatoire", "Oui") == "Oui",
            "validation": props.get("Validation"),
            "validationMessage": props.get("Message de validation"),
            "versioning": props.get("Versioning"),
            "folders": props.get("Dossiers"),
            "columns": [],
        }
        explicit = [parse_column(r) for r in tables[1]]
        title_col = next((c for c in explicit if c["name"] == "Title"), None)
        if title_col:
            obj["titleLabel"] = title_col["label"]
            obj["titleRequired"] = title_col["required"]
        obj["titleColumn"] = title_col or {
            "name": "Title", "label": obj["titleLabel"], "type": "Text", "required": obj["titleRequired"],
            "perso": False, "confidentiel": False, "indexed": False, "unique": False, "implicit": True,
        }
        cols = [c for c in explicit if c["name"] != "Title"]
        implicit = []
        if obj["prefix"]:
            implicit.append({"name": "IdHNCS", "label": "Identifiant HNCS", "type": "Text", "required": False,
                             "indexed": True, "unique": True, "flux": True})
        if obj["statusEnum"]:
            implicit += [
                {"name": "Statut", "label": "Statut", "type": "Choice", "required": True,
                 "enum": obj["statusEnum"], "default": obj["initialStatus"], "indexed": True},
                {"name": "StatutPrecedent", "label": "Statut précédent (technique)", "type": "Text",
                 "required": False, "hidden": True, "flux": True},
                {"name": "DateStatut", "label": "Date du dernier changement de statut", "type": "DateTime",
                 "required": False, "flux": True},
            ]
        for c in implicit:
            base = {"description": "", "enum": None, "lookup": None, "default": None, "indexed": False,
                    "unique": False, "hidden": False, "flux": False, "perso": False, "confidentiel": False,
                    "min": None, "max": None, "decimals": None, "lot": None}
            base.update(c)
            base["implicit"] = True
            cols.insert(0, base) if c["name"] == "IdHNCS" else cols.append(base)
        # IdHNCS en tête, statut en fin
        obj["columns"] = cols
        objects.append(obj)
    return objects


def parse_simple(lines, tag, idx_table=0):
    return tables_after(lines, single(lines, tag))[idx_table]


def parse_transitions(lines, enums, objects_by_name, partition):
    object_to_list = {}
    for p in partition:
        object_to_list.setdefault(p["object"], p["list"])
    result = []
    for idx, m in find_headings(lines, r"^### TRANSITIONS: (\w+)\s*$"):
        obj = m.group(1)
        if obj not in object_to_list:
            raise SpecError(f"Transitions de {obj} : objet absent de la partition")
        lst = objects_by_name[object_to_list[obj]]
        statuses = enums[lst["statusEnum"]]
        for row in tables_after(lines, idx)[0]:
            frm_raw = unquote(row["De"])
            if frm_raw == "∅":
                froms = ["∅"]
            elif frm_raw == "*":
                froms = None  # développé par cible
            else:
                froms = split_values(frm_raw)
            tos = split_values(row["Vers"])
            pairs = []
            for to in tos:
                for frm in (froms if froms is not None else [s for s in statuses if s != to]):
                    pairs.append((frm, to))
            for k, (frm, to) in enumerate(pairs, start=1):
                code = row["Code"] if len(pairs) == 1 else f"{row['Code']}-{k:02d}"
                result.append({
                    "code": code,
                    "baseCode": row["Code"],
                    "object": obj,
                    "list": lst["name"],
                    "from": frm,
                    "to": to,
                    "actors": split_values(row["Acteurs"]),
                    "controls": split_values(row["Contrôle"]),
                    "flow": row["Flux responsable"],
                })
    return result


def parse_measures(lines):
    body = code_block_after(lines, single(lines, "MESURES"))
    names = []
    for l in body:
        if not l or l[0].isspace() or l.startswith("//"):
            continue
        m = re.match(r"^(.+?) =", l)
        if m:
            names.append(m.group(1).strip())
    return names, "\n".join(body)


def parse_pbi_tables(rows):
    tables = []
    for r in rows:
        cols = []
        for raw in split_values(r["Colonnes"]):
            m = re.match(r"^(\w+)\s*\(→\s*(?:booléen\s+)?(\w+)\s*\)$", raw)
            if m:
                cols.append({"name": m.group(2), "source": m.group(1),
                             "transform": "bool" if "booléen" in raw else "rename"})
            else:
                cols.append({"name": raw, "source": raw, "transform": None})
        tables.append({"table": r["Table"], "source": r["Source"], "columns": cols})
    return tables


def parse_views(lines):
    views = {}
    for idx, m in find_headings(lines, r"^### VUES: (\w+)\s*$"):
        out = []
        for r in tables_after(lines, idx)[0]:
            filt = []
            f = r["Filtre"].strip()
            if f not in EMPTY:
                for cond in f.split(" ET "):
                    cond = cond.strip()
                    mm = re.match(r"^(\w+) (est vide|non vide)$", cond)
                    if mm:
                        filt.append({"field": mm.group(1), "op": "isnull" if mm.group(2) == "est vide" else "isnotnull", "values": []})
                        continue
                    mm = re.match(r"^(\w+) (in|notin) \((.*)\)$", cond)
                    if mm:
                        filt.append({"field": mm.group(1), "op": mm.group(2), "values": [v.strip() for v in mm.group(3).split(";")]})
                        continue
                    mm = re.match(r"^(\w+) (=|<>|<=|>=|<|>) (.+)$", cond)
                    if mm:
                        filt.append({"field": mm.group(1), "op": mm.group(2), "values": [mm.group(3).strip()]})
                        continue
                    raise SpecError(f"Filtre de vue illisible : {cond}")
            sort = []
            s = r["Tri"].strip()
            if s not in EMPTY:
                for part in s.split(","):
                    fld, direction = part.strip().split()
                    sort.append({"field": fld, "dir": direction})
            out.append({
                "name": r["Vue"],
                "default": r["Par défaut"] == "Oui",
                "columns": [c.strip() for c in r["Colonnes"].split(",")],
                "filter": filt,
                "sort": sort,
                "groupBy": None if r["Regroupement"].strip() in EMPTY else r["Regroupement"].strip(),
            })
        views[m.group(1)] = out
    return views


def parse_seeds(lines):
    seeds = {}
    for idx, m in find_headings(lines, r"^### SEED: (\w+)\s*$"):
        seeds[m.group(1)] = [{k: unquote(v) for k, v in r.items()} for r in tables_after(lines, idx)[0]]
    return seeds


# --------------------------------------------------------------------------- contrôles

def validate(model) -> list[str]:
    errs: list[str] = []
    enums = model["enums"]
    objs = {o["name"]: o for o in model["objects"]}
    lists = {n: o for n, o in objs.items()}

    for o in model["objects"]:
        names = [c["name"] for c in o["columns"]]
        if len(names) != len(set(names)):
            errs.append(f"{o['name']} : colonnes en double")
        if o["statusEnum"] and o["statusEnum"] not in enums:
            errs.append(f"{o['name']} : énumération de statut inconnue {o['statusEnum']}")
        if o["statusEnum"] and o["initialStatus"] not in enums.get(o["statusEnum"], []):
            errs.append(f"{o['name']} : statut initial {o['initialStatus']} hors énumération")
        for c in o["columns"]:
            if c["type"] not in COLUMN_TYPES:
                errs.append(f"{o['name']}.{c['name']} : type inconnu {c['type']}")
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,31}", c["name"]):
                errs.append(f"{o['name']}.{c['name']} : nom interne non conforme")
            if c["type"] in ("Choice", "MultiChoice"):
                if not c["enum"] or c["enum"] not in enums:
                    errs.append(f"{o['name']}.{c['name']} : énumération manquante ou inconnue")
                elif c["default"] and c["default"] not in enums[c["enum"]]:
                    errs.append(f"{o['name']}.{c['name']} : défaut {c['default']} hors énumération")
            if c["type"] in ("Lookup", "LookupMulti"):
                tgt = lists.get(c["lookup"] or "")
                if not tgt or tgt["kind"] != "list":
                    errs.append(f"{o['name']}.{c['name']} : cible de lookup inconnue {c['lookup']}")
                else:
                    lot = c["lot"] or o["lot"]
                    if tgt["lot"] > lot:
                        errs.append(f"{o['name']}.{c['name']} : lookup vers {tgt['name']} (lot {tgt['lot']}) depuis le lot {lot}")
                    if not tgt["prefix"]:
                        errs.append(f"{o['name']}.{c['name']} : la cible {tgt['name']} n'a pas d'IdHNCS à afficher")
            if c["type"] == "Boolean" and c["default"] not in (None, "Oui", "Non"):
                errs.append(f"{o['name']}.{c['name']} : défaut booléen invalide")

    roles = set(enums["ROLE"])
    trans = model["transitions"]
    seen = set()
    for t in trans:
        lst = objs[t["list"]]
        statuses = enums[lst["statusEnum"]]
        if t["from"] != "∅" and t["from"] not in statuses:
            errs.append(f"{t['code']} : statut de départ inconnu « {t['from']} »")
        if t["to"] not in statuses:
            errs.append(f"{t['code']} : statut d'arrivée inconnu « {t['to']} »")
        for a in t["actors"]:
            if a not in roles:
                errs.append(f"{t['code']} : rôle inconnu {a}")
        for g in t["controls"]:
            if g not in model["controlsByCode"]:
                errs.append(f"{t['code']} : contrôle inconnu {g}")
        key = (t["object"], t["from"], t["to"])
        if key in seen:
            errs.append(f"{t['code']} : transition en double {key}")
        seen.add(key)

    # partition : disjointe et complète
    by_obj: dict[str, dict[str, str]] = {}
    for p in model["partition"]:
        lst = objs.get(p["list"])
        if not lst:
            errs.append(f"Partition : liste inconnue {p['list']}")
            continue
        for s in p["targets"]:
            if s not in enums[lst["statusEnum"]]:
                errs.append(f"Partition {p['flow']} : statut inconnu {s}")
            prev = by_obj.setdefault(p["object"], {}).get(s)
            if prev:
                errs.append(f"Partition : statut « {s} » de {p['object']} traité par {prev} et {p['flow']}")
            by_obj[p["object"]][s] = p["flow"]
    for obj, mapping in by_obj.items():
        lst = next(o for o in model["objects"] if o["name"] == next(p["list"] for p in model["partition"] if p["object"] == obj))
        missing = set(enums[lst["statusEnum"]]) - set(mapping)
        if missing:
            errs.append(f"Partition {obj} : statuts sans flux {sorted(missing)}")

    # décisions humaines : jamais FLUX (sauf exception explicite)
    decisions = {(d["object"], d["status"]) for d in model["humanDecisions"]}
    for t in trans:
        if (t["object"], t["to"]) in decisions and "FLUX" in t["actors"] and t["baseCode"] not in FLUX_EXCEPTIONS:
            errs.append(f"{t['code']} : FLUX autorisé sur une décision humaine ({t['object']} → {t['to']})")

    # matrice
    groups = {g["code"] for g in model["groups"]}
    for name, perms in model["matrix"].items():
        if name not in objs:
            errs.append(f"Matrice : objet inconnu {name}")
        for g, lvl in perms.items():
            if g not in groups:
                errs.append(f"Matrice : groupe inconnu {g}")
            base = re.sub(r"^IL\((\w+)\)$", r"\1", lvl)
            if base not in PERMISSION_LEVELS:
                errs.append(f"Matrice {name}/{g} : niveau inconnu {lvl}")
    for name in objs:
        if name not in model["matrix"]:
            errs.append(f"Matrice : {name} absent")

    # vues
    for lname, views in model["views"].items():
        o = objs.get(lname)
        if not o:
            errs.append(f"Vues : liste inconnue {lname}")
            continue
        colnames = {c["name"] for c in o["columns"]} | {"Title"}
        defaults = [v for v in views if v["default"]]
        if len(defaults) != 1:
            errs.append(f"Vues {lname} : une et une seule vue par défaut attendue")
        for v in views:
            for c in v["columns"] + [f["field"] for f in v["filter"]] + [s["field"] for s in v["sort"]] + ([v["groupBy"]] if v["groupBy"] else []):
                if c not in colnames:
                    errs.append(f"Vue {lname}/{v['name']} : colonne inconnue {c}")
            for f in v["filter"]:
                col = next((c for c in o["columns"] if c["name"] == f["field"]), None)
                if col and col["type"] in ("Choice", "MultiChoice"):
                    for val in f["values"]:
                        if val not in enums[col["enum"]]:
                            errs.append(f"Vue {lname}/{v['name']} : valeur « {val} » hors énumération {col['enum']}")

    # seeds
    for lname, rows in model["seeds"].items():
        o = objs.get(lname)
        if not o:
            errs.append(f"Seed : liste inconnue {lname}")
            continue
        colnames = {c["name"]: c for c in o["columns"]}
        for r in rows:
            for k, v in r.items():
                if k == "Title":
                    continue
                c = colnames.get(k)
                if not c:
                    errs.append(f"Seed {lname} : colonne inconnue {k}")
                elif c["type"] == "Choice" and v and v not in enums[c["enum"]]:
                    errs.append(f"Seed {lname} : « {v} » hors énumération {c['enum']}")
                elif c["type"] == "MultiChoice" and v:
                    for item in v.split(";"):
                        if item not in enums[c["enum"]]:
                            errs.append(f"Seed {lname} : « {item} » hors énumération {c['enum']}")

    # Power BI
    for t in model["powerbi"]["tables"]:
        src = objs.get(t["source"])
        if t["source"] in ("DAX",) or t["source"].startswith("DAX"):
            continue
        if t["table"] == "SujetDomaine":
            continue
        if not src:
            errs.append(f"Power BI {t['table']} : source inconnue {t['source']}")
            continue
        cols = {c["name"]: c for c in src["columns"]}
        cols["Title"] = src["titleColumn"]
        for c in t["columns"]:
            s = c["source"]
            if s == "Id":
                continue
            if s in cols:
                col = cols[s]
            elif s.endswith("Id") and s[:-2] in cols and cols[s[:-2]]["type"] in ("Lookup", "LookupMulti"):
                col = cols[s[:-2]]
            elif s.endswith("Email") and s[:-5] in cols and cols[s[:-5]]["type"] in ("User",):
                col = cols[s[:-5]]
            else:
                errs.append(f"Power BI {t['table']} : colonne source inconnue {s}")
                continue
            if (col.get("perso") or col.get("confidentiel")) and not (t["table"] == "Alternants" and s == "Title"):
                if c["transform"] != "bool":
                    errs.append(f"Power BI {t['table']} : colonne {s} marquée perso/confidentiel importée")
    for r in model["powerbi"]["relations"]:
        for side in ("from", "to"):
            tbl = r[side].split("[")[0]
            if tbl not in {t["table"] for t in model["powerbi"]["tables"]}:
                errs.append(f"Relation Power BI : table inconnue {tbl}")

    # flux référencés
    flow_ids = {f["id"] for f in model["flows"]}
    # Une référence « PA-01 » désigne la famille PA-01a / PA-01b.
    flow_codes = flow_ids | {re.sub(r"[a-z]$", "", i) for i in flow_ids}
    for t in trans:
        if t["flow"] not in flow_codes:
            errs.append(f"{t['code']} : flux inconnu {t['flow']}")
    for p in model["partition"]:
        if p["flow"] not in flow_codes:
            errs.append(f"Partition : flux inconnu {p['flow']}")
    for n in model["notifications"]:
        for f in re.findall(r"PA-\d\d[a-z]?[A-E]?", n["flow"]):
            if f not in flow_codes:
                errs.append(f"Notification {n['code']} : flux inconnu {f}")
    return errs


# --------------------------------------------------------------------------- assemblage

def build() -> dict:
    lines = read_lines(SPEC)
    sub = {p.name: read_lines(p) for p in SUBSPECS}
    version = re.search(r"\| Version de la spec \| ([0-9.]+) \|", "\n".join(lines)).group(1)

    enums = parse_enums(lines)
    objects = parse_lists(lines)
    objects_by_name = {o["name"]: o for o in objects}

    partition = [{"object": r["Objet"], "list": r["Liste"], "targets": split_values(r["Statuts cibles"]), "flow": r["Flux"]}
                 for r in parse_simple(lines, "PARTITION")]
    controls = [{"code": r["Code"], "object": r["Objet"], "rule": r["Règle"], "flow": r["Évalué par"]}
                for r in parse_simple(lines, "CONTROLES")]
    decisions = [{"object": r["Objet"], "status": r["Statut d'arrivée"], "decision": r["Décision humaine"],
                  "deciders": split_values(r["Décideur"])} for r in parse_simple(lines, "DECISIONS_HUMAINES")]
    roles = []
    for r in parse_simple(lines, "ROLES"):
        grp = re.search(r"`(HNCS-RD-\w+)`", r["Résolution"])
        roles.append({"role": r["Rôle"], "group": grp.group(1) if grp else None, "resolution": r["Résolution"]})
    groups = [{"code": r["Code"], "name": r["Nom du groupe"], "members": r["Membres cibles"], "description": r["Description"]}
              for r in parse_simple(lines, "GROUPES")]
    matrix_rows = parse_simple(lines, "MATRICE")
    matrix = {r["Objet"]: {k: v for k, v in r.items() if k != "Objet"} for r in matrix_rows}
    flows = [{"id": r["ID"], "name": r["Nom"], "type": r["Type"], "lot": r["Lot"], "trigger": r["Déclencheur technique"]}
             for r in parse_simple(lines, "FLUX")]
    measures, measures_dax = parse_measures(lines)

    model = {
        "$comment": "FICHIER GÉNÉRÉ par tools/spec_extract.py à partir de spec.md — ne pas modifier à la main.",
        "specVersion": version,
        "site": {"url": "https://<tenant>.sharepoint.com/sites/HNCS-RD", "title": "HNCS-R&D", "template": "STS#3",
                 "lcid": 1036, "timeZone": "Romance Standard Time"},
        "enums": enums,
        "objects": objects,
        "groups": groups,
        "roles": roles,
        "roleToGroupCode": GROUP_ROLES,
        "permissionLevels": {
            "FC": {"roleTypeKind": "Administrator"},
            "R": {"roleTypeKind": "Reader"},
            "CSS": {"name": "HNCS - Contribution sans suppression", "basedOn": "Contributor",
                    "remove": ["DeleteListItems", "DeleteVersions"]},
        },
        "matrix": matrix,
        "partition": partition,
        "controls": controls,
        "humanDecisions": decisions,
        "fluxExceptions": sorted(FLUX_EXCEPTIONS),
        "flows": flows,
        "views": parse_views(sub["sharepoint-vues.md"]),
        "parameters": [{k_out: unquote(r[k_in]) for k_out, k_in in
                        (("key", "Clé"), ("value", "Valeur"), ("category", "Catégorie"), ("description", "Description"))}
                       for r in parse_simple(sub["referentiels-initiaux.md"], "PARAMETRES")],
        "seeds": parse_seeds(sub["referentiels-initiaux.md"]),
        "notifications": [{"code": r["Code"], "flow": r["Flux"], "recipients": r["Destinataires"], "channel": r["Canal"],
                           "subject": r["Objet"], "content": r["Contenu"], "data": split_values(r["Données exposées"])}
                          for r in parse_simple(sub["notifications.md"], "NOTIFICATIONS")],
        "powerbi": {
            "tables": parse_pbi_tables(parse_simple(lines, "PBI_TABLES")),
            "relations": [{"from": r["De (plusieurs)"], "to": r["Vers (un)"], "active": r["Active"] == "Oui"}
                          for r in parse_simple(lines, "PBI_RELATIONS")],
            "measures": measures,
            "measuresDax": measures_dax,
            "roles": [{"role": r["Rôle"], "members": r["Membres (groupes Entra / personnes)"], "filters": r["Filtres (DAX)"], "ols": r["OLS"]}
                      for r in parse_simple(lines, "PBI_ROLES")],
        },
        "lots": [{"lot": r["Lot"], "content": r["Contenu dans ce dépôt"], "exit": r["Condition de sortie"]}
                 for r in parse_simple(lines, "LOTS")],
        "hypotheses": [{"id": r["ID"], "subject": r["Sujet"]} for r in parse_simple(lines, "HYPOTHESES")],
    }
    model["controlsByCode"] = {c["code"]: c for c in controls}
    model["transitions"] = parse_transitions(lines, enums, objects_by_name, partition)
    errs = validate(model)
    del model["controlsByCode"]
    if errs:
        raise SpecError("Incohérences dans la spec :\n  - " + "\n  - ".join(errs))
    return model


def render(model: dict) -> str:
    return json.dumps(model, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str]) -> int:
    try:
        content = render(build())
    except SpecError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    if "--check" in argv:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
            print(f"ERREUR : {OUTPUT.relative_to(ROOT)} n'est pas à jour ; exécuter python tools/spec_extract.py", file=sys.stderr)
            return 1
        print("Modèle à jour.")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"Écrit : {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
