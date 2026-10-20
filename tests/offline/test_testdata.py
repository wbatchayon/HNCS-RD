# -*- coding: utf-8 -*-
"""Validation hors ligne du jeu de test `testdata/` contre le modèle (spec § 4, § 6, § 12).

Les dates relatives (`@J±N`) sont résolues par rapport à la date du jour : toutes les règles
vérifiées ici sont invariantes par translation dans le temps.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import unittest
from urllib.parse import urlparse

from hncs_offline import (EMPREINTE_TOKEN, ID_TOKEN, ISO_DATE, ISO_DATETIME, PERSONA_TOKEN, REL_DATE,
                          SEED_ONLY_LISTS, SITE_TOKEN, TESTDATA_DIR, Jeu, as_date, columns_of, eval_formula,
                          is_blank, load_model, load_personas, load_testdata, parse_formula, persona_key)

HAS_DATA = TESTDATA_DIR.is_dir() and any(TESTDATA_DIR.glob("*.json"))
ALLOWED_HOST_SUFFIX = ("example.org", "example.com")
SYSTEM_FIELDS = set()
TERMINAUX_CAND = {"Intégrée", "Non retenue", "Clôturée"}
LIV_OUVERTS = {"À produire", "En cours", "Soumis à revue", "En revue", "Corrections demandées"}
# Contrôles qui ne restent pas vrais après la transition (constat ponctuel) : exclus des invariants d'état.
NON_PERSISTANTS = {"G_ENTRETIEN_PLANIFIE", "G_AUCUN_ENTRETIEN_ACTIF", "G_DATE_FIN_DEPASSEE"}
OBJET_LISTE = {"Candidature": "Candidatures", "Livrable": "Livrables", "CompteRendu": "ComptesRendus",
               "Affectation": "Affectations", "Alternant": "Alternants", "Communication": "CommunicationsRD",
               "Convention": "Conventions", "Sujet": "SujetsRD", "Entretien": "Entretiens"}
CODE_REFERENT = "REF-PRINCIPAL"  # § 6.5 (b) : changement de référent principal
# Empreintes calculées à l'import (format documenté dans testdata/README.md).
EMPREINTES_CALCULEES = {("Affectations", "EmpreinteVerrou"), ("ActionsIntegration", "EmpreinteAction")}


def jeu() -> Jeu:
    return Jeu()


# --------------------------------------------------------------------------- contrôles G_* (spec § 6.6)

class Controles:
    """Réimplémentation des contrôles de § 6.6 sur le jeu de test (partie vérifiable hors ligne)."""

    def __init__(self, j: Jeu):
        self.j = j

    def _entretiens(self, cid):
        return self.j.where("Entretiens", Candidature=cid)

    def G_RESP_ANALYSE(self, it):
        return not is_blank(it.get("ResponsableAnalyse"))

    def G_IDENTITE(self, it):
        return not is_blank(it.get("Email")) and not str(it.get("Title", "")).startswith("À qualifier")

    def G_DECIDEUR(self, it):
        return not is_blank(it.get("DecideurFinal"))

    def _compte(self, idh, col):
        it = self.j.get(idh) if idh else None
        return persona_key(it.get(col)) if it else None

    def valideur_legitime(self, valideur, auteur, affectation_id) -> bool:
        """G_VALIDEUR_LEGITIME : référent de l'affectation, ou membre de DIRECTION_RD ; jamais l'auteur."""
        if not valideur or valideur == auteur:
            return False
        aff = self.j.get(affectation_id)
        if aff and self._compte(aff.get("Referent"), "Compte") == valideur:
            return True
        from hncs_offline import load_personas
        return "G_DRD" in load_personas().get(valideur, {}).get("groupes", [])

    def G_VALIDEUR_LEGITIME(self, it):
        if "Proprietaire" in it:  # livrable
            return self.valideur_legitime(persona_key(it.get("Valideur")) or persona_key(it.get("Reviseur")),
                                          persona_key(it.get("Proprietaire")), it["Affectation"])
        aff = self.j.get(it["Affectation"])  # compte rendu
        auteur = self._compte(it.get("Alternant") or aff["Alternant"], "CompteM365")
        return self.valideur_legitime(persona_key(it.get("Valideur")), auteur, it["Affectation"])

    def G_SOURCE_ALTERNANT(self, it):
        # Partie persistante : candidature source « Intégrée », ou reprise de l'existant sans candidature
        # (Fonction.RepriseExistantActive était alors à Oui : données « déjà validées »).
        src = it.get("CandidatureSource")
        return not src or (self.j.get(src) or {}).get("Statut") == "Intégrée"

    def G_DATE_FIN_REPORTEE(self, it):
        fin = self.j.v("Alternants", it, "DateFin")
        return (fin - self.j.today).days > self.j.param_int("Fin.AnticipationJours", 30)

    def G_DECISION_PARTENARIAT(self, it):
        if it.get("TypeConvention") not in ("Convention de partenariat", "Sponsoring"):
            return True
        return it.get("DecisionPartenariat") in ("Partenariat retenu", "Sponsoring retenu") and \
            not is_blank(it.get("DecideurPartenariat"))

    def G_MOTIF_DECISION(self, it):
        return not is_blank(it.get("MotifDecision"))

    def G_ACTION_FORMALITE(self, it):
        # Hors ligne : l'empreinte de l'action de formalités existe (contrôle de l'auteur fait par PA-04).
        return it.get("Contexte") != "Formalités d'intégration" or not is_blank(it.get("EmpreinteAction"))

    def G_AVIS_ANALYSE(self, it):
        return not is_blank(it.get("AvisAnalyse"))

    def G_ENTRETIEN_PLANIFIE(self, it):
        return any(e["Statut"] == "Planifié" for e in self._entretiens(it["IdHNCS"]))

    def G_AUCUN_ENTRETIEN_ACTIF(self, it):
        return not self.G_ENTRETIEN_PLANIFIE(it)

    def G_ENTRETIEN_REALISE(self, it):
        return any(e["Statut"] == "Réalisé" and not is_blank(e.get("Resultat")) for e in self._entretiens(it["IdHNCS"]))

    def G_DECISION_FINALE(self, it):
        return not is_blank(it.get("DecideurFinal")) and any(e["Statut"] == "Réalisé" for e in self._entretiens(it["IdHNCS"]))

    def integration_manquants(self, it) -> list:
        manq = []
        if is_blank(it.get("DateDecisionFinale")):
            manq.append("(a) DateDecisionFinale")
        for c in ("DateDemarrageConfirmee", "DateFinPrevue"):
            if is_blank(it.get(c)):
                manq.append(f"(b) {c}")
        for c in ("Etablissement", "PolePressenti"):
            if is_blank(it.get(c)):
                manq.append(f"(c) {c}")
        acts = [a for a in self.j.where("ActionsIntegration", Candidature=it["IdHNCS"])
                if a.get("Contexte") == "Formalités d'intégration"]
        if not acts:
            manq.append("(d) aucune action de formalités")
        for a in acts:
            if not a.get("Bloquante"):
                continue
            ok = (a["Statut"] == "Terminée" and not is_blank(a.get("Preuve"))) or \
                 (a["Statut"] == "Non applicable" and not is_blank(a.get("Commentaire")))
            if not ok:
                manq.append(f"(e) {a['IdHNCS']} {a.get('CodeModeleAction', '')} « {a['Statut']} »")
        return manq

    def G_INTEGRATION(self, it):
        return not self.integration_manquants(it)

    def G_DOCUMENT(self, it):
        return not is_blank(it.get("LienDocument"))

    def G_COMMENTAIRE_REVUE(self, it):
        return not is_blank(it.get("CommentaireRevue"))

    def _dod(self, it):
        return all(it.get(f"DoD{k}") for k in ("1Fonctionnel", "2FicheMethodo", "3Restitution", "4SupportCom", "5Enseignements"))

    def G_CAPITALISATION(self, it):
        if is_blank(it.get("LienDocument")):
            return False
        if it.get("TypeLivrable") in ("POC / démonstrateur", "Plan de stratégie"):
            return self._dod(it)
        return True

    def G_CR_COMPLET(self, it):
        return not is_blank(it.get("Realisations")) and not is_blank(it.get("ProchainesEtapes")) \
            and it.get("Avancement") is not None

    def G_CR_ECHU(self, it):
        ech = self.j.v("ComptesRendus", it, "Echeance")
        return self.j.today > ech + dt.timedelta(days=self.j.param_int("CR.DelaiNonRemisJours", 3))

    def G_COMMENTAIRE_REFERENT(self, it):
        return not is_blank(it.get("CommentaireReferent"))

    def G_AFFECTATION_COMPLETE(self, it):
        # Partie persistante : champs verrouillés renseignés et référent existant. L'état « À intégrer / Actif »
        # de l'alternant et « Actif » du référent n'est exigé qu'au moment de l'activation.
        if any(is_blank(it.get(c)) for c in ("Alternant", "Sujet", "Referent", "DateDebut")):
            return False
        # v1.3.0 : l'alternant doit avoir un CompteM365 (propriétaire des livrables, bénéficiaire des droits)
        alt = self.j.get(it["Alternant"]) or {}
        return self.j.get(it["Referent"]) is not None and not is_blank(alt.get("CompteM365"))

    def G_DATE_FIN(self, it):
        return not is_blank(it.get("DateFin"))

    def G_LIVRABLES_CLOS(self, it):
        return not [l for l in self.j.where("Livrables", Affectation=it["IdHNCS"]) if l["Statut"] in LIV_OUVERTS]

    def G_DATE_DEBUT_ATTEINTE(self, it):
        return self.j.v("Alternants", it, "DateDebut") <= self.j.today

    def G_CLOTURE_ALTERNANCE(self, it):
        acts = [a for a in self.j.where("ActionsIntegration", Alternant=it["IdHNCS"])
                if a.get("Contexte") == "Clôture d'alternance" and a.get("Bloquante")]
        ok_acts = all(a["Statut"] == "Terminée" or (a["Statut"] == "Non applicable" and not is_blank(a.get("Commentaire")))
                      for a in acts)
        bilan = any(b["Statut"] == "Réalisé" for b in self.j.where("BilansAlternance", Alternant=it["IdHNCS"]))
        return ok_acts and bilan

    def G_AUTORISATIONS(self, it):
        return it.get("AutorisationsTiers", "Non requise") in ("Non requise", "Obtenue")

    def G_PUBLICATION(self, it):
        if is_blank(it.get("DateEffective")):
            return False
        return not (it.get("Externe", True) and is_blank(it.get("UrlPublication")))

    def G_PREUVE_SIGNATURE(self, it):
        return not is_blank(it.get("DateSignature")) and not is_blank(it.get("PreuveSignature"))

    def G_DATE_FIN_DEPASSEE(self, it):
        fin = self.j.v("Conventions", it, "DateFin")
        return fin is not None and fin < self.j.today


def dominating_controls(model, obj: str, status: str) -> set:
    """Contrôles présents sur TOUS les chemins ∅ → status (graphe des transitions du modèle)."""
    trans = [t for t in model["transitions"] if t["object"] == obj]
    all_ctrls = {g for t in trans for g in t["controls"]}
    out = set()
    for g in all_ctrls:
        edges = [(t["from"], t["to"]) for t in trans if g not in t["controls"]]
        reach, todo = {"∅"}, ["∅"]
        while todo:
            cur = todo.pop()
            for a, b in edges:
                if a == cur and b not in reach:
                    reach.add(b)
                    todo.append(b)
        if status not in reach:
            out.add(g)
    return out


# --------------------------------------------------------------------------- tests structurels

@unittest.skipUnless(HAS_DATA, "testdata/data absent")
class TestStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.j = jeu()
        cls.m = cls.j.model
        cls.personas = load_personas()

    def test_fichiers_correspondent_a_des_listes(self):
        for name in self.j.data:
            self.assertIn(name, self.j.objs, f"{name}.json ne correspond à aucune liste")
            self.assertEqual(self.j.objs[name]["kind"], "list", f"{name} est une bibliothèque")
            self.assertNotIn(name, SEED_ONLY_LISTS, f"{name} est un référentiel du provisioning : ne pas le dupliquer")
            self.assertIsInstance(self.j.data[name], list, name)

    def test_seeds_non_dupliques(self):
        for lst, ids in self.j.seed_ids.items():
            for it in self.j.items(lst):
                self.assertNotIn(it.get("IdHNCS"), ids, f"{lst} : {it.get('IdHNCS')} duplique un référentiel")

    def test_colonnes_existantes(self):
        for lst, items in self.j.data.items():
            cols = columns_of(self.j.objs[lst])
            for it in items:
                for k in it:
                    self.assertIn(k, cols, f"{lst} : colonne inconnue {k}")

    def test_statut_precedent_egal_au_statut(self):
        for lst, items in self.j.data.items():
            for it in items:
                if "StatutPrecedent" in it:
                    self.assertEqual(it["StatutPrecedent"], it.get("Statut"), f"{lst} {it.get('IdHNCS')}")

    def test_obligatoires_renseignes(self):
        for lst, items in self.j.data.items():
            obj = self.j.objs[lst]
            req = [c["name"] for c in obj["columns"] if c["required"]]
            if obj["titleColumn"]["required"]:
                req.append("Title")
            if obj["prefix"]:
                req.append("IdHNCS")
            for it in items:
                for c in req:
                    self.assertFalse(is_blank(it.get(c)), f"{lst} {it.get('IdHNCS', it.get('Title'))} : {c} obligatoire")

    def test_format_et_unicite_des_identifiants(self):
        seen = {}
        for lst, items in self.j.data.items():
            prefix = self.j.objs[lst]["prefix"]
            for it in items:
                idh = it.get("IdHNCS")
                if not prefix:
                    self.assertIsNone(idh, f"{lst} n'a pas d'IdHNCS")
                    continue
                self.assertRegex(idh, rf"^{prefix}-\d{{4}}-\d{{4,}}$", lst)
                self.assertNotIn(idh, seen, f"{idh} en double ({seen.get(idh)} / {lst})")
                seen[idh] = lst

    def test_unicite_des_idhncs_non_vides(self):
        """v1.2.0 : IdHNCS n'a plus de contrainte d'unicité SharePoint ; l'unicité est vérifiée ici,
        sur le jeu de test et les référentiels du provisionnement réunis."""
        vus = {}
        for lst, rows in self.m["seeds"].items():
            for r in rows:
                if r.get("IdHNCS"):
                    self.assertNotIn(r["IdHNCS"], vus, f"{r['IdHNCS']} en double ({vus.get(r['IdHNCS'])} / {lst})")
                    vus[r["IdHNCS"]] = f"seed {lst}"
        for lst, items in self.j.data.items():
            for it in items:
                idh = it.get("IdHNCS")
                if not is_blank(idh):
                    self.assertNotIn(idh, vus, f"{idh} en double ({vus.get(idh)} / {lst})")
                    vus[idh] = lst

    def test_cle_d_import_des_listes_sans_identifiant(self):
        """Idempotence de l'import : clé naturelle unique pour les listes sans IdHNCS."""
        keys = {"HistoriqueStatuts": "FluxRunId", "JournalFlux": "RunUrl", "GitlabSync": "CleSynchro"}
        for lst, key in keys.items():
            vals = [it.get(key) for it in self.j.items(lst)]
            self.assertTrue(all(vals), f"{lst} : {key} obligatoire pour l'import idempotent")
            self.assertEqual(len(vals), len(set(vals)), f"{lst} : {key} en double")

    def test_types_et_valeurs(self):
        enums = self.m["enums"]
        for lst, items in self.j.data.items():
            cols = columns_of(self.j.objs[lst])
            for it in items:
                ident = it.get("IdHNCS") or it.get("Title")
                for k, v in it.items():
                    c, where = cols[k], f"{lst} {ident} .{k}"
                    t = c["type"]
                    if v is None:
                        continue
                    if t in ("Text", "Note"):
                        self.assertIsInstance(v, str, where)
                        if t == "Text":
                            self.assertLessEqual(len(v), 255, where)
                        if v.startswith("@") and k != "RefMessage":
                            self.assertTrue(PERSONA_TOKEN.match(v) or v == EMPREINTE_TOKEN or ID_TOKEN.match(v),
                                            f"{where} : jeton {v}")
                        if v == EMPREINTE_TOKEN:
                            self.assertIn((lst, k), EMPREINTES_CALCULEES, where)
                    elif t == "Choice":
                        self.assertIn(v, enums[c["enum"]], where)
                    elif t == "MultiChoice":
                        self.assertIsInstance(v, list, where)
                        for x in v:
                            self.assertIn(x, enums[c["enum"]], where)
                    elif t == "Boolean":
                        self.assertIsInstance(v, bool, where)
                    elif t == "Number":
                        if isinstance(v, str):
                            m = ID_TOKEN.match(v)
                            self.assertTrue(m, f"{where} : nombre ou @id: attendu")
                            continue
                        self.assertIsInstance(v, (int, float), where)
                        self.assertNotIsInstance(v, bool, where)
                        if c["min"] is not None:
                            self.assertGreaterEqual(v, c["min"], where)
                        if c["max"] is not None:
                            self.assertLessEqual(v, c["max"], where)
                        if c["decimals"] == 0:
                            self.assertEqual(v, int(v), where)
                    elif t == "Date":
                        self.assertTrue(isinstance(v, str) and (REL_DATE.match(v) and "T" not in v or ISO_DATE.match(v)), where)
                    elif t == "DateTime":
                        self.assertTrue(isinstance(v, str) and (REL_DATE.match(v) or ISO_DATETIME.match(v) or ISO_DATE.match(v)), where)
                    elif t == "User":
                        self.assertRegex(v, PERSONA_TOKEN.pattern, where)
                    elif t == "UserMulti":
                        self.assertIsInstance(v, list, where)
                        for x in v:
                            self.assertRegex(x, PERSONA_TOKEN.pattern, where)
                    elif t == "Lookup":
                        self.assertIsInstance(v, str, where)
                    elif t == "LookupMulti":
                        self.assertIsInstance(v, list, where)
                    elif t == "URL":
                        self.assertIsInstance(v, str, where)
                        self.assertTrue(SITE_TOKEN.match(v) or v.startswith("https://"), f"{where} : {v}")

    def test_lookups_resolus(self):
        for lst, items in self.j.data.items():
            cols = columns_of(self.j.objs[lst])
            for it in items:
                for k, v in it.items():
                    c = cols[k]
                    if c["type"] not in ("Lookup", "LookupMulti") or v is None:
                        continue
                    target = c["lookup"]
                    for ref in (v if isinstance(v, list) else [v]):
                        ok = self.j.list_of(ref) == target or ref in self.j.seed_ids.get(target, set())
                        self.assertTrue(ok, f"{lst} {it.get('IdHNCS')} .{k} = {ref} introuvable dans {target}")

    def test_jetons_id_resolus(self):
        for lst, items in self.j.data.items():
            for it in items:
                for k, v in it.items():
                    if isinstance(v, str) and (m := ID_TOKEN.match(v)):
                        self.assertIsNotNone(self.j.get(m.group(1)), f"{lst} .{k} : {v}")
                        if "Liste" in it:
                            self.assertEqual(self.j.list_of(m.group(1)), it["Liste"], f"{lst} : {v} hors de {it['Liste']}")

    def test_personas_references_existent(self):
        for lst, items in self.j.data.items():
            for it in items:
                for v in it.values():
                    for x in (v if isinstance(v, list) else [v]):
                        k = persona_key(x)
                        if k:
                            self.assertIn(k, self.personas, f"{lst} : persona {k} absente de personas.sample.json")

    def test_codes_de_modeles_d_action(self):
        codes = {r["Code"]: r for r in self.m["seeds"]["ModelesActions"]}
        for a in self.j.items("ActionsIntegration"):
            code = a.get("CodeModeleAction")
            if code:
                self.assertIn(code, codes, a["IdHNCS"])
                self.assertEqual(a["Contexte"], codes[code]["Contexte"], a["IdHNCS"])
                self.assertEqual(a.get("Bloquante", False), codes[code]["Bloquante"] == "Oui", a["IdHNCS"])


