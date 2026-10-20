"""Fin d'alternance, écoles, gouvernance, communications, conservation et sujets : PA-09/09b, PA-10/10b, PA-11, PA-12, PA-13, PA-14."""
from __future__ import annotations

from flowlib import (odq, item_changes, MODEL, SITE, SVC, TZ, TODAY, ANTI_LOOP, Flow, P, arr, at, compose, cond, cond_targets, cond_transition,
                     create_with_id, dfr, dloc, ensure_idhncs, filt, flux_transition, foreach, get_item, get_items, grant_item,
                     html_table, ip, item_link, list_link, log, notify, odata, patch_item, q, recurrence_trigger, select,
                     sp_trigger, standard_shell, switch, teams_channel, terminate, truthy)
from gen_common import (restore_flux_columns, I_EL, affectation_controls, alternant_controls, communication_controls, controls_needed_for,
                        convention_controls, emp_action, fin_planifiee_effects, first, generate_actions, lookup_first, role_map,
                        sujet_controls, transition_body)
from defs_production import n22

ALT, AFF, BIL, CONV, INT, ECO, COM, SUJ, CAND = ("Alternants", "Affectations", "BilansAlternance", "Conventions",
                                                 "InteractionsEcoles", "Etablissements", "CommunicationsRD", "SujetsRD", "Candidatures")
ACTEUR = "toLower(coalesce(triggerOutputs()?['body/Editor/Email'], ''))"
CTX_PART = "Évaluation partenariat"


def targets(code, lst):
    return [p for p in MODEL.partition if p["flow"] == code and p["list"] == lst][0]["targets"]


# --------------------------------------------------------------------------------------------
# PA-09 : Fin d'alternance (alternants, bilans) et PA-09b
# --------------------------------------------------------------------------------------------

