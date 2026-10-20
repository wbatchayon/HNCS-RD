# -*- coding: utf-8 -*-
"""Contrat des flux Power Automate (`flows/`) avec la spec § 8. Sauté si `flows/manifest.json` est absent."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest

from hncs_offline import ROOT, columns_of, load_model, objects_by_name

FLOWS = ROOT / "flows"
MANIFEST = FLOWS / "manifest.json"
HAS_MANIFEST = MANIFEST.is_file()
REQUIRED_KEYS = {"id", "code", "displayName", "lot", "type", "trigger", "targetStatuses", "listsRead", "listsWritten",
                 "fieldsUsed", "statusesWritten", "transitions", "notifications", "childFlows", "enabledByDefault"}
SYSTEM_FIELDS = {"ID", "Id", "Title", "Created", "Modified", "Author", "Editor", "FileLeafRef", "FileRef", "FileDirRef",
                 "ContentType", "ContentTypeId", "Attachments", "GUID", "_UIVersionString", "OData__UIVersionString",
                 "FSObjType", "UniqueId", "HasUniqueRoleAssignments", "LinkFilename", "ServerRedirectedEmbedUri"}
ALLOWED_CONNREFS = {"hncs_sharepoint", "hncs_outlook", "hncs_teams", "hncs_o365users"}
PREMIUM_ACTION_TYPES = {"http", "httpwebhook"}
SP_ITEM_TRIGGERS = re.compile(r"^(GetOnNewItems|GetOnUpdatedItems|GetOnChangedItems|GetOnNewFileItems|GetOnUpdatedFileItems|"
                              r"GetOnChangedFileItems)$", re.I)
MAIL_SEND = re.compile(r"(send.*(mail|email)|(mail|email).*send)", re.I)


def family(code: str) -> str:
    """PA-01a → PA-01 ; PA-00B reste PA-00B (les lettres majuscules désignent des flux distincts)."""
    return re.sub(r"[a-z]$", "", code)


def walk(node, path=()):
    if isinstance(node, dict):
        yield path, node
        for k, v in node.items():
            yield from walk(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, path + (i,))


@unittest.skipUnless(HAS_MANIFEST, "flows/manifest.json absent")
class TestManifesteFlux(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_model()
        cls.objs = objects_by_name(cls.m)
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
        cls.by_id = {e["id"]: e for e in cls.manifest} if isinstance(cls.manifest, list) else {}
        cls.model_flows = {f["id"]: f for f in cls.m["flows"]}
        cls.trans_base = {t["baseCode"] for t in cls.m["transitions"]}
        cls.notif = {n["code"]: n for n in cls.m["notifications"]}

    def test_structure(self):
        self.assertIsInstance(self.manifest, list)
        ids = [e.get("id") for e in self.manifest]
        self.assertEqual(len(ids), len(set(ids)), "identifiants techniques en double")
        for e in self.manifest:
            with self.subTest(flux=e.get("id")):
                self.assertEqual(REQUIRED_KEYS - set(e), set(), "clés manquantes")
                self.assertIn(e["code"], self.model_flows, "code PA inconnu")
                self.assertEqual(str(e["lot"]), self.model_flows[e["code"]]["lot"], "lot")

    def test_couverture_des_codes_pa(self):
        codes = {e["code"] for e in self.manifest}
        self.assertEqual(set(self.model_flows) - codes, set(), "flux de la spec sans définition")

    def test_workflows_json_valides(self):
        for e in self.manifest:
            p = FLOWS / "src" / e["id"] / "workflow.json"
            with self.subTest(flux=e["id"]):
                self.assertTrue(p.is_file(), f"{p.relative_to(ROOT)} absent")
                json.loads(p.read_text(encoding="utf-8-sig"))

    def test_tous_les_json_valides(self):
        for p in FLOWS.rglob("*.json"):
            if "dist" in p.relative_to(FLOWS).parts:
                continue
            with self.subTest(fichier=str(p.relative_to(ROOT))):
                json.loads(p.read_text(encoding="utf-8-sig"))

    def test_listes_champs_et_statuts(self):
        enums = self.m["enums"]
        for e in self.manifest:
            with self.subTest(flux=e["id"]):
                lists = set(e["listsRead"]) | set(e["listsWritten"]) | set(e["fieldsUsed"]) | set(e["statusesWritten"])
                if (e.get("trigger") or {}).get("list"):
                    lists.add(e["trigger"]["list"])
                for l in lists:
                    self.assertIn(l, self.objs, f"liste inconnue {l}")
                for l, fields in e["fieldsUsed"].items():
                    cols = set(columns_of(self.objs[l])) | SYSTEM_FIELDS
                    for f in fields:
                        self.assertIn(f.split("/")[0], cols, f"{l}.{f}")
                for l, statuses in e["statusesWritten"].items():
                    enum = enums.get(self.objs[l]["statusEnum"] or "", [])
                    for s in statuses:
                        self.assertIn(s, enum, f"{l} : statut {s}")
                for t in e["transitions"]:
                    self.assertIn(t, self.trans_base, f"transition {t}")
                for n in e["notifications"]:
                    self.assertIn(n, self.notif, f"notification {n}")
                for c in e["childFlows"]:
                    self.assertIn(c, {x["code"] for x in self.manifest} | set(self.by_id), f"flux enfant {c}")

    def test_transitions_couvertes_par_leur_flux_responsable(self):
        uniques = {t["baseCode"]: t for t in self.m["transitions"]}
        for t in uniques.values():
            owners = [e for e in self.manifest if family(e["code"]) == family(t["flow"]) or e["code"] == t["flow"]]
            with self.subTest(transition=t["baseCode"]):
                self.assertTrue(any(t["baseCode"] in e["transitions"] for e in owners),
                                f"{t['baseCode']} non déclarée par {t['flow']}")

    def test_partition_respectee(self):
        """§ 8.2 : un statut cible n'est traité que par le flux de la partition."""
        owner = {(p["list"], s): p["flow"] for p in self.m["partition"] for s in p["targets"]}
        claimed = {}
        for e in self.manifest:
            lst = (e.get("trigger") or {}).get("list")
            for s in e["targetStatuses"] or []:
                with self.subTest(flux=e["id"], statut=s):
                    self.assertIn((lst, s), owner, f"{lst} / {s} hors partition")
                    self.assertEqual(family(owner[(lst, s)]), family(e["code"]), f"{lst} / {s}")
                    prev = claimed.get((lst, s))
                    if prev:
                        self.assertEqual(family(prev), family(e["code"]), f"{lst} / {s} traité par {prev} et {e['code']}")
                    claimed[(lst, s)] = e["code"]
        for key, flow in owner.items():
            with self.subTest(partition=f"{key[0]} / {key[1]}"):
                self.assertIn(key, claimed, f"aucun flux ne déclare ce statut cible ({flow})")

    def test_aucune_decision_humaine_ecrite_par_flux(self):
        """P-01 : un flux n'écrit un statut de décision humaine que via l'exception CAND-T02, ou pour rétablir
        le statut précédent (PA-00B, annulation d'une transition refusée)."""
        decisions = {(d["object"], d["status"]) for d in self.m["humanDecisions"]}
        list_obj = {p["list"]: p["object"] for p in self.m["partition"]}
        allowed = {(t["list"], t["to"]) for t in self.m["transitions"]
                   if "FLUX" in t["actors"] and t["baseCode"] in self.m["fluxExceptions"]}
        for e in self.manifest:
            if e["code"] == "PA-00B":
                continue
            for lst, statuses in e["statusesWritten"].items():
                for s in statuses:
                    if (list_obj.get(lst), s) in decisions:
                        with self.subTest(flux=e["id"], statut=s):
                            self.assertIn((lst, s), allowed, f"{e['id']} écrit la décision humaine {lst} / {s}")

    def test_aucun_declencheur_ne_conditionne_sur_statut_precedent(self):
        """RX-02 (v1.6.0, § 8.1) : sur une liste à statut contrôlé, la condition de déclenchement est uniquement
        l'anti-boucle ; le statut de référence est la dernière transition acceptée de HistoriqueStatuts,
        jamais StatutPrecedent (colonne technique, P-09)."""
        listes_controlees = {p["list"] for p in self.m["partition"]}
        for e in self.manifest:
            if (e.get("trigger") or {}).get("list") not in listes_controlees:
                continue
            p = FLOWS / "src" / e["id"] / "workflow.json"
            if not p.is_file():
                continue
            wf = json.loads(p.read_text(encoding="utf-8-sig"))
            for path, node in walk(wf):
                if "triggers" not in path or "conditions" not in node:
                    continue
                with self.subTest(flux=e["id"], declencheur="/".join(map(str, path))):
                    self.assertNotIn("StatutPrecedent", json.dumps(node["conditions"], ensure_ascii=False),
                                     "condition de déclenchement fondée sur StatutPrecedent")

    def test_pa13_desactive_par_defaut(self):
        for e in self.manifest:
            if e["code"] == "PA-13":
                self.assertFalse(e["enabledByDefault"])

    def test_notifications_couvertes_et_modeles_html(self):
        declared = {n for e in self.manifest for n in e["notifications"]}
        for code in self.notif:
            with self.subTest(notification=code):
                self.assertIn(code, declared, "notification émise par aucun flux")
                self.assertTrue((FLOWS / "templates" / f"{code}.html").is_file(), "modèle HTML absent")

    def test_workflows_securite(self):
        """Pas de pièce jointe aux courriels (P-04), connecteurs standard (P-08), anti-boucle (§ 8.1)."""
        for e in self.manifest:
            p = FLOWS / "src" / e["id"] / "workflow.json"
            if not p.is_file():
                continue
            wf = json.loads(p.read_text(encoding="utf-8-sig"))
            with self.subTest(flux=e["id"]):
                for path, node in walk(wf):
                    t = str(node.get("type", "")).lower()
                    self.assertNotIn(t, PREMIUM_ACTION_TYPES, f"action premium {'/'.join(map(str, path))}")
                    host = (node.get("inputs") or {}).get("host") if isinstance(node.get("inputs"), dict) else None
                    if isinstance(host, dict):
                        ref = host.get("connectionReferenceLogicalName") or host.get("connectionName")
                        if ref:
                            self.assertIn(ref, ALLOWED_CONNREFS | {"shared_sharepointonline", "shared_office365",
                                                                   "shared_teams", "shared_office365users"}, ref)
                        op = str(host.get("operationId", ""))
                        if MAIL_SEND.search(op):
                            self.assertNotIn("attachment", json.dumps(node.get("inputs")).lower(),
                                             f"pièce jointe dans {'/'.join(map(str, path))}")
                        if SP_ITEM_TRIGGERS.match(op) and "triggers" in path:
                            conds = json.dumps(node.get("conditions", []))
                            self.assertIn("ServiceAccountEmail", conds, "condition anti-boucle absente du déclencheur")


@unittest.skipUnless((FLOWS / "build" / "build_solution.py").is_file(), "flows/build/build_solution.py absent")
class TestBuildSolution(unittest.TestCase):
    def test_build_check(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        res = subprocess.run([sys.executable, str(FLOWS / "build" / "build_solution.py"), "--check"], cwd=ROOT,
                             capture_output=True, env=env, timeout=300)
        self.assertEqual(res.returncode, 0, (res.stdout + res.stderr).decode("utf-8", "replace")[-3000:])


@unittest.skipUnless((FLOWS / "tools" / "check_flows.py").is_file(), "flows/tools/check_flows.py absent")
class TestCheckFlows(unittest.TestCase):
    def test_check_flows(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        res = subprocess.run([sys.executable, str(FLOWS / "tools" / "check_flows.py")], cwd=ROOT, capture_output=True,
                             env=env, timeout=300)
        self.assertEqual(res.returncode, 0, (res.stdout + res.stderr).decode("utf-8", "replace")[-3000:])


if __name__ == "__main__":
    unittest.main()
