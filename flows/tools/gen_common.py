"""Briques métier partagées : contrôles G_*, squelette des flux de transition, créations idempotentes."""
from __future__ import annotations

from flowlib import (item_changes, obj_srv, sp_http, MODEL, SVC, SITE, TODAY, NOW, Seq, P, arr, at, compose, cond, create_with_id, ctl_msg, dfr,
                     dloc, ensure_idhncs, eval_controls, filt, foreach, get_item, get_items, grant_item, historize,
                     ip, item_link, log, notify, odata, odq, patch_item, post_item, q, select, switch, tech_error_check,
                     terminate, truthy, verify, autorise, flux_transition, html_table)

I_EL = "body('Lire_element')"
CTX_FORM = "Formalités d'intégration"
CTX_CLO = "Clôture d'alternance"


def first(action):
    return f"first(body('{action}')?['value'])"


def lookup_first(s, base, lst, id_expr, fields=()):
    """Lecture tolérante d'un élément par ID (tableau vide si l'ID est absent). Retourne l'expression de l'élément."""
    a = get_items(s, base, lst, filter_=f"ID eq @{{coalesce({id_expr}, 0)}}", fields=fields, top=1)
    return first(a)


# --------------------------------------------------------------------------------------------
# Contrôles G_* par objet : fonctions (s, tag) -> {code: (ok_expr, msg_expr)}
# --------------------------------------------------------------------------------------------

def blocking_bad_where():
    return ("and(equals(item()?['Bloquante'], true), not(or(and(equals(item()?['Statut']?['Value'], 'Terminée'), "
            "not(empty(item()?['Preuve']))), and(equals(item()?['Statut']?['Value'], 'Non applicable'), "
            "not(empty(item()?['Commentaire']))))))")


def candidature_controls(flow, I, ID, needed):
    flow.use("Candidatures", "ResponsableAnalyse", "AvisAnalyse", "DecideurFinal", "DateDecisionFinale", "Email", "Title",
             "DateDemarrageConfirmee", "DateFinPrevue", "Etablissement", "PolePressenti")

    def fn(s, tag):
        known = {}
        ent = {"G_ENTRETIEN_PLANIFIE", "G_AUCUN_ENTRETIEN_ACTIF", "G_ENTRETIEN_REALISE", "G_DECISION_FINALE"} & needed
        if ent:
            e = get_items(s, f"Entretiens_{tag}", "Entretiens", filter_=f"CandidatureId eq @{{{ID}}}",
                          fields=("Candidature", "Statut", "Resultat"))
            pl = filt(s, f"Entretiens_planifies_{tag}", f"body('{e}')?['value']", "equals(item()?['Statut']?['Value'], 'Planifié')")
            re_ = filt(s, f"Entretiens_realises_{tag}", f"body('{e}')?['value']", "equals(item()?['Statut']?['Value'], 'Réalisé')")
            rr = filt(s, f"Entretiens_resultat_{tag}", f"body('{re_}')", "not(empty(item()?['Resultat']?['Value']))")
            known["G_ENTRETIEN_PLANIFIE"] = (f"greater(length(body('{pl}')), 0)", ctl_msg("G_ENTRETIEN_PLANIFIE"))
            known["G_AUCUN_ENTRETIEN_ACTIF"] = (f"equals(length(body('{pl}')), 0)", ctl_msg("G_AUCUN_ENTRETIEN_ACTIF"))
            known["G_ENTRETIEN_REALISE"] = (f"greater(length(body('{rr}')), 0)", ctl_msg("G_ENTRETIEN_REALISE"))
            known["G_DECISION_FINALE"] = (f"and(not(empty({I}?['DecideurFinal']?['Email'])), greater(length(body('{re_}')), 0))",
                                          ctl_msg("G_DECISION_FINALE"))
        known["G_RESP_ANALYSE"] = (f"not(empty({I}?['ResponsableAnalyse']?['Email']))", ctl_msg("G_RESP_ANALYSE"))
        known["G_IDENTITE"] = (f"and(not(empty(trim(coalesce({I}?['Email'], '')))), not(startsWith(coalesce({I}?['Title'], ''), 'À qualifier')))",
                               ctl_msg("G_IDENTITE"))
        known["G_DECIDEUR"] = (f"not(empty({I}?['DecideurFinal']?['Email']))", ctl_msg("G_DECIDEUR"))
        known["G_AVIS_ANALYSE"] = (f"not(empty(trim(coalesce({I}?['AvisAnalyse'], ''))))", ctl_msg("G_AVIS_ANALYSE"))
        if "G_INTEGRATION" in needed:
            a = get_items(s, f"Actions_formalites_{tag}", "ActionsIntegration",
                          filter_=f"CandidatureId eq @{{{ID}}} and Contexte eq {odata(CTX_FORM)}",
                          fields=("Candidature", "Contexte", "Bloquante", "Statut", "Preuve", "Commentaire"))
            bad = filt(s, f"Actions_bloquantes_ouvertes_{tag}", f"body('{a}')?['value']", blocking_bad_where())
            detail = (f"concat(if(empty({I}?['DateDecisionFinale']), '(a) date de décision finale manquante ; ', ''), "
                      f"if(or(empty({I}?['DateDemarrageConfirmee']), empty({I}?['DateFinPrevue'])), '(b) dates de démarrage et de fin prévues à renseigner ; ', ''), "
                      f"if(or(empty({I}?['Etablissement']?['Id']), empty({I}?['PolePressenti']?['Id'])), '(c) établissement et pôle pressenti à renseigner ; ', ''), "
                      f"if(equals(length(body('{a}')?['value']), 0), '(d) aucune action de formalités ; ', ''), "
                      f"if(greater(length(body('{bad}')), 0), concat('(e) actions bloquantes non terminées avec preuve : ', "
                      f"join(body('Select_{bad}'), ', ')), ''))")
            select(s, f"Select_{bad}", f"body('{bad}')", at("coalesce(item()?['IdHNCS'], string(item()?['ID']))"))
            flow.use("ActionsIntegration", "IdHNCS", "ID")
            ok = (f"and(not(empty({I}?['DateDecisionFinale'])), not(empty({I}?['DateDemarrageConfirmee'])), "
                  f"not(empty({I}?['DateFinPrevue'])), not(empty({I}?['Etablissement']?['Id'])), "
                  f"not(empty({I}?['PolePressenti']?['Id'])), greater(length(body('{a}')?['value']), 0), "
                  f"equals(length(body('{bad}')), 0))")
            known["G_INTEGRATION"] = (ok, ctl_msg("G_INTEGRATION", detail))
        return {k: v for k, v in known.items() if k in needed}
    return fn


