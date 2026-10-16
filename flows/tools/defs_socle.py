"""Flux du socle technique : PA-00A, PA-00B, PA-00C (flux enfants), PA-00D, PA-00E."""
from __future__ import annotations

import json

from flowlib import (MODEL, SITE, SVC, SUPPORT, TZ, Flow, Seq, P, arr, at, child_trigger, compose, cond, filt, foreach,
                     get_items, html_table, ip, list_exists, log, notify, odq, patch_item, post_item, q, read_params,
                     recurrence_trigger, response, scope, select, sp_http, standard_shell, terminate, idhncs_expr,
                     list_srv, item_link, list_link)

T = "triggerBody()"
STATUS_LISTS = sorted({p["list"] for p in MODEL.partition})


# --------------------------------------------------------------------------------------------
# PA-00A — Vérifier une transition
# --------------------------------------------------------------------------------------------

def pa00a():
    f = Flow("PA-00A", "PA-00A", "HNCS-RD PA-00A — Vérifier une transition", 2, "Flux enfant", "ChildFlow")
    f.params_needed = False
    child_trigger(f, {
        "Objet": ("string", "Objet de la transition (énumération OBJET_TRANSITION)"),
        "StatutAvant": ("string", "Statut de départ (∅ pour une création)"),
        "StatutApres": ("string", "Statut demandé"),
        "ActeurEmail": ("string", "Adresse de l'auteur de la modification (Editor)"),
        "ItemAuteurEmail": ("string", "Adresse de la personne ITEM_AUTEUR (facultatif)"),
        "ItemValideurEmail": ("string", "Adresse de la personne ITEM_VALIDEUR (facultatif)"),
    }, ["Objet", "StatutAvant", "StatutApres", "ActeurEmail"])
    top = Seq(f)
    top.add("Initialiser_RolesSatisfaits", {"type": "InitializeVariable", "inputs": {
        "variables": [{"name": "RolesSatisfaits", "type": "array", "value": []}]}})
    types = {"Autorise": "boolean", "CodeTransition": "string", "Controles": "string", "Motif": "string"}

    def controle(s):
        compose(s, "Groupes_par_role", MODEL.role_group)
        tr = get_items(s, "Lire_transitions", "TransitionsStatuts", top=5,
                       filter_=(f"Objet eq {odq(T + "?['Objet']")} and StatutDe eq {odq(T + "?['StatutAvant']")} and "
                                f"StatutVers eq {odq(T + "?['StatutApres']")} and Actif eq 1"),
                       fields=("Title", "Objet", "StatutDe", "StatutVers", "Acteurs", "Controle", "Actif"))

        def none(y):
            response(y, "Repondre_transition_inexistante", {"Autorise": False, "CodeTransition": "", "Controles": "",
                                                            "Motif": "Transition non autorisée"}, types)

        def some(y):
            t = compose(y, "Transition", at(f"first(body('{tr}')?['value'])"))
            roles = select(y, "Roles_autorises", f"outputs('{t}')?['Acteurs']", at("item()?['Value']"))
            ok_body = {"Autorise": True, "CodeTransition": ip(f"outputs('{t}')?['Title']"),
                       "Controles": ip(f"coalesce(outputs('{t}')?['Controle'], '')"), "Motif": ""}
            ko_body = {"Autorise": False, "CodeTransition": ip(f"outputs('{t}')?['Title']"),
                       "Controles": ip(f"coalesce(outputs('{t}')?['Controle'], '')"), "Motif": "Rôle non autorisé"}
            acteur = f"toLower(trim(coalesce({T}?['ActeurEmail'], '')))"

            def service(z):
                cond(z, "Si_FLUX_autorise", f"contains(body('{roles}'), 'FLUX')",
                     lambda a: response(a, "Repondre_FLUX_autorise", ok_body, types),
                     lambda b: response(b, "Repondre_FLUX_refuse", ko_body, types))

            def human(z):
                def per_role(b, loop):
                    role = f"items('{loop}')"

                    def group(g):
                        m = sp_http(g, "Membres_du_groupe", "GET",
                                    ip(f"concat('_api/web/sitegroups/getbyname(''', outputs('Groupes_par_role')?[{role}], ''')/users?$select=Email')"))
                        e = select(g, "Emails_du_groupe", f"body('{m}')?['value']", at("toLower(coalesce(item()?['Email'], ''))"))
                        cond(g, "Si_membre", f"contains(body('{e}'), {acteur})",
                             lambda h: h.add("Ajouter_role_groupe", {"type": "AppendToArrayVariable",
                                                                     "inputs": {"name": "RolesSatisfaits", "value": at(role)}}))

                    def item_roles(g):
                        for r, key in (("ITEM_AUTEUR", "ItemAuteurEmail"), ("ITEM_VALIDEUR", "ItemValideurEmail")):
                            cond(g, f"Si_{r}", (f"and(equals({role}, '{r}'), not(empty(trim(coalesce({T}?['{key}'], '')))), "
                                                f"equals(toLower(trim({T}?['{key}'])), {acteur}))"),
                                 lambda h, r=r: h.add(f"Ajouter_{r}", {"type": "AppendToArrayVariable",
                                                                       "inputs": {"name": "RolesSatisfaits", "value": r}}))
                    cond(b, "Si_role_de_groupe", f"not(empty(outputs('Groupes_par_role')?[{role}]))", group, item_roles)
                foreach(z, "Tester_roles", f"body('{roles}')", per_role)
                cond(z, "Si_role_satisfait", "greater(length(variables('RolesSatisfaits')), 0)",
                     lambda a: response(a, "Repondre_autorise", ok_body, types),
                     lambda b: response(b, "Repondre_role_refuse", ko_body, types))

            cond(y, "Si_compte_service", f"equals({acteur}, toLower({SVC}))", service, human)

        cond(s, "Si_aucune_transition", f"equals(length(body('{tr}')?['value']), 0)", none, some)

    sc = scope(top, "Controle", controle)

    def erreur(s):
        response(s, "Repondre_erreur_technique", {"Autorise": False, "CodeTransition": "", "Controles": "",
                                                  "Motif": "Erreur technique de contrôle"}, types)
    scope(top, "Erreur_controle", erreur, after={sc: ["Failed", "TimedOut"]})
    f.top = top.actions
    f.doc = dict(
        objectif="Vérifier qu'une transition de statut est autorisée : couple (De, Vers) actif dans `TransitionsStatuts` et rôle de l'acteur.",
        entrees="`Objet`, `StatutAvant` (`∅` pour une création), `StatutApres`, `ActeurEmail`, `ItemAuteurEmail`, `ItemValideurEmail` (facultatifs).",
        etapes=["Lire les lignes actives de `TransitionsStatuts` (Objet, StatutDe, StatutVers).",
                "Aucune ligne → `Autorise` = false, motif « Transition non autorisée ».",
                "Acteur = compte de service → rôle `FLUX` uniquement.",
                "Sinon, pour chaque rôle autorisé : appartenance au groupe SharePoint par REST (`sitegroups/getbyname/users`), ou comparaison en minuscules à `ItemAuteurEmail` / `ItemValideurEmail`.",
                "Aucun rôle satisfait → motif « Rôle non autorisé ». Sinon `Autorise` = true, `CodeTransition`, `Controles` (codes `G_*`)."],
        sorties="`Autorise`, `CodeTransition`, `Controles`, `Motif`.",
        erreurs="Portée `Erreur_controle` : toute erreur technique répond `Autorise` = false et « Erreur technique de contrôle » (fail-safe) ; l'appelant journalise via PA-00C.",
        decision="Aucune : le flux ne fait que vérifier ; il n'existe aucun rôle `FLUX` sur une décision humaine (hors CAND-T02).",
        tests=["Transition inexistante (ex. Reçue → Intégrée) refusée.", "Acteur hors groupe refusé ; membre direct du groupe accepté (H-14).",
               "ITEM_VALIDEUR : casse de l'adresse ignorée.", "Groupe absent → réponse « Erreur technique de contrôle »."])
    return f


