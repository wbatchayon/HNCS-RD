# -*- coding: utf-8 -*-
"""Cohérence de la spec et du modèle généré (spec § 1, § 4, § 6, § 7, § 8.2, § 9.2, § 12)."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest

from hncs_offline import ROOT, columns_of, load_model, objects_by_name

CANDIDATURE_STATUTS = [
    "Reçue", "À analyser", "En cours d'analyse", "Présélectionnée", "Transmise à l'administration",
    "Entretien planifié", "Entretien réalisé", "En attente de décision", "Retenue", "Formalités en cours",
    "Intégrée", "Non retenue", "Clôturée",
]
LEVEL_RANK = {"—": 0, "R": 1, "CSS": 2, "FC": 3}


class TestExtracteur(unittest.TestCase):
    def test_spec_extract_check(self):
        """tools/spec_extract.py --check réussit (modèle à jour, spec cohérente)."""
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        res = subprocess.run([sys.executable, str(ROOT / "tools" / "spec_extract.py"), "--check"],
                             cwd=ROOT, capture_output=True, env=env, timeout=120)
        self.assertEqual(res.returncode, 0, res.stderr.decode("utf-8", "replace"))

    def test_version_spec(self):
        m = load_model()
        self.assertRegex(m["specVersion"], r"^\d+\.\d+\.\d+$")
        spec = (ROOT / "spec.md").read_text(encoding="utf-8")
        self.assertIn(f"| Version de la spec | {m['specVersion']} |", spec)


class TestStatutsEtTransitions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_model()
        cls.objs = objects_by_name(cls.m)
        cls.trans = cls.m["transitions"]
        cls.decisions = {(d["object"], d["status"]) for d in cls.m["humanDecisions"]}

    def test_13_statuts_candidature(self):
        self.assertEqual(self.m["enums"]["STATUT_CANDIDATURE"], CANDIDATURE_STATUTS)
        self.assertEqual(self.objs["Candidatures"]["statusEnum"], "STATUT_CANDIDATURE")
        self.assertEqual(self.objs["Candidatures"]["initialStatus"], "Reçue")

    def test_integree_uniquement_depuis_formalites(self):
        """P-02 : « Intégrée » n'est atteignable que depuis « Formalités en cours », avec G_INTEGRATION, sans FLUX."""
        vers = [t for t in self.trans if t["object"] == "Candidature" and t["to"] == "Intégrée"]
        self.assertEqual(len(vers), 1, vers)
        t = vers[0]
        self.assertEqual(t["from"], "Formalités en cours")
        self.assertIn("G_INTEGRATION", t["controls"])
        self.assertNotIn("FLUX", t["actors"])
        self.assertEqual(t["flow"], "PA-04")

    def test_aucune_decision_humaine_par_flux(self):
        """P-01 : aucune transition vers une décision humaine n'admet FLUX, hors exceptions documentées."""
        exceptions = set(self.m["fluxExceptions"])
        self.assertEqual(exceptions, {"CAND-T02"})
        for t in self.trans:
            if (t["object"], t["to"]) in self.decisions and "FLUX" in t["actors"]:
                self.assertIn(t["baseCode"], exceptions, f"{t['code']} : FLUX vers la décision humaine {t['to']}")

    def test_exception_flux_limitee_a_recue_vers_a_analyser(self):
        t = [t for t in self.trans if t["baseCode"] == "CAND-T02"]
        self.assertEqual([(x["from"], x["to"]) for x in t], [("Reçue", "À analyser")])

    def test_decideurs_presents_dans_les_transitions(self):
        """Chaque décideur de § 6.1 figure parmi les acteurs d'au moins une transition vers ce statut."""
        for d in self.m["humanDecisions"]:
            actors = set()
            for t in self.trans:
                if t["object"] == d["object"] and t["to"] == d["status"]:
                    actors |= set(t["actors"])
            self.assertTrue(actors, f"aucune transition vers {d['object']} / {d['status']}")
            for who in d["deciders"]:
                self.assertIn(who, actors, f"{d['object']} / {d['status']} : décideur {who} absent des transitions")

    def test_partition_disjointe_et_complete(self):
        by_list: dict[str, dict[str, str]] = {}
        for p in self.m["partition"]:
            seen = by_list.setdefault(p["list"], {})
            for s in p["targets"]:
                self.assertNotIn(s, seen, f"{p['list']} : « {s} » traité par {seen.get(s)} et {p['flow']}")
                seen[s] = p["flow"]
        for lst, mapping in by_list.items():
            enum = self.m["enums"][self.objs[lst]["statusEnum"]]
            self.assertEqual(set(mapping), set(enum), f"{lst} : partition incomplète")

    def test_flux_responsable_conforme_a_la_partition(self):
        """Le flux responsable d'une transition est celui qui traite le statut d'arrivée (§ 8.2)."""
        owner = {(p["list"], s): p["flow"] for p in self.m["partition"] for s in p["targets"]}
        for t in self.trans:
            self.assertEqual(t["flow"], owner[(t["list"], t["to"])],
                             f"{t['code']} : flux {t['flow']} ≠ partition {owner[(t['list'], t['to'])]}")

    def test_statut_initial_cree_par_une_transition(self):
        lists = {t["list"] for t in self.trans}
        for lst in lists:
            initial = self.objs[lst]["initialStatus"]
            creations = {t["to"] for t in self.trans if t["list"] == lst and t["from"] == "∅"}
            self.assertIn(initial, creations, f"{lst} : statut initial {initial} non créable")

    def test_tous_les_statuts_atteignables(self):
        for lst in {t["list"] for t in self.trans}:
            edges = [(t["from"], t["to"]) for t in self.trans if t["list"] == lst]
            reach, frontier = {"∅"}, ["∅"]
            while frontier:
                cur = frontier.pop()
                for a, b in edges:
                    if a == cur and b not in reach:
                        reach.add(b)
                        frontier.append(b)
            enum = set(self.m["enums"][self.objs[lst]["statusEnum"]])
            self.assertEqual(enum - reach, set(), f"{lst} : statuts inatteignables")

    def test_controles_des_transitions_existent_et_portent_sur_le_meme_objet(self):
        ctrls = {c["code"]: c for c in self.m["controls"]}
        for t in self.trans:
            for g in t["controls"]:
                self.assertIn(g, ctrls, f"{t['code']} : contrôle {g}")
                objets = [x.strip() for x in ctrls[g]["object"].split(";")]
                self.assertIn(t["object"], objets, f"{t['code']} : {g} porte sur {ctrls[g]['object']}")

    def test_aucune_transition_directe_recue_vers_integree(self):
        self.assertFalse([t for t in self.trans if t["object"] == "Candidature" and t["from"] == "Reçue"
                          and t["to"] in ("Retenue", "Formalités en cours", "Intégrée")])

    def test_validation_par_valideur_legitime(self):
        """Une validation ou une demande de correction exige G_VALIDEUR_LEGITIME (livrables et comptes rendus)."""
        for t in self.trans:
            if (t["object"], t["to"]) in {("Livrable", "Validé"), ("Livrable", "Corrections demandées"),
                                          ("CompteRendu", "Validé"), ("CompteRendu", "À compléter")}:
                self.assertIn("G_VALIDEUR_LEGITIME", t["controls"], t["code"])
                self.assertNotIn("FLUX", t["actors"], t["code"])

    def test_arbitrage_des_sujets_reserve_a_la_direction(self):
        for t in self.trans:
            if t["object"] == "Sujet" and t["to"] in ("Priorisé", "Suspendu", "Abandonné"):
                self.assertEqual(set(t["actors"]), {"DIRECTION_RD", "DIRECTION"}, t["code"])
            if t["object"] == "Sujet" and t["to"] in ("Suspendu", "Abandonné"):
                self.assertIn("G_MOTIF_DECISION", t["controls"], t["code"])

    def test_signature_partenariat_apres_decision(self):
        for t in self.trans:
            if t["object"] == "Convention" and t["to"] == "Signée / active":
                self.assertIn("G_DECISION_PARTENARIAT", t["controls"], t["code"])

    def test_reouverture_reservee_a_la_direction_rd(self):
        for t in self.trans:
            if t["baseCode"] == "CAND-T16":
                self.assertEqual(t["actors"], ["DIRECTION_RD"])