def capitalisation_parts(s, flow, I, ID, tag):
    """Évalue G_CAPITALISATION ; retourne (ok_expr, detail_expr)."""
    flow.use("Livrables", "LienDocument", "TypeLivrable", "DoD1Fonctionnel", "DoD2FicheMethodo", "DoD3Restitution",
             "DoD4SupportCom", "DoD5Enseignements")
    d = get_items(s, f"Documents_cap_{tag}", "LivrablesRD", filter_=f"LivrableId eq @{{{ID}}}",
                  fields=("Livrable", "Sujet", "TypeDocument"))
    inc = filt(s, f"Documents_incomplets_{tag}", f"body('{d}')?['value']",
               "or(empty(item()?['Sujet']?['Id']), empty(item()?['TypeDocument']?['Value']))")
    in_lib = f"contains(toLower(coalesce({I}?['LienDocument'], '')), toLower(concat(uriPath({SITE}), '/LivrablesRD/')))"
    docs_ok = f"or(not({in_lib}), and(greater(length(body('{d}')?['value']), 0), equals(length(body('{inc}')), 0)))"
    poc = f"contains(createArray('POC / démonstrateur', 'Plan de stratégie'), {I}?['TypeLivrable']?['Value'])"
    dod = (f"and({truthy(I + "?['DoD1Fonctionnel']")}, {truthy(I + "?['DoD2FicheMethodo']")}, {truthy(I + "?['DoD3Restitution']")}, "
           f"{truthy(I + "?['DoD4SupportCom']")}, {truthy(I + "?['DoD5Enseignements']")})")
    dod_ok = f"or(not({poc}), {dod})"
    ok = f"and(not(empty({I}?['LienDocument'])), {docs_ok}, {dod_ok})"
    detail = (f"concat(if(empty({I}?['LienDocument']), 'lien du document (LienDocument) manquant ; ', ''), "
              f"if({docs_ok}, '', 'document de « 04 : Livrables R&D » sans Sujet ou Type de document ; '), "
              f"if({dod_ok}, '', 'Definition of Done incomplète (5 critères requis pour un POC ou un plan) ; '))")
    return ok, detail, d


def valideur_legitime(flow, acteur, ref_compte, valideur, auteur):
    """G_VALIDEUR_LEGITIME : référent de l'affectation, ou membre de DIRECTION_RD désigné comme valideur ;
    jamais l'auteur (ITEM_AUTEUR)."""
    drd = flow.group_emails("G_DRD")
    return (f"and(or(equals({acteur}, toLower(coalesce({ref_compte}, '#'))), and(contains(split({drd}, ';'), {acteur}), "
            f"equals({acteur}, toLower(coalesce({valideur}, '#'))))), not(equals({acteur}, toLower(coalesce({auteur}, '#')))))")


def livrable_controls(flow, I, ID, needed, acteur=None, ref_compte=None):
    flow.use("Livrables", "LienDocument", "CommentaireRevue", "EmpreinteCommentaire", "Proprietaire", "Reviseur")

    def fn(s, tag):
        known = {}
        if "G_DOCUMENT" in needed:
            d = get_items(s, f"Documents_{tag}", "LivrablesRD", filter_=f"LivrableId eq @{{{ID}}}", fields=("Livrable",))
            known["G_DOCUMENT"] = (f"or(not(empty({I}?['LienDocument'])), greater(length(body('{d}')?['value']), 0))",
                                   ctl_msg("G_DOCUMENT"))
        cur = f"trim(coalesce({I}?['CommentaireRevue'], ''))"
        known["G_COMMENTAIRE_REVUE"] = (f"and(not(empty({cur})), not(equals({cur}, trim(coalesce({I}?['EmpreinteCommentaire'], '')))))",
                                        ctl_msg("G_COMMENTAIRE_REVUE"))
        if "G_VALIDEUR_LEGITIME" in needed:
            known["G_VALIDEUR_LEGITIME"] = (valideur_legitime(flow, acteur, ref_compte, f"{I}?['Reviseur']?['Email']",
                                                              f"{I}?['Proprietaire']?['Email']"), ctl_msg("G_VALIDEUR_LEGITIME"))
        if "G_CAPITALISATION" in needed:
            ok, detail, _ = capitalisation_parts(s, flow, I, ID, tag)
            known["G_CAPITALISATION"] = (ok, ctl_msg("G_CAPITALISATION", detail))
        return {k: v for k, v in known.items() if k in needed}
    return fn


def cr_controls(flow, I, needed, acteur=None, ref_compte=None, auteur=None):
    flow.use("ComptesRendus", "Realisations", "ProchainesEtapes", "Avancement", "Echeance", "CommentaireReferent", "Valideur")

    def fn(s, tag):
        known = {
            "G_VALIDEUR_LEGITIME": ((valideur_legitime(flow, acteur, ref_compte, f"{I}?['Valideur']?['Email']", auteur)
                                     if acteur else "false"), ctl_msg("G_VALIDEUR_LEGITIME")),
            "G_CR_COMPLET": (f"and(not(empty(trim(coalesce({I}?['Realisations'], '')))), not(empty(trim(coalesce({I}?['ProchainesEtapes'], '')))), not(equals({I}?['Avancement'], null)))",
                             ctl_msg("G_CR_COMPLET")),
            "G_CR_ECHU": (f"and(not(empty({I}?['Echeance'])), greater({TODAY}, addDays({dloc(I + "?['Echeance']")}, int({P('CR.DelaiNonRemisJours', '3')}), 'yyyy-MM-dd')))",
                          ctl_msg("G_CR_ECHU")),
            "G_COMMENTAIRE_REFERENT": (f"not(empty(trim(coalesce({I}?['CommentaireReferent'], ''))))", ctl_msg("G_COMMENTAIRE_REFERENT")),
        }
        return {k: v for k, v in known.items() if k in needed}
    return fn


