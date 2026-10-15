"""Tests hors ligne de gitlab/sync/sync_gitlab_sharepoint.py (unittest, bibliothèque standard).

Aucun appel réseau : les requêtes HTTP sont servies par une doublure (`FauxServeur`) qui simule
l'API REST GitLab v4, le point de jeton Entra et Microsoft Graph (listes SharePoint).

    python -m unittest discover -s gitlab/sync/tests -v
"""
from __future__ import annotations

import json
import logging
import sys
import unittest
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sync_gitlab_sharepoint as sync  # noqa: E402

logging.getLogger("hncs.gitlabsync").setLevel(logging.CRITICAL)

GRAPH = "https://graph.microsoft.com/v1.0"
GITLAB = "https://gitlab.example.org"
SITE_ID = "contoso.sharepoint.com,site-guid,web-guid"
LISTES = {"SujetsRD": "l-suj", "Livrables": "l-liv", "GitlabSync": "l-sync"}

CONFIG = sync.Config(
    gitlab_url=GITLAB,
    gitlab_token="glpat-factice",
    tenant_id="00000000-0000-0000-0000-000000000000",
    client_id="11111111-1111-1111-1111-111111111111",
    client_secret="secret-factice",
    client_assertion=None,
    site_hote="contoso.sharepoint.com",
    site_chemin="/sites/HNCS-RD",
)


def reponse(donnees, statut=200, entetes=None):
    corps = json.dumps(donnees, ensure_ascii=False).encode("utf-8") if donnees is not None else b""
    return statut, dict(entetes or {}), corps


