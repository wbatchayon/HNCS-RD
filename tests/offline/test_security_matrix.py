# -*- coding: utf-8 -*-
"""Cohérence de la sécurité : matrice § 7.3 ↔ permissions par élément § 7.4 ↔ personas de recette."""
from __future__ import annotations

import json
import re
import unittest

from hncs_offline import ROOT, load_model, load_personas

RANK = {"-": 0, "R": 1, "CSS": 2, "FC": 3}
# « IL(x) » ou « R+IL(x) » (§ 7.2) : groupe 1 = niveau de base éventuel, groupe 2 = niveau par élément.
IL = re.compile(r"^(?:(R)\+)?IL\((\w+)\)$")
# Bénéficiaires désignés nominativement sur l'élément (pas un groupe) : vérifiés par les tests E2E.
PERSONNES = ("Participants", "Responsable", "Proprietaire", "Propriétaire du modèle")


def beneficiaire(seg: str) -> str:
    g = re.search(r"\bG_[A-Z]+\b", seg)
    if g:
        return g.group(0)
    if "DestinataireAdmin" in seg:
        return "G_ADM"
    if "éférent" in seg:
        return "G_REF"
    if "lternant" in seg:
        return "G_ALT"
    if any(x in seg for x in PERSONNES):
        return "PERSONNE"
    raise AssertionError(f"§ 7.4 : bénéficiaire non reconnu dans « {seg.strip()} »")


def parse_74() -> list[dict]:
    """Lit le tableau de § 7.4 dans spec.md : [{objects, grants: [(groupe, niveau)], flux, raw}]."""
    lines = (ROOT / "spec.md").read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("### 7.4 "))
    rows, i = [], start + 1
    while i < len(lines) and not lines[i].startswith("#"):
        l = lines[i]
        if l.startswith("|") and not l.startswith("| ---") and not l.startswith("| Objet"):
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            objs = [tok.split("/")[0] for tok in re.findall(r"`([^`]+)`", cells[0])]
            grants = []
            for seg in re.split(r"[;,]", cells[2]):
                lvl = re.findall(r"\b(FC|CSS|R)\b", seg)
                if lvl:
                    grants.append((beneficiaire(seg), lvl[-1]))
            rows.append({"objects": objs, "grants": grants, "flux": cells[3], "raw": l})
        i += 1
    return rows


def effective(matrix_row: dict, groups: list[str]) -> tuple[str, list[str]]:
    """Niveau de base effectif (max des groupes) et niveaux par élément (IL) accordables."""
    base, il = "-", []
    for g in groups:
        lvl = matrix_row.get(g, "-")
        m = IL.match(lvl)
        if m:
            il.append(m.group(2))
            lvl = m.group(1) or "-"
        if RANK[lvl] > RANK[base]:
            base = lvl
    return base, il


class TestMatriceEtPermissionsElement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_model()
        cls.rows = parse_74()
        cls.grants = {(o, g, l) for r in cls.rows for o in r["objects"] for g, l in r["grants"]}

    def test_table_74_lue(self):
        self.assertGreaterEqual(len(self.rows), 9)
        objs = {o for r in self.rows for o in r["objects"]}
        self.assertEqual(objs - set(self.m["matrix"]), set(), "objet de § 7.4 absent de la matrice")

    def test_niveaux_connus(self):
        for obj, row in self.m["matrix"].items():
            for g, lvl in row.items():
                self.assertTrue(lvl in RANK or IL.match(lvl), f"{obj}/{g} : {lvl}")

    def test_tout_IL_de_la_matrice_a_une_regle(self):
        for obj, row in self.m["matrix"].items():
            for g, lvl in row.items():
                mm = IL.match(lvl)
                if mm:
                    with self.subTest(objet=obj, groupe=g):
                        ok = (obj, g, mm.group(2)) in self.grants or (obj, "PERSONNE", mm.group(2)) in self.grants
                        self.assertTrue(ok, f"{obj}/{g} {lvl} sans règle § 7.4")

    def test_toute_regle_74_est_compatible_avec_la_matrice(self):
        """Une attribution par élément accordée à un groupe correspond à IL(x) / R+IL(x) dans la matrice, ou est
        déjà couverte par le niveau de base du groupe. Les bénéficiaires désignés nominativement (participants,
        responsable, propriétaire) relèvent de plusieurs groupes : vérifiés en E2E (Access.Tests.ps1)."""
        for obj, g, lvl in sorted(self.grants):
            if g == "PERSONNE":
                continue
            cell = self.m["matrix"][obj][g]
            with self.subTest(objet=obj, groupe=g, niveau=lvl):
                mm = IL.match(cell)
                if mm:
                    self.assertEqual(mm.group(2), lvl, f"{obj}/{g} : matrice {cell}, § 7.4 {lvl}")
                else:
                    self.assertGreaterEqual(RANK[cell], RANK[lvl], f"{obj}/{g} : matrice {cell} mais {lvl} au § 7.4")

    def test_flux_des_regles_existent(self):
        flows = {f["id"] for f in self.m["flows"]} | {re.sub(r"[a-z]$", "", f["id"]) for f in self.m["flows"]}
        for r in self.rows:
            for f in re.findall(r"PA-\d\d[A-Za-z]?", r["flux"]):
                self.assertIn(f, flows, r["raw"])

    def test_proprietaire_fc_partout(self):
        """§ 7.2 : seules les attributions de la matrice existent ; G_PROP a FC partout."""
        for obj, row in self.m["matrix"].items():
            self.assertEqual(row["G_PROP"], "FC", obj)

    def test_alternants_sans_acces_large(self):
        """G_ALT n'a jamais d'accès au niveau liste sur les objets nominatifs ou de suivi."""
        for obj in ("Candidatures", "Entretiens", "Alternants", "Affectations", "Livrables", "ComptesRendus",
                    "BilansAlternance", "SuiviAlternants", "LivrablesRD", "Administration", "Recrutement"):
            lvl = self.m["matrix"][obj]["G_ALT"]
            self.assertTrue(lvl == "-" or lvl.startswith("IL("), f"{obj} : G_ALT {lvl}")

    def test_direction_sans_liste_nominative(self):
        """§ 7.5 : la Direction n'accède à aucune liste nominative dans SharePoint."""
        for obj in ("Candidatures", "Entretiens", "Alternants", "Livrables", "Etablissements", "BilansAlternance"):
            self.assertEqual(self.m["matrix"][obj]["G_DIR"], "-", obj)


