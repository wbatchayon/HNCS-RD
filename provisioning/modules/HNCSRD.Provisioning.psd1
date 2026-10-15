@{
    RootModule           = 'HNCSRD.Provisioning.psm1'
    ModuleVersion        = '1.0.0'
    GUID                 = '6f1c2b8e-4d7a-4c3e-9a51-2e8f0b7d4c19'
    Author               = 'Équipe projet HNCS-RD'
    CompanyName          = 'HNCS Groupe'
    Copyright            = '(c) HNCS Groupe'
    Description          = 'Provisionnement SharePoint du système de suivi R&D HNCS, piloté par provisioning/model/model.generated.json (spec.md). Fonctions pures compatibles Windows PowerShell 5.1 ; fonctions SharePoint : PowerShell 7.4+ et PnP.PowerShell 2.12+.'
    PowerShellVersion    = '5.1'
    CompatiblePSEditions = @('Desktop', 'Core')
    FunctionsToExport    = @(
        'Start-HNCSRDLog', 'Write-HNCSRDLog', 'Set-HNCSRDEtape', 'Add-HNCSRDResultat', 'Get-HNCSRDResultats', 'Get-HNCSRDResume',
        'Set-HNCSRDSimulation', 'Test-HNCSRDSimulation',
        'Get-HNCSRDModel', 'Get-HNCSRDConfig', 'Get-HNCSRDObject', 'Get-HNCSRDObjects', 'Test-HNCSRDLookupType', 'Get-HNCSRDColumns',
        'Get-HNCSRDColumnTypes', 'Get-HNCSRDListUrl', 'Get-HNCSRDGroupName', 'Get-HNCSRDOwnerGroupCode', 'Get-HNCSRDEnumValues',
        'Resolve-HNCSRDMarqueurs', 'Get-HNCSRDPropriete', 'ConvertTo-HNCSRDXmlText', 'Format-HNCSRDNombre', 'ConvertTo-HNCSRDBoolean',
        'Get-HNCSRDDefaultValue', 'ConvertTo-HNCSRDFieldXml', 'Compare-HNCSRDFieldSchema', 'ConvertTo-HNCSRDCaml', 'Format-HNCSRDCamlNormalise',
        'ConvertTo-HNCSRDValidationFormula', 'Get-HNCSRDValidationColumns', 'Get-HNCSRDVersioningSpec', 'Get-HNCSRDAttributionsAttendues',
        'Get-HNCSRDAttributionsSite', 'Get-HNCSRDNavigationPlan', 'Get-HNCSRDTimeZoneId',
        'Assert-HNCSRDPrerequis', 'Get-HNCSRDTenantDomain', 'Connect-HNCSRD',
        'Get-HNCSRDList', 'Get-HNCSRDChamps', 'Get-HNCSRDRoleDefinitionName', 'Get-HNCSRDPermissionKinds', 'Get-HNCSRDEtatAttributions',
        'Compare-HNCSRDAttributions', 'Get-HNCSRDItemsParCle', 'Resolve-HNCSRDLookupId', 'ConvertTo-HNCSRDValeurChamp',
        'Get-HNCSRDTransitionValeurs', 'Compare-HNCSRDTransitionItem',
        'Ensure-HNCSRDSite', 'Ensure-HNCSRDPermissionLevels', 'Ensure-HNCSRDGroups', 'Set-HNCSRDVersioning', 'Ensure-HNCSRDList',
        'Ensure-HNCSRDTitleColumn', 'Ensure-HNCSRDColumn', 'Set-HNCSRDListValidation', 'Ensure-HNCSRDView', 'Sync-HNCSRDAttributions',
        'Set-HNCSRDListPermissions', 'Set-HNCSRDSitePermissions', 'Get-HNCSRDGroupesParDefaut', 'Clear-HNCSRDGroupesParDefaut', 'Ensure-HNCSRDParameters', 'Ensure-HNCSRDSeeds', 'Sync-HNCSRDTransitions',
        'Ensure-HNCSRDNavigation', 'Ensure-HNCSRDTeam'
    )
    CmdletsToExport      = @()
    VariablesToExport    = @()
    AliasesToExport      = @()
    PrivateData          = @{
        PSData = @{
            Tags = @('SharePoint', 'PnP', 'HNCS', 'Provisioning')
        }
    }
}
