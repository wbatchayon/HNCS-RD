#!/usr/bin/env python3
"""Synchronisation GitLab -> liste SharePoint `GitlabSync` (spec § 10.3, lot 5).

Lecture seule côté GitLab ; écriture **uniquement** dans la liste technique `GitlabSync`
(jamais dans `SujetsRD`, `Livrables` ni dans un statut métier, spec § 10.1).

Pour chaque sujet de `SujetsRD` ayant un `GitlabProjetId` :
  * une ligne de niveau projet (clé `<projetId>:0`) : issues ouvertes / fermées du projet,
    merge requests ouvertes, dernière activité ;
  * une ligne par jalon du projet (clé `<projetId>:<milestoneId>`) : échéance, état, issues
    ouvertes / fermées du jalon, MR ouvertes du jalon, `IdLivrable` extrait du titre
    (`LIV-aaaa-nnnn`), `EcartEcheance` = échéance du jalon différente de `Livrables.Echeance`.

Idempotent : une ligne n'est écrite que si au moins un champ a changé (`DateSynchro` est alors
mise à jour). Les lignes orphelines (jalon supprimé, sujet détaché ou projet retiré du sujet) sont
marquées `Orpheline` = Oui et signalées, jamais supprimées ; une ligne qui redevient valide repasse
à Non (spec § 10.3).

Configuration (variables d'environnement, jamais de secret dans le code ni dans le dépôt) :
  GITLAB_URL            ex. https://gitlab.example.com
  GITLAB_TOKEN          jeton d'accès de groupe, portée `read_api`
  HNCS_TENANT_ID        identifiant du tenant Entra
  HNCS_CLIENT_ID        identifiant de l'application Entra : `Lists.SelectedOperations.Selected`
                        (GitlabSync en écriture, SujetsRD et Livrables en lecture), à défaut
                        `Sites.Selected` en écriture sur le site (spec § 10.3, H-31)
  HNCS_CLIENT_SECRET    secret de l'application            } l'un ou l'autre
  HNCS_CLIENT_ASSERTION assertion JWT (identité fédérée     }
                        GitLab OIDC ou JWT signé par certificat, produit hors de ce script)
  HNCS_SITE_URL         ex. https://<tenant>.sharepoint.com/sites/HNCS-RD
Facultatives : HNCS_GRAPH_URL (défaut https://graph.microsoft.com/v1.0),
               HNCS_LOGIN_URL (défaut https://login.microsoftonline.com),
               HNCS_SITE_ID et HNCS_LISTE_ID_SUJETSRD / _LIVRABLES / _GITLABSYNC (identifiants Graph,
               non secrets) : obligatoires avec la permission `Lists.SelectedOperations.Selected`
               (spec § 10.3, H-31), qui ne donne accès ni au site ni à l'énumération de ses listes.

Usage :
    python gitlab/sync/sync_gitlab_sharepoint.py [--dry-run] [--sujet SUJ-aaaa-nnnn] [--verbose]

Codes de sortie : 0 succès ; 1 erreur pendant la synchronisation (au moins un projet ou une
écriture en échec) ; 2 configuration invalide ou erreur d'initialisation (jeton, site, listes).

Bibliothèque standard uniquement (urllib, json).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Any, Callable, Iterable, Iterator, Mapping, Optional

LOG = logging.getLogger("hncs.gitlabsync")

# --------------------------------------------------------------------------- constantes

LISTE_SUJETS = "SujetsRD"
LISTE_LIVRABLES = "Livrables"
LISTE_SYNC = "GitlabSync"
# Identifiants Graph facultatifs (mode `Lists.SelectedOperations.Selected`, spec § 10.3 / H-31).
VARIABLES_LISTES = {
    LISTE_SUJETS: "HNCS_LISTE_ID_SUJETSRD",
    LISTE_LIVRABLES: "HNCS_LISTE_ID_LIVRABLES",
    LISTE_SYNC: "HNCS_LISTE_ID_GITLABSYNC",
}

REGEX_LIVRABLE = re.compile(r"LIV-\d{4}-\d{4,}")
REGEX_SUJET = re.compile(r"^SUJ-\d{4}-\d{4,}$")

# Champs de `GitlabSync` (noms Graph) et nature utilisée pour la normalisation / comparaison.
# `Sujet` est une colonne de recherche : Graph l'expose et l'écrit sous `SujetLookupId`.
# `DateSynchro` n'est pas comparée : elle n'est réécrite que si un autre champ change.
CHAMPS_SYNC: dict[str, str] = {
    "Title": "texte",
    "CleSynchro": "texte",
    "SujetLookupId": "lookup",
    "GitlabProjetId": "entier",
    "Milestone": "texte",
    "MilestoneEcheance": "date",
    "MilestoneEtat": "texte",
    "IssuesOuvertes": "entier",
    "IssuesFermees": "entier",
    "MRsOuvertes": "entier",
    "DerniereActivite": "instant",
    "IdLivrable": "texte",
    "EcartEcheance": "booleen",
    "Orpheline": "booleen",
}
CHAMP_DATE_SYNCHRO = "DateSynchro"

STATUTS_A_REESSAYER = {429, 500, 502, 503, 504}
MAX_TENTATIVES = 5
DELAI_MAX_SECONDES = 120.0
TIMEOUT_HTTP = 60
PAR_PAGE_GITLAB = 100
PAR_PAGE_GRAPH = 500


class ErreurConfig(Exception):
    """Configuration absente ou invalide."""


class ErreurHttp(Exception):
    """Réponse HTTP en échec après les nouvelles tentatives éventuelles."""

    def __init__(self, methode: str, url: str, statut: int, extrait: str = "") -> None:
        self.methode = methode
        self.url = url
        self.statut = statut
        self.extrait = extrait
        super().__init__(f"{methode} {url} -> HTTP {statut} {extrait}".strip())


# --------------------------------------------------------------------------- fonctions pures

def extraire_id_livrable(titre: Optional[str]) -> Optional[str]:
    """Premier identifiant `LIV-aaaa-nnnn` trouvé dans le titre d'un jalon, sinon None."""
    if not titre:
        return None
    trouve = REGEX_LIVRABLE.search(titre)
    return trouve.group(0) if trouve else None


