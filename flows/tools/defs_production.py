"""Flux de production R&D : PA-05 (affectations), PA-06, PA-07/07b (livrables), PA-08/08b (comptes rendus)."""
from __future__ import annotations

from flowlib import (MODEL, SITE, SVC, TZ, TODAY, ANTI_LOOP, Flow, P, arr, at, compose, cond, cond_targets,
                     cond_transition, create_with_id, dfr, dloc, ensure_folder, ensure_idhncs, filt, flux_transition,
                     foreach, get_item, get_items, grant_folder, grant_item, ip, item_link, list_exists, lib_url, list_link,
                     log, notify, odq, patch_item, post_item, q, recurrence_trigger, select, sp_trigger, standard_shell,
                     switch, terminate, truthy)
from gen_common import (restore_flux_columns, jdate, jnum, CR_FP, DOD, I_EL, LIV_FP, Env, affectation_controls, cadence_effective, capitalisation_parts,
                        changed_keys, controls_needed_for, cr_controls, create_cr, emp_action, first, flux_creation,
                        fp_compute, fp_refresh, fp_restore_values, livrable_controls, lookup_first, period_current,
                        period_end, period_first, transition_body, valideur_legitime)

AFF, LIV, CR, ACT = "Affectations", "Livrables", "ComptesRendus", "ActionsIntegration"
OUVERTS = ["À produire", "En cours", "Soumis à revue", "En revue", "Corrections demandées"]
ACTEUR = "toLower(coalesce(triggerOutputs()?['body/Editor/Email'], ''))"


def targets(code, lst):
    return [p for p in MODEL.partition if p["flow"] == code and p["list"] == lst][0]["targets"]


def col_types(lst):
    return {c: d["type"] for c, d in MODEL.columns(lst).items()}


def empreinte_verrou(alt, suj, ref, deb):
    """EmpreinteVerrou (P-03, § 6.5) : {"AlternantId":12,"SujetId":3,"ReferentId":5,"DateDebut":"2026-11-02"} ; absent = null."""
    return (f"concat('{{\"AlternantId\":', {jnum(alt)}, ',\"SujetId\":', {jnum(suj)}, "
            f"',\"ReferentId\":', {jnum(ref)}, ',\"DateDebut\":', {jdate(deb)}, '}}')")


def verrou_differs(emp, I):
    """Comparaison clé par clé (sémantique) entre l'empreinte validée et les valeurs courantes."""
    pairs = [("AlternantId", f"{I}?['Alternant']?['Id']"), ("SujetId", f"{I}?['Sujet']?['Id']"), ("ReferentId", f"{I}?['Referent']?['Id']")]
    tests = [f"not(equals(string(coalesce(json({emp})?['{k}'], '')), string(coalesce({v}, ''))))" for k, v in pairs]
    tests.append(f"not(equals(string(coalesce(json({emp})?['DateDebut'], '')), {dloc(I + "?['DateDebut']")}))")
    return "or(" + ", ".join(tests) + ")"


def ev_item(I):
    return empreinte_verrou(f"{I}?['Alternant']?['Id']", f"{I}?['Sujet']?['Id']", f"{I}?['Referent']?['Id']", f"{I}?['DateDebut']")


def ev_trigger():
    t = "triggerOutputs()?['body/"
    return empreinte_verrou(f"{t}Alternant/Id']", f"{t}Sujet/Id']", f"{t}Referent/Id']", f"{t}DateDebut']")


# --------------------------------------------------------------------------------------------
# Livrable proposé (PA-05) : effets de création de PA-07 exécutés par le flux auteur (§ 6.1-8)
# --------------------------------------------------------------------------------------------

def creer_livrable(s, f, tag, aff_id, aff_idobj, suj, modele, owner, reviseur, echeance):
    vals = {"Title": ip(f"concat({modele}?['Title'], ' : ', coalesce({suj}?['IdHNCS'], ''))"),
            "Affectation": at(aff_id), "Sujet": at(f"{suj}?['ID']"),
            "TypeLivrable": ip(f"coalesce({modele}?['TypeLivrableCible']?['Value'], 'Autre')"),
            "Modele": at(f"{modele}?['ID']"), "VersionModele": ip(f"{modele}?['Version']"),
            "Proprietaire": ip(owner), "Reviseur": at(f"if(empty({reviseur}), null, {reviseur})"),
            "Echeance": ip(echeance), "EcheanceInitiale": ip(echeance), "Statut": "À produire"}
    f.use("RegistreModeles", "Title", "TypeLivrableCible", "ID", "Version")
    p, idc = create_with_id(s, f"Creer_livrable_{tag}", LIV, vals)
    pid = f"body('{p}')?['ID']"
    grant_item(s, f"livrable_{tag}", LIV, pid, [("user", owner, "CSS")])
    fp_refresh(s, f"liv_{tag}", LIV, pid, LIV_FP)
    flux_creation(s, f"LIV_T01_{tag}", "Livrable", LIV, pid, idc, "À produire", "LIV-T01")


def n22(s, f, I, ID, idobj, alt_mail, ref_mail, tag):
    """N-22 : affectation terminée, avec la liste des livrables encore ouverts (décision de la R&D, H-51)."""
    lv = get_items(s, f"Livrables_ouverts_{tag}", LIV,
                   filter_=f"AffectationId eq @{{{ID}}} and (" + " or ".join(f"Statut eq '{x}'" for x in OUVERTS) + ")",
                   fields=("Affectation", "Statut", "IdHNCS"))
    sel = select(s, f"Ids_livrables_ouverts_{tag}", f"body('{lv}')?['value']", at("concat(item()?['IdHNCS'], ' (', item()?['Statut']?['Value'], ')')"))
    f.use(AFF, "DateFin", "MotifFin")
    notify(s, "N-22", [alt_mail, ref_mail, f.group_emails("G_RD")], {
        "IdHNCS": idobj, "DateFin": dfr(I + "?['DateFin']"), "MotifFin": f"coalesce({I}?['MotifFin'], '-')",
        "LivrablesOuverts": f"if(empty(body('{sel}')), 'aucun', join(body('{sel}'), ', '))", "Lien": item_link(AFF, ID)})


# --------------------------------------------------------------------------------------------
# PA-05 : Affectation
# --------------------------------------------------------------------------------------------

