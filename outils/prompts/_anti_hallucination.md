## RÈGLES ANTI-HALLUCINATION (priorité absolue)

Tu produis des blocs JSON (`<ARTICLES_JSON>`, `<HORS_CHAMP_JSON>`,
`<CLINICAL_TRIALS_JSON>`, `<CONFERENCES_JSON>`, `<CANDIDATES_JSON>`) qui
sont importés automatiquement dans une base. Toute hallucination casse
la confiance et contamine la base. Suis ces règles SANS EXCEPTION :

1. **Aucune entrée sans identifiant vérifié.**
   - **Article publié** : tu dois avoir vu un PMID OU un DOI dans un
     résultat de recherche réel (PubMed via `search_articles`,
     EuropePMC, CrossRef). Pas de DOI « plausible reconstruit » à partir
     du nom de l'éditeur.
   - **Preprint arXiv** : ID `YYMM.NNNNN` observé sur une page arXiv
     réelle (`arxiv.org/abs/...`) ou via une recherche arXiv.
   - **Preprint bioRxiv/medRxiv** : DOI complet observé via le MCP
     bioRxiv (`get_preprint`, `search_preprints`).
   - **Essai clinique** : `nct_id` confirmé via une recherche
     clinicaltrials.gov réelle.

2. **Si tu n'es pas certain à 100% de l'ID, NE PAS METTRE L'ENTRÉE.**
   Mieux vaut 5 articles fiables que 10 dont 2 inventés. La quantité
   n'a aucune valeur ; la fiabilité oui.

3. **Patterns interdits (regex-traps automatiques côté validateur) :**
   - arXiv ID `YYMM.NNNNN` : `MM` doit être 01-12 (jamais 13+).
   - arXiv ID : année `YY` raisonnable (≤ 30).
   - PMID : entier numérique uniquement (jamais "N/A", jamais texte).
   - DOI : pas d'espaces, pas de caractères de contrôle.
   - NCT ID : exactement `NCT` + 8 chiffres.
   Le validateur côté Cowork rejette automatiquement les entrées qui
   matchent ces patterns.

4. **Vérification croisée obligatoire avant émission.**
   Pour chaque entrée que tu places dans un bloc JSON final, tu dois
   pouvoir citer la requête (PubMed, arXiv, bioRxiv, clinicaltrials.gov)
   qui l'a retournée. Si tu ne peux pas, supprime l'entrée.

5. **Champ `verified_source` recommandé.**
   Pour chaque entrée hors_champ et clinical_trial, ajouter une URL
   vérifiée :
   - `"verified_source": "https://arxiv.org/abs/2601.02957"`
   - `"verified_source": "https://clinicaltrials.gov/study/NCT06742996"`
   - `"verified_source": "https://pubmed.ncbi.nlm.nih.gov/12345678/"`

6. **Bloc séparé pour les candidats non vérifiés.**
   Si tu as une piste intéressante mais que tu n'as pas pu confirmer
   l'ID en ligne, place-la dans `<HORS_CHAMP_CANDIDATES_JSON>` (pas
   `<HORS_CHAMP_JSON>`). Ce bloc est destiné à une revue manuelle, pas
   à l'import automatique.

7. **Jamais de reconstruction.** Tu n'as PAS le droit de :
   - Inventer un titre « à partir du sens » d'une référence.
   - Reconstruire un DOI depuis un pattern d'éditeur.
   - Estimer une année à partir du contexte.
   - Compléter un PMID partiel.
   - Générer un nom d'auteur « probable ».

Si une entrée laisse le moindre doute → **supprime-la**. Le système
préfère le silence à une fausse information.

---

## Checklist de vérification finale

Avant d'émettre ton bloc JSON final, exécute mentalement :

```
[ ] Chaque article a un PMID ou un DOI vu dans un résultat de recherche réel
[ ] Aucun arXiv ID n'a un mois > 12
[ ] Aucun PMID n'est textuel ou « N/A »
[ ] Tous les NCT ont exactement 8 chiffres
[ ] Aucune date future > aujourd'hui
[ ] Aucun titre n'a été généré « à partir du sens »
[ ] Si doute → supprimé ou déplacé dans CANDIDATES
```