@unittest.skipUnless(HAS_DATA, "testdata/data absent")
class TestDonneesFictives(unittest.TestCase):
    """Le dépôt est public (H-30) : aucune donnée réelle."""

    @classmethod
    def setUpClass(cls):
        cls.j = jeu()

    def _strings(self):
        for lst, items in self.j.data.items():
            for it in items:
                for k, v in it.items():
                    for x in (v if isinstance(v, list) else [v]):
                        if isinstance(x, str):
                            yield lst, it, k, x

    def test_emails_en_example_org(self):
        rx = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
        for lst, it, k, s in self._strings():
            if s.startswith("@"):
                continue
            for dom in rx.findall(s):
                self.assertTrue(dom.endswith(ALLOWED_HOST_SUFFIX), f"{lst} .{k} : domaine {dom}")

    def test_emails_candidats_et_contacts(self):
        for c in self.j.items("Candidatures"):
            if c.get("Email"):
                self.assertTrue(c["Email"].lower().endswith("@example.org"), c["IdHNCS"])
        for e in self.j.items("Etablissements"):
            if e.get("EmailContact"):
                self.assertTrue(e["EmailContact"].endswith("@example.org"), e["IdHNCS"])

    def test_urls_fictives(self):
        for lst, it, k, s in self._strings():
            if s.startswith("http"):
                host = urlparse(s).hostname or ""
                self.assertTrue(host.endswith(ALLOWED_HOST_SUFFIX), f"{lst} .{k} : hôte {host}")

    def test_personas_sample_fictives(self):
        personas = load_personas()
        groups = {g["code"] for g in self.j.model["groups"]}
        for k, p in personas.items():
            self.assertRegex(k, r"^[A-Z][A-Z0-9_]*$")
            self.assertTrue(p["upn"].endswith("@contoso.onmicrosoft.com"), k)
            self.assertTrue(set(p["groupes"]) <= groups, k)
        self.assertEqual(sum(1 for p in personas.values() if p.get("compteService")), 1)

    def test_journal_et_historique_sans_nom(self):
        """§ 7.5 : HistoriqueStatuts et JournalFlux ne contiennent que des identifiants."""
        noms = {x["Title"] for lst in ("Candidatures", "Alternants") for x in self.j.items(lst)}
        noms |= {x["Email"].lower() for x in self.j.items("Candidatures") if x.get("Email")}
        for lst in ("HistoriqueStatuts", "JournalFlux"):
            for it in self.j.items(lst):
                txt = " ".join(str(v) for v in it.values()).lower()
                for n in noms:
                    self.assertNotIn(n.lower(), txt, f"{lst} : nom ou e-mail {n}")


