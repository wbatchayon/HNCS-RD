#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recalcul des mesures clés du rapport Power BI (spec § 9.5) à partir de données au format du jeu de test.

Sources possibles (même format : un fichier JSON par liste, lookups = IdHNCS, dates ISO ou relatives) :
  - le jeu de test lui-même (`testdata/data`) : valeurs ATTENDUES après import ;
  - un export du site de recette produit par `Export-HNCSRDDonnees.ps1` : valeurs RÉELLES dans SharePoint.

Usage :
    python tests/e2e/reconciliation/reconcilier.py --source testdata/data [--date 2026-10-15]
    python tests/e2e/reconciliation/reconcilier.py --source export/ --comparer rapport.json [--tolerance 0.001]
    python tests/e2e/reconciliation/reconcilier.py --source export/ --json > sharepoint.json

`rapport.json` : {"<nom de mesure>": valeur} relevé dans le rapport publié (carte ou tableau de mesures).
Code retour 1 si un écart dépasse la tolérance. Bibliothèque standard uniquement.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "offline"))
from hncs_offline import Jeu, as_date, is_blank, load_model, read_json  # noqa: E402

CAND_TERMINAUX = {"Intégrée", "Non retenue", "Clôturée"}
LIV_NON_TERMINAUX = {"À produire", "En cours", "Corrections demandées"}
LIV_VALIDES = {"Validé", "Archivé / clôturé"}
AFF_ACTIVES = {"Active", "À risque", "Bloquée"}


def days(a, b) -> int:
    """DATEDIFF ( a, b, DAY ) : nombre de frontières de jour franchies."""
    return (as_date(b) - as_date(a)).days