def pa09_alt():
    f = Flow("PA-09-alt", "PA-09", "HNCS-RD PA-09 : Fin d'alternance (alternants)", 3, "Automatisé", "SharePointItem", ALT,
             targets=targets("PA-09", ALT), objet="Alternant")
    sp_trigger(f, ALT, "GetOnUpdatedItems", [ANTI_LOOP])  # RX-02 : anti-boucle uniquement, filtrage dans le flux
    f.use(ALT, "ReferentPrincipal", "DateFinReelle", "Title", "IdHNCS", "Etablissement", "DateFin")

    def body(s):
        def ref_mail(z, tag, I):
            r = lookup_first(z, f"Referent_{tag}", "Referents", f"{I}?['ReferentPrincipal']?['Id']", fields=("Compte",))
            return f"{r}?['Compte']?['Email']"

        def suspendu(z, env):
            rm = ref_mail(z, "susp", env.I)
            notify(z, "N-36", [rm, f.group_emails("G_RD")], {"IdAlternant": env.IDOBJ, "NomAlternant": f"{env.I}?['Title']", "Lien": env.LIEN})

        def fin_planifiee(z, env):
            fin_planifiee_effects(z, "man", env.I, env.ID, env.IDOBJ)

        def termine(z, env):
            I = env.I
            affs = get_items(z, "Affectations_en_cours", AFF,
                             filter_=f"AlternantId eq @{{{env.ID}}} and (Statut eq 'Active' or Statut eq 'À risque' or Statut eq 'Bloquée')",
                             fields=("Alternant", "Statut", "DateFin", "DateDebut", "Referent", "IdHNCS", "ID", "Sujet", "MotifFin"))
            alt_cm = lookup_first(z, "Compte_alternant", ALT, env.ID, fields=("CompteM365",))
            am = f"{alt_cm}?['CompteM365']?['Email']"

            def each(e, loop):
                a = f"items('{loop}')"
                aid = f"{a}?['ID']"
                patch_item(e, "Date_fin_reelle", AFF, aid, {"DateFin": ip(dloc(I + "?['DateFinReelle']"))}, a)
                ra = get_item(e, "Relire_affectation", AFF, aid)
                RA = f"body('{ra}')"
                aidobj = f"coalesce({RA}?['IdHNCS'], string({aid}))"
                ref = lookup_first(e, "Referent_affectation", "Referents", f"{RA}?['Referent']?['Id']", fields=("Compte", "Statut"))
                flux_transition(e, "AFF_T05", "Affectation", AFF, aid, aidobj, f"{RA}?['Statut']?['Value']", "Terminée", "AFF-T05",
                                affectation_controls(f, RA, aid, controls_needed_for("AFF-T05"), alt_cm, ref), src=RA,
                                after_fn=lambda w: n22(w, f, RA, aid, aidobj, am, f"{ref}?['Compte']?['Email']", "fin"))
            foreach(z, "Pour_affectation", f"body('{affs}')?['value']", each)
            ids = select(z, "Affectations_terminees", f"body('{affs}')?['value']", at("item()?['IdHNCS']"))
            tab, ref = fin_planifiee_effects(z, "term", I, env.ID, env.IDOBJ, send_n35=False)
            notify(z, "N-37", [f.group_emails("G_RD"), f"{ref}?['Compte']?['Email']", P("Destinataires.Administration"),
                               P("Destinataires.Support")], {
                "IdAlternant": env.IDOBJ, "NomAlternant": f"{I}?['Title']",
                "Affectations": f"if(empty(body('{ids}')), 'aucune', join(body('{ids}'), ', '))", "Checklist": tab, "Lien": env.LIEN})

        needed = MODEL.controls_for("Alternant", f.targets)
        transition_body(s, f, ALT, "Alternant", restore=False, effects={"Suspendu": suspendu, "Fin planifiée": fin_planifiee, "Terminé": termine},
                        controls=lambda y, tag: alternant_controls(f, I_EL, f"{I_EL}?['ID']", needed, "outputs('Statut_valide_el')")(y, tag))
    standard_shell(f, body, ALT, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-09-alt"]
    return f


def pa09_bil():
    f = Flow("PA-09-bil", "PA-09", "HNCS-RD PA-09 : Fin d'alternance (bilans)", 3, "Automatisé", "SharePointItem", BIL)
    t = "triggerOutputs()?['body/"
    sp_trigger(f, BIL, "GetOnUpdatedItems", [ANTI_LOOP])
    f.use(BIL, "Statut", "Alternant", "Etablissement", "Referent", "RecommandationPartenariat", "IdHNCS", "ID")

    def body(s):
        I = I_EL
        restore_flux_columns(s, BIL, "triggerOutputs()?['body/ID']", "coalesce(triggerOutputs()?['body/IdHNCS'], '')",
                             "toLower(coalesce(triggerOutputs()?['body/Editor/Email'], ''))")
        get_item(s, "Lire_element", BIL, "triggerOutputs()?['body/ID']")
        ID = f"{I}?['ID']"
        idobj = ensure_idhncs(s, BIL, I, ID, "el")
        ref = lookup_first(s, "Referent_bilan", "Referents", f"{I}?['Referent']?['Id']", fields=("Compte",))
        # Création d'un bilan : référent du bilan CSS sur l'élément (§ 7.4)
        grant_item(s, "bilan", BIL, ID, [("user", f"{ref}?['Compte']?['Email']", "CSS")])

        def realise(y):
            alt = lookup_first(y, "Alternant_bilan", ALT, f"{I}?['Alternant']?['Id']", fields=("Etablissement", "IdHNCS"))
            etab_id = f"coalesce({I}?['Etablissement']?['Id'], {alt}?['Etablissement']?['Id'])"
            eco = lookup_first(y, "Etablissement_bilan", ECO, etab_id, fields=("Statut", "ResponsableHNCS", "IdHNCS", "ID"))
            # Dans tous les cas : action PART-01 « Évaluation partenariat » (tâche distincte), au responsable HNCS de l'école
            generate_actions(y, "part", CTX_PART, {"Etablissement": etab_id, "Alternant": f"{I}?['Alternant']?['Id']"},
                             f"EtablissementId eq @{{{etab_id}}} and AlternantId eq @{{{I}?['Alternant']?['Id']}} and Contexte eq {odata(CTX_PART)}",
                             TODAY, role_map(eco_resp=f"{eco}?['ResponsableHNCS']?['Email']"))
            f.status(ECO, "Partenariat à évaluer")
            cond(y, "Si_partenariat_a_evaluer",
                 (f"and(contains(createArray('Recommandé', 'À étudier'), coalesce({I}?['RecommandationPartenariat']?['Value'], '')), "
                  f"not(contains(createArray('Partenaire actif', 'Partenariat à évaluer'), coalesce({eco}?['Statut']?['Value'], ''))))"),
                 lambda w: patch_item(w, "Etablissement_a_evaluer", ECO, f"{eco}?['ID']", {"Statut": "Partenariat à évaluer"}, eco))
            act = get_items(y, "Action_evaluation", "ActionsIntegration",
                            filter_=f"EtablissementId eq @{{{etab_id}}} and AlternantId eq @{{{I}?['Alternant']?['Id']}} and Contexte eq {odata(CTX_PART)}",
                            fields=("IdHNCS", "ID", "Etablissement", "Alternant", "Contexte"), top=1)
            notify(y, "N-38", [f.group_emails("G_DRD"), f.group_emails("G_ECO")], {
                "IdHNCS": idobj, "Recommandation": f"coalesce({I}?['RecommandationPartenariat']?['Value'], '-')",
                "IdEtablissement": f"coalesce({eco}?['IdHNCS'], '')", "IdAction": f"coalesce({first(act)}?['IdHNCS'], '')",
                "LienAction": item_link("ActionsIntegration", f"coalesce({first(act)}?['ID'], 0)"), "Lien": item_link(BIL, ID)})
        f.read("JournalFlux", "Title", "IdObjet", "Message")
        j = get_items(s, "Marqueur_N38", "JournalFlux", filter_=f"Title eq 'PA-09' and IdObjet eq {odq(idobj)}")
        deja = filt(s, "Bilan_deja_traite", f"body('{j}')?['value']", "equals(item()?['Message'], 'Bilan réalisé traité (N-38 envoyée)')")

        def realise_et_marque(y):
            realise(y)
            log(y, "Marquer_bilan_traite", "Info", q("Bilan réalisé traité (N-38 envoyée)"), BIL, ID, idobj)
        cond(s, "Si_bilan_realise", f"and(equals({I}?['Statut']?['Value'], 'Réalisé'), equals(length(body('{deja}')), 0))", realise_et_marque)
    standard_shell(f, body, BIL, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-09-bil"]
    return f


def pa09b():
    f = Flow("PA-09b", "PA-09b", "HNCS-RD PA-09b : Détection des fins d'alternance", 3, "Planifié", "Recurrence",
             recurrence="Quotidien 06:50 (heure de Paris)")
    recurrence_trigger(f, {"frequency": "Day", "interval": 1, "schedule": {"hours": ["6"], "minutes": [50]}})

    def body(s):
        a = get_items(s, "Alternants_actifs", ALT, filter_="Statut eq 'Actif'",
                      fields=("Statut", "DateFin", "ReferentPrincipal", "Etablissement", "Title", "IdHNCS", "ID", "CandidatureSource"))
        lim = f"addDays({TODAY}, int({P('Fin.AnticipationJours', '30')}), 'yyyy-MM-dd')"
        due = filt(s, "Fin_approchante", f"body('{a}')?['value']", f"and(not(empty(item()?['DateFin'])), lessOrEquals({dloc("item()?['DateFin']")}, {lim}))")

        def each(e, loop):
            it = f"items('{loop}')"
            aid = f"coalesce({it}?['IdHNCS'], string({it}?['ID']))"
            flux_transition(e, "ALT_T04", "Alternant", ALT, f"{it}?['ID']", aid, q("Actif"), "Fin planifiée", "ALT-T04", None, src=it,
                            after_fn=lambda w: fin_planifiee_effects(w, "auto", it, f"{it}?['ID']", aid))
        foreach(s, "Pour_alternant", f"body('{due}')", each)
    standard_shell(f, body)
    f.doc = DOC["PA-09b"]
    return f


# --------------------------------------------------------------------------------------------
# PA-10 : École et convention (conventions, échanges) et PA-10b
# --------------------------------------------------------------------------------------------

def pa10_conv():
    f = Flow("PA-10-conv", "PA-10", "HNCS-RD PA-10 : École et convention (conventions)", 3, "Automatisé", "SharePointItem", CONV,
             targets=targets("PA-10", CONV), objet="Convention")
    sp_trigger(f, CONV, "GetOnUpdatedItems", [ANTI_LOOP])  # P-09 : toute modification humaine (décision de partenariat)
    f.use(CONV, "DecisionPartenariat", "EmpreinteDecision", "DecideurPartenariat", "DateDecisionPartenariat", "TypeConvention",
          "Etablissement", "IdHNCS")

    def decision(z, env, tag):
        I = env.I
        cur = f"coalesce({I}?['DecisionPartenariat']?['Value'], '')"
        emp = f"coalesce({I}?['EmpreinteDecision'], '')"
        habilite = f"contains(split(concat({f.group_emails('G_DRD')}, ';', {f.group_emails('G_DIR')}), ';'), {ACTEUR})"

        def ok(y):
            patch_item(y, f"Tracer_decision_{tag}", CONV, env.ID, {
                "DecideurPartenariat": ip("triggerOutputs()?['body/Editor/Email']"), "DateDecisionPartenariat": ip(TODAY),
                "EmpreinteDecision": ip(cur)}, I)
            notify(y, "N-39", [f.group_emails("G_ECO"), P("Destinataires.Administration"), f.group_emails("G_DRD")], {
                "IdHNCS": env.IDOBJ, "Decision": cur, "Decideur": "coalesce(triggerOutputs()?['body/Editor/DisplayName'], '')",
                "Date": dfr(TODAY), "Lien": env.LIEN})

        def ko(y):
            patch_item(y, f"Retablir_decision_{tag}", CONV, env.ID, {"DecisionPartenariat": at(f"if(empty({emp}), null, {emp})")}, I)
            log(y, f"Decision_retablie_{tag}", "Avertissement", q("P-09 : décision de partenariat modifiée sans habilitation, valeur rétablie"),
                CONV, env.ID, env.IDOBJ)
            notify(y, "N-92", [ACTEUR], {"IdHNCS": env.IDOBJ, "Champs": q("Décision de partenariat"),
                                         "RoleHabilite": q("Direction R&D (DIRECTION_RD) ou Direction (DIRECTION)"), "Lien": env.LIEN},
                   teams_to=[ACTEUR])
        def init(y):
            patch_item(y, f"Initialiser_EmpreinteDecision_{tag}", CONV, env.ID, {"EmpreinteDecision": ip(cur)}, I)

        def check(y):
            cond(y, f"Si_empreinte_decision_a_initialiser_{tag}", f"and(empty({emp}), not(empty({I}?['DecideurPartenariat']?['Email'])))",
                 init, lambda w: cond(w, f"Si_decideur_habilite_{tag}", habilite, ok, ko))
        cond(z, f"Si_decision_modifiee_{tag}", f"not(equals({cur}, {emp}))", check)

    def body(s):
        def signee(z, env):
            I = env.I
            f.status(ECO, "Partenaire actif")
            eco = lookup_first(z, "Etablissement_convention", ECO, f"{I}?['Etablissement']?['Id']", fields=("Statut", "ID"))
            cond(z, "Si_convention_de_partenariat",
                 f"and(contains(createArray('Convention de partenariat', 'Sponsoring'), coalesce({I}?['TypeConvention']?['Value'], '')), "
                 f"not(equals(coalesce({eco}?['Statut']?['Value'], ''), 'Partenaire actif')))",
                 lambda y: patch_item(y, "Etablissement_partenaire_actif", ECO, f"{eco}?['ID']", {"Statut": "Partenaire actif"}, eco))

        needed = MODEL.controls_for("Convention", f.targets)
        transition_body(s, f, CONV, "Convention", effects={"Signée / active": signee},
                        controls=lambda y, tag: convention_controls(f, I_EL, needed, "false")(y, tag),
                        post=lambda s2, env: decision(s2, env, "post" if not env.NOTRANS else "seule"),
                        on_refuse=lambda z, env: decision(z, env, "refus"))
    standard_shell(f, body, CONV, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-10-conv"]
    return f


def pa10_int():
    f = Flow("PA-10-int", "PA-10", "HNCS-RD PA-10 : École et convention (échanges)", 3, "Automatisé", "SharePointItem", INT)
    sp_trigger(f, INT, "GetOnNewItems", [ANTI_LOOP])
    f.use(INT, "Etablissement", "DateInteraction", "ProchaineAction", "DateProchaineAction", "IdHNCS", "ID")
    f.use(ECO, "DateDerniereInteraction", "ProchaineAction", "DateProchaineAction")

    def body(s):
        I = I_EL
        restore_flux_columns(s, INT, "triggerOutputs()?['body/ID']", "coalesce(triggerOutputs()?['body/IdHNCS'], '')",
                             "toLower(coalesce(triggerOutputs()?['body/Editor/Email'], ''))")
        get_item(s, "Lire_element", INT, "triggerOutputs()?['body/ID']")
        ensure_idhncs(s, INT, I, f"{I}?['ID']", "el")
        g = get_item(s, "Lire_etablissement", ECO, f"{I}?['Etablissement']?['Id']")
        E = f"body('{g}')"
        di, de = dloc(I + "?['DateInteraction']"), dloc(E + "?['DateDerniereInteraction']")
        patch_item(s, "Mettre_a_jour_etablissement", ECO, f"{E}?['ID']", {
            "DateDerniereInteraction": ip(f"if(or(empty({E}?['DateDerniereInteraction']), greater({di}, {de})), {di}, {de})"),
            "ProchaineAction": at(f"if(empty({I}?['ProchaineAction']), {E}?['ProchaineAction'], {I}?['ProchaineAction'])"),
            "DateProchaineAction": at(f"if(empty({I}?['DateProchaineAction']), {E}?['DateProchaineAction'], {dloc(I + "?['DateProchaineAction']")})")}, E)
    standard_shell(f, body, INT, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-10-int"]
    return f


def pa10b():
    f = Flow("PA-10b", "PA-10b", "HNCS-RD PA-10b : Échéances des conventions et des écoles", 3, "Planifié", "Recurrence",
             recurrence="Quotidien 07:10 (heure de Paris)")
    recurrence_trigger(f, {"frequency": "Day", "interval": 1, "schedule": {"hours": ["7"], "minutes": [10]}})

    def body(s):
        c = get_items(s, "Conventions_actives", CONV, filter_="Statut eq 'Signée / active' or Statut eq 'À renouveler'",
                      fields=("Statut", "DateFin", "Responsable", "Renouvellement", "IdHNCS", "ID", "DateSignature", "PreuveSignature",
                              "TypeConvention", "DecisionPartenariat", "DecideurPartenariat", "EmpreinteDecision"))
        lim = f"addDays({TODAY}, int({P('Convention.AlerteExpirationJours', '60')}), 'yyyy-MM-dd')"
        df = dloc("item()?['DateFin']")
        exp = filt(s, "Conventions_expirees", f"body('{c}')?['value']", f"and(not(empty(item()?['DateFin'])), less({df}, {TODAY}))")
        ren = filt(s, "Conventions_a_renouveler", f"body('{c}')?['value']",
                   f"and(equals(item()?['Statut']?['Value'], 'Signée / active'), not(empty(item()?['DateFin'])), greaterOrEquals({df}, {TODAY}), lessOrEquals({df}, {lim}))")

        def step(code, to, tag):
            def each(e, loop):
                it = f"items('{loop}')"
                idc = f"coalesce({it}?['IdHNCS'], string({it}?['ID']))"
                flux_transition(e, tag, "Convention", CONV, f"{it}?['ID']", idc, f"{it}?['Statut']?['Value']", to, code,
                                convention_controls(f, it, controls_needed_for(code), "true"), src=it,
                                after_fn=lambda w: notify(w, "N-40", [f"{it}?['Responsable']?['Email']", f.group_emails("G_ECO")], {
                                    "IdHNCS": idc, "Statut": q(to), "DateFin": dfr(it + "?['DateFin']"),
                                    "Renouvellement": f"coalesce({it}?['Renouvellement']?['Value'], '-')", "Lien": item_link(CONV, f"{it}?['ID']")}))
            return each
        foreach(s, "Pour_convention_expiree", f"body('{exp}')", step("CONV-T05", "Expirée", "CONV_T05"))
        foreach(s, "Pour_convention_a_renouveler", f"body('{ren}')", step("CONV-T04", "À renouveler", "CONV_T04"))
        e = get_items(s, "Etablissements_action", ECO, filter_="DateProchaineAction ne null",
                      fields=("DateProchaineAction", "ProchaineAction", "ResponsableHNCS", "IdHNCS", "ID"))
        due = filt(s, "Prochaine_action_atteinte", f"body('{e}')?['value']", f"lessOrEquals({dloc("item()?['DateProchaineAction']")}, {TODAY})")

        def each(x, loop):
            it = f"items('{loop}')"
            rr = f"{it}?['ResponsableHNCS']?['Email']"
            notify(x, "N-41", [rr], {"IdHNCS": f"coalesce({it}?['IdHNCS'], string({it}?['ID']))", "ProchaineAction": f"coalesce({it}?['ProchaineAction'], '-')",
                                     "Date": dfr(it + "?['DateProchaineAction']"), "Lien": item_link(ECO, f"{it}?['ID']")}, teams_to=[rr])
        foreach(s, "Pour_etablissement", f"body('{due}')", each)
    standard_shell(f, body)
    f.doc = DOC["PA-10b"]
    return f


# --------------------------------------------------------------------------------------------
# PA-11 : Préparation de la gouvernance
# --------------------------------------------------------------------------------------------

def pa11():
    f = Flow("PA-11", "PA-11", "HNCS-RD PA-11 : Préparation de la gouvernance", 3, "Planifié", "Recurrence",
             recurrence="Hebdomadaire lundi 08:00 (heure de Paris) ; Point Direction le 1er lundi du mois ; Revue trimestrielle le 1er lundi du trimestre")
    recurrence_trigger(f, {"frequency": "Week", "interval": 1, "schedule": {"weekDays": ["Monday"], "hours": ["8"], "minutes": [0]}})
    LIV, CR = "Livrables", "ComptesRendus"

    def body(s):
        cond(s, "Si_parametre_comite_different", f"not(equals({P('Gouvernance.ComiteJourHeure', 'Lundi 08:00')}, 'Lundi 08:00'))",
             lambda y: log(y, "Parametre_comite_non_applique", "Avertissement",
                           q("Gouvernance.ComiteJourHeure diffère de « Lundi 08:00 » : la récurrence du flux doit être modifiée à la main")))
        sections = []

        def section(title, lst, filter_, where, cols, tag, fields):
            g = get_items(s, f"Lire_{tag}", lst, filter_=filter_, fields=fields)
            src = f"body('{g}')?['value']"
            if where:
                src = f"body('{filt(s, f'Filtrer_{tag}', src, where)}')"
            t = html_table(s, f"Tableau_{tag}", src, cols)
            sections.append((title, f"body('{t}')", f"length({src})"))

        lv_cols = [("Livrable", "item()?['IdHNCS']"), ("Statut", "item()?['Statut']?['Value']"), ("Échéance", dfr("item()?['Echeance']"))]
        esc = f"addDays({TODAY}, mul(-1, int({P('Delai.EscaladeComiteJours', '7')})), 'yyyy-MM-dd')"
        section("Livrables en retard (escaladés)", LIV, "EnRetard eq 1", f"less({dloc("item()?['Echeance']")}, {esc})", lv_cols, "retards",
                ("EnRetard", "Echeance", "Statut", "IdHNCS"))
        section("Échéances des 14 prochains jours", LIV, "Statut eq 'À produire' or Statut eq 'En cours' or Statut eq 'Corrections demandées'",
                f"and(not(empty(item()?['Echeance'])), greaterOrEquals({dloc("item()?['Echeance']")}, {TODAY}), lessOrEquals({dloc("item()?['Echeance']")}, addDays({TODAY}, 14, 'yyyy-MM-dd')))",
                lv_cols, "echeances", ("Echeance", "Statut", "IdHNCS"))
        cr_cols = [("Compte rendu", "item()?['IdHNCS']"), ("Statut", "item()?['Statut']?['Value']"), ("Échéance", dfr("item()?['Echeance']"))]
        section("Comptes rendus non remis", CR, "Statut eq 'Non remis'", None, cr_cols, "cr_non_remis", ("Statut", "Echeance", "IdHNCS"))
        section("Blocages signalés", CR, "BlocageSignale eq 1 and Statut ne 'Validé'", None, cr_cols, "blocages", ("BlocageSignale", "Statut", "Echeance", "IdHNCS"))
        st_cols = [("Identifiant", "item()?['IdHNCS']"), ("Statut", "item()?['Statut']?['Value']")]
        section("Affectations à risque ou bloquées", AFF, "Statut eq 'À risque' or Statut eq 'Bloquée'", None, st_cols, "affectations", ("Statut", "IdHNCS"))
        section("Sujets bloqués ou à arbitrer", SUJ, "Statut eq 'Bloqué' or Statut eq 'À arbitrer'", None, st_cols, "sujets", ("Statut", "IdHNCS"))
        section("Conventions à renouveler", CONV, "Statut eq 'À renouveler'", None, st_cols, "conventions", ("Statut", "IdHNCS"))
        section("Établissements : partenariat à évaluer", ECO, "Statut eq 'Partenariat à évaluer'", None, st_cols, "etablissements", ("Statut", "IdHNCS"))
        section("Communications en revue", COM, "Statut eq 'En revue'", None, st_cols, "communications", ("Statut", "IdHNCS"))
        # Candidatures en attente : en nombre par statut (aucun nom)
        attente = [x for x in MODEL.enums["STATUT_CANDIDATURE"] if x not in ("Intégrée", "Non retenue", "Clôturée")]
        c = get_items(s, "Candidatures_en_attente", CAND, filter_="Statut ne 'Intégrée' and Statut ne 'Non retenue' and Statut ne 'Clôturée'",
                      fields=("Statut",))
        rows = []
        for i, st in enumerate(attente, 1):
            fl = filt(s, f"Candidatures_statut_{i}", f"body('{c}')?['value']", f"equals(item()?['Statut']?['Value'], {q(st)})")
            rows.append(f"'<tr><td>{st.replace(chr(39), chr(39) * 2)}</td><td>', string(length(body('{fl}'))), '</td></tr>'")
        cand = compose(s, "Tableau_candidatures", at("concat('<table><tr><th>Statut</th><th>Nombre</th></tr>', " + ", ".join(rows) + ", '</table>')"))
        detail = "concat(" + ", ".join(f"'<h3>{t}</h3>', {tab}" for t, tab, _ in sections) + ", '<h3>Candidatures en attente (nombre par statut)</h3>', outputs('" + cand + "'))"
        synth = compose(s, "Synthese_comite", at(detail))
        agreg = "concat('<table><tr><th>Indicateur</th><th>Nombre</th></tr>', " + ", ".join(
            f"'<tr><td>{t}</td><td>', string({n}), '</td></tr>'" for t, _, n in sections) + ", '</table><h3>Points d''arbitrage : sujets bloqués ou à arbitrer</h3>', body('Tableau_sujets'), '<h3>Candidatures en attente</h3>', outputs('" + cand + "'))"
        synth_dir = compose(s, "Synthese_direction", at(agreg))
        date = dfr(TODAY)
        notify(s, "N-42", [f.group_emails("G_DRD")], {"Date": date, "Synthese": f"outputs('{synth}')", "LienRapport": P("Lien.RapportPowerBI")})
        canal = P("Lien.CanalComite")

        def post_teams(y):
            gid = f"first(split(last(split({canal}, 'groupId=')), '&'))"
            cid = f"decodeUriComponent(first(split(last(split({canal}, '/l/channel/')), '/')))"
            teams_channel(y, "Publier_canal_comite", gid, cid,
                          f"<p><strong>[HNCS-R&amp;D][N-42] Synthèse Comité R&amp;D du @{{{date}}}</strong></p>@{{outputs('{synth}')}}"
                          f"<p><a href=\"@{{{P('Lien.RapportPowerBI')}}}\">Rapport Power BI</a></p>")
        tc = cond(s, "Si_canal_comite", f"and(contains({canal}, 'groupId='), contains({canal}, '/l/channel/'))", post_teams)
        log(s, "Canal_comite_echec", "Avertissement", q("N-42 : publication dans le canal Teams du comité impossible"), after={tc: ["Failed", "TimedOut"]})
        jour = f"int(formatDateTime(convertTimeZone(utcNow(), 'UTC', '{TZ}'), 'dd'))"
        mois = f"int(formatDateTime(convertTimeZone(utcNow(), 'UTC', '{TZ}'), 'MM'))"
        trimestre = f"contains(createArray(1, 4, 7, 10), {mois})"
        cond(s, "Si_premier_lundi_du_mois", f"and(lessOrEquals({jour}, 7), not({trimestre}))",
             lambda y: notify(y, "N-43", [f.group_emails("G_DRD")], {"TypeSynthese": q("Point Direction"), "Date": date,
                                                                    "Synthese": f"outputs('{synth_dir}')", "LienRapport": P("Lien.RapportPowerBI")}),
             after={"Canal_comite_echec": ["Succeeded", "Skipped"]})
        cond(s, "Si_premier_lundi_du_trimestre", f"and(lessOrEquals({jour}, 7), {trimestre})",
             lambda y: notify(y, "N-43", [f.group_emails("G_DRD")], {"TypeSynthese": q("Revue trimestrielle"), "Date": date,
                                                                    "Synthese": f"outputs('{synth_dir}')", "LienRapport": P("Lien.RapportPowerBI")}))
        f.use(LIV, "IdHNCS", "Statut", "Echeance")
        f.use(CR, "IdHNCS", "Statut", "Echeance")
    standard_shell(f, body)
    f.doc = DOC["PA-11"]
    return f


# --------------------------------------------------------------------------------------------
# PA-12 : Validation des communications
# --------------------------------------------------------------------------------------------

def pa12():
    f = Flow("PA-12", "PA-12", "HNCS-RD PA-12 : Validation des communications", 3, "Automatisé", "SharePointItem", COM,
             targets=targets("PA-12", COM), objet="Communication")
    t = "triggerOutputs()?['body/"
    # statut cible ∈ partition, ou toute autre modification (changement d'Auteur détecté dans le flux, § 7.4)
    sp_trigger(f, COM, "GetOnUpdatedItems", [ANTI_LOOP])  # RX-02 : toute modification humaine (statut ou auteur)
    f.use(COM, "Auteur", "ValidationInterne", "DateValidation", "Canal", "DatePrevue", "AutorisationsTiers", "IdHNCS")

    def body(s):
        def pre(z, env):
            au = f"toLower(coalesce({env.I}?['Auteur']?['Email'], ''))"
            ch = item_changes(z, "Changements", COM, env.ID)
            changed = (f"or(not(equals(string(coalesce(body('{ch}')?['SinceVersionExisted'], true)), 'True')), "
                       f"equals(string(coalesce(body('{ch}')?['ColumnHasChanged']?['Auteur'], false)), 'True'))")
            cond(z, "Si_auteur_alternant", f"and({changed}, not(empty({au})), contains(split({f.group_emails('G_ALT')}, ';'), {au}))",
                 lambda y: grant_item(y, "auteur", COM, env.ID, [("user", au, "CSS")]))

        def n45(z, env, tag):
            au = f"{env.I}?['Auteur']?['Email']"
            notify(z, "N-45", [au], {"IdHNCS": env.IDOBJ, "Statut": env.APRES, "Lien": env.LIEN}, teams_to=[au])

        def en_revue(z, env):
            I = env.I
            ap = f"toLower(coalesce({I}?['ValidationInterne']?['Email'], ''))"
            dest = f"if(and(not(empty({ap})), contains(split(concat({f.group_emails('G_DRD')}, ';', {f.group_emails('G_DIR')}), ';'), {ap})), {ap}, {f.group_emails('G_DRD')})"
            notify(z, "N-44", [dest], {"IdHNCS": env.IDOBJ, "Canal": f"coalesce({I}?['Canal']?['Value'], '')",
                                       "DatePrevue": dfr(I + "?['DatePrevue']"), "Autorisations": f"coalesce({I}?['AutorisationsTiers']?['Value'], '-')",
                                       "Lien": env.LIEN}, teams_to=[ap])

        def validee(z, env):
            I = env.I
            patch_item(z, "Validation", COM, env.ID, {"DateValidation": ip("utcNow()"),
                                                     "ValidationInterne": ip(f"coalesce({I}?['ValidationInterne']?['Email'], triggerOutputs()?['body/Editor/Email'])")}, I)
            n45(z, env, "val")

        def suspendue(z, env):
            n45(z, env, "susp")

        def redaction(z, env):  # renvoi en rédaction depuis la revue (COM-T03)
            cond(z, "Si_renvoi_en_redaction", f"equals({env.AVANT}, 'En revue')", lambda y: n45(y, env, "renvoi"))

        needed = MODEL.controls_for("Communication", f.targets)
        transition_body(s, f, COM, "Communication", pre=pre,
                        effects={"En revue": en_revue, "Validée": validee, "Suspendue / refusée": suspendue, "En rédaction": redaction},
                        auteur=lambda env: f"{env.I}?['Auteur']?['Email']", valideur=lambda env: f"{env.I}?['ValidationInterne']?['Email']",
                        controls=lambda y, tag: communication_controls(f, I_EL, needed)(y, tag))
    standard_shell(f, body, COM, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-12"]
    return f


# --------------------------------------------------------------------------------------------
# PA-13 : Conservation des candidatures (désactivé par défaut)
# --------------------------------------------------------------------------------------------

def pa13():
    f = Flow("PA-13", "PA-13", "HNCS-RD PA-13 : Conservation des candidatures", 5, "Planifié", "Recurrence",
             recurrence="Mensuel (le 1er à 06:00, heure de Paris) : désactivé par défaut", enabled=False)
    recurrence_trigger(f, {"frequency": "Month", "interval": 1, "startTime": "2026-11-01T06:00:00"})

    def body(s):
        duree = P("Conservation.CandidatureNonRetenueMois")
        cond(s, "Si_duree_non_validee", f"empty({duree})", lambda y: terminate(y, "Fin_conservation_inactive"))
        cond(s, "Si_mode_non_implemente", f"not(equals({P('Conservation.ModePurge', 'Signalement')}, 'Signalement'))",
             lambda y: log(y, "Mode_purge_ignore", "Avertissement", q("Conservation.ModePurge ≠ Signalement : seul le signalement est implémenté")))
        c = get_items(s, "Candidatures_closes", CAND, filter_="(Statut eq 'Non retenue' or Statut eq 'Clôturée') and DateCloture ne null",
                      fields=("Statut", "DateCloture", "DateFinConservation", "IdHNCS", "ID"))

        def each(e, loop):
            it = f"items('{loop}')"
            fin = f"formatDateTime(addToTime({it}?['DateCloture'], int({duree}), 'Month'), 'yyyy-MM-dd')"
            cond(e, "Si_date_a_jour", f"not(equals({dloc(it + "?['DateFinConservation']")}, {fin}))",
                 lambda y: patch_item(y, "DateFinConservation", CAND, f"{it}?['ID']", {"DateFinConservation": ip(fin)}, it))
        foreach(s, "Pour_candidature", f"body('{c}')?['value']", each)
        depasse = filt(s, "Conservation_depassee", f"body('{c}')?['value']",
                       f"less(formatDateTime(addToTime(item()?['DateCloture'], int({duree}), 'Month'), 'yyyy-MM-dd'), {TODAY})")
        ids = select(s, "Identifiants", f"body('{depasse}')", at("coalesce(item()?['IdHNCS'], string(item()?['ID']))"))
        cond(s, "Si_candidatures_a_traiter", f"greater(length(body('{ids}')), 0)",
             lambda y: notify(y, "N-46", [f.group_emails("G_DRD"), f.group_emails("G_PROP")], {
                 "Nombre": f"string(length(body('{ids}')))", "Liste": f"join(body('{ids}'), ', ')", "Lien": list_link(CAND)}))
    standard_shell(f, body)
    f.doc = DOC["PA-13"]
    return f


# --------------------------------------------------------------------------------------------
# PA-14 : Arbitrage du portefeuille de sujets
# --------------------------------------------------------------------------------------------

def pa14():
    f = Flow("PA-14", "PA-14", "HNCS-RD PA-14 : Arbitrage du portefeuille de sujets", 3, "Automatisé", "SharePointItem", SUJ,
             targets=targets("PA-14", SUJ), objet="Sujet")
    sp_trigger(f, SUJ, "GetOnUpdatedItems", [ANTI_LOOP])  # RX-02 : anti-boucle uniquement, filtrage dans le flux
    f.use(SUJ, "Referent", "MotifDecision", "IdHNCS")

    def body(s):
        def n47(z, env, to, objet):
            notify(z, "N-47", to, {"IdHNCS": env.IDOBJ, "Statut": env.APRES, "Objet": q(objet),
                                   "Motif": f"coalesce({env.I}?['MotifDecision'], '-')", "Lien": env.LIEN})

        def drd(objet):
            return lambda z, env: n47(z, env, [f.group_emails("G_DRD")], objet)

        def decision(z, env):
            ref = lookup_first(z, "Referent_sujet", "Referents", f"{env.I}?['Referent']?['Id']", fields=("Compte",))
            n47(z, env, [f"{ref}?['Compte']?['Email']", f.group_emails("G_RD")], "Décision d'arbitrage du portefeuille (DIRECTION_RD / DIRECTION).")

        needed = MODEL.controls_for("Sujet", f.targets)
        transition_body(s, f, SUJ, "Sujet",
                        effects={"À arbitrer": drd("Demande d'arbitrage (GO / NO-GO) au prochain Comité R&D."),
                                 "Priorisé": decision, "Suspendu": decision, "Abandonné": decision,
                                 "Bloqué": drd("Blocage signalé : arbitrage ou soutien de la Direction R&D attendu.")},
                        controls=lambda y, tag: sujet_controls(f, I_EL, needed)(y, tag))
    standard_shell(f, body, SUJ, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-14"]
    return f


BUILDERS = [pa09_alt, pa09_bil, pa09b, pa10_conv, pa10_int, pa10b, pa11, pa12, pa13, pa14]

DOC = {
    "PA-09-alt": dict(
        objectif="Préparer et tracer la fin d'une alternance : checklist de clôture, bilan, fin des affectations, sans jamais retirer d'accès automatiquement.",
        entrees="Élément `Alternants` modifié vers « Suspendu », « Fin planifiée », « Terminé » ou « Clôturé ».",
        etapes=["PA-00A puis contrôles (`G_CLOTURE_ALTERNANCE` pour « Clôturé ») ; refus → annulation, N-90.",
                "**Suspendu** : N-36 au référent principal et à G_RD.",
                "**Fin planifiée** (manuel) : mêmes effets que PA-09b : checklist « Clôture d'alternance » (idempotente, échéance = date de fin, responsables résolus § 8.1, CSS des responsables), bilan « À réaliser » s'il n'existe pas (référent CSS), N-35.",
                "**Terminé** : affectations encore actives → `DateFin` = `DateFinReelle` puis « Terminée » (AFF-T05, FLUX, `G_DATE_FIN`) et N-22 pour chacune (règle § 6.1-8) ; checklist et bilan garantis ; N-37 (affectations terminées, checklist dont le retrait des accès, action humaine).",
                "**Clôturé** : contrôle uniquement.", "PA-00B."],
        sorties="Checklist, bilan, affectations terminées, notifications, historique.", erreurs="Socle (PA-00C) ; générations idempotentes.",
        decision="La fin effective, le bilan et la recommandation sont humains ; la décision de partenariat est prise ensuite dans `Conventions` par DIRECTION_RD / DIRECTION ; le retrait des accès reste une action de checklist (H-18).",
        tests=["« Terminé » avec deux affectations actives → deux AFF-T05, deux N-22, N-37.", "« Clôturé » avec une action bloquante ouverte → refus.", "« Fin planifiée » manuelle → checklist sans doublon."]),
    "PA-09-bil": dict(
        objectif="Ouvrir le bilan à son référent et, lorsqu'il est réalisé, déclencher l'évaluation d'un partenariat (signal, jamais décision).",
        entrees="Élément `BilansAlternance` créé ou passé à « Réalisé ».",
        etapes=["`IdHNCS` ; à la création : référent du bilan CSS sur l'élément (§ 7.4).",
                "**Réalisé** : dans tous les cas, action PART-01 « Évaluation partenariat » (idempotente par établissement + alternant) assignée au responsable HNCS de l'école ; si `RecommandationPartenariat` ∈ {Recommandé, À étudier} et que l'établissement n'est ni « Partenaire actif » ni déjà « Partenariat à évaluer » → « Partenariat à évaluer » (jamais de rétrogradation) ; N-38 à G_DRD et G_ECO.",
                "Idempotence : marqueur `JournalFlux` Info « Bilan réalisé traité (N-38 envoyée) » ; référent du bilan CSS posé à chaque modification (idempotent)."],
        sorties="Permissions, action d'évaluation, statut d'établissement, N-38.", erreurs="Socle (PA-00C).",
        decision="La recommandation est un signal ; la décision de partenariat reste à DIRECTION_RD / DIRECTION (PA-10).",
        tests=["Bilan réalisé « Non recommandé » → action PART-01 créée, établissement inchangé.", "Établissement « Partenaire actif » → non rétrogradé."]),
    "PA-09b": dict(
        objectif="Détecter les fins d'alternance proches et préparer la clôture.",
        entrees="Alternants « Actif » ; `Fin.AnticipationJours`.",
        etapes=["`DateFin` ≤ aujourd'hui + `Fin.AnticipationJours` → « Fin planifiée » (ALT-T04, FLUX).",
                "Effets du statut cible (§ 6.1-8) : checklist « Clôture d'alternance » (idempotente), bilan « À réaliser » s'il n'existe pas (référent CSS), N-35 au référent, à G_RD et au responsable HNCS de l'école."],
        sorties="Statuts, checklists, bilans, N-35.", erreurs="Socle (PA-00C) ; rattrapage le lendemain.",
        decision="« Fin planifiée » est un constat de date ; « Terminé » reste humain.",
        tests=["Alternant à J-30 → « Fin planifiée », checklist et bilan créés une seule fois."]),
    "PA-10-conv": dict(
        objectif="Contrôler le cycle de vie des conventions (preuve de signature, décision de partenariat préalable) et protéger la décision de partenariat (P-09).",
        entrees="Élément `Conventions` créé ou modifié par une personne (toute modification).",
        etapes=["`IdHNCS`.", "Transition : PA-00A puis `G_PREUVE_SIGNATURE`, `G_DECISION_PARTENARIAT` (décision « Partenariat retenu » / « Sponsoring retenu » déjà validée : égale à `EmpreinteDecision` : et `DecideurPartenariat` renseigné, pour une convention de partenariat ou de sponsoring) ; refus → annulation, N-90.",
                "**Signée / active** d'une convention de partenariat ou de sponsoring → établissement « Partenaire actif » (constat de signature).",
                "Décision de partenariat : `DecisionPartenariat` ≠ `EmpreinteDecision` (valeur texte, § 6.5) → empreinte vide et décideur déjà tracé (données importées) : initialisation sans rien rétablir ; sinon acteur membre de G_DRD ou G_DIR : `DecideurPartenariat`, `DateDecisionPartenariat`, empreinte mise à jour, N-39 ; sinon valeur rétablie, Avertissement, N-92 (P-09). Traitée aussi sans transition et après un refus de transition.",
                "PA-00B."],
        sorties="Statuts, décision tracée, statut d'établissement, notifications.", erreurs="Socle (PA-00C).",
        decision="Aucun établissement n'est converti automatiquement en partenaire : seule une convention signée avec preuve après décision tracée de DIRECTION_RD / DIRECTION le permet.",
        tests=["Signature sans preuve → refus.", "Convention de sponsoring signée sans décision → refus `G_DECISION_PARTENARIAT`.",
               "Décision saisie par un membre ADMIN → rétablie, N-92.", "Décision par la Direction R&D → tracée, N-39."]),
    "PA-10-int": dict(
        objectif="Reporter chaque échange avec une école sur la fiche de l'établissement.",
        entrees="Élément `InteractionsEcoles` créé.",
        etapes=["`IdHNCS`.", "Établissement : `DateDerniereInteraction` = date de l'échange si plus récente ; `ProchaineAction` / `DateProchaineAction` reportées si renseignées."],
        sorties="Fiche établissement à jour.", erreurs="Socle (PA-00C).", decision="Sans objet.",
        tests=["Échange plus ancien que la dernière interaction → date inchangée."]),
    "PA-10b": dict(
        objectif="Suivre les échéances des conventions et les prochaines actions des écoles.",
        entrees="Conventions « Signée / active » / « À renouveler » ; établissements avec prochaine action ; `Convention.AlerteExpirationJours`.",
        etapes=["`DateFin` dépassée → « Expirée » (CONV-T05, FLUX, `G_DATE_FIN_DEPASSEE`) + N-40.",
                "`DateFin` dans `Convention.AlerteExpirationJours` → « À renouveler » (CONV-T04, FLUX) + N-40.",
                "Établissements dont `DateProchaineAction` est atteinte → N-41 au responsable HNCS (chaque jour tant que l'échéance n'est pas mise à jour)."],
        sorties="Statuts de conventions, rappels.", erreurs="Socle (PA-00C).", decision="Constats de date uniquement.",
        tests=["Convention échue hier → « Expirée » et N-40.", "Convention à J-30 → « À renouveler »."]),
    "PA-11": dict(
        objectif="Préparer les synthèses de gouvernance (Comité R&D hebdomadaire, Point Direction mensuel, Revue trimestrielle).",
        entrees="Livrables, comptes rendus, affectations, sujets, conventions, établissements, communications, candidatures (en nombre).",
        etapes=["Synthèse HTML : livrables en retard escaladés (au-delà de `Delai.EscaladeComiteJours`), échéances à 14 jours, comptes rendus « Non remis », blocages signalés, affectations « À risque » / « Bloquée », sujets « Bloqué » / « À arbitrer », conventions « À renouveler », établissements « Partenariat à évaluer », communications « En revue », candidatures en attente **en nombre par statut** ; lien `Lien.RapportPowerBI`. Uniquement des identifiants et des statuts.",
                "Comité : N-42 à G_DRD et publication dans le canal Teams `Lien.CanalComite` (groupe et canal lus dans le lien).",
                "1er lundi du mois : N-43 « Point Direction » à G_DRD (version agrégée, à relire et transmettre) ; le 1er lundi d'un trimestre, la N-43 « Revue trimestrielle » **remplace** l'envoi mensuel (une seule N-43).",
                "`Gouvernance.ComiteJourHeure` ≠ « Lundi 08:00 » → Avertissement (la récurrence est statique, voir divergences)."],
        sorties="N-42, N-43.", erreurs="Socle (PA-00C) ; échec Teams journalisé sans bloquer les courriels.",
        decision="Aucune : synthèse d'information ; la Direction R&D relit et transmet à la Direction Générale.",
        tests=["Lundi ordinaire → N-42 seule.", "Premier lundi de mai → N-42 et N-43 « Point Direction ».",
               "Premier lundi d'avril → N-42 et une seule N-43 « Revue trimestrielle ».", "Aucun nom de personne dans N-43."]),
    "PA-12": dict(
        objectif="Contrôler la validation des communications (réservée à DIRECTION_RD / DIRECTION) et notifier auteur et approbateur.",
        entrees="Élément `CommunicationsRD` créé ou modifié : statut cible de la partition PA-12, ou changement d'`Auteur`.",
        etapes=["`IdHNCS` ; à la création ou au changement d'`Auteur` (« Obtenir les modifications ») : auteur membre de G_ALT → CSS sur l'élément (§ 7.4) ; une modification sans changement de statut s'arrête là.",
                "PA-00A (`ItemAuteurEmail` = `Auteur`, `ItemValideurEmail` = `ValidationInterne`) puis `G_AUTORISATIONS`, `G_PUBLICATION`.",
                "**En revue** : N-44 à l'approbateur proposé s'il est membre de G_DRD ou G_DIR, sinon à G_DRD.",
                "**Validée** : `DateValidation`, `ValidationInterne` = `Editor` si vide, N-45. **Suspendue / refusée** : N-45. **En rédaction** depuis « En revue » (renvoi, COM-T03) : N-45.", "PA-00B."],
        sorties="Dates, permissions, notifications, historique.", erreurs="Socle (PA-00C).",
        decision="La validation d'une communication externe est réservée à DIRECTION_RD / DIRECTION (H-11) ; l'approbateur proposé peut seulement renvoyer en rédaction.",
        tests=["Validation par un référent → refus.", "Validation sans autorisation des tiers → refus `G_AUTORISATIONS`.", "Renvoi en rédaction → N-45."]),
    "PA-13": dict(
        objectif="Signaler les candidatures arrivées en fin de conservation, sans aucune suppression automatique.",
        entrees="Candidatures « Non retenue » / « Clôturée » ; `Conservation.CandidatureNonRetenueMois`, `Conservation.ModePurge`.",
        etapes=["Durée non renseignée → fin (flux inactif, H-10).", "`DateFinConservation` = `DateCloture` + durée (mois).",
                "Candidatures dont la date est dépassée → N-46 (identifiants seulement) à G_DRD et G_PROP.", "`Conservation.ModePurge` ≠ Signalement → Avertissement : seul le signalement est implémenté."],
        sorties="`DateFinConservation`, N-46.", erreurs="Socle (PA-00C).",
        decision="Toute suppression reste manuelle, après validation DPO.", tests=["Durée vide → aucune action.", "Durée 24 mois → dates calculées, N-46 listant les dépassements."]),
    "PA-14": dict(
        objectif="Historiser et notifier l'arbitrage du portefeuille de sujets R&D.",
        entrees="Élément `SujetsRD` créé ou modifié vers un statut de la partition PA-14.",
        etapes=["`IdHNCS` ; PA-00A puis `G_MOTIF_DECISION` (« Suspendu », « Abandonné ») ; refus → annulation, N-90 (création refusée → corbeille).",
                "**À arbitrer** : N-47 à G_DRD. **Priorisé**, **Suspendu**, **Abandonné** : N-47 au référent du sujet et à G_RD (motif inclus). **Bloqué** : N-47 à G_DRD.", "PA-00B."],
        sorties="Historique, notifications.", erreurs="PA-00C.",
        decision="L'arbitrage (Priorisé, Suspendu, Abandonné) est réservé à DIRECTION_RD / DIRECTION et toujours motivé pour un NO-GO ; le flux ne fait qu'historiser et notifier.",
        tests=["« Priorisé » par un membre RD → refus.", "« Abandonné » sans motif → refus `G_MOTIF_DECISION`.", "« À arbitrer » → N-47 à G_DRD."]),
}