# --------------------------------------------------------------------------- règles de validation de liste

@unittest.skipUnless(HAS_DATA, "testdata/data absent")
class TestValidationsDeListe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.j = jeu()

    def values(self, lst, it):
        cols = columns_of(self.j.objs[lst])
        return {k: self.j.v(lst, it, k) for k in cols}

    def test_formules_prises_en_charge(self):
        for o in self.j.model["objects"]:
            if o["validation"]:
                parse_formula(o["validation"])  # lève FormulaError si une construction est inconnue

    def test_validations_respectees(self):
        for lst, items in self.j.data.items():
            f = self.j.objs[lst]["validation"]
            if not f:
                continue
            tree = parse_formula(f)
            for it in items:
                self.assertTrue(eval_formula(tree, self.values(lst, it)),
                                f"{lst} {it.get('IdHNCS')} viole : {self.j.objs[lst]['validationMessage']}")

    def test_evaluateur_rejette_les_cas_invalides(self):
        """Témoins négatifs : l'évaluateur détecte bien les violations."""
        cases = [
            ("Candidatures", {"Statut": "Non retenue", "MotifCode": None}),
            ("Candidatures", {"Statut": "Intégrée", "MotifCode": None, "DateDemarrageConfirmee": dt.date(2026, 1, 1),
                              "DateFinPrevue": None}),
            ("Candidatures", {"Statut": "Retenue", "DateDemarrageConfirmee": dt.date(2026, 5, 1),
                              "DateFinPrevue": dt.date(2026, 4, 1)}),
            ("Livrables", {"Statut": "Archivé / clôturé", "TypeLivrable": "POC / démonstrateur", "DoD1Fonctionnel": True,
                           "DoD2FicheMethodo": True, "DoD3Restitution": False, "DoD4SupportCom": True, "DoD5Enseignements": True}),
            ("Livrables", {"Statut": "Suspendu / abandonné", "TypeLivrable": "Autre", "MotifSuspension": None}),
            ("Alternants", {"Statut": "Terminé", "DateDebut": dt.date(2026, 1, 1), "DateFin": dt.date(2026, 6, 1)}),
            ("CommunicationsRD", {"Statut": "Validée", "AutorisationsTiers": "Demandée"}),
            ("Conventions", {"Statut": "Signée / active", "DateSignature": None}),
            ("Entretiens", {"Statut": "Réalisé", "Resultat": None}),
        ]
        for lst, vals in cases:
            tree = parse_formula(self.j.objs[lst]["validation"])
            self.assertFalse(eval_formula(tree, vals), f"{lst} {vals}")