def cle_synchro(projet_id: int, milestone_id: Optional[int] = None) -> str:
    """Clé `CleSynchro` : `<projetId>:<milestoneId ou 0>` (0 = ligne de niveau projet)."""
    return f"{int(projet_id)}:{int(milestone_id) if milestone_id else 0}"


def _dernier_dimanche(annee: int, mois: int) -> date:
    fin = date(annee, 12, 31) if mois == 12 else date(annee, mois + 1, 1) - timedelta(days=1)
    return fin - timedelta(days=(fin.weekday() + 1) % 7)


def decalage_paris(instant_utc: datetime) -> timedelta:
    """Décalage UTC de l'heure de Paris (règle européenne : dernier dimanche de mars et
    d'octobre à 01:00 UTC). Calcul autonome pour ne pas dépendre de la base tzdata."""
    instant_utc = instant_utc.astimezone(timezone.utc)
    annee = instant_utc.year
    debut = datetime.combine(_dernier_dimanche(annee, 3), dtime(1, 0), tzinfo=timezone.utc)
    fin = datetime.combine(_dernier_dimanche(annee, 10), dtime(1, 0), tzinfo=timezone.utc)
    return timedelta(hours=2) if debut <= instant_utc < fin else timedelta(hours=1)


def _parser_instant(valeur: str) -> datetime:
    texte = valeur.strip()
    if texte.endswith("Z") or texte.endswith("z"):
        texte = texte[:-1] + "+00:00"
    instant = datetime.fromisoformat(texte)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc)


def normaliser_date(valeur: Any) -> Optional[str]:
    """Date calendaire `AAAA-MM-JJ`.

    GitLab renvoie `due_date` sous la forme `AAAA-MM-JJ`. Graph renvoie une colonne SharePoint
    « date seule » sous forme d'instant UTC (minuit heure de Paris, soit `…T22:00:00Z` ou
    `…T23:00:00Z` la veille) : l'instant est ramené à la date de Paris (fuseau du site, § 2.2).
    """
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, datetime):
        instant = valeur if valeur.tzinfo else valeur.replace(tzinfo=timezone.utc)
        instant = instant.astimezone(timezone.utc)
        return (instant + decalage_paris(instant)).date().isoformat()
    if isinstance(valeur, date):
        return valeur.isoformat()
    texte = str(valeur).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texte):
        return texte
    instant = _parser_instant(texte)
    return (instant + decalage_paris(instant)).date().isoformat()


def normaliser_instant(valeur: Any) -> Optional[str]:
    """Instant UTC tronqué à la minute (`AAAA-MM-JJTHH:MM:00Z`), précision commune à GitLab et
    SharePoint pour que la comparaison reste idempotente."""
    if valeur is None or valeur == "":
        return None
    instant = valeur if isinstance(valeur, datetime) else _parser_instant(str(valeur))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    instant = instant.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return instant.strftime("%Y-%m-%dT%H:%M:00Z")


def normaliser(nature: str, valeur: Any) -> Any:
    """Normalise une valeur lue (GitLab ou Graph) pour la comparer à la valeur cible."""
    if nature == "texte":
        if valeur is None:
            return None
        texte = str(valeur).strip()
        return texte or None
    if nature in ("entier", "lookup"):
        if valeur is None or valeur == "":
            return None
        entier = int(float(valeur))
        return str(entier) if nature == "lookup" else entier
    if nature == "booleen":
        if isinstance(valeur, str):
            return valeur.strip().lower() in ("true", "1", "oui", "yes")
        return bool(valeur)
    if nature == "date":
        return normaliser_date(valeur)
    if nature == "instant":
        return normaliser_instant(valeur)
    raise ValueError(f"Nature de champ inconnue : {nature}")


def serialiser(nature: str, valeur: Any) -> Any:
    """Valeur à envoyer à Graph pour une valeur normalisée."""
    if valeur is None:
        return None
    if nature == "date":
        # Midi UTC : la date reste la même quel que soit le fuseau appliqué par SharePoint.
        return f"{valeur}T12:00:00Z"
    if nature == "entier":
        return int(valeur)
    if nature == "booleen":
        return bool(valeur)
    if nature == "lookup":
        return str(valeur)
    return valeur


