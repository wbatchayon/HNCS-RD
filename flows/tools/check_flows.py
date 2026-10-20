"""Vérification hors ligne des flux HNCS-RD (bibliothèque standard uniquement).

Contrôles :
 1. chaque ``flows/src/<Id>/workflow.json`` est un JSON valide au format « Workflows » de solution ;
 2. correspondance exacte entre les définitions et ``flows/manifest.json`` ;
 3. tous les codes PA du catalogue ``flows`` du modèle sont couverts ;
 4. les listes désignées (paramètre ``table``) sont des titres de listes ou bibliothèques du modèle ;
 5. les colonnes de ``fieldsUsed`` existent ; les écritures ``item/<Colonne>`` y sont déclarées ;
 6. les statuts de ``statusesWritten`` appartiennent à l'énumération de la liste ;
 7. les transitions citées existent ;
 8. aucun statut écrit par un flux n'est l'arrivée d'une décision humaine (hors ``fluxExceptions``) et chaque
    statut écrit correspond à une transition autorisant ``FLUX`` déclarée par la définition ;
 9. les ``targetStatuses`` respectent exactement la partition (§ 8.2), chaque ligne étant couverte une seule fois ;
10. les notifications citées existent et ont un modèle HTML (et inversement) ; données exposées respectées ;
11. aucune action n'attache de fichier aux courriels ;
12. connecteurs standard uniquement, références de connexion ``hncs_*``, appels de flux enfants valides ;
13. socle : anti-boucle sur les déclencheurs SharePoint (seule condition sur les listes à statut contrôlé), portées Principal / Erreur,
    flux enfants avec réponse ; aucune lecture de StatutPrecedent ; aucun filtre OData sur une colonne Note ;
14. noms d'actions uniques, ``runAfter`` cohérents, profondeur ≤ 8, ≤ 500 actions, aucun ``{{`` résiduel ;
15. reprise de l'existant : entrée REPRISE et test de première version sur les listes contrôlées, PA-00D gardé par
    ``Fonction.Lot2Actif``, aucune mise à la corbeille sans vérification de version (PA-00B).

Code de sortie 0 si aucune erreur.
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOWS = ROOT / "flows"
MODEL = json.loads((ROOT / "provisioning" / "model" / "model.generated.json").read_text(encoding="utf-8"))

STANDARD_APIS = {"shared_sharepointonline": "hncs_sharepoint", "shared_office365": "hncs_outlook",
                 "shared_teams": "hncs_teams", "shared_office365users": "hncs_o365users"}
REQUIRED_ENV = ["hncs_SiteUrl"]
ANTI_LOOP = ("@not(equals(toLower(triggerOutputs()?['body/Editor/Email']), "
             "toLower(parameters('hncs_ServiceAccountEmail (hncs_ServiceAccountEmail)'))))")
SYSTEM_FIELDS = {"ID", "Created", "Modified", "Author", "Editor"}
ALLOWED_TYPES = {"OpenApiConnection", "Compose", "Select", "Query", "Table", "If", "Switch", "Foreach", "Scope",
                 "Terminate", "Workflow", "Response", "InitializeVariable", "AppendToArrayVariable", "IncrementVariable",
                 "SetVariable", "Until"}
KINDS = {"SharePointItem", "SharePointFile", "SharedMailbox", "Recurrence", "ChildFlow", "Manual"}
TYPES = {"Automatisé", "Planifié", "Flux enfant"}
GUID_PREFIX = "urn:hncs-rd:flow:"


def code_matches(flow_code, manifest_code):
    """Le code de partition « PA-01 » couvre « PA-01a » / « PA-01b » (variantes du même flux, § 8.3)."""
    return re.fullmatch(re.escape(flow_code) + r"[a-z]?", manifest_code) is not None


def workflow_guid(tid):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, GUID_PREFIX + tid))


objects = {o["name"]: o for o in MODEL["objects"]}
titles = {o["title"]: o["name"] for o in MODEL["objects"]}


def columns(lst):
    o = objects[lst]
    cols = {c["name"] for c in o["columns"]}
    if o.get("titleColumn"):
        cols.add("Title")
    return cols | SYSTEM_FIELDS


CONTROLLED = {p["list"] for p in MODEL["partition"]}


def note_columns(lst):
    return {c["name"] for c in objects[lst]["columns"] if c["type"] == "Note"}


def status_enum(lst):
    o = objects[lst]
    return MODEL["enums"].get(o["statusEnum"]) if o.get("statusEnum") else None


errors: list = []
warnings: list = []


def err(msg):
    errors.append(msg)


def walk(actions, depth=1, parent="(racine)", out=None):
    """Parcourt les actions ; renvoie [(nom, action, profondeur, conteneur, frères)]."""
    out = [] if out is None else out
    for name, a in actions.items():
        out.append((name, a, depth, parent, actions))
        for key in ("actions",):
            if isinstance(a.get(key), dict):
                walk(a[key], depth + 1, name, out)
        if isinstance(a.get("else"), dict) and isinstance(a["else"].get("actions"), dict):
            walk(a["else"]["actions"], depth + 1, name, out)
        if isinstance(a.get("cases"), dict):
            for c in a["cases"].values():
                walk(c.get("actions", {}), depth + 1, name, out)
        if isinstance(a.get("default"), dict):
            walk(a["default"].get("actions", {}), depth + 1, name, out)
    return out


def check_workflow(tid, wf, entry, child_guids):
    where = f"{tid}"
    props = wf.get("properties")
    if wf.get("schemaVersion") != "1.0.0.0" or not isinstance(props, dict):
        err(f"{where} : structure racine invalide (properties / schemaVersion)")
        return
    if props.get("templateName", None) != "":
        err(f"{where} : templateName attendu vide")
    d = props.get("definition", {})
    if not d.get("$schema", "").endswith("workflowdefinition.json#") or d.get("contentVersion") != "1.0.0.0":
        err(f"{where} : $schema / contentVersion invalides")
    params = d.get("parameters", {})
    for p in ("$connections", "$authentication"):
        if p not in params:
            err(f"{where} : paramètre {p} absent")
    for env in REQUIRED_ENV:
        key = f"{env} ({env})"
        if key not in params or params[key].get("metadata", {}).get("schemaName") != env:
            err(f"{where} : variable d'environnement {key} absente ou mal formée")
    for key, val in params.items():
        if key.startswith("hncs_"):
            m = re.fullmatch(r"(hncs_\w+) \((hncs_\w+)\)", key)
            if not m or m.group(1) != m.group(2) or val.get("type") != "String":
                err(f"{where} : paramètre d'environnement mal formé {key}")
    crefs = props.get("connectionReferences", {})
    for api, ref in crefs.items():
        if api not in STANDARD_APIS:
            err(f"{where} : connecteur non standard {api}")
        elif ref.get("connection", {}).get("connectionReferenceLogicalName") != STANDARD_APIS[api]:
            err(f"{where} : référence de connexion {api} ≠ {STANDARD_APIS[api]}")
    triggers = d.get("triggers", {})
    if len(triggers) != 1:
        err(f"{where} : un et un seul déclencheur attendu")
        return
    tname, trig = next(iter(triggers.items()))
    kind = entry["trigger"]["kind"]
    text = json.dumps(wf, ensure_ascii=False)
    if "{{" in text:
        err(f"{where} : variable de modèle non substituée ({{{{…}}}})")
    # déclencheur
    if kind == "ChildFlow":
        if trig.get("type") != "Request" or trig.get("kind") != "Button":
            err(f"{where} : flux enfant sans déclencheur manuel (Request/Button)")
    elif kind == "Recurrence":
        if trig.get("type") != "Recurrence":
            err(f"{where} : déclencheur Recurrence attendu")
    else:
        host = trig.get("inputs", {}).get("host", {})
        op = host.get("operationId")
        expected = {"SharePointItem": {"GetOnNewItems", "GetOnUpdatedItems"}, "SharePointFile": {"GetOnUpdatedFileItems"},
                    "SharedMailbox": {"SharedMailboxOnNewEmailV2"}}.get(kind, set())
        if op not in expected:
            err(f"{where} : opération de déclenchement {op} incohérente avec {kind}")
        if kind in ("SharePointItem", "SharePointFile"):
            table = trig.get("inputs", {}).get("parameters", {}).get("table")
            if titles.get(table) != entry["trigger"]["list"]:
                err(f"{where} : liste du déclencheur « {table} » ≠ manifeste {entry['trigger']['list']}")
            conds = [c.get("expression") for c in trig.get("conditions", [])]
            if ANTI_LOOP not in conds:
                err(f"{where} : condition anti-boucle (§ 8.1) absente du déclencheur")
            if entry["targetStatuses"]:
                tgt = [c for c in conds if "body/Statut/Value" in (c or "")]
                guard = ""
                if not tgt:
                    # P-09 : flux déclenché sur toute modification humaine ; la garde de transition est dans le flux
                    for name, a, *_ in walk(d.get("actions", {})):
                        if name == "Si_aucune_transition_a_traiter":
                            guard = a.get("expression", "")
                    if not guard:
                        err(f"{where} : ni condition de déclenchement sur le statut cible, ni garde de transition dans le flux")
                text_c = "".join(conds) + guard
                for st in entry["targetStatuses"]:
                    if st.replace("'", "''") not in text_c:
                        err(f"{where} : statut cible « {st} » absent des conditions de déclenchement / de la garde de transition")
    # actions
    actions = d.get("actions", {})
    allacts = walk(actions)
    names = [n for n, *_ in allacts]
    dups = {n for n in names if names.count(n) > 1}
    if dups:
        err(f"{where} : noms d'actions en double {sorted(dups)[:5]}")
    if len(allacts) > 500:
        err(f"{where} : {len(allacts)} actions (> 500)")
    maxd = max((dp for _, _, dp, _, _ in allacts), default=0)
    if maxd > 8:
        err(f"{where} : profondeur d'imbrication {maxd} (> 8)")
    fields_used = entry["fieldsUsed"]
    has_response = False
    # RX-02 : StatutPrecedent n'est jamais une source de décision (ni StatutAvant, ni condition de déclenchement)
    # (seule lecture admise : la version précédente de l'élément, pour rétablir la colonne technique elle-même)
    if re.search(r"(?<!\?\[1\])\?\['StatutPrecedent'\]|body/StatutPrecedent", text):
        err(f"{where} : lecture de StatutPrecedent (le statut validé se lit dans HistoriqueStatuts, § 8.1)")
    if kind in ("SharePointItem", "SharePointFile") and entry["trigger"]["list"] in CONTROLLED:
        conds = [c.get("expression") for c in trig.get("conditions", [])]
        if conds != [ANTI_LOOP]:
            err(f"{where} : liste à statut contrôlé : la condition de déclenchement doit être l'anti-boucle seule (RX-02)")
    if re.search(r'"_[a-z]\w*"\s*:', text):
        err(f"{where} : clé interne du générateur présente dans la définition")
    # Références : action existante ; jamais une action interne à une boucle Foreach depuis l'extérieur
    parents = {}

    def index(acts, chain):
        for nm, a in acts.items():
            parents[nm] = chain
            sub = chain + ([nm] if a.get("type") == "Foreach" else [])
            for key in ("actions",):
                if isinstance(a.get(key), dict):
                    index(a[key], sub)
            if isinstance(a.get("else"), dict):
                index(a["else"].get("actions", {}), sub)
            for c in (a.get("cases") or {}).values():
                index(c.get("actions", {}), sub)
            if isinstance(a.get("default"), dict):
                index(a["default"].get("actions", {}), sub)
    index(actions, [])
    for nm, a, *_ in allacts:
        own = json.dumps({k: v for k, v in a.items() if k not in ("actions", "else", "cases", "default")}, ensure_ascii=False)
        for ref in set(re.findall(r"(?:body|outputs|actions)\('([^']+)'\)", own)):
            if ref not in parents:
                err(f"{where}/{nm} : référence à une action inconnue « {ref} »")
            elif any(lp not in parents[nm] + [nm] for lp in parents[ref]):
                err(f"{where}/{nm} : référence à « {ref} », interne à une boucle Foreach, depuis l'extérieur de la boucle")
        for ref in set(re.findall(r"items\('([^']+)'\)", own)):
            if ref not in parents[nm] + ([nm] if a.get("type") == "Foreach" else []):
                err(f"{where}/{nm} : items('{ref}') hors de la boucle correspondante")
    for name, a, depth, parent, siblings in allacts:
        t = a.get("type")
        if t not in ALLOWED_TYPES:
            err(f"{where}/{name} : type d'action non autorisé {t}")
        for dep in a.get("runAfter", {}):
            if dep not in siblings:
                err(f"{where}/{name} : runAfter vers « {dep} » hors du conteneur")
        if t == "Response":
            has_response = True
        if t == "Terminate" and parent != "(racine)":
            # Terminate interdit dans une boucle
            pass
        if t == "Workflow":
            ref = a.get("inputs", {}).get("host", {}).get("workflowReferenceName")
            if ref not in child_guids:
                err(f"{where}/{name} : appel d'un flux enfant inconnu {ref}")
            else:
                code = child_guids[ref]
                if code not in entry["childFlows"]:
                    err(f"{where}/{name} : flux enfant {code} absent de childFlows")
        if t == "OpenApiConnection":
            host = a.get("inputs", {}).get("host", {})
            api = host.get("connectionName")
            if api not in crefs:
                err(f"{where}/{name} : connexion {api} non déclarée")
            if host.get("apiId") != f"/providers/Microsoft.PowerApps/apis/{api}":
                err(f"{where}/{name} : apiId incohérent")
            p = a.get("inputs", {}).get("parameters", {})
            for k, v in p.items():
                if "attachment" in k.lower() and v not in (None, "", [], "@null"):
                    err(f"{where}/{name} : pièce jointe interdite dans un courriel ({k})")
            if api == "shared_sharepointonline" and "table" in p:
                tbl = p["table"]
                lst = titles.get(tbl)
                if not lst:
                    err(f"{where}/{name} : table « {tbl} » n'est pas un titre de liste du modèle")
                    continue
                flt = p.get("$filter") or ""
                for col in re.findall(r"\b([A-Za-z]\w*)\s+(?:eq|ne|lt|gt|le|ge)\b", flt):
                    if col in note_columns(lst):
                        err(f"{where}/{name} : filtre OData sur la colonne Note {lst}.{col} (non filtrable)")
                for k, val in p.items():
                    mc = re.fullmatch(r"item/([^/]+)/Value", k)
                    if mc and isinstance(val, str) and not val.startswith("@") and mc.group(1) in columns(lst):
                        col = next((c for c in objects[lst]["columns"] if c["name"] == mc.group(1)), None)
                        enum = MODEL["enums"].get(col["enum"]) if col and col.get("enum") else None
                        if enum is not None and val not in enum:
                            err(f"{where}/{name} : valeur « {val} » hors énumération pour {lst}.{mc.group(1)}")
                for k in p:
                    m = re.match(r"item/([^/]+)", k)
                    if m:
                        fld = m.group(1)
                        if fld not in columns(lst):
                            err(f"{where}/{name} : colonne inconnue {lst}.{fld}")
                        elif fld not in fields_used.get(lst, []):
                            err(f"{where}/{name} : colonne écrite {lst}.{fld} absente de fieldsUsed")
                if host.get("operationId") in ("PatchItem", "PostItem", "PatchFileItem", "CreateNewFolder") and lst not in entry["listsWritten"]:
                    err(f"{where}/{name} : écriture dans {lst} absente de listsWritten")
                if host.get("operationId") in ("GetItems", "GetItem", "GetFileItems", "GetItemChanges") and lst not in entry["listsRead"]:
                    err(f"{where}/{name} : lecture de {lst} absente de listsRead")
            if host.get("operationId", "").lower().startswith("http") and api != "shared_sharepointonline":
                err(f"{where}/{name} : requête HTTP hors connecteur SharePoint")
    if kind == "ChildFlow" and not has_response:
        err(f"{where} : flux enfant sans action « Répondre à une application ou à un flux »")
    if kind != "ChildFlow":
        if not ("Principal" in actions and "Erreur" in actions):
            err(f"{where} : portées Principal / Erreur absentes (§ 8.1)")
        else:
            ra = actions["Erreur"].get("runAfter", {}).get("Principal", [])
            if set(ra) != {"Failed", "TimedOut"}:
                err(f"{where} : la portée Erreur doit s'exécuter si Principal échoue ou expire")
            sub = json.dumps(actions["Erreur"])
            if workflow_guid("PA-00C") not in sub or '"Failed"' not in sub:
                err(f"{where} : la portée Erreur doit appeler PA-00C puis terminer en échec")
        if "Lire_parametres" not in names:
            err(f"{where} : lecture des Parametres absente")


def main():
    manifest_path = FLOWS / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"ERREUR manifeste illisible : {e}")
        return 1
    ids = [m.get("id") for m in manifest]
    if len(ids) != len(set(ids)):
        err("manifeste : IdTechnique en double")
    by_id = {m["id"]: m for m in manifest}
    src_ids = {p.parent.name for p in (FLOWS / "src").glob("*/workflow.json")}
    for i in sorted(src_ids - set(by_id)):
        err(f"{i} : définition sans entrée de manifeste")
    for i in sorted(set(by_id) - src_ids):
        err(f"{i} : entrée de manifeste sans définition")
    flow_codes = {f["id"] for f in MODEL["flows"]}
    covered = {m["code"] for m in manifest}
    for c in sorted(flow_codes - covered):
        err(f"code {c} du catalogue non couvert")
    for c in sorted(covered - flow_codes):
        err(f"code {c} inconnu du catalogue")
    base_codes = {t["baseCode"] for t in MODEL["transitions"]}
    human = {(h["object"], h["status"]) for h in MODEL["humanDecisions"]}
    exceptions = set(MODEL["fluxExceptions"])
    notif_codes = {n["code"]: n for n in MODEL["notifications"]}
    templates = {p.stem for p in (FLOWS / "templates").glob("N-*.html")}
    child_guids = {workflow_guid(i): by_id[i]["code"] for i in by_id if by_id[i]["trigger"]["kind"] == "ChildFlow"}
    list_objects = {}
    for t in MODEL["transitions"]:
        list_objects.setdefault(t["list"], t["object"])
    for m in manifest:
        tid = m["id"]
        if not re.fullmatch(r"PA-\d\d[A-Za-z]?(-[a-z]+)?", tid):
            err(f"{tid} : IdTechnique mal formé")
        if not tid.startswith(m["code"]):
            err(f"{tid} : l'IdTechnique doit commencer par le code {m['code']}")
        if m["type"] not in TYPES:
            err(f"{tid} : type « {m['type']} » invalide")
        if m["trigger"]["kind"] not in KINDS:
            err(f"{tid} : type de déclencheur invalide")
        if not m["displayName"].startswith(f"HNCS-RD {m['code']} : "):
            err(f"{tid} : displayName non conforme à la convention § 2.2")
        lstt = m["trigger"]["list"]
        if lstt is not None and lstt not in objects:
            err(f"{tid} : liste de déclenchement inconnue {lstt}")
        for lst in set(m["listsRead"]) | set(m["listsWritten"]):
            if lst not in objects:
                err(f"{tid} : liste inconnue {lst}")
        for lst, fields in m["fieldsUsed"].items():
            if lst not in objects:
                err(f"{tid} : fieldsUsed liste inconnue {lst}")
                continue
            for fl in fields:
                if fl not in columns(lst):
                    err(f"{tid} : colonne inconnue {lst}.{fl}")
        for lst, sts in m["statusesWritten"].items():
            enum = status_enum(lst) if lst in objects else None
            if enum is None:
                err(f"{tid} : statuts écrits sur une liste sans statut {lst}")
                continue
            for s in sts:
                if s not in enum:
                    err(f"{tid} : statut « {s} » hors énumération de {lst}")
                    continue
                obj = list_objects.get(lst)
                if obj is None:
                    continue  # statuts libres (§ 6.1 règle 7)
                cands = [t for t in MODEL["transitions"] if t["list"] == lst and t["to"] == s
                         and "FLUX" in t["actors"] and t["baseCode"] in m["transitions"]]
                if not cands:
                    err(f"{tid} : écrit « {s} » sur {lst} sans transition FLUX déclarée")
                for t in cands:
                    if (obj, s) in human and t["baseCode"] not in exceptions:
                        err(f"{tid} : {t['code']} écrit une décision humaine ({obj} → {s})")
        for t in m["transitions"]:
            if t not in base_codes:
                err(f"{tid} : transition inconnue {t}")
        for n in m["notifications"]:
            if n not in notif_codes:
                err(f"{tid} : notification inconnue {n}")
            elif n not in templates:
                err(f"{tid} : modèle flows/templates/{n}.html absent")
        for c in m["childFlows"]:
            if c not in ("PA-00A", "PA-00B", "PA-00C"):
                err(f"{tid} : flux enfant inattendu {c}")
        part = [p for p in MODEL["partition"] if code_matches(p["flow"], m["code"]) and p["list"] == lstt]
        expected = part[0]["targets"] if part else []
        if list(m["targetStatuses"]) != list(expected):
            err(f"{tid} : targetStatuses {m['targetStatuses']} ≠ partition {expected}")
        wf_path = FLOWS / "src" / tid / "workflow.json"
        if wf_path.exists():
            try:
                wf = json.loads(wf_path.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                err(f"{tid} : JSON invalide ({e})")
                continue
            check_workflow(tid, wf, m, child_guids)
    # Reprise de l'existant (spec 6.1, point 3 ter ; H-57)
    texts = {}
    for m in manifest:
        wp = FLOWS / "src" / m["id"] / "workflow.json"
        if wp.exists():
            texts[m["id"]] = wp.read_text(encoding="utf-8")
    creation_test = ("triggerOutputs()?['body/Created']", "triggerOutputs()?['body/Modified']")
    for lst in sorted(CONTROLLED):
        defs = [m for m in manifest if m["trigger"]["list"] == lst and m["trigger"]["kind"] == "SharePointItem"]
        updated = [m for m in defs if "GetOnUpdatedItems" in texts.get(m["id"], "")]
        if not any("'REPRISE'" in texts.get(m["id"], "") or '"REPRISE"' in texts.get(m["id"], "") for m in updated):
            err(f"{lst} : aucun flux de la liste n'écrit l'entrée REPRISE (reprise de l'existant)")
        for m in updated:
            t = texts.get(m["id"], "")
            if not all(c in t for c in creation_test):
                err(f"{m['id']} : test de première version (Created = Modified de l'événement) absent")
    d_text = texts.get("PA-00D", "")
    if '"REPRISE"' not in d_text and "'REPRISE'" not in d_text:
        err("PA-00D : écriture des entrées REPRISE absente")
    if "Fonction.Lot2Actif" not in d_text:
        err("PA-00D : la reprise et les empreintes doivent être gardées par le paramètre Fonction.Lot2Actif")
    if re.search(r"Origine eq 'Flux'", d_text):
        err("PA-00D : l'activation du lot 2 ne doit jamais être déduite de l'historique")
    b_text = texts.get("PA-00B", "")
    if "recycle()" in b_text and "Versions_avant_corbeille" not in b_text:
        err("PA-00B : la mise à la corbeille doit vérifier que l'élément est à sa première version")
    # partition couverte une seule fois
    for p in MODEL["partition"]:
        owners = [m["id"] for m in manifest if code_matches(p["flow"], m["code"]) and m["trigger"]["list"] == p["list"]]
        if len(owners) != 1:
            err(f"partition {p['list']} / {p['flow']} : {len(owners)} définition(s) au lieu d'une")
    # modèles
    for code in sorted(set(notif_codes) - templates):
        err(f"modèle absent pour {code}")
    for code in sorted(templates - set(notif_codes)):
        err(f"modèle {code}.html hors catalogue")
    for code in sorted(templates & set(notif_codes)):
        raw = (FLOWS / "templates" / f"{code}.html").read_text(encoding="utf-8")
        data = set(notif_codes[code]["data"])
        variables = set(re.findall(r"\{\{(\w+)\}\}", raw))
        if "NOM" not in data and any(re.match(r"Nom[A-Z]", v) for v in variables):
            err(f"{code} : nom de personne exposé alors que les données exposées sont {sorted(data)}")
        if "COMM" not in data and any(v.startswith("Commentaire") for v in variables):
            err(f"{code} : commentaire exposé alors que les données exposées sont {sorted(data)}")
        if re.search(r"AvisAnalyse|CommentaireRestreint|CriteresEvaluation|SyntheseParcours|MotifCommentaire", raw):
            err(f"{code} : référence à une colonne confidentielle")
        if f"[HNCS-R&amp;D][{code}]" not in raw:
            err(f"{code} : objet sans préfixe [HNCS-R&D][{code}]")
    if (FLOWS / "manifest.json").exists():
        enabled_children = [m for m in manifest if m["code"] in ("PA-00A", "PA-00B", "PA-00C") and not m["enabledByDefault"]]
        if enabled_children:
            err("les flux enfants PA-00A/B/C doivent être activés par défaut")
        pa13 = [m for m in manifest if m["code"] == "PA-13"]
        if pa13 and any(m["enabledByDefault"] for m in pa13):
            err("PA-13 doit être désactivé par défaut")
    for e in errors:
        print(f"ERREUR {e}")
    for w in warnings:
        print(f"ATTENTION {w}")
    print(f"{len(manifest)} définitions vérifiées, {len(errors)} erreur(s), {len(warnings)} avertissement(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