# --------------------------------------------------------------------------- couverture

@unittest.skipUnless(HAS_DATA, "testdata/data absent")
class TestCouverture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.j = jeu()

    def test_tous_les_statuts_couverts(self):
        for lst, items in self.j.data.items():
            enum = self.j.status_enum(lst)
            if not enum:
                continue
            present = {it.get("Statut") for it in items}
            present |= {r.get("Statut") for r in self.j.model["seeds"].get(lst, [])}
            self.assertEqual(set(enum) - present, set(), f"{lst} : statuts non couverts")

    def test_niveaux_et_reprises_du_journal(self):
        e = self.j.model["enums"]
        jf = self.j.items("JournalFlux")
        self.assertEqual({x["Niveau"] for x in jf}, set(e["NIVEAU_LOG"]))
        self.assertEqual({x["StatutReprise"] for x in jf}, set(e["STATUT_REPRISE"]))
        self.assertTrue([x for x in jf if x["Niveau"] == "Erreur" and x["StatutReprise"] == "À reprendre" and x.get("RunUrl")])

    def test_canaux_de_candidature(self):
        cands = self.j.items("Candidatures")
        canaux = {c["Canal"] for c in cands}
        for c in ("Site HNCS", "LinkedIn", "France Travail", "Candidature spontanée", "À qualifier"):
            self.assertIn(c, canaux)
        self.assertIn("Boîte mail R&D", {c["ModeReception"] for c in cands})
        self.assertTrue(all(c.get("RefMessage") for c in cands if c["ModeReception"] == "Boîte mail R&D"),
                        "RefMessage obligatoire pour l'idempotence de PA-01b")

    def test_doublon_signale_non_fusionne(self):
        cands = {c["IdHNCS"]: c for c in self.j.items("Candidatures")}
        doublons = [c for c in cands.values() if c.get("DoublonPotentiel")]
        self.assertTrue(doublons)
        for d in doublons:
            src = cands.get(d.get("DoublonDe"))
            self.assertIsNotNone(src, d["IdHNCS"])
            self.assertEqual(src["Email"].lower(), d["Email"].lower())
            self.assertNotIn(d["Statut"], TERMINAUX_CAND, "un doublon est signalé, jamais clôturé automatiquement")

    def test_non_retenues_apres_analyse_et_apres_entretien(self):
        ctl = Controles(self.j)
        nr = [c for c in self.j.items("Candidatures") if c["Statut"] == "Non retenue"]
        self.assertTrue([c for c in nr if not ctl._entretiens(c["IdHNCS"])], "non retenue après analyse")
        self.assertTrue([c for c in nr if any(e.get("Resultat") == "Défavorable" for e in ctl._entretiens(c["IdHNCS"]))],
                        "non retenue après entretien")
        for c in nr:
            self.assertTrue(ctl.G_AVIS_ANALYSE(c) or ctl.G_DECISION_FINALE(c), c["IdHNCS"])

    def test_doublon_verifie(self):
        """v1.3.0 : un doublon vérifié (faux positif) reste tracé (DoublonPotentiel) mais sort de la vue des doublons."""
        ver = [c for c in self.j.items("Candidatures") if c.get("DoublonPotentiel") and c.get("DoublonVerifie")]
        self.assertTrue(ver)
        vue = next(v for v in self.j.model["views"]["Candidatures"] if v["name"] == "Doublons potentiels")
        self.assertIn({"field": "DoublonVerifie", "op": "=", "values": ["Non"]}, vue["filter"])
        for c in self.j.items("Candidatures"):
            if c.get("DoublonVerifie"):
                self.assertTrue(c.get("DoublonPotentiel"), c["IdHNCS"])

    def test_cloturee_par_desistement(self):
        self.assertTrue([c for c in self.j.items("Candidatures")
                         if c["Statut"] == "Clôturée" and c.get("MotifCode") == "Désistement du candidat"])

    def test_formalites_incompletes_non_integrables(self):
        ctl = Controles(self.j)
        form = [c for c in self.j.items("Candidatures") if c["Statut"] == "Formalités en cours"]
        self.assertTrue(form)
        self.assertTrue([c for c in form if not ctl.G_INTEGRATION(c)],
                        "au moins une candidature en formalités doit échouer à G_INTEGRATION (témoin négatif)")

    def test_ecole_avec_plusieurs_alternants_sans_doublon(self):
        norm = lambda s: re.sub(r"\W+", "", s.lower())
        noms = [norm(e["Title"]) for e in self.j.items("Etablissements")]
        self.assertEqual(len(noms), len(set(noms)), "établissement en double")
        par_ecole = {}
        for a in self.j.items("Alternants"):
            par_ecole.setdefault(a["Etablissement"], []).append(a["IdHNCS"])
        multi = [e for e, al in par_ecole.items() if len(al) >= 2]
        self.assertTrue(multi)
        self.assertTrue([c for c in self.j.items("Conventions") if c["Etablissement"] in multi],
                        "une convention, avec son propre statut, doit concerner cette école")

    def test_livrables_cas_limites(self):
        livs = self.j.items("Livrables")
        ctl = Controles(self.j)
        self.assertTrue([l for l in livs if l["Statut"] == "Archivé / clôturé" and l["TypeLivrable"] == "POC / démonstrateur"
                         and ctl._dod(l)], "POC archivé avec DoD complète")
        self.assertTrue([l for l in livs if l["Statut"] == "Validé" and l.get("NbCorrections") == 1], "validé après corrections")
        self.assertTrue([l for l in livs if l.get("EnRetard")], "livrable en retard")
        self.assertTrue([l for l in livs if l["Statut"] == "Suspendu / abandonné"])

    def test_comptes_rendus_cas_limites(self):
        crs = self.j.items("ComptesRendus")
        for st in ("Remis", "Validé", "Non remis", "À compléter"):
            self.assertTrue([c for c in crs if c["Statut"] == st], st)
        self.assertTrue([c for c in crs if c.get("BlocageSignale")])

    def test_affectations_successives(self):
        self.assertTrue([a for a in self.j.items("Affectations") if a.get("AffectationRemplacee")])

    def test_transition_refusee_historisee(self):
        self.assertTrue([h for h in self.j.items("HistoriqueStatuts") if h["Resultat"] == "Refusée et annulée"])

    def test_candidature_de_plateforme_a_qualifier(self):
        """S-11 : courriel de plateforme sans identité, « À qualifier : … » sans e-mail, bloqué en « Reçue »."""
        aq = [c for c in self.j.items("Candidatures") if c["Title"].startswith("À qualifier") and is_blank(c.get("Email"))]
        self.assertTrue(aq)
        for c in aq:
            self.assertEqual(c["Statut"], "Reçue", c["IdHNCS"])
            self.assertEqual(c["ModeReception"], "Boîte mail R&D", c["IdHNCS"])

    def test_refus_administration_sans_entretien(self):
        """CAND-T17 : non retenue par l'administration avant tout entretien réalisé (G_DECIDEUR)."""
        ctl = Controles(self.j)
        cas = [c for c in self.j.items("Candidatures") if c["Statut"] == "Non retenue" and c.get("DateTransmissionAdmin")
               and not ctl.G_ENTRETIEN_REALISE(c)]
        self.assertTrue(cas)
        for c in cas:
            self.assertTrue(ctl.G_DECIDEUR(c), c["IdHNCS"])

    def test_convention_de_partenariat_signee_avec_decision(self):
        ctl = Controles(self.j)
        sig = [c for c in self.j.items("Conventions") if c["Statut"] == "Signée / active"
               and c["TypeConvention"] in ("Convention de partenariat", "Sponsoring")]
        self.assertTrue(sig)
        for c in sig:
            self.assertTrue(ctl.G_DECISION_PARTENARIAT(c), c["IdHNCS"])

    def test_livrable_repris_via_livrable_origine(self):
        self.assertTrue([l for l in self.j.items("Livrables") if l.get("LivrableOrigine")])

    def test_historique_sujets_et_entretiens(self):
        objets = {h["Objet"] for h in self.j.items("HistoriqueStatuts")}
        for o in ("Sujet", "Entretien", "Candidature", "Livrable", "Affectation", "Alternant", "CompteRendu",
                  "Communication", "Convention"):
            self.assertIn(o, objets)


