# -*- coding: utf-8 -*-
"""Utilitaires partagés des tests hors ligne HNCS-RD (bibliothèque standard uniquement).

- chargement du modèle généré (`provisioning/model/model.generated.json`) ;
- chargement du jeu de test (`testdata/data/*.json`) et des personas ;
- résolution des jetons du jeu de test (`@J+7`, `@J-30T09:00`, `@persona:CLE`, `@site:/…`, `@id:…`, `@empreinte`) ;
- évaluateur du sous-ensemble de formules SharePoint utilisé par les règles `Validation` de la spec.

Ce module est aussi importé par `tests/e2e/reconciliation/reconcilier.py`.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "provisioning" / "model" / "model.generated.json"
TESTDATA_DIR = ROOT / "testdata" / "data"
PERSONAS_SAMPLE = ROOT / "testdata" / "personas.sample.json"

# Listes alimentées uniquement par le provisioning : le jeu de test ne les duplique pas.
SEED_ONLY_LISTS = {"Poles", "ModelesActions", "Parametres", "TransitionsStatuts"}

REL_DATE = re.compile(r"^@J(?:([+-])(\d{1,4}))?(?:T(\d{2}):(\d{2}))?$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?$")
PERSONA_TOKEN = re.compile(r"^@persona:([A-Z][A-Z0-9_]*)$")
SITE_TOKEN = re.compile(r"^@site:/\S*$")
ID_TOKEN = re.compile(r"^@id:(\S+)$")
EMPREINTE_TOKEN = "@empreinte"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_model() -> dict:
    return read_json(MODEL_PATH)


def objects_by_name(model: dict | None = None) -> dict:
    model = model or load_model()
    return {o["name"]: o for o in model["objects"]}


def columns_of(obj: dict) -> dict:
    """Colonnes d'une liste, y compris la colonne Titre (explicite ou implicite)."""
    cols = {c["name"]: c for c in obj["columns"]}
    cols["Title"] = obj["titleColumn"]
    return cols


@lru_cache(maxsize=1)
def load_testdata() -> dict:
    data = {}
    if TESTDATA_DIR.is_dir():
        for p in sorted(TESTDATA_DIR.glob("*.json")):
            data[p.stem] = read_json(p)
    return data


@lru_cache(maxsize=1)
def load_personas() -> dict:
    raw = read_json(PERSONAS_SAMPLE)
    return {k: v for k, v in raw.items() if not k.startswith("$")}


