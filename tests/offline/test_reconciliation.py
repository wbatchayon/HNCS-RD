# -*- coding: utf-8 -*-
"""Valeurs attendues des mesures § 9.5 sur le jeu de test (référence de la réconciliation Power BI, lot 4).

Les dates du jeu étant relatives au jour d'import, ces valeurs ne dépendent pas de la date d'exécution.
Après import en recette, le rapport doit afficher ces valeurs (à jeu de test seul sur le site).
"""
from __future__ import annotations

import sys
import unittest

from hncs_offline import ROOT, TESTDATA_DIR, Jeu

sys.path.insert(0, str(ROOT / "tests" / "e2e" / "reconciliation"))
import reconcilier  # noqa: E402

ATTENDU = {
    "Candidatures reçues": 25,
    "Candidatures actives": 15,
    "Candidatures en attente": 3,
    "Candidatures analysées": 17,
    "Candidatures présélectionnées": 15,
    "Entretiens réalisés": 11,
    "Candidatures avec entretien réalisé": 11,
    "Entretiens à venir": 1,
    "Candidatures retenues": 8,
    "Candidatures intégrées": 6,
    "Doublons signalés": 1,
    "Alternants actifs": 4,
    "Alternants accueillis": 7,
    "Affectations actives": 5,
    "Affectations sans référent": 1,
    "Affectations incomplètes": 2,
    "Alternants sans affectation active": 0,
    "Livrables": 16,
    "Livrables validés": 6,
    "Livrables soumis à revue": 9,
    "Livrables en retard": 3,
    "Corrections en cours": 1,
    "Livrables sans modèle": 5,
    "POC réalisés": 2,
    "Plans de stratégie formalisés": 0,
    "Sujets bloqués": 2,
    "Sujets actifs": 4,
    "Mobilisations commerciales": 3,
    "Comptes rendus manquants": 4,
    "Blocages signalés": 1,
    "Partenariats académiques actifs": 1,
    "Conventions à renouveler": 1,
    "Établissements collaborants": 3,
    "Partenariats à évaluer": 1,
    "Bilans réalisés": 1,
    "Communications publiées": 1,
    "Communications en préparation": 6,
    "Livrables valorisés": 1,
    "Transitions refusées": 5,
    "Écarts d'échéance GitLab": 1,
}
RATIOS = {
    "Taux de présélection": 15 / 17,
    "Taux de transformation": 6 / 25,
    "Taux de validation": 6 / 9,
    "Taux de capitalisation": 4 / 6,
    "Taux de validation au premier passage": 5 / 9,
    "Taux de charge référent": 5 / 7,
    "Couverture des domaines cibles": 4 / 6,
}


@unittest.skipUnless(TESTDATA_DIR.is_dir(), "testdata/data absent")
class TestValeursAttendues(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = reconcilier.Mesures(Jeu()).calculer()

    def test_mesures_de_la_spec_recalculees(self):
        from hncs_offline import load_model
        non_recalculees = {"Alternants présents sur la période", "Avancement moyen (dernier CR)", "Cible", "Dernière actualisation"}
        for name in load_model()["powerbi"]["measures"]:
            if name not in non_recalculees:
                self.assertIn(name, self.res, f"mesure {name} non recalculée")

    def test_valeurs_attendues(self):
        for k, v in ATTENDU.items():
            self.assertEqual(self.res[k], v, k)
        for k, v in RATIOS.items():
            self.assertAlmostEqual(self.res[k], v, places=6, msg=k)

    def test_comparaison(self):
        self.assertEqual(reconcilier.comparer(self.res, {"Candidatures reçues": 25}, 0.001), [])
        self.assertTrue(reconcilier.comparer(self.res, {"Candidatures reçues": 24}, 0.001))


if __name__ == "__main__":
    unittest.main()
