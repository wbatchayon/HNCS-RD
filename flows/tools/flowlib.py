"""Bibliothèque de construction des définitions de flux Power Automate (format « Workflows » de solution).

Utilisée par ``generate_flows.py``. Bibliothèque standard uniquement.

Principes :
- chaque flux est décrit en Python par un objet ``Flow`` et des séquences d'actions ``Seq`` ;
- les noms d'actions sont uniques dans tout le flux (ASCII, sans accent) ;
- chaque référence à une colonne est enregistrée (``Flow.use``) pour produire ``fieldsUsed`` du manifeste ;
- les modèles HTML ``flows/templates/N-xx.html`` sont intégrés dans les actions d'envoi (``{{Var}}`` → expression).
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
import uuid
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "provisioning" / "model" / "model.generated.json"
TEMPLATES_DIR = ROOT / "flows" / "templates"

# --------------------------------------------------------------------------------------------
# Constantes de solution
# --------------------------------------------------------------------------------------------
GUID_NAMESPACE = uuid.NAMESPACE_URL
GUID_PREFIX = "urn:hncs-rd:flow:"


def workflow_guid(tech_id: str) -> str:
    """WorkflowId déterministe : uuid5(NAMESPACE_URL, 'urn:hncs-rd:flow:<IdTechnique>')."""
    return str(uuid.uuid5(GUID_NAMESPACE, GUID_PREFIX + tech_id))


ENV_VARS = {
    "hncs_SiteUrl": ("URL du site SharePoint HNCS-R&D (sans barre finale)", "https://contoso.sharepoint.com/sites/HNCS-RD"),
    "hncs_ServiceAccountEmail": ("Adresse du compte de service des flux (rôle FLUX)", "svc-hncs-rd@contoso.com"),
    "hncs_SupportEmail": ("Adresse du support des flux (N-99, N-98)", "support-rd@contoso.com"),
    # Écart signalé : le déclencheur « boîte partagée » exige des valeurs statiques (voir README, divergences)
    "hncs_BoiteRDEmail": ("Boîte partagée R&D surveillée par PA-01b (= Destinataires.BoiteRD)", "rd@contoso.com"),
    "hncs_BoiteRDDossierCandidatures": ("Identifiant du dossier « Candidatures » de la boîte partagée R&D (PA-01b)", "Inbox"),
}


def P_ENV(name: str) -> str:
    return f"parameters('{name} ({name})')"


SITE = P_ENV("hncs_SiteUrl")
SVC = P_ENV("hncs_ServiceAccountEmail")
SUPPORT = P_ENV("hncs_SupportEmail")
TZ = "Romance Standard Time"

CONNECTORS = {
    "shared_sharepointonline": "hncs_sharepoint",
    "shared_office365": "hncs_outlook",
    "shared_teams": "hncs_teams",
    "shared_office365users": "hncs_o365users",
}

RETRY = {"type": "exponential", "count": 4, "interval": "PT10S"}
CHILD_IDS = {"PA-00A", "PA-00B", "PA-00C"}

# --------------------------------------------------------------------------------------------
# Modèle
# --------------------------------------------------------------------------------------------


class Model:
    def __init__(self, path: Path = MODEL_PATH):
        self.data = json.loads(path.read_text(encoding="utf-8"))
        self.objects = {o["name"]: o for o in self.data["objects"]}
        self.enums = self.data["enums"]
        self.transitions = self.data["transitions"]
        self.partition = self.data["partition"]
        self.groups = {g["code"]: g["name"] for g in self.data["groups"]}
        self.role_group = {r: self.groups[c] for r, c in self.data["roleToGroupCode"].items()}
        self.controls = {c["code"]: c for c in self.data["controls"]}
        self.notifications = {n["code"]: n for n in self.data["notifications"]}
        self.flows = {f["id"]: f for f in self.data["flows"]}
        self.params = {p["key"]: p for p in self.data["parameters"]}

    def obj(self, name):
        return self.objects[name]

    def title(self, name):
        return self.objects[name]["title"]

    def columns(self, name):
        o = self.objects[name]
        cols = {c["name"]: c for c in o["columns"]}
        if o.get("titleColumn"):
            tc = dict(o["titleColumn"])
            tc.setdefault("type", "Text")
            tc["required"] = o.get("titleRequired", tc.get("required", False))
            cols["Title"] = tc
        return cols

    def col(self, lst, field):
        cols = self.columns(lst)
        if field not in cols:
            raise KeyError(f"Colonne inconnue {lst}.{field}")
        return cols[field]

    def enum_of(self, lst, field):
        c = self.col(lst, field)
        return self.enums[c["enum"]] if c.get("enum") else None

    def initial_status(self, lst):
        return self.objects[lst]["initialStatus"]

    def is_library(self, lst):
        return self.objects[lst]["kind"] == "library"

    def transitions_of(self, base_codes):
        return [t for t in self.transitions if t["baseCode"] in base_codes]

    def controls_for(self, obj, targets):
        """Codes G_* portés par les transitions de ``obj`` arrivant dans ``targets``."""
        s = set()
        for t in self.transitions:
            if t["object"] == obj and t["to"] in targets:
                s.update(t["controls"])
        return s

    def control_rule(self, code):
        return re.sub(r"[`*]", "", self.controls[code]["rule"])


MODEL = Model()
SYSTEM_FIELDS = {"ID", "Created", "Modified", "Author", "Editor"}

# --------------------------------------------------------------------------------------------
# Expressions
# --------------------------------------------------------------------------------------------


def q(s: str) -> str:
    """Littéral chaîne WDL."""
    return "'" + str(s).replace("'", "''") + "'"


def at(e: str) -> str:
    return "@" + e


def ip(e: str) -> str:
    return "@{" + e + "}"


def arr(values) -> str:
    return "createArray(" + ", ".join(q(v) for v in values) + ")"


def odata(s: str) -> str:
    """Littéral OData (apostrophes doublées), à placer dans une chaîne non interprétée."""
    return "'" + s.replace("'", "''") + "'"


def odq(expr: str) -> str:
    """Valeur dynamique dans un filtre OData : apostrophes doublées."""
    return "'@{replace(string(" + expr + "), '''', '''''')}'"


def dloc(e: str) -> str:
    """Date (yyyy-MM-dd) en heure de Paris, chaîne vide si absente."""
    return f"if(empty({e}), '', formatDateTime(convertTimeZone({e}, 'UTC', '{TZ}'), 'yyyy-MM-dd'))"


def dtloc(e: str) -> str:
    """Date et heure lisibles (dd/MM/yyyy HH:mm) en heure de Paris."""
    return f"if(empty({e}), '', formatDateTime(convertTimeZone({e}, 'UTC', '{TZ}'), 'dd/MM/yyyy HH:mm'))"


def dfr(e: str) -> str:
    """Date seule lisible (dd/MM/yyyy) à partir d'une date yyyy-MM-dd ou ISO."""
    return f"if(empty({e}), '', formatDateTime(convertTimeZone({e}, 'UTC', '{TZ}'), 'dd/MM/yyyy'))"