def affectation_controls(flow, I, ID, needed, alt_expr, ref_expr):
    flow.use("Affectations", "Alternant", "Sujet", "Referent", "DateDebut", "DateFin")
    flow.use("Alternants", "Statut", "CompteM365")
    flow.use("Referents", "Statut")

    def fn(s, tag):
        known = {
            "G_AFFECTATION_COMPLETE": (
                f"and(not(empty({I}?['Alternant']?['Id'])), not(empty({I}?['Sujet']?['Id'])), not(empty({I}?['Referent']?['Id'])), "
                f"not(empty({I}?['DateDebut'])), contains(createArray('À intégrer', 'Actif'), coalesce({alt_expr}?['Statut']?['Value'], '')), "
                f"not(empty({alt_expr}?['CompteM365']?['Email'])), "
                f"equals(coalesce({ref_expr}?['Statut']?['Value'], ''), 'Actif'))", ctl_msg("G_AFFECTATION_COMPLETE")),
            "G_DATE_FIN": (f"not(empty({I}?['DateFin']))", ctl_msg("G_DATE_FIN")),
        }
        if "G_LIVRABLES_CLOS" in needed:
            lv = get_items(s, f"Livrables_ouverts_{tag}", "Livrables",
                           filter_=(f"AffectationId eq @{{{ID}}} and (Statut eq 'À produire' or Statut eq 'En cours' or "
                                    f"Statut eq 'Soumis à revue' or Statut eq 'En revue' or Statut eq 'Corrections demandées')"),
                           fields=("Affectation", "Statut"))
            known["G_LIVRABLES_CLOS"] = (f"equals(length(body('{lv}')?['value']), 0)", ctl_msg("G_LIVRABLES_CLOS"))
        return {k: v for k, v in known.items() if k in needed}
    return fn


def alternant_controls(flow, I, ID, needed, avant_expr, is_flux_expr="false"):
    flow.use("Alternants", "DateDebut", "DateFin", "CandidatureSource")

    def fn(s, tag):
        known = {"G_DATE_DEBUT_ATTEINTE": (
            f"or(equals({avant_expr}, 'Suspendu'), and(not(empty({I}?['DateDebut'])), lessOrEquals({dloc(I + "?['DateDebut']")}, {TODAY})))",
            ctl_msg("G_DATE_DEBUT_ATTEINTE")),
            "G_DATE_FIN_REPORTEE": (
            f"and(not(empty({I}?['DateFin'])), greater({dloc(I + "?['DateFin']")}, addDays({TODAY}, int({P('Fin.AnticipationJours', '30')}), 'yyyy-MM-dd')))",
            ctl_msg("G_DATE_FIN_REPORTEE"))}
        if "G_SOURCE_ALTERNANT" in needed:
            c = lookup_first(s, f"Candidature_source_{tag}", "Candidatures", f"{I}?['CandidatureSource']?['Id']", fields=("Statut",))
            known["G_SOURCE_ALTERNANT"] = (
                f"if({is_flux_expr}, and(not(empty({I}?['CandidatureSource']?['Id'])), equals(coalesce({c}?['Statut']?['Value'], ''), 'Intégrée')), "
                f"and(empty({I}?['CandidatureSource']?['Id']), equals({P('Fonction.RepriseExistantActive', 'Non')}, 'Oui')))",
                ctl_msg("G_SOURCE_ALTERNANT"))
        if "G_CLOTURE_ALTERNANCE" in needed:
            a = get_items(s, f"Actions_cloture_{tag}", "ActionsIntegration",
                          filter_=f"AlternantId eq @{{{ID}}} and Contexte eq 'Clôture d''alternance'",
                          fields=("Alternant", "Contexte", "Bloquante", "Statut", "Preuve", "Commentaire"))
            bad = filt(s, f"Actions_cloture_ouvertes_{tag}", f"body('{a}')?['value']", blocking_bad_where())
            b = get_items(s, f"Bilans_realises_{tag}", "BilansAlternance",
                          filter_=f"AlternantId eq @{{{ID}}} and Statut eq 'Réalisé'", fields=("Alternant", "Statut"))
            known["G_CLOTURE_ALTERNANCE"] = (
                f"and(equals(length(body('{bad}')), 0), greater(length(body('{b}')?['value']), 0))",
                ctl_msg("G_CLOTURE_ALTERNANCE", f"concat(if(greater(length(body('{bad}')), 0), concat(string(length(body('{bad}'))), ' action(s) bloquante(s) de clôture non terminée(s) ; '), ''), if(equals(length(body('{b}')?['value']), 0), 'aucun bilan « Réalisé » ; ', ''))"))
        return {k: v for k, v in known.items() if k in needed}
    return fn


def communication_controls(flow, I, needed):
    flow.use("CommunicationsRD", "AutorisationsTiers", "DateEffective", "UrlPublication", "Externe")

    def fn(s, tag):
        known = {
            "G_AUTORISATIONS": (f"contains(createArray('Non requise', 'Obtenue'), coalesce({I}?['AutorisationsTiers']?['Value'], 'Non requise'))",
                                ctl_msg("G_AUTORISATIONS")),
            "G_PUBLICATION": (f"and(not(empty({I}?['DateEffective'])), or(not({truthy(I + "?['Externe']")}), not(empty({I}?['UrlPublication']))))",
                              ctl_msg("G_PUBLICATION")),
        }
        return {k: v for k, v in known.items() if k in needed}
    return fn


def convention_controls(flow, I, needed, is_flux_expr):
    flow.use("Conventions", "DateSignature", "PreuveSignature", "DateFin", "TypeConvention", "DecisionPartenariat", "DecideurPartenariat",
             "EmpreinteDecision")

    def fn(s, tag):
        known = {
            "G_DECISION_PARTENARIAT": (
                f"or(not(contains(createArray('Convention de partenariat', 'Sponsoring'), coalesce({I}?['TypeConvention']?['Value'], ''))), "
                f"and(contains(createArray('Partenariat retenu', 'Sponsoring retenu'), coalesce({I}?['DecisionPartenariat']?['Value'], '')), "
                f"equals(coalesce({I}?['DecisionPartenariat']?['Value'], ''), coalesce({I}?['EmpreinteDecision'], '')), "
                f"not(empty({I}?['DecideurPartenariat']?['Email']))))", ctl_msg("G_DECISION_PARTENARIAT")),
            "G_PREUVE_SIGNATURE": (f"and(not(empty({I}?['DateSignature'])), not(empty({I}?['PreuveSignature'])))",
                                   ctl_msg("G_PREUVE_SIGNATURE")),
            "G_DATE_FIN_DEPASSEE": (f"or(not({is_flux_expr}), and(not(empty({I}?['DateFin'])), less({dloc(I + "?['DateFin']")}, {TODAY})))",
                                    ctl_msg("G_DATE_FIN_DEPASSEE")),
        }
        return {k: v for k, v in known.items() if k in needed}
    return fn