# --------------------------------------------------------------------------------------------
# PA-00B — Appliquer ou annuler une transition
# --------------------------------------------------------------------------------------------

def pa00b():
    f = Flow("PA-00B", "PA-00B", "HNCS-RD PA-00B — Appliquer ou annuler une transition", 2, "Flux enfant", "ChildFlow")
    child_trigger(f, {
        "Liste": ("string", "Nom interne de la liste"), "ItemId": ("number", "ID SharePoint"),
        "IdObjet": ("string", "IdHNCS"), "Objet": ("string", "Objet (OBJET_TRANSITION)"),
        "StatutAvant": ("string", "Statut avant (∅ pour une création)"), "StatutApres": ("string", "Statut demandé"),
        "Accepte": ("boolean", "Transition acceptée ?"), "CodeTransition": ("string", "Code de transition"),
        "ActeurEmail": ("string", "Adresse de l'acteur"), "Origine": ("string", "Humain ou Flux"),
        "Motif": ("string", "Motif du refus ou commentaire"), "RunId": ("string", "Identifiant d'exécution du flux parent"),
    }, ["Liste", "ItemId", "IdObjet", "Objet", "StatutAvant", "StatutApres", "Accepte", "ActeurEmail", "Origine"])
    for lst in STATUS_LISTS:
        f.write(lst, "Statut", "StatutPrecedent", "DateStatut")
    top = Seq(f)
    lst_srv = f"concat(uriPath({SITE}), '/Lists/', {T}?['Liste'])"
    base_uri = f"concat('_api/web/GetList(''', {lst_srv}, ''')"
    verbose = {"Accept": "application/json;odata=verbose", "Content-Type": "application/json;odata=verbose",
               "IF-MATCH": "*", "X-HTTP-Method": "MERGE"}

    def principal(s):
        read_params(s, ["Destinataires", "Fonctionnalités"])
        te = sp_http(s, "Type_entite", "GET", ip(f"concat({base_uri}, ''')?$select=ListItemEntityTypeFullName')"))
        accepte = f"equals(toLower(string({T}?['Accepte'])), 'true')"
        creation = f"equals({T}?['StatutAvant'], '∅')"
        retabli = compose(s, "Statut_retabli", at(f"if({creation}, 'création annulée : élément placé dans la corbeille du site', {T}?['StatutAvant'])"))
        item_uri = ip(f"concat({base_uri}, ''')/items(', string({T}?['ItemId']), ')')")
        etype = f"body('{te}')?['ListItemEntityTypeFullName']"

        def yes(y):
            c = compose(y, "Corps_acceptation", {"__metadata": {"type": ip(etype)},
                                                 "StatutPrecedent": ip(f"{T}?['StatutApres']"), "DateStatut": ip("utcNow()")})
            sp_http(y, "Valider_StatutPrecedent", "POST", item_uri, body=ip(f"outputs('{c}')"), headers=verbose)

        def no(n):
            def restore(r):
                c = compose(r, "Corps_annulation", {"__metadata": {"type": ip(etype)}, "Statut": ip(f"{T}?['StatutAvant']")})
                sp_http(r, "Retablir_statut", "POST", item_uri, body=ip(f"outputs('{c}')"), headers=verbose)

            def recycle(r):
                # § 6.1-3 bis : refus d'une création → corbeille du site (récupérable 93 jours), jamais de suppression définitive
                sp_http(r, "Envoyer_a_la_corbeille", "POST",
                        ip(f"concat({base_uri}, ''')/items(', string({T}?['ItemId']), ')/recycle()')"))
            cond(n, "Si_creation_refusee", creation, recycle, restore)
            notify(n, "N-90", [f"{T}?['ActeurEmail']"], {
                "IdHNCS": f"{T}?['IdObjet']", "StatutDemande": f"{T}?['StatutApres']", "Motif": f"coalesce({T}?['Motif'], '')",
                "StatutRetabli": f"outputs('{retabli}')",
                "Lien": f"concat({SITE}, '/Lists/', {T}?['Liste'], '/DispForm.aspx?ID=', string({T}?['ItemId']))"},
                teams_to=[f"{T}?['ActeurEmail']"])
        cond(s, "Si_acceptee", accepte, yes, no)
        post_item(s, "Creer_historique", "HistoriqueStatuts", {
            "Title": ip(f"{T}?['IdObjet']"), "Objet": ip(f"{T}?['Objet']"), "Liste": ip(f"{T}?['Liste']"),
            "ItemId": at(f"{T}?['ItemId']"), "StatutAvant": ip(f"if(equals({T}?['StatutAvant'], '∅'), '', {T}?['StatutAvant'])"),
            "StatutApres": ip(f"{T}?['StatutApres']"), "CodeTransition": ip(f"coalesce({T}?['CodeTransition'], '')"), "Acteur": ip(f"{T}?['ActeurEmail']"),
            "ActeurEmail": ip(f"{T}?['ActeurEmail']"), "DateChangement": ip("utcNow()"), "Origine": ip(f"{T}?['Origine']"),
            "Resultat": ip(f"if({accepte}, 'Acceptée', 'Refusée — annulée')"), "Motif": ip(f"coalesce({T}?['Motif'], '')"),
            "FluxRunId": ip(f"coalesce({T}?['RunId'], '')")})
        response(s, "Repondre", {"Ok": True}, {"Ok": "boolean"})

    sc = scope(top, "Principal", principal)
    err = top.sub()
    terminate(err, "Echec_ecriture", "Failed", "PA-00B : échec d'écriture (remonté à l'appelant)")
    top.actions["Erreur"] = {"type": "Scope", "actions": err.actions, "runAfter": {sc: ["Failed", "TimedOut"]}}
    f.names.add("Erreur")
    f.top = top.actions
    f.doc = dict(
        objectif="Appliquer (acceptation) ou annuler (refus) une transition et l'historiser.",
        entrees="`Liste`, `ItemId`, `IdObjet`, `Objet`, `StatutAvant`, `StatutApres`, `Accepte`, `CodeTransition`, `ActeurEmail`, `Origine`, `Motif`, `RunId`.",
        etapes=["Lire les paramètres (boîte R&D, notifications Teams).",
                "Acceptée : `StatutPrecedent` = `StatutApres`, `DateStatut` = maintenant (REST `MERGE`, liste désignée par son nom interne via `GetList`).",
                "Refusée : `Statut` = `StatutAvant` (`StatutPrecedent` inchangé) puis N-90 à l'acteur. Refus d'une création (`StatutAvant` = `∅`, § 6.1-3 bis) : l'élément est envoyé à la corbeille du site (`recycle`, récupérable 93 jours, jamais supprimé définitivement), puis N-90.",
                "Dans les deux cas : création d'un élément `HistoriqueStatuts` (`Acceptée` ou `Refusée — annulée`)."],
        sorties="`Ok` = true.",
        erreurs="Toute erreur d'écriture termine le flux en échec : l'action d'appel du parent échoue et le parent passe en portée `Erreur` (PA-00C).",
        decision="Le flux ne modifie jamais une décision : il ne fait que rétablir le dernier statut validé.",
        tests=["Refus : statut rétabli, historique « Refusée — annulée », N-90 reçu.", "Acceptation : `StatutPrecedent` et `DateStatut` mis à jour.",
               "Écriture impossible (liste verrouillée) : le parent journalise une erreur."])
    return f


