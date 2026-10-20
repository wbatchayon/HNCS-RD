"""Génère les définitions de flux HNCS-RD à partir du modèle (spec) et des modèles de notification.

Sorties (versionnées telles quelles) :
- ``flows/src/<IdTechnique>/workflow.json`` ;
- ``flows/manifest.json`` ;
- ``flows/docs/PA-xx.md`` (une fiche par code PA).

Usage :
    python flows/tools/generate_flows.py           # régénère
    python flows/tools/generate_flows.py --check   # vérifie que les fichiers versionnés sont à jour (code 1 sinon)

Bibliothèque standard uniquement. Ne pas modifier les ``workflow.json`` à la main : modifier ce générateur.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flowlib import MODEL, ROOT, assemble  # noqa: E402
import defs_socle  # noqa: E402
import defs_recrutement  # noqa: E402
import defs_production  # noqa: E402
import defs_ecoles  # noqa: E402

FLOWS_DIR = ROOT / "flows"
BUILDERS = defs_socle.BUILDERS + defs_recrutement.BUILDERS + defs_production.BUILDERS + defs_ecoles.BUILDERS


def manifest_entry(f):
    reads = set(f.reads)
    if f.trigger_list:
        reads.add(f.trigger_list)
    return {
        "id": f.id,
        "code": f.code,
        "displayName": f.label,
        "lot": int(MODEL.flows[f.code]["lot"]),
        "type": f.type,
        "trigger": {"kind": f.trigger_kind, "list": f.trigger_list, "recurrence": f.recurrence},
        "targetStatuses": list(f.targets),
        "listsRead": sorted(reads),
        "listsWritten": sorted(f.writes),
        "fieldsUsed": {k: sorted(v) for k, v in sorted(f.fields.items())},
        "statusesWritten": {k: sorted(v, key=lambda s: MODEL.enum_of(k, "Statut").index(s)) for k, v in sorted(f.statuses.items()) if v},
        "transitions": sorted(f.transitions),
        "notifications": sorted(f.notifs),
        "childFlows": sorted(f.children),
        "enabledByDefault": f.enabled,
    }


TRIGGER_TEXT = {
    "SharePointItem": "SharePoint : élément de la liste « {title} » ({op})",
    "SharePointFile": "SharePoint : fichier de la bibliothèque « {title} » créé ou modifié (propriétés uniquement)",
    "SharedMailbox": "Office 365 Outlook : nouveau courriel dans une boîte partagée (V2), dossier « Candidatures »",
    "Recurrence": "Récurrence : {rec}",
    "ChildFlow": "Déclenchement manuel par un flux parent (action « Exécuter un flux enfant »)",
}


def trigger_text(f, entry):
    t = entry["trigger"]
    title = MODEL.title(t["list"]) if t["list"] else ""
    op = {"GetOnNewItems": "création", "GetOnUpdatedItems": "création ou modification"}.get(
        f.trigger["inputs"]["host"]["operationId"] if f.trigger.get("type") == "OpenApiConnection" else "", "")
    text = TRIGGER_TEXT[t["kind"]].format(title=title, op=op, rec=t["recurrence"])
    conds = f.trigger.get("conditions") or []
    return text, [c["expression"] for c in conds]


SPEC = ROOT / "spec.md"


def _slug(title: str) -> str:
    """Ancre de titre Markdown (GitHub) : minuscules, ponctuation retirée (lettres accentuées conservées), espaces → « - »."""
    t = title.strip().lower()
    t = re.sub(r"[^\w\- ]", "", t)
    return t.replace(" ", "-")


def spec_anchors():
    """Numéro de section (« 8.1 ») → ancre du titre correspondant dans spec.md."""
    anchors, seen = {}, {}
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if not m:
            continue
        slug = _slug(m.group(2))
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        if n:
            slug = f"{slug}-{n}"
        num = re.match(r"^(\d+(?:\.\d+)*)\.?\s", m.group(2))
        if num and num.group(1) not in anchors:
            anchors[num.group(1)] = slug
    return anchors


_ANCHORS = {}


def linkify(text: str, spec_path: str) -> str:
    """Renvois « § 8.1 », « § 6.1-8 », « § 6.1-3 bis » → liens Markdown vers les sections de spec.md."""
    if not _ANCHORS:
        _ANCHORS.update(spec_anchors())

    def rep(m):
        num, rule = m.group(1), m.group(2)
        if num not in _ANCHORS:
            raise SystemExit(f"Section de spec introuvable pour le renvoi § {num}")
        link = f"[{num}]({spec_path}#{_ANCHORS[num]})"
        return link + (f", règle {rule}" if rule else "")
    return re.sub(r"§\s?(\d+(?:\.\d+)?)(?:-(\d+(?: bis)?))?", rep, text)


def doc_for_code(code, flows, entries):
    first = flows[0]
    name = MODEL.flows[code]["name"]
    out = [f"# {code} : {name}", "",
           f"> Fiche générée par `flows/tools/generate_flows.py` à partir de la spec (§ 8.4) : ne pas modifier à la main.", "",
           "| Élément | Valeur |", "| --- | --- |",
           f"| Lot | {MODEL.flows[code]['lot']} |",
           f"| Type (spec) | {MODEL.flows[code]['type'].replace('**', '')} |",
           f"| Définitions techniques | {', '.join('`' + f.id + '`' for f in flows)} |",
           f"| Activé par défaut | {'Oui' if all(f.enabled for f in flows) else 'Non'} |", "",
           "## Objectif", "", first.doc.get("objectif", ""), ""]
    out += ["## Déclencheur(s)", ""]
    for f, e in zip(flows, entries):
        text, conds = trigger_text(f, e)
        out.append(f"- `{f.id}` : {text}.")
        for c in conds:
            out.append(f"  - condition de déclenchement : `{c}`")
        if e["targetStatuses"]:
            out.append(f"  - statuts cibles (partition § 8.2) : {', '.join('« ' + s + ' »' for s in e['targetStatuses'])}")
    out += ["", "## Entrées", ""]
    for f in flows:
        out.append(f"- `{f.id}` : {f.doc.get('entrees', '')}")
    out += ["", "## Traitement pas à pas", ""]
    for f in flows:
        if len(flows) > 1:
            out += [f"### {f.id}", ""]
        for i, st in enumerate(f.doc.get("etapes", []), 1):
            out.append(f"{i}. {re.sub(r'^[0-9]+[.] ', '', st)}")
        out.append("")
    out += ["## Sorties", ""]
    for f in flows:
        out.append(f"- `{f.id}` : {f.doc.get('sorties', '')}")
    trans = sorted({t for e in entries for t in e["transitions"]})
    out += ["", "## Transitions", ""]
    if trans:
        out += ["| Code | De | Vers | Acteurs | Contrôles |", "| --- | --- | --- | --- | --- |"]
        seen = set()
        for t in MODEL.transitions:
            if t["baseCode"] in trans and t["code"] not in seen:
                seen.add(t["code"])
                out.append(f"| {t['code']} | {t['from']} | {t['to']} | {', '.join(t['actors'])} | {', '.join(t['controls']) or '-'} |")
    else:
        out.append("Aucune transition de statut.")
    written = {}
    for e in entries:
        for k, v in e["statusesWritten"].items():
            written.setdefault(k, set()).update(v)
    if written:
        out += ["", "Statuts écrits par le compte de service (rôle `FLUX`, jamais une décision humaine) :", ""]
        for k, v in sorted(written.items()):
            out.append(f"- `{k}` : {', '.join('« ' + s + ' »' for s in sorted(v))}")
    notifs = sorted({n for e in entries for n in e["notifications"]})
    out += ["", "## Notifications", ""]
    if notifs:
        out += ["| Code | Destinataires | Canal | Objet | Modèle |", "| --- | --- | --- | --- | --- |"]
        for n in notifs:
            d = MODEL.notifications[n]
            out.append(f"| {n} | {d['recipients']} | {d['channel']} | {d['subject']} | `flows/templates/{n}.html` |")
    else:
        out.append("Aucune.")
    ctl = sorted({c for t in MODEL.transitions if t["baseCode"] in trans for c in t["controls"]})
    out += ["", "## Contrôles", ""]
    if ctl:
        for c in ctl:
            out.append(f"- `{c}` : {MODEL.control_rule(c)}")
    else:
        out.append("Aucun contrôle `G_*`.")
    out += ["", "## Erreurs et reprise", ""]
    for f in flows:
        out.append(f"- `{f.id}` : {f.doc.get('erreurs', '')}")
    out += ["", "## Décision humaine préservée", "", first.doc.get("decision", ""), "", "## Points de test", ""]
    for f in flows:
        for t in f.doc.get("tests", []):
            out.append(f"- {t}")
    out += ["", "## Données lues et écrites", ""]
    for f, e in zip(flows, entries):
        out.append(f"- `{f.id}` : lit {', '.join('`' + x + '`' for x in e['listsRead']) or '-'} ; écrit {', '.join('`' + x + '`' for x in e['listsWritten']) or '-'} ; "
                   f"flux enfants {', '.join(e['childFlows']) or '-'}.")
    return linkify("\n".join(out).rstrip() + "\n", "../../spec.md")


def build():
    flows = [b() for b in BUILDERS]
    ids = [f.id for f in flows]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SystemExit(f"IdTechnique en double : {dup}")
    files = {}
    entries = []
    for f in flows:
        wf = assemble(f)
        files[FLOWS_DIR / "src" / f.id / "workflow.json"] = json.dumps(wf, ensure_ascii=False, indent=2) + "\n"
        entries.append(manifest_entry(f))
    files[FLOWS_DIR / "manifest.json"] = json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
    by_code = {}
    for f, e in zip(flows, entries):
        by_code.setdefault(f.code, []).append((f, e))
    for code, pairs in by_code.items():
        files[FLOWS_DIR / "docs" / f"{code}.md"] = doc_for_code(code, [p[0] for p in pairs], [p[1] for p in pairs])
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="vérifie sans écrire")
    args = ap.parse_args()
    files = build()
    stale = []
    for path, content in files.items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            stale.append(path)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
    src = FLOWS_DIR / "src"
    orphans = [p for p in src.glob("*/workflow.json") if p not in files] if src.exists() else []
    if args.check:
        for p in stale:
            print(f"À régénérer : {p.relative_to(ROOT)}")
        for p in orphans:
            print(f"Définition orpheline : {p.relative_to(ROOT)}")
        print(f"{len(files)} fichiers attendus, {len(stale)} à régénérer, {len(orphans)} orphelin(s).")
        return 1 if stale or orphans else 0
    for p in orphans:
        print(f"Attention, définition orpheline (non supprimée) : {p.relative_to(ROOT)}")
    print(f"{len(files)} fichiers générés ({len(stale)} modifiés).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