def calculer_ecart(echeance_jalon: Optional[str], echeance_livrable: Optional[str]) -> bool:
    """`EcartEcheance` : vrai si l'échéance du jalon diffère de `Echeance` du livrable.

    Livrable inconnu ou sans échéance -> pas d'écart calculable (False). Jalon sans échéance
    alors que le livrable en a une -> écart (lecture littérale de « ≠ »)."""
    if echeance_livrable is None:
        return False
    return echeance_jalon != echeance_livrable


@dataclass(frozen=True)
class Sujet:
    item_id: str
    id_hncs: Optional[str]
    projet_id: int


def lire_sujets(elements: Iterable[Mapping[str, Any]]) -> list[Sujet]:
    """Sujets ayant un `GitlabProjetId` (un projet ne peut être rattaché qu'à un seul sujet :
    en cas de doublon, le sujet de plus petit ID SharePoint est retenu et un avertissement émis)."""
    retenus: dict[int, Sujet] = {}
    candidats = []
    for element in elements:
        champs = element.get("fields") or {}
        brut = champs.get("GitlabProjetId")
        if brut is None or brut == "":
            continue
        try:
            projet_id = int(float(brut))
        except (TypeError, ValueError):
            LOG.warning("Sujet %s : GitlabProjetId illisible (%r), ignoré.", champs.get("IdHNCS") or element.get("id"), brut)
            continue
        if projet_id <= 0:
            continue
        candidats.append(Sujet(str(element.get("id")), normaliser("texte", champs.get("IdHNCS")), projet_id))
    for sujet in sorted(candidats, key=lambda s: int(s.item_id) if s.item_id.isdigit() else 0):
        if sujet.projet_id in retenus:
            LOG.warning(
                "Projet GitLab %s rattaché à plusieurs sujets (%s, %s) : seul %s est synchronisé.",
                sujet.projet_id, retenus[sujet.projet_id].id_hncs, sujet.id_hncs, retenus[sujet.projet_id].id_hncs,
            )
            continue
        retenus[sujet.projet_id] = sujet
    return list(retenus.values())


def indexer_livrables(elements: Iterable[Mapping[str, Any]]) -> dict[str, Optional[str]]:
    """`IdHNCS` du livrable -> échéance normalisée (`AAAA-MM-JJ`)."""
    index: dict[str, Optional[str]] = {}
    for element in elements:
        champs = element.get("fields") or {}
        id_hncs = normaliser("texte", champs.get("IdHNCS"))
        if id_hncs:
            index[id_hncs] = normaliser_date(champs.get("Echeance"))
    return index


@dataclass
class Jalon:
    id: int
    titre: str
    echeance: Optional[str]
    etat: Optional[str]
    issues_ouvertes: int
    issues_fermees: int
    mrs_ouvertes: int


@dataclass
class DonneesProjet:
    projet_id: int
    chemin: str
    derniere_activite: Optional[str]
    issues_ouvertes: int
    issues_fermees: int
    mrs_ouvertes: int
    jalons: list[Jalon] = field(default_factory=list)


def construire_lignes(sujet: Sujet, donnees: DonneesProjet, echeances_livrables: Mapping[str, Optional[str]]) -> list[dict[str, Any]]:
    """Lignes cibles de `GitlabSync` (valeurs normalisées, sans `DateSynchro`)."""
    activite = normaliser_instant(donnees.derniere_activite)
    lignes: list[dict[str, Any]] = [{
        "Title": donnees.chemin,
        "CleSynchro": cle_synchro(donnees.projet_id, 0),
        "SujetLookupId": normaliser("lookup", sujet.item_id),
        "GitlabProjetId": donnees.projet_id,
        "Milestone": None,
        "MilestoneEcheance": None,
        "MilestoneEtat": None,
        "IssuesOuvertes": donnees.issues_ouvertes,
        "IssuesFermees": donnees.issues_fermees,
        "MRsOuvertes": donnees.mrs_ouvertes,
        "DerniereActivite": activite,
        "IdLivrable": None,
        "EcartEcheance": False,
        "Orpheline": False,
    }]
    for jalon in sorted(donnees.jalons, key=lambda j: j.id):
        id_livrable = extraire_id_livrable(jalon.titre)
        echeance_jalon = normaliser_date(jalon.echeance)
        ecart = False
        if id_livrable:
            if len(REGEX_LIVRABLE.findall(jalon.titre)) > 1:
                LOG.warning("Jalon %s (%s) : plusieurs identifiants de livrable, %s retenu.", jalon.id, donnees.chemin, id_livrable)
            if id_livrable in echeances_livrables:
                ecart = calculer_ecart(echeance_jalon, echeances_livrables[id_livrable])
            else:
                LOG.warning("Jalon %s (%s) : livrable %s introuvable dans la liste Livrables.", jalon.id, donnees.chemin, id_livrable)
        lignes.append({
            "Title": donnees.chemin,
            "CleSynchro": cle_synchro(donnees.projet_id, jalon.id),
            "SujetLookupId": normaliser("lookup", sujet.item_id),
            "GitlabProjetId": donnees.projet_id,
            "Milestone": normaliser("texte", jalon.titre),
            "MilestoneEcheance": echeance_jalon,
            "MilestoneEtat": normaliser("texte", jalon.etat),
            "IssuesOuvertes": jalon.issues_ouvertes,
            "IssuesFermees": jalon.issues_fermees,
            "MRsOuvertes": jalon.mrs_ouvertes,
            "DerniereActivite": activite,
            "IdLivrable": id_livrable,
            "EcartEcheance": ecart,
            "Orpheline": False,
        })
    return lignes