def sujet_controls(flow, I, needed):
    flow.use("SujetsRD", "MotifDecision")

    def fn(s, tag):
        known = {"G_MOTIF_DECISION": (f"not(empty(trim(coalesce({I}?['MotifDecision'], ''))))", ctl_msg("G_MOTIF_DECISION"))}
        return {k: v for k, v in known.items() if k in needed}
    return fn


def controls_needed_for(base_code):
    s = set()
    for t in MODEL.transitions_of([base_code]):
        s.update(t["controls"])
    return s


# --------------------------------------------------------------------------------------------
# Squelette d'un flux de transition (déclenché par une modification humaine)
# --------------------------------------------------------------------------------------------

class Env(dict):
    __getattr__ = dict.get


HIST = "HistoriqueStatuts"


def ref_status(s, lst, id_expr, tag):
    """Statut validé de référence (P-09, § 8.1) : dernier `StatutApres` accepté dans `HistoriqueStatuts` pour l'élément
    (Liste + ItemId ; les entrées REPRISE comptent, les entrées hors statut `REF-PRINCIPAL` sont exclues) ; à défaut : `∅`.
    Jamais `StatutPrecedent`."""
    h = get_items(s, f"Historique_{tag}", HIST, filter_=f"Liste eq '{lst}' and ItemId eq @{{{id_expr}}} and Resultat eq {odata(MODEL.enums['RESULTAT_TRANSITION'][0])}",
                  fields=("Liste", "ItemId", "Resultat", "StatutApres", "CodeTransition", "ID"), order="ID desc", top=100)
    fl = filt(s, f"Transitions_acceptees_{tag}", f"body('{h}')?['value']", "not(equals(coalesce(item()?['CodeTransition'], ''), 'REF-PRINCIPAL'))")
    c = compose(s, f"Statut_valide_{tag}", at(f"if(empty(body('{fl}')), '∅', coalesce(first(body('{fl}'))?['StatutApres'], '∅'))"))
    return f"outputs('{c}')"


def write_reprise(s, lst, objet, id_expr, idobj_expr, statut_expr, tag=""):
    """Entrée HistoriqueStatuts de reprise de l'existant (6.1, point 3 ter) : CodeTransition REPRISE, StatutAvant ∅,
    StatutApres = statut courant, Origine Flux, Résultat Acceptée, motif « Reprise de l'existant »."""
    return post_item(s, f"Historiser_reprise{tag}", HIST, {
        "Title": ip(idobj_expr), "Objet": objet, "Liste": lst, "ItemId": at(f"int({id_expr})"), "StatutAvant": "∅",
        "StatutApres": ip(statut_expr), "CodeTransition": "REPRISE", "Acteur": ip(SVC), "ActeurEmail": ip(SVC),
        "DateChangement": ip("utcNow()"), "Origine": "Flux", "Resultat": MODEL.enums["RESULTAT_TRANSITION"][0],
        "Motif": "Reprise de l'existant", "FluxRunId": ip("workflow()?['run']?['name']")})


def flux_columns(lst):
    return [(n, c["type"]) for n, c in MODEL.columns(lst).items() if c.get("flux")]


MERGE_HEADERS = {"Accept": "application/json;odata=verbose", "Content-Type": "application/json;odata=verbose",
                 "IF-MATCH": "*", "X-HTTP-Method": "MERGE"}


def restore_flux_columns(s, lst, id_expr, idobj_expr, acteur):
    """§ 8.1 « Colonnes techniques » : si la dernière modification (humaine) a changé une colonne `flux`, la rétablir à sa valeur
    de la version précédente (API des versions), journaliser (Avertissement), N-92, puis poursuivre sur les valeurs rétablies."""
    flow = s.flow
    cols = flux_columns(lst)
    flow.use(lst, *[n for n, _ in cols])
    srv = obj_srv(lst)
    base = f"concat('_api/web/GetList(''', {srv}, ''')/items(', string({id_expr}), ')"
    vs = sp_http(s, "Versions_element", "GET", ip(f"{base}/versions?$orderby=VersionId desc&$top=2')"))
    V = f"body('{vs}')?['value']"
    cur, prev = f"first({V})", f"{V}?[1]"

    def check(y):
        ch = item_changes(y, "Modifications_depuis_version_precedente", lst, id_expr, since=f"string({prev}?['VersionLabel'])")
        changed = filt(y, "Colonnes_techniques_modifiees", arr([n for n, _ in cols]),
                       f"equals(string(coalesce(body('{ch}')?['ColumnHasChanged']?[item()], false)), 'True')")

        def restore(z):
            te = sp_http(z, "Type_entite_colonnes_techniques", "GET",
                         ip(f"concat('_api/web/GetList(''', {srv}, ''')?$select=ListItemEntityTypeFullName')"))
            body = {"__metadata": {"type": ip(f"body('{te}')?['ListItemEntityTypeFullName']")}}
            for n, t in cols:
                pv = f"{prev}?['{n}']"
                if t in ("Lookup", "User"):
                    body[f"{n}Id"] = at(f"if(empty({pv}), null, {pv}?['LookupId'])")
                elif t == "URL":
                    u = compose(z, f"Lien_{n}", {"__metadata": {"type": "SP.FieldUrlValue"},
                                                 "Url": ip(f"coalesce({pv}?['Url'], string({pv}))"),
                                                 "Description": ip(f"coalesce({pv}?['Description'], {pv}?['Url'], string({pv}))")})
                    body[n] = at(f"if(empty({pv}), null, outputs('{u}'))")
                else:
                    body[n] = at(pv)
            c = compose(z, "Valeurs_techniques_precedentes", body)
            sp_http(z, "Retablir_colonnes_techniques", "POST", ip(f"{base}')"), body=ip(f"outputs('{c}')"), headers=dict(MERGE_HEADERS))
            log(z, "Colonnes_techniques_retablies", "Avertissement",
                f"concat('P-09 : colonne(s) technique(s) modifiée(s) hors flux, rétablie(s) : ', join(body('{changed}'), ', '))",
                lst, id_expr, idobj_expr)
            lien = f"concat({SITE}, '/{lst}')" if MODEL.is_library(lst) else item_link(lst, id_expr)
            notify(z, "N-92", [acteur], {"IdHNCS": idobj_expr, "Champs": f"join(body('{changed}'), ', ')",
                                         "RoleHabilite": q("Aucun : colonne technique écrite uniquement par les flux (compte de service)"),
                                         "Lien": lien}, teams_to=[acteur])
        cond(y, "Si_colonne_technique_modifiee", f"greater(length(body('{changed}')), 0)", restore)
    cond(s, "Si_modification_humaine_a_verifier",
         f"and(greater(length(coalesce({V}, createArray())), 1), not(equals(toLower(coalesce({cur}?['Editor']?['Email'], '')), toLower({SVC}))))",
         check, after={vs: ["Succeeded", "Failed"]})