# --------------------------------------------------------------------------------------------
# PA-00C — Journaliser une erreur
# --------------------------------------------------------------------------------------------

def pa00c():
    f = Flow("PA-00C", "PA-00C", "HNCS-RD PA-00C — Journaliser une erreur", 2, "Flux enfant", "ChildFlow")
    child_trigger(f, {
        "CodeFlux": ("string", "Code du flux appelant"), "Niveau": ("string", "Info, Avertissement ou Erreur"),
        "Liste": ("string", "Nom interne de la liste concernée"), "ItemId": ("string", "ID SharePoint (texte, facultatif)"),
        "IdObjet": ("string", "IdHNCS"), "Message": ("string", "Message sans donnée personnelle"),
        "DetailErreur": ("string", "Détail technique"), "RunUrl": ("string", "Lien vers l'exécution"),
    }, ["CodeFlux", "Niveau", "Message"])
    top = Seq(f)
    erreur = f"equals({T}?['Niveau'], 'Erreur')"
    j = post_item(top, "Creer_journal", "JournalFlux", {
        "Title": ip(f"{T}?['CodeFlux']"), "Niveau": ip(f"{T}?['Niveau']"), "Liste": ip(f"coalesce({T}?['Liste'], '')"),
        "ItemId": at(f"if(empty({T}?['ItemId']), null, int({T}?['ItemId']))"), "IdObjet": ip(f"coalesce({T}?['IdObjet'], '')"),
        "Message": ip(f"{T}?['Message']"), "DetailErreur": ip(f"coalesce({T}?['DetailErreur'], '')"),
        "RunUrl": ip(f"coalesce({T}?['RunUrl'], '')"), "DateEvenement": ip("utcNow()"),
        "StatutReprise": ip(f"if({erreur}, 'À reprendre', 'Sans objet')")})
    # Les paramètres sont lus après le journal : un échec de lecture n'empêche pas l'écriture du journal
    from flowlib import get_items as gi
    lp = gi(top, "Lire_parametres", "Parametres", filter_="Categorie eq 'Destinataires'", fields=("Title", "Valeur", "Categorie"),
            top=100, after={j: ["Succeeded", "Failed", "TimedOut"]})
    pair = ("concat('\"', replace(item()?['Title'], '\"', ''), '\":', if(empty(item()?['Valeur']), 'null', "
            "concat('\"', replace(replace(item()?['Valeur'], '\\', '\\\\'), '\"', '\\\"'), '\"')))")
    sel = select(top, "Parametres_cles_valeurs", f"coalesce(body('{lp}')?['value'], createArray())", at(pair),
                 after={lp: ["Succeeded", "Failed", "TimedOut"]})
    compose(top, "Parametres", at(f"json(concat('{{', join(coalesce(body('{sel}'), createArray()), ','), '}}'))"),
            after={sel: ["Succeeded", "Failed", "Skipped"]})

    def mail(s):
        notify(s, "N-99", [SUPPORT], {
            "CodeFlux": f"{T}?['CodeFlux']", "Message": f"{T}?['Message']", "IdObjet": f"coalesce({T}?['IdObjet'], '')",
            "Liste": f"coalesce({T}?['Liste'], '')", "RunUrl": f"coalesce({T}?['RunUrl'], '')",
            "Lien": list_link("JournalFlux")},
            mailbox_expr=f"coalesce(outputs('Parametres')?['Destinataires.BoiteRD'], {SVC})", log_missing=False)
    c = cond(top, "Si_niveau_erreur", erreur, mail, after={"Parametres": ["Succeeded", "Failed"]})
    response(top, "Repondre", {"IdJournal": ip(f"string(coalesce(body('{j}')?['ID'], ''))")}, {"IdJournal": "string"},
             after={c: ["Succeeded", "Failed", "Skipped", "TimedOut"]})
    f.top = top.actions
    f.doc = dict(
        objectif="Tracer une erreur, un avertissement ou un événement métier dans `JournalFlux` et prévenir le support en cas d'erreur.",
        entrees="`CodeFlux`, `Niveau`, `Liste`, `ItemId`, `IdObjet`, `Message`, `DetailErreur`, `RunUrl`.",
        etapes=["Créer l'élément `JournalFlux` (`StatutReprise` = « À reprendre » si Niveau = Erreur, sinon « Sans objet »).",
                "Lire la boîte expéditrice (`Destinataires.BoiteRD`), même si l'écriture du journal a échoué.",
                "Niveau = Erreur : envoyer N-99 à `hncs_SupportEmail` (tenté même si le journal n'a pas pu être écrit)."],
        sorties="`IdJournal` (vide si l'écriture a échoué).",
        erreurs="Le courriel N-99 est tenté quel que soit le résultat de l'écriture du journal ; le flux répond toujours à l'appelant.",
        decision="Sans objet.",
        tests=["Niveau Erreur : élément « À reprendre » et N-99 reçu.", "Liste `JournalFlux` indisponible : N-99 reçu quand même.",
               "Niveau Info : aucun courriel."])
    return f