@dataclass
class Plan:
    creations: list[dict[str, Any]] = field(default_factory=list)
    mises_a_jour: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)  # (itemId, clé, champs)
    inchangees: int = 0
    orphelines: list[str] = field(default_factory=list)

    @property
    def nb_ecritures(self) -> int:
        return len(self.creations) + len(self.mises_a_jour)


def _payload(ligne: Mapping[str, Any], noms: Iterable[str], date_synchro: str) -> dict[str, Any]:
    champs = {nom: serialiser(CHAMPS_SYNC[nom], ligne.get(nom)) for nom in noms}
    champs[CHAMP_DATE_SYNCHRO] = date_synchro
    return champs


def calculer_operations(
    lignes: Iterable[Mapping[str, Any]],
    existants: Iterable[Mapping[str, Any]],
    date_synchro: str,
    projets_ignores: Iterable[int] = (),
) -> Plan:
    """Compare les lignes cibles aux éléments existants de `GitlabSync` (clé `CleSynchro`).

    * clé absente -> création (tous les champs + `DateSynchro`) ;
    * clé présente et au moins un champ différent -> mise à jour des seuls champs modifiés
      + `DateSynchro` ;
    * rien de changé -> aucune écriture (idempotence) ;
    * clé existante sans ligne cible -> orpheline : `Orpheline` = Oui (+ `DateSynchro`) si elle ne
      l'est pas déjà, jamais supprimée ; sauf pour les projets en échec de lecture
      (`projets_ignores`), dont les lignes ne sont ni recalculées ni marquées ;
    * une ligne cible porte toujours `Orpheline` = Non : une ligne qui redevient valide est rétablie.
    """
    ignores = {int(p) for p in projets_ignores}
    index: dict[str, Mapping[str, Any]] = {}
    for element in existants:
        champs = element.get("fields") or {}
        cle = normaliser("texte", champs.get("CleSynchro"))
        if not cle:
            continue
        if cle in index:
            LOG.warning("Clé %s présente plusieurs fois dans GitlabSync : seul l'élément %s est mis à jour.", cle, index[cle].get("id"))
            continue
        index[cle] = element

    plan = Plan()
    vues: set[str] = set()
    for ligne in lignes:
        cle = ligne["CleSynchro"]
        if cle in vues:
            continue
        vues.add(cle)
        existant = index.get(cle)
        if existant is None:
            plan.creations.append(_payload(ligne, CHAMPS_SYNC, date_synchro))
            continue
        champs_existants = existant.get("fields") or {}
        modifies = [
            nom for nom, nature in CHAMPS_SYNC.items()
            if normaliser(nature, champs_existants.get(nom)) != ligne.get(nom)
        ]
        if modifies:
            plan.mises_a_jour.append((str(existant.get("id")), cle, _payload(ligne, modifies, date_synchro)))
        else:
            plan.inchangees += 1

    for cle in sorted(set(index) - vues):
        projet = cle.split(":", 1)[0]
        if projet.isdigit() and int(projet) in ignores:
            continue
        plan.orphelines.append(cle)
        existant = index[cle]
        if normaliser("booleen", (existant.get("fields") or {}).get("Orpheline")):
            plan.inchangees += 1
        else:
            plan.mises_a_jour.append((str(existant.get("id")), cle, {"Orpheline": True, CHAMP_DATE_SYNCHRO: date_synchro}))
    return plan


# --------------------------------------------------------------------------- configuration

@dataclass(frozen=True)
class Config:
    gitlab_url: str
    gitlab_token: str
    tenant_id: str
    client_id: str
    client_secret: Optional[str]
    client_assertion: Optional[str]
    site_hote: str
    site_chemin: str
    graph_url: str = "https://graph.microsoft.com/v1.0"
    login_url: str = "https://login.microsoftonline.com"
    site_id: Optional[str] = None
    listes_ids: Mapping[str, str] = field(default_factory=dict)

    def __repr__(self) -> str:  # jamais de secret dans les journaux
        return f"Config(gitlab_url={self.gitlab_url!r}, site={self.site_hote}{self.site_chemin}, client_id={self.client_id!r})"