class FauxServeur:
    """Doublure des API GitLab et Graph. État en mémoire ; journal des requêtes dans `appels`."""

    def __init__(self):
        self.appels: list[tuple[str, str]] = []
        self.pannes: list[tuple[str, int, dict]] = []  # (fragment d'URL, statut, en-têtes) consommées une fois
        self.par_page_graph = 2
        self.projets = {
            42: {
                "id": 42, "path_with_namespace": "hncs-rd/suj-2026-0003-sauvegarde-pra",
                "last_activity_at": "2026-10-13T16:45:12.345Z",
                "issues": {None: (5, 7), "LIV-2026-0010 — Plan PRA": (2, 3), "Jalon libre": (1, 0)},
                "mrs": {None: 3, "LIV-2026-0010 — Plan PRA": 1, "Jalon libre": 0},
                "jalons": [
                    {"id": 901, "title": "LIV-2026-0010 — Plan PRA", "due_date": "2026-11-30", "state": "active"},
                    {"id": 902, "title": "Jalon libre", "due_date": None, "state": "closed"},
                ],
            },
        }
        self.sujets = [
            {"id": "3", "fields": {"IdHNCS": "SUJ-2026-0003", "GitlabProjetId": 42.0}},
            {"id": "4", "fields": {"IdHNCS": "SUJ-2026-0004"}},
        ]
        # Échéance « date seule » renvoyée par Graph : minuit heure de Paris exprimé en UTC.
        self.livrables = [{"id": "10", "fields": {"IdHNCS": "LIV-2026-0010", "Echeance": "2026-11-29T23:00:00Z"}}]
        self.sync_items: dict[str, dict] = {}
        self._prochain_id = 100

    # -- routage ---------------------------------------------------------------------------
    def __call__(self, methode, url, entetes, corps, timeout):
        self.appels.append((methode, url))
        for i, (fragment, statut, ent) in enumerate(self.pannes):
            if fragment in url:
                del self.pannes[i]
                return reponse({"error": "panne simulée"}, statut, ent)
        if url.startswith("https://login.microsoftonline.com/"):
            assert methode == "POST" and b"client_credentials" in corps
            return reponse({"access_token": "jeton-graph", "expires_in": 3600})
        if url.startswith(GITLAB):
            assert entetes.get("PRIVATE-TOKEN") == "glpat-factice"
            assert methode == "GET", "la synchronisation est en lecture seule côté GitLab"
            return self._gitlab(url)
        if url.startswith(GRAPH):
            assert entetes.get("Authorization") == "Bearer jeton-graph"
            return self._graph(methode, url, json.loads(corps.decode("utf-8")) if corps else None)
        raise AssertionError(f"URL inattendue : {url}")

    def _gitlab(self, url):
        morceaux = urllib.parse.urlsplit(url)
        params = dict(urllib.parse.parse_qsl(morceaux.query))
        chemin = morceaux.path[len("/api/v4"):]
        segments = chemin.strip("/").split("/")
        projet = self.projets.get(int(segments[1]))
        if projet is None:
            return reponse({"message": "404 Project Not Found"}, 404)
        if len(segments) == 2:
            return reponse({k: projet[k] for k in ("id", "path_with_namespace", "last_activity_at")})
        ressource = segments[2]
        jalon = params.get("milestone")
        if ressource == "issues_statistics":
            ouvertes, fermees = projet["issues"][jalon]
            return reponse({"statistics": {"counts": {"all": ouvertes + fermees, "opened": ouvertes, "closed": fermees}}})
        if ressource == "merge_requests":
            assert params.get("state") == "opened"
            total = projet["mrs"][jalon]
            return self._page_gitlab([{"iid": i} for i in range(total)], params, avec_total=True)
        if ressource == "milestones":
            return self._page_gitlab(projet["jalons"], params, avec_total=False)
        raise AssertionError(f"Ressource GitLab inattendue : {chemin}")

    @staticmethod
    def _page_gitlab(elements, params, avec_total):
        par_page = int(params.get("per_page", 20))
        page = int(params.get("page", 1))
        tranche = elements[(page - 1) * par_page: page * par_page]
        entetes = {"X-Next-Page": str(page + 1) if page * par_page < len(elements) else ""}
        if avec_total:
            entetes["X-Total"] = str(len(elements))
        return reponse(tranche, entetes=entetes)

    def _graph(self, methode, url, charge):
        morceaux = urllib.parse.urlsplit(url)
        chemin = morceaux.path[len("/v1.0"):]
        params = dict(urllib.parse.parse_qsl(morceaux.query))
        if chemin == "/sites/contoso.sharepoint.com:/sites/HNCS-RD":
            return reponse({"id": SITE_ID})
        if chemin == f"/sites/{SITE_ID}/lists":
            return reponse({"value": [
                {"id": "l-autre", "name": "Poles", "displayName": "Pôles R&D"},
                {"id": "l-suj", "name": "SujetsRD", "displayName": "Sujets R&D"},
                {"id": "l-liv", "name": "Livrables", "displayName": "Livrables"},
                {"id": "l-sync", "displayName": "Synchronisation GitLab",
                 "webUrl": "https://contoso.sharepoint.com/sites/HNCS-RD/Lists/GitlabSync"},
            ]})
        prefixe = f"/sites/{SITE_ID}/lists/"
        assert chemin.startswith(prefixe), chemin
        liste, _, reste = chemin[len(prefixe):].partition("/")
        if methode == "GET" and reste == "items":
            source = {"l-suj": self.sujets, "l-liv": self.livrables,
                      "l-sync": list(self.sync_items.values())}[liste]
            debut = int(params.get("$skiptoken", 0))
            tranche = source[debut: debut + self.par_page_graph]
            corps = {"value": json.loads(json.dumps(tranche))}
            if debut + self.par_page_graph < len(source):
                corps["@odata.nextLink"] = f"{GRAPH}{chemin}?$skiptoken={debut + self.par_page_graph}"
            return reponse(corps)
        assert liste == "l-sync", "aucune écriture hors de GitlabSync"
        if methode == "POST" and reste == "items":
            champs = charge["fields"]
            if any(i["fields"]["CleSynchro"] == champs["CleSynchro"] for i in self.sync_items.values()):
                return reponse({"error": "duplicate"}, 409)
            item_id = str(self._prochain_id)
            self._prochain_id += 1
            self.sync_items[item_id] = {"id": item_id, "fields": self._stocker(champs)}
            return reponse({"id": item_id}, 201)
        if methode == "PATCH" and reste.endswith("/fields"):
            item_id = reste.split("/")[1]
            self.sync_items[item_id]["fields"].update(self._stocker(charge))
            return reponse(self.sync_items[item_id]["fields"])
        raise AssertionError(f"Appel Graph inattendu : {methode} {chemin}")

    @staticmethod
    def _stocker(champs):
        """Simule les conversions SharePoint : nombres en flottants, date seule rendue à minuit
        heure de Paris en UTC, valeurs nulles omises."""
        stocke = {}
        for nom, valeur in champs.items():
            if valeur is None:
                continue
            if nom == "MilestoneEcheance":
                jour = sync.normaliser_date(valeur)
                minuit = datetime.fromisoformat(jour + "T00:00:00+00:00")
                valeur = (minuit - sync.decalage_paris(minuit)).strftime("%Y-%m-%dT%H:%M:%SZ")
            elif isinstance(valeur, int) and not isinstance(valeur, bool):
                valeur = float(valeur)
            stocke[nom] = valeur
        return stocke

    def ecritures(self):
        return [(m, u) for m, u in self.appels if m in ("POST", "PATCH") and u.startswith(GRAPH)]


