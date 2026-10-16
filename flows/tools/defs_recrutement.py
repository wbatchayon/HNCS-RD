"""Flux du recrutement et de l'intégration : PA-01a/b, PA-02/02b, PA-03/03b, PA-04/04b (spec v1.1.0)."""
from __future__ import annotations

from flowlib import (MODEL, SITE, SVC, TZ, TODAY, ANTI_LOOP, Flow, P, arr, at, compose, cond, conn_action, cond_targets,
                     cond_transition, create_with_id, dfr, dloc, dtloc, ensure_folder, ensure_idhncs, filt, flux_transition,
                     foreach, get_item, get_items, grant_folder, grant_item, historize, ip, item_changes, item_link, lib_srv,
                     log, notify, odata, odq, patch_item, list_exists, post_item, q, recurrence_trigger, select, sp_http, sp_trigger,
                     standard_shell, switch, terminate, truthy, verify, autorise, list_srv)
from gen_common import (CTX_FORM, I_EL, alternant_controls, blocking_bad_where, candidature_controls, checklist_table,
                        controls_needed_for, emp_action, first, flux_creation, generate_actions, lookup_first, role_map,
                        role_resolution, transition_body)

CAND = "Candidatures"
ALT = "Alternants"
ACT = "ActionsIntegration"
APRES_TRANSMISSION = ["Transmise à l'administration", "Entretien planifié", "Entretien réalisé", "En attente de décision",
                      "Retenue", "Formalités en cours"]
DEPUIS_ADMINISTRATION = ["Transmise à l'administration", "Entretien planifié", "Entretien réalisé", "En attente de décision"]


def targets(code, lst):
    return [p for p in MODEL.partition if p["flow"] == code and p["list"] == lst][0]["targets"]


def resp(I):
    return f"{I}?['ResponsableAnalyse']?['Email']"


def annee(I):
    return f"formatDateTime(convertTimeZone({I}?['Created'], 'UTC', '{TZ}'), 'yyyy')"


def recrut_rel(I, idobj):
    return f"concat({annee(I)}, '/', {idobj})"


def identite_ok(I):
    return f"and(not(empty(trim(coalesce({I}?['Email'], '')))), not(startsWith(coalesce({I}?['Title'], ''), 'À qualifier')))"


def doublon_check(s, f, I, ID, tag="dbl"):
    """Contrôle doublon (signalement uniquement) si `Email` est renseigné. Retourne le nom de l'action de recherche."""
    f.use(CAND, "Email", "ID", "Statut", "IdHNCS", "DoublonPotentiel", "DoublonDe")
    d = get_items(s, f"Doublons_{tag}", CAND,
                  filter_=(f"Email eq {odq(I + "?['Email']")} and ID ne @{{{ID}}} and Statut ne 'Intégrée' and "
                           f"Statut ne 'Non retenue' and Statut ne 'Clôturée'"))
    cond(s, f"Si_doublon_potentiel_{tag}",
         f"and(not(empty(trim(coalesce({I}?['Email'], '')))), greater(length(body('{d}')?['value']), 0), not({truthy(I + "?['DoublonPotentiel']")}))",
         lambda y: patch_item(y, f"Signaler_doublon_{tag}", CAND, ID, {
             "DoublonPotentiel": at("true"), "DoublonDe": ip(f"{first(d)}?['IdHNCS']")}, I))
    return d


def n03(s, f, I, idobj, ID):
    notify(s, "N-03", [resp(I)], {"IdHNCS": idobj, "NomCandidat": f"{I}?['Title']",
                                  "DelaiRelance": P("Delai.RelanceAnalyseJours", "5"), "Lien": item_link(CAND, ID)},
           teams_to=[resp(I)])


# --------------------------------------------------------------------------------------------
# PA-01 — traitement commun
# --------------------------------------------------------------------------------------------

def pa01_common(s, f, I, ID, idobj, origine, acteur, attachments=None):
    f.use(CAND, "ID", "Created", "Email", "Statut", "StatutPrecedent", "ResponsableAnalyse", "LienCV", "DoublonPotentiel",
          "DoublonDe", "AccuseReceptionEnvoye", "Title", "Canal", "DateReception", "PosteVise", "IdHNCS")
    # 2. Contrôle doublon (si Email renseigné)
    d = doublon_check(s, f, I, ID, "cr")
    # 3. Dossier Recrutement/{AAAA}/{IdHNCS}
    rel = recrut_rel(I, idobj)
    url = ensure_folder(s, "cv", "Recrutement", rel)
    grant_folder(s, "cv", "Recrutement", rel, [("group", "G_PROP", "FC"), ("group", "G_DRD", "CSS"), ("group", "G_RD", "CSS")])
    cond(s, "Si_LienCV_vide", f"empty({I}?['LienCV'])",
         lambda y: patch_item(y, "Renseigner_LienCV", CAND, ID, {"LienCV": ip(url)}, I))
    if attachments:
        exts = f"split(toLower({P('Canal.ExtensionsAutorisees', '.pdf;.doc;.docx;.odt')}), ';')"

        def each(e, loop):
            att = f"items('{loop}')"
            ext = f"toLower(concat('.', last(split({att}?['name'], '.'))))"

            def ok(o):
                cf = o.add("Enregistrer_piece_jointe", conn_action(f, "shared_sharepointonline", "CreateFile", {
                    "dataset": at(SITE), "folderPath": ip(f"concat('/Recrutement/', {rel})"),
                    "name": ip(f"{att}?['name']"), "body": at(f"base64ToBinary({att}?['contentBytes'])")}))
                f.write("Recrutement")
                patch_item(o, "Metadonnees_piece_jointe", "Recrutement", f"body('{cf}')?['ItemId']", {
                    "TypeDocument": "CV", "Candidature": at(ID), "IdObjet": ip(idobj)}, None)

            def ko(o):
                log(o, "Piece_jointe_refusee", "Avertissement", f"concat('Pièce jointe refusée (type ', {ext}, ') ; candidature créée')",
                    CAND, ID, idobj)
            cond(e, "Si_extension_autorisee", f"contains({exts}, {ext})", ok, ko)
        f.use("Recrutement", "TypeDocument", "Candidature", "IdObjet")
        nonin = filt(s, "Pieces_jointes", f"coalesce({attachments}, createArray())", "not(equals(item()?['isInline'], true))")
        foreach(s, "Pour_piece_jointe", f"body('{nonin}')", each)
    # 4. Historiser CAND-T01
    f.trans("CAND-T01")
    if origine == "Flux":
        f.status(CAND, "Reçue")
    cond(s, "Si_creation_non_historisee", f"empty({I}?['StatutPrecedent'])",
         lambda y: historize(y, "Historiser_CAND_T01", CAND, ID, idobj, "Candidature", q("∅"), q("Reçue"), True,
                             q("CAND-T01"), acteur, origine))
    # 5. Responsable renseigné et identité qualifiée → CAND-T02 (FLUX, exception documentée) puis N-03 (§ 6.1-8)
    needed = controls_needed_for("CAND-T02")
    cond(s, "Si_responsable_et_identite",
         f"and(not(empty({resp(I)})), {identite_ok(I)}, equals({I}?['Statut']?['Value'], 'Reçue'))",
         lambda y: flux_transition(y, "CAND_T02", "Candidature", CAND, ID, idobj, q("Reçue"), "À analyser", "CAND-T02",
                                   candidature_controls(f, I, ID, needed), src=I,
                                   after_fn=lambda w: n03(w, f, I, idobj, ID)))
    # 6. N-01
    notify(s, "N-01", [f"if(empty({resp(I)}), {f.group_emails('G_RD')}, {resp(I)})"], {
        "IdHNCS": idobj, "NomCandidat": f"{I}?['Title']", "Canal": f"{I}?['Canal']?['Value']",
        "DateReception": dtloc(I + "?['DateReception']"), "PosteVise": f"coalesce({I}?['PosteVise'], '—')",
        "Doublon": (f"if(and(not(empty(trim(coalesce({I}?['Email'], '')))), greater(length(body('{d}')?['value']), 0)), "
                    f"concat('doublon potentiel de ', coalesce({first(d)}?['IdHNCS'], '')), 'aucun')"),
        "Qualification": (f"if({identite_ok(I)}, '', 'Identité à qualifier : le courriel provient d''une plateforme. Renseignez le nom "
                          f"et l''adresse du candidat à partir du message avant l''analyse (contrôle G_IDENTITE).')"),
        "Lien": item_link(CAND, ID), "LienDossier": url}, teams_to=[resp(I)])
    # 7. N-02 (accusé de réception, désactivé par défaut — H-09)
    def ar(y):
        notify(y, "N-02", [f"{I}?['Email']"], {"NomCandidat": f"{I}?['Title']"})
        patch_item(y, "Accuse_reception_envoye", CAND, ID, {"AccuseReceptionEnvoye": at("true")}, I)
    cond(s, "Si_accuse_reception", (f"and(equals({P('Fonction.AccuseReceptionActif', 'Non')}, 'Oui'), {identite_ok(I)}, "
                                    f"not({truthy(I + "?['AccuseReceptionEnvoye']")}))"), ar)