def charger_config(env: Mapping[str, str]) -> Config:
    def lire(nom: str) -> str:
        return (env.get(nom) or "").strip()

    obligatoires = ["GITLAB_URL", "GITLAB_TOKEN", "HNCS_TENANT_ID", "HNCS_CLIENT_ID", "HNCS_SITE_URL"]
    manquantes = [nom for nom in obligatoires if not lire(nom)]
    secret = lire("HNCS_CLIENT_SECRET") or None
    assertion = lire("HNCS_CLIENT_ASSERTION") or None
    if not secret and not assertion:
        manquantes.append("HNCS_CLIENT_SECRET (ou HNCS_CLIENT_ASSERTION)")
    if manquantes:
        raise ErreurConfig("Variables d'environnement manquantes : " + ", ".join(manquantes))

    gitlab_url = lire("GITLAB_URL").rstrip("/")
    site = urllib.parse.urlsplit(lire("HNCS_SITE_URL"))
    for nom, url in (("GITLAB_URL", urllib.parse.urlsplit(gitlab_url)), ("HNCS_SITE_URL", site)):
        if url.scheme != "https" or not url.netloc:
            raise ErreurConfig(f"{nom} doit être une URL https complète.")
    chemin = site.path.rstrip("/")
    if not chemin.startswith("/sites/") and not chemin.startswith("/teams/"):
        raise ErreurConfig("HNCS_SITE_URL doit désigner un site (…/sites/HNCS-RD).")
    return Config(
        gitlab_url=gitlab_url,
        gitlab_token=lire("GITLAB_TOKEN"),
        tenant_id=lire("HNCS_TENANT_ID"),
        client_id=lire("HNCS_CLIENT_ID"),
        client_secret=secret,
        client_assertion=assertion,
        site_hote=site.netloc,
        site_chemin=chemin,
        graph_url=(lire("HNCS_GRAPH_URL") or "https://graph.microsoft.com/v1.0").rstrip("/"),
        login_url=(lire("HNCS_LOGIN_URL") or "https://login.microsoftonline.com").rstrip("/"),
        site_id=lire("HNCS_SITE_ID") or None,
        listes_ids={nom: lire(variable) for nom, variable in VARIABLES_LISTES.items() if lire(variable)},
    )


# --------------------------------------------------------------------------- HTTP

Reponse = tuple[int, dict[str, str], bytes]
Transport = Callable[[str, str, Mapping[str, str], Optional[bytes], int], Reponse]


def transport_urllib(methode: str, url: str, entetes: Mapping[str, str], corps: Optional[bytes], timeout: int) -> Reponse:
    requete = urllib.request.Request(url, data=corps, method=methode, headers=dict(entetes))
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:
            return reponse.status, {k.lower(): v for k, v in reponse.headers.items()}, reponse.read()
    except urllib.error.HTTPError as erreur:
        return erreur.code, {k.lower(): v for k, v in (erreur.headers or {}).items()}, erreur.read() or b""


def _url_journal(url: str) -> str:
    """URL sans paramètres de requête (évite de journaliser des données inutiles)."""
    morceaux = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((morceaux.scheme, morceaux.netloc, morceaux.path, "", ""))


class ClientHttp:
    """Requêtes JSON avec nouvelles tentatives sur 429 / 5xx / erreur réseau."""

    def __init__(self, transport: Transport = transport_urllib, attendre: Callable[[float], None] = time.sleep,
                 max_tentatives: int = MAX_TENTATIVES) -> None:
        self.transport = transport
        self.attendre = attendre
        self.max_tentatives = max_tentatives

    def requete(self, methode: str, url: str, entetes: Optional[Mapping[str, str]] = None,
                corps: Optional[bytes] = None) -> Reponse:
        entetes = dict(entetes or {})
        entetes.setdefault("Accept", "application/json")
        entetes.setdefault("User-Agent", "hncs-rd-gitlab-sync/1.0")
        for tentative in range(1, self.max_tentatives + 1):
            try:
                statut, reponse_entetes, contenu = self.transport(methode, url, entetes, corps, TIMEOUT_HTTP)
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as erreur:
                if tentative >= self.max_tentatives:
                    raise ErreurHttp(methode, _url_journal(url), 0, f"erreur réseau : {erreur}") from erreur
                delai = min(2.0 ** (tentative - 1), DELAI_MAX_SECONDES)
                LOG.warning("%s %s : erreur réseau (%s), nouvelle tentative %d/%d dans %.0f s.",
                            methode, _url_journal(url), erreur, tentative + 1, self.max_tentatives, delai)
                self.attendre(delai)
                continue
            reponse_entetes = {k.lower(): v for k, v in reponse_entetes.items()}
            if 200 <= statut < 300:
                return statut, reponse_entetes, contenu
            if statut in STATUTS_A_REESSAYER and tentative < self.max_tentatives:
                delai = self._delai(reponse_entetes.get("retry-after"), tentative)
                LOG.warning("%s %s : HTTP %d, nouvelle tentative %d/%d dans %.0f s.",
                            methode, _url_journal(url), statut, tentative + 1, self.max_tentatives, delai)
                self.attendre(delai)
                continue
            extrait = contenu[:300].decode("utf-8", "replace") if contenu else ""
            raise ErreurHttp(methode, _url_journal(url), statut, extrait)
        raise AssertionError("inatteignable")  # pragma: no cover

    @staticmethod
    def _delai(retry_after: Optional[str], tentative: int) -> float:
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), DELAI_MAX_SECONDES)
            except ValueError:
                pass
        return min(2.0 ** (tentative - 1), DELAI_MAX_SECONDES)

    def json(self, methode: str, url: str, entetes: Optional[Mapping[str, str]] = None,
             charge: Any = None) -> tuple[Any, dict[str, str]]:
        entetes = dict(entetes or {})
        corps = None
        if charge is not None:
            corps = json.dumps(charge, ensure_ascii=False).encode("utf-8")
            entetes["Content-Type"] = "application/json; charset=utf-8"
        _, reponse_entetes, contenu = self.requete(methode, url, entetes, corps)
        donnees = json.loads(contenu.decode("utf-8")) if contenu else None
        return donnees, reponse_entetes