def transition_body(s: Seq, flow, lst, objet, *, effects=None, pre=None, post=None, auteur=None, valideur=None,
                    controls=None, with_id=True, effects_before_history=True, on_refuse=None, restore=True):
    """Corps standard (§ 8.1, § 6.1) :

    lecture fraîche de l'élément → événement obsolète ignoré → IdHNCS → [pré-traitement] →
    colonnes techniques rétablies d'abord ; statut validé = dernière transition acceptée de l'historique ;
    si Statut ≠ statut validé et statut cible du flux : PA-00A → contrôles G_* → refus : PA-00B (annulation) et fin ;
    acceptation : effets par statut cible → PA-00B (acceptée) → [post-traitement reprenable].
    """
    I = I_EL
    flow.use(lst, "ID", "Statut")
    if restore:
        restore_flux_columns(s, lst, "triggerOutputs()?['body/ID']", "coalesce(triggerOutputs()?['body/IdHNCS'], '')",
                             "toLower(coalesce(triggerOutputs()?['body/Editor/Email'], ''))")
    get_item(s, "Lire_element", lst, "triggerOutputs()?['body/ID']")
    cond(s, "Si_evenement_obsolete", f"not(equals({I}?['Statut']?['Value'], triggerOutputs()?['body/Statut/Value']))",
         lambda y: terminate(y, "Fin_evenement_obsolete"))
    ID = f"{I}?['ID']"
    idobj = ensure_idhncs(s, lst, I, ID, "el") if (with_id and MODEL.obj(lst)["prefix"]) else f"string({ID})"
    hist = ref_status(s, lst, ID, "el")
    # Reprise de l'existant : sans transition acceptée, l'élément n'est une création que s'il est à sa première version
    # (Created = Modified de l'événement déclencheur) ; sinon son statut courant devient le statut de référence (entrée REPRISE).
    creation = "equals(string(triggerOutputs()?['body/Created']), string(triggerOutputs()?['body/Modified']))"
    reprise = f"and(equals({hist}, '∅'), not({creation}), not(empty({I}?['Statut']?['Value'])))"
    if restore:  # flux propriétaire de la liste : écrit l'entrée REPRISE (une seule entrée par élément)
        cond(s, "Si_reprise_existant", reprise, lambda y: write_reprise(y, lst, objet, ID, idobj, f"{I}?['Statut']?['Value']"))
    ref = compose(s, "Statut_reference", at(f"if({reprise}, {I}?['Statut']?['Value'], {hist})"))
    avant = f"outputs('{ref}')"
    env = Env(I=I, ID=ID, IDOBJ=idobj, AVANT=avant, APRES=f"{I}?['Statut']?['Value']",
              ACTEUR="toLower(coalesce(triggerOutputs()?['body/Editor/Email'], ''))", LIEN=item_link(lst, ID), LST=lst)
    if pre:
        pre(s, env)
    targets = flow.targets
    for t in MODEL.transitions:
        if t["object"] == objet and t["to"] in targets:
            flow.trans(t["baseCode"])

    a_traiter = f"and(not(equals({env.APRES}, {env.AVANT})), contains({arr(targets)}, {env.APRES}))"

    def nothing(y):
        if post:
            post(y, Env(env, NOTRANS=True))
        terminate(y, "Fin_sans_transition")
    cond(s, "Si_aucune_transition_a_traiter", f"not({a_traiter})", nothing)
    v = verify(s, "Verifier_transition", objet, env.AVANT, env.APRES, env.ACTEUR,
               (auteur(env) if auteur else "''"), (valideur(env) if valideur else "''"))
    tech_error_check(s, v, lst, ID, idobj)
    known = controls(s, "el") if controls else {}
    ok_all, motif = eval_controls(s, v, known, "el")
    motif_refus = f"if({autorise(v)}, {motif}, coalesce(body('{v}')?['Motif'], 'Transition non autorisée'))"

    def refused(z):
        historize(z, "Annuler_transition", lst, ID, idobj, objet, env.AVANT, env.APRES, False,
                  f"body('{v}')?['CodeTransition']", env.ACTEUR, "Humain", motif_refus)
        if on_refuse:
            on_refuse(z, env)
        terminate(z, "Fin_transition_refusee")
    cond(s, "Si_transition_refusee", f"not(and({autorise(v)}, {ok_all}))", refused)
    if effects:
        cases = {st: (lambda fn: (lambda zz: fn(zz, env)))(fn) for st, fn in effects.items() if fn}
        if cases:
            switch(s, "Effets_par_statut", env.APRES, cases)
    historize(s, "Historiser_transition", lst, ID, idobj, objet, env.AVANT, env.APRES, True,
              f"body('{v}')?['CodeTransition']", env.ACTEUR, "Humain")
    if post:
        post(s, env)
    return env


def flux_creation(s, tag, objet, liste, id_expr, idobj_expr, status, base_code, controls_fn=None):
    """Création par le compte de service (statut initial déjà écrit) : PA-00A (FLUX, ∅ → statut) [+ contrôles] puis PA-00B."""
    flow = s.flow
    flow.trans(base_code)
    flow.status(liste, status)
    v = verify(s, f"Verifier_{tag}", objet, q("∅"), q(status), SVC)
    ok_all = "true"
    if controls_fn:
        ok_all, _ = eval_controls(s, v, controls_fn(s, tag), tag)
    cond(s, f"Si_{tag}_autorisee", f"and({autorise(v)}, {ok_all})",
         lambda y: historize(y, f"Historiser_{tag}", liste, id_expr, idobj_expr, objet, q("∅"), q(status), True,
                             f"body('{v}')?['CodeTransition']", SVC, "Flux"),
         lambda n: log(n, f"Creation_non_historisee_{tag}", "Avertissement",
                       f"concat({q(base_code + ' (FLUX) refusée : ')}, coalesce(body('{v}')?['Motif'], ''))", liste, id_expr, idobj_expr))