# --------------------------------------------------------------------------------------------
# PA-00D — Attribuer les identifiants manquants
# --------------------------------------------------------------------------------------------

def pa00d():
    f = Flow("PA-00D", "PA-00D", "HNCS-RD PA-00D — Attribuer les identifiants et initialiser les empreintes", 1, "Planifié", "Recurrence",
             recurrence="Toutes les heures (exécution manuelle possible par « Exécuter »)")
    recurrence_trigger(f, {"frequency": "Hour", "interval": 1})
    lists = [o for o in MODEL.data["objects"] if o["kind"] == "list" and o["prefix"]]

    def empreintes(s):
        """H-55 : à partir du lot 2, initialiser les empreintes vides (§ 6.5) à partir des valeurs courantes, sans rien rétablir.

        Garde « lot 2 actif » : au moins une transition historisée par un flux (Origine = Flux, écrite par PA-00B).
        Chaque liste est traitée dans sa propre portée ; une colonne ou une liste absente est ignorée sans erreur.
        """
        from gen_common import CR_FP, LIV_FP, emp_action, fp_compute
        from defs_production import ev_item
        g = get_items(s, "Lot2_actif", "HistoriqueStatuts", filter_="Origine eq 'Flux'", fields=("Origine",), top=1,
                      after={s.last: ["Succeeded", "Skipped", "Failed"]})
        specs = [
            ("Affectations", "EmpreinteVerrou",
             "EmpreinteVerrou eq null and (StatutPrecedent eq 'Active' or StatutPrecedent eq 'À risque' or StatutPrecedent eq 'Bloquée' "
             "or StatutPrecedent eq 'Terminée' or StatutPrecedent eq 'Clôturée')",
             lambda e, it: ip(ev_item(it)), ("Alternant", "Sujet", "Referent", "DateDebut", "StatutPrecedent")),
            ("Livrables", "EmpreinteRevue", "EmpreinteRevue eq null", "LIV", ()),
            ("ComptesRendus", "EmpreinteRevue", "EmpreinteRevue eq null", "CR", ()),
            ("ActionsIntegration", "EmpreinteAction", "EmpreinteAction eq null", lambda e, it: ip(emp_action(it)), ("Bloquante", "Statut")),
            ("Alternants", "EmpreinteReferent", "EmpreinteReferent eq null and ReferentPrincipalId ne null",
             lambda e, it: ip(f"string({it}?['ReferentPrincipal']?['Id'])"), ("ReferentPrincipal",)),
            ("Conventions", "EmpreinteDecision", "EmpreinteDecision eq null and DecideurPartenariatId ne null and DecisionPartenariat ne null",
             lambda e, it: ip(f"{it}?['DecisionPartenariat']?['Value']"), ("DecideurPartenariat", "DecisionPartenariat")),
        ]

        def gated(y):
            prevp = None
            for lst, col, flt, value, fields in specs:
                def per_list(ls, lst=lst, col=col, flt=flt, value=value, fields=fields):
                    def work(w):
                        items = get_items(w, f"Empreintes_vides_{lst}", lst, filter_=flt, fields=(col,) + tuple(fields))

                        def each(e, loop):
                            it = f"items('{loop}')"
                            if value in ("LIV", "CR"):
                                expr, _ = fp_compute(e, f, lst, it, LIV_FP if value == "LIV" else CR_FP, f"Empreinte_{lst}")
                                v = ip(expr)
                            else:
                                v = value(e, it)
                            patch_item(e, f"Initialiser_{col}_{lst}", lst, f"{it}?['ID']", {col: v}, it)
                            e.add(f"Compter_empreinte_{lst}", {"type": "IncrementVariable", "inputs": {"name": "NbEmpreintes", "value": 1}})
                        foreach(w, f"Pour_empreinte_{lst}", f"body('{items}')?['value']", each)
                    if MODEL.obj(lst)["lot"] >= 3:
                        cond(ls, f"Si_liste_deployee_empreinte_{lst}", list_exists(ls, f"emp_{lst}", lst), work)
                    else:
                        work(ls)
                after = None if prevp is None else {prevp: ["Succeeded", "Failed", "TimedOut", "Skipped"]}
                prevp = scope(y, f"Empreintes_{lst}", per_list, after=after)
            cond(y, "Si_empreintes_initialisees", "greater(variables('NbEmpreintes'), 0)",
                 lambda w: log(w, "Journaliser_empreintes", "Info",
                               "concat(string(variables('NbEmpreintes')), ' empreinte(s) initialisée(s) à partir des valeurs courantes (H-55)')"),
                 after={prevp: ["Succeeded", "Failed", "TimedOut", "Skipped"]})
        cond(s, "Si_lot2_actif", f"greater(length(coalesce(body('{g}')?['value'], createArray())), 0)", gated,
             after={g: ["Succeeded", "Failed"]})

    def body(s):
        prev = None
        for o in lists:
            name = o["name"]

            def per_list(ls, o=o, name=name):
                def work(w):
                    items = get_items(w, f"Sans_IdHNCS_{name}", name, filter_="IdHNCS eq null", fields=("IdHNCS",))

                    def each(e, loop):
                        it = f"items('{loop}')"
                        if name == "Poles":
                            f.use("Poles", "CodePole")
                            val = f"concat('POL-', {it}?['CodePole'])"
                        else:
                            val = idhncs_expr(name, it, f)
                        patch_item(e, f"Attribuer_{name}", name, f"{it}?['ID']", {"IdHNCS": ip(val)}, it)
                        e.add(f"Compter_{name}", {"type": "IncrementVariable", "inputs": {"name": "NbIdentifiants", "value": 1}})
                    foreach(w, f"Pour_{name}", f"body('{items}')?['value']", each)
                if o["lot"] >= 3:
                    present = list_exists(ls, name, name)
                    cond(ls, f"Si_liste_deployee_{name}", present, work)
                else:
                    work(ls)
            after = None if prev is None else {prev: ["Succeeded", "Skipped", "Failed"]}
            sc = scope(s, f"Liste_{name}", per_list, after=after)
            prev = log(s, f"Erreur_liste_{name}", "Erreur", q(f"PA-00D : échec de l'attribution des identifiants ({name})"),
                       name, after={sc: ["Failed", "TimedOut"]})
        cond(s, "Si_identifiants_attribues", "greater(variables('NbIdentifiants'), 0)",
             lambda y: log(y, "Journaliser_nombre", "Info", "concat(string(variables('NbIdentifiants')), ' identifiant(s) IdHNCS attribué(s)')"),
             after={prev: ["Succeeded", "Skipped", "Failed"]})
        empreintes(s)
    standard_shell(f, body, variables=[("NbIdentifiants", "integer", 0), ("NbEmpreintes", "integer", 0)])
    f.doc = dict(
        objectif="Filet de sécurité : attribuer `IdHNCS` aux éléments qui n'en ont pas (listes sans flux de création, créations hors flux) et, à partir du lot 2, initialiser les empreintes vides (§ 6.5, H-55).",
        entrees="Toutes les listes ayant un préfixe d'identifiant (§ 4.3) ; les listes des lots ≥ 3 ne sont traitées que si elles sont déployées.",
        etapes=["Pour chaque liste : éléments dont `IdHNCS` est vide.",
                "`IdHNCS` = `{PREFIXE}-{année de Created, heure de Paris}-{ID sur 4 chiffres}` ; Pôles : `POL-{CodePole}`.",
                "Une portée par liste : l'échec d'une liste est journalisé (PA-00C, Erreur) sans bloquer les autres.",
                "Nombre d'identifiants attribués → `JournalFlux` niveau Info.",
                "À partir du lot 2 (au moins une transition historisée par un flux, Origine = Flux) : empreintes vides initialisées à partir des valeurs courantes, sans rien rétablir — `EmpreinteVerrou` des affectations déjà validées (actives ou au-delà), `EmpreinteRevue` des livrables et comptes rendus, `EmpreinteAction`, `EmpreinteReferent` (référent renseigné), `EmpreinteDecision` (décideur déjà tracé, H-55) ; une portée par liste, liste ou colonne absente ignorée sans erreur ; nombre initialisé → `JournalFlux` Info."],
        sorties="`IdHNCS` renseigné.",
        erreurs="PA-00C par liste en échec ; rattrapage automatique au passage suivant.",
        decision="Sans objet.",
        tests=["Élément créé sans identifiant → identifiant au format attendu en moins d'une heure.", "Pôle P3 → `POL-P3`.",
               "Liste de lot 3 absente : aucune erreur.", "Lot 1 seul (aucun historique Origine = Flux) : aucune empreinte écrite.",
               "Livrable importé sans empreinte → `EmpreinteRevue` au format § 6.5 dans l'heure, aucune valeur rétablie."])
    return f


