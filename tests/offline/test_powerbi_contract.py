# -*- coding: utf-8 -*-
"""Contrat du projet Power BI (PBIP / TMDL / PBIR) avec la spec § 9. Sauté si `powerbi/` est absent."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest

from hncs_offline import ROOT, columns_of, load_model, objects_by_name

PBI = ROOT / "powerbi"
SM = PBI / "HNCS-RD.SemanticModel" / "definition"
REPORT = PBI / "HNCS-RD.Report" / "definition"
HAS_SM = (SM / "tables").is_dir()

NAME = r"(?:'((?:[^']|'')+)'|([^\s=']+))"


def tmdl_name(m, i=1):
    quoted, bare = m.group(i), m.group(i + 1)
    return quoted.replace("''", "'") if quoted is not None else bare


def parse_tables() -> dict:
    """table → {'columns': {nom: sourceColumn}, 'measures': set, 'text': str, 'partition': str}"""
    out = {}
    for p in sorted((SM / "tables").glob("*.tmdl")):
        text = p.read_text(encoding="utf-8-sig")
        m = re.search(rf"^table {NAME}\s*$", text, re.M)
        if not m:
            continue
        name = tmdl_name(m)
        cols, current = {}, None
        for line in text.splitlines():
            cm = re.match(rf"^\tcolumn {NAME}(\s*=.*)?$", line)
            if cm:
                current = tmdl_name(cm)
                cols[current] = None
                continue
            if re.match(r"^\t\S", line):
                current = None
            sm = re.match(r"^\t\tsourceColumn:\s*(.+?)\s*$", line)
            if sm and current:
                cols[current] = sm.group(1).strip("'\"")
        measures = {tmdl_name(mm) for mm in re.finditer(rf"^\tmeasure {NAME}\s*=", text, re.M)}
        part = "\n".join(re.findall(r"^\tpartition .*?(?=^\t\S|\Z)", text, re.M | re.S))
        out[name] = {"columns": cols, "measures": measures, "text": text, "partition": part}
    return out


@unittest.skipUnless(HAS_SM, "powerbi/HNCS-RD.SemanticModel/definition/tables absent")
class TestModeleSemantique(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_model()
        cls.objs = objects_by_name(cls.m)
        cls.tables = parse_tables()

    def test_pbip_present(self):
        self.assertTrue((PBI / "HNCS-RD.pbip").is_file())
        json.loads((PBI / "HNCS-RD.pbip").read_text(encoding="utf-8-sig"))

    def test_mesures_de_la_spec_presentes(self):
        all_measures = set().union(*(t["measures"] for t in self.tables.values()))
        missing = [n for n in self.m["powerbi"]["measures"] if n not in all_measures]
        self.assertEqual(missing, [], "mesures § 9.5 absentes du TMDL")

    def test_tables_et_colonnes_de_la_spec(self):
        for t in self.m["powerbi"]["tables"]:
            with self.subTest(table=t["table"]):
                self.assertIn(t["table"], self.tables, "table absente")
                cols = self.tables[t["table"]]["columns"]
                for c in t["columns"]:
                    # Le modèle peut absorber un commentaire de la spec (« Cible — cibles indicatives… ») :
                    # seul le nom avant « — » est comparé (signalé dans le rapport de tests).
                    name = c["name"].split(" — ")[0].strip()
                    self.assertIn(name, cols, f"colonne {name} absente")

    def test_aucune_colonne_perso_ou_confidentielle_importee(self):
        """§ 9.2 / P-04 : ni colonne de table ni sélection M sur une colonne perso/confidentiel (sauf NomAffichage)."""
        for t in self.m["powerbi"]["tables"]:
            src = self.objs.get(t["source"])
            if not src or t["table"] not in self.tables:
                continue
            sensibles = {n for n, c in columns_of(src).items() if c.get("perso") or c.get("confidentiel")}
            if t["table"] == "Alternants":
                sensibles.discard("Title")
            tbl = self.tables[t["table"]]
            with self.subTest(table=t["table"]):
                for col, srccol in tbl["columns"].items():
                    self.assertNotIn(col, sensibles, f"colonne {col}")
                    self.assertNotIn(srccol, sensibles, f"sourceColumn {srccol}")
                for s in sensibles:
                    self.assertNotRegex(tbl["partition"], rf"\"{re.escape(s)}(?:/[A-Za-z]+)?\"",
                                        f"colonne {s} sélectionnée par la requête M")

    def test_nom_affichage_masque_pour_direction(self):
        p = SM / "roles" / "Direction.tmdl"
        self.assertTrue(p.is_file())
        text = p.read_text(encoding="utf-8-sig")
        self.assertRegex(text, r"tablePermission\s+'?Alternants'?")
        self.assertRegex(text, r"columnPermission\s+'?NomAffichage'?\s*(?:=\s*none|\n\s+metadataPermission:\s*none)")

    def test_roles_presents(self):
        for r in self.m["powerbi"]["roles"]:
            p = SM / "roles" / f"{r['role']}.tmdl"
            with self.subTest(role=r["role"]):
                self.assertTrue(p.is_file())
                self.assertRegex(p.read_text(encoding="utf-8-sig"), re.compile(rf"^role\s+'?{r['role']}'?\s*$", re.M))

    def test_filtres_rls(self):
        adm = (SM / "roles" / "Administration.tmdl").read_text(encoding="utf-8-sig")
        for t in ("Livrables", "ComptesRendus", "Mobilisations", "GitlabSync"):
            self.assertRegex(adm, rf"tablePermission\s+'?{t}'?\s*=\s*FALSE\s*\(\s*\)", t)
        ref = (SM / "roles" / "Referent.tmdl").read_text(encoding="utf-8-sig")
        self.assertIn("USERPRINCIPALNAME", ref)
        for t in ("Candidatures", "Entretiens", "ActionsIntegration"):
            self.assertRegex(ref, rf"tablePermission\s+'?{t}'?\s*=\s*FALSE\s*\(\s*\)", t)

    def test_relations(self):
        p = SM / "relationships.tmdl"
        self.assertTrue(p.is_file())
        rels = []
        for block in re.split(r"^relationship ", p.read_text(encoding="utf-8-sig"), flags=re.M)[1:]:
            f = re.search(r"fromColumn:\s*(\S+)", block)
            t = re.search(r"toColumn:\s*(\S+)", block)
            inactive = re.search(r"isActive:\s*false", block) is not None
            if f and t:
                rels.append((f.group(1).replace("'", ""), t.group(1).replace("'", ""), not inactive))
        found = {(a, b): act for a, b, act in rels}
        for r in self.m["powerbi"]["relations"]:
            key = (r["from"].replace("[", ".").rstrip("]"), r["to"].replace("[", ".").rstrip("]"))
            with self.subTest(relation=f"{key[0]} -> {key[1]}"):
                self.assertIn(key, found)
                self.assertEqual(found[key], r["active"], "état actif/inactif")

    def test_lecture_seule_par_api_rest(self):
        expr = SM / "expressions.tmdl"
        self.assertTrue(expr.is_file())
        text = expr.read_text(encoding="utf-8-sig")
        self.assertIn("SiteUrl", text)
        # § 9.1 (v1.1.0) : listes désignées par leur nom interne via GetList, jamais par leur titre affiché.
        self.assertIn("_api/web/GetList", text)
        self.assertNotIn("getbytitle", text.lower())


@unittest.skipUnless((REPORT / "pages").is_dir(), "powerbi/HNCS-RD.Report/definition/pages absent")
class TestRapport(unittest.TestCase):
    PAGES = ["Vue exécutive", "Recrutement", "Effectifs et encadrement", "Projets et livrables",
             "Établissements et partenariats", "Communications et valorisation", "Comité R&D", "Qualité des données"]

    def test_pages_de_la_spec(self):
        names = set()
        for p in (REPORT / "pages").glob("*/page.json"):
            names.add(json.loads(p.read_text(encoding="utf-8-sig")).get("displayName"))
        for page in self.PAGES:
            self.assertIn(page, names)

    def test_visuels_sans_colonne_sensible(self):
        m = load_model()
        objs = objects_by_name(m)
        sensibles = set()
        for t in m["powerbi"]["tables"]:
            src = objs.get(t["source"])
            if src:
                sensibles |= {(t["table"], n) for n, c in columns_of(src).items()
                              if (c.get("perso") or c.get("confidentiel")) and not (t["table"] == "Alternants" and n == "Title")}
        for p in (REPORT / "pages").rglob("visual.json"):
            text = p.read_text(encoding="utf-8-sig")
            for tbl, col in sensibles:
                if f'"Property": "{col}"' in text or f'"Property":"{col}"' in text:
                    self.assertNotRegex(text, rf'"Entity":\s*"{tbl}"[^{{}}]*"Property":\s*"{col}"', str(p.relative_to(ROOT)))


@unittest.skipUnless((PBI / "tools" / "check_pbip.py").is_file(), "powerbi/tools/check_pbip.py absent")
class TestOutilPbip(unittest.TestCase):
    def test_check_pbip(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        res = subprocess.run([sys.executable, str(PBI / "tools" / "check_pbip.py")], cwd=ROOT, capture_output=True,
                             env=env, timeout=300)
        self.assertEqual(res.returncode, 0, (res.stdout + res.stderr).decode("utf-8", "replace")[-3000:])


if __name__ == "__main__":
    unittest.main()