def is_blank(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def resolve_temporal(value, ref: dt.date):
    """Résout une date relative (`@J-3`, `@J+2T14:00`) ou ISO. Renvoie date ou datetime ; None si vide."""
    if is_blank(value):
        return None
    if not isinstance(value, str):
        raise ValueError(f"date attendue sous forme de chaîne : {value!r}")
    m = REL_DATE.match(value)
    if m:
        sign, num, hh, mm = m.groups()
        d = ref + dt.timedelta(days=(int(num) if num else 0) * (-1 if sign == "-" else 1))
        if hh is not None:
            return dt.datetime(d.year, d.month, d.day, int(hh), int(mm))
        return d
    if ISO_DATE.match(value):
        return dt.date.fromisoformat(value)
    if ISO_DATETIME.match(value):
        v = value.replace("Z", "+00:00")
        return dt.datetime.fromisoformat(v).replace(tzinfo=None)
    raise ValueError(f"date non reconnue : {value!r}")


def as_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    return v


def persona_key(value):
    if isinstance(value, str):
        m = PERSONA_TOKEN.match(value)
        if m:
            return m.group(1)
    return None


class Jeu:
    """Jeu de test indexé, valeurs temporelles résolues par rapport à une date de référence."""

    def __init__(self, model=None, data=None, today: dt.date | None = None):
        self.model = model or load_model()
        self.data = data if data is not None else load_testdata()
        self.today = today or dt.date.today()
        self.objs = objects_by_name(self.model)
        self.index: dict[str, tuple[str, dict]] = {}
        for lst, items in self.data.items():
            for it in items:
                if it.get("IdHNCS"):
                    self.index[it["IdHNCS"]] = (lst, it)
        self.seed_ids: dict[str, set] = {}
        for lst, rows in self.model["seeds"].items():
            self.seed_ids[lst] = {r["IdHNCS"] for r in rows if r.get("IdHNCS")}
        self.params = {p["key"]: p["value"] for p in self.model["parameters"]}

    # ---------------------------------------------------------------- accès
    def items(self, lst: str) -> list:
        return self.data.get(lst, [])

    def get(self, idhncs: str):
        hit = self.index.get(idhncs)
        return hit[1] if hit else None

    def list_of(self, idhncs: str):
        hit = self.index.get(idhncs)
        return hit[0] if hit else None

    def col(self, lst: str, name: str):
        return columns_of(self.objs[lst]).get(name)

    def v(self, lst: str, item: dict, name: str):
        """Valeur résolue : dates → date/datetime ; autres types inchangés."""
        raw = item.get(name)
        c = self.col(lst, name)
        if c and c["type"] in ("Date", "DateTime"):
            return resolve_temporal(raw, self.today)
        return raw

    def where(self, lst: str, **eq) -> list:
        out = []
        for it in self.items(lst):
            if all(it.get(k) == val for k, val in eq.items()):
                out.append(it)
        return out

    def status_enum(self, lst: str) -> list:
        e = self.objs[lst]["statusEnum"]
        return self.model["enums"][e] if e else []

    def param_int(self, key: str, default: int) -> int:
        try:
            return int(str(self.params.get(key, "")).split(";")[0])
        except ValueError:
            return default


# --------------------------------------------------------------------------- formules SharePoint

class FormulaError(Exception):
    pass


_TOKEN = re.compile(r"\s*(?:(\[[^\]]+\])|(\"[^\"]*\")|(<>|>=|<=|=|>|<)|([(),])|([A-Za-z_][A-Za-z0-9_]*)|(\d+(?:\.\d+)?))")
SUPPORTED_FUNCTIONS = {"AND", "OR", "IF", "NOT", "ISBLANK"}


def _tokenize(formula: str) -> list:
    s = formula.strip()
    if s.startswith("="):
        s = s[1:]
    pos, out = 0, []
    while pos < len(s):
        if s[pos:].strip() == "":
            break
        m = _TOKEN.match(s, pos)
        if not m:
            raise FormulaError(f"jeton illisible à la position {pos} : {s[pos:pos + 20]!r}")
        field, string, op, punct, ident, num = m.groups()
        if field:
            out.append(("field", field[1:-1]))
        elif string is not None:
            out.append(("str", string[1:-1]))
        elif op:
            out.append(("op", op))
        elif punct:
            out.append(("punct", punct))
        elif ident:
            out.append(("ident", ident.upper()))
        else:
            out.append(("num", float(num)))
        pos = m.end()
    return out


def parse_formula(formula: str):
    """Analyse une formule en arbre (tuples). Lève FormulaError si une construction n'est pas prise en charge."""
    toks = _tokenize(formula)
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else (None, None)

    def take(kind=None, val=None):
        nonlocal pos
        t = peek()
        if t[0] is None or (kind and t[0] != kind) or (val is not None and t[1] != val):
            raise FormulaError(f"attendu {kind} {val}, trouvé {t}")
        pos += 1
        return t

    def primary():
        k, v = peek()
        if k == "ident":
            take()
            if v in ("TRUE", "FALSE") and peek() != ("punct", "("):
                return ("const", v == "TRUE")
            if v not in SUPPORTED_FUNCTIONS:
                raise FormulaError(f"fonction non prise en charge : {v}")
            take("punct", "(")
            args = []
            if peek() != ("punct", ")"):
                args.append(expr())
                while peek() == ("punct", ","):
                    take()
                    args.append(expr())
            take("punct", ")")
            return ("call", v, args)
        if k == "field":
            take()
            return ("field", v)
        if k == "str":
            take()
            return ("const", v)
        if k == "num":
            take()
            return ("const", v)
        if (k, v) == ("punct", "("):
            take()
            e = expr()
            take("punct", ")")
            return e
        raise FormulaError(f"expression attendue, trouvé {peek()}")

    def expr():
        left = primary()
        if peek()[0] == "op":
            op = take()[1]
            right = primary()
            return ("cmp", op, left, right)
        return left

    tree = expr()
    if pos != len(toks):
        raise FormulaError(f"jetons excédentaires : {toks[pos:]}")
    return tree


def formula_fields(tree) -> set:
    if tree[0] == "field":
        return {tree[1]}
    if tree[0] == "call":
        out = set()
        for a in tree[2]:
            out |= formula_fields(a)
        return out
    if tree[0] == "cmp":
        return formula_fields(tree[2]) | formula_fields(tree[3])
    return set()


def _norm(a, b):
    if isinstance(a, dt.datetime) and isinstance(b, dt.date) and not isinstance(b, dt.datetime):
        b = dt.datetime(b.year, b.month, b.day)
    if isinstance(b, dt.datetime) and isinstance(a, dt.date) and not isinstance(a, dt.datetime):
        a = dt.datetime(a.year, a.month, a.day)
    return a, b


def eval_formula(tree, values: dict):
    """Évalue l'arbre. `values` : nom de colonne → valeur résolue (None si vide)."""
    kind = tree[0]
    if kind == "const":
        return tree[1]
    if kind == "field":
        v = values.get(tree[1])
        return None if is_blank(v) else v
    if kind == "cmp":
        op, a, b = tree[1], eval_formula(tree[2], values), eval_formula(tree[3], values)
        if a is None or b is None:
            # Comparaison avec une valeur vide : seule l'égalité de deux vides est vraie.
            return op == "=" and a is None and b is None
        a, b = _norm(a, b)
        return {"=": a == b, "<>": a != b, ">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b}[op]
    if kind == "call":
        fn, args = tree[1], tree[2]
        if fn == "AND":
            return all(bool(eval_formula(x, values)) for x in args)
        if fn == "OR":
            return any(bool(eval_formula(x, values)) for x in args)
        if fn == "NOT":
            return not bool(eval_formula(args[0], values))
        if fn == "ISBLANK":
            return eval_formula(args[0], values) is None
        if fn == "IF":
            cond = bool(eval_formula(args[0], values))
            if cond:
                return eval_formula(args[1], values)
            return eval_formula(args[2], values) if len(args) > 2 else False
    raise FormulaError(f"nœud inconnu {tree!r}")