# --------------------------------------------------------------------------- GitLab (lecture seule)

class ClientGitLab:
    def __init__(self, http: ClientHttp, base_url: str, jeton: str) -> None:
        self.http = http
        self.api = base_url.rstrip("/") + "/api/v4"
        self._entetes = {"PRIVATE-TOKEN": jeton}

    def _url(self, chemin: str, params: Optional[Mapping[str, Any]] = None) -> str:
        url = self.api + chemin
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        return url

    def get(self, chemin: str, params: Optional[Mapping[str, Any]] = None) -> tuple[Any, dict[str, str]]:
        return self.http.json("GET", self._url(chemin, params), self._entetes)

    def paginer(self, chemin: str, params: Optional[Mapping[str, Any]] = None) -> Iterator[Any]:
        """Parcourt toutes les pages en suivant l'en-tête `X-Next-Page`."""
        params = dict(params or {})
        params.setdefault("per_page", PAR_PAGE_GITLAB)
        page: Optional[str] = "1"
        while page:
            params["page"] = page
            donnees, entetes = self.get(chemin, params)
            for element in donnees or []:
                yield element
            page = (entetes.get("x-next-page") or "").strip() or None

    def compter(self, chemin: str, params: Optional[Mapping[str, Any]] = None) -> int:
        """Nombre d'éléments : en-tête `X-Total` si GitLab le fournit, sinon parcours complet."""
        params = dict(params or {})
        donnees, entetes = self.get(chemin, {**params, "per_page": 1, "page": 1})
        total = (entetes.get("x-total") or "").strip()
        if total.isdigit():
            return int(total)
        if not (entetes.get("x-next-page") or "").strip():
            return len(donnees or [])
        return sum(1 for _ in self.paginer(chemin, params))

    def projet(self, projet_id: int) -> dict[str, Any]:
        donnees, _ = self.get(f"/projects/{int(projet_id)}")
        return donnees

    def jalons(self, projet_id: int) -> list[dict[str, Any]]:
        return list(self.paginer(f"/projects/{int(projet_id)}/milestones"))

    def stats_issues(self, projet_id: int, titre_jalon: Optional[str] = None) -> tuple[int, int]:
        donnees, _ = self.get(f"/projects/{int(projet_id)}/issues_statistics", {"milestone": titre_jalon})
        compteurs = ((donnees or {}).get("statistics") or {}).get("counts") or {}
        return int(compteurs.get("opened") or 0), int(compteurs.get("closed") or 0)

    def mrs_ouvertes(self, projet_id: int, titre_jalon: Optional[str] = None) -> int:
        return self.compter(f"/projects/{int(projet_id)}/merge_requests", {"state": "opened", "milestone": titre_jalon})


def collecter_projet(gitlab: ClientGitLab, projet_id: int) -> DonneesProjet:
    projet = gitlab.projet(projet_id)
    ouvertes, fermees = gitlab.stats_issues(projet_id)
    donnees = DonneesProjet(
        projet_id=int(projet["id"]),
        chemin=projet.get("path_with_namespace") or str(projet_id),
        derniere_activite=projet.get("last_activity_at"),
        issues_ouvertes=ouvertes,
        issues_fermees=fermees,
        mrs_ouvertes=gitlab.mrs_ouvertes(projet_id),
    )
    for jalon in gitlab.jalons(projet_id):
        titre = jalon.get("title") or ""
        j_ouvertes, j_fermees = gitlab.stats_issues(projet_id, titre)
        donnees.jalons.append(Jalon(
            id=int(jalon["id"]),
            titre=titre,
            echeance=jalon.get("due_date"),
            etat=jalon.get("state"),
            issues_ouvertes=j_ouvertes,
            issues_fermees=j_fermees,
            mrs_ouvertes=gitlab.mrs_ouvertes(projet_id, titre),
        ))
    return donnees


# --------------------------------------------------------------------------- Microsoft Graph