def mean(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def divide(a, b):
    return None if not b else a / b


def load_source(path: Path) -> dict:
    data = {}
    for p in sorted(path.glob("*.json")):
        content = read_json(p)
        if isinstance(content, list):
            data[p.stem] = content
    return data


class Mesures:
    def __init__(self, jeu: Jeu):
        self.j = jeu
        self.today = jeu.today
        self.now = dt.datetime.combine(jeu.today, dt.time(12, 0))

    def v(self, lst, it, col):
        return self.j.v(lst, it, col)

    def L(self, lst):
        return self.j.items(lst)

    def domaines(self):
        """Domaines cibles : référentiels du modèle complétés (ou remplacés) par les données."""
        by_id = {r["IdHNCS"]: {"IdHNCS": r["IdHNCS"], "Cible": r.get("Cible") == "Oui", "Statut": r.get("Statut")}
                 for r in self.j.model["seeds"].get("DomainesCibles", [])}
        for d in self.L("DomainesCibles"):
            by_id[d["IdHNCS"]] = d
        return list(by_id.values())

    def parametre(self, cle, defaut):
        try:
            return int(self.j.params.get(cle) or defaut)
        except ValueError:
            return defaut

    def calculer(self) -> dict:
        r = {}
        C, E, A = self.L("Candidatures"), self.L("Entretiens"), self.L("Alternants")
        F, Lv, CR = self.L("Affectations"), self.L("Livrables"), self.L("ComptesRendus")
        v = self.v

        # ---------------- Recrutement
        r["Candidatures reçues"] = len(C)
        actives = [c for c in C if c["Statut"] not in CAND_TERMINAUX]
        r["Candidatures actives"] = len(actives)
        seuil = self.parametre("Delai.SeuilAttenteCandidatureJours", 10)
        r["Seuil attente (j)"] = seuil
        r["Candidatures en attente"] = sum(
            1 for c in actives
            if days(v("Candidatures", c, "DateStatut") or v("Candidatures", c, "DateReception"), self.now) > seuil)
        r["Délai moyen de présélection (j)"] = mean(
            days(v("Candidatures", c, "DateReception"), v("Candidatures", c, "DateDecisionPreselection"))
            for c in C if c.get("DateDecisionPreselection"))
        r["Délai moyen de traitement (j)"] = mean(
            days(v("Candidatures", c, "DateReception"),
                 v("Candidatures", c, "DateIntegration") or v("Candidatures", c, "DateCloture"))
            for c in C if c.get("DateIntegration") or c.get("DateCloture"))
        r["Candidatures analysées"] = sum(1 for c in C if c.get("DateDecisionPreselection"))
        r["Candidatures présélectionnées"] = sum(1 for c in C if c.get("DateTransmissionAdmin"))
        r["Taux de présélection"] = divide(r["Candidatures présélectionnées"], r["Candidatures analysées"])
        r["Entretiens réalisés"] = sum(1 for e in E if e["Statut"] == "Réalisé")
        r["Candidatures avec entretien réalisé"] = len({e["Candidature"] for e in E if e["Statut"] == "Réalisé"})
        r["Entretiens à venir"] = sum(1 for e in E if e["Statut"] == "Planifié" and v("Entretiens", e, "DateHeure") >= self.now)
        r["Candidatures retenues"] = sum(1 for c in C if c["Statut"] in ("Retenue", "Formalités en cours", "Intégrée"))
        r["Candidatures intégrées"] = sum(1 for c in C if c["Statut"] == "Intégrée")
        r["Taux de transformation"] = divide(r["Candidatures intégrées"], r["Candidatures reçues"])
        r["Doublons signalés"] = sum(1 for c in C if c.get("DoublonPotentiel") and not c.get("DoublonVerifie"))

        # ---------------- Effectifs et encadrement
        r["Alternants actifs"] = sum(1 for a in A if a["Statut"] in ("Actif", "Fin planifiée"))
        r["Alternants accueillis"] = sum(
            1 for a in A if a["Statut"] in ("Actif", "Suspendu", "Fin planifiée", "Terminé", "Clôturé")
            and (not a.get("DateFinReelle") or v("Alternants", a, "DateFinReelle") >= v("Alternants", a, "DateDebut")))
        r["Affectations actives"] = sum(1 for f in F if f["Statut"] in AFF_ACTIVES)
        ouvertes = [f for f in F if f["Statut"] in AFF_ACTIVES | {"À préparer"}]
        r["Affectations sans référent"] = sum(1 for f in ouvertes if is_blank(f.get("Referent")))
        r["Affectations incomplètes"] = sum(
            1 for f in ouvertes
            if is_blank(f.get("Referent")) or is_blank(f.get("DateFin")) or not [l for l in Lv if l["Affectation"] == f["IdHNCS"]])
        r["Alternants sans affectation active"] = sum(
            1 for a in A if a["Statut"] in ("Actif", "Fin planifiée")
            and not [f for f in F if f["Alternant"] == a["IdHNCS"] and f["Statut"] in AFF_ACTIVES])
        capacite = sum(x.get("CapaciteIndicative") or 0 for x in self.L("Referents"))
        r["Taux de charge référent"] = divide(len({f["Alternant"] for f in F if f["Statut"] in AFF_ACTIVES}), capacite)

        # ---------------- Projets et livrables
        r["Livrables"] = len(Lv)
        r["Livrables validés"] = sum(1 for l in Lv if l["Statut"] in LIV_VALIDES)
        r["Livrables soumis à revue"] = sum(1 for l in Lv if l.get("DatePremierDepot"))
        r["Taux de validation"] = divide(r["Livrables validés"], r["Livrables soumis à revue"])
        ech = lambda l: v("Livrables", l, "Echeance")  # noqa: E731
        r["Livrables en retard"] = sum(1 for l in Lv if l["Statut"] in LIV_NON_TERMINAUX and ech(l) < self.today)
        echus = [l for l in Lv if ech(l) <= self.today and l["Statut"] != "Suspendu / abandonné"]
        r["Livrables arrivés à échéance"] = len(echus)
        r["Taux de remise à l'heure"] = divide(
            sum(1 for l in echus if l.get("DatePremierDepot") and as_date(v("Livrables", l, "DatePremierDepot")) <= ech(l)),
            len(echus))
        r["Taux de validation au premier passage"] = divide(
            sum(1 for l in Lv if l["Statut"] in LIV_VALIDES and (l.get("NbCorrections") or 0) == 0),
            r["Livrables soumis à revue"])
        dod = lambda l: all(l.get(k) for k in ("DoD1Fonctionnel", "DoD2FicheMethodo", "DoD3Restitution", "DoD4SupportCom", "DoD5Enseignements"))  # noqa: E731
        poc_plan = lambda l: l["TypeLivrable"] in ("POC / démonstrateur", "Plan de stratégie")  # noqa: E731
        archives = [l for l in Lv if l["Statut"] == "Archivé / clôturé"]
        r["Taux de capitalisation"] = divide(
            sum(1 for l in archives if l.get("LienDocument") and (not poc_plan(l) or dod(l))),
            sum(1 for l in Lv if l["Statut"] in LIV_VALIDES))
        r["Corrections en cours"] = sum(1 for l in Lv if l["Statut"] == "Corrections demandées")
        r["Échéances à 14 jours"] = sum(1 for l in Lv if l["Statut"] in LIV_NON_TERMINAUX
                                        and self.today <= ech(l) <= self.today + dt.timedelta(days=14))
        r["Livrables sans modèle"] = sum(1 for l in Lv if is_blank(l.get("Modele")) and l["Statut"] != "Suspendu / abandonné")
        r["POC réalisés"] = sum(1 for l in archives if l["TypeLivrable"] == "POC / démonstrateur" and dod(l))
        r["Plans de stratégie formalisés"] = sum(1 for l in archives if l["TypeLivrable"] == "Plan de stratégie" and dod(l))
        affs = {f["IdHNCS"]: f for f in F}
        sujets_valides = {affs[l["Affectation"]]["Sujet"] for l in Lv if l["Statut"] in LIV_VALIDES and l["Affectation"] in affs}
        cibles = [d for d in self.domaines() if d.get("Cible") and d.get("Statut") == "Actif"]
        couverts = {d["IdHNCS"] for d in cibles
                    if any(d["IdHNCS"] in (s.get("Domaines") or []) for s in self.L("SujetsRD") if s["IdHNCS"] in sujets_valides)}
        r["Couverture des domaines cibles"] = divide(len(couverts), len(cibles))
        r["Sujets bloqués"] = sum(1 for s in self.L("SujetsRD") if s["Statut"] in ("Bloqué", "À arbitrer"))
        r["Sujets actifs"] = sum(1 for s in self.L("SujetsRD") if s["Statut"] in ("Priorisé", "En cours", "Bloqué"))
        r["Mobilisations commerciales"] = len(self.L("Mobilisations"))

        # ---------------- Comptes rendus
        cech = lambda c: v("ComptesRendus", c, "Echeance")  # noqa: E731
        attendus = [c for c in CR if cech(c) <= self.today]
        r["Comptes rendus attendus"] = len(attendus)
        r["Comptes rendus manquants"] = sum(1 for c in CR if c["Statut"] == "Non remis"
                                            or (c["Statut"] in ("Attendu", "En rédaction") and cech(c) < self.today))
        r["Taux de remise des comptes rendus"] = divide(
            sum(1 for c in attendus if c.get("DateRemise") and as_date(v("ComptesRendus", c, "DateRemise")) <= cech(c)),
            len(attendus))
        r["Blocages signalés"] = sum(1 for c in CR if c.get("BlocageSignale"))

        # ---------------- Établissements et partenariats
        Cv, Et = self.L("Conventions"), self.L("Etablissements")
        r["Partenariats académiques actifs"] = sum(1 for c in Cv if c["Statut"] == "Signée / active"
                                                   and c["TypeConvention"] in ("Convention de partenariat", "Sponsoring"))
        r["Conventions à renouveler"] = sum(1 for c in Cv if c["Statut"] == "À renouveler")
        r["Établissements collaborants"] = sum(1 for e in Et if e["Statut"] in ("Établissement d'accueil", "Partenariat à évaluer", "Partenaire actif"))
        r["Partenariats à évaluer"] = sum(1 for e in Et if e["Statut"] == "Partenariat à évaluer")
        r["Bilans réalisés"] = sum(1 for b in self.L("BilansAlternance") if b["Statut"] == "Réalisé")

        # ---------------- Communications
        Co = self.L("CommunicationsRD")
        r["Communications publiées"] = sum(1 for c in Co if c["Statut"] == "Publiée" and c.get("Externe", True))
        r["Communications en préparation"] = sum(1 for c in Co if c["Statut"] in ("Idée", "À préparer", "En rédaction", "En revue", "Validée", "Programmée"))
        r["Livrables valorisés"] = len({c["LivrableSource"] for c in Co if c["Statut"] == "Publiée" and c.get("LivrableSource")})

        # ---------------- Actions et qualité des données
        r["Actions en retard"] = sum(1 for a in self.L("ActionsIntegration") if a["Statut"] in ("À faire", "En cours", "Bloquée")
                                     and a.get("Echeance") and v("ActionsIntegration", a, "Echeance") < self.today)
        r["Transitions refusées"] = sum(1 for h in self.L("HistoriqueStatuts") if h["Resultat"] == "Refusée — annulée")
        r["Écarts d'échéance GitLab"] = sum(1 for g in self.L("GitlabSync") if g.get("EcartEcheance"))
        return r


def comparer(calcule: dict, rapport: dict, tolerance: float) -> list[str]:
    ecarts = []
    for nom, attendu in rapport.items():
        if nom not in calcule:
            ecarts.append(f"{nom} : mesure inconnue du recalcul")
            continue
        val = calcule[nom]
        if val is None or attendu is None:
            if val != attendu:
                ecarts.append(f"{nom} : recalcul {val} / rapport {attendu}")
        elif abs(float(val) - float(attendu)) > tolerance:
            ecarts.append(f"{nom} : recalcul {val:.4f} / rapport {float(attendu):.4f}")
    return ecarts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="dossier de fichiers JSON (testdata/data ou export SharePoint)")
    ap.add_argument("--date", help="date de référence AAAA-MM-JJ (défaut : aujourd'hui ; = date d'import pour le jeu de test)")
    ap.add_argument("--comparer", help="fichier JSON des valeurs relevées dans le rapport Power BI")
    ap.add_argument("--tolerance", type=float, default=0.001)
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    args = ap.parse_args(argv)
    today = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    jeu = Jeu(model=load_model(), data=load_source(Path(args.source)), today=today)
    res = Mesures(jeu).calculer()
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        width = max(len(k) for k in res)
        for k, val in res.items():
            txt = "(vide)" if val is None else (f"{val:.4f}" if isinstance(val, float) else str(val))
            print(f"{k.ljust(width)}  {txt}")
    if args.comparer:
        ecarts = comparer(res, read_json(Path(args.comparer)), args.tolerance)
        for e in ecarts:
            print("ÉCART  " + e, file=sys.stderr)
        print(f"{len(ecarts)} écart(s).", file=sys.stderr)
        return 1 if ecarts else 0
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