# --------------------------------------------------------------------------------------------
# Actions de checklist générées depuis ModelesActions (idempotentes par CodeModeleAction)
# --------------------------------------------------------------------------------------------

def role_map(resp_analyse=None, referent=None, eco_resp=None):
    """Résolution RoleResponsable → personne (§ 8.1). Les rôles sans personne résolue restent vides."""
    m = {"ADMIN": P("Destinataires.Administration"),
         "RD": (f"if(empty({resp_analyse}), {P('Destinataires.DirectionRD')}, {resp_analyse})" if resp_analyse
                else P("Destinataires.DirectionRD")),
         "DIRECTION_RD": P("Destinataires.DirectionRD"),
         "PROPRIETAIRE": P("Destinataires.Support")}
    if referent:
        m["REFERENT"] = referent
    if eco_resp:
        m["ECOLES"] = eco_resp
    return m


def emp_action(src):
    """EmpreinteAction : JSON {Bloquante, Statut} (P-09, G_ACTION_FORMALITE)."""
    return ("concat('{\"Bloquante\":', if(equals(" + src + "?['Bloquante'], true), 'true', 'false'), ',\"Statut\":\"', "
            "coalesce(" + src + "?['Statut']?['Value'], ''), '\"}')")


def role_resolution(role_expr, mapping: dict):
    e = "''"
    for role, email in reversed(list(mapping.items())):
        e = f"if(equals({role_expr}, {q(role)}), coalesce({email}, ''), {e})"
    return e


def generate_actions(s, tag, contexte, links: dict, key_filter, base_date_expr, role_map: dict):
    """Crée une action par modèle actif du contexte, si aucune action liée ne porte déjà ce ``CodeModeleAction``.

    ``links`` : {colonne lookup: expression ID}. ``key_filter`` : filtre OData identifiant le rattachement.
    """
    flow = s.flow
    flow.use("ModelesActions", "Code", "Contexte", "Categorie", "Description", "RoleResponsable", "DelaiJours",
             "Bloquante", "PreuveAttendue", "Ordre", "Actif", "Title")
    flow.use("ActionsIntegration", "CodeModeleAction", "Contexte")
    m = get_items(s, f"Modeles_{tag}", "ModelesActions",
                  filter_=f"Contexte eq {odata(contexte)} and Actif eq 1", order="Ordre asc")

    def body(b, loop):
        it = f"items('{loop}')"
        ex = get_items(b, f"Existe_{tag}", "ActionsIntegration",
                       filter_=f"{key_filter} and CodeModeleAction eq {odq(it + "?['Code']")}")

        def create(c):
            vals = {"Title": ip(f"{it}?['Title']"), "Contexte": contexte,
                    "Categorie": at(f"{it}?['Categorie']?['Value']"),
                    "Description": at(f"{it}?['Description']"), "RoleResponsable": at(f"{it}?['RoleResponsable']?['Value']"),
                    "Echeance": ip(f"addDays({base_date_expr}, int(coalesce({it}?['DelaiJours'], 0)), 'yyyy-MM-dd')"),
                    "Bloquante": at(f"coalesce({it}?['Bloquante'], false)"), "PreuveAttendue": at(f"{it}?['PreuveAttendue']"),
                    "CodeModeleAction": ip(f"{it}?['Code']"), "Statut": "À faire"}
            for col, idx in links.items():
                vals[col] = at(idx)
            p, _ = create_with_id(c, f"Creer_action_{tag}", "ActionsIntegration", vals)
            resp = role_resolution(f"{it}?['RoleResponsable']?['Value']", role_map)
            pid = f"body('{p}')?['ID']"
            flow.use("ActionsIntegration", "EmpreinteAction", "Bloquante", "Statut", "Responsable")
            patch_item(c, f"Empreinte_action_{tag}", "ActionsIntegration", pid, {"EmpreinteAction": ip(emp_action(f"body('{p}')"))}, f"body('{p}')")

            def set_resp(r):
                patch_item(r, f"Responsable_action_{tag}", "ActionsIntegration", pid, {"Responsable": ip(resp)}, f"body('{p}')")
                grant_item(r, f"action_{tag}", "ActionsIntegration", pid, [("user", resp, "CSS")])
            cond(c, f"Si_responsable_{tag}", f"not(empty({resp}))", set_resp)
        cond(b, f"Si_action_absente_{tag}", f"equals(length(body('{ex}')?['value']), 0)", create)

    foreach(s, f"Pour_modele_{tag}", f"body('{m}')?['value']", body)


def checklist_table(s, tag, filter_):
    a = get_items(s, f"Checklist_{tag}", "ActionsIntegration", filter_=filter_,
                  fields=("IdHNCS", "Title", "Responsable", "Echeance", "Statut", "Bloquante"), order="Echeance asc")
    t = html_table(s, f"Tableau_{tag}", f"body('{a}')?['value']", [
        ("Action", "concat(coalesce(item()?['IdHNCS'], ''), ' : ', item()?['Title'])"),
        ("Responsable", "coalesce(item()?['Responsable']?['DisplayName'], '')"),
        ("Échéance", dfr("item()?['Echeance']")),
        ("Bloquante", "if(equals(item()?['Bloquante'], true), 'Oui', 'Non')"),
        ("Statut", "item()?['Statut']?['Value']")])
    return f"body('{t}')"


# --------------------------------------------------------------------------------------------
# Comptes rendus : période selon la cadence, création avec effets de PA-08 (§ 7.4)
# --------------------------------------------------------------------------------------------

def cadence_effective(aff):
    return (f"if(or(empty({aff}?['CadenceCR']?['Value']), equals({aff}?['CadenceCR']?['Value'], 'Selon paramètre global')), "
            f"{P('CR.CadenceGlobale', 'Quinzaine')}, {aff}?['CadenceCR']?['Value'])")