def client(serveur, attentes=None):
    attentes = attentes if attentes is not None else []
    return sync.ClientHttp(transport=serveur, attendre=attentes.append)


# =========================================================================================

class TestExtractionEtCle(unittest.TestCase):
    def test_extraction_id_livrable(self):
        self.assertEqual(sync.extraire_id_livrable("LIV-2026-0042 — Démonstrateur"), "LIV-2026-0042")
        self.assertEqual(sync.extraire_id_livrable("Recette (LIV-2026-12345)"), "LIV-2026-12345")
        self.assertEqual(sync.extraire_id_livrable("LIV-2026-0001 puis LIV-2026-0002"), "LIV-2026-0001")

    def test_extraction_sans_id(self):
        for titre in (None, "", "Jalon libre", "LIV-26-0042", "LIV-2026-042", "liv-2026-0042"):
            self.assertIsNone(sync.extraire_id_livrable(titre), titre)

    def test_cle_synchro(self):
        self.assertEqual(sync.cle_synchro(42, 901), "42:901")
        self.assertEqual(sync.cle_synchro(42), "42:0")
        self.assertEqual(sync.cle_synchro(42.0, None), "42:0")
        self.assertEqual(sync.cle_synchro(42, 0), "42:0")


class TestDatesEtEcart(unittest.TestCase):
    def test_date_seule_graph_ramenee_a_paris(self):
        self.assertEqual(sync.normaliser_date("2026-11-29T23:00:00Z"), "2026-11-30")  # hiver UTC+1
        self.assertEqual(sync.normaliser_date("2026-06-29T22:00:00Z"), "2026-06-30")  # été UTC+2
        self.assertEqual(sync.normaliser_date("2026-11-30T12:00:00Z"), "2026-11-30")
        self.assertEqual(sync.normaliser_date("2026-11-30"), "2026-11-30")
        self.assertIsNone(sync.normaliser_date(None))
        self.assertIsNone(sync.normaliser_date(""))

    def test_changements_d_heure(self):
        # 2026 : passage à l'heure d'été le 29 mars, à l'heure d'hiver le 25 octobre (01:00 UTC).
        self.assertEqual(sync.decalage_paris(datetime(2026, 3, 29, 0, 59, tzinfo=timezone.utc)).seconds, 3600)
        self.assertEqual(sync.decalage_paris(datetime(2026, 3, 29, 1, 0, tzinfo=timezone.utc)).seconds, 7200)
        self.assertEqual(sync.decalage_paris(datetime(2026, 10, 25, 0, 59, tzinfo=timezone.utc)).seconds, 7200)
        self.assertEqual(sync.decalage_paris(datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)).seconds, 3600)

    def test_instant_tronque_a_la_minute(self):
        self.assertEqual(sync.normaliser_instant("2026-10-13T16:45:12.345Z"), "2026-10-13T16:45:00Z")
        self.assertEqual(sync.normaliser_instant("2026-10-13T18:45:59+02:00"), "2026-10-13T16:45:00Z")
        self.assertIsNone(sync.normaliser_instant(None))

    def test_calcul_ecart(self):
        self.assertFalse(sync.calculer_ecart("2026-11-30", "2026-11-30"))
        self.assertTrue(sync.calculer_ecart("2026-12-15", "2026-11-30"))
        self.assertTrue(sync.calculer_ecart(None, "2026-11-30"))  # jalon sans échéance
        self.assertFalse(sync.calculer_ecart("2026-11-30", None))  # livrable inconnu / sans échéance