# --------------------------------------------------------------------------------------------
# PA-00E — Supervision quotidienne
# --------------------------------------------------------------------------------------------

def pa00e():
    f = Flow("PA-00E", "PA-00E", "HNCS-RD PA-00E — Supervision quotidienne des flux", 2, "Planifié", "Recurrence",
             recurrence="Quotidien 07:30 (heure de Paris)")
    recurrence_trigger(f, {"frequency": "Day", "interval": 1, "schedule": {"hours": ["7"], "minutes": [30]}})

    def body(s):
        j = get_items(s, "Erreurs_a_reprendre", "JournalFlux", filter_="Niveau eq 'Erreur' and StatutReprise eq 'À reprendre'",
                      fields=("Title", "Niveau", "StatutReprise", "IdObjet", "Liste", "DateEvenement", "RunUrl", "Message"),
                      order="DateEvenement desc")
        tab = html_table(s, "Tableau_erreurs", f"body('{j}')?['value']", [
            ("Date", "if(empty(item()?['DateEvenement']), '', formatDateTime(convertTimeZone(item()?['DateEvenement'], 'UTC', 'Romance Standard Time'), 'dd/MM/yyyy HH:mm'))"),
            ("Flux", "item()?['Title']"), ("Objet", "coalesce(item()?['IdObjet'], '')"),
            ("Message", "item()?['Message']"), ("Exécution", "coalesce(item()?['RunUrl'], '')")])
        cond(s, "Si_erreurs", f"greater(length(body('{j}')?['value']), 0)",
             lambda y: notify(y, "N-98", [SUPPORT, f.group_emails("G_PROP")], {
                 "Nombre": f"string(length(body('{j}')?['value']))", "Tableau": f"body('{tab}')",
                 "Lien": list_link("JournalFlux")}))
    standard_shell(f, body)
    f.doc = dict(
        objectif="Rappeler chaque jour les erreurs de flux non reprises.",
        entrees="`JournalFlux` : Niveau = Erreur et `StatutReprise` = « À reprendre ».",
        etapes=["Lister les erreurs à reprendre.", "Si la liste n'est pas vide : N-98 (synthèse avec liens d'exécution) au support (`hncs_SupportEmail`) et aux membres de G_PROP."],
        sorties="Courriel de synthèse.", erreurs="Socle (PA-00C).", decision="Sans objet.",
        tests=["Aucune erreur : aucun courriel.", "Deux erreurs à reprendre : N-98 avec deux lignes ; après « Reprise effectuée », plus de rappel."])
    return f