def period_first(start, cad):
    """Première période à partir de ``start`` (yyyy-MM-dd)."""
    fin = (f"if(equals({cad}, 'Hebdomadaire'), addDays({start}, 6, 'yyyy-MM-dd'), if(equals({cad}, 'Mensuelle'), "
           f"addDays(startOfMonth(addToTime({start}, 1, 'Month')), -1, 'yyyy-MM-dd'), addDays({start}, 13, 'yyyy-MM-dd')))")
    return start, fin


def period_current(start, cad):
    """Période courante (contenant aujourd'hui) ancrée sur ``start``."""
    length = f"if(equals({cad}, 'Hebdomadaire'), 7, 14)"
    days = f"div(sub(ticks({TODAY}), ticks({start})), 864000000000)"
    k = f"div(max({days}, 0), {length})"
    som = f"formatDateTime(startOfMonth({TODAY}), 'yyyy-MM-dd')"
    deb = (f"if(equals({cad}, 'Mensuelle'), if(greater({start}, {som}), {start}, {som}), "
           f"addDays({start}, mul({k}, {length}), 'yyyy-MM-dd'))")
    return deb


def period_end(deb, cad):
    return (f"if(equals({cad}, 'Mensuelle'), addDays(startOfMonth(addToTime({deb}, 1, 'Month')), -1, 'yyyy-MM-dd'), "
            f"addDays({deb}, sub(if(equals({cad}, 'Hebdomadaire'), 7, 14), 1), 'yyyy-MM-dd'))")


def create_cr(s, tag, aff, alt, ref, deb, fin):
    """Crée un compte rendu « Attendu » (CR-T01, FLUX) avec les effets de création de PA-08 :
    IdHNCS, Title, Alternant copié, Valideur = référent, permissions élément (alternant et valideur : CSS)."""
    flow = s.flow
    flow.use("Affectations", "ID", "IdHNCS", "Alternant")
    flow.use("Alternants", "CompteM365")
    flow.use("Referents", "Compte")
    ech = f"addDays({fin}, int({P('CR.DelaiRemiseJours', '2')}), 'yyyy-MM-dd')"
    vals = {"Affectation": at(f"{aff}?['ID']"), "Alternant": at(f"{aff}?['Alternant']?['Id']"),
            "PeriodeDebut": ip(deb), "PeriodeFin": ip(fin), "Echeance": ip(ech),
            "Title": ip(f"concat('CR ', coalesce({aff}?['IdHNCS'], ''), ' : ', {deb}, ' au ', {fin})"), "Statut": "Attendu"}
    p, idcalc = create_with_id(s, f"Creer_CR_{tag}", "ComptesRendus", vals)
    pid = f"body('{p}')?['ID']"
    valideur = f"{ref}?['Compte']?['Email']"
    cond(s, f"Si_valideur_{tag}", f"not(empty({valideur}))",
         lambda y: patch_item(y, f"Valideur_CR_{tag}", "ComptesRendus", pid, {"Valideur": ip(valideur)}, f"body('{p}')"))
    grant_item(s, f"CR_{tag}", "ComptesRendus", pid,
               [("user", f"{alt}?['CompteM365']?['Email']", "CSS"), ("user", valideur, "CSS")])
    fp_refresh(s, f"cr_{tag}", "ComptesRendus", pid, CR_FP)
    flux_creation(s, f"CR_T01_{tag}", "CompteRendu", "ComptesRendus", pid, idcalc, "Attendu", "CR-T01")
    return p, ech


# --------------------------------------------------------------------------------------------
# Fin d'alternance planifiée (PA-09b et PA-09 manuel)
# --------------------------------------------------------------------------------------------

def fin_planifiee_effects(s, tag, A, AID, aidobj, send_n35=True):
    flow = s.flow
    flow.use("Alternants", "ReferentPrincipal", "Etablissement", "DateFin", "CandidatureSource", "Title", "IdHNCS")
    ref = lookup_first(s, f"Referent_{tag}", "Referents", f"{A}?['ReferentPrincipal']?['Id']", fields=("Compte",))
    eco = lookup_first(s, f"Etablissement_{tag}", "Etablissements", f"{A}?['Etablissement']?['Id']", fields=("ResponsableHNCS",))
    fin = dloc(A + "?['DateFin']")
    generate_actions(s, f"clo_{tag}", "Clôture d'alternance", {"Alternant": AID},
                     f"AlternantId eq @{{{AID}}} and Contexte eq 'Clôture d''alternance'", fin,
                     role_map(referent=f"{ref}?['Compte']?['Email']", eco_resp=f"{eco}?['ResponsableHNCS']?['Email']"))
    b = get_items(s, f"Bilan_existant_{tag}", "BilansAlternance", filter_=f"AlternantId eq @{{{AID}}}",
                  fields=("Alternant", "IdHNCS", "ID"))

    def create(c):
        p, _ = create_with_id(c, f"Creer_bilan_{tag}", "BilansAlternance", {
            "Alternant": at(AID), "Etablissement": at(f"{A}?['Etablissement']?['Id']"),
            "Referent": at(f"{A}?['ReferentPrincipal']?['Id']"),
            "Title": ip(f"concat('Bilan ', {aidobj})"), "Statut": "À réaliser"})
        grant_item(c, f"bilan_{tag}", "BilansAlternance", f"body('{p}')?['ID']", [("user", f"{ref}?['Compte']?['Email']", "CSS")])
    cond(s, f"Si_bilan_absent_{tag}", f"equals(length(body('{b}')?['value']), 0)", create)
    b2 = get_items(s, f"Bilan_{tag}", "BilansAlternance", filter_=f"AlternantId eq @{{{AID}}}", fields=("Alternant", "IdHNCS", "ID"), top=1)
    bil = first(b2)
    tab = checklist_table(s, f"clo_{tag}", f"AlternantId eq @{{{AID}}} and Contexte eq 'Clôture d''alternance'")
    if not send_n35:
        return tab, ref
    notify(s, "N-35", [f"{ref}?['Compte']?['Email']", flow.group_emails("G_RD"), f"{eco}?['ResponsableHNCS']?['Email']"], {
        "IdAlternant": aidobj, "NomAlternant": f"{A}?['Title']", "DateFin": dfr(A + "?['DateFin']"), "Checklist": tab,
        "IdBilan": f"coalesce({bil}?['IdHNCS'], '')", "LienBilan": item_link("BilansAlternance", f"coalesce({bil}?['ID'], 0)"),
        "Lien": item_link("Alternants", AID)})
    return tab, ref