class ClientGraph:
    def __init__(self, http: ClientHttp, config: Config) -> None:
        self.http = http
        self.config = config
        self._jeton: Optional[str] = None
        self._expiration = 0.0

    def jeton(self) -> str:
        if self._jeton and time.time() < self._expiration - 120:
            return self._jeton
        formulaire = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
            "scope": "https://graph.microsoft.com/.default",
        }
        if self.config.client_secret:
            formulaire["client_secret"] = self.config.client_secret
        else:
            formulaire["client_assertion_type"] = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
            formulaire["client_assertion"] = self.config.client_assertion or ""
        url = f"{self.config.login_url}/{urllib.parse.quote(self.config.tenant_id)}/oauth2/v2.0/token"
        _, _, contenu = self.http.requete(
            "POST", url, {"Content-Type": "application/x-www-form-urlencoded"},
            urllib.parse.urlencode(formulaire).encode("ascii"),
        )
        donnees = json.loads(contenu.decode("utf-8"))
        self._jeton = donnees["access_token"]
        self._expiration = time.time() + float(donnees.get("expires_in") or 3600)
        return self._jeton

    def _entetes(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.jeton()}"}

    def appel(self, methode: str, chemin_ou_url: str, charge: Any = None) -> Any:
        url = chemin_ou_url if chemin_ou_url.startswith("https://") else self.config.graph_url + chemin_ou_url
        donnees, _ = self.http.json(methode, url, self._entetes(), charge)
        return donnees

    def paginer(self, chemin: str) -> Iterator[dict[str, Any]]:
        """Parcourt toutes les pages en suivant `@odata.nextLink`."""
        url: Optional[str] = chemin
        while url:
            donnees = self.appel("GET", url) or {}
            for element in donnees.get("value") or []:
                yield element
            url = donnees.get("@odata.nextLink")

    def site_id(self) -> str:
        donnees = self.appel("GET", f"/sites/{self.config.site_hote}:{urllib.parse.quote(self.config.site_chemin)}")
        return donnees["id"]

    def listes(self, site_id: str, noms: Iterable[str]) -> dict[str, str]:
        """Nom interne (URL) de liste -> identifiant Graph."""
        voulus = set(noms)
        trouves: dict[str, str] = {}
        for liste in self.paginer(f"/sites/{site_id}/lists?$select=id,name,displayName,webUrl"):
            candidats = {liste.get("name"), (liste.get("webUrl") or "").rstrip("/").rsplit("/", 1)[-1]}
            for nom in voulus & {c for c in candidats if c}:
                trouves.setdefault(nom, liste["id"])
        absentes = voulus - set(trouves)
        if absentes:
            raise ErreurConfig("Listes introuvables sur le site : " + ", ".join(sorted(absentes)))
        return trouves

    def elements(self, site_id: str, liste_id: str, champs: Iterable[str]) -> list[dict[str, Any]]:
        selection = ",".join(champs)
        return list(self.paginer(
            f"/sites/{site_id}/lists/{liste_id}/items?expand=fields(select={selection})&$top={PAR_PAGE_GRAPH}"
        ))

    def creer(self, site_id: str, liste_id: str, champs: Mapping[str, Any]) -> Any:
        return self.appel("POST", f"/sites/{site_id}/lists/{liste_id}/items", {"fields": dict(champs)})

    def modifier(self, site_id: str, liste_id: str, item_id: str, champs: Mapping[str, Any]) -> Any:
        return self.appel("PATCH", f"/sites/{site_id}/lists/{liste_id}/items/{item_id}/fields", dict(champs))


# --------------------------------------------------------------------------- orchestration

def maintenant_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def resoudre_cibles(graph: ClientGraph, config: Config) -> tuple[str, dict[str, str]]:
    """Identifiants Graph du site et des trois listes.

    Avec `Lists.SelectedOperations.Selected` (recommandé, H-31), l'application n'a accès qu'aux listes
    octroyées : ni `GET /sites/{hôte}:{chemin}` ni l'énumération des listes ne sont permis. Les
    identifiants sont alors fournis par la configuration (`HNCS_SITE_ID`, `HNCS_LISTE_ID_*`) et aucune
    requête de niveau site n'est émise. Avec `Sites.Selected`, ils sont résolus automatiquement."""
    noms = [LISTE_SUJETS, LISTE_LIVRABLES, LISTE_SYNC]
    listes = {nom: config.listes_ids[nom] for nom in noms if config.listes_ids.get(nom)}
    try:
        site_id = config.site_id or graph.site_id()
        if len(listes) < len(noms):
            resolues = graph.listes(site_id, [nom for nom in noms if nom not in listes])
            listes.update(resolues)
    except ErreurHttp as erreur:
        if erreur.statut in (401, 403):
            raise ErreurConfig(
                f"{erreur}, accès refusé au niveau du site : avec Lists.SelectedOperations.Selected, "
                "renseigner HNCS_SITE_ID et HNCS_LISTE_ID_SUJETSRD / _LIVRABLES / _GITLABSYNC."
            ) from erreur
        raise
    return site_id, listes


