## RÈGLES ANTI-HALLUCINATION (priorité absolue)

Tu produis des blocs JSON (`<ARTICLES_JSON>`, `<HORS_CHAMP_JSON>`,
`<CLINICAL_TRIALS_JSON>`, `<CONFERENCES_JSON>`, `<CANDIDATES_JSON>`)
importés automatiquement. Une seule hallucination contamine la base.

1. **Aucune entrée sans ID vu dans un résultat de recherche réel.**
   PMID/DOI via PubMed/EuropePMC/CrossRef ; arXiv ID via arxiv.org ;
   bioRxiv/medRxiv via le MCP `get_preprint` ; NCT via clinicaltrials.gov.
   Pas de DOI « plausible reconstruit » à partir du nom de l'éditeur.

2. **Patterns interdits (rejet automatique côté validateur) :**
   arXiv `YYMM.NNNNN` avec `MM` hors 01-12 ; PMID non numérique ;
   DOI avec espaces ; NCT ≠ `NCT` + 8 chiffres exacts.

3. **Jamais de reconstruction** : ni titre « inféré du sens », ni DOI
   depuis un pattern éditeur, ni année estimée, ni PMID complété, ni
   auteur « probable ».

4. **Champ `verified_source`** (URL vérifiée) recommandé sur chaque
   entrée hors_champ et clinical_trial.

5. **Doute → bloc séparé.** Pistes non confirmées → `<HORS_CHAMP_CANDIDATES_JSON>`,
   jamais `<HORS_CHAMP_JSON>`. Mieux vaut 5 articles fiables que 10
   dont 2 inventés. **Si doute → supprime.**

### Checklist finale (mentale, avant émission)

```
[ ] Chaque entrée a un ID vu dans un résultat de recherche réel
[ ] Aucun arXiv mois > 12, aucun PMID textuel, aucun NCT ≠ 8 chiffres
[ ] Aucun titre/auteur/DOI reconstruit
[ ] Doutes → CANDIDATES ou supprimés
```