def truthy(e: str) -> str:
    return f"equals(toLower(string(coalesce({e}, false))), 'true')"


TODAY = "outputs('Aujourdhui')"
NOW = "utcNow()"


def item_link(lst: str, id_expr: str) -> str:
    return f"concat({SITE}, '/Lists/{lst}/DispForm.aspx?ID=', string({id_expr}))"


def list_link(lst: str) -> str:
    if MODEL.is_library(lst):
        return f"concat({SITE}, '/{lst}')"
    return f"concat({SITE}, '/Lists/{lst}')"


def lib_url(lib: str, rel_expr: str) -> str:
    return f"concat({SITE}, '/{lib}/', {rel_expr})"


def lib_srv(lib: str, rel_expr: str) -> str:
    return f"concat(uriPath({SITE}), '/{lib}/', {rel_expr})"


def list_srv(lst: str) -> str:
    return f"concat(uriPath({SITE}), '/Lists/{lst}')"


def run_url() -> str:
    return ("concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], "
            "'/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])")


def sanitize_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9_]+", "_", s).strip("_")
    return s or "Action"


# --------------------------------------------------------------------------------------------
# Modèles de notifications
# --------------------------------------------------------------------------------------------
_TEMPLATE_CACHE: dict = {}


def template(code: str):
    if code not in _TEMPLATE_CACHE:
        raw = (TEMPLATES_DIR / f"{code}.html").read_text(encoding="utf-8")
        body = re.sub(r"<!--.*?-->\s*", "", raw, flags=re.S).strip()
        m = re.search(r"<title>(.*?)</title>", body, flags=re.S)
        subject = html.unescape(m.group(1).strip()) if m else f"[HNCS-R&D][{code}]"
        variables = set(re.findall(r"\{\{(\w+)\}\}", body))
        _TEMPLATE_CACHE[code] = (subject, body, variables)
    return _TEMPLATE_CACHE[code]


def render(text: str, values: dict) -> str:
    def rep(m):
        return ip(values[m.group(1)])
    return re.sub(r"\{\{(\w+)\}\}", rep, text)


# --------------------------------------------------------------------------------------------
# Flux et séquences
# --------------------------------------------------------------------------------------------


class Flow:
    def __init__(self, tech_id, code, label, lot, ftype, trigger_kind, trigger_list=None, recurrence=None,
                 targets=(), enabled=True, objet=None):
        self.id = tech_id
        self.code = code
        # Nom affiché : « HNCS-RD PA-xx : <Libellé du catalogue> » (§ 2.2), suffixe de liste éventuel conservé
        m = re.search(r"\s(\([^()]*\))$", label)
        if code in MODEL.flows:
            label = f"HNCS-RD {code} : {MODEL.flows[code]['name']}" + (f" {m.group(1)}" if m else "")
        self.label = label
        self.lot = lot
        self.type = ftype
        self.trigger_kind = trigger_kind
        self.trigger_list = trigger_list
        self.recurrence = recurrence
        self.targets = list(targets)
        self.enabled = enabled
        self.objet = objet
        self.names: set = set()
        self.fields = defaultdict(set)
        self.reads: set = set()
        self.writes: set = set()
        self.statuses = defaultdict(set)
        self.transitions: set = set()
        self.notifs: set = set()
        self.children: set = set()
        self.connections: set = set()
        self.preludes: dict = {}          # nom -> (ordre, action)
        self.trigger = None
        self.trigger_name = None
        self.doc = {}
        self.top: dict = {}             # actions de premier niveau
        self.params_needed = True

    # ---- identifiants -------------------------------------------------------------------
    @property
    def display(self):
        return self.label

    def n(self, base: str) -> str:
        base = sanitize_name(base)
        name, i = base, 2
        while name in self.names:
            name = f"{base}_{i}"
            i += 1
        self.names.add(name)
        return name

    # ---- traçabilité --------------------------------------------------------------------
    def use(self, lst, *fields):
        for f in fields:
            if f not in SYSTEM_FIELDS:
                MODEL.col(lst, f)  # lève une erreur si la colonne n'existe pas
            self.fields[lst].add(f)

    def read(self, lst, *fields):
        self.reads.add(lst)
        self.use(lst, *fields)

    def write(self, lst, *fields):
        self.writes.add(lst)
        self.use(lst, *fields)

    def status(self, lst, *statuses):
        enum = MODEL.enum_of(lst, "Statut")
        for s in statuses:
            if s not in enum:
                raise ValueError(f"Statut inconnu {lst}: {s}")
            self.statuses[lst].add(s)

    def trans(self, *codes):
        known = {t["baseCode"] for t in MODEL.transitions}
        for c in codes:
            if c not in known:
                raise ValueError(f"Transition inconnue {c}")
            self.transitions.add(c)

    # ---- accès champs -------------------------------------------------------------------
    def f(self, lst, src, field, sub=None):
        """Expression lisant ``field`` dans l'objet ``src`` (sortie SharePoint)."""
        self.use(lst, field)
        e = f"{src}?['{field}']"
        if sub:
            e += f"?['{sub}']"
        return e

    # ---- ressources partagées (préambule) -----------------------------------------------
    def prelude(self, name, order, action):
        if name not in self.preludes:
            self.names.add(name)
            self.preludes[name] = (order, action)
        return name

    def group_emails(self, gcode):
        """Adresses (séparées par ;) des membres d'un groupe SharePoint (résolution REST, H-14)."""
        gname = MODEL.groups[gcode]
        http = f"Membres_{gcode}"
        sel = f"Emails_{gcode}"
        self.prelude(http, 10, sp_http_action(self, "GET",
                     f"_api/web/sitegroups/getbyname('{gname}')/users?$select=Email"))
        self.prelude(sel, 11, {"type": "Select", "inputs": {
            "from": at(f"body('{http}')?['value']"),
            "select": at("toLower(coalesce(item()?['Email'], ''))")}})
        return f"join(body('{sel}'), ';')"

    def group_id(self, gcode):
        gname = MODEL.groups[gcode]
        name = f"Groupe_{gcode}"
        self.prelude(name, 20, sp_http_action(self, "GET", f"_api/web/sitegroups/getbyname('{gname}')?$select=Id"))
        return f"body('{name}')?['Id']"

    def roledef(self, level):
        name = f"Niveau_{level}"
        if level == "CSS":
            uri = f"_api/web/roledefinitions/getbyname('{MODEL.data['permissionLevels']['CSS']['name']}')?$select=Id"
        elif level == "R":
            uri = "_api/web/roledefinitions/getbytype(2)?$select=Id"
        elif level == "FC":
            uri = "_api/web/roledefinitions/getbytype(5)?$select=Id"
        else:
            raise ValueError(level)
        self.prelude(name, 30, sp_http_action(self, "GET", uri))
        return f"body('{name}')?['Id']"