def executer(config: Config, dry_run: bool = False, http: Optional[ClientHttp] = None,
             filtre_sujet: Optional[str] = None, horloge: Callable[[], str] = maintenant_utc) -> int:
    http = http or ClientHttp()
    gitlab = ClientGitLab(http, config.gitlab_url, config.gitlab_token)
    graph = ClientGraph(http, config)
    date_synchro = horloge()
    LOG.info("Synchronisation GitLab -> GitlabSync%s (site %s%s).", " [simulation]" if dry_run else "",
             config.site_hote, config.site_chemin)

    try:
        site_id, listes = resoudre_cibles(graph, config)
        sujets = lire_sujets(graph.elements(site_id, listes[LISTE_SUJETS], ["IdHNCS", "GitlabProjetId"]))
        echeances = indexer_livrables(graph.elements(site_id, listes[LISTE_LIVRABLES], ["IdHNCS", "Echeance"]))
        existants = graph.elements(site_id, listes[LISTE_SYNC], [*CHAMPS_SYNC, CHAMP_DATE_SYNCHRO])
    except (ErreurHttp, ErreurConfig, KeyError, ValueError) as erreur:
        LOG.error("Initialisation impossible : %s", erreur)
        return 2

    if filtre_sujet:
        sujets = [s for s in sujets if s.id_hncs == filtre_sujet]
        if not sujets:
            LOG.error("Sujet %s introuvable ou sans GitlabProjetId.", filtre_sujet)
            return 1
        existants = [e for e in existants
                     if normaliser("entier", (e.get("fields") or {}).get("GitlabProjetId")) == sujets[0].projet_id]
    LOG.info("%d sujet(s) avec projet GitLab, %d livrable(s), %d ligne(s) GitlabSync existante(s).",
             len(sujets), len(echeances), len(existants))

    erreurs = 0
    lignes: list[dict[str, Any]] = []
    en_echec: set[int] = set()
    for sujet in sujets:
        try:
            donnees = collecter_projet(gitlab, sujet.projet_id)
        except (ErreurHttp, KeyError, ValueError, TypeError) as erreur:
            erreurs += 1
            en_echec.add(sujet.projet_id)
            LOG.error("Sujet %s, projet %s : lecture GitLab impossible (%s).", sujet.id_hncs, sujet.projet_id, erreur)
            continue
        lignes_sujet = construire_lignes(sujet, donnees, echeances)
        lignes.extend(lignes_sujet)
        LOG.info("Sujet %s -> projet %s (%s) : %d jalon(s).", sujet.id_hncs, sujet.projet_id, donnees.chemin,
                 len(lignes_sujet) - 1)

    plan = calculer_operations(lignes, existants, date_synchro, en_echec)
    for cle in plan.orphelines:
        LOG.warning("Ligne GitlabSync %s sans correspondance GitLab (jalon supprimé, sujet détaché ou projet retiré) : "
                    "conservée, marquée Orpheline.", cle)
    LOG.info("Plan : %d création(s), %d mise(s) à jour, %d inchangée(s), %d orpheline(s).",
             len(plan.creations), len(plan.mises_a_jour), plan.inchangees, len(plan.orphelines))

    if dry_run:
        for champs in plan.creations:
            LOG.info("[simulation] créer %s", champs["CleSynchro"])
        for item_id, cle, champs in plan.mises_a_jour:
            LOG.info("[simulation] mettre à jour %s (élément %s) : %s", cle, item_id,
                     ", ".join(n for n in champs if n != CHAMP_DATE_SYNCHRO))
    else:
        for champs in plan.creations:
            try:
                graph.creer(site_id, listes[LISTE_SYNC], champs)
                LOG.info("Créé %s.", champs["CleSynchro"])
            except ErreurHttp as erreur:
                if erreur.statut == 409:
                    LOG.warning("Création %s refusée (clé déjà présente) : reprise au prochain passage.", champs["CleSynchro"])
                else:
                    erreurs += 1
                    LOG.error("Création %s impossible : %s", champs["CleSynchro"], erreur)
        for item_id, cle, champs in plan.mises_a_jour:
            try:
                graph.modifier(site_id, listes[LISTE_SYNC], item_id, champs)
                LOG.info("Mis à jour %s : %s.", cle, ", ".join(n for n in champs if n != CHAMP_DATE_SYNCHRO))
            except ErreurHttp as erreur:
                erreurs += 1
                LOG.error("Mise à jour %s impossible : %s", cle, erreur)

    if erreurs:
        LOG.error("Synchronisation terminée avec %d erreur(s).", erreurs)
        return 1
    LOG.info("Synchronisation terminée sans erreur.")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parseur = argparse.ArgumentParser(description="Synchronisation GitLab -> liste SharePoint GitlabSync (lecture seule GitLab).")
    parseur.add_argument("--dry-run", action="store_true", help="calcule et journalise les écritures sans rien écrire")
    parseur.add_argument("--sujet", metavar="SUJ-aaaa-nnnn", help="limite la synchronisation à un sujet")
    parseur.add_argument("--verbose", action="store_true", help="journal détaillé")
    arguments = parseur.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if arguments.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    if arguments.sujet and not REGEX_SUJET.match(arguments.sujet):
        LOG.error("--sujet attend un identifiant SUJ-aaaa-nnnn.")
        return 2
    try:
        config = charger_config(os.environ)
    except ErreurConfig as erreur:
        LOG.error("%s", erreur)
        return 2
    return executer(config, dry_run=arguments.dry_run, filtre_sujet=arguments.sujet)


if __name__ == "__main__":
    sys.exit(main())
