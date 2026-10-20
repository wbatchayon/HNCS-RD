## Tâche R&D

**Sujet** : {{ID_SUJET}}, {{TITRE_SUJET}}
**Livrable concerné** : LIV-aaaa-nnnn <!-- obligatoire : identifiant IdHNCS du livrable (spec section 10.2) -->

### Objectif

<!-- Ce que la tâche doit produire, en une ou deux phrases. -->

### Travail à réaliser

- [ ] …
- [ ] …

### Critères d'acceptation

- [ ] …
- [ ] Documentation mise à jour (README, fiche méthodologie si concernée)

### Liens

- Fiche du sujet (SharePoint) : {{URL_SUJET}}
- Livrables du sujet (SharePoint) : {{URL_LIVRABLES}}

<!--
Règles :
- aucune donnée personnelle, aucun identifiant, mot de passe ni jeton dans une issue ;
- remplacer LIV-aaaa-nnnn ci-dessus et dans la commande /label ci-dessous ;
- la validation d'un livrable se fait dans SharePoint (liste Livrables), jamais dans GitLab.
-->

/label ~"rd::sujet::{{ID_SUJET}}" ~"rd::pole::{{CODE_POLE}}"
/label ~"rd::livrable::LIV-aaaa-nnnn"