class Seq:
    def __init__(self, flow: Flow):
        self.flow = flow
        self.actions: dict = {}
        self.last = None

    def add(self, base, action, after=None, name=None):
        nm = name or self.flow.n(base)
        if after is None:
            prev = self.actions.get(self.last, {}) if self.last else {}
            if self.last and "_next_after" in prev:
                action["runAfter"] = prev.pop("_next_after")
            else:
                action["runAfter"] = {self.last: ["Succeeded"]} if self.last else {}
        else:
            action["runAfter"] = after
        self.actions[nm] = action
        self.last = nm
        return nm

    def sub(self):
        return Seq(self.flow)


# --------------------------------------------------------------------------------------------
# Actions élémentaires
# --------------------------------------------------------------------------------------------


def conn_action(flow, api, op, params):
    flow.connections.add(api)
    return {"type": "OpenApiConnection", "inputs": {
        "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{api}", "connectionName": api, "operationId": op},
        "parameters": params, "authentication": "@parameters('$authentication')", "retryPolicy": dict(RETRY)}}


NOMETA = {"Accept": "application/json;odata=nometadata", "Content-Type": "application/json;odata=nometadata"}


def sp_http_action(flow, method, uri, body=None, headers=None):
    params = {"dataset": at(SITE), "parameters/method": method, "parameters/uri": uri,
              "parameters/headers": headers or dict(NOMETA)}
    if body is not None:
        params["parameters/body"] = body
    return conn_action(flow, "shared_sharepointonline", "HttpRequest", params)


def sp_http(seq, base, method, uri, body=None, headers=None, after=None):
    return seq.add(base, sp_http_action(seq.flow, method, uri, body, headers), after=after)


def compose(seq, base, value, after=None):
    return seq.add(base, {"type": "Compose", "inputs": value}, after=after)


def select(seq, base, frm, sel, after=None):
    return seq.add(base, {"type": "Select", "inputs": {"from": at(frm), "select": sel}}, after=after)


def filt(seq, base, frm, where, after=None):
    return seq.add(base, {"type": "Query", "inputs": {"from": at(frm), "where": at(where)}}, after=after)


def html_table(seq, base, frm, columns, after=None):
    return seq.add(base, {"type": "Table", "inputs": {
        "from": at(frm), "format": "HTML",
        "columns": [{"header": h, "value": at(v)} for h, v in columns]}}, after=after)


def terminate(seq, base, status="Succeeded", message=None, after=None):
    inp = {"runStatus": status}
    if status == "Failed":
        inp["runError"] = {"code": "HNCS_ECHEC", "message": message or "Échec du flux"}
    return seq.add(base, {"type": "Terminate", "inputs": inp}, after=after)


def cond(seq, base, expr, yes_fn=None, no_fn=None, after=None):
    """Condition ; ``yes_fn``/``no_fn`` reçoivent une sous-séquence."""
    ys, ns = seq.sub(), seq.sub()
    action = {"type": "If", "expression": at(expr), "actions": {}, "else": {"actions": {}}}
    name = seq.add(base, action, after=after)
    if yes_fn:
        yes_fn(ys)
    if no_fn:
        no_fn(ns)
    action["actions"] = ys.actions
    action["else"]["actions"] = ns.actions
    return name


def switch(seq, base, expr, cases: dict, default_fn=None, after=None):
    action = {"type": "Switch", "expression": at(expr), "cases": {}, "default": {"actions": {}}}
    name = seq.add(base, action, after=after)
    for i, (value, fn) in enumerate(cases.items(), 1):
        s = seq.sub()
        fn(s)
        action["cases"][f"Cas_{i}_{sanitize_name(value)}"] = {"case": value, "actions": s.actions}
    if default_fn:
        s = seq.sub()
        default_fn(s)
        action["default"]["actions"] = s.actions
    return name


def foreach(seq, base, frm, body_fn, after=None, concurrency=1):
    action = {"type": "Foreach", "foreach": at(frm), "actions": {},
              "runtimeConfiguration": {"concurrency": {"repetitions": concurrency}}}
    name = seq.add(base, action, after=after)
    s = seq.sub()
    body_fn(s, name)
    action["actions"] = s.actions
    return name