class TestConstructionDesLignes(unittest.TestCase):
    def setUp(self):
        self.sujet = sync.Sujet("3", "SUJ-2026-0003", 42)
        self.donnees = sync.DonneesProjet(
            projet_id=42, chemin="hncs-rd/suj-2026-0003-sauvegarde-pra",
            derniere_activite="2026-10-13T16:45:12Z", issues_ouvertes=5, issues_fermees=7, mrs_ouvertes=3,
            jalons=[
                sync.Jalon(902, "Jalon libre", None, "closed", 1, 0, 0),
                sync.Jalon(901, "LIV-2026-0010 — Plan PRA", "2026-12-15", "active", 2, 3, 1),
                sync.Jalon(903, "LIV-2026-0099 — Inconnu", "2026-12-01", "active", 0, 0, 0),
            ],
        )

    def test_ligne_projet_et_lignes_jalons(self):
        lignes = sync.construire_lignes(self.sujet, self.donnees, {"LIV-2026-0010": "2026-11-30"})
        self.assertEqual([l["CleSynchro"] for l in lignes], ["42:0", "42:901", "42:902", "42:903"])
        projet = lignes[0]
        self.assertEqual(projet["Title"], "hncs-rd/suj-2026-0003-sauvegarde-pra")
        self.assertEqual((projet["IssuesOuvertes"], projet["IssuesFermees"], projet["MRsOuvertes"]), (5, 7, 3))
        self.assertIsNone(projet["Milestone"])
        self.assertFalse(projet["EcartEcheance"])
        self.assertEqual(projet["SujetLookupId"], "3")
        jalon = lignes[1]
        self.assertEqual(jalon["IdLivrable"], "LIV-2026-0010")
        self.assertEqual(jalon["MilestoneEcheance"], "2026-12-15")
        self.assertTrue(jalon["EcartEcheance"])
        self.assertEqual((jalon["IssuesOuvertes"], jalon["IssuesFermees"], jalon["MRsOuvertes"]), (2, 3, 1))
        self.assertIsNone(lignes[2]["IdLivrable"])
        self.assertFalse(lignes[2]["EcartEcheance"])
        self.assertEqual(lignes[3]["IdLivrable"], "LIV-2026-0099")
        self.assertFalse(lignes[3]["EcartEcheance"])  # livrable introuvable : pas d'écart calculable
        self.assertEqual(set(lignes[0]), set(sync.CHAMPS_SYNC))

    def test_lecture_des_sujets(self):
        elements = [
            {"id": "7", "fields": {"IdHNCS": "SUJ-2026-0007", "GitlabProjetId": 42.0}},
            {"id": "3", "fields": {"IdHNCS": "SUJ-2026-0003", "GitlabProjetId": 42}},
            {"id": "4", "fields": {"IdHNCS": "SUJ-2026-0004"}},
            {"id": "5", "fields": {"IdHNCS": "SUJ-2026-0005", "GitlabProjetId": "abc"}},
            {"id": "6", "fields": {"IdHNCS": "SUJ-2026-0006", "GitlabProjetId": 77}},
        ]
        sujets = sync.lire_sujets(elements)
        self.assertEqual([(s.id_hncs, s.projet_id) for s in sujets], [("SUJ-2026-0003", 42), ("SUJ-2026-0006", 77)])


