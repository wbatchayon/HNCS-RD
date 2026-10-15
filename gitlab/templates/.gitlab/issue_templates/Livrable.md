## Livrable LIV-aaaa-nnnn — titre du livrable

<!-- Une issue « Livrable » par livrable ayant une composante technique ; elle est rattachée au jalon
« LIV-aaaa-nnnn — <titre> » créé par New-GitlabProjetSujet.ps1 (échéance = Echeance du livrable). -->

**Sujet** : {{ID_SUJET}} — {{TITRE_SUJET}}
**Livrable** : LIV-aaaa-nnnn
**Type** : <!-- POC / démonstrateur, plan de stratégie, document technique… (TypeLivrable) -->
**Échéance** : <!-- reprise de SharePoint ; toute modification se fait d'abord dans la liste Livrables -->

### Périmètre technique

<!-- Composants, dépôts, environnements de démonstration (référencés dans RessourcesTechniques). -->

### Découpage

- [ ] …

### Definition of Done (POC et plans de stratégie — cases DoD1 à DoD5 de la liste Livrables)

- [ ] DoD 1 — Fonctionnel et démontrable
- [ ] DoD 2 — Fiche méthodologie rangée (bibliothèque « 04 — Livrables R&D »)
- [ ] DoD 3 — Restitution présentée
- [ ] DoD 4 — Support de communication prêt
- [ ] DoD 5 — Enseignements et limites documentés

> Ces cases sont un aide-mémoire. Seules les cases DoD de l'élément SharePoint font foi ; la
> soumission (« Soumis à revue ») et la validation se font dans SharePoint par les personnes
> désignées, jamais depuis GitLab.

### Liens

- Livrables du sujet (SharePoint) : {{URL_LIVRABLES}}
- Dossier documentaire du sujet : {{URL_DOSSIER_LIVRABLES}}

/label ~"rd::sujet::{{ID_SUJET}}" ~"rd::pole::{{CODE_POLE}}"
/label ~"rd::livrable::LIV-aaaa-nnnn"
/milestone %"LIV-aaaa-nnnn — titre du livrable"