def scope(seq, base, body_fn, after=None):
    action = {"type": "Scope", "actions": {}}
    name = seq.add(base, action, after=after)
    s = seq.sub()
    body_fn(s)
    action["actions"] = s.actions
    return name


def call_child(seq, base, child_id, body, after=None):
    seq.flow.children.add(child_id)
    return seq.add(base, {"type": "Workflow", "inputs": {
        "host": {"workflowReferenceName": workflow_guid(child_id)}, "body": body}}, after=after)


# ---- SharePoint ------------------------------------------------------------------------------


def _wkey(lst, field):
    t = MODEL.col(lst, field)["type"] if field not in SYSTEM_FIELDS else "Text"
    if t == "Choice":
        return f"item/{field}/Value"
    if t == "Lookup":
        return f"item/{field}/Id"
    if t == "User":
        return f"item/{field}/Claims"
    if t in ("MultiChoice", "LookupMulti", "UserMulti"):
        return f"item/{field}"
    return f"item/{field}"


def _src_value(flow, lst, src, field):
    t = MODEL.col(lst, field)["type"]
    if t == "Choice":
        return ip(flow.f(lst, src, field, "Value"))
    if t == "Lookup":
        return at(flow.f(lst, src, field, "Id"))
    if t == "User":
        return ip(flow.f(lst, src, field, "Claims"))
    return at(flow.f(lst, src, field))


def _item_params(flow, lst, values: dict, src=None, require_all=False):
    params = {}
    cols = MODEL.columns(lst)
    for field, value in values.items():
        params[_wkey(lst, field)] = value
    missing = [c for c, d in cols.items() if d.get("required") and c not in values]
    if missing:
        if require_all and src is None:
            raise ValueError(f"{flow.id} : création {lst} sans colonnes obligatoires {missing}")
        if src is not None:
            for c in missing:
                params[_wkey(lst, c)] = _src_value(flow, lst, src, c)
    flow.write(lst, *values.keys())
    if "Statut" in values:
        v = values["Statut"]
        if not v.startswith("@"):
            flow.status(lst, v)
    return params


def get_items(seq, base, lst, filter_=None, fields=(), top=5000, order=None, after=None):
    flow = seq.flow
    flow.read(lst, *fields)
    params = {"dataset": at(SITE), "table": MODEL.title(lst)}
    if filter_:
        params["$filter"] = filter_
    if order:
        params["$orderby"] = order
    params["$top"] = top
    op = "GetFileItems" if MODEL.is_library(lst) else "GetItems"
    return seq.add(base, conn_action(flow, "shared_sharepointonline", op, params), after=after)


def get_item(seq, base, lst, id_expr, after=None):
    flow = seq.flow
    flow.read(lst)
    op = "GetFileItem" if MODEL.is_library(lst) else "GetItem"
    return seq.add(base, conn_action(flow, "shared_sharepointonline", op, {
        "dataset": at(SITE), "table": MODEL.title(lst), "id": at(id_expr)}), after=after)


def patch_item(seq, base, lst, id_expr, values: dict, src, after=None):
    """Mise à jour : les colonnes obligatoires non modifiées sont reprises de ``src`` (lecture courante)."""
    flow = seq.flow
    params = {"dataset": at(SITE), "table": MODEL.title(lst), "id": at(id_expr)}
    params.update(_item_params(flow, lst, values, src=src))
    op = "PatchFileItem" if MODEL.is_library(lst) else "PatchItem"
    return seq.add(base, conn_action(flow, "shared_sharepointonline", op, params), after=after)


def post_item(seq, base, lst, values: dict, after=None):
    flow = seq.flow
    params = {"dataset": at(SITE), "table": MODEL.title(lst)}
    params.update(_item_params(flow, lst, values, require_all=True))
    return seq.add(base, conn_action(flow, "shared_sharepointonline", "PostItem", params), after=after)


def item_changes(seq, base, lst, id_expr, after=None, since=None):
    flow = seq.flow
    flow.read(lst)
    return seq.add(base, conn_action(flow, "shared_sharepointonline", "GetItemChanges", {
        "dataset": at(SITE), "table": MODEL.title(lst), "id": at(id_expr),
        "since": ip(since or "triggerOutputs()?['body/{TriggerWindowStartToken}']"), "includeDrafts": False}), after=after)


def create_folder(seq, base, lib, rel_expr, after=None):
    flow = seq.flow
    flow.write(lib)
    return seq.add(base, conn_action(flow, "shared_sharepointonline", "CreateNewFolder", {
        "dataset": at(SITE), "table": MODEL.title(lib), "parameters/path": ip(rel_expr)}), after=after)


# ---- Messagerie ------------------------------------------------------------------------------


def send_mail(seq, base, to_expr, subject, body, mailbox_expr, after=None):
    """Envoi depuis la boîte partagée R&D. Jamais de pièce jointe (spec § 7.5)."""
    return seq.add(base, conn_action(seq.flow, "shared_office365", "SharedMailboxSendEmailV2", {
        "body/MailboxAddress": ip(mailbox_expr), "body/To": ip(to_expr),
        "body/Subject": subject, "body/Body": body, "body/Importance": "Normal"}), after=after)


def teams_chat(seq, base, recipient_expr, message, after=None):
    return seq.add(base, conn_action(seq.flow, "shared_teams", "PostMessageToConversation", {
        "poster": "Flow bot", "location": "Chat with Flow bot",
        "body/recipient": ip(recipient_expr), "body/messageBody": message}), after=after)


def teams_channel(seq, base, group_expr, channel_expr, message, after=None):
    return seq.add(base, conn_action(seq.flow, "shared_teams", "PostMessageToConversation", {
        "poster": "Flow bot", "location": "Channel",
        "body/recipient/groupId": ip(group_expr), "body/recipient/channelId": ip(channel_expr),
        "body/messageBody": message}), after=after)


# --------------------------------------------------------------------------------------------
# Paramètres
# --------------------------------------------------------------------------------------------
PARAM_CATS = ["Destinataires", "Délais", "Fonctionnalités", "Conservation", "Liens", "Gouvernance", "Canaux"]