def pa05():
    f = Flow("PA-05", "PA-05", "HNCS-RD PA-05 : Affectation", 2, "Automatisé", "SharePointItem", AFF,
             targets=targets("PA-05", AFF), objet="Affectation")
    t = "triggerOutputs()?['body/"
    sp_trigger(f, AFF, "GetOnUpdatedItems", [ANTI_LOOP])  # RX-02 : toute modification humaine
    f.use(AFF, "Alternant", "Sujet", "Referent", "DateDebut", "DateFin", "EmpreinteVerrou", "Title", "AffectationRemplacee",
          "MotifFin", "CadenceCR", "Objectifs", "ProchaineEcheanceCR", "IdHNCS")
    f.use("Alternants", "CompteM365", "IdHNCS", "ID", "ReferentPrincipal", "EmpreinteReferent", "Title")
    f.use("Referents", "Compte", "IdHNCS")

    def body(s):
        def pre(z, env):
            I = env.I
            cond(z, "Si_titre_vide", f"empty({I}?['Title'])",
                 lambda y: patch_item(y, "Renseigner_titre", AFF, env.ID, {
                     "Title": ip(f"concat(coalesce({I}?['Alternant']?['Value'], ''), ' / ', coalesce({I}?['Sujet']?['Value'], ''))")}, I))
            emp = f"coalesce({I}?['EmpreinteVerrou'], '')"

            def restore(y):
                patch_item(y, "Retablir_champs_verrouilles", AFF, env.ID, {
                    "Alternant": at(f"json({emp})?['AlternantId']"), "Sujet": at(f"json({emp})?['SujetId']"),
                    "Referent": at(f"json({emp})?['ReferentId']"),
                    "DateDebut": at(f"json({emp})?['DateDebut']")}, I)
                log(y, "Verrou_retabli", "Avertissement", q("P-03 : modification d'un champ verrouillé d'une affectation active annulée"),
                    AFF, env.ID, env.IDOBJ)
                notify(y, "N-91", [ACTEUR], {"IdHNCS": env.IDOBJ, "Champs": q("Alternant, Sujet, Référent, Date de début"), "Lien": env.LIEN},
                       teams_to=[ACTEUR])
                # v1.5.0 : pas d'arrêt : un changement de statut fait dans la même modification est traité ensuite
                # sur les valeurs rétablies (sinon la garde de transition termine l'exécution)
            viole = compose(z, "Verrou_viole", at(f"and(not(empty({emp})), {verrou_differs(emp, I)})"))
            vv = f"equals(string(outputs('{viole}')), 'True')"
            cond(z, "Si_champs_verrouilles_modifies", vv, restore)
            # § 6.5 : empreinte vide sur une affectation déjà active (données importées) → initialisation, sans rien rétablir
            cond(z, "Si_verrou_a_initialiser",
                 f"and(empty({emp}), contains(createArray('Active', 'À risque', 'Bloquée', 'Terminée', 'Clôturée'), {env.AVANT}))",
                 lambda y: patch_item(y, "Initialiser_EmpreinteVerrou", AFF, env.ID, {"EmpreinteVerrou": ip(ev_item(I))}, I))
            env["ALT"] = lookup_first(z, "Alternant_affectation", "Alternants", f"if({vv}, json({emp})?['AlternantId'], {I}?['Alternant']?['Id'])",
                                      fields=("CompteM365", "IdHNCS", "Statut", "ReferentPrincipal", "EmpreinteReferent", "Title"))
            env["REF"] = lookup_first(z, "Referent_affectation", "Referents", f"if({vv}, json({emp})?['ReferentId'], {I}?['Referent']?['Id'])",
                                      fields=("Compte", "IdHNCS", "Statut"))

        def active(z, env):
            def activation(y):
                I, A, R = env.I, env.ALT, env.REF
                am, rm = f"{A}?['CompteM365']?['Email']", f"{R}?['Compte']?['Email']"
                aidobj = f"coalesce({A}?['IdHNCS'], {I}?['Alternant']?['Value'])"
                patch_item(y, "Figer_EmpreinteVerrou", AFF, env.ID, {"EmpreinteVerrou": ip(ev_item(I))}, I)
                suj = lookup_first(y, "Sujet_affectation", "SujetsRD", f"{I}?['Sujet']?['Id']",
                                   fields=("IdHNCS", "Title", "TypeSujet", "GitlabProjetUrl", "ID"))
                sujid = f"coalesce({suj}?['IdHNCS'], {I}?['Sujet']?['Value'])"
                ensure_folder(y, "sujet", "LivrablesRD", sujid)
                grant_folder(y, "sujet", "LivrablesRD", sujid, [("user", am, "CSS")])
                grant_item(y, "affectation", AFF, env.ID, [("user", am, "R")])
                grant_folder(y, "suivi", "SuiviAlternants", aidobj, [("user", rm, "CSS")])
                # Référent principal dérivé (P-09) : référent de l'affectation active la plus récente, historisé
                def ref_change(w):
                    patch_item(w, "Referent_principal", "Alternants", f"{A}?['ID']", {
                        "ReferentPrincipal": at(f"{I}?['Referent']?['Id']"),
                        "EmpreinteReferent": ip(f"string({I}?['Referent']?['Id'])")}, A)
                    post_item(w, "Historiser_referent_principal", "HistoriqueStatuts", {
                        "Title": ip(aidobj), "Objet": "Alternant", "Liste": "Alternants", "ItemId": at(f"int({A}?['ID'])"),
                        "StatutAvant": ip(f"coalesce({A}?['ReferentPrincipal']?['Value'], '')"),
                        "StatutApres": ip(f"coalesce({I}?['Referent']?['Value'], '')"), "CodeTransition": "REF-PRINCIPAL",
                        "Acteur": ip(SVC), "ActeurEmail": ip(SVC), "DateChangement": ip("utcNow()"), "Origine": "Flux",
                        "Resultat": "Acceptée", "Motif": "Changement de référent principal",
                        "FluxRunId": ip("workflow()?['run']?['name']")})
                    grant_item(w, "fiche_alternant", "Alternants", f"{A}?['ID']", [("user", rm, "R")])
                cond(y, "Si_referent_principal_change",
                     f"not(equals(string(coalesce({A}?['ReferentPrincipal']?['Id'], '')), string(coalesce({I}?['Referent']?['Id'], ''))))", ref_change)
                # Livrables proposés depuis le registre (idempotent par affectation + modèle)
                f.use("RegistreModeles", "CreationAuto", "Statut", "ApplicableA", "DelaiStandardJours")
                f.use("SujetsRD", "TypeSujet")
                mods = get_items(y, "Modeles_auto", "RegistreModeles", filter_="CreationAuto eq 1 and Statut eq 'Approuvé'")
                appl = filt(y, "Modeles_applicables", f"body('{mods}')?['value']",
                            f"contains(string(coalesce(item()?['ApplicableA'], createArray())), concat('\"', coalesce({suj}?['TypeSujet']?['Value'], '#'), '\"'))")
                owner = am  # v1.3.0 : Proprietaire = CompteM365 de l'alternant (exigé par G_AFFECTATION_COMPLETE)

                def each(e, loop):
                    m = f"items('{loop}')"
                    ex = get_items(e, "Livrable_propose_existant", LIV, filter_=f"AffectationId eq @{{{env.ID}}} and ModeleId eq @{{{m}?['ID']}}",
                                   fields=("Affectation", "Modele"), top=1)
                    ech = f"addDays({dloc(I + "?['DateDebut']")}, int(coalesce({m}?['DelaiStandardJours'], 0)), 'yyyy-MM-dd')"

                    def mk(c):
                        cond(c, "Si_proprietaire_connu", f"not(empty({owner}))",
                             lambda d: creer_livrable(d, f, "propose", env.ID, env.IDOBJ, suj, m, owner, rm, ech),
                             lambda d: log(d, "Livrable_non_propose", "Avertissement",
                                           q("Livrable non proposé : compte Microsoft 365 de l'alternant absent"), AFF, env.ID, env.IDOBJ))
                    cond(e, "Si_livrable_absent", f"equals(length(body('{ex}')?['value']), 0)", mk)
                foreach(y, "Pour_modele", f"body('{appl}')", each)
                # Premier compte rendu (lot 3 déployé, cadence ≠ Par jalon)
                cad = compose(y, "Cadence_effective", at(cadence_effective(I)))
                present = list_exists(y, "CR", CR)

                def first_cr(w):
                    ex = get_items(w, "CR_existants", CR, filter_=f"AffectationId eq @{{{env.ID}}}", fields=("Affectation",), top=1)

                    def mk(c):
                        deb, fin = period_first(dloc(I + "?['DateDebut']"), f"outputs('{cad}')")
                        _, ech = create_cr(c, "premier", I, A, R, deb, fin)
                        patch_item(c, "ProchaineEcheanceCR", AFF, env.ID, {"ProchaineEcheanceCR": ip(ech)}, I)
                    cond(w, "Si_aucun_CR", f"equals(length(body('{ex}')?['value']), 0)", mk)
                cond(y, "Si_CR_a_creer", f"and({present}, not(equals(outputs('{cad}'), 'Par jalon')))", first_cr)
                lv = get_items(y, "Livrables_affectation", LIV, filter_=f"AffectationId eq @{{{env.ID}}}", fields=("Affectation", "IdHNCS"))
                ids = select(y, "Ids_livrables", f"body('{lv}')?['value']", at("item()?['IdHNCS']"))
                f.use("SujetsRD", "Title", "GitlabProjetUrl")
                notify(y, "N-20", [am, rm], {
                    "IdHNCS": env.IDOBJ, "NomAlternant": f"{A}?['Title']",
                    "Sujet": f"concat({sujid}, ' : ', coalesce({suj}?['Title'], ''))", "Objectifs": f"coalesce({I}?['Objectifs'], '-')",
                    "Livrables": f"if(empty(body('{ids}')), 'aucun', join(body('{ids}'), ', '))",
                    "LienSujet": item_link("SujetsRD", f"coalesce({suj}?['ID'], 0)"),
                    "LienGitlab": f"coalesce({suj}?['GitlabProjetUrl'], {item_link('SujetsRD', f"coalesce({suj}?['ID'], 0)")})",
                    "LienModeles": list_link("ModelesRD"), "LienDossierSuivi": lib_url("SuiviAlternants", aidobj),
                    "Lien": env.LIEN}, teams_to=[am, rm])
                # Remplacement : terminer l'ancienne affectation (AFF-T05, FLUX) puis N-22 (§ 6.1-8)
                def replace(w):
                    old = lookup_first(w, "Affectation_remplacee", AFF, f"{I}?['AffectationRemplacee']?['Id']",
                                       fields=("Statut", "DateDebut", "DateFin", "IdHNCS", "ID", "MotifFin", "Alternant", "Referent"))

                    def end_old(v):
                        oid = f"{old}?['ID']"
                        prev = f"addDays({dloc(I + "?['DateDebut']")}, -1, 'yyyy-MM-dd')"
                        odeb = dloc(old + "?['DateDebut']")
                        patch_item(v, "Date_fin_ancienne", AFF, oid, {
                            "DateFin": ip(f"if(greater({odeb}, {prev}), {odeb}, {prev})"),
                            "MotifFin": ip(f"concat('Remplacée par ', {env.IDOBJ})")}, old)
                        ro = get_item(v, "Relire_ancienne", AFF, oid)
                        RO = f"body('{ro}')"
                        oidobj = f"coalesce({RO}?['IdHNCS'], string({oid}))"
                        oref = lookup_first(v, "Referent_ancienne", "Referents", f"{RO}?['Referent']?['Id']", fields=("Compte",))
                        flux_transition(v, "AFF_T05_remplacee", "Affectation", AFF, oid, oidobj, f"{RO}?['Statut']?['Value']", "Terminée",
                                        "AFF-T05", affectation_controls(f, RO, oid, controls_needed_for("AFF-T05"), A, R), src=RO,
                                        after_fn=lambda u: n22(u, f, RO, oid, oidobj, am, f"{oref}?['Compte']?['Email']", "remplacee"))
                    cond(w, "Si_ancienne_active", f"contains(createArray('Active', 'À risque', 'Bloquée'), coalesce({old}?['Statut']?['Value'], ''))", end_old)
                cond(y, "Si_remplacement", f"not(empty({I}?['AffectationRemplacee']?['Id']))", replace)
            cond(z, "Si_activation", f"equals({env.AVANT}, 'À préparer')", activation)

        def risque(z, env):
            notify(z, "N-21", [f.group_emails("G_DRD")], {"IdHNCS": env.IDOBJ, "Statut": env.APRES, "Lien": env.LIEN})

        def terminee(z, env):
            n22(z, f, env.I, env.ID, env.IDOBJ, f"{env.ALT}?['CompteM365']?['Email']", f"{env.REF}?['Compte']?['Email']", "terminee")

        needed = MODEL.controls_for("Affectation", f.targets)
        transition_body(s, f, AFF, "Affectation", pre=pre,
                        effects={"Active": active, "À risque": risque, "Bloquée": risque, "Terminée": terminee},
                        auteur=lambda env: f"{env.ALT}?['CompteM365']?['Email']", valideur=lambda env: f"{env.REF}?['Compte']?['Email']",
                        controls=lambda y, tag: affectation_controls(f, I_EL, f"{I_EL}?['ID']", needed,
                                                                     first("Alternant_affectation"), first("Referent_affectation"))(y, tag))
    standard_shell(f, body, AFF, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-05"]
    return f


# --------------------------------------------------------------------------------------------
# PA-06 : Échéance de livrable
# --------------------------------------------------------------------------------------------

def pa06():
    f = Flow("PA-06", "PA-06", "HNCS-RD PA-06 : Échéance de livrable", 2, "Planifié", "Recurrence", recurrence="Quotidien 07:00 (heure de Paris)")
    recurrence_trigger(f, {"frequency": "Day", "interval": 1, "schedule": {"hours": ["7"], "minutes": [0]}})

    def body(s):
        lv = get_items(s, "Livrables_en_production", LIV, filter_="Statut eq 'À produire' or Statut eq 'En cours' or Statut eq 'Corrections demandées'",
                       fields=("Statut", "Echeance", "EnRetard", "DernierRappel", "Proprietaire", "Reviseur", "IdHNCS", "ID"))
        rappels = f"split(replace({P('Delai.RappelLivrableJours', '7;2')}, ' ', ''), ';')"

        def each(e, loop):
            it = f"items('{loop}')"
            ech = dloc(it + "?['Echeance']")
            diff = compose(e, "Jours_avant_echeance", at(f"div(sub(ticks({ech}), ticks({TODAY})), 864000000000)"))
            d = f"outputs('{diff}')"
            idl = f"coalesce({it}?['IdHNCS'], string({it}?['ID']))"
            own, rev = f"{it}?['Proprietaire']?['Email']", f"{it}?['Reviseur']?['Email']"
            dr = f"coalesce({it}?['DernierRappel'], '')"

            def rappel(y):
                key = f"concat('J-', string({d}), ':', {ech})"
                cond(y, "Si_rappel_non_envoye", f"not(equals({dr}, {key}))", lambda w: (
                    notify(w, "N-23", [own], {"IdHNCS": idl, "Date": dfr(it + "?['Echeance']"), "Lien": item_link(LIV, f"{it}?['ID']")}, teams_to=[own]),
                    patch_item(w, "Memoriser_rappel", LIV, f"{it}?['ID']", {"DernierRappel": ip(key)}, it)))

            def retard(y):
                key = f"concat('J+1:', {ech})"
                patch_item(y, "Marquer_en_retard", LIV, f"{it}?['ID']", {"EnRetard": at("true"),
                                                                       "DernierRappel": ip(f"if(equals({dr}, {key}), {dr}, {key})")}, it)
                cond(y, "Si_retard_non_notifie", f"not(equals({dr}, {key}))",
                     lambda w: notify(w, "N-24", [own, rev], {"IdHNCS": idl, "Date": dfr(it + "?['Echeance']"),
                                                              "JoursRetard": f"string(mul(-1, {d}))", "Lien": item_link(LIV, f"{it}?['ID']")},
                                      teams_to=[own, rev]))

            def a_l_heure(y):
                cond(y, "Si_retard_leve", truthy(it + "?['EnRetard']"),
                     lambda w: patch_item(w, "Lever_retard", LIV, f"{it}?['ID']", {"EnRetard": at("false")}, it))
                cond(y, "Si_palier_de_rappel", f"contains({rappels}, string({d}))", rappel)
            cond(e, "Si_echeance_depassee", f"and(not(empty({it}?['Echeance'])), less({d}, 0))", retard, a_l_heure)
        foreach(s, "Pour_livrable", f"body('{lv}')?['value']", each)
        hors = get_items(s, "Livrables_hors_production_en_retard", LIV,
                         filter_="EnRetard eq 1 and Statut ne 'À produire' and Statut ne 'En cours' and Statut ne 'Corrections demandées'",
                         fields=("EnRetard", "Statut", "ID"))
        foreach(s, "Pour_livrable_hors_production", f"body('{hors}')?['value']",
                lambda e, loop: patch_item(e, "Lever_retard_hors_production", LIV, f"items('{loop}')?['ID']", {"EnRetard": at("false")}, f"items('{loop}')"))
    standard_shell(f, body)
    f.doc = DOC["PA-06"]
    return f


# --------------------------------------------------------------------------------------------
# PA-07 : Revue d'un livrable
# --------------------------------------------------------------------------------------------

def pa07():
    f = Flow("PA-07", "PA-07", "HNCS-RD PA-07 : Revue d'un livrable", 2, "Automatisé", "SharePointItem", LIV,
             targets=targets("PA-07", LIV), objet="Livrable")
    sp_trigger(f, LIV, "GetOnUpdatedItems", [ANTI_LOOP])  # P-09 : toute modification humaine
    f.use(LIV, "Affectation", "Sujet", "Reviseur", "Proprietaire", "Modele", "VersionModele", "Echeance", "EcheanceInitiale",
          "EmpreinteRevue", "EmpreinteCommentaire", "CommentaireRevue", "DateDepot", "DatePremierDepot", "DateRevue", "DecisionRevue",
          "NbCorrections", "Valideur", "DateValidation", "VersionValidee", "DateArchivage", "MotifSuspension", "LienDocument", "Modified")
    f.use("Affectations", "Referent", "Sujet")
    f.use("Referents", "Compte")
    types = col_types(LIV)

    def docs(s, tag, ID):
        return get_items(s, f"Documents_{tag}", "LivrablesRD", filter_=f"LivrableId eq @{{{ID}}}",
                         fields=("Livrable", "StatutDocument", "ID", "Sujet", "TypeDocument"))

    def set_docs(s, tag, ID, status):
        d = docs(s, tag, ID)
        foreach(s, f"Pour_document_{tag}", f"body('{d}')?['value']",
                lambda e, loop: patch_item(e, f"Statut_document_{tag}", "LivrablesRD", f"items('{loop}')?['ID']",
                                           {"StatutDocument": status}, None))
        f.use("LivrablesRD", "StatutDocument")
        return d

    def body(s):
        def pre(z, env):
            I = env.I
            aff = lookup_first(z, "Affectation_livrable", AFF, f"{I}?['Affectation']?['Id']", fields=("Referent", "Sujet", "ID"))
            ref = lookup_first(z, "Referent_affectation", "Referents", f"{aff}?['Referent']?['Id']", fields=("Compte",))
            env["REFMAIL"] = f"{ref}?['Compte']?['Email']"
            # 0. Champs protégés (P-09)
            cur, curc = fp_compute(z, f, LIV, I, LIV_FP, "Empreinte_courante")
            emp = f"coalesce({I}?['EmpreinteRevue'], '')"
            REV_KEYS = ["DoD", "Echeance"]  # habilités : RD, DIRECTION_RD et le réviseur légitime
            dod_changed = filt(z, "DoD_modifies", f"if(empty({emp}), createArray(), {changed_keys(emp, curc, REV_KEYS, LIV_FP)})", "not(empty(item()))")
            other_changed = filt(z, "Autres_champs_modifies",
                                 f"if(empty({emp}), createArray(), {changed_keys(emp, curc, [k for k in LIV_FP if k not in REV_KEYS], LIV_FP)})",
                                 "not(empty(item()))")
            drd = f.group_emails("G_DRD")
            rev_cur = f"toLower(coalesce({I}?['Reviseur']?['Email'], ''))"
            rev_ok = (f"or(empty({rev_cur}), equals({rev_cur}, toLower(coalesce({env.REFMAIL}, '#'))), "
                      f"contains(split({drd}, ';'), {rev_cur}))")
            rev_changed = f"and(not(empty({emp})), not(equals(toLower(string(coalesce(json({emp})?['Reviseur'], ''))), {rev_cur})))"
            rd = f"contains(split(concat({f.group_emails('G_RD')}, ';', {f.group_emails('G_DRD')}), ';'), {ACTEUR})"
            legit_rev = f"and(equals({ACTEUR}, toLower(coalesce({I}?['Reviseur']?['Email'], '#'))), " + \
                valideur_legitime(f, ACTEUR, env.REFMAIL, f"{I}?['Reviseur']?['Email']", f"{I}?['Proprietaire']?['Email']") + ")"
            violation = (f"and(not(empty({emp})), or(and(greater(length(body('{other_changed}')), 0), not({rd})), "
                         f"and(greater(length(body('{dod_changed}')), 0), not(or({rd}, {legit_rev}))), "
                         f"and({rev_changed}, not({rev_ok}))))")

            def restore(y):
                patch_item(y, "Retablir_champs_proteges", LIV, env.ID, fp_restore_values(LIV, emp, LIV_FP, types), I)
                log(y, "Champs_proteges_retablis", "Avertissement", q("P-09 : modification non autorisée de champs protégés du livrable annulée"),
                    LIV, env.ID, env.IDOBJ)
                notify(y, "N-92", [ACTEUR], {"IdHNCS": env.IDOBJ,
                                             "Champs": f"join(union(body('{other_changed}'), body('{dod_changed}')), ', ')",
                                             "RoleHabilite": q("Équipe R&D ou Direction R&D (échéance et critères de la Definition of Done : également le réviseur légitime ; réviseur : référent de l'affectation ou membre de la Direction R&D)"),
                                             "Lien": env.LIEN}, teams_to=[ACTEUR])
                terminate(y, "Fin_champs_retablis")
            cond(z, "Si_champ_protege_modifie_sans_droit", violation, restore)

            # 1. Création (∅ → À produire)
            def creation(y):
                mod = lookup_first(y, "Modele_livrable", "RegistreModeles", f"{I}?['Modele']?['Id']", fields=("Version",))
                patch_item(y, "Effets_creation", LIV, env.ID, {
                    "Sujet": at(f"coalesce({I}?['Sujet']?['Id'], {aff}?['Sujet']?['Id'])"),
                    # réviseur vide ou non légitime (ni référent ni Direction R&D) → référent de l'affectation
                    "Reviseur": at(f"if({rev_ok}, coalesce({I}?['Reviseur']?['Claims'], {env.REFMAIL}), {env.REFMAIL})"),
                    "VersionModele": at(f"coalesce({I}?['VersionModele'], {mod}?['Version'])"),
                    "EcheanceInitiale": at(f"coalesce({I}?['EcheanceInitiale'], {dloc(I + "?['Echeance']")})")}, I)
                grant_item(y, "proprietaire", LIV, env.ID, [("user", f"{I}?['Proprietaire']?['Email']", "CSS")])
                cond(y, "Si_reviseur_refuse", f"not({rev_ok})",
                     lambda w: notify(w, "N-92", [ACTEUR], {"IdHNCS": env.IDOBJ, "Champs": q("Reviseur"),
                                                            "RoleHabilite": q("Réviseur : référent de l'affectation ou membre de la Direction R&D"),
                                                            "Lien": env.LIEN}, teams_to=[ACTEUR]))
            cond(z, "Si_creation", f"and(equals({env.AVANT}, '∅'), equals({env.APRES}, 'À produire'))", creation)
            env["REV"] = f"if(and(not(empty({I}?['Reviseur']?['Email'])), {rev_ok}), {I}?['Reviseur']?['Email'], {env.REFMAIL})"

        dec_new = "less(ticks(coalesce({I}?['DateRevue'], '1900-01-01T00:00:00Z')), ticks(triggerOutputs()?['body/Modified']))"

        def soumis(z, env):
            I = env.I
            patch_item(z, "Depot", LIV, env.ID, {"DateDepot": ip("utcNow()"), "DatePremierDepot": at(f"coalesce({I}?['DatePremierDepot'], utcNow())")}, I)
            set_docs(z, "soumis", env.ID, "Soumis")
            notify(z, "N-25", [env.REV], {"IdHNCS": env.IDOBJ, "NomAuteur": f"coalesce({I}?['Proprietaire']?['DisplayName'], '')",
                                          "Lien": env.LIEN, "LienDocument": f"coalesce({I}?['LienDocument'], {env.LIEN})"}, teams_to=[env.REV])

        def corrections(z, env):
            I = env.I

            def record(y):
                patch_item(y, "Decision_corrections", LIV, env.ID, {
                    "DateRevue": ip("utcNow()"), "DecisionRevue": "Corrections demandées",
                    "NbCorrections": at(f"add(int(coalesce({I}?['NbCorrections'], 0)), 1)"),
                    "EmpreinteCommentaire": at(f"{I}?['CommentaireRevue']")}, I)
            cond(z, "Si_decision_non_enregistree", dec_new.format(I=I), record)
            code = f"concat('CORR-', formatDateTime(triggerOutputs()?['body/Modified'], 'yyyyMMddHHmmss'))"
            ex = get_items(z, "Action_correction_existante", ACT, filter_=f"LivrableId eq @{{{env.ID}}} and CodeModeleAction eq {odq(code)}",
                           fields=("Livrable", "CodeModeleAction", "IdHNCS", "Echeance"), top=1)
            ech = f"if(less({dloc(I + "?['Echeance']")}, {TODAY}), addDays({TODAY}, 5, 'yyyy-MM-dd'), {dloc(I + "?['Echeance']")})"
            own = f"{I}?['Proprietaire']?['Email']"

            def mk(y):
                p, _ = create_with_id(y, "Creer_action_correction", ACT, {
                    "Title": ip(f"concat('Corriger le livrable ', {env.IDOBJ})"), "Contexte": "Correction livrable",
                    "Livrable": at(env.ID), "Echeance": ip(ech), "Bloquante": at("false"), "CodeModeleAction": ip(code),
                    "RoleResponsable": "ITEM_AUTEUR", "Statut": "À faire"})
                pid = f"body('{p}')?['ID']"
                patch_item(y, "Responsable_correction", ACT, pid, {"Responsable": ip(own), "EmpreinteAction": ip(emp_action(f"body('{p}')"))}, f"body('{p}')")
                grant_item(y, "correction", ACT, pid, [("user", own, "CSS")])
            cond(z, "Si_action_correction_absente", f"equals(length(body('{ex}')?['value']), 0)", mk)
            ac = get_items(z, "Action_correction", ACT, filter_=f"LivrableId eq @{{{env.ID}}} and CodeModeleAction eq {odq(code)}",
                           fields=("Livrable", "CodeModeleAction", "IdHNCS", "Echeance"), top=1)
            notify(z, "N-26", [own], {"IdHNCS": env.IDOBJ,
                                      "Commentaires": f"replace(coalesce({I}?['CommentaireRevue'], ''), decodeUriComponent('%0A'), '<br/>')",
                                      "IdAction": f"coalesce({first(ac)}?['IdHNCS'], '')", "EcheanceAction": dfr(first(ac) + "?['Echeance']"),
                                      "Lien": env.LIEN}, teams_to=[own])

        def valide(z, env):
            I = env.I
            d = docs(z, "valide", env.ID)

            def record(y):
                patch_item(y, "Decision_validation", LIV, env.ID, {
                    "DateRevue": ip("utcNow()"), "DecisionRevue": "Validé", "EmpreinteCommentaire": at(f"{I}?['CommentaireRevue']"),
                    "Valideur": ip("triggerOutputs()?['body/Editor/Email']"), "DateValidation": ip("utcNow()"),
                    "VersionValidee": ip(f"string(coalesce(first(body('{d}')?['value'])?['{{VersionNumber}}'], ''))")}, I)
            cond(z, "Si_validation_non_enregistree", dec_new.format(I=I), record)
            set_docs(z, "valide", env.ID, "Validé")
            oc = get_items(z, "Corrections_ouvertes", ACT,
                           filter_=f"LivrableId eq @{{{env.ID}}} and Contexte eq 'Correction livrable' and Statut ne 'Terminée' and Statut ne 'Non applicable'",
                           fields=("Livrable", "Contexte", "Statut", "ID"))
            f.status(ACT, "Terminée")
            foreach(z, "Pour_correction_ouverte", f"body('{oc}')?['value']",
                    lambda e, loop: patch_item(e, "Terminer_correction", ACT, f"items('{loop}')?['ID']", {"Statut": "Terminée"}, f"items('{loop}')"))
            notify(z, "N-27", [f"{I}?['Proprietaire']?['Email']"], {
                "IdHNCS": env.IDOBJ, "Valideur": "coalesce(triggerOutputs()?['body/Editor/DisplayName'], '')",
                "Date": dfr("utcNow()"), "Version": f"string(coalesce(first(body('{d}')?['value'])?['{{VersionNumber}}'], '-'))",
                "Lien": env.LIEN}, teams_to=[f"{I}?['Proprietaire']?['Email']"])

        def archive(z, env, tag="man"):
            patch_item(z, f"Date_archivage_{tag}", LIV, env.ID, {"DateArchivage": at(f"coalesce({env.I}?['DateArchivage'], utcNow())")}, env.I)
            set_docs(z, f"ref_{tag}", env.ID, "Référence")
            log(z, f"Journaliser_archivage_{tag}", "Info", q("Livrable archivé et capitalisé (documents « Référence »)"), LIV, env.ID, env.IDOBJ)

        def suspendu(z, env):
            I = env.I
            notify(z, "N-29", [f"{I}?['Proprietaire']?['Email']", env.REV], {
                "IdHNCS": env.IDOBJ, "Statut": env.APRES, "Motif": f"coalesce({I}?['MotifSuspension'], '-')", "Lien": env.LIEN})

        def post(s2, env):
            def capitalise(y):
                rr = get_item(y, "Relire_livrable", LIV, env.ID)
                R = f"body('{rr}')"
                ok, detail, _ = capitalisation_parts(y, f, R, env.ID, "post")

                def t08(w):
                    flux_transition(w, "LIV_T08", "Livrable", LIV, env.ID, env.IDOBJ, q("Validé"), "Archivé / clôturé", "LIV-T08",
                                    lambda u, tag: {"G_CAPITALISATION": (ok, q("G_CAPITALISATION"))}, src=R,
                                    extra_values={"DateArchivage": ip("utcNow()")},
                                    after_fn=lambda u: (set_docs(u, "ref_flux", env.ID, "Référence"),
                                                        log(u, "Journaliser_archivage", "Info", q("Livrable archivé et capitalisé (LIV-T08)"),
                                                            LIV, env.ID, env.IDOBJ)))
                incomplete = (lambda w: notify(w, "N-28", [env.REV], {"IdHNCS": env.IDOBJ, "ElementsManquants": detail, "Lien": env.LIEN})) \
                    if not env.NOTRANS else None
                cond(y, "Si_capitalisation_possible", ok, t08, incomplete)
            cond(s2, "Si_valide_non_archive", f"equals({env.APRES}, 'Validé')", capitalise)
            fp_refresh(s2, "fin", LIV, env.ID, LIV_FP)

        needed = MODEL.controls_for("Livrable", f.targets)
        transition_body(s, f, LIV, "Livrable", pre=pre, post=post,
                        effects={"Soumis à revue": soumis, "Corrections demandées": corrections, "Validé": valide,
                                 "Archivé / clôturé": archive, "Suspendu / abandonné": suspendu},
                        auteur=lambda env: f"{env.I}?['Proprietaire']?['Email']", valideur=lambda env: env.REV,
                        controls=lambda y, tag: livrable_controls(f, I_EL, f"{I_EL}?['ID']", needed, ACTEUR,
                                                                  f"{first('Referent_affectation')}?['Compte']?['Email']")(y, tag))
    standard_shell(f, body, LIV, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-07"]
    return f


def pa07b():
    f = Flow("PA-07b", "PA-07b", "HNCS-RD PA-07b : Dépôt d'une nouvelle version", 2, "Automatisé", "SharePointFile", "LivrablesRD")
    sp_trigger(f, "LivrablesRD", "GetOnUpdatedFileItems", [ANTI_LOOP, "@not(empty(triggerOutputs()?['body/Livrable/Id']))"])
    f.use("LivrablesRD", "Livrable", "Sujet", "IdObjet", "ID")

    def body(s):
        T = "triggerOutputs()?['body"
        restore_flux_columns(s, "LivrablesRD", "triggerOutputs()?['body/ID']", "''",
                             "toLower(coalesce(triggerOutputs()?['body/Editor/Email'], ''))")
        g = get_item(s, "Lire_livrable", LIV, f"{T}/Livrable/Id']")
        L = f"body('{g}')"
        f.use(LIV, "IdHNCS", "Sujet", "LienDocument", "ID")
        patch_item(s, "Metadonnees_document", "LivrablesRD", f"{T}/ID']", {
            "IdObjet": ip(f"{L}?['IdHNCS']"), "Sujet": at(f"coalesce({T}/Sujet/Id'], {L}?['Sujet']?['Id'])")}, None)
        cond(s, "Si_LienDocument_vide", f"empty({L}?['LienDocument'])",
             lambda y: patch_item(y, "Renseigner_LienDocument", LIV, f"{L}?['ID']", {"LienDocument": ip(f"{T}/{{Link}}']")}, L))
    standard_shell(f, body, "LivrablesRD", "triggerOutputs()?['body/ID']", "''")
    f.doc = DOC["PA-07b"]
    return f


# --------------------------------------------------------------------------------------------
# PA-08 : Compte rendu périodique et PA-08b
# --------------------------------------------------------------------------------------------

def pa08():
    f = Flow("PA-08", "PA-08", "HNCS-RD PA-08 : Compte rendu périodique", 3, "Automatisé", "SharePointItem", CR,
             targets=targets("PA-08", CR), objet="CompteRendu")
    sp_trigger(f, CR, "GetOnUpdatedItems", [ANTI_LOOP])  # P-09 : toute modification humaine
    f.use(CR, "Affectation", "Alternant", "Valideur", "Title", "PeriodeDebut", "PeriodeFin", "EmpreinteRevue", "DateRemise",
          "DateValidation", "CommentaireReferent", "BlocageSignale", "EtatGeneral", "Avancement", "IdHNCS")
    f.use("Affectations", "Referent", "Alternant", "IdHNCS")
    f.use("Alternants", "CompteM365", "Title")
    f.use("Referents", "Compte")
    types = col_types(CR)

    def body(s):
        def pre(z, env):
            I = env.I
            aff = lookup_first(z, "Affectation_CR", AFF, f"{I}?['Affectation']?['Id']", fields=("Referent", "Alternant", "IdHNCS", "ID"))
            ref = lookup_first(z, "Referent_CR", "Referents", f"{aff}?['Referent']?['Id']", fields=("Compte",))
            alt = lookup_first(z, "Alternant_CR", "Alternants", f"coalesce({I}?['Alternant']?['Id'], {aff}?['Alternant']?['Id'])",
                               fields=("CompteM365", "Title"))
            env["REFMAIL"], env["ALTMAIL"], env["ALTNOM"] = f"{ref}?['Compte']?['Email']", f"{alt}?['CompteM365']?['Email']", f"{alt}?['Title']"
            env["VAL"] = f"if(empty({I}?['Valideur']?['Email']), {env.REFMAIL}, {I}?['Valideur']?['Email'])"
            cur, curc = fp_compute(z, f, CR, I, CR_FP, "Empreinte_courante")
            emp = f"coalesce({I}?['EmpreinteRevue'], '')"
            oth = filt(z, "Champs_proteges_modifies", f"if(empty({emp}), createArray(), {changed_keys(emp, curc, list(CR_FP), CR_FP)})",
                       "not(empty(item()))")
            rd = f"contains(split(concat({f.group_emails('G_RD')}, ';', {f.group_emails('G_DRD')}), ';'), {ACTEUR})"
            violation = f"and(not(empty({emp})), greater(length(body('{oth}')), 0), not({rd}))"

            def restore(y):
                patch_item(y, "Retablir_champs_proteges", CR, env.ID, fp_restore_values(CR, emp, CR_FP, types), I)
                log(y, "Champs_proteges_retablis", "Avertissement", q("P-09 : modification non autorisée de champs protégés du compte rendu annulée"),
                    CR, env.ID, env.IDOBJ)
                notify(y, "N-92", [ACTEUR], {"IdHNCS": env.IDOBJ, "Champs": f"join(body('{oth}'), ', ')",
                                             "RoleHabilite": q("Équipe R&D ou Direction R&D (l'alternant ne modifie que les champs de contenu, le référent que son commentaire)"),
                                             "Lien": env.LIEN}, teams_to=[ACTEUR])
                terminate(y, "Fin_champs_retablis")
            cond(z, "Si_champ_protege_modifie_sans_droit", violation, restore)

            def creation(y):
                patch_item(y, "Effets_creation", CR, env.ID, {
                    "Title": ip(f"coalesce({I}?['Title'], concat('CR ', coalesce({aff}?['IdHNCS'], ''), ' : ', {dloc(I + "?['PeriodeDebut']")}, ' au ', {dloc(I + "?['PeriodeFin']")}))"),
                    "Alternant": at(f"coalesce({I}?['Alternant']?['Id'], {aff}?['Alternant']?['Id'])"),
                    "Valideur": at(f"if(empty({I}?['Valideur']?['Email']), {env.REFMAIL}, {I}?['Valideur']?['Claims'])")}, I)
                grant_item(y, "cr", CR, env.ID, [("user", env.ALTMAIL, "CSS"), ("user", env.VAL, "CSS")])
            cond(z, "Si_creation", f"and(equals({env.AVANT}, '∅'), equals({env.APRES}, 'Attendu'))", creation)

        def remis(z, env):
            I = env.I
            patch_item(z, "Date_remise", CR, env.ID, {"DateRemise": ip("utcNow()")}, I)
            notify(z, "N-32", [env.VAL], {"IdHNCS": env.IDOBJ, "NomAlternant": env.ALTNOM, "EtatGeneral": f"coalesce({I}?['EtatGeneral']?['Value'], '-')",
                                          "Avancement": f"string(coalesce({I}?['Avancement'], '-'))", "Lien": env.LIEN}, teams_to=[env.VAL])
            cond(z, "Si_blocage_signale", truthy(I + "?['BlocageSignale']"),
                 lambda y: notify(y, "N-33", [f.group_emails("G_DRD")], {"IdHNCS": env.IDOBJ, "Lien": env.LIEN}))

        def n34(z, env, explication):
            notify(z, "N-34", [env.ALTMAIL], {"IdHNCS": env.IDOBJ, "Statut": env.APRES, "Explication": q(explication),
                                              "Commentaire": f"replace(coalesce({env.I}?['CommentaireReferent'], '-'), decodeUriComponent('%0A'), '<br/>')",
                                              "Lien": env.LIEN}, teams_to=[env.ALTMAIL])

        def valide(z, env):
            patch_item(z, "Date_validation", CR, env.ID, {"DateValidation": ip("utcNow()")}, env.I)
            n34(z, env, "validation confirmée par votre référent")

        def a_completer(z, env):
            n34(z, env, "votre référent demande des compléments")

        needed = MODEL.controls_for("CompteRendu", f.targets)
        transition_body(s, f, CR, "CompteRendu", pre=pre, post=lambda s2, env: fp_refresh(s2, "fin", CR, env.ID, CR_FP),
                        effects={"Remis": remis, "Validé": valide, "À compléter": a_completer},
                        auteur=lambda env: env.ALTMAIL, valideur=lambda env: env.VAL,
                        controls=lambda y, tag: cr_controls(f, I_EL, needed, ACTEUR, f"{first('Referent_CR')}?['Compte']?['Email']",
                                                            f"{first('Alternant_CR')}?['CompteM365']?['Email']")(y, tag))
    standard_shell(f, body, CR, "triggerOutputs()?['body/ID']", "triggerOutputs()?['body/IdHNCS']")
    f.doc = DOC["PA-08"]
    return f


def pa08b():
    f = Flow("PA-08b", "PA-08b", "HNCS-RD PA-08b : Création et relance des comptes rendus", 3, "Planifié", "Recurrence",
             recurrence="Quotidien 06:45 (heure de Paris)")
    recurrence_trigger(f, {"frequency": "Day", "interval": 1, "schedule": {"hours": ["6"], "minutes": [45]}})

    def body(s):
        affs = get_items(s, "Affectations_en_cours", AFF, filter_="Statut eq 'Active' or Statut eq 'À risque' or Statut eq 'Bloquée'",
                         fields=("Statut", "CadenceCR", "DateDebut", "Alternant", "Referent", "IdHNCS", "ID", "ProchaineEcheanceCR"))

        def each(e, loop):
            a = f"items('{loop}')"
            cad = compose(e, "Cadence", at(cadence_effective(a)))
            deb = compose(e, "Debut_periode", at(period_current(dloc(a + "?['DateDebut']"), f"outputs('{cad}')")))
            fin = compose(e, "Fin_periode", at(period_end(f"outputs('{deb}')", f"outputs('{cad}')")))

            def check(y):
                crs = get_items(y, "CR_affectation", CR, filter_=f"AffectationId eq @{{{a}?['ID']}}", fields=("Affectation", "PeriodeDebut", "PeriodeFin"))
                cov = filt(y, "CR_periode_courante", f"body('{crs}')?['value']",
                           f"and(lessOrEquals({dloc("item()?['PeriodeDebut']")}, {TODAY}), greaterOrEquals({dloc("item()?['PeriodeFin']")}, {TODAY}))")

                def mk(w):
                    alt = lookup_first(w, "Alternant_aff", "Alternants", f"{a}?['Alternant']?['Id']", fields=("CompteM365",))
                    ref = lookup_first(w, "Referent_aff", "Referents", f"{a}?['Referent']?['Id']", fields=("Compte",))
                    _, ech = create_cr(w, "periode", a, alt, ref, f"outputs('{deb}')", f"outputs('{fin}')")
                    patch_item(w, "ProchaineEcheanceCR", AFF, f"{a}?['ID']", {"ProchaineEcheanceCR": ip(ech)}, a)
                cond(y, "Si_periode_non_couverte", f"equals(length(body('{cov}')), 0)", mk)
            cond(e, "Si_cadence_periodique", f"not(equals(outputs('{cad}'), 'Par jalon'))", check)
        foreach(s, "Pour_affectation", f"body('{affs}')?['value']", each)
        ouverts = get_items(s, "CR_ouverts", CR, filter_="Statut eq 'Attendu' or Statut eq 'En rédaction'",
                            fields=("Statut", "Echeance", "DernierRappel", "Alternant", "Valideur", "PeriodeDebut", "PeriodeFin", "IdHNCS", "ID",
                                    "Realisations", "ProchainesEtapes", "Avancement", "CommentaireReferent"))
        demain = f"addDays({TODAY}, 1, 'yyyy-MM-dd')"
        veille = filt(s, "CR_echeance_demain", f"body('{ouverts}')?['value']",
                      f"and(equals({dloc("item()?['Echeance']")}, {demain}), not(equals(coalesce(item()?['DernierRappel'], ''), concat('J-1:', {demain}))))")

        def rappel(e, loop):
            it = f"items('{loop}')"
            alt = lookup_first(e, "Alternant_CR", "Alternants", f"{it}?['Alternant']?['Id']", fields=("CompteM365",))
            am = f"{alt}?['CompteM365']?['Email']"
            notify(e, "N-30", [am], {"IdHNCS": f"coalesce({it}?['IdHNCS'], string({it}?['ID']))", "Date": dfr(it + "?['Echeance']"),
                                     "Periode": f"concat({dfr(it + "?['PeriodeDebut']")}, ' au ', {dfr(it + "?['PeriodeFin']")})",
                                     "Lien": item_link(CR, f"{it}?['ID']")}, teams_to=[am])
            patch_item(e, "Memoriser_rappel", CR, f"{it}?['ID']", {"DernierRappel": ip(f"concat('J-1:', {demain})")}, it)
        foreach(s, "Pour_rappel", f"body('{veille}')", rappel)
        echus = filt(s, "CR_echus", f"body('{ouverts}')?['value']",
                     f"and(not(empty(item()?['Echeance'])), greater({TODAY}, addDays({dloc("item()?['Echeance']")}, int({P('CR.DelaiNonRemisJours', '3')}), 'yyyy-MM-dd')))")

        def non_remis(e, loop):
            it = f"items('{loop}')"
            idc = f"coalesce({it}?['IdHNCS'], string({it}?['ID']))"
            alt = lookup_first(e, "Alternant_echu", "Alternants", f"{it}?['Alternant']?['Id']", fields=("Title",))
            flux_transition(e, "CR_T04", "CompteRendu", CR, f"{it}?['ID']", idc, f"{it}?['Statut']?['Value']", "Non remis", "CR-T04",
                            cr_controls(f, it, controls_needed_for("CR-T04")), src=it,
                            after_fn=lambda w: notify(w, "N-31", [f"{it}?['Valideur']?['Email']"], {
                                "IdHNCS": idc, "NomAlternant": f"{alt}?['Title']", "Date": dfr(it + "?['Echeance']"),
                                "Periode": f"concat({dfr(it + "?['PeriodeDebut']")}, ' au ', {dfr(it + "?['PeriodeFin']")})",
                                "Lien": item_link(CR, f"{it}?['ID']")}))
        foreach(s, "Pour_CR_echu", f"body('{echus}')", non_remis)
    standard_shell(f, body)
    f.doc = DOC["PA-08b"]
    return f


BUILDERS = [pa05, pa06, pa07, pa07b, pa08, pa08b]

DOC = {
    "PA-05": dict(
        objectif="Exécuter les conséquences d'une affectation décidée par la R&D (accès, livrables proposés, premier compte rendu, référent principal), protéger l'affectation active (P-03) et terminer une affectation remplacée sans l'écraser.",
        entrees="Élément `Affectations` créé ou modifié (changement de statut, ou champs verrouillés différents de `EmpreinteVerrou`).",
        etapes=["`IdHNCS` ; `Title` = `{IdAlternant} / {IdSujet}` si vide.",
                "Verrouillage (P-03) : `EmpreinteVerrou` (`{\"AlternantId\":12,\"SujetId\":3,\"ReferentId\":5,\"DateDebut\":\"2026-11-02\"}`, § 6.5) renseignée et `Alternant`, `Sujet`, `Referent` ou `DateDebut` différents (comparaison clé par clé) → valeurs rétablies, Avertissement, N-91 à l'auteur (« créez une nouvelle affectation ») ; si la même modification change le statut, la transition est ensuite traitée sur les valeurs rétablies, sinon fin ; empreinte vide sur une affectation déjà validée (données importées) → initialisée sans rien rétablir.",
                "Transition : PA-00A (`ItemAuteurEmail` = compte de l'alternant, `ItemValideurEmail` = compte du référent) puis `G_AFFECTATION_COMPLETE` (dont `CompteM365` de l'alternant renseigné), `G_DATE_FIN`, `G_LIVRABLES_CLOS`.",
                "**Active** (depuis « À préparer ») : `EmpreinteVerrou` figée ; dossier `04 : Livrables R&D/{SUJ}` (alternant CSS) ; lecture de l'alternant sur l'affectation ; référent CSS sur `05 : Suivi des alternants/{ALT}` ; référent principal de l'alternant = référent de l'affectation (et `EmpreinteReferent`), changement historisé (Objet = Alternant, `CodeTransition` = `REF-PRINCIPAL`, `StatutAvant` / `StatutApres` = `IdHNCS` des référents) et lecture du référent sur la fiche ; livrables « À produire » proposés depuis `RegistreModeles` (`CreationAuto`, « Approuvé », `ApplicableA` contient le type du sujet ; `Proprietaire` = compte de l'alternant, `Reviseur` = compte du référent ; idempotent par affectation + modèle ; effets de création de PA-07 exécutés : propriétaire CSS, `EmpreinteRevue`, LIV-T01 FLUX) ; premier compte rendu « Attendu » si la liste du lot 3 existe et que la cadence n'est pas « Par jalon » (effets de création de PA-08, CR-T01 FLUX), `ProchaineEcheanceCR` ; N-20.",
                "Remplacement (`AffectationRemplacee` active) : `DateFin` = max(début de l'ancienne, début de la nouvelle − 1 jour), `MotifFin` = « Remplacée par {IdHNCS} », AFF-T05 (FLUX, `G_DATE_FIN`) puis N-22 listant les livrables encore ouverts ; aucun autre champ de l'ancienne affectation n'est modifié ; aucun transfert automatique de livrable (H-51).",
                "**À risque / Bloquée** : N-21 à G_DRD. **Terminée** : N-22 (livrables encore ouverts listés, décision de la R&D). **Clôturée** : `G_LIVRABLES_CLOS`.", "PA-00B."],
        sorties="Empreinte, accès, livrables et compte rendu proposés, référent principal, historique, notifications.",
        erreurs="PA-00C ; idempotence sur dossiers, permissions, livrables proposés et compte rendu.",
        decision="Le choix du sujet, du référent et le remplacement sont faits par la R&D ; le flux exécute la conséquence (terminer l'ancienne affectation), propose des livrables modifiables et ne transfère jamais un livrable.",
        tests=["Activation sans référent → refus `G_AFFECTATION_COMPLETE`.", "Modification du sujet d'une affectation active → rétablie, N-91.",
               "Nouvelle affectation remplaçant l'ancienne → ancienne « Terminée », date de fin correcte, N-22 listant ses livrables ouverts.",
               "Activation → référent principal de l'alternant mis à jour et historisé."]),
    "PA-06": dict(
        objectif="Rappeler les échéances de livrables et signaler les retards, une seule fois par palier.",
        entrees="Livrables « À produire », « En cours », « Corrections demandées » ; `Delai.RappelLivrableJours`, `Delai.EscaladeComiteJours`.",
        etapes=["Écart en jours entre l'échéance (date de Paris) et aujourd'hui.",
                "Écart ∈ paliers de rappel (ex. 7 ; 2) → N-23 au propriétaire, `DernierRappel` = `J-n:AAAA-MM-JJ` (échéance) pour ne jamais répéter un palier.",
                "Échéance dépassée → `EnRetard` = Oui ; N-24 au propriétaire et au réviseur une fois (`DernierRappel` = `J+1:échéance`) ; l'escalade au-delà de `Delai.EscaladeComiteJours` est portée par la synthèse PA-11.",
                "Échéance redevenue future → `EnRetard` = Non ; livrables passés dans un autre statut → `EnRetard` = Non, aucun rappel."],
        sorties="`EnRetard`, `DernierRappel`, rappels ciblés (propriétaire et réviseur uniquement).", erreurs="Socle (PA-00C) ; rattrapage le lendemain.",
        decision="Aucune.", tests=["Échéance à J-7 → un N-23.", "Échéance dépassée → un seul N-24, `EnRetard` = Oui.", "Échéance repoussée → `EnRetard` = Non."]),
    "PA-07": dict(
        objectif="Enregistrer les décisions de revue des livrables (jamais les prendre), protéger les champs de revue (P-09) et capitaliser après validation.",
        entrees="Élément `Livrables` créé ou modifié par une personne (toute modification, P-09).",
        etapes=["0. Champs protégés (P-09) : empreinte courante (format § 6.5 : `AffectationId`, `Proprietaire`, `Reviseur`, `Echeance`, `DoD` [5 booléens], `NbCorrections`, `DecisionRevue`, `Valideur`, `DateValidation`, `VersionValidee`, `DatePremierDepot`, `DateDepot`, `DateRevue`) comparée clé par clé à `EmpreinteRevue` ; champ modifié par une personne qui n'est ni membre de G_RD ni de G_DRD (pour `Echeance` et `DoD`, le réviseur légitime est aussi habilité), ou `Reviseur` désigné qui n'est ni le référent de l'affectation ni membre de G_DRD → valeurs rétablies, Avertissement, N-92, fin ; empreinte vide → initialisée sans rien rétablir.",
                "1. Création (∅ → À produire) : `IdHNCS` ; `Sujet` copié de l'affectation ; `Reviseur` = compte du référent s'il est vide ou non légitime (N-92 dans ce dernier cas) ; `VersionModele` ; `EcheanceInitiale` ; héritage rompu et propriétaire CSS ; `EmpreinteRevue` initialisée (étape finale).",
                "2. PA-00A (`ItemAuteurEmail` = `Proprietaire`, `ItemValideurEmail` = `Reviseur`) puis contrôles (`G_DOCUMENT`, `G_VALIDEUR_LEGITIME`, `G_COMMENTAIRE_REVUE` comparé à `EmpreinteCommentaire`, `G_CAPITALISATION`) ; refus → annulation, N-90 (création refusée → corbeille).",
                "3. **Soumis à revue** : `DateDepot`, `DatePremierDepot` si vide ; documents liés → « Soumis » ; N-25 au réviseur.",
                "5. **Corrections demandées** : `DateRevue`, `DecisionRevue`, `NbCorrections` + 1, `EmpreinteCommentaire` (une seule fois par décision : `DateRevue` antérieure à la modification) ; action « Correction livrable » (responsable = propriétaire, CSS, échéance = `Echeance` ou aujourd'hui + 5 j si dépassée, idempotente) ; N-26 avec les commentaires.",
                "6. **Validé** : `DateRevue`, `DecisionRevue`, `EmpreinteCommentaire`, `Valideur` = `Editor`, `DateValidation`, `VersionValidee` = version du document ; documents → « Validé » ; actions de correction ouvertes → « Terminée » ; N-27.",
                "7. **Archivé / clôturé** saisi à la main : `G_CAPITALISATION`, `DateArchivage`, documents → « Référence », `JournalFlux` Info.",
                "8. **Suspendu / abandonné** : N-29.", "9. PA-00B ; puis tentative de capitalisation d'un livrable « Validé » : `G_CAPITALISATION` → LIV-T08 (FLUX), `DateArchivage`, documents « Référence », `JournalFlux` Info ; sinon N-28 au réviseur (le livrable reste « Validé ») ; enfin mise à jour de `EmpreinteRevue`."],
        sorties="Champs de revue, documents, actions de correction, historique, notifications, empreinte.",
        erreurs="PA-00C ; la décision saisie n'est jamais modifiée ; les écritures datées sont protégées contre la double prise en compte d'une resoumission.",
        decision="Validation et demande de corrections réservées au réviseur désigné et légitime (`G_VALIDEUR_LEGITIME`) ; le flux enregistre la décision, ne la prend jamais.",
        tests=["Alternant désigné réviseur de son propre livrable → validation refusée.", "Corrections avec le même commentaire que la fois précédente → refus `G_COMMENTAIRE_REVUE`.",
               "Membre G_REF non réviseur qui coche un critère DoD → rétabli, N-92.", "Validation d'un POC avec DoD complète → archivage automatique (LIV-T08), documents « Référence »."]),
    "PA-07b": dict(
        objectif="Rattacher les documents déposés dans « 04 : Livrables R&D » à leur livrable, sans changer son statut.",
        entrees="Fichier créé ou modifié dans `LivrablesRD` avec la colonne `Livrable` renseignée.",
        etapes=["`IdObjet` = `IdHNCS` du livrable ; `Sujet` du document = sujet du livrable si vide.",
                "`LienDocument` du livrable vide → renseigné avec le lien du fichier.", "**Aucun changement de statut** : la soumission reste une action explicite (LIV-T03)."],
        sorties="Métadonnées du document, lien du livrable.", erreurs="Socle (PA-00C).",
        decision="La soumission reste une décision de l'alternant.", tests=["Dépôt d'un fichier lié → `IdObjet` et `Sujet` renseignés, statut inchangé."]),
    "PA-08": dict(
        objectif="Suivre la remise et la validation des comptes rendus périodiques, en protégeant les champs de validation (P-09).",
        entrees="Élément `ComptesRendus` créé ou modifié par une personne (toute modification).",
        etapes=["Champs protégés (P-09) : `EmpreinteRevue` (format § 6.5 : `AffectationId`, `Valideur`, `Echeance`, `PeriodeDebut`, `PeriodeFin`, `DateValidation`, `DateRemise`) comparée clé par clé en premier ; modification par une personne qui n'est membre ni de G_RD ni de G_DRD → rétablie, Avertissement, N-92, fin ; empreinte vide → initialisée sans rien rétablir.",
                "Création : `IdHNCS`, `Title`, `Alternant` copié de l'affectation, `Valideur` = compte du référent ; alternant et valideur CSS sur l'élément.",
                "PA-00A puis contrôles (`G_CR_COMPLET`, `G_VALIDEUR_LEGITIME`, `G_COMMENTAIRE_REFERENT`, `G_CR_ECHU`).",
                "**Remis** : `DateRemise`, N-32 au valideur ; `BlocageSignale` → N-33 à G_DRD. **Validé** : `DateValidation`, N-34 à l'alternant. **À compléter** : N-34 à l'alternant avec le commentaire.",
                "PA-00B dans tous les cas, puis mise à jour de `EmpreinteRevue`."],
        sorties="Dates, permissions, notifications, historique, empreinte.", erreurs="Socle (PA-00C).",
        decision="La validation du compte rendu appartient au référent légitime ; « Non remis » est un constat de date (PA-08b).",
        tests=["« Remis » sans réalisations → refus `G_CR_COMPLET`.", "L'alternant passe son propre compte rendu à « Validé » → refus.", "Blocage signalé → N-33."]),
    "PA-08b": dict(
        objectif="Créer les comptes rendus attendus selon la cadence, rappeler l'échéance et constater les non-remises.",
        entrees="Affectations « Active », « À risque », « Bloquée » ; comptes rendus « Attendu » / « En rédaction » ; `CR.CadenceGlobale`, `CR.DelaiRemiseJours`, `CR.DelaiNonRemisJours`.",
        etapes=["Cadence « Par jalon » : aucune création automatique (les rappels et le constat « Non remis » s'appliquent aux comptes rendus créés à la main). Cadence effective (`CadenceCR`, sinon `CR.CadenceGlobale`) ≠ « Par jalon » : période courante ancrée sur le début de l'affectation (Hebdomadaire 7 j, Quinzaine 14 j, Mensuelle = mois calendaire) ; aucun compte rendu ne la couvre → création « Attendu » (`Echeance` = fin + `CR.DelaiRemiseJours`, effets de création de PA-08, CR-T01 FLUX) et `ProchaineEcheanceCR`.",
                "Veille de l'échéance → N-30 à l'alternant (une fois, `DernierRappel`).",
                "`G_CR_ECHU` (aujourd'hui > échéance + `CR.DelaiNonRemisJours`) → « Non remis » (CR-T04, FLUX) et N-31 au valideur."],
        sorties="Comptes rendus, rappels, statuts « Non remis ».", erreurs="Socle (PA-00C) ; rattrapage le lendemain.",
        decision="« Non remis » est un constat de date ; la validation reste au référent.",
        tests=["Affectation quinzaine sans CR courant → un CR créé, aucun doublon le lendemain.", "Échéance + 3 j dépassée → « Non remis » et N-31."]),
}