class TestCalculDesOperations(unittest.TestCase):
    DATE = "2026-10-14T05:30:00Z"

    def lignes(self):
        return [{
            "Title": "hncs-rd/p", "CleSynchro": "42:901", "SujetLookupId": "3", "GitlabProjetId": 42,
            "Milestone": "LIV-2026-0010 — Plan PRA", "MilestoneEcheance": "2026-11-30", "MilestoneEtat": "active",
            "IssuesOuvertes": 2, "IssuesFermees": 3, "MRsOuvertes": 1, "DerniereActivite": "2026-10-13T16:45:00Z",
            "IdLivrable": "LIV-2026-0010", "EcartEcheance": False,
        }]

    @staticmethod
    def existant_identique():
        # Valeurs telles que Graph les renvoie : flottants, lookup en chaîne, date seule en UTC.
        return {"id": "100", "fields": {
            "Title": "hncs-rd/p", "CleSynchro": "42:901", "SujetLookupId": "3", "GitlabProjetId": 42.0,
            "Milestone": "LIV-2026-0010 — Plan PRA", "MilestoneEcheance": "2026-11-29T23:00:00Z",
            "MilestoneEtat": "active", "IssuesOuvertes": 2.0, "IssuesFermees": 3.0, "MRsOuvertes": 1.0,
            "DerniereActivite": "2026-10-13T16:45:00Z", "IdLivrable": "LIV-2026-0010", "EcartEcheance": False,
            "DateSynchro": "2026-10-13T05:30:00Z",
        }}

    def test_creation_si_cle_absente(self):
        plan = sync.calculer_operations(self.lignes(), [], self.DATE)
        self.assertEqual(len(plan.creations), 1)
        champs = plan.creations[0]
        self.assertEqual(champs["DateSynchro"], self.DATE)
        self.assertEqual(champs["MilestoneEcheance"], "2026-11-30T12:00:00Z")
        self.assertEqual(champs["SujetLookupId"], "3")
        self.assertEqual(plan.mises_a_jour, [])

    def test_idempotence_aucune_ecriture_si_rien_ne_change(self):
        plan = sync.calculer_operations(self.lignes(), [self.existant_identique()], self.DATE)
        self.assertEqual(plan.nb_ecritures, 0)
        self.assertEqual(plan.inchangees, 1)

    def test_mise_a_jour_des_seuls_champs_modifies(self):
        existant = self.existant_identique()
        existant["fields"]["IssuesOuvertes"] = 1.0
        existant["fields"]["MilestoneEcheance"] = "2026-11-14T23:00:00Z"
        plan = sync.calculer_operations(self.lignes(), [existant], self.DATE)
        self.assertEqual(len(plan.mises_a_jour), 1)
        item_id, cle, champs = plan.mises_a_jour[0]
        self.assertEqual((item_id, cle), ("100", "42:901"))
        self.assertEqual(set(champs), {"IssuesOuvertes", "MilestoneEcheance", "DateSynchro"})
        self.assertEqual(champs["IssuesOuvertes"], 2)

    def test_effacement_d_un_champ(self):
        lignes = self.lignes()
        lignes[0]["MilestoneEcheance"] = None
        plan = sync.calculer_operations(lignes, [self.existant_identique()], self.DATE)
        self.assertIsNone(plan.mises_a_jour[0][2]["MilestoneEcheance"])

    def test_orphelines_signalees_sauf_projet_en_echec(self):
        orphelin = {"id": "101", "fields": {"CleSynchro": "42:777"}}
        echec = {"id": "102", "fields": {"CleSynchro": "55:0"}}
        plan = sync.calculer_operations(self.lignes(), [self.existant_identique(), orphelin, echec], self.DATE, {55})
        self.assertEqual(plan.orphelines, ["42:777"])
        self.assertEqual(plan.nb_ecritures, 0)