def P(key, default=None):
    if key not in MODEL.params:
        raise KeyError(f"Paramètre inconnu {key}")
    e = f"outputs('Parametres')?['{key}']"
    if default is not None:
        return f"coalesce({e}, {q(default)})"
    return f"coalesce({e}, '')"


def read_params(seq, categories=None):
    flow = seq.flow
    cats = categories or PARAM_CATS
    filt_ = " or ".join(f"Categorie eq {odata(c)}" for c in cats)
    get_items(seq, "Lire_parametres", "Parametres", filter_=filt_, fields=("Title", "Valeur", "Categorie"), top=500)
    pair = ("concat('\"', replace(item()?['Title'], '\"', ''), '\":', if(empty(item()?['Valeur']), 'null', "
            "concat('\"', replace(replace(item()?['Valeur'], '\\', '\\\\'), '\"', '\\\"'), '\"')))")
    select(seq, "Parametres_cles_valeurs", "body('Lire_parametres')?['value']", at(pair))
    compose(seq, "Parametres", at("json(concat('{', join(body('Parametres_cles_valeurs'), ','), '}'))"))
    compose(seq, "Aujourdhui", at(f"formatDateTime(convertTimeZone(utcNow(), 'UTC', '{TZ}'), 'yyyy-MM-dd')"))


# --------------------------------------------------------------------------------------------
# Journalisation (PA-00C) et notifications
# --------------------------------------------------------------------------------------------


def log(seq, base, niveau, message_expr, liste="", item_id_expr="''", idobj_expr="''", detail_expr="''", after=None):
    flow = seq.flow
    return call_child(seq, base, "PA-00C", {
        "CodeFlux": flow.code, "Niveau": niveau, "Liste": liste,
        "ItemId": ip(f"string(coalesce({item_id_expr}, ''))"), "IdObjet": ip(f"coalesce({idobj_expr}, '')"),
        "Message": ip(message_expr), "DetailErreur": ip(f"string(coalesce({detail_expr}, ''))"),
        "RunUrl": ip(run_url())}, after=after)


def _join_addr(exprs):
    if not exprs:
        return "''"
    return "concat(" + ", ';', ".join(f"coalesce({e}, '')" for e in exprs) + ")"


def notify(seq, code, mail_to, values: dict, teams_to=(), mailbox_expr=None, after=None, log_missing=True):
    """Courriel (et message Teams si le canal le prévoit) selon le modèle ``flows/templates/<code>.html``.

    ``mail_to``/``teams_to`` : expressions donnant des adresses séparées par « ; ».
    """
    flow = seq.flow
    n = MODEL.notifications[code]
    subject_t, body_t, variables = template(code)
    provided = set(values)
    if provided != variables:
        raise ValueError(f"{flow.id} {code} : variables {sorted(variables)} attendues, {sorted(provided)} fournies")
    flow.notifs.add(code)
    tag = code.replace("-", "")
    subject = render(subject_t, values)
    body = render(body_t, values)
    mailbox = mailbox_expr or P("Destinataires.BoiteRD")
    sel = select(seq, f"Dest_{tag}", f"split({_join_addr(list(mail_to))}, ';')", at("toLower(trim(item()))"), after=after)
    ok = filt(seq, f"DestOK_{tag}", f"body('{sel}')", "not(empty(item()))")
    to = f"join(union(body('{ok}'), body('{ok}')), ';')"
    want_teams = "Teams" in n["channel"] and teams_to

    def yes(s):
        send_mail(s, f"Envoyer_{tag}", to, subject, body, mailbox)

    def no(s):
        if log_missing:
            log(s, f"Sans_destinataire_{tag}", "Avertissement", q(f"{code} : aucun destinataire résolu, notification non envoyée"))

    last = cond(seq, f"Si_destinataires_{tag}", f"greater(length(body('{ok}')), 0)", yes, no)
    if want_teams:
        tsel = filt(seq, f"TeamsDest_{tag}", f"split({_join_addr(list(teams_to))}, ';')", "not(empty(trim(item())))")

        def tbody(sss, loop):
            link = values.get("Lien")
            msg = f"<p><strong>{subject}</strong></p>" + (f"<p><a href=\"{ip(link)}\">Ouvrir dans SharePoint</a></p>" if link else "")
            teams_chat(sss, f"Teams_{tag}", f"trim(items('{loop}'))", msg)
        tc = cond(seq, f"Si_teams_{tag}",
                  f"and(equals({P('Fonction.NotificationsTeams', 'Non')}, 'Oui'), greater(length(body('{tsel}')), 0))",
                  lambda y: foreach(y, f"Pour_teams_{tag}", f"union(body('{tsel}'), body('{tsel}'))", tbody))
        last = log(seq, f"Teams_echec_{tag}", "Avertissement", q(f"{code} : échec de l'envoi Teams (le courriel est parti)"),
                   after={tc: ["Failed", "TimedOut"]})
        # l'action suivante de la séquence s'exécute que Teams ait réussi ou non
        seq.actions[last]["_next_after"] = {last: ["Succeeded", "Skipped"]}
    return last


# --------------------------------------------------------------------------------------------
# Transitions (PA-00A / PA-00B)
# --------------------------------------------------------------------------------------------


def verify(seq, base, objet, avant_expr, apres_expr, acteur_expr, auteur_expr="''", valideur_expr="''", after=None):
    return call_child(seq, base, "PA-00A", {
        "Objet": objet, "StatutAvant": ip(avant_expr), "StatutApres": ip(apres_expr),
        "ActeurEmail": ip(acteur_expr), "ItemAuteurEmail": ip(f"coalesce({auteur_expr}, '')"),
        "ItemValideurEmail": ip(f"coalesce({valideur_expr}, '')")}, after=after)