# --------------------------------------------------------------------------- règles métier

@unittest.skipUnless(HAS_DATA, "testdata/data absent")
class TestReglesMetier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.j = jeu()
        cls.ctl = Controles(cls.j)

    def test_tous_les_controles_evalues(self):
        for c in self.j.model["controls"]:
            self.assertTrue(hasattr(self.ctl, c["code"]), f"contrôle {c['code']} non réimplémenté dans les tests")

    def test_P02_integrees_satisfont_G_INTEGRATION(self):
        for c in self.j.items("Candidatures"):
            if c["Statut"] == "Intégrée":
                self.assertEqual(self.ctl.integration_manquants(c), [], c["IdHNCS"])

    def test_integree_reliee_a_un_alternant(self):
        alts = {a["IdHNCS"]: a for a in self.j.items("Alternants")}
        for c in self.j.items("Candidatures"):
            if c["Statut"] != "Intégrée":
                continue
            a = alts.get(c.get("IdAlternant"))
            self.assertIsNotNone(a, c["IdHNCS"])
            self.assertEqual(a.get("CandidatureSource"), c["IdHNCS"])
            self.assertEqual(a["DateDebut"], c["DateDemarrageConfirmee"])
            self.assertEqual(a["DateFin"], c["DateFinPrevue"])
            self.assertEqual(a["Etablissement"], c["Etablissement"])
            self.assertEqual(a["Pole"], c["PolePressenti"])
        for a in alts.values():
            src = a.get("CandidatureSource")
            if src:
                self.assertEqual(self.j.get(src)["Statut"], "Intégrée", a["IdHNCS"])

    def test_ecole_d_accueil_constatee(self):
        """PA-04 étape 7 : l'école d'un alternant intégré n'est plus « Prospect » ni « Contact établi »."""
        for a in self.j.items("Alternants"):
            if a.get("CandidatureSource"):
                self.assertNotIn(self.j.get(a["Etablissement"])["Statut"], ("Prospect", "Contact établi"), a["IdHNCS"])

    def test_invariants_d_etat(self):
        """Tout contrôle persistant présent sur tous les chemins vers le statut courant est satisfait."""
        for obj, lst in OBJET_LISTE.items():
            for it in self.j.items(lst):
                for g in sorted(dominating_controls(self.j.model, obj, it["Statut"]) - NON_PERSISTANTS):
                    self.assertTrue(getattr(self.ctl, g)(it), f"{lst} {it['IdHNCS']} « {it['Statut']} » : {g} non satisfait")

    def test_entretien_planifie_existe(self):
        for c in self.j.items("Candidatures"):
            if c["Statut"] == "Entretien planifié":
                self.assertTrue(self.ctl.G_ENTRETIEN_PLANIFIE(c), c["IdHNCS"])

    def test_actions_bloquantes_terminees_avec_preuve(self):
        for a in self.j.items("ActionsIntegration"):
            if a.get("Bloquante") and a["Statut"] == "Terminée":
                self.assertFalse(is_blank(a.get("Preuve")), f"{a['IdHNCS']} : preuve obligatoire")
            if a.get("Bloquante") and a["Statut"] == "Non applicable":
                self.assertFalse(is_blank(a.get("Commentaire")), f"{a['IdHNCS']} : commentaire obligatoire")

    def test_cloture_alternance(self):
        for a in self.j.items("Alternants"):
            if a["Statut"] == "Clôturé" and self.j.where("Affectations", Alternant=a["IdHNCS"]):
                self.assertTrue(self.ctl.G_CLOTURE_ALTERNANCE(a), a["IdHNCS"])

    def test_affectations_cloturees_sans_livrable_ouvert(self):
        for a in self.j.items("Affectations"):
            if a["Statut"] == "Clôturée" and a.get("EmpreinteVerrou"):
                self.assertTrue(self.ctl.G_LIVRABLES_CLOS(a), a["IdHNCS"])

    def test_copies_des_flux(self):
        affs = {a["IdHNCS"]: a for a in self.j.items("Affectations")}
        for l in self.j.items("Livrables"):
            self.assertEqual(l.get("Sujet"), affs[l["Affectation"]]["Sujet"], l["IdHNCS"])
        for c in self.j.items("ComptesRendus"):
            self.assertEqual(c.get("Alternant"), affs[c["Affectation"]]["Alternant"], c["IdHNCS"])

    def test_retard_coherent_avec_pa06(self):
        """PA-06 : EnRetard = Oui exactement pour les livrables non terminaux dont l'échéance est dépassée."""
        for l in self.j.items("Livrables"):
            attendu = l["Statut"] in ("À produire", "En cours", "Corrections demandées") and \
                self.j.v("Livrables", l, "Echeance") < self.j.today
            self.assertEqual(bool(l.get("EnRetard")), attendu, l["IdHNCS"])

    def test_corrections_comptees(self):
        for l in self.j.items("Livrables"):
            if l["Statut"] == "Corrections demandées" or l.get("DecisionRevue") == "Corrections demandées":
                self.assertGreaterEqual(l.get("NbCorrections", 0), 1, l["IdHNCS"])

    def test_referent_principal_derive(self):
        """Référent principal = référent de l'affectation activée la plus récente, à défaut le référent pressenti ;
        EmpreinteReferent = son ID (P-09)."""
        for a in self.j.items("Alternants"):
            actives = [f for f in self.j.where("Affectations", Alternant=a["IdHNCS"]) if f.get("EmpreinteVerrou")]
            if actives:
                attendu = max(actives, key=lambda f: self.j.v("Affectations", f, "DateDebut"))["Referent"]
            else:
                src = self.j.get(a["CandidatureSource"]) if a.get("CandidatureSource") else None
                attendu = src.get("ReferentPressenti") if src else a.get("ReferentPrincipal")
            self.assertEqual(a.get("ReferentPrincipal"), attendu, a["IdHNCS"])
            if a.get("ReferentPrincipal"):
                self.assertEqual(a.get("EmpreinteReferent"), "@id:" + a["ReferentPrincipal"], a["IdHNCS"])

    def test_livrable_valide_par_le_referent_jamais_par_le_proprietaire(self):
        """G_VALIDEUR_LEGITIME : le valideur d'un livrable validé est le référent de l'affectation (ou la Direction R&D)."""
        for l in self.j.items("Livrables"):
            if l["Statut"] in ("Validé", "Archivé / clôturé") or l.get("Valideur"):
                v = persona_key(l.get("Valideur"))
                self.assertIsNotNone(v, l["IdHNCS"])
                self.assertNotEqual(v, persona_key(l.get("Proprietaire")), l["IdHNCS"])
                self.assertTrue(self.ctl.G_VALIDEUR_LEGITIME(l), l["IdHNCS"])

    def test_proprietaire_du_livrable_est_l_alternant(self):
        """v1.3.0 : le propriétaire d'un livrable est le CompteM365 de l'alternant de l'affectation."""
        affs = {f["IdHNCS"]: f for f in self.j.items("Affectations")}
        for l in self.j.items("Livrables"):
            alt = self.j.get(affs[l["Affectation"]]["Alternant"])
            self.assertEqual(l.get("Proprietaire"), alt.get("CompteM365"), l["IdHNCS"])

    def test_affectations_activees_avec_compte(self):
        for f in self.j.items("Affectations"):
            if f["Statut"] != "À préparer":
                self.assertFalse(is_blank(self.j.get(f["Alternant"]).get("CompteM365")), f["IdHNCS"])

    def test_livrable_origine(self):
        """H-51 / P-03 : un livrable repris pointe un livrable d'une affectation remplacée par la sienne ;
        l'ancien est suspendu (« Transféré vers … ») ou clos."""
        affs = {f["IdHNCS"]: f for f in self.j.items("Affectations")}
        for l in self.j.items("Livrables"):
            o_id = l.get("LivrableOrigine")
            if not o_id:
                continue
            o = self.j.get(o_id)
            chaine, cur = set(), affs[l["Affectation"]]
            while cur.get("AffectationRemplacee"):
                chaine.add(cur["AffectationRemplacee"])
                cur = affs[cur["AffectationRemplacee"]]
            self.assertIn(o["Affectation"], chaine, l["IdHNCS"])
            self.assertTrue(o["Statut"] in ("Validé", "Archivé / clôturé") or
                            (o["Statut"] == "Suspendu / abandonné" and o.get("MotifSuspension") == f"Transféré vers {l['IdHNCS']}"),
                            o_id)

    def test_decision_de_preselection(self):
        for c in self.j.items("Candidatures"):
            d = c.get("DecisionPreselection")
            if c.get("DateTransmissionAdmin") or c["Statut"] == "Présélectionnée":
                self.assertEqual(d, "Présélectionnée", c["IdHNCS"])
            elif c.get("DateDecisionPreselection"):
                self.assertEqual(d, "Écartée", c["IdHNCS"])
            else:
                self.assertIsNone(d, c["IdHNCS"])

    def test_empreintes_d_actions_de_formalites(self):
        for a in self.j.items("ActionsIntegration"):
            self.assertTrue(self.ctl.G_ACTION_FORMALITE(a), a["IdHNCS"])

    def test_decision_partenariat_tracee(self):
        roles_ok = {"DIR_RD", "DIRECTION"}
        for c in self.j.items("Conventions"):
            if c.get("DecisionPartenariat"):
                self.assertEqual(c.get("EmpreinteDecision"), c["DecisionPartenariat"], c["IdHNCS"])
                self.assertIn(persona_key(c.get("DecideurPartenariat")), roles_ok, c["IdHNCS"])

    def test_gitlab_sync_orpheline(self):
        """RX-07 : chaque ligne GitlabSync porte la colonne Orpheline ; une ligne orpheline est conservée."""
        lignes = self.j.items("GitlabSync")
        if not lignes:
            self.skipTest("aucune ligne GitlabSync")
        for g in lignes:
            self.assertIsInstance(g.get("Orpheline"), bool, g["CleSynchro"])
        self.assertTrue([g for g in lignes if g["Orpheline"]], "au moins une ligne orpheline (exclue des indicateurs)")

    def test_gitlab_sync_coherent(self):
        for g in self.j.items("GitlabSync"):
            suj = self.j.get(g["Sujet"])
            self.assertEqual(suj.get("GitlabProjetId"), g["GitlabProjetId"], g["CleSynchro"])
            self.assertTrue(g["CleSynchro"].startswith(f"{g['GitlabProjetId']}:"))
            if g.get("IdLivrable"):
                liv = self.j.get(g["IdLivrable"])
                self.assertIsNotNone(liv, g["IdLivrable"])
                ecart = self.j.v("GitlabSync", g, "MilestoneEcheance") != self.j.v("Livrables", liv, "Echeance")
                self.assertEqual(bool(g.get("EcartEcheance")), ecart, g["CleSynchro"])