# --------------------------------------------------------------------------------------------
# PA-00F — Droits des propriétaires de modèles
# --------------------------------------------------------------------------------------------

def pa00f():
    from flowlib import ANTI_LOOP, sp_trigger, get_item, item_changes, grant_item, ensure_idhncs
    MOD = "RegistreModeles"
    f = Flow("PA-00F", "PA-00F", "HNCS-RD PA-00F — Droits des propriétaires de modèles", 2, "Automatisé", "SharePointItem", MOD)
    sp_trigger(f, MOD, "GetOnUpdatedItems", [ANTI_LOOP])
    f.use(MOD, "Proprietaire", "LienFichier", "IdHNCS", "ID")

    def body(s):
        I = "body('Lire_element')"
        get_item(s, "Lire_element", MOD, "triggerOutputs()?['body/ID']")
        ID = f"{I}?['ID']"
        idobj = ensure_idhncs(s, MOD, I, ID, "el")
        ch = item_changes(s, "Changements", MOD, ID)

        def chg(col):
            return f"equals(string(coalesce(body('{ch}')?['ColumnHasChanged']?['{col}'], false)), 'True')"
        creation = f"not(equals(string(coalesce(body('{ch}')?['SinceVersionExisted'], true)), 'True'))"
        owner = f"{I}?['Proprietaire']?['Email']"

        def grant(y):
            grant_item(y, "modele", MOD, ID, [("user", owner, "CSS")])
            fichiers = get_items(y, "Fichiers_du_modele", "ModelesRD", filter_=f"ModeleId eq @{{{ID}}}", fields=("Modele", "ID"))

            def each(e, loop):
                grant_item(e, "fichier_modele", "ModelesRD", f"items('{loop}')?['ID']", [("user", owner, "CSS")])
            foreach(y, "Pour_fichier", f"body('{fichiers}')?['value']", each)
            log(y, "Journaliser_droits_modele", "Info", f"concat('Droits du propriétaire posés sur ', {idobj})", MOD, ID, idobj)
        cond(s, "Si_proprietaire_ou_fichier_modifie",
             f"and(not(empty({owner})), or({creation}, {chg('Proprietaire')}, {chg('LienFichier')}))", grant)
    standard_shell(f, body, MOD, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = dict(
        objectif="Réserver la modification d'un modèle à son propriétaire (§ 7.4) : élément du registre et fichiers de « 03 — Modèles R&D » liés.",
        entrees="Élément `RegistreModeles` créé ou modifié (création, changement de `Proprietaire` ou de `LienFichier`, détectés par « Obtenir les modifications »).",
        etapes=["`IdHNCS` (`MOD-…`) si vide.",
                "Rompre l'héritage de l'élément (copie) et donner CSS au `Proprietaire`.",
                "Même attribution sur chaque fichier de `ModelesRD` dont la colonne `Modele` désigne l'élément.",
                "L'ancien propriétaire n'est pas retiré automatiquement (revue des accès, § 7.1) ; `JournalFlux` Info."],
        sorties="Permissions ; `JournalFlux` Info.", erreurs="Socle (PA-00C) ; attributions idempotentes.",
        decision="Sans objet (droits techniques) ; l'approbation d'un modèle reste humaine.",
        tests=["Changement de propriétaire → le nouveau propriétaire peut modifier le modèle et ses fichiers ; l'ancien conserve ses droits jusqu'à la revue.",
               "Modification d'un autre champ → aucune action."])
    return f


BUILDERS = [pa00a, pa00b, pa00c, pa00d, pa00e, pa00f]