class TestModeleDeDonnees(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_model()
        cls.objs = objects_by_name(cls.m)

    def test_colonnes_implicites(self):
        for o in self.m["objects"]:
            names = [c["name"] for c in o["columns"]]
            if o["prefix"]:
                self.assertEqual(names[0], "IdHNCS", o["name"])
            if o["statusEnum"]:
                for n in ("Statut", "StatutPrecedent", "DateStatut"):
                    self.assertIn(n, names, o["name"])

    def test_champs_de_verrouillage_affectation(self):
        """P-03 : champs verrouillés, empreinte et lien de succession présents sur Affectations."""
        cols = columns_of(self.objs["Affectations"])
        for n in ("Alternant", "Sujet", "Referent", "DateDebut", "DateFin", "MotifFin"):
            self.assertIn(n, cols)
        self.assertEqual(cols["AffectationRemplacee"]["type"], "Lookup")
        self.assertEqual(cols["AffectationRemplacee"]["lookup"], "Affectations")
        emp = cols["EmpreinteVerrou"]
        self.assertTrue(emp["hidden"] and emp["flux"], "EmpreinteVerrou doit être masquée et réservée aux flux")
        self.assertTrue(cols["Alternant"]["required"] and cols["Sujet"]["required"] and cols["DateDebut"]["required"])

    def test_lookups_vers_lot_inferieur_ou_egal(self):
        for o in self.m["objects"]:
            for c in o["columns"]:
                if c["type"] in ("Lookup", "LookupMulti"):
                    tgt = self.objs[c["lookup"]]
                    self.assertLessEqual(tgt["lot"], c["lot"] or o["lot"], f"{o['name']}.{c['name']}")

    def test_validations_n_utilisent_pas_note_url_lookup(self):
        """§ 2.4 : les règles de validation ne référencent ni Note, ni URL, ni Lookup."""
        from hncs_offline import formula_fields, parse_formula
        for o in self.m["objects"]:
            if not o["validation"]:
                continue
            cols = columns_of(o)
            for f in formula_fields(parse_formula(o["validation"])):
                self.assertIn(f, cols, f"{o['name']} : colonne {f} inconnue dans la validation")
                self.assertNotIn(cols[f]["type"], ("Note", "URL", "Lookup", "LookupMulti", "User", "UserMulti", "MultiChoice"),
                                 f"{o['name']}.{f}")

    def test_champs_proteges_P09(self):
        """P-09 : les empreintes des champs protégés existent, sont masquées et réservées aux flux."""
        attendus = {"Affectations": "EmpreinteVerrou", "Alternants": "EmpreinteReferent", "Livrables": "EmpreinteRevue",
                    "ComptesRendus": "EmpreinteRevue", "ActionsIntegration": "EmpreinteAction", "Conventions": "EmpreinteDecision"}
        for lst, col in attendus.items():
            c = columns_of(self.objs[lst])[col]
            self.assertTrue(c["hidden"] and c["flux"], f"{lst}.{col}")
        self.assertTrue(columns_of(self.objs["Livrables"])["EmpreinteCommentaire"]["flux"])
        self.assertTrue(columns_of(self.objs["Alternants"])["ReferentPrincipal"]["flux"], "référent principal dérivé")
        self.assertIn("N-92", {n["code"] for n in self.m["notifications"]})

    def test_commentaires_en_ajout_seul(self):
        """S-07 : commentaires de revue conservés (colonnes Note en ajout seul)."""
        self.assertTrue(columns_of(self.objs["Livrables"])["CommentaireRevue"].get("appendOnly"))
        self.assertTrue(columns_of(self.objs["ComptesRendus"])["CommentaireReferent"].get("appendOnly"))

    def test_email_facultatif_mais_identite_controlee(self):
        cols = columns_of(self.objs["Candidatures"])
        self.assertFalse(cols["Email"]["required"])
        trans = [t for t in self.m["transitions"] if t["object"] == "Candidature" and t["from"] == "Reçue"
                 and t["to"] in ("À analyser", "En cours d'analyse")]
        self.assertTrue(trans)
        for t in trans:
            self.assertIn("G_IDENTITE", t["controls"], t["code"])

    def test_validation_integree_exige_les_dates(self):
        v = self.objs["Candidatures"]["validation"]
        self.assertIn('[Statut]="Intégrée"', v)
        self.assertIn("DateDemarrageConfirmee", v)
        self.assertIn("DateFinPrevue", v)

    def test_noms_internes(self):
        for o in self.m["objects"]:
            self.assertRegex(o["name"], r"^[A-Z][A-Za-z0-9]+$")
            for c in o["columns"]:
                self.assertRegex(c["name"], r"^[A-Za-z][A-Za-z0-9]{0,31}$")


class TestSecuriteModele(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_model()
        cls.objs = objects_by_name(cls.m)

    def test_direction_sans_acces_au_recrutement_ni_aux_alternants(self):
        """P-04 : G_DIR n'a aucun accès aux objets de recrutement et de suivi nominatif."""
        for name in ("Candidatures", "Entretiens", "Recrutement", "Administration", "Alternants", "SuiviAlternants",
                     "Livrables", "Etablissements", "BilansAlternance"):
            self.assertEqual(self.m["matrix"][name]["G_DIR"], "—", name)

    def test_entretiens_et_administration_reserves(self):
        for name in ("Entretiens", "Administration"):
            row = self.m["matrix"][name]
            others = {g: lvl for g, lvl in row.items() if g not in ("G_PROP", "G_ADM")}
            # seuls des accès ciblés par élément ou dossier (IL) sont admis hors administration (ex. dossier Operationnel)
            self.assertTrue(all(v == "—" or v.startswith("IL(") for v in others.values()), f"{name} : {others}")

    def test_journal_et_historique_sans_donnees_personnelles(self):
        for name in ("HistoriqueStatuts", "JournalFlux"):
            o = self.objs[name]
            self.assertFalse(o["personalData"], name)
            self.assertFalse([c["name"] for c in o["columns"] if c["perso"] or c["confidentiel"]], name)

    def test_powerbi_sans_colonne_perso_ni_confidentielle(self):
        """§ 9.2 : aucune colonne perso/confidentiel importée, sauf Alternants.Title (NomAffichage)."""
        for t in self.m["powerbi"]["tables"]:
            src = self.objs.get(t["source"])
            if not src:
                continue
            cols = columns_of(src)
            for c in t["columns"]:
                s = c["source"]
                col = cols.get(s)
                if col is None and s.endswith("Id"):
                    col = cols.get(s[:-2])
                if col is None and s.endswith("Email"):
                    col = cols.get(s[:-5])
                if col is None:
                    continue
                if col.get("perso") or col.get("confidentiel"):
                    self.assertTrue((t["table"], s, c["name"]) == ("Alternants", "Title", "NomAffichage")
                                    or c["transform"] == "bool", f"{t['table']}.{s} importée")

    def test_role_direction_masque_nom_affichage(self):
        roles = {r["role"]: r for r in self.m["powerbi"]["roles"]}
        self.assertIn("NomAffichage", roles["Direction"]["ols"])
        for r in ("Direction", "PilotageRD", "Administration", "Referent"):
            self.assertIn(r, roles)

    def test_notifications_larges_limitees_aux_identifiants(self):
        """§ 7.5 : notifications vers G_DIR / Direction / comité limitées à ID."""
        for n in self.m["notifications"]:
            dest = n["recipients"]
            if re.search(r"G_DIR\b|Destinataires\.Direction\b|comité", dest):
                self.assertEqual(set(n["data"]), {"ID"}, f"{n['code']} expose {n['data']}")

    def test_aucune_notification_ne_joint_de_cv(self):
        for n in self.m["notifications"]:
            self.assertNotRegex(n["content"].lower(), r"pièce jointe", n["code"])

    def test_niveaux_de_la_matrice(self):
        groups = [g["code"] for g in self.m["groups"]]
        for name, row in self.m["matrix"].items():
            self.assertEqual(list(row), groups, name)
            self.assertEqual(row["G_PROP"], "FC", name)


if __name__ == "__main__":
    unittest.main()
