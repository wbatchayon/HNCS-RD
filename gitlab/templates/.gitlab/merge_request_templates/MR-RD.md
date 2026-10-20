## Merge request R&D

**Sujet** : {{ID_SUJET}}, {{TITRE_SUJET}}
**Livrable** : LIV-aaaa-nnnn <!-- obligatoire : identifiant IdHNCS du livrable (spec section 10.2) -->
**Issues** : Closes #… <!-- ou « Relates to #… » -->

### Résumé des changements

<!-- Quoi et pourquoi, en quelques lignes. -->

### Vérifications

- [ ] Le livrable `LIV-aaaa-nnnn` est cité ci-dessus et l'étiquette `rd::livrable::LIV-aaaa-nnnn` est posée
- [ ] Tests ou démonstration réalisés (préciser comment)
- [ ] Documentation à jour (README du projet, fiche méthodologie si concernée)
- [ ] Aucun secret, mot de passe, jeton, identifiant d'infrastructure ni donnée personnelle dans le code, les journaux ou la description
- [ ] Revue demandée au référent du sujet

> La merge request porte le code. La revue et la validation du **livrable** restent dans SharePoint
> (liste Livrables, réviseur désigné) : fusionner cette MR ne valide pas le livrable.

/label ~"rd::sujet::{{ID_SUJET}}" ~"rd::pole::{{CODE_POLE}}"
/label ~"rd::livrable::LIV-aaaa-nnnn"