class TestPaginationEtNouvellesTentatives(unittest.TestCase):
    def test_pagination_gitlab_x_next_page(self):
        serveur = FauxServeur()
        serveur.projets[42]["jalons"] = [{"id": i, "title": f"J{i}", "due_date": None, "state": "active"} for i in range(1, 251)]
        gitlab = sync.ClientGitLab(client(serveur), GITLAB, "glpat-factice")
        jalons = gitlab.jalons(42)
        self.assertEqual(len(jalons), 250)
        pages = [u for m, u in serveur.appels if "/milestones" in u]
        self.assertEqual(len(pages), 3)
        self.assertIn("page=3", pages[-1])

    def test_comptage_par_x_total_et_repli_sans_en_tete(self):
        serveur = FauxServeur()
        serveur.projets[42]["mrs"][None] = 230
        gitlab = sync.ClientGitLab(client(serveur), GITLAB, "glpat-factice")
        self.assertEqual(gitlab.mrs_ouvertes(42), 230)
        self.assertEqual(len([u for m, u in serveur.appels if "merge_requests" in u]), 1)  # X-Total suffit

        transport_sans_total = FauxServeur()
        transport_sans_total.projets[42]["mrs"][None] = 230
        original = transport_sans_total._page_gitlab

        def sans_total(elements, params, avec_total):
            return original(elements, params, False)

        transport_sans_total._page_gitlab = sans_total
        gitlab = sync.ClientGitLab(client(transport_sans_total), GITLAB, "glpat-factice")
        self.assertEqual(gitlab.mrs_ouvertes(42), 230)

    def test_pagination_graph_odata_nextlink(self):
        serveur = FauxServeur()
        serveur.sujets = [{"id": str(i), "fields": {"IdHNCS": f"SUJ-2026-{i:04d}", "GitlabProjetId": i}} for i in range(1, 6)]
        graph = sync.ClientGraph(client(serveur), CONFIG)
        elements = graph.elements(SITE_ID, "l-suj", ["IdHNCS", "GitlabProjetId"])
        self.assertEqual(len(elements), 5)
        self.assertEqual(len([u for m, u in serveur.appels if "/lists/l-suj/items" in u]), 3)
        premiere = [u for m, u in serveur.appels if "/lists/l-suj/items" in u][0]
        self.assertIn("expand=fields(select=IdHNCS,GitlabProjetId)", premiere)

    def test_nouvelle_tentative_sur_429_avec_retry_after(self):
        serveur = FauxServeur()
        serveur.pannes.append(("/projects/42", 429, {"Retry-After": "7"}))
        serveur.pannes.append(("/projects/42", 503, {}))
        attentes = []
        gitlab = sync.ClientGitLab(client(serveur, attentes), GITLAB, "glpat-factice")
        self.assertEqual(gitlab.projet(42)["id"], 42)
        self.assertEqual(attentes, [7.0, 2.0])

    def test_echec_apres_les_tentatives(self):
        serveur = FauxServeur()
        serveur.pannes.extend([("/projects/42", 502, {})] * sync.MAX_TENTATIVES)
        attentes = []
        gitlab = sync.ClientGitLab(client(serveur, attentes), GITLAB, "glpat-factice")
        with self.assertRaises(sync.ErreurHttp) as contexte:
            gitlab.projet(42)
        self.assertEqual(contexte.exception.statut, 502)
        self.assertEqual(len(attentes), sync.MAX_TENTATIVES - 1)

    def test_pas_de_nouvelle_tentative_sur_erreur_client(self):
        serveur = FauxServeur()
        attentes = []
        gitlab = sync.ClientGitLab(client(serveur, attentes), GITLAB, "glpat-factice")
        with self.assertRaises(sync.ErreurHttp) as contexte:
            gitlab.projet(999)
        self.assertEqual(contexte.exception.statut, 404)
        self.assertEqual(attentes, [])


class TestExecutionComplete(unittest.TestCase):
    def executer(self, serveur, **options):
        return sync.executer(CONFIG, http=client(serveur), horloge=lambda: "2026-10-14T05:30:00Z", **options)

    def test_premiere_synchro_puis_idempotence(self):
        serveur = FauxServeur()
        self.assertEqual(self.executer(serveur), 0)
        cles = sorted(i["fields"]["CleSynchro"] for i in serveur.sync_items.values())
        self.assertEqual(cles, ["42:0", "42:901", "42:902"])
        par_cle = {i["fields"]["CleSynchro"]: i["fields"] for i in serveur.sync_items.values()}
        self.assertEqual(par_cle["42:901"]["IdLivrable"], "LIV-2026-0010")
        self.assertFalse(par_cle["42:901"]["EcartEcheance"])  # 2026-11-30 des deux côtés
        self.assertEqual(par_cle["42:0"]["IssuesOuvertes"], 5.0)
        self.assertEqual(par_cle["42:0"]["MRsOuvertes"], 3.0)
        self.assertEqual(par_cle["42:0"]["DerniereActivite"], "2026-10-13T16:45:00Z")
        self.assertEqual(par_cle["42:0"]["SujetLookupId"], "3")
        self.assertEqual(len(serveur.ecritures()), 3)

        serveur.appels.clear()
        self.assertEqual(self.executer(serveur), 0)
        self.assertEqual(serveur.ecritures(), [], "un second passage sans changement n'écrit rien")

    def test_ecart_detecte_apres_deplacement_du_jalon(self):
        serveur = FauxServeur()
        self.executer(serveur)
        serveur.projets[42]["jalons"][0]["due_date"] = "2026-12-15"
        serveur.appels.clear()
        self.assertEqual(self.executer(serveur), 0)
        ecritures = serveur.ecritures()
        self.assertEqual(len(ecritures), 1)
        self.assertEqual(ecritures[0][0], "PATCH")
        par_cle = {i["fields"]["CleSynchro"]: i["fields"] for i in serveur.sync_items.values()}
        self.assertTrue(par_cle["42:901"]["EcartEcheance"])
        self.assertEqual(sync.normaliser_date(par_cle["42:901"]["MilestoneEcheance"]), "2026-12-15")

    def test_simulation_n_ecrit_rien(self):
        serveur = FauxServeur()
        self.assertEqual(self.executer(serveur, dry_run=True), 0)
        self.assertEqual(serveur.ecritures(), [])
        self.assertEqual(serveur.sync_items, {})

    def test_projet_inaccessible_code_de_sortie_non_nul(self):
        serveur = FauxServeur()
        serveur.sujets.append({"id": "9", "fields": {"IdHNCS": "SUJ-2026-0009", "GitlabProjetId": 999}})
        self.assertEqual(self.executer(serveur), 1)
        # Les autres projets sont tout de même synchronisés.
        self.assertEqual(len(serveur.sync_items), 3)

    def test_aucune_ecriture_hors_gitlabsync_et_gitlab_en_lecture(self):
        serveur = FauxServeur()
        self.executer(serveur)
        for methode, url in serveur.appels:
            if url.startswith(GITLAB):
                self.assertEqual(methode, "GET")
            if methode in ("POST", "PATCH") and url.startswith(GRAPH):
                self.assertIn("/lists/l-sync/", url)

    def test_filtre_sur_un_sujet(self):
        serveur = FauxServeur()
        self.assertEqual(self.executer(serveur, filtre_sujet="SUJ-2026-0003"), 0)
        self.assertEqual(self.executer(serveur, filtre_sujet="SUJ-2026-0004"), 1)

    def test_site_ou_liste_introuvable_code_2(self):
        serveur = FauxServeur()
        serveur.pannes.append(("/sites/contoso.sharepoint.com:", 404, {}))
        self.assertEqual(self.executer(serveur), 2)