class TestPersonas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_model()
        cls.personas = load_personas()

    def test_chaque_groupe_a_une_persona(self):
        for g in self.m["groups"]:
            self.assertTrue([k for k, p in self.personas.items() if g["code"] in p["groupes"]], g["code"])

    def test_chaque_role_a_une_persona(self):
        for role, grp in self.m["roleToGroupCode"].items():
            self.assertTrue([k for k, p in self.personas.items() if grp in p["groupes"]], role)
        self.assertTrue([k for k, p in self.personas.items() if p.get("compteService")], "FLUX")

    def test_compte_de_service_proprietaire(self):
        for k, p in self.personas.items():
            if p.get("compteService"):
                self.assertIn("G_PROP", p["groupes"], "H-13 : compte de service membre de G_PROP")

    def test_persona_sans_acces(self):
        """Au moins une persona sans groupe (ancien alternant) : aucun accès attendu (H-18)."""
        self.assertTrue([k for k, p in self.personas.items() if not p["groupes"]])

    def test_attentes_cles(self):
        mx = self.m["matrix"]
        dirp = next(p for p in self.personas.values() if p["groupes"] == ["G_DIR"])
        for obj in ("Candidatures", "Entretiens", "Alternants", "Recrutement", "Livrables", "Etablissements"):
            self.assertEqual(effective(mx[obj], dirp["groupes"]), ("-", []), obj)
        adm = next(p for p in self.personas.values() if p["groupes"] == ["G_ADM"])
        self.assertEqual(effective(mx["Candidatures"], adm["groupes"]), ("-", ["CSS"]))
        self.assertEqual(effective(mx["Entretiens"], adm["groupes"]), ("CSS", []))
        ref = next(p for p in self.personas.values() if p["groupes"] == ["G_REF"])
        self.assertEqual(effective(mx["ActionsIntegration"], ref["groupes"]), ("R", ["CSS"]))
        self.assertEqual(effective(mx["Alternants"], ref["groupes"]), ("-", ["R"]))

    def test_membres_sample_du_provisioning(self):
        p = ROOT / "provisioning" / "config" / "membres.sample.json"
        if not p.is_file():
            self.skipTest("provisioning/config/membres.sample.json absent")
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        keys = {k for k in data if not k.startswith("$")}
        self.assertEqual(keys, {g["code"] for g in self.m["groups"]})


class TestAccesPiloteParLaMatrice(unittest.TestCase):
    def test_access_tests_pilote_par_le_modele(self):
        p = ROOT / "tests" / "e2e" / "Access.Tests.ps1"
        if not p.is_file():
            self.skipTest("tests/e2e/Access.Tests.ps1 absent")
        text = p.read_text(encoding="utf-8-sig")
        self.assertIn("matrix", text, "Access.Tests.ps1 doit lire la matrice du modèle généré")
        self.assertIn("Get-E2EAttendu", text)


if __name__ == "__main__":
    unittest.main()