def historize(seq, base, liste, item_id_expr, idobj_expr, objet, avant_expr, apres_expr, accepte: bool | str,
              code_expr, acteur_expr, origine, motif_expr="''", after=None):
    acc = at("true") if accepte is True else at("false") if accepte is False else at(accepte)
    return call_child(seq, base, "PA-00B", {
        "Liste": liste, "ItemId": at(f"int({item_id_expr})"), "IdObjet": ip(idobj_expr), "Objet": objet,
        "StatutAvant": ip(avant_expr), "StatutApres": ip(apres_expr), "Accepte": acc,
        "CodeTransition": ip(f"coalesce({code_expr}, '')"), "ActeurEmail": ip(acteur_expr), "Origine": origine,
        "Motif": ip(f"coalesce({motif_expr}, '')"), "RunId": ip("workflow()?['run']?['name']")}, after=after)


def autorise(v):
    return f"equals(toLower(string(coalesce(body('{v}')?['Autorise'], false))), 'true')"


def eval_controls(seq, v, known: dict, tag):
    """Évalue les contrôles ``G_*`` renvoyés par PA-00A.

    ``known`` : code -> (expression booléenne « satisfait », expression du message d'échec).
    Un code renvoyé mais inconnu du flux est considéré comme non satisfait (fail-safe).
    Retourne (expression « tous satisfaits », expression du motif).
    """
    ctl = compose(seq, f"Controles_{tag}", at(f"split(replace(coalesce(body('{v}')?['Controles'], ''), ' ', ''), ';')"))
    inconnus = filt(seq, f"Controles_inconnus_{tag}", f"outputs('{ctl}')",
                    f"and(not(empty(item())), not(contains({arr(sorted(known)) if known else 'createArray()'}, item())))")
    parts = [f"if(and(contains(outputs('{ctl}'), {q(c)}), not({ok})), {msg}, '')" for c, (ok, msg) in sorted(known.items())]
    frm = "createArray(" + ", ".join(parts) + ")" if parts else "createArray()"
    echecs = filt(seq, f"Controles_echec_{tag}", frm, "not(empty(item()))")
    ok_all = f"and(empty(body('{echecs}')), empty(body('{inconnus}')))"
    motif = (f"concat('Contrôle(s) non satisfait(s) : ', join(union(body('{echecs}'), "
             f"body('{inconnus}')), ' ; '))")
    return ok_all, motif


def ctl_msg(code, detail_expr=None):
    rule = MODEL.control_rule(code)
    if detail_expr:
        return f"concat({q(code + ' : ')}, {detail_expr})"
    return q(f"{code} ({rule})")


def tech_error_check(seq, v, liste, id_expr, idobj_expr):
    cond(seq, f"Si_erreur_controle_{v}", f"equals(coalesce(body('{v}')?['Motif'], ''), 'Erreur technique de contrôle')",
         lambda s: log(s, f"Journaliser_erreur_controle_{v}", "Erreur",
                       q("PA-00A : erreur technique de contrôle, transition refusée par sécurité"),
                       liste, id_expr, idobj_expr))


def flux_transition(seq, tag, objet, liste, item_id_expr, idobj_expr, avant_expr, to_status, base_code,
                    controls_fn=None, src=None, extra_values=None, after_fn=None, after=None):
    """Transition exécutée par le compte de service (rôle FLUX) en conséquence d'une action humaine.

    PA-00A (acteur FLUX) → contrôles G_* → écriture du statut → PA-00B (Origine Flux).
    Refus : rien n'est écrit, avertissement journalisé.
    """
    flow = seq.flow
    flow.trans(base_code)
    flow.status(liste, to_status)
    v = verify(seq, f"Verifier_{tag}", objet, avant_expr, q(to_status), SVC, after=after)
    known = controls_fn(seq, tag) if controls_fn else {}
    ok_all, motif = eval_controls(seq, v, known, tag)

    def yes(s):
        vals = {"Statut": to_status}
        vals.update(extra_values or {})
        patch_item(s, f"Statut_{tag}", liste, item_id_expr, vals, src)
        historize(s, f"Historiser_{tag}", liste, item_id_expr, idobj_expr, objet, avant_expr, q(to_status), True,
                  f"body('{v}')?['CodeTransition']", SVC, "Flux")
        if after_fn:
            after_fn(s)

    def no(s):
        log(s, f"Transition_non_appliquee_{tag}", "Avertissement",
            f"concat({q(base_code + ' (FLUX) non appliquée : ')}, if({autorise(v)}, {motif}, coalesce(body('{v}')?['Motif'], '')))",
            liste, item_id_expr, idobj_expr)

    return cond(seq, f"Si_{tag}_autorisee", f"and({autorise(v)}, {ok_all})", yes, no)


# --------------------------------------------------------------------------------------------
# Identifiants, dossiers, permissions
# --------------------------------------------------------------------------------------------


def idhncs_expr(lst, src, flow):
    prefix = MODEL.obj(lst)["prefix"]
    flow.use(lst, "ID", "Created")
    return (f"concat('{prefix}-', formatDateTime(convertTimeZone({src}?['Created'], 'UTC', '{TZ}'), 'yyyy'), '-', "
            f"formatNumber(int({src}?['ID']), '0000'))")


def ensure_idhncs(seq, lst, src, id_expr, tag):
    """Compose ``IdObjet_<tag>`` (identifiant courant ou calculé) et l'écrit s'il est vide. Retourne l'expression."""
    flow = seq.flow
    flow.use(lst, "IdHNCS")
    calc = idhncs_expr(lst, src, flow)
    c = compose(seq, f"IdObjet_{tag}", at(f"if(empty({src}?['IdHNCS']), {calc}, {src}?['IdHNCS'])"))
    cond(seq, f"Si_IdHNCS_vide_{tag}", f"empty({src}?['IdHNCS'])",
         lambda s: patch_item(s, f"Ecrire_IdHNCS_{tag}", lst, id_expr, {"IdHNCS": ip(f"outputs('{c}')")}, src))
    return f"outputs('{c}')"


def create_with_id(seq, base, lst, values):
    """Crée un élément puis renseigne son ``IdHNCS`` (les écritures du compte de service ne déclenchent rien)."""
    p = post_item(seq, base, lst, values)
    flow = seq.flow
    calc = idhncs_expr(lst, f"body('{p}')", flow)
    patch_item(seq, f"IdHNCS_{base}", lst, f"body('{p}')?['ID']", {"IdHNCS": ip(calc)}, f"body('{p}')")
    return p, calc.replace(f"body('{p}')", f"body('{p}')")