class TestConfiguration(unittest.TestCase):
    ENV = {
        "GITLAB_URL": "https://gitlab.example.org/",
        "GITLAB_TOKEN": "glpat-factice",
        "HNCS_TENANT_ID": "t",
        "HNCS_CLIENT_ID": "c",
        "HNCS_CLIENT_SECRET": "s",
        "HNCS_SITE_URL": "https://contoso.sharepoint.com/sites/HNCS-RD/",
    }

    def test_configuration_valide(self):
        config = sync.charger_config(self.ENV)
        self.assertEqual(config.gitlab_url, "https://gitlab.example.org")
        self.assertEqual((config.site_hote, config.site_chemin), ("contoso.sharepoint.com", "/sites/HNCS-RD"))
        self.assertNotIn("glpat", repr(config))
        self.assertNotIn("'s'", repr(config))

    def test_variables_manquantes(self):
        env = dict(self.ENV)
        del env["GITLAB_TOKEN"]
        del env["HNCS_CLIENT_SECRET"]
        with self.assertRaises(sync.ErreurConfig) as contexte:
            sync.charger_config(env)
        self.assertIn("GITLAB_TOKEN", str(contexte.exception))
        self.assertIn("HNCS_CLIENT_ASSERTION", str(contexte.exception))

    def test_assertion_a_la_place_du_secret(self):
        env = dict(self.ENV)
        del env["HNCS_CLIENT_SECRET"]
        env["HNCS_CLIENT_ASSERTION"] = "eyJ.factice.jwt"
        self.assertEqual(sync.charger_config(env).client_assertion, "eyJ.factice.jwt")

    def test_url_non_https_refusee(self):
        env = dict(self.ENV, GITLAB_URL="http://gitlab.example.org")
        with self.assertRaises(sync.ErreurConfig):
            sync.charger_config(env)

    def test_main_sans_configuration_retourne_2(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {}, clear=True):
            logging.disable(logging.CRITICAL)
            try:
                self.assertEqual(sync.main([]), 2)
            finally:
                logging.disable(logging.NOTSET)


class TestAbsenceDeSecrets(unittest.TestCase):
    def test_aucun_secret_en_dur(self):
        racine = Path(__file__).resolve().parents[2]
        motif = __import__("re").compile(r"glpat-[A-Za-z0-9_\-]{20}|client_secret\s*=\s*['\"][^'\"]{8,}")
        for fichier in racine.rglob("*"):
            if fichier.is_file() and fichier.suffix in {".py", ".ps1", ".yml", ".yaml", ".md"} and "tests" not in fichier.parts:
                self.assertIsNone(motif.search(fichier.read_text(encoding="utf-8")), fichier)


if __name__ == "__main__":
    unittest.main()
