# -*- coding: utf-8 -*-
"""RX-01 : une empreinte réaliste (format § 6.5) tient dans la capacité du type de sa colonne (spec § 6.5, P-09).

Les exemples du tableau § 6.5 sont relus dans spec.md, puis chaque valeur est remplacée par une valeur réaliste
« pire cas » (adresses longues, identifiants à 7 chiffres, dates-heures ISO 8601 UTC, commentaire de revue de
2 000 caractères). Capacités SharePoint : Text = 255 caractères ; Note (texte brut) = 63 999 caractères.
En v1.5.0, EmpreinteRevue (Livrables) était une colonne Text : ce test aurait échoué.
"""
from __future__ import annotations

import json
import re
import unittest

from hncs_offline import ROOT, columns_of, load_model, objects_by_name

CAPACITE = {"Text": 255, "Note": 63999}
# Adresse longue mais réaliste (UPN avec prénom et nom composés, sous-domaine de filiale) : 100 caractères.
EMAIL_LONG = ("marie-christine.de-la-fontaine-dupont-exemple@" + "direction-recherche-developpement.filiale-hncs.example.org")[:100]
ID_LONG = 9999999
DATETIME_UTC = "2026-12-31T23:59:59Z"
COMMENTAIRE_2000 = ("Commentaire de revue détaillé : préciser les prérequis, la phase de bascule et les risques. " * 30)[:2000]


def lire_formats() -> dict:
    """(liste, colonne) → exemple brut de la colonne Format du tableau § 6.5."""
    lines = (ROOT / "spec.md").read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("### 6.5 "))
    out = {}
    for l in lines[start + 1:]:
        if l.startswith("#"):
            break
        if l.startswith("| `"):
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            out[(cells[1], cells[0].strip("`"))] = cells[2]
    return out


def valeur_longue(cle: str, v, enums: dict):
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return ID_LONG
    if isinstance(v, list):
        return [valeur_longue(cle, x, enums) for x in v]
    if isinstance(v, str) and "@" in v:
        return EMAIL_LONG
    if cle == "Statut":
        return max(enums["STATUT_ACTION"], key=len)
    if cle in ("Valideur", "Proprietaire", "Reviseur"):
        return EMAIL_LONG
    if cle == "DecisionRevue":
        return max(enums["DECISION_REVUE"], key=len)
    if cle == "VersionValidee":
        return "512.0"
    if cle.startswith("Date") and (v is None or "T" in str(v)):
        return DATETIME_UTC
    if cle.startswith("Date") or cle in ("Echeance", "PeriodeDebut", "PeriodeFin"):
        return "2026-12-31"
    return v


def empreinte_realiste(liste: str, colonne: str, fmt: str, enums: dict) -> str:
    m = re.search(r"`(\{.*?\})`", fmt)
    if m:
        modele = json.loads(m.group(1))
        return json.dumps({k: valeur_longue(k, v, enums) for k, v in modele.items()}, ensure_ascii=False, separators=(",", ":"))
    if colonne == "EmpreinteCommentaire":
        return COMMENTAIRE_2000
    if colonne == "EmpreinteReferent":
        return str(ID_LONG)
    if colonne == "EmpreinteDecision":
        return max(enums["DECISION_PARTENARIAT"], key=len)
    raise AssertionError(f"format § 6.5 non interprété pour {liste}.{colonne} : {fmt}")


class TestEmpreintes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_model()
        cls.objs = objects_by_name(cls.m)
        cls.formats = lire_formats()

    def test_toutes_les_empreintes_ont_un_format(self):
        modele = {(o["name"], c["name"]) for o in self.m["objects"] for c in o["columns"] if c["name"].startswith("Empreinte")}
        self.assertEqual(modele, set(self.formats), "colonnes Empreinte* du modèle ↔ tableau § 6.5")

    def test_empreintes_masquees_et_reservees_aux_flux(self):
        for liste, col in self.formats:
            c = columns_of(self.objs[liste])[col]
            self.assertTrue(c["hidden"] and c["flux"], f"{liste}.{col}")

    def test_longueur_realiste_dans_la_capacite_de_la_colonne(self):
        for (liste, col), fmt in sorted(self.formats.items()):
            c = columns_of(self.objs[liste])[col]
            valeur = empreinte_realiste(liste, col, fmt, self.m["enums"])
            with self.subTest(colonne=f"{liste}.{col}", type=c["type"], longueur=len(valeur)):
                self.assertIn(c["type"], CAPACITE, "une empreinte est une colonne Text ou Note")
                self.assertLessEqual(len(valeur), CAPACITE[c["type"]],
                                     f"{len(valeur)} caractères pour une colonne {c['type']} ({CAPACITE[c['type']]} au plus)")

    def test_exemples_json_valides_et_compacts(self):
        for (liste, col), fmt in self.formats.items():
            m = re.search(r"`(\{.*?\})`", fmt)
            if m:
                obj = json.loads(m.group(1))
                self.assertEqual(m.group(1), json.dumps(obj, ensure_ascii=False, separators=(",", ":")), f"{liste}.{col} : JSON compact")

    def test_format_de_l_import_du_jeu_de_test(self):
        """Les empreintes calculées par Import-TestData.ps1 suivent les clés et l'ordre de § 6.5."""
        text = (ROOT / "testdata" / "Import-TestData.ps1").read_text(encoding="utf-8-sig")
        for (liste, col) in (("Affectations", "EmpreinteVerrou"), ("ActionsIntegration", "EmpreinteAction")):
            cles = list(json.loads(re.search(r"`(\{.*?\})`", self.formats[(liste, col)]).group(1)))
            bloc = re.search(rf"'{liste}' -and \$Colonne -eq '{col}'\) \{{(.*?)\}}\s*\n", text, re.S)
            self.assertIsNotNone(bloc, f"{liste}.{col} absent de Get-Empreinte")
            trouve = re.findall(r"(\w+)\s*=", bloc.group(1).split("[ordered]@{", 1)[1])
            self.assertEqual(trouve, cles, f"{liste}.{col} : clés ou ordre différents de § 6.5")


if __name__ == "__main__":
    unittest.main()