def pa01a():
    f = Flow("PA-01a", "PA-01a", "HNCS-RD PA-01a — Nouvelle candidature — saisie ou formulaire", 2, "Automatisé",
             "SharePointItem", CAND, targets=targets("PA-01", CAND), objet="Candidature")
    sp_trigger(f, CAND, "GetOnNewItems", [ANTI_LOOP, cond_transition(), cond_targets(f.targets)])
    acteur = "toLower(coalesce(triggerOutputs()?['body/Editor/Email'], ''))"

    def body(s):
        I = I_EL
        get_item(s, "Lire_element", CAND, "triggerOutputs()?['body/ID']")
        ID = f"{I}?['ID']"
        idobj = ensure_idhncs(s, CAND, I, ID, "el")
        # Socle : PA-00A sur CAND-T01 ; refus d'une création → § 6.1-3 bis (corbeille, historique, N-90)
        v = verify(s, "Verifier_creation", "Candidature", q("∅"), q("Reçue"), acteur)
        cond(s, "Si_creation_refusee", f"and(not({autorise(v)}), empty({I}?['StatutPrecedent']))",
             lambda y: (historize(y, "Annuler_creation", CAND, ID, idobj, "Candidature", q("∅"), q("Reçue"), False,
                                  f"body('{v}')?['CodeTransition']", acteur, "Humain", f"coalesce(body('{v}')?['Motif'], '')"),
                        terminate(y, "Fin_creation_refusee")))
        pa01_common(s, f, I, ID, idobj, "Humain", acteur)
    standard_shell(f, body, CAND, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-01a"]
    return f


def pa01b():
    f = Flow("PA-01b", "PA-01b", "HNCS-RD PA-01b — Nouvelle candidature — boîte mail R&D", 2, "Automatisé",
             "SharedMailbox", None, objet="Candidature")
    f.connections.add("shared_office365")
    f.trigger_name = "Quand_un_courriel_arrive_dans_la_boite_RD"
    f.trigger = {"type": "OpenApiConnection", "recurrence": {"interval": 3, "frequency": "Minute"},
                 "splitOn": "@triggerOutputs()?['body/value']",
                 "inputs": {"host": {"apiId": "/providers/Microsoft.PowerApps/apis/shared_office365",
                                     "connectionName": "shared_office365", "operationId": "SharedMailboxOnNewEmailV2"},
                            "parameters": {"mailboxAddress": "@parameters('hncs_BoiteRDEmail (hncs_BoiteRDEmail)')",
                                           "folderId": "@parameters('hncs_BoiteRDDossierCandidatures (hncs_BoiteRDDossierCandidatures)')",
                                           "includeAttachments": True, "importance": "Any", "fetchOnlyWithAttachment": False},
                            "authentication": "@parameters('$authentication')"}}
    TB = "triggerOutputs()?['body"
    msgid = f"{TB}/internetMessageId']"
    sender = f"toLower(trim(coalesce({TB}/from'], '')))"
    subject = f"coalesce({TB}/subject'], '')"

    def body(s):
        ex = get_items(s, "Message_deja_traite", CAND, filter_=f"RefMessage eq {odq(msgid)}", fields=("RefMessage", "ID", "LienCV"), top=1)
        cond(s, "Si_message_deja_traite", f"and(greater(length(body('{ex}')?['value']), 0), not(empty({first(ex)}?['LienCV'])))",
             lambda y: terminate(y, "Fin_idempotence"))
        dom = compose(s, "Domaine_expediteur", at(f"last(split({sender}, '@'))"))
        rules = f"split({P('Canal.Regles')}, ';')"
        motif = "toLower(trim(first(split(item(), '='))))"
        r1 = filt(s, "Regles_domaine", rules, f"and(contains(item(), '='), or(equals(outputs('{dom}'), {motif}), endsWith(outputs('{dom}'), concat('.', {motif}))))")
        r2 = filt(s, "Regles_objet", rules, f"and(contains(item(), '='), contains(toLower({subject}), {motif}))")
        cr = compose(s, "Canal_regle", at(f"if(greater(length(body('{r1}')), 0), trim(last(split(first(body('{r1}')), '='))), "
                                         f"if(greater(length(body('{r2}')), 0), trim(last(split(first(body('{r2}')), '='))), 'À qualifier'))"))
        canal = compose(s, "Canal", at(f"if(contains({arr(MODEL.enums['CANAL'])}, outputs('{cr}')), outputs('{cr}'), 'À qualifier')"))
        # Courriel de plateforme (règle de domaine LinkedIn / France Travail) : l'expéditeur n'est pas le candidat
        plateforme = compose(s, "Courriel_de_plateforme",
                             at(f"and(greater(length(body('{r1}')), 0), contains(createArray('LinkedIn', 'France Travail'), outputs('{canal}')))"))
        pf = f"equals(string(outputs('{plateforme}')), 'True')"

        def create(y):
            p = post_item(y, "Creer_candidature", CAND, {
                "Title": ip(f"if({pf}, concat('À qualifier – ', {msgid}), first(split({sender}, '@')))"),
                "Email": ip(f"if({pf}, '', {sender})"), "Canal": ip(f"outputs('{canal}')"),
                "ModeReception": "Boîte mail R&D", "DateReception": ip(f"coalesce({TB}/receivedDateTime'], utcNow())"),
                "Statut": "Reçue", "RefMessage": ip(msgid)})
            y.add("Memoriser_ID_cree", {"type": "SetVariable", "inputs": {"name": "IdCandidature", "value": at(f"body('{p}')?['ID']")}})

        def reuse(y):
            y.add("Memoriser_ID_existant", {"type": "SetVariable", "inputs": {"name": "IdCandidature", "value": at(f"{first(ex)}?['ID']")}})
        cond(s, "Si_nouveau_message", f"equals(length(body('{ex}')?['value']), 0)", create, reuse)
        I = I_EL
        get_item(s, "Lire_element", CAND, "variables('IdCandidature')")
        ID = f"{I}?['ID']"
        idobj = ensure_idhncs(s, CAND, I, ID, "el")
        pa01_common(s, f, I, ID, idobj, "Flux", SVC, attachments=f"{TB}/attachments']")
    standard_shell(f, body, CAND, "variables('IdCandidature')", "''", variables=[("IdCandidature", "integer", 0)])
    f.doc = DOC["PA-01b"]
    return f


# --------------------------------------------------------------------------------------------
# PA-02 — Présélection et suivi de l'analyse
# --------------------------------------------------------------------------------------------

def pa02():
    f = Flow("PA-02", "PA-02", "HNCS-RD PA-02 — Présélection et suivi de l'analyse", 2, "Automatisé", "SharePointItem", CAND,
             targets=targets("PA-02", CAND), objet="Candidature")
    sp_trigger(f, CAND, "GetOnUpdatedItems", [ANTI_LOOP, cond_transition(), cond_targets(f.targets)])
    f.use(CAND, "ResponsableAnalyse", "DateAnalyse", "DateDecisionPreselection", "DecisionPreselection", "DestinataireAdmin",
          "DateTransmissionAdmin", "DateDecisionFinale", "DateCloture", "MotifCode", "InformationCandidat", "Email", "Title",
          "Created", "IdHNCS")

    def body(s):
        def depuis_recue(z, env, tag):
            cond(z, f"Si_qualification_{tag}", f"equals({env.AVANT}, 'Reçue')", lambda y: doublon_check(y, f, env.I, env.ID, tag))

        def a_analyser(z, env):
            I = env.I
            depuis_recue(z, env, "aa")
            cond(z, "Si_reouverture", f"contains(createArray('Non retenue', 'Clôturée'), {env.AVANT})",
                 lambda y: patch_item(y, "Vider_DateCloture", CAND, env.ID, {"DateCloture": at("null")}, I))
            n03(z, f, I, env.IDOBJ, env.ID)

        def en_cours(z, env):
            depuis_recue(z, env, "ec")
            cond(z, "Si_DateAnalyse_vide", f"empty({env.I}?['DateAnalyse'])",
                 lambda y: patch_item(y, "Renseigner_DateAnalyse", CAND, env.ID, {"DateAnalyse": ip("utcNow()")}, env.I))

        def preselectionnee(z, env):
            I = env.I
            admin = P("Destinataires.Administration")
            patch_item(z, "Dates_preselection", CAND, env.ID, {
                "DateDecisionPreselection": at(f"coalesce({I}?['DateDecisionPreselection'], utcNow())"),
                "DecisionPreselection": "Présélectionnée",
                "DestinataireAdmin": ip(f"if(empty({I}?['DestinataireAdmin']?['Email']), {admin}, {I}?['DestinataireAdmin']?['Email'])")}, I)
            rel = recrut_rel(I, env.IDOBJ)
            url = ensure_folder(z, "cv_adm", "Recrutement", rel)
            dest = f"if(empty({I}?['DestinataireAdmin']?['Email']), {admin}, {I}?['DestinataireAdmin']?['Email'])"

            def to_dest(y):  # Recrutement.PartageTransmission = Destinataire (H-45)
                grant_item(y, "candidature_dest", CAND, env.ID, [("user", dest, "CSS")])
                grant_folder(y, "cv_dest", "Recrutement", rel, [("user", dest, "CSS")])

            def to_group(y):  # valeur par défaut : Groupe (G_ADM)
                grant_item(y, "candidature_adm", CAND, env.ID, [("group", "G_ADM", "CSS")])
                grant_folder(y, "cv_adm", "Recrutement", rel, [("group", "G_ADM", "CSS")])
            cond(z, "Si_partage_destinataire", f"equals({P('Recrutement.PartageTransmission', 'Groupe')}, 'Destinataire')", to_dest, to_group)
            # v1.3.0 : dossier administratif (grilles d'entretien) créé dès la transmission (§ 7.4)
            ensure_folder(z, "adm_cand_transmission", "Administration", f"concat('Candidatures/', {env.IDOBJ})")

            def send(y):
                notify(y, "N-05", [admin], {"IdHNCS": env.IDOBJ, "NomCandidat": f"{I}?['Title']", "Lien": env.LIEN,
                                            "LienDossier": url}, teams_to=[admin])
                patch_item(y, "Renseigner_DateTransmissionAdmin", CAND, env.ID, {"DateTransmissionAdmin": ip("utcNow()")}, I)
            cond(z, "Si_non_transmise", f"empty({I}?['DateTransmissionAdmin'])", send)

        def non_retenue(z, env):
            I = env.I
            analyse = f"equals({env.AVANT}, 'En cours d''analyse')"
            admin_dec = f"contains({arr(DEPUIS_ADMINISTRATION)}, {env.AVANT})"
            admin_imp = f"contains({arr(APRES_TRANSMISSION)}, {env.AVANT})"
            cond(z, "Si_ecartee_a_l_analyse", analyse,
                 lambda y: patch_item(y, "Decision_ecartee", CAND, env.ID, {"DecisionPreselection": "Écartée"}, I))
            patch_item(z, "Dates_non_retenue", CAND, env.ID, {
                "DateDecisionPreselection": at(f"if(and({analyse}, empty({I}?['DateDecisionPreselection'])), utcNow(), {I}?['DateDecisionPreselection'])"),
                "DateDecisionFinale": at(f"if(and({admin_dec}, empty({I}?['DateDecisionFinale'])), utcNow(), {I}?['DateDecisionFinale'])"),
                "DateCloture": at(f"coalesce({I}?['DateCloture'], utcNow())")}, I)
            notify(z, "N-06", [f.group_emails("G_RD"), f"if({admin_imp}, {P('Destinataires.Administration')}, '')"],
                   {"IdHNCS": env.IDOBJ, "Statut": env.APRES, "MotifCode": f"coalesce({I}?['MotifCode']?['Value'], '—')", "Lien": env.LIEN})

            def auto(y):
                notify(y, "N-07", [f"{I}?['Email']"], {"NomCandidat": f"{I}?['Title']"})
                f.use(CAND, "DateInformationCandidat")
                patch_item(y, "Candidat_informe", CAND, env.ID, {"InformationCandidat": at("true"), "DateInformationCandidat": ip(TODAY)}, I)

            def task(y):
                notify(y, "N-08", [resp(I)], {"IdHNCS": env.IDOBJ, "NomCandidat": f"{I}?['Title']", "Lien": env.LIEN})
            cond(z, "Si_information_auto", f"and(equals({P('Fonction.InformationCandidatAuto', 'Non')}, 'Oui'), not({truthy(I + "?['InformationCandidat']")}))", auto, task)

        def cloturee(z, env):
            I = env.I
            admin_imp = f"contains({arr(APRES_TRANSMISSION)}, {env.AVANT})"
            patch_item(z, "Date_cloture", CAND, env.ID, {"DateCloture": at(f"coalesce({I}?['DateCloture'], utcNow())")}, I)
            notify(z, "N-06", [f.group_emails("G_RD"), f"if({admin_imp}, {P('Destinataires.Administration')}, '')"],
                   {"IdHNCS": env.IDOBJ, "Statut": env.APRES, "MotifCode": f"coalesce({I}?['MotifCode']?['Value'], '—')", "Lien": env.LIEN})

        def transmise(z, env):
            notify(z, "N-04", [P("Destinataires.Administration")], {"IdHNCS": env.IDOBJ, "NomCandidat": f"{env.I}?['Title']", "Lien": env.LIEN})

        def post(s2, env):
            def t05(y):
                rr = get_item(y, "Relire_candidature", CAND, env.ID)
                R = f"body('{rr}')"
                cond(y, "Si_notification_envoyee", f"not(empty({R}?['DateTransmissionAdmin']))",
                     lambda w: flux_transition(w, "CAND_T05", "Candidature", CAND, env.ID, env.IDOBJ, q("Présélectionnée"),
                                               "Transmise à l'administration", "CAND-T05", None, src=R))
            cond(s2, "Si_preselectionnee", f"equals({env.APRES}, 'Présélectionnée')", t05)

        needed = MODEL.controls_for("Candidature", f.targets)
        transition_body(s, f, CAND, "Candidature", effects={
            "À analyser": a_analyser, "En cours d'analyse": en_cours, "Présélectionnée": preselectionnee,
            "Non retenue": non_retenue, "Clôturée": cloturee, "Transmise à l'administration": transmise},
            controls=candidature_controls(f, I_EL, f"{I_EL}?['ID']", needed), post=post)
    standard_shell(f, body, CAND, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-02"]
    return f


def pa02b():
    f = Flow("PA-02b", "PA-02b", "HNCS-RD PA-02b — Relance des candidatures sans traitement", 2, "Planifié", "Recurrence",
             recurrence="Quotidien 08:00 (heure de Paris)")
    recurrence_trigger(f, {"frequency": "Day", "interval": 1, "schedule": {"hours": ["8"], "minutes": [0]}})

    def body(s):
        c = get_items(s, "Candidatures_en_attente", CAND,
                      filter_="Statut eq 'Reçue' or Statut eq 'À analyser' or Statut eq 'En cours d''analyse'",
                      fields=("Statut", "DateStatut", "DateReception", "ResponsableAnalyse", "IdHNCS", "ID"))
        ref = "coalesce(item()?['DateStatut'], item()?['DateReception'])"
        old = filt(s, "Candidatures_sans_traitement", f"body('{c}')?['value']",
                   f"and(not(empty({ref})), less(ticks({ref}), ticks(addDays(utcNow(), mul(-1, int({P('Delai.RelanceAnalyseJours', '5')}))))))")

        def each(e, loop):
            it = f"items('{loop}')"
            r = f"{it}?['ResponsableAnalyse']?['Email']"
            refd = f"coalesce({it}?['DateStatut'], {it}?['DateReception'])"
            notify(e, "N-09", [f"if(empty({r}), {f.group_emails('G_RD')}, {r})"], {
                "IdHNCS": f"coalesce({it}?['IdHNCS'], string({it}?['ID']))", "Statut": f"{it}?['Statut']?['Value']",
                "Anciennete": f"string(div(sub(ticks(utcNow()), ticks({refd})), 864000000000))",
                "Lien": item_link(CAND, f"{it}?['ID']")})
        foreach(s, "Pour_candidature", f"body('{old}')", each)
    standard_shell(f, body)
    f.doc = DOC["PA-02b"]
    return f


# --------------------------------------------------------------------------------------------
# PA-03 — Entretien (entretiens + candidatures) et PA-03b
# --------------------------------------------------------------------------------------------

def pa03_ent():
    ENT = "Entretiens"
    f = Flow("PA-03-ent", "PA-03", "HNCS-RD PA-03 — Entretien (entretiens)", 2, "Automatisé", "SharePointItem", ENT)
    sp_trigger(f, ENT, "GetOnUpdatedItems", [ANTI_LOOP])
    f.use(ENT, "ID", "Statut", "StatutPrecedent", "DateStatut", "DateHeure", "Resultat", "LienReunion", "RappelEnvoye",
          "Participants", "Candidature", "SaisiPar", "DateSaisieResultat", "Title", "Modalite")

    def body(s):
        I = I_EL
        get_item(s, "Lire_element", ENT, "triggerOutputs()?['body/ID']")
        ID = f"{I}?['ID']"
        idobj = ensure_idhncs(s, ENT, I, ID, "el")
        ch = item_changes(s, "Changements", ENT, ID)

        def chg(col):
            return f"equals(string(coalesce(body('{ch}')?['ColumnHasChanged']?['{col}'], false)), 'True')"
        creation = f"not(equals(string(coalesce(body('{ch}')?['SinceVersionExisted'], true)), 'True'))"
        get_item(s, "Lire_candidature", CAND, f"{I}?['Candidature']?['Id']")
        C = "body('Lire_candidature')"
        CID = f"{C}?['ID']"
        f.use(CAND, "ID", "Statut", "IdHNCS", "ResponsableAnalyse", "Title")
        cst = f"{C}?['Statut']?['Value']"
        cidobj = f"coalesce({C}?['IdHNCS'], string({CID}))"
        acteur = "toLower(coalesce(triggerOutputs()?['body/Editor/Email'], ''))"

        # 5. Historisation de tout changement de Statut ou de Resultat (Objet = Entretien, § 6.1-7)
        def histo(y):
            res = f"{I}?['Resultat']?['Value']"
            post_item(y, "Historiser_entretien", "HistoriqueStatuts", {
                "Title": ip(idobj), "Objet": "Entretien", "Liste": ENT, "ItemId": at(f"int({ID})"),
                "StatutAvant": ip(f"coalesce({I}?['StatutPrecedent'], '')"),
                "StatutApres": ip(f"{I}?['Statut']?['Value']"),
                "CodeTransition": "", "Acteur": ip(acteur), "ActeurEmail": ip(acteur), "DateChangement": ip("utcNow()"),
                "Origine": "Humain", "Resultat": "Acceptée", "Motif": ip(f"if(empty({res}), '', concat('Résultat : ', {res}))"), "FluxRunId": ip("workflow()?['run']?['name']")})
            patch_item(y, "Statut_entretien_valide", ENT, ID, {"StatutPrecedent": ip(f"{I}?['Statut']?['Value']"),
                                                              "DateStatut": ip("utcNow()")}, I)
        cond(s, "Si_statut_ou_resultat_modifie", f"or({creation}, {chg('Statut')}, {chg('Resultat')})", histo)

        def planifie(z):
            def ev(y):
                # Participants : lecture sur l'entretien (§ 7.4)
                srv = list_srv(ENT)
                pre = f"concat('_api/web/GetList(''', {srv}, ''')/items(', string({ID}), ')')"
                sp_http(y, "Rompre_heritage_entretien", "POST",
                        ip(f"concat({pre}, '/breakroleinheritance(copyRoleAssignments=true,clearSubscopes=true)')"))
                rd = f.roledef("R")

                def part(p, loop):
                    eu = sp_http(p, "Utilisateur_participant", "POST", "_api/web/ensureuser",
                                 body=ip(f"concat('{{\"logonName\":\"i:0#.f|membership|', toLower(items('{loop}')?['Email']), '\"}}')"))
                    sp_http(p, "Lecture_participant", "POST",
                            ip(f"concat({pre}, '/roleassignments/addroleassignment(principalid=', string(body('{eu}')?['Id']), ',roledefid=', string({rd}), ')')"))
                foreach(y, "Pour_participant", f"coalesce({I}?['Participants'], createArray())", part)
                cond(y, "Si_candidature_a_planifier",
                     f"contains(createArray('Transmise à l''administration', 'Entretien réalisé', 'En attente de décision'), {cst})",
                     lambda w: flux_transition(w, "CAND_T07", "Candidature", CAND, CID, cidobj, cst, "Entretien planifié", "CAND-T07",
                                               candidature_controls(f, C, CID, controls_needed_for("CAND-T07")), src=C))

                def teams(w):
                    parts = select(w, "Participants_emails", f"coalesce({I}?['Participants'], createArray())", at("item()?['Email']"))
                    mt = w.add("Creer_reunion_Teams", conn_action(f, "shared_teams", "CreateTeamsMeeting", {
                        "calendarid": "Calendar", "body/subject": ip(f"concat('[HNCS-R&D] Entretien ', {idobj})"),
                        "body/start/dateTime": ip(f"formatDateTime(convertTimeZone({I}?['DateHeure'], 'UTC', '{TZ}'), 'yyyy-MM-ddTHH:mm:ss')"),
                        "body/start/timeZone": TZ,
                        "body/end/dateTime": ip(f"formatDateTime(convertTimeZone(addHours({I}?['DateHeure'], 1), 'UTC', '{TZ}'), 'yyyy-MM-ddTHH:mm:ss')"),
                        "body/end/timeZone": TZ, "body/requiredAttendees": ip(f"join(body('{parts}'), ';')"),
                        "body/body/content": ip(f"concat('<p>Entretien ', {idobj}, '</p>')"), "body/body/contentType": "html",
                        "body/isOnlineMeeting": True, "body/onlineMeetingProvider": "teamsForBusiness"}))
                    patch_item(w, "Renseigner_LienReunion", ENT, ID, {"LienReunion": ip(f"body('{mt}')?['onlineMeeting']?['joinUrl']")}, I)
                cond(y, "Si_reunion_Teams", f"and(equals({P('Fonction.CreationReunionTeams', 'Non')}, 'Oui'), empty({I}?['LienReunion']))", teams)
                cond(y, "Si_rappel_a_reinitialiser", truthy(I + "?['RappelEnvoye']"),
                     lambda w: patch_item(w, "Reinitialiser_rappel", ENT, ID, {"RappelEnvoye": at("false")}, I))
            cond(z, "Si_planification", f"or({creation}, {chg('DateHeure')}, {chg('Statut')}, {chg('Participants')})", ev)

        def realise(z):
            def ev(y):
                patch_item(y, "Tracer_saisie_resultat", ENT, ID, {
                    "SaisiPar": ip("triggerOutputs()?['body/Editor/Email']"), "DateSaisieResultat": ip("utcNow()")}, I)
                cond(y, "Si_candidature_en_entretien", f"equals({cst}, 'Entretien planifié')",
                     lambda w: flux_transition(w, "CAND_T09", "Candidature", CAND, CID, cidobj, q("Entretien planifié"),
                                               "Entretien réalisé", "CAND-T09",
                                               candidature_controls(f, C, CID, controls_needed_for("CAND-T09")), src=C))
                get_item(y, "Relire_candidature", CAND, CID)
                R = "body('Relire_candidature')"
                notify(y, "N-11", [f.group_emails("G_RD"), resp(R)], {
                    "IdHNCS": cidobj, "Statut": f"{R}?['Statut']?['Value']", "Lien": item_link(CAND, CID)})
            cond(z, "Si_resultat_saisi", f"and(not(empty({I}?['Resultat']?['Value'])), or({creation}, {chg('Statut')}, {chg('Resultat')}))", ev)

        def reporte(z):
            def ev(y):
                pl = get_items(y, "Entretiens_planifies_restants", ENT, filter_=f"CandidatureId eq @{{{CID}}} and Statut eq 'Planifié'",
                               fields=("Candidature", "Statut"))

                def t08(w):
                    flux_transition(w, "CAND_T08", "Candidature", CAND, CID, cidobj, q("Entretien planifié"),
                                    "Transmise à l'administration", "CAND-T08",
                                    candidature_controls(f, C, CID, controls_needed_for("CAND-T08")), src=C,
                                    after_fn=lambda v: notify(v, "N-04", [P("Destinataires.Administration")], {
                                        "IdHNCS": cidobj, "NomCandidat": f"{C}?['Title']", "Lien": item_link(CAND, CID)}))
                cond(y, "Si_plus_aucun_entretien", f"and(equals(length(body('{pl}')?['value']), 0), equals({cst}, 'Entretien planifié'))", t08)
            cond(z, "Si_report_ou_annulation", f"or({creation}, {chg('Statut')})", ev)

        switch(s, "Selon_statut_entretien", f"{I}?['Statut']?['Value']",
               {"Planifié": planifie, "Réalisé": realise, "Reporté": reporte, "Annulé": reporte})
    standard_shell(f, body, ENT, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-03-ent"]
    return f


def pa03_cand():
    f = Flow("PA-03-cand", "PA-03", "HNCS-RD PA-03 — Entretien (candidatures)", 2, "Automatisé", "SharePointItem", CAND,
             targets=targets("PA-03", CAND), objet="Candidature")
    sp_trigger(f, CAND, "GetOnUpdatedItems", [ANTI_LOOP, cond_transition(), cond_targets(f.targets)])

    def body(s):
        def attente(z, env):
            notify(z, "N-12", [P("Destinataires.Administration")], {"IdHNCS": env.IDOBJ, "NomCandidat": f"{env.I}?['Title']", "Lien": env.LIEN})

        def retenue(z, env):
            I = env.I
            f.use(CAND, "DateDecisionFinale", "Title")
            patch_item(z, "Date_decision_finale", CAND, env.ID, {"DateDecisionFinale": at(f"coalesce({I}?['DateDecisionFinale'], utcNow())")}, I)
            notify(z, "N-13", [f.group_emails("G_ADM"), resp(I)], {"IdHNCS": env.IDOBJ, "NomCandidat": f"{I}?['Title']",
                                                                   "Lien": env.LIEN}, teams_to=[resp(I)])
        needed = MODEL.controls_for("Candidature", f.targets)
        transition_body(s, f, CAND, "Candidature", effects={"En attente de décision": attente, "Retenue": retenue},
                        controls=candidature_controls(f, I_EL, f"{I_EL}?['ID']", needed))
    standard_shell(f, body, CAND, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-03-cand"]
    return f


def pa03b():
    f = Flow("PA-03b", "PA-03b", "HNCS-RD PA-03b — Rappels d'entretien et demande de résultat", 2, "Planifié", "Recurrence",
             recurrence="Toutes les heures de 07:00 à 20:00 (heure de Paris)")
    recurrence_trigger(f, {"frequency": "Day", "interval": 1,
                           "schedule": {"hours": [str(h) for h in range(7, 21)], "minutes": [0]}})
    ENT = "Entretiens"

    def body(s):
        e = get_items(s, "Entretiens_planifies", ENT, filter_="Statut eq 'Planifié'",
                      fields=("Statut", "DateHeure", "RappelEnvoye", "DemandeResultatEnvoyee", "Participants", "Candidature",
                              "Modalite", "LienReunion", "IdHNCS", "ID"))
        dh = "ticks(item()?['DateHeure'])"
        a = filt(s, "A_rappeler", f"body('{e}')?['value']",
                 f"and(not(equals(item()?['RappelEnvoye'], true)), greaterOrEquals({dh}, ticks(utcNow())), "
                 f"lessOrEquals({dh}, ticks(addHours(utcNow(), int({P('Delai.RappelEntretienHeures', '24')})))))")

        def rappel(r, loop):
            it = f"items('{loop}')"
            get_item(r, "Candidature_entretien", CAND, f"{it}?['Candidature']?['Id']")
            C = "body('Candidature_entretien')"
            f.use(CAND, "Title", "IdHNCS")
            pe = select(r, "Emails_participants", f"coalesce({it}?['Participants'], createArray())", at("item()?['Email']"))
            parts = f"join(body('{pe}'), ';')"
            notify(r, "N-10", [parts], {
                "IdHNCS": f"coalesce({it}?['IdHNCS'], string({it}?['ID']))", "IdCandidature": f"coalesce({C}?['IdHNCS'], '')",
                "NomCandidat": f"{C}?['Title']", "Date": dtloc(it + "?['DateHeure']"), "Modalite": f"{it}?['Modalite']?['Value']",
                "LienReunion": f"coalesce({it}?['LienReunion'], '—')", "Lien": item_link(ENT, f"{it}?['ID']")}, teams_to=[parts])
            patch_item(r, "Rappel_envoye", ENT, f"{it}?['ID']", {"RappelEnvoye": at("true")}, it)
        foreach(s, "Pour_rappel", f"body('{a}')", rappel)
        b = filt(s, "Resultats_a_demander", f"body('{e}')?['value']",
                 f"and(not(equals(item()?['DemandeResultatEnvoyee'], true)), less({dh}, ticks(addHours(utcNow(), -2))))")

        def demande(r, loop):
            it = f"items('{loop}')"
            notify(r, "N-14", [P("Destinataires.Administration")], {
                "IdHNCS": f"coalesce({it}?['IdHNCS'], string({it}?['ID']))", "IdCandidature": f"coalesce({it}?['Candidature']?['Value'], '')",
                "Date": dtloc(it + "?['DateHeure']"), "Lien": item_link(ENT, f"{it}?['ID']")})
            patch_item(r, "Demande_resultat_envoyee", ENT, f"{it}?['ID']", {"DemandeResultatEnvoyee": at("true")}, it)
        foreach(s, "Pour_demande_resultat", f"body('{b}')", demande)
    standard_shell(f, body)
    f.doc = DOC["PA-03b"]
    return f


# --------------------------------------------------------------------------------------------
# PA-04 — Intégration (candidatures, alternants, actions) et PA-04b
# --------------------------------------------------------------------------------------------

def alternant_setup(z, f, A, AID, aidobj, rc, resp_expr, eco_resp, tag):
    """Étapes 5 et 6 de PA-04 : dossiers cloisonnés, accès du référent, liens, checklist « Accueil »."""
    f.use(ALT, "CompteM365", "LienDossierSuivi", "LienDossierAdministratif")
    suivi = ensure_folder(z, f"suivi_{tag}", "SuiviAlternants", aidobj)
    grant_folder(z, f"suivi_{tag}", "SuiviAlternants", aidobj, [("user", f"{A}?['CompteM365']?['Email']", "CSS"), ("user", rc, "CSS")])
    ev_rel = f"concat({aidobj}, '/_Evaluations')"
    ensure_folder(z, f"evaluations_{tag}", "SuiviAlternants", ev_rel)
    grant_folder(z, f"evaluations_{tag}", "SuiviAlternants", ev_rel,
                 [("group", "G_PROP", "FC"), ("group", "G_DRD", "R"), ("user", rc, "CSS")], copy=False)
    adm = ensure_folder(z, f"adm_alt_{tag}", "Administration", f"concat('Alternants/', {aidobj})")
    op_rel = f"concat('Alternants/', {aidobj}, '/Operationnel')"
    ensure_folder(z, f"operationnel_{tag}", "Administration", op_rel)
    grant_folder(z, f"operationnel_{tag}", "Administration", op_rel, [("group", "G_RD", "R")])
    grant_item(z, f"fiche_{tag}", ALT, AID, [("user", rc, "R")])
    patch_item(z, f"Liens_dossiers_alternant_{tag}", ALT, AID, {
        "LienDossierSuivi": ip(f"coalesce({A}?['LienDossierSuivi'], {suivi})"),
        "LienDossierAdministratif": ip(f"coalesce({A}?['LienDossierAdministratif'], {adm})")}, A)
    generate_actions(z, f"acc_{tag}", "Accueil", {"Alternant": AID}, f"AlternantId eq @{{{AID}}} and Contexte eq 'Accueil'", TODAY,
                     role_map(resp_analyse=resp_expr, referent=rc, eco_resp=eco_resp))
    log(z, f"Journaliser_checklist_accueil_{tag}", "Info", q("Checklist « Accueil » générée"), ALT, AID, aidobj)
    return suivi


def pa04_cand():
    f = Flow("PA-04-cand", "PA-04", "HNCS-RD PA-04 — Intégration (candidatures)", 2, "Automatisé", "SharePointItem", CAND,
             targets=targets("PA-04", CAND), objet="Candidature")
    sp_trigger(f, CAND, "GetOnUpdatedItems", [ANTI_LOOP, cond_transition(), cond_targets(f.targets)])
    f.use(CAND, "ResponsableAnalyse", "Title", "IdHNCS", "Etablissement", "Formation", "PolePressenti", "ReferentPressenti",
          "DateDemarrageConfirmee", "DateFinPrevue", "IdAlternant", "DateIntegration", "ID")

    def body(s):
        def formalites(z, env):
            I = env.I
            generate_actions(z, "form", CTX_FORM, {"Candidature": env.ID},
                             f"CandidatureId eq @{{{env.ID}}} and Contexte eq {odata(CTX_FORM)}", TODAY, role_map(resp_analyse=resp(I)))
            log(z, "Journaliser_checklist_formalites", "Info", q("Checklist « Formalités d'intégration » générée"), CAND, env.ID, env.IDOBJ)
            url = ensure_folder(z, "adm_cand", "Administration", f"concat('Candidatures/', {env.IDOBJ})")
            tab = checklist_table(z, "form", f"CandidatureId eq @{{{env.ID}}} and Contexte eq {odata(CTX_FORM)}")
            notify(z, "N-15", [P("Destinataires.Administration")], {
                "IdHNCS": env.IDOBJ, "NomCandidat": f"{I}?['Title']", "TableauActions": tab, "Lien": env.LIEN, "LienDossier": url})

        def integree(z, env):
            I = env.I
            ex = get_items(z, "Alternant_existant", ALT, filter_=f"CandidatureSourceId eq @{{{env.ID}}}", fields=("CandidatureSource",), top=1)

            def create(y):
                f.use(ALT, "EmpreinteReferent")
                p, idc = create_with_id(y, "Creer_alternant", ALT, {
                    "Title": ip(f"{I}?['Title']"), "CandidatureSource": at(env.ID), "Etablissement": at(f"{I}?['Etablissement']?['Id']"),
                    "Formation": at(f"{I}?['Formation']"), "Pole": at(f"{I}?['PolePressenti']?['Id']"),
                    "ReferentPrincipal": at(f"{I}?['ReferentPressenti']?['Id']"),
                    "EmpreinteReferent": ip(f"string(coalesce({I}?['ReferentPressenti']?['Id'], ''))"),
                    "DateDebut": ip(dloc(I + "?['DateDemarrageConfirmee']")), "DateFin": ip(dloc(I + "?['DateFinPrevue']")),
                    "Statut": "À intégrer"})
                nb = f"body('{p}')"
                flux_creation(y, "ALT_T01", "Alternant", ALT, f"{nb}?['ID']", idc, "À intégrer", "ALT-T01",
                              alternant_controls(f, nb, f"{nb}?['ID']", controls_needed_for("ALT-T01"), q("∅"), "true"))
                log(y, "Journaliser_creation_alternant", "Info", f"concat('Fiche alternant ', {idc}, ' créée depuis ', {env.IDOBJ})",
                    ALT, f"{nb}?['ID']", idc)
            cond(z, "Si_alternant_absent", f"equals(length(body('{ex}')?['value']), 0)", create)
            al = get_items(z, "Lire_alternant", ALT, filter_=f"CandidatureSourceId eq @{{{env.ID}}}",
                           fields=("CandidatureSource", "IdHNCS", "ID", "CompteM365", "LienDossierSuivi", "LienDossierAdministratif",
                                   "DateDebut", "Title", "Pole", "ReferentPrincipal", "Etablissement", "DateFin", "Formation"), top=1)
            A = first(al)
            AID = f"{A}?['ID']"
            aidobj = f"{A}?['IdHNCS']"
            patch_item(z, "Lier_candidature_alternant", CAND, env.ID, {
                "IdAlternant": ip(aidobj), "DateIntegration": at(f"coalesce({I}?['DateIntegration'], utcNow())")}, I)
            ref = lookup_first(z, "Referent_pressenti", "Referents", f"{I}?['ReferentPressenti']?['Id']", fields=("Compte", "Title"))
            rc = f"{ref}?['Compte']?['Email']"
            eco = lookup_first(z, "Etablissement_candidature", "Etablissements", f"{I}?['Etablissement']?['Id']",
                               fields=("Statut", "ResponsableHNCS", "Title"))
            suivi = alternant_setup(z, f, A, AID, aidobj, rc, resp(I), f"{eco}?['ResponsableHNCS']?['Email']", "int")
            f.status("Etablissements", "Établissement d'accueil")
            cond(z, "Si_etablissement_prospect", f"contains(createArray('Prospect', 'Contact établi'), coalesce({eco}?['Statut']?['Value'], ''))",
                 lambda y: patch_item(y, "Etablissement_accueil", "Etablissements", f"{eco}?['ID']",
                                      {"Statut": "Établissement d'accueil"}, eco))
            notify(z, "N-16", [f.group_emails("G_RD"), rc, P("Destinataires.Administration")], {
                "IdAlternant": aidobj, "NomAlternant": f"{A}?['Title']", "IdCandidature": env.IDOBJ,
                "DateDebut": dfr(A + "?['DateDebut']"), "Pole": f"coalesce({I}?['PolePressenti']?['Value'], '')",
                "Referent": f"coalesce({ref}?['Title'], '—')", "Lien": item_link(ALT, AID), "LienDossierSuivi": suivi}, teams_to=[rc])

        needed = MODEL.controls_for("Candidature", f.targets)
        transition_body(s, f, CAND, "Candidature", effects={"Formalités en cours": formalites, "Intégrée": integree},
                        controls=candidature_controls(f, I_EL, f"{I_EL}?['ID']", needed))
    standard_shell(f, body, CAND, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-04-cand"]
    return f


def pa04_alt():
    f = Flow("PA-04-alt", "PA-04", "HNCS-RD PA-04 — Intégration (alternants)", 2, "Automatisé", "SharePointItem", ALT,
             targets=targets("PA-04", ALT), objet="Alternant")
    tgt = f.targets
    sp_trigger(f, ALT, "GetOnUpdatedItems", [ANTI_LOOP,
               "@or(and(not(equals(coalesce(triggerOutputs()?['body/Statut/Value'], ''), coalesce(triggerOutputs()?['body/StatutPrecedent'], ''))), "
               f"contains({arr(tgt)}, triggerOutputs()?['body/Statut/Value'])), not(empty(triggerOutputs()?['body/CompteM365/Email'])), "
               "not(equals(string(coalesce(triggerOutputs()?['body/ReferentPrincipal/Id'], '')), coalesce(triggerOutputs()?['body/EmpreinteReferent'], ''))))"])
    f.use(ALT, "CompteM365", "IdHNCS", "ReferentPrincipal", "EmpreinteReferent", "Etablissement", "Title")
    acteur = "toLower(coalesce(triggerOutputs()?['body/Editor/Email'], ''))"

    def body(s):
        def pre(z, env):
            I = env.I
            cur_ref = f"string(coalesce({I}?['ReferentPrincipal']?['Id'], ''))"
            emp = f"coalesce({I}?['EmpreinteReferent'], '')"

            # P-09 : référent principal dérivé (PA-04 / PA-05) — toute modification manuelle est rétablie (N-91)
            def protect(y):
                patch_item(y, "Retablir_referent_principal", ALT, env.ID, {
                    "ReferentPrincipal": at(f"if(empty({emp}), null, int({emp}))")}, I)
                log(y, "Referent_principal_retabli", "Avertissement", q("Modification manuelle du référent principal annulée (P-09)"),
                    ALT, env.ID, env.IDOBJ)
                notify(y, "N-91", [acteur], {"IdHNCS": env.IDOBJ, "Champs": q("Référent principal"), "Lien": env.LIEN}, teams_to=[acteur])
                terminate(y, "Fin_referent_retabli")

            def init(y):
                patch_item(y, "Initialiser_EmpreinteReferent", ALT, env.ID, {"EmpreinteReferent": ip(cur_ref)}, I)
            cond(z, "Si_referent_modifie", f"not(equals({cur_ref}, {emp}))",
                 lambda y: cond(y, "Si_empreinte_referent_connue", f"and(not(empty({emp})), not(empty({I}?['StatutPrecedent'])))", protect, init))

            ch = item_changes(z, "Changements", ALT, env.ID)
            changed = f"equals(string(coalesce(body('{ch}')?['ColumnHasChanged']?['CompteM365'], false)), 'True')"

            def grant(y):
                g = sp_http(y, "Dossier_suivi_existe", "GET",
                            ip(f"concat('_api/web/GetFolderByServerRelativeUrl(''', {lib_srv('SuiviAlternants', env.IDOBJ)}, ''')?$select=Exists')"))

                def ok(w):
                    grant_folder(w, "compte", "SuiviAlternants", env.IDOBJ, [("user", f"{I}?['CompteM365']?['Email']", "CSS")])

                def ko(w):
                    log(w, "Dossier_suivi_absent", "Avertissement", q("Compte Microsoft 365 renseigné mais dossier de suivi absent : accès non ajouté"),
                        ALT, env.ID, env.IDOBJ)
                cond(y, "Si_dossier_suivi_present", f"equals(string(coalesce(body('{g}')?['Exists'], false)), 'True')", ok, ko,
                     after={g: ["Succeeded", "Failed"]})
            cond(z, "Si_compte_modifie", f"and({changed}, not(empty({I}?['CompteM365']?['Email'])))", grant)

            # v1.3.0 : rejouer les attributions de PA-05 pour les affectations actives de l'alternant
            def replay(y):
                am = f"{I}?['CompteM365']?['Email']"
                f.use("Affectations", "Alternant", "Sujet", "Statut", "ID")
                affs = get_items(y, "Affectations_actives", "Affectations",
                                 filter_=f"AlternantId eq @{{{env.ID}}} and (Statut eq 'Active' or Statut eq 'À risque' or Statut eq 'Bloquée')")

                def each(e, loop):
                    a = f"items('{loop}')"
                    grant_folder(e, "sujet_rejeu", "LivrablesRD", f"{a}?['Sujet']?['Value']", [("user", am, "CSS")])
                    grant_item(e, "affectation_rejeu", "Affectations", f"{a}?['ID']", [("user", am, "R")])
                    f.use("Livrables", "Affectation", "Proprietaire", "ID")
                    lv = get_items(e, "Livrables_de_l_alternant", "Livrables", filter_=f"AffectationId eq @{{{a}?['ID']}}")
                    mine = filt(e, "Livrables_dont_il_est_auteur", f"body('{lv}')?['value']",
                                f"equals(toLower(coalesce(item()?['Proprietaire']?['Email'], '')), toLower({am}))")
                    foreach(e, "Pour_livrable_rejeu", f"body('{mine}')",
                            lambda g, l2: grant_item(g, "livrable_rejeu", "Livrables", f"items('{l2}')?['ID']", [("user", am, "CSS")]))
                    present = list_exists(e, "CR_rejeu", "ComptesRendus")

                    def crs(g):
                        f.use("ComptesRendus", "Affectation", "Alternant", "ID")
                        c = get_items(g, "CR_de_l_alternant", "ComptesRendus", filter_=f"AffectationId eq @{{{a}?['ID']}} and AlternantId eq @{{{env.ID}}}")
                        foreach(g, "Pour_CR_rejeu", f"body('{c}')?['value']",
                                lambda h, l3: grant_item(h, "cr_rejeu", "ComptesRendus", f"items('{l3}')?['ID']", [("user", am, "CSS")]))
                    cond(e, "Si_CR_deployes", present, crs)
                foreach(y, "Pour_affectation_active", f"body('{affs}')?['value']", each)
            cond(z, "Si_compte_a_rejouer", f"and({changed}, not(empty({I}?['CompteM365']?['Email'])))", replay)

        def a_integrer(z, env):
            # Création manuelle (reprise de l'existant, ALT-T01 par DIRECTION_RD) : étapes 5 et 6 de PA-04
            def manuel(y):
                I = env.I
                ref = lookup_first(y, "Referent_principal", "Referents", f"{I}?['ReferentPrincipal']?['Id']", fields=("Compte",))
                eco = lookup_first(y, "Etablissement_alternant", "Etablissements", f"{I}?['Etablissement']?['Id']", fields=("ResponsableHNCS",))
                alternant_setup(y, f, I, env.ID, env.IDOBJ, f"{ref}?['Compte']?['Email']", None,
                                f"{eco}?['ResponsableHNCS']?['Email']", "man")
            cond(z, "Si_creation_manuelle", f"equals({env.AVANT}, '∅')", manuel)

        def actif(z, env):
            # Prolongation (ALT-T08) : échéance des actions de clôture ouvertes recalculée sur la nouvelle DateFin ; bilan conservé
            def prolongation(y):
                f.use(ACT, "Alternant", "Contexte", "Statut", "Echeance", "ID")
                f.use(ALT, "DateFin")
                ac = get_items(y, "Actions_cloture_ouvertes", ACT,
                               filter_=f"AlternantId eq @{{{env.ID}}} and Contexte eq 'Clôture d''alternance' and Statut ne 'Terminée' and Statut ne 'Non applicable'")
                foreach(y, "Pour_action_cloture", f"body('{ac}')?['value']",
                        lambda e, loop: patch_item(e, "Nouvelle_echeance_cloture", ACT, f"items('{loop}')?['ID']",
                                                   {"Echeance": ip(dloc(env.I + "?['DateFin']"))}, f"items('{loop}')"))
                log(y, "Journaliser_prolongation", "Info", q("Prolongation (ALT-T08) : échéances de clôture recalculées, bilan conservé"),
                    ALT, env.ID, env.IDOBJ)
            cond(z, "Si_prolongation", f"equals({env.AVANT}, 'Fin planifiée')", prolongation)

        needed = MODEL.controls_for("Alternant", f.targets)
        transition_body(s, f, ALT, "Alternant", pre=pre, effects={"À intégrer": a_integrer, "Actif": actif},
                        controls=lambda y, tag: alternant_controls(f, I_EL, f"{I_EL}?['ID']", needed, "outputs('Statut_avant')", "false")(y, tag))
    standard_shell(f, body, ALT, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-04-alt"]
    return f


def pa04_act():
    f = Flow("PA-04-act", "PA-04", "HNCS-RD PA-04 — Intégration (actions d'intégration)", 2, "Automatisé", "SharePointItem", ACT)
    sp_trigger(f, ACT, "GetOnUpdatedItems", [ANTI_LOOP, "@equals(triggerOutputs()?['body/Contexte/Value'], 'Formalités d''intégration')"])
    f.use(ACT, "Contexte", "Candidature", "EmpreinteAction", "Bloquante", "Statut", "Responsable", "IdHNCS", "ID")
    acteur = "toLower(coalesce(triggerOutputs()?['body/Editor/Email'], ''))"

    def body(s):
        I = I_EL
        get_item(s, "Lire_element", ACT, "triggerOutputs()?['body/ID']")
        ID = f"{I}?['ID']"
        idobj = ensure_idhncs(s, ACT, I, ID, "el")
        cur = compose(s, "Empreinte_courante", at(emp_action(I)))
        emp = f"coalesce({I}?['EmpreinteAction'], '')"
        # 1. G_ACTION_FORMALITE (P-09)
        changed_bloq = f"not(equals(json({emp})?['Bloquante'], equals({I}?['Bloquante'], true)))"
        st_changed = f"not(equals(json({emp})?['Statut'], {I}?['Statut']?['Value']))"
        adm = f"contains(split({f.group_emails('G_ADM')}, ';'), {acteur})"
        resp_ok = f"equals({acteur}, toLower(coalesce({I}?['Responsable']?['Email'], '#')))"
        bloquante = f"or(equals(json({emp})?['Bloquante'], true), equals({I}?['Bloquante'], true))"
        # Bloquante : ADMIN seul ; action bloquante → « Non applicable » : ADMIN seul ; → « Terminée » : ADMIN ou responsable
        v_bloq = f"and({changed_bloq}, not({adm}))"
        v_na = f"and({st_changed}, equals({I}?['Statut']?['Value'], 'Non applicable'), {bloquante}, not({adm}))"
        v_term = f"and({st_changed}, equals({I}?['Statut']?['Value'], 'Terminée'), not(or({adm}, {resp_ok})))"

        def differs(y):
            def violation(w):
                patch_item(w, "Retablir_action", ACT, ID, {
                    "Bloquante": at(f"json({emp})?['Bloquante']"), "Statut": ip(f"json({emp})?['Statut']")}, I)
                f.status(ACT)
                log(w, "Action_retablie", "Avertissement", q("G_ACTION_FORMALITE : modification non autorisée annulée (P-09)"), ACT, ID, idobj)
                notify(w, "N-92", [acteur], {"IdHNCS": idobj, "Champs": q("Bloquante / passage à « Terminée » ou « Non applicable »"),
                                             "RoleHabilite": q("Bloquante et « Non applicable » d'une action bloquante : Administration (ADMIN) ; « Terminée » : ADMIN ou responsable désigné"),
                                             "Lien": item_link(ACT, ID)}, teams_to=[acteur])
                terminate(w, "Fin_action_retablie")

            def legit(w):
                patch_item(w, "Mettre_a_jour_EmpreinteAction", ACT, ID, {"EmpreinteAction": ip(f"outputs('{cur}')")}, I)
            cond(y, "Si_modification_non_autorisee",
                 f"and(not(empty({emp})), or({v_bloq}, {v_na}, {v_term}))", violation, legit)
        cond(s, "Si_empreinte_differente",
             f"or(empty({emp}), not(equals(json({emp})?['Bloquante'], equals({I}?['Bloquante'], true))), "
             f"not(equals(string(json({emp})?['Statut']), string({I}?['Statut']?['Value']))))", differs)
        # Permissions du responsable (§ 7.4)
        grant_item(s, "responsable", ACT, ID, [("user", f"{I}?['Responsable']?['Email']", "CSS")])
        # 2. Formalités complètes → N-17 (une seule fois), sans changement de statut
        get_items(s, "Candidature_liee", CAND, filter_=f"ID eq @{{coalesce({I}?['Candidature']?['Id'], 0)}}", fields=("Statut", "IdHNCS"), top=1)
        C = first("Candidature_liee")
        f.use(CAND, "Statut", "IdHNCS", "ID")
        CID = f"{C}?['ID']"
        cidobj = f"coalesce({C}?['IdHNCS'], string({CID}))"

        def check(y):
            a = get_items(y, "Actions_formalites", ACT, filter_=f"CandidatureId eq @{{{CID}}} and Contexte eq {odata(CTX_FORM)}",
                          fields=("Candidature", "Contexte", "Bloquante", "Statut", "Preuve", "Commentaire"))
            bad = filt(y, "Actions_bloquantes_ouvertes", f"body('{a}')?['value']", blocking_bad_where())
            f.read("JournalFlux", "Title", "IdObjet", "Message")
            j = get_items(y, "Marqueur_N17", "JournalFlux", filter_=f"Title eq 'PA-04' and IdObjet eq {odq(cidobj)}")
            sent = filt(y, "N17_deja_envoyee", f"body('{j}')?['value']", "equals(item()?['Message'], 'N-17 envoyée')")

            def send(w):
                notify(w, "N-17", [P("Destinataires.Administration")], {"IdHNCS": cidobj, "Lien": item_link(CAND, CID)})
                log(w, "Marquer_N17", "Info", q("N-17 envoyée"), CAND, CID, cidobj)
            cond(y, "Si_formalites_completes", f"and(greater(length(body('{a}')?['value']), 0), equals(length(body('{bad}')), 0), equals(length(body('{sent}')), 0))", send)
        cond(s, "Si_formalites_en_cours", f"and(not(empty({I}?['Candidature']?['Id'])), equals({C}?['Statut']?['Value'], 'Formalités en cours'))", check)
    standard_shell(f, body, ACT, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-04-act"]
    return f


def pa04b():
    f = Flow("PA-04b", "PA-04b", "HNCS-RD PA-04b — Activation des alternants et rappels d'actions", 2, "Planifié", "Recurrence",
             recurrence="Quotidien 06:30 (heure de Paris)")
    recurrence_trigger(f, {"frequency": "Day", "interval": 1, "schedule": {"hours": ["6"], "minutes": [30]}})

    def body(s):
        a = get_items(s, "Alternants_a_integrer", ALT, filter_="Statut eq 'À intégrer'",
                      fields=("Statut", "DateDebut", "ReferentPrincipal", "IdHNCS", "ID", "Title"))
        due = filt(s, "Date_debut_atteinte", f"body('{a}')?['value']", f"and(not(empty(item()?['DateDebut'])), lessOrEquals({dloc("item()?['DateDebut']")}, {TODAY}))")

        def each(e, loop):
            it = f"items('{loop}')"
            AID = f"{it}?['ID']"
            aid = f"coalesce({it}?['IdHNCS'], string({AID}))"

            def after(w):
                ref = lookup_first(w, "Referent_principal", "Referents", f"{it}?['ReferentPrincipal']?['Id']", fields=("Compte",))
                rc = f"{ref}?['Compte']?['Email']"
                notify(w, "N-18", [rc], {"IdAlternant": aid, "NomAlternant": f"{it}?['Title']", "Lien": item_link(ALT, AID)}, teams_to=[rc])
            flux_transition(e, "ALT_T02", "Alternant", ALT, AID, aid, q("À intégrer"), "Actif", "ALT-T02",
                            alternant_controls(f, it, AID, controls_needed_for("ALT-T02"), q("À intégrer"), "true"), src=it, after_fn=after)
        foreach(s, "Pour_alternant", f"body('{due}')", each)
        acts = get_items(s, "Actions_ouvertes", ACT, filter_="Statut ne 'Terminée' and Statut ne 'Non applicable'",
                         fields=("Statut", "Echeance", "DernierRappel", "Responsable", "RoleResponsable", "Title", "Description",
                                 "PreuveAttendue", "IdHNCS", "ID"))
        marker = f"concat('Rappel:', {TODAY})"
        lim = f"addDays({TODAY}, int({P('Delai.RappelActionJours', '2')}), 'yyyy-MM-dd')"
        r = filt(s, "Actions_a_rappeler", f"body('{acts}')?['value']",
                 f"and(not(empty(item()?['Echeance'])), lessOrEquals({dloc("item()?['Echeance']")}, {lim}), not(equals(coalesce(item()?['DernierRappel'], ''), {marker})))")
        fallback = role_map()
        fallback["ECOLES"] = f.group_emails("G_ECO")

        def rappel(e, loop):
            it = f"items('{loop}')"
            rr = f"{it}?['Responsable']?['Email']"
            to = f"if(empty({rr}), {role_resolution(it + "?['RoleResponsable']?['Value']", fallback)}, {rr})"
            notify(e, "N-19", [to], {"IdHNCS": f"coalesce({it}?['IdHNCS'], string({it}?['ID']))", "Action": f"{it}?['Title']",
                                     "Date": dfr(it + "?['Echeance']"), "Description": f"coalesce({it}?['Description'], '—')",
                                     "PreuveAttendue": f"coalesce({it}?['PreuveAttendue'], '—')", "Lien": item_link(ACT, f"{it}?['ID']")},
                   teams_to=[rr])
            patch_item(e, "Memoriser_rappel", ACT, f"{it}?['ID']", {"DernierRappel": ip(marker)}, it)
        foreach(s, "Pour_action", f"body('{r}')", rappel)
    standard_shell(f, body)
    f.doc = DOC["PA-04b"]
    return f


BUILDERS = [pa01a, pa01b, pa02, pa02b, pa03_ent, pa03_cand, pa03b, pa04_cand, pa04_alt, pa04_act, pa04b]

# --------------------------------------------------------------------------------------------
# Fiches (contenu rédactionnel)
# --------------------------------------------------------------------------------------------
DOC = {
    "PA-01a": dict(
        objectif="Enregistrer proprement toute nouvelle candidature (saisie manuelle, formulaire ou boîte mail R&D) : identifiant, signalement de doublon, dossier CV cloisonné, historique et notification de la R&D.",
        entrees="Élément `Candidatures` créé par une personne (statut « Reçue »).",
        etapes=["`IdHNCS` (`CAND-AAAA-NNNN`) s'il est vide.",
                "Socle : PA-00A sur CAND-T01 (∅ → Reçue, acteurs RD ou FLUX) ; refus → règle § 6.1-3 bis : PA-00B envoie l'élément à la corbeille du site, historise « Refusée — annulée » et notifie N-90 ; fin.",
                "Contrôle doublon si `Email` est renseigné : autre candidature non terminale (≠ Intégrée, Non retenue, Clôturée) avec le même `Email` (comparaison SharePoint insensible à la casse) → `DoublonPotentiel` = Oui et `DoublonDe` ; jamais de fusion ni de clôture.",
                "Dossier `01 — Recrutement/{AAAA}/{IdHNCS}` (AAAA = année de création, heure de Paris) créé s'il est absent ; héritage rompu avec copie (G_PROP FC, G_DRD et G_RD CSS ajoutés explicitement) ; `LienCV` = lien du dossier.",
                "PA-00B : historiser CAND-T01 si `StatutPrecedent` est vide (fixe `StatutPrecedent` = Reçue).",
                "Si `ResponsableAnalyse` est renseigné **et** `G_IDENTITE` satisfait : CAND-T02 (Reçue → À analyser, rôle FLUX, exception documentée) via PA-00A, contrôles `G_RESP_ANALYSE` et `G_IDENTITE`, écriture du statut, PA-00B, puis N-03 au responsable (règle § 6.1-8).",
                "N-01 au responsable d'analyse, sinon aux membres de G_RD (Teams au responsable) ; pour une candidature « À qualifier », N-01 demande la qualification de l'identité.",
                "Si `Fonction.AccuseReceptionActif` = Oui, identité qualifiée et `AccuseReceptionEnvoye` = Non : N-02 au candidat puis `AccuseReceptionEnvoye` = Oui."],
        sorties="Élément complété, dossier CV, historique, notifications.",
        erreurs="Socle : portée `Erreur` → PA-00C (N-99) puis échec ; la resoumission est idempotente (identifiant, doublon, dossier, historique et accusé déjà posés ne sont pas refaits). N-01 peut être renvoyée lors d'une resoumission (aucun marqueur prévu par la spec).",
        decision="Aucune décision : le doublon est **signalé**, jamais fusionné ni clôturé ; la présélection reste une décision de la R&D.",
        tests=["Saisie manuelle par un membre RD : identifiant, dossier, historique CAND-T01, N-01 à G_RD.",
               "Création par un membre ADMIN (hors acteurs de CAND-T01) : élément en corbeille, historique « Refusée — annulée », N-90.",
               "Saisie avec responsable : passage à « À analyser » par FLUX, historisé, N-03.",
               "Même e-mail qu'une candidature ouverte : doublon signalé, aucune autre modification.", "Accusé de réception désactivé par défaut : aucun courriel au candidat."]),
    "PA-01b": dict(
        objectif="Créer une candidature à partir d'un courriel déposé dans le dossier « Candidatures » de la boîte partagée R&D, puis appliquer le traitement commun de PA-01a.",
        entrees="Expéditeur, objet, `Internet-Message-Id`, date de réception et pièces jointes du courriel.",
        etapes=["Idempotence : si une candidature porte déjà ce `RefMessage` et que son dossier CV est posé → fin ; si elle existe sans dossier (exécution interrompue) → reprise sur l'élément existant.",
                "Canal déduit par `Canal.Regles` (`motif=canal`) : domaine de l'expéditeur, puis balise d'objet (ex. `[CANDIDATURE-SITE]`) ; valeur hors énumération ou aucune règle → « À qualifier ».",
                "Création de l'élément (`ModeReception` = Boîte mail R&D, `Statut` = Reçue, `DateReception`, `RefMessage`) : courriel de plateforme (règle de **domaine** donnant LinkedIn ou France Travail) → `Title` = « À qualifier – {RefMessage} », `Email` vide ; sinon `Email` = adresse de l'expéditeur et `Title` = partie locale de l'adresse (le nom affiché n'est pas exposé par le déclencheur standard, voir divergences).",
                "Traitement commun PA-01a (CAND-T01 par FLUX) ; en plus, enregistrement des pièces jointes non incorporées dont l'extension figure dans `Canal.ExtensionsAutorisees` dans le dossier CV, métadonnées `TypeDocument` = CV, `Candidature`, `IdObjet`.",
                "Pièce jointe refusée (type) → `JournalFlux` Avertissement (extension seulement, jamais le nom du fichier) ; la candidature est créée quand même."],
        sorties="Candidature créée et complétée, pièces jointes classées, historique CAND-T01 (Origine Flux).",
        erreurs="Socle (PA-00C) ; reprise par resoumission sans doublon grâce à `RefMessage`.",
        decision="Aucune : le flux enregistre, il ne juge pas la candidature ; l'identité d'un courriel de plateforme est qualifiée par la R&D.",
        tests=["Courriel `[CANDIDATURE-SITE]` → canal « Site HNCS », e-mail de l'expéditeur.", "Expéditeur `@linkedin.com` → « LinkedIn », titre « À qualifier – … », e-mail vide, pas de passage automatique à « À analyser ».",
               "Pièce jointe `.exe` refusée et journalisée.", "Même courriel retraité : aucun doublon."]),
    "PA-02": dict(
        objectif="Tracer l'analyse des candidatures par la R&D, exécuter la transmission à l'administration après présélection et notifier les clôtures.",
        entrees="Élément `Candidatures` modifié vers un statut de la partition PA-02, `StatutPrecedent`, `Editor`.",
        etapes=["Socle : lecture fraîche de l'élément, événement obsolète ignoré, `IdHNCS`.",
                "PA-00A (acteur = `Editor`) puis contrôles `G_*` renvoyés (`G_RESP_ANALYSE`, `G_IDENTITE`, `G_AVIS_ANALYSE`, `G_AUCUN_ENTRETIEN_ACTIF`, `G_DECISION_FINALE`, `G_DECIDEUR`) ; refus → PA-00B (annulation, N-90) et fin.",
                "**À analyser** / **En cours d'analyse** depuis « Reçue » : contrôle doublon si `Email` est renseigné (comme PA-01).",
                "**À analyser** : N-03 au responsable d'analyse ; réouverture (depuis Non retenue / Clôturée, CAND-T16) : `DateCloture` vidée puis N-03.",
                "**En cours d'analyse** : `DateAnalyse` si vide.",
                "**Présélectionnée** : `DateDecisionPreselection`, `DecisionPreselection` = Présélectionnée ; `DestinataireAdmin` = `Destinataires.Administration` ; héritage de l'élément et du dossier CV rompu (copie) puis CSS à G_ADM (`Recrutement.PartageTransmission` = Groupe, défaut) ou au seul `DestinataireAdmin` (= Destinataire, H-45) ; N-05 (liens uniquement, jamais de pièce jointe ni de recopie de l'avis) puis `DateTransmissionAdmin` ; PA-00B (CAND-T04) ; enfin CAND-T05 → « Transmise à l'administration » (FLUX) via PA-00A et PA-00B. Cette dernière étape est reprenable (exécutée aussi si le statut validé est déjà « Présélectionnée »).",
                "**Non retenue** : depuis l'analyse (CAND-T06) → `DateDecisionPreselection` et `DecisionPreselection` = Écartée ; depuis l'administration (CAND-T12, CAND-T17) → `DateDecisionFinale` ; `DateCloture` ; N-06 à G_RD (et à l'administration si la candidature lui avait été transmise) ; `Fonction.InformationCandidatAuto` = Oui → N-07 au candidat et `InformationCandidat` = Oui, sinon N-08 au responsable d'analyse.",
                "**Clôturée** : `DateCloture` ; N-06.", "**Transmise à l'administration** (retour CAND-T08 saisi à la main) : N-04 à l'administration.",
                "PA-00B (acceptée)."],
        sorties="Champs datés, permissions, notifications, historique.",
        erreurs="Échec de partage → la candidature reste « Présélectionnée » (StatutPrecedent non validé), erreur journalisée (PA-00C) ; la resoumission rejoue les étapes idempotentes (dates déjà posées conservées, permissions réattribuées sans doublon, N-05 non renvoyé si `DateTransmissionAdmin` est posée).",
        decision="La présélection et le refus sont saisis par la R&D (ou l'administration après transmission) ; le flux n'exécute que la transmission (CAND-T05) en conséquence de la présélection. `DecisionPreselection` n'est que le reflet de la décision portée par le statut.",
        tests=["Passage à « En cours d'analyse » d'une candidature « À qualifier » → refus `G_IDENTITE`.",
               "Présélection sans avis → refus `G_AVIS_ANALYSE`, statut rétabli, N-90.", "Présélection avec avis → G_ADM (ou le seul destinataire) voit la candidature et le dossier, N-05 sans pièce jointe ni avis, statut « Transmise à l'administration ».",
               "Réouverture par un membre RD (non DIRECTION_RD) → refusée.", "Non retenue par l'administration avant entretien sans `DecideurFinal` → refus `G_DECIDEUR` (CAND-T17)."]),
    "PA-02b": dict(
        objectif="Relancer les candidatures restées sans traitement au-delà du délai paramétré.",
        entrees="Candidatures « Reçue », « À analyser », « En cours d'analyse » ; `Delai.RelanceAnalyseJours`.",
        etapes=["Sélection des candidatures dont `DateStatut` (ou à défaut `DateReception`) est antérieure à maintenant − délai.",
                "N-09 au responsable d'analyse, sinon aux membres de G_RD, avec l'ancienneté en jours.", "Aucune modification de statut ni de donnée."],
        sorties="Relances.", erreurs="Socle (PA-00C) ; le passage du lendemain rattrape une exécution manquée.",
        decision="Aucune modification : simple relance.",
        tests=["Candidature reçue il y a 6 jours (délai 5) → N-09.", "Candidature « Présélectionnée » ancienne → aucune relance.",
               "Une exécution par jour (08:00) : au plus une relance par jour en fonctionnement normal."]),
    "PA-03-ent": dict(
        objectif="Refléter dans la candidature l'existence d'entretiens planifiés ou réalisés, historiser les entretiens et ouvrir l'accès des participants, sans jamais modifier le résultat saisi.",
        entrees="Élément `Entretiens` créé ou modifié par une personne ; changements de colonnes depuis le dernier passage (« Obtenir les modifications »).",
        etapes=["`IdHNCS` (`ENT-…`) si vide ; lecture de la candidature liée.",
                "Tout changement de `Statut` ou de `Resultat` (ou création) : élément `HistoriqueStatuts` (Objet = Entretien, Origine = Humain, Acceptée, `StatutApres` = statut et résultat) ; `StatutPrecedent` et `DateStatut` de l'entretien mis à jour.",
                "**Planifié** (création, nouvelle date, passage à Planifié ou changement des participants) : lecture (R) donnée aux `Participants` sur l'élément (§ 7.4) ; si la candidature est « Transmise à l'administration », « Entretien réalisé » ou « En attente de décision » → CAND-T07 (FLUX, `G_ENTRETIEN_PLANIFIE`) ; si `Fonction.CreationReunionTeams` = Oui et `LienReunion` vide → réunion Teams créée et `LienReunion` renseigné ; `RappelEnvoye` réinitialisé.",
                "**Réalisé** avec `Resultat` (création, changement de statut ou de résultat) : `SaisiPar` = auteur, `DateSaisieResultat` ; si la candidature est « Entretien planifié » → CAND-T09 (FLUX, `G_ENTRETIEN_REALISE`) ; N-11 (statut seul, sans commentaire) à G_RD et au responsable d'analyse.",
                "**Reporté / Annulé** : s'il ne reste aucun entretien « Planifié » et que la candidature est « Entretien planifié » → CAND-T08 (FLUX, `G_AUCUN_ENTRETIEN_ACTIF`) puis N-04 à l'administration (règle § 6.1-8)."],
        sorties="Statut de la candidature aligné, historique des entretiens, accès des participants, lien de réunion, traçabilité de la saisie du résultat.",
        erreurs="Socle (PA-00C). Une transition FLUX refusée par PA-00A ou un contrôle est journalisée en Avertissement et n'est pas appliquée.",
        decision="Le résultat d'entretien et la décision finale sont saisis par l'administration ; le flux ne fait que refléter l'existence d'un entretien planifié ou réalisé et ne modifie jamais `Resultat`.",
        tests=["Création d'un entretien planifié → candidature « Entretien planifié » (historique Origine Flux), participants en lecture, historique Objet = Entretien.",
               "Résultat saisi → « Entretien réalisé », N-11 sans commentaire.",
               "Annulation du seul entretien → retour « Transmise à l'administration » et N-04.", "Modification d'un champ sans incidence → aucune action."]),
    "PA-03-cand": dict(
        objectif="Contrôler les transitions de la candidature liées aux entretiens et à la décision finale saisies à la main.",
        entrees="Élément `Candidatures` modifié vers « Entretien planifié », « Entretien réalisé », « En attente de décision » ou « Retenue ».",
        etapes=["Socle et PA-00A ; contrôles `G_ENTRETIEN_PLANIFIE`, `G_ENTRETIEN_REALISE`, `G_DECISION_FINALE` ; refus → annulation et N-90.",
                "**Entretien planifié / réalisé** saisis à la main : contrôles uniquement.",
                "**En attente de décision** : N-12 à `Destinataires.Administration`.",
                "**Retenue** : `DateDecisionFinale` ; N-13 aux membres de G_ADM et au responsable d'analyse (« lancer les formalités »).", "PA-00B (acceptée)."],
        sorties="Date de décision, notifications, historique.", erreurs="Socle (PA-00C).",
        decision="La décision finale (Retenue / Non retenue) est saisie par l'administration ; le flux contrôle et notifie.",
        tests=["« Retenue » sans `DecideurFinal` → refus.", "« Entretien réalisé » saisi sans entretien réalisé avec résultat → refus.", "« Retenue » valide → N-13."]),
    "PA-03b": dict(
        objectif="Rappeler les entretiens à venir et demander la saisie des résultats en retard.",
        entrees="Entretiens « Planifié » ; `Delai.RappelEntretienHeures`.",
        etapes=["Entretiens dans les `Delai.RappelEntretienHeures` à venir avec `RappelEnvoye` = Non → N-10 aux participants puis `RappelEnvoye` = Oui.",
                "Entretiens dont la date est passée de plus de 2 h avec `DemandeResultatEnvoyee` = Non → N-14 à l'administration puis `DemandeResultatEnvoyee` = Oui."],
        sorties="Rappels et demandes, indicateurs posés (idempotence).", erreurs="Socle (PA-00C) ; rattrapage au passage horaire suivant.",
        decision="Aucune.", tests=["Entretien dans 20 h → un seul rappel.", "Entretien passé de 3 h → une seule demande de résultat."]),
    "PA-04-cand": dict(
        objectif="Lancer les formalités d'intégration et, à la confirmation, créer la fiche alternant et ses dossiers cloisonnés — uniquement si les formalités sont au bon stade (P-02).",
        entrees="Élément `Candidatures` modifié vers « Formalités en cours » ou « Intégrée ».",
        etapes=["**Formalités en cours** (CAND-T13) : PA-00A ; actions générées depuis `ModelesActions` (contexte « Formalités d'intégration », `Actif` = Oui), une par `Code`, liées à la candidature, échéance = aujourd'hui + `DelaiJours`, responsable résolu (§ 8.1 : ADMIN → `Destinataires.Administration`, RD → responsable d'analyse sinon `Destinataires.DirectionRD`, DIRECTION_RD → `Destinataires.DirectionRD`, PROPRIETAIRE → `Destinataires.Support`), CSS du responsable sur l'action, `EmpreinteAction` initialisée (idempotent par Candidature + `CodeModeleAction`) ; dossier `02 — Administration/Candidatures/{CAND}` (héritage de la bibliothèque) ; N-15 avec le tableau des actions ; PA-00B.",
                "**Intégrée** (CAND-T14) : PA-00A puis `G_INTEGRATION` ; échec → annulation (retour « Formalités en cours ») et N-90 détaillant les éléments manquants (a) à (e).",
                "Fiche `Alternants` liée existante (`CandidatureSource`) → rien n'est recréé ; sinon création (`Title`, `CandidatureSource`, `Etablissement`, `Formation`, `Pole` = `PolePressenti`, `ReferentPrincipal` = `ReferentPressenti` et `EmpreinteReferent`, `DateDebut`, `DateFin`, statut « À intégrer ») ; ALT-T01 par FLUX avec `G_SOURCE_ALTERNANT` (candidature source « Intégrée »), historisé ; `JournalFlux` Info.",
                "Candidature : `IdAlternant`, `DateIntegration`.",
                "Dossiers : `05 — Suivi des alternants/{ALT}` (copie + alternant si compte connu + référent : CSS), `/{ALT}/_Evaluations` (sans copie : G_PROP FC, G_DRD R, référent CSS ; alternant exclu), `02 — Administration/Alternants/{ALT}` et son sous-dossier `Operationnel` (G_RD : R) ; lecture du référent principal sur la fiche ; liens renseignés.",
                "Actions « Accueil » liées à l'alternant (idempotentes, responsables résolus, REFERENT → référent pressenti, ECOLES → responsable HNCS de l'établissement) ; `JournalFlux` Info.",
                "Établissement « Prospect » ou « Contact établi » → « Établissement d'accueil » (constat factuel, pas un partenariat).",
                "N-16 à G_RD, au référent pressenti et à l'administration ; PA-00B."],
        sorties="Checklists, fiche alternant, dossiers et permissions, notifications, historique.",
        erreurs="Création partielle → la resoumission reprend sans doublon (recherche par `CandidatureSource`, dossiers existants, `CodeModeleAction`).",
        decision="Le lancement des formalités et la confirmation d'intégration sont des actions de l'administration ; le flux vérifie (`G_INTEGRATION`) et crée la fiche.",
        tests=["« Intégrée » avec une action bloquante sans preuve → refus, N-90 listant l'action.", "Intégration valide → fiche « À intégrer », dossiers, `_Evaluations` inaccessible à l'alternant, `Operationnel` lisible par G_RD.",
               "Resoumission après échec → aucune deuxième fiche ni action en double."]),
    "PA-04-alt": dict(
        objectif="Contrôler la création manuelle et l'activation des alternants, protéger le référent principal dérivé et ouvrir le dossier de suivi quand le compte Microsoft 365 est renseigné.",
        entrees="Élément `Alternants` créé ou modifié (statut « À intégrer » / « Actif », compte renseigné, ou référent principal différent de son empreinte).",
        etapes=["P-09 : `ReferentPrincipal` différent de `EmpreinteReferent` (ID du référent en texte, § 6.5) sur une fiche existante → valeur rétablie, Avertissement, N-91 à l'auteur, fin ; empreinte vide (fiche importée ou création) → initialisée sans rien rétablir.",
                "Changement de `CompteM365` (« Obtenir les modifications ») : alternant ajouté (CSS) sur `05 — Suivi des alternants/{ALT}` (hors `_Evaluations`) ; dossier absent → Avertissement ; attributions de PA-05 rejouées pour ses affectations actives (dossier `04 — Livrables R&D/{SUJ}` CSS, lecture de l'affectation, CSS sur les livrables dont il est propriétaire et sur ses comptes rendus).",
                "Création manuelle (ALT-T01 par DIRECTION_RD, reprise de l'existant) : PA-00A puis `G_SOURCE_ALTERNANT` (`CandidatureSource` vide et `Fonction.RepriseExistantActive` = Oui) ; refus → corbeille (§ 6.1-3 bis) ; acceptation → étapes 5 et 6 de PA-04 (dossiers, accès du référent, checklist « Accueil »).",
                "Passage à « Actif » saisi à la main : PA-00A puis `G_DATE_DEBUT_ATTEINTE` (depuis « À intégrer » ; non exigé depuis « Suspendu ») ou `G_DATE_FIN_REPORTEE` (prolongation depuis « Fin planifiée », ALT-T08) ; refus → annulation et N-90. Prolongation acceptée : échéance des actions de clôture encore ouvertes = nouvelle `DateFin` ; le bilan « À réaliser » est conservé ; `JournalFlux` Info.",
                "PA-00B (acceptée)."],
        sorties="Permissions de l'alternant, dossiers de la reprise, historique.", erreurs="Socle (PA-00C).",
        decision="L'activation manuelle et la reprise de l'existant restent humaines ; le flux contrôle les conditions et ne choisit jamais le référent principal (dérivé des affectations par PA-05).",
        tests=["« Actif » avant la date de début → refus.", "Prolongation : « Fin planifiée » → « Actif » sans nouvelle date de fin → refus `G_DATE_FIN_REPORTEE`.",
               "Création manuelle avec `Fonction.RepriseExistantActive` = Non → élément en corbeille, N-90.",
               "Modification manuelle du référent principal → rétablie, N-91.", "Compte renseigné → l'alternant accède à son dossier de suivi mais pas à `_Evaluations`."]),
    "PA-04-act": dict(
        objectif="Protéger les formalités (caractère bloquant, clôture des actions), ouvrir l'action à son responsable et prévenir l'administration lorsque toutes les formalités bloquantes sont terminées, sans changer aucun statut de candidature.",
        entrees="Élément `ActionsIntegration` de contexte « Formalités d'intégration » créé ou modifié.",
        etapes=["`G_ACTION_FORMALITE` (P-09) : `Bloquante` modifiée par une personne hors G_ADM, action bloquante passée à « Non applicable » hors G_ADM, ou action passée à « Terminée » par une personne qui n'est ni membre de G_ADM ni le `Responsable` → valeurs de `EmpreinteAction` (`{\"Bloquante\":true,\"Statut\":\"À faire\"}`, § 6.5) rétablies, Avertissement, N-92, fin ; sinon empreinte mise à jour ; empreinte vide → initialisée sans rien rétablir.",
                "CSS du `Responsable` sur l'action (§ 7.4, idempotent).",
                "Candidature liée « Formalités en cours » : si au moins une action existe et que toutes les actions bloquantes sont « Terminée » avec preuve ou « Non applicable » avec commentaire → N-17 à l'administration, une seule fois (marqueur `JournalFlux` Info « N-17 envoyée »)."],
        sorties="Empreinte et permissions de l'action, N-17.", erreurs="Socle (PA-00C).",
        decision="**Aucun changement de statut automatique** : la confirmation de l'intégration reste une action de l'administration.",
        tests=["Un membre RD passe une action bloquante à « Terminée » sans en être responsable → rétablie, N-92.",
               "Dernière action bloquante terminée avec preuve par l'administration → N-17.", "Action terminée sans preuve → pas de N-17.", "Nouvelle modification après N-17 → pas de second envoi."]),
    "PA-04b": dict(
        objectif="Activer les alternants à leur date de début et rappeler les actions de checklist à échéance.",
        entrees="Alternants « À intégrer » ; actions non terminées ; `Delai.RappelActionJours`.",
        etapes=["Alternants « À intégrer » dont `DateDebut` ≤ aujourd'hui (heure de Paris) → « Actif » (ALT-T02, FLUX, `G_DATE_DEBUT_ATTEINTE`), N-18 au référent principal.",
                "Actions (tous contextes) non terminées dont l'échéance est dans `Delai.RappelActionJours` jours ou dépassée → N-19 au responsable (à défaut, résolution § 8.1 du rôle responsable : ADMIN, RD et DIRECTION_RD → destinataires paramétrés, PROPRIETAIRE → `Destinataires.Support`, ECOLES → G_ECO), au plus une fois par jour (`DernierRappel` = `Rappel:AAAA-MM-JJ`)."],
        sorties="Statuts « Actif », rappels.", erreurs="Socle (PA-00C) ; rattrapage le lendemain.",
        decision="Le passage à « Actif » est un constat de date, pas une décision.",
        tests=["Alternant dont la date de début est aujourd'hui → « Actif » et N-18.", "Action échue → un rappel par jour au plus."]),
}