def ensure_folder(seq, tag, lib, rel_expr):
    """Crée le dossier ``lib/rel`` s'il n'existe pas (idempotent). Retourne l'URL absolue."""
    srv = lib_srv(lib, rel_expr)
    g = sp_http(seq, f"Dossier_existe_{tag}", "GET", ip(f"concat('_api/web/GetFolderByServerRelativeUrl(''', {srv}, ''')?$select=Exists')"))
    cond(seq, f"Si_dossier_absent_{tag}", f"not(equals(string(coalesce(body('{g}')?['Exists'], false)), 'True'))",
         lambda s: create_folder(s, f"Creer_dossier_{tag}", lib, rel_expr),
         after={g: ["Succeeded", "Failed"]})
    return lib_url(lib, rel_expr)


def _grant(seq, tag, target_uri_prefix, grants):
    """``grants`` : liste de (type, valeur, niveau) ; type ∈ {group, user}."""
    flow = seq.flow
    for i, (kind, who, level) in enumerate(grants, 1):
        rd = flow.roledef(level)
        if kind == "group":
            pid = flow.group_id(who)
            sp_http(seq, f"Attribuer_{tag}_{who}_{level}", "POST",
                    ip(f"concat({target_uri_prefix}, '/roleassignments/addroleassignment(principalid=', string({pid}), ',roledefid=', string({rd}), ')')"))
        else:
            def yes(s, who=who, rd=rd, i=i, level=level):
                eu = sp_http(s, f"Utilisateur_{tag}_{i}", "POST", "_api/web/ensureuser",
                             body=ip(f"concat('{{\"logonName\":\"i:0#.f|membership|', toLower({who}), '\"}}')"))
                sp_http(s, f"Attribuer_{tag}_U{i}_{level}", "POST",
                        ip(f"concat({target_uri_prefix}, '/roleassignments/addroleassignment(principalid=', string(body('{eu}')?['Id']), ',roledefid=', string({rd}), ')')"))
            cond(seq, f"Si_utilisateur_{tag}_{i}", f"not(empty({who}))", yes)


def grant_folder(seq, tag, lib, rel_expr, grants, copy=True):
    """Rompt l'héritage du dossier (copie ou non des attributions) puis ajoute les attributions (idempotent)."""
    srv = lib_srv(lib, rel_expr)
    prefix = f"concat('_api/web/GetFolderByServerRelativeUrl(''', {srv}, ''')/ListItemAllFields')"
    sp_http(seq, f"Rompre_heritage_{tag}", "POST",
            ip(f"concat({prefix}, '/breakroleinheritance(copyRoleAssignments={'true' if copy else 'false'},clearSubscopes=true)')"))
    _grant(seq, tag, prefix, grants)


def obj_srv(lst: str) -> str:
    """URL relative au serveur d'une liste (``/Lists/<Nom>``) ou d'une bibliothèque (``/<Nom>``)."""
    if MODEL.is_library(lst):
        return f"concat(uriPath({SITE}), '/{lst}')"
    return list_srv(lst)


def fingerprint(seq, base, values: dict):
    """Empreinte canonique (P-09) : objet à valeurs texte sérialisé. Retourne (expression texte, nom du compose)."""
    c = compose(seq, base, {k: ip(f"string(coalesce({v}, ''))") for k, v in values.items()})
    return f"string(outputs('{c}'))", c


def grant_item(seq, tag, lst, id_expr, grants, copy=True):
    srv = obj_srv(lst)
    # alias de paramètre @l : l'URL de la liste (nom interne ASCII)
    prefix = f"concat('_api/web/GetList(''', {srv}, ''')/items(', string({id_expr}), ')')"
    sp_http(seq, f"Rompre_heritage_{tag}", "POST",
            ip(f"concat({prefix}, '/breakroleinheritance(copyRoleAssignments={'true' if copy else 'false'},clearSubscopes=true)')"))
    _grant(seq, tag, prefix, grants)


def list_exists(seq, tag, lst):
    """Vérifie qu'une liste (lot ultérieur) est déployée. Retourne l'expression booléenne."""
    g = sp_http(seq, f"Liste_deployee_{tag}", "GET", ip(f"concat('_api/web/GetList(''', {list_srv(lst)}, ''')?$select=Id')"))
    c = compose(seq, f"Liste_presente_{tag}", at(f"not(empty(body('{g}')?['Id']))"), after={g: ["Succeeded", "Failed"]})
    return f"equals(string(outputs('{c}')), 'True')"


# --------------------------------------------------------------------------------------------
# Assemblage
# --------------------------------------------------------------------------------------------


def env_parameters(names=None):
    names = names or list(ENV_VARS)
    params = {"$connections": {"defaultValue": {}, "type": "Object"},
              "$authentication": {"defaultValue": {}, "type": "SecureObject"}}
    for n in names:
        desc, default = ENV_VARS[n]
        params[f"{n} ({n})"] = {"defaultValue": default, "type": "String",
                                "metadata": {"schemaName": n, "description": desc}}
    return params


def _strip_internal(node):
    if isinstance(node, dict):
        for k in [k for k in node if k.startswith("_next")]:
            del node[k]
        for v in node.values():
            _strip_internal(v)
    elif isinstance(node, list):
        for v in node:
            _strip_internal(v)


def assemble(flow: Flow):
    _strip_internal(flow.top)
    text = json.dumps({"t": flow.trigger, "a": flow.top}, ensure_ascii=False)
    used_env = [n for n in ENV_VARS if f"parameters('{n} ({n})')" in text]
    if "hncs_SiteUrl" not in used_env:
        used_env.insert(0, "hncs_SiteUrl")
    conn_refs = {api: {"runtimeSource": "embedded", "connection": {"connectionReferenceLogicalName": CONNECTORS[api]},
                       "api": {"name": api}} for api in sorted(flow.connections)}
    definition = {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": env_parameters(used_env),
        "triggers": {flow.trigger_name: flow.trigger},
        "actions": flow.top,
        "outputs": {},
    }
    return {"properties": {"connectionReferences": conn_refs, "definition": definition, "templateName": ""},
            "schemaVersion": "1.0.0.0"}


