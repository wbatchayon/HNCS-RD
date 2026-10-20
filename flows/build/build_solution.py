"""Assemble la solution Power Platform NON GÉRÉE « HNCSRDSuivi » à partir de ``flows/src/``.

Produit ``flows/dist/HNCSRDSuivi_<specVersion>.zip`` contenant :
- ``[Content_Types].xml`` ;
- ``solution.xml`` (éditeur ``hncs``, préfixe ``hncs``, version = ``specVersion`` du modèle complétée à 4 nombres) ;
- ``customizations.xml`` (Workflows, connectionreferences, environmentvariabledefinitions) ;
- ``Workflows/<Nom>-<GUID>.json`` (un fichier par définition technique).

``WorkflowId`` = uuid5(NAMESPACE_URL, "urn:hncs-rd:flow:<IdTechnique>") : déterministe, identique d'un build à l'autre, et
utilisé par les actions « Exécuter un flux enfant » (``workflowReferenceName``).

Usage :
    python flows/build/build_solution.py            # construit le zip
    python flows/build/build_solution.py --check    # valide sans rien écrire (code 1 en cas d'erreur)
    python flows/build/build_solution.py --brouillon  # tous les flux en brouillon (activation par lot à l'import)

Bibliothèque standard uniquement.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import unicodedata
import uuid
import zipfile
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[2]
FLOWS = ROOT / "flows"
SRC = FLOWS / "src"
DIST = FLOWS / "dist"
MODEL = json.loads((ROOT / "provisioning" / "model" / "model.generated.json").read_text(encoding="utf-8"))

SOLUTION = "HNCSRDSuivi"
SOLUTION_LABEL = "HNCS-RD : Suivi R&D (flux Power Automate)"
PUBLISHER = "hncs"
PUBLISHER_LABEL = "HNCS Groupe"
PREFIX = "hncs"
OPTION_PREFIX = 10652
GUID_PREFIX = "urn:hncs-rd:flow:"

CONNECTORS = {
    "hncs_sharepoint": ("shared_sharepointonline", "HNCS-RD SharePoint"),
    "hncs_outlook": ("shared_office365", "HNCS-RD Office 365 Outlook"),
    "hncs_teams": ("shared_teams", "HNCS-RD Microsoft Teams"),
    "hncs_o365users": ("shared_office365users", "HNCS-RD Office 365 Utilisateurs"),
}
# Variables d'environnement (texte), liste de la ligne « Conditionnement » de la spec 8.1.
ENV_VARS = {
    "hncs_SiteUrl": ("URL du site SharePoint HNCS-R&D", "URL du site, sans barre finale (ex. https://contoso.sharepoint.com/sites/HNCS-RD)"),
    "hncs_ServiceAccountEmail": ("Compte de service des flux", "Adresse du compte de service (rôle FLUX, anti-boucle)"),
    "hncs_SupportEmail": ("Support des flux", "Adresse du support (N-99, N-98)"),
    "hncs_BoiteRDEmail": ("Boîte partagée R&D (PA-01b)", "Adresse de la boîte partagée surveillée par PA-01b (= Destinataires.BoiteRD)"),
    "hncs_BoiteRDDossierCandidatures": ("Dossier Candidatures de la boîte R&D (PA-01b)", "Identifiant du dossier « Candidatures » de la boîte partagée"),
}


def workflow_guid(tech_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, GUID_PREFIX + tech_id))


def solution_version() -> str:
    parts = [p for p in str(MODEL["specVersion"]).split(".") if p != ""]
    if not all(p.isdigit() for p in parts):
        raise ValueError(f"specVersion invalide : {MODEL['specVersion']}")
    parts = (parts + ["0", "0", "0", "0"])[:4]
    return ".".join(parts)


def file_name(display: str, guid: str) -> str:
    base = unicodedata.normalize("NFKD", display).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9-]+", "", base.replace(" ", "")) or "Flux"
    return f"{base}-{guid.upper()}.json"


def load(errors):
    manifest = json.loads((FLOWS / "manifest.json").read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in manifest}
    flows = []
    src_ids = sorted(p.parent.name for p in SRC.glob("*/workflow.json"))
    for tid in src_ids:
        if tid not in by_id:
            errors.append(f"{tid} : absent du manifeste")
            continue
        try:
            wf = json.loads((SRC / tid / "workflow.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{tid} : JSON invalide ({e})")
            continue
        flows.append((by_id[tid], wf))
    for tid in sorted(set(by_id) - set(src_ids)):
        errors.append(f"{tid} : présent au manifeste sans workflow.json")
    return flows


def validate(flows, errors):
    guids = {}
    for m, wf in flows:
        g = workflow_guid(m["id"])
        if g in guids:
            errors.append(f"GUID en double : {m['id']} / {guids[g]}")
        guids[g] = m["id"]
    child_guids = {workflow_guid(m["id"]) for m, _ in flows if m["trigger"]["kind"] == "ChildFlow"}
    for m, wf in flows:
        tid = m["id"]
        props = wf.get("properties", {})
        d = props.get("definition", {})
        text = json.dumps(d, ensure_ascii=False)
        for ref in re.findall(r'"workflowReferenceName":\s*"([^"]+)"', text):
            if ref not in child_guids:
                errors.append(f"{tid} : flux enfant inconnu {ref}")
        for env in re.findall(r"parameters\('(hncs_\w+) \(\1\)'\)", text):
            if env not in ENV_VARS:
                errors.append(f"{tid} : variable d'environnement non déclarée {env}")
            if f"{env} ({env})" not in d.get("parameters", {}):
                errors.append(f"{tid} : paramètre {env} utilisé mais non défini dans la définition")
        logical = {CONNECTORS[k][0]: k for k in CONNECTORS}
        for api, ref in props.get("connectionReferences", {}).items():
            ln = ref.get("connection", {}).get("connectionReferenceLogicalName")
            if logical.get(api) != ln:
                errors.append(f"{tid} : référence de connexion {api} → {ln} inattendue")
        for api in set(re.findall(r'"connectionName":\s*"([^"]+)"', text)):
            if api not in props.get("connectionReferences", {}):
                errors.append(f"{tid} : connexion {api} utilisée mais non référencée")


def content_types():
    return ('<?xml version="1.0" encoding="utf-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/octet-stream" />'
            '<Default Extension="json" ContentType="application/octet-stream" /></Types>')


def solution_xml(flows, version):
    roots = "".join(f'<RootComponent type="29" id="{{{workflow_guid(m["id"])}}}" behavior="0" />' for m, _ in flows)
    roots += "".join(f'<RootComponent type="380" schemaName="{n}" behavior="0" />' for n in ENV_VARS)
    return f'''<?xml version="1.0" encoding="utf-8"?>
<ImportExportXml version="9.2.24094.208" SolutionPackageVersion="9.2" languagecode="1036" generatedBy="CrmLive" OrganizationSchemaType="Standard" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <SolutionManifest>
    <UniqueName>{SOLUTION}</UniqueName>
    <LocalizedNames><LocalizedName description={quoteattr(SOLUTION_LABEL)} languagecode="1036" /><LocalizedName description={quoteattr(SOLUTION_LABEL)} languagecode="1033" /></LocalizedNames>
    <Descriptions><Description description={quoteattr("Flux Power Automate du système de suivi R&D HNCS (spec " + MODEL["specVersion"] + ")")} languagecode="1036" /></Descriptions>
    <Version>{version}</Version>
    <Managed>0</Managed>
    <Publisher>
      <UniqueName>{PUBLISHER}</UniqueName>
      <LocalizedNames><LocalizedName description={quoteattr(PUBLISHER_LABEL)} languagecode="1036" /><LocalizedName description={quoteattr(PUBLISHER_LABEL)} languagecode="1033" /></LocalizedNames>
      <Descriptions />
      <EMailAddress xsi:nil="true"></EMailAddress>
      <SupportingWebsiteUrl xsi:nil="true"></SupportingWebsiteUrl>
      <CustomizationPrefix>{PREFIX}</CustomizationPrefix>
      <CustomizationOptionValuePrefix>{OPTION_PREFIX}</CustomizationOptionValuePrefix>
      <Addresses />
    </Publisher>
    <RootComponents>{roots}</RootComponents>
    <MissingDependencies />
  </SolutionManifest>
</ImportExportXml>
'''


def customizations_xml(flows, files, brouillon=False):
    wfs = []
    for m, _ in flows:
        g = workflow_guid(m["id"])
        state, status = ("1", "2") if (m["enabledByDefault"] and not brouillon) else ("0", "1")
        wfs.append(f'''    <Workflow WorkflowId="{{{g}}}" Name={quoteattr(m["displayName"])}>
      <JsonFileName>/Workflows/{escape(files[m["id"]])}</JsonFileName>
      <Type>1</Type>
      <Subprocess>0</Subprocess>
      <Category>5</Category>
      <Mode>0</Mode>
      <Scope>4</Scope>
      <OnDemand>0</OnDemand>
      <TriggerOnCreate>0</TriggerOnCreate>
      <TriggerOnDelete>0</TriggerOnDelete>
      <AsyncAutodelete>0</AsyncAutodelete>
      <SyncWorkflowLogOnFailure>0</SyncWorkflowLogOnFailure>
      <StateCode>{state}</StateCode>
      <StatusCode>{status}</StatusCode>
      <RunAs>1</RunAs>
      <IsTransacted>1</IsTransacted>
      <IntroducedVersion>1.0.0.0</IntroducedVersion>
      <IsCustomizable>1</IsCustomizable>
      <BusinessProcessType>0</BusinessProcessType>
      <IsCustomProcessingStepAllowedForOtherPublishers>1</IsCustomProcessingStepAllowedForOtherPublishers>
      <PrimaryEntity>none</PrimaryEntity>
      <LocalizedNames><LocalizedName languagecode="1036" description={quoteattr(m["displayName"])} /></LocalizedNames>
    </Workflow>''')
    crs = "".join(f'''
    <connectionreference connectionreferencelogicalname="{ln}">
      <connectionreferencedisplayname>{escape(label)}</connectionreferencedisplayname>
      <connectorid>/providers/Microsoft.PowerApps/apis/{api}</connectorid>
      <iscustomizable>1</iscustomizable>
      <statecode>0</statecode>
      <statuscode>1</statuscode>
    </connectionreference>''' for ln, (api, label) in CONNECTORS.items())
    evs = "".join(f'''
    <environmentvariabledefinition schemaname="{n}">
      <defaultvalue></defaultvalue>
      <description default={quoteattr(desc)}><label description={quoteattr(desc)} languagecode="1036" /></description>
      <displayname default={quoteattr(label)}><label description={quoteattr(label)} languagecode="1036" /></displayname>
      <introducedversion>1.0.0.0</introducedversion>
      <iscustomizable>1</iscustomizable>
      <isrequired>1</isrequired>
      <secretstore>0</secretstore>
      <statecode>0</statecode>
      <statuscode>1</statuscode>
      <type>100000000</type>
    </environmentvariabledefinition>''' for n, (label, desc) in ENV_VARS.items())
    return f'''<?xml version="1.0" encoding="utf-8"?>
<ImportExportXml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" OrganizationVersion="9.2.24094.208" OrganizationSchemaType="Standard" CRMServerServiceabilityVersion="9.2.24094.00208">
  <Entities />
  <Roles />
  <Workflows>
{chr(10).join(wfs)}
  </Workflows>
  <FieldSecurityProfiles />
  <Templates />
  <EntityMaps />
  <EntityRelationships />
  <OrganizationSettings />
  <optionsets />
  <CustomControls />
  <EntityDataProviders />
  <connectionreferences>{crs}
  </connectionreferences>
  <environmentvariabledefinitions>{evs}
  </environmentvariabledefinitions>
  <Languages>
    <Language>1036</Language>
  </Languages>
</ImportExportXml>
'''


def build(check: bool, brouillon: bool = False) -> int:
    errors: list = []
    flows = load(errors)
    validate(flows, errors)
    version = solution_version()
    files = {m["id"]: file_name(m["displayName"], workflow_guid(m["id"])) for m, _ in flows}
    if len(set(files.values())) != len(files):
        errors.append("noms de fichiers Workflows en double")
    parts = {"[Content_Types].xml": content_types(), "solution.xml": solution_xml(flows, version),
             "customizations.xml": customizations_xml(flows, files, brouillon)}
    for name, xml in parts.items():
        try:
            minidom.parseString(xml.encode("utf-8"))
            ET.fromstring(xml.encode("utf-8"))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name} : XML invalide ({e})")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, xml in parts.items():
            z.writestr(name, xml.encode("utf-8"))
        for m, wf in flows:
            z.writestr(f"Workflows/{files[m['id']]}", json.dumps(wf, ensure_ascii=False, indent=2).encode("utf-8"))
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
        names = z.namelist()
        bad = z.testzip()
        if bad:
            errors.append(f"archive corrompue : {bad}")
    out = DIST / f"{SOLUTION}_{MODEL['specVersion']}.zip"
    for e in errors:
        print(f"ERREUR {e}")
    enabled = sum(1 for m, _ in flows if m["enabledByDefault"])
    print(f"Solution {SOLUTION} {version} (non gérée) : {len(flows)} flux ({enabled} activés par défaut), "
          f"{len(CONNECTORS)} références de connexion, {len(ENV_VARS)} variables d'environnement, {len(names)} fichiers.")
    if errors:
        print(f"{len(errors)} erreur(s).")
        return 1
    if check:
        print(f"Vérification réussie (aucun fichier écrit ; cible : {out.relative_to(ROOT)}).")
        return 0
    DIST.mkdir(parents=True, exist_ok=True)
    out.write_bytes(buf.getvalue())
    (DIST / "workflows.json").write_text(json.dumps(
        [{"id": m["id"], "displayName": m["displayName"], "workflowId": workflow_guid(m["id"]), "enabledByDefault": m["enabledByDefault"],
          "childFlow": m["trigger"]["kind"] == "ChildFlow", "lot": m["lot"], "code": m["code"], "brouillon": brouillon}
         for m, _ in flows], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Écrit : {out.relative_to(ROOT)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Assemble la solution Power Platform HNCSRDSuivi")
    ap.add_argument("--check", action="store_true", help="valide sans écrire")
    ap.add_argument("--brouillon", action="store_true",
                    help="tous les flux à l'état Brouillon (aucune activation à l'import ; activation par lot avec Import-HNCSRDFlows.ps1)")
    a = ap.parse_args()
    return build(a.check, a.brouillon)


if __name__ == "__main__":
    sys.exit(main())