# --------------------------------------------------------------------------------------------
# Empreintes des champs protégés (P-09) : format § 6.5 (JSON compact, clés dans l'ordre de la spec,
# dates AAAA-MM-JJ, dates-heures ISO 8601 UTC, lookups = ID entier, personnes = e-mail en minuscules, absent = null)
# --------------------------------------------------------------------------------------------
DOD = ["DoD1Fonctionnel", "DoD2FicheMethodo", "DoD3Restitution", "DoD4SupportCom", "DoD5Enseignements"]
# clé -> (colonne, sous-champ, nature) ; nature ∈ id, email, date, dt, int, str, dod
LIV_FP = {"AffectationId": ("Affectation", "Id", "id"), "Proprietaire": ("Proprietaire", "Email", "email"),
          "Reviseur": ("Reviseur", "Email", "email"), "Echeance": ("Echeance", None, "date"), "DoD": (None, None, "dod"),
          "NbCorrections": ("NbCorrections", None, "int"), "DecisionRevue": ("DecisionRevue", "Value", "str"),
          "Valideur": ("Valideur", "Email", "email"), "DateValidation": ("DateValidation", None, "dt"),
          "VersionValidee": ("VersionValidee", None, "str"), "DatePremierDepot": ("DatePremierDepot", None, "dt"),
          "DateDepot": ("DateDepot", None, "dt"), "DateRevue": ("DateRevue", None, "dt")}
CR_FP = {"AffectationId": ("Affectation", "Id", "id"), "Valideur": ("Valideur", "Email", "email"),
         "Echeance": ("Echeance", None, "date"), "PeriodeDebut": ("PeriodeDebut", None, "date"),
         "PeriodeFin": ("PeriodeFin", None, "date"), "DateValidation": ("DateValidation", None, "dt"),
         "DateRemise": ("DateRemise", None, "dt")}
FP_KEY_LABELS = {"AffectationId": "Affectation", "DoD": "Definition of Done (DoD 1 à 5)"}


def jnull(e):
    return f"equals({e}, null)"


def jnum(e):
    return f"if({jnull(e)}, 'null', string({e}))"


def jbool(e):
    return f"if(equals({e}, true), 'true', 'false')"


def jstr(e):
    return ("if(or(" + jnull(e) + ", equals(string(" + e + "), '')), 'null', concat('\"', replace(replace(string(" + e +
            "), '\\', '\\\\'), '\"', '\\\"'), '\"'))")


def jdate(e):
    return f"if(empty({e}), 'null', concat('\"', {dloc(e)}, '\"'))"


def jdt(e):
    return f"if(empty({e}), 'null', concat('\"', formatDateTime({e}, 'yyyy-MM-ddTHH:mm:ssZ'), '\"'))"


def _fp_part(flow, lst, src, col, sub, kind):
    if kind == "dod":
        flow.use(lst, *DOD)
        return "concat('[', " + ", ',', ".join(jbool(f"{src}?['{d}']") for d in DOD) + ", ']')"
    e = flow.f(lst, src, col, sub)
    if kind == "id" or kind == "int":
        return jnum(e)
    if kind == "email":
        return jstr(f"toLower(coalesce({e}, ''))")
    if kind == "date":
        return jdate(e)
    if kind == "dt":
        return jdt(e)
    return jstr(e)


def fp_compute(s, flow, lst, src, spec, base):
    """Empreinte courante au format § 6.5. Retourne (expression texte, nom du compose)."""
    parts = []
    for i, (key, (col, sub, kind)) in enumerate(spec.items()):
        parts.append(q(("{" if i == 0 else ",") + f'"{key}":'))
        parts.append(_fp_part(flow, lst, src, col, sub, kind))
    parts.append(q("}"))
    c = compose(s, base, at("concat(" + ", ".join(parts) + ")"))
    return f"outputs('{c}')", c


def _norm(v, kind):
    """Valeur normalisée pour la comparaison sémantique (robuste aux variantes d'écriture de l'empreinte)."""
    if kind == "dt":
        return f"if(empty({v}), '', string(ticks({v})))"
    if kind == "email":
        return f"toLower(string(coalesce({v}, '')))"
    return f"string(coalesce({v}, ''))"


def changed_keys(emp, cur_compose, keys, spec):
    """Tableau des clés dont la valeur diffère entre l'empreinte validée ``emp`` et l'état courant."""
    parts = []
    for k in keys:
        kind = spec[k][2]
        a, b = f"json({emp})?['{k}']", f"json(outputs('{cur_compose}'))?['{k}']"
        parts.append(f"if(equals({_norm(a, kind)}, {_norm(b, kind)}), '', {q(FP_KEY_LABELS.get(k, k))})")
    return "createArray(" + ", ".join(parts) + ")"


def fp_refresh(s, tag, lst, id_expr, spec, field="EmpreinteRevue"):
    """Relit l'élément et (ré)écrit l'empreinte si elle est vide (initialisation) ou si une valeur a changé."""
    flow = s.flow
    flow.use(lst, field)
    r = get_item(s, f"Relire_pour_empreinte_{tag}", lst, id_expr)
    R = f"body('{r}')"
    expr, c = fp_compute(s, flow, lst, R, spec, f"Empreinte_{tag}")
    emp = f"coalesce({R}?['{field}'], '')"
    diff = filt(s, f"Ecarts_empreinte_{tag}", f"if(empty({emp}), createArray('init'), {changed_keys(emp, c, list(spec), spec)})",
                "not(empty(item()))")
    cond(s, f"Si_empreinte_a_ecrire_{tag}", f"greater(length(body('{diff}')), 0)",
         lambda y: patch_item(y, f"Ecrire_empreinte_{tag}", lst, id_expr, {field: ip(expr)}, R))


def fp_restore_values(lst, emp, spec, types):
    """Valeurs de rétablissement depuis l'empreinte JSON ``emp``."""
    vals = {}
    for key, (col, sub, kind) in spec.items():
        v = f"json({emp})?['{key}']"
        if kind == "dod":
            for i, d in enumerate(DOD):
                vals[d] = at(f"equals(json({emp})?['DoD']?[{i}], true)")
        elif kind in ("id", "int"):
            vals[col] = at(v)
        elif kind == "date":
            vals[col] = at(f"if(empty({v}), null, {v})")
        else:
            vals[col] = at(f"if(empty({v}), null, {v})")
    return vals