def with_preludes(flow: Flow, principal_actions: dict, first_after: str):
    """Insère les actions de préambule (groupes, niveaux) après ``first_after`` dans la portée Principal."""
    if not flow.preludes:
        return principal_actions
    ordered = sorted(flow.preludes.items(), key=lambda kv: (kv[1][0], kv[0]))
    # successeurs directs de first_after
    succ = [n for n, a in principal_actions.items() if first_after in a.get("runAfter", {})]
    prev = first_after
    out = {}
    for name, (_, action) in ordered:
        a = json.loads(json.dumps(action))
        a["runAfter"] = {prev: ["Succeeded"]}
        out[name] = a
        prev = name
    for n in succ:
        ra = principal_actions[n]["runAfter"]
        ra[prev] = ra.pop(first_after)
    merged = {}
    for n, a in principal_actions.items():
        merged[n] = a
        if n == first_after:
            merged.update(out)
    return merged


def standard_shell(flow: Flow, body_fn, liste="", item_id_expr="''", idobj_expr="''", variables=()):
    """Socle § 8.1 : Principal → Erreur (PA-00C puis échec) → Terminer.

    ``variables`` : [(nom, type, valeur)] initialisées au premier niveau (obligatoire en Power Automate).
    """
    top = Seq(flow)
    for vname, vtype, vval in variables:
        top.add(f"Initialiser_{vname}", {"type": "InitializeVariable",
                                         "inputs": {"variables": [{"name": vname, "type": vtype, "value": vval}]}})
    pseq = top.sub()
    if flow.params_needed:
        read_params(pseq)
    body_fn(pseq)
    actions = pseq.actions
    if flow.preludes:
        anchor = "Aujourdhui" if "Aujourdhui" in actions else next(iter(actions))
        actions = with_preludes(flow, actions, anchor)
    flow.names.update({"Principal", "Erreur", "Terminer"})
    top.actions["Principal"] = {"type": "Scope", "actions": actions,
                                "runAfter": ({top.last: ["Succeeded"]} if top.last else {})}
    err = Seq(flow)
    det = compose(err, "Detail_erreur", at("string(result('Principal'))"))
    log(err, "Journaliser_erreur", "Erreur", q(f"Échec de l'exécution du flux {flow.id}"), liste,
        item_id_expr, idobj_expr, detail_expr=f"substring(outputs('{det}'), 0, min(length(outputs('{det}')), 8000))")
    terminate(err, "Terminer_en_echec", "Failed", f"Échec du flux {flow.id} : voir le journal des flux",
              after={err.last: ["Succeeded", "Failed", "TimedOut", "Skipped"]})
    top.actions["Erreur"] = {"type": "Scope", "actions": err.actions, "runAfter": {"Principal": ["Failed", "TimedOut"]}}
    top.actions["Terminer"] = {"type": "Terminate", "inputs": {"runStatus": "Succeeded"}, "runAfter": {"Erreur": ["Skipped"]}}
    flow.top = top.actions


# ---- Déclencheurs ---------------------------------------------------------------------------

ANTI_LOOP = ("@not(equals(toLower(triggerOutputs()?['body/Editor/Email']), "
             "toLower(parameters('hncs_ServiceAccountEmail (hncs_ServiceAccountEmail)'))))")


def cond_transition():
    return "@not(equals(coalesce(triggerOutputs()?['body/Statut/Value'], ''), coalesce(triggerOutputs()?['body/StatutPrecedent'], '')))"


def cond_targets(targets):
    return "@contains(" + arr(targets) + ", triggerOutputs()?['body/Statut/Value'])"


def sp_trigger(flow: Flow, lst, op="GetOnUpdatedItems", conditions=()):
    flow.connections.add("shared_sharepointonline")
    flow.read(lst)
    flow.trigger_name = {"GetOnNewItems": "Quand_un_element_est_cree",
                         "GetOnUpdatedItems": "Quand_un_element_est_cree_ou_modifie",
                         "GetOnUpdatedFileItems": "Quand_un_fichier_est_cree_ou_modifie"}[op]
    flow.trigger = {"type": "OpenApiConnection", "recurrence": {"interval": 1, "frequency": "Minute"},
                    "splitOn": "@triggerOutputs()?['body/value']",
                    "inputs": {"host": {"apiId": "/providers/Microsoft.PowerApps/apis/shared_sharepointonline",
                                        "connectionName": "shared_sharepointonline", "operationId": op},
                               "parameters": {"dataset": at(SITE), "table": MODEL.title(lst)},
                               "authentication": "@parameters('$authentication')"},
                    "conditions": [{"expression": c} for c in conditions]}


def recurrence_trigger(flow: Flow, recurrence: dict):
    flow.trigger_name = "Recurrence"
    rec = dict(recurrence)
    rec.setdefault("timeZone", TZ)
    flow.trigger = {"type": "Recurrence", "recurrence": rec}


def child_trigger(flow: Flow, props: dict, required):
    """« Déclencher manuellement un flux » (kind Button) : appelable comme flux enfant."""
    flow.trigger_name = "manual"
    schema = {"type": "object", "properties": {}, "required": list(required)}
    for name, (typ, desc) in props.items():
        hint = {"string": "TEXT", "boolean": "BOOLEAN", "number": "NUMBER"}[typ]
        schema["properties"][name] = {"title": name, "type": typ, "x-ms-dynamically-added": True,
                                      "description": desc, "x-ms-content-hint": hint}
    flow.trigger = {"type": "Request", "kind": "Button", "inputs": {"schema": schema}}


def response(seq, base, body: dict, types: dict, after=None):
    props = {k: {"title": k, "x-ms-dynamically-added": True, "type": types[k]} for k in body}
    return seq.add(base, {"type": "Response", "kind": "PowerApp", "inputs": {
        "statusCode": 200, "body": body, "schema": {"type": "object", "properties": props}}}, after=after)