# --------------------------------------------------------------------------- P-03 : affectations

@unittest.skipUnless(HAS_DATA, "testdata/data absent")
class TestAffectationsP03(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.j = jeu()
        cls.affs = {a["IdHNCS"]: a for a in cls.j.items("Affectations")}

    def d(self, a, c):
        return self.j.v("Affectations", a, c)

    def test_chaine_de_remplacement(self):
        remplacees = {}
        for a in self.affs.values():
            old_id = a.get("AffectationRemplacee")
            if not old_id:
                continue
            old = self.affs[old_id]
            self.assertNotIn(old_id, remplacees, f"{old_id} remplacée deux fois")
            remplacees[old_id] = a["IdHNCS"]
            self.assertEqual(old["Alternant"], a["Alternant"], a["IdHNCS"])
            self.assertIn(old["Statut"], ("Terminée", "Clôturée"), old_id)
            self.assertEqual(self.d(old, "DateFin"), self.d(a, "DateDebut") - dt.timedelta(days=1), old_id)
            self.assertEqual(old.get("MotifFin"), f"Remplacée par {a['IdHNCS']}", old_id)
            self.assertTrue(old["Sujet"] != a["Sujet"] or old.get("Referent") != a.get("Referent"),
                            f"{a['IdHNCS']} : un remplacement change le sujet ou le référent")

    def test_pas_de_cycle(self):
        for a in self.affs.values():
            seen, cur = set(), a
            while cur and cur.get("AffectationRemplacee"):
                self.assertNotIn(cur["IdHNCS"], seen, "cycle de remplacement")
                seen.add(cur["IdHNCS"])
                cur = self.affs.get(cur["AffectationRemplacee"])

    def test_dates_non_chevauchantes_par_alternant(self):
        """H-42 (v1.6.0) : les affectations concomitantes sont admises ; seules celles d'une même chaîne de
        remplacement (AffectationRemplacee) ne se chevauchent pas."""
        par_alt = {}
        for a in self.affs.values():
            racine = a
            while racine.get("AffectationRemplacee"):
                racine = self.affs[racine["AffectationRemplacee"]]
            par_alt.setdefault((a["Alternant"], racine["IdHNCS"]), []).append(a)
        far = dt.date.max
        for alt, lst in par_alt.items():
            lst.sort(key=lambda a: self.d(a, "DateDebut"))
            for prev, nxt in zip(lst, lst[1:]):
                fin = self.d(prev, "DateFin") or far
                self.assertLess(fin, self.d(nxt, "DateDebut"), f"{alt} : {prev['IdHNCS']} chevauche {nxt['IdHNCS']}")

    def test_changement_de_sujet_puis_de_referent(self):
        """Un alternant a changé de sujet, puis de référent : chaîne d'au moins trois affectations."""
        ok = False
        for a in self.affs.values():
            chain = [a]
            while chain[-1].get("AffectationRemplacee"):
                chain.append(self.affs[chain[-1]["AffectationRemplacee"]])
            if len(chain) >= 3:
                pairs = list(zip(chain[1:], chain))  # (ancienne, nouvelle)
                kinds = ["sujet" if o["Sujet"] != n["Sujet"] else "referent" for o, n in reversed(pairs)]
                ok = ok or kinds[:2] == ["sujet", "referent"]
        self.assertTrue(ok)

    def test_affectations_activees_ont_une_empreinte(self):
        for a in self.affs.values():
            if a["Statut"] in ("Active", "À risque", "Bloquée", "Terminée"):
                self.assertEqual(a.get("EmpreinteVerrou"), EMPREINTE_TOKEN, a["IdHNCS"])
            if a["Statut"] == "À préparer":
                self.assertIsNone(a.get("EmpreinteVerrou"), a["IdHNCS"])


# --------------------------------------------------------------------------- historique des statuts

@unittest.skipUnless(HAS_DATA, "testdata/data absent")
class TestHistorique(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.j = jeu()
        cls.m = cls.j.model
        cls.trans = {(t["object"], t["from"], t["to"]): t for t in cls.m["transitions"]}
        cls.personas = load_personas()
        inv = {}
        for role, grp in cls.m["roleToGroupCode"].items():
            inv.setdefault(grp, set()).add(role)
        cls.group_roles = inv

    def roles(self, persona: str, obj: str, item: dict) -> set:
        p = self.personas[persona]
        out = set()
        for g in p["groupes"]:
            out |= self.group_roles.get(g, set())
        if p.get("compteService"):
            out.add("FLUX")
        auteur, valideur = self.item_people(obj, item)
        if persona == auteur:
            out.add("ITEM_AUTEUR")
        if persona == valideur:
            out.add("ITEM_VALIDEUR")
        return out

    def compte(self, idh, col):
        it = self.j.get(idh) if idh else None
        return persona_key(it.get(col)) if it else None

    def item_people(self, obj, it):
        if obj == "Livrable":
            return persona_key(it.get("Proprietaire")), persona_key(it.get("Reviseur"))
        if obj == "CompteRendu":
            aff = self.j.get(it["Affectation"])
            val = persona_key(it.get("Valideur")) or self.compte(aff.get("Referent"), "Compte")
            return self.compte(it.get("Alternant") or aff["Alternant"], "CompteM365"), val
        if obj == "Affectation":
            return self.compte(it["Alternant"], "CompteM365"), self.compte(it.get("Referent"), "Compte")
        if obj == "Communication":
            return persona_key(it.get("Auteur")), persona_key(it.get("ValidationInterne"))
        return None, None

    def entries(self):
        return self.j.items("HistoriqueStatuts")

    def statuts(self):
        """Entrées de changement de statut (hors changements de référent principal, historisés à part par PA-05)."""
        return [h for h in self.entries() if h.get("CodeTransition") != CODE_REFERENT]

    def test_coherence_avec_le_modele(self):
        objets_transitions = {t["object"] for t in self.m["transitions"]}
        for h in self.statuts():
            obj = h["Objet"]
            self.assertEqual(h["Liste"], OBJET_LISTE[obj], h["FluxRunId"])
            item = self.j.get(h["Title"])
            self.assertIsNotNone(item, h["Title"])
            self.assertEqual(self.j.list_of(h["Title"]), h["Liste"])
            self.assertEqual(h["ItemId"], f"@id:{h['Title']}")
            actor = persona_key(h.get("Acteur"))
            self.assertEqual(persona_key(h.get("ActeurEmail")), actor)
            self.assertEqual(h["Origine"], "Flux" if self.personas[actor].get("compteService") else "Humain", h["FluxRunId"])
            if obj not in objets_transitions:
                # Objet à statuts libres (ex. Entretien, § 6.1-7) : statut de l'énumération, auteur habilité en écriture.
                enum = self.j.status_enum(h["Liste"])
                self.assertIn(h["StatutApres"], enum, h["FluxRunId"])
                self.assertEqual(h["Resultat"], "Acceptée", h["FluxRunId"])
                niveaux = {self.m["matrix"][h["Liste"]][g] for g in self.personas[actor]["groupes"]}
                self.assertTrue(niveaux & {"CSS", "FC"}, f"{h['FluxRunId']} : {actor} sans droit d'écriture sur {h['Liste']}")
                continue
            key = (obj, h.get("StatutAvant") or "∅", h["StatutApres"])
            t = self.trans.get(key)
            if h["Resultat"] == "Acceptée":
                self.assertIsNotNone(t, f"{h['FluxRunId']} : transition historisée absente du modèle {key}")
                self.assertEqual(h.get("CodeTransition"), t["code"], h["FluxRunId"])
                self.assertTrue(self.roles(actor, obj, item) & set(t["actors"]),
                                f"{h['FluxRunId']} {t['code']} : {actor} n'a aucun rôle parmi {t['actors']}")
            else:
                self.assertFalse(is_blank(h.get("Motif")), h["FluxRunId"])
                if h.get("CodeTransition"):
                    self.assertIsNotNone(t, h["FluxRunId"])
                    self.assertEqual(h["CodeTransition"], t["code"], h["FluxRunId"])
                    if h["Motif"].startswith("Rôle non autorisé"):
                        self.assertFalse(self.roles(actor, obj, item) & set(t["actors"]), h["FluxRunId"])
                    m = re.search(r"\b(G_[A-Z_]+)\b", h["Motif"])
                    if m:
                        self.assertIn(m.group(1), t["controls"], f"{h['FluxRunId']} : contrôle cité absent de {t['code']}")
                else:
                    self.assertIsNone(t, f"{h['FluxRunId']} : refus sans code mais transition existante")

    def test_changements_de_referent_principal(self):
        """PA-05 : StatutAvant / StatutApres = IdHNCS des référents, par le compte de service ; le dernier = référent courant."""
        derniers = {}
        for h in sorted([h for h in self.entries() if h.get("CodeTransition") == CODE_REFERENT],
                        key=lambda h: self.j.v("HistoriqueStatuts", h, "DateChangement")):
            self.assertEqual(h["Objet"], "Alternant", h["FluxRunId"])
            self.assertEqual(h["Origine"], "Flux", h["FluxRunId"])
            for c in ("StatutAvant", "StatutApres"):
                self.assertEqual(self.j.list_of(h[c]), "Referents", h["FluxRunId"])
            derniers[h["Title"]] = h["StatutApres"]
        self.assertTrue(derniers, "au moins un changement de référent principal historisé")
        for alt, ref in derniers.items():
            self.assertEqual(self.j.get(alt)["ReferentPrincipal"], ref, alt)

    def test_statut_de_reference_derniere_transition_acceptee(self):
        """RX-02 (§ 8.1 v1.6.0) : pour chaque élément d'un objet à statut contrôlé, le statut courant est le dernier
        StatutApres accepté de HistoriqueStatuts (sinon le rapprochement quotidien de PA-00E le rétablirait)."""
        derniers = {}
        for h in sorted(self.statuts(), key=lambda h: self.j.v("HistoriqueStatuts", h, "DateChangement")):
            if h["Resultat"] == "Acceptée":
                derniers[h["Title"]] = h["StatutApres"]
        objets = {t["object"] for t in self.m["transitions"]}
        for obj in objets:
            for it in self.j.items(OBJET_LISTE[obj]):
                with self.subTest(element=it["IdHNCS"]):
                    self.assertIn(it["IdHNCS"], derniers, "aucune transition acceptée historisée")
                    self.assertEqual(derniers[it["IdHNCS"]], it["Statut"])

    def test_historisations_hors_statut(self):
        """§ 6.5 : résultat d'entretien (Motif « Résultat : {Resultat} ») et changement de référent (REF-PRINCIPAL)."""
        for h in self.entries():
            if h["Objet"] == "Entretien" and h.get("Motif", "").startswith("Résultat"):
                ent = self.j.get(h["Title"])
                self.assertEqual(h["Motif"], f"Résultat : {ent['Resultat']}", h["FluxRunId"])
            if h.get("CodeTransition") == CODE_REFERENT:
                self.assertEqual(h["Objet"], "Alternant", h["FluxRunId"])
        self.assertTrue([h for h in self.entries() if h["Objet"] == "Entretien" and h.get("Motif", "").startswith("Résultat : ")])

    def test_aucune_decision_humaine_historisee_par_flux(self):
        decisions = {(d["object"], d["status"]) for d in self.m["humanDecisions"]}
        for h in self.statuts():
            if h["Resultat"] == "Acceptée" and h["Origine"] == "Flux" and (h["Objet"], h["StatutApres"]) in decisions:
                self.assertIn(h["CodeTransition"].rsplit("-", 1)[0] if h["CodeTransition"].count("-") > 1
                              else h["CodeTransition"], self.m["fluxExceptions"], h["FluxRunId"])

    def test_chaines_continues_et_statut_courant(self):
        par_objet = {}
        for h in self.statuts():
            par_objet.setdefault(h["Title"], []).append(h)
        for idh, hs in par_objet.items():
            hs.sort(key=lambda h: self.j.v("HistoriqueStatuts", h, "DateChangement"))
            courant = None
            for h in hs:
                self.assertEqual(h.get("StatutAvant"), courant, f"{idh} : rupture de chaîne à {h['FluxRunId']}")
                if h["Resultat"] == "Acceptée":
                    courant = h["StatutApres"]
            self.assertEqual(courant, self.j.get(idh)["Statut"], f"{idh} : dernier statut historisé ≠ statut courant")

    def test_journal_flux_coherent(self):
        flows = {f["id"] for f in self.m["flows"]}
        for e in self.j.items("JournalFlux"):
            self.assertIn(e["Title"], flows, e["RunUrl"])
            if e.get("IdObjet"):
                self.assertEqual(self.j.list_of(e["IdObjet"]), e.get("Liste"), e["RunUrl"])
                self.assertEqual(e.get("ItemId"), f"@id:{e['IdObjet']}")
            if e["Niveau"] == "Erreur":
                self.assertNotEqual(e["StatutReprise"], "Sans objet", e["RunUrl"])
            else:
                self.assertEqual(e["StatutReprise"], "Sans objet", e["RunUrl"])


if __name__ == "__main__":
    unittest.main()
