# Système de veille hémato-immuno-oncologie

Alexis est médecin chercheur AHU à Henri Mondor (Créteil), spécialisé en biopsie liquide et lymphomes B.

## À FAIRE À CHAQUE OUVERTURE DE SESSION

Dès que cette session démarre avec ce dossier :

**1. Vérifier la fraîcheur de la base.**
   - Lire `outils/weekly_search_done.txt` pour récupérer la date du dernier import.
   - Si > 10 jours sans import : alerter Alexis ("⚠️ Aucun import depuis N jours — la veille planifiée a peut-être échoué. Vérifier les tâches `hemato-weekly-search` et `hemato-weekly-summary`.").
   - Si > 35 jours sans import hemato-clinical-trials : alerter aussi.

**2. Vérifier s'il y a des digests à importer.**
   - Appeler `mcp__session_info__list_sessions` (limit 10).
   - Chercher les sessions "Hemato weekly summary" ou "hemato-clinical-trials" plus récentes que le dernier import.
   - S'il y en a, proposer : "J'ai trouvé N digest(s) non importé(s). Je les importe ?"
   - Si un transcript de hemato-clinical-trials contient `<CONFERENCES_JSON>` ou `<CLINICAL_TRIALS_JSON>`, extraire dans `output/conferences.json` / `output/clinical_trials.json`.

**3. Tirage anti-drift hebdomadaire (optionnel).**
   - Si la dernière entrée du journal `outils/veille_log.txt` mentionnant "sample_for_verification" date de plus de 7 jours, proposer à Alexis : "Je tire 5% des articles pour vérification PubMed ?"
   - Lancer `python3 outils/sample_for_verification.py .` puis vérifier les PMID via PubMed MCP.

## Architecture

Stockage central : `output/articles_db.json` (JSON pur, pas d'Excel).

Des tâches planifiées cherchent des articles automatiquement. Elles n'ont PAS accès à ce dossier. Elles produisent un résumé avec un bloc `<ARTICLES_JSON>[...]</ARTICLES_JSON>` dans leur transcript.

Quand Alexis ouvre une session Cowork, il peut dire **"importe la veille"**. Voici quoi faire :

## Import de la veille

Workflow standard, 11 étapes. Ne pas sauter d'étape sauf indication explicite.

```bash
VEILLE_DIR=$(ls -d /sessions/*/mnt/Veille 2>/dev/null | head -1)

# === ÉTAPE 1 — Récupérer les digests ===
# Utiliser mcp__session_info__list_sessions puis mcp__session_info__read_transcript
# Chercher les sessions "Hemato weekly summary" ou "Hemato clinical trials"
# Extraire le bloc <ARTICLES_JSON>[...]</ARTICLES_JSON> du transcript
# Sauvegarder dans /tmp/articles_import.json

# === ÉTAPE 2 — Importer dans la base JSON ===
python3 $VEILLE_DIR/outils/update_db.py $VEILLE_DIR /tmp/articles_import.json

# === ÉTAPE 3 — Valider le schéma (OBLIGATOIRE avant dashboard) ===
python3 $VEILLE_DIR/outils/validate_schema.py $VEILLE_DIR
# Si erreurs → corriger AVANT de continuer

# === ÉTAPE 4 — Extraire les blocs annexes du transcript ===
# Si transcript hemato-weekly-summary :
#   <HORS_CHAMP_JSON>   → output/hors_champ.json
#   <DIRECTIONS_JSON>   → output/directions.json
# Si transcript hemato-clinical-trials :
#   <CONFERENCES_JSON>      → output/conferences.json
#   <CLINICAL_TRIALS_JSON>  → output/clinical_trials.json

# === ÉTAPE 5 — Vérification ANTI-HALLUCINATION des essais cliniques ===
# (uniquement si nouveaux essais à l'étape 4)
# Pour chaque essai dans clinical_trials.json :
#   - Naviguer vers https://clinicaltrials.gov/study/{nct_id} via Chrome MCP
#   - Vérifier NCT, titre, phase, statut
#   - Corriger / supprimer les essais non vérifiables
# OBLIGATOIRE car la tâche planifiée n'a pas accès direct à l'API ClinicalTrials.gov

# === ÉTAPE 6 — Vérification ANTI-HALLUCINATION offline (format) ===
# Le sandbox Python n'a PAS accès à arxiv.org / doi.org → ces scripts vérifient
# uniquement le format. La VRAIE vérification en ligne se fait via les MCP Cowork
# (cf. section "Vérification en ligne" ci-dessous).
python3 $VEILLE_DIR/outils/verify_hors_champ.py $VEILLE_DIR
python3 $VEILLE_DIR/outils/verify_articles.py $VEILLE_DIR

# === ÉTAPE 7 — Analyser les feedbacks (si fichiers présents) ===
python3 $VEILLE_DIR/outils/analyze_feedback.py $VEILLE_DIR
# Si le résultat contient un prompt_paragraph non vide :
#   → Lire le prompt actuel du digest via mcp__scheduled-tasks__list_scheduled_tasks
#   → Ajouter/remplacer la section "Préférences utilisateur" dans le prompt
#   → Mettre à jour via mcp__scheduled-tasks__update_scheduled_task

# === ÉTAPE 8 — Audit hebdomadaire de la base (OBLIGATOIRE) ===
python3 $VEILLE_DIR/outils/audit_db.py $VEILLE_DIR
# Vérifie : DOIs manquants/doublons, PMIDs, scores, catégories, dates, titres dupliqués
# Inclut des regex-traps anti-hallucination (DOI/arXiv malformés)
# Rapport détaillé dans output/audit_report.json
# Si erreurs → corriger AVANT de considérer l'import terminé

# === ÉTAPE 9 — Régénérer le dashboard ===
python3 $VEILLE_DIR/outils/generate_dashboard.py $VEILLE_DIR

# === ÉTAPE 10 — Consolider les feedbacks (mensuel uniquement) ===
# Uniquement à l'occasion d'un import hemato-clinical-trials
python3 $VEILLE_DIR/outils/consolidate_feedback.py $VEILLE_DIR

# === ÉTAPE 11 — Mettre à jour les citations (mensuel, via Chrome MCP) ===
# Le proxy sandbox bloque toutes les APIs de citations, MAIS Chrome MCP passe
# par le navigateur d'Alexis (réseau maison) et atteint OpenAlex.
# Prérequis : domaine api.openalex.org ajouté à l'allowlist de l'extension
# Claude in Chrome.
#
# Workflow en 3 phases :
#
#   Phase 1 (Python) : préparer les batches + générer un snippet JS
python3 $VEILLE_DIR/outils/prepare_citations_update.py $VEILLE_DIR
#     → /tmp/citations_fetch.js + /tmp/citations_input.json
#     → option : --max-age-days N (skip articles rafraîchis < N jours, défaut 30)
#
#   Phase 2 (Chrome MCP) : Cowork exécute le JS via javascript_tool
#     1. Ouvrir un onglet api.openalex.org dans Chrome (ou tout onglet allowlisté)
#     2. Lire /tmp/citations_fetch.js et l'exécuter :
#          mcp__Claude_in_Chrome__javascript_tool(
#              action='javascript_exec', tabId=<id>, code=<contenu du .js>)
#     3. Le résultat ressort tronqué (>100 items ou >1KB). Stratégie :
#          a. Stocker dans window.__citations_result
#          b. Aplatir :
#             window.__flat = Object.entries(window.__citations_result.citations)
#                 .map(([d,v]) => ({d, c:v.cited_by_count,
#                                    o:(v.openalex_id||'').replace(/^https:\/\/openalex\.org\//,'')}));
#          c. Extraire par chunks de 90 :
#             window.__flat.slice(N, N+90).map(e => [e.d, e.c, e.o])
#     4. Réassembler côté Python en /tmp/citations_results.json au format :
#          {"backend":"openalex","fetched_at":"YYYY-MM-DD",
#           "citations":{doi:{cited_by_count,openalex_id,title}, ...}}
#
#   Phase 3 (Python) : merge dans articles_db.json
python3 $VEILLE_DIR/outils/apply_citations_update.py $VEILLE_DIR
#     → ajoute citation_count, citation_count_updated, citation_source, openalex_id
#     → --dry-run pour voir le plan sans écrire
```

## Vérification en ligne via MCP Cowork (OBLIGATOIRE après import)

Les scripts Python ne peuvent pas atteindre arxiv.org/doi.org depuis le sandbox.
**Cowork doit faire la vérification en ligne lui-même** via les MCP qui ont
accès au réseau de la machine de l'utilisateur :

### A. Vérification des PMID des nouveaux articles
Pour chaque article ajouté à la dernière semaine ISO, appeler **PubMed MCP** :
```
mcp__c1938703-7f1d-4b20-a7f7-c940a37a18fc__get_article_metadata(pmids=[...])
```
- Si le PMID existe et que le titre matche → article validé
- Si le PMID renvoie 404 ou un titre incohérent → quarantaine
- Vérifier en lots de 5-10 PMIDs max
- Pour les articles SANS PMID mais avec DOI : `convert_article_ids` pour
  retrouver le PMID, puis re-vérification

### B. Vérification des hors_champ (arXiv)
Pour chaque entrée hors_champ avec un arxiv ID, utiliser **Chrome MCP** :
```
mcp__Claude_in_Chrome__navigate(url="https://arxiv.org/abs/{arxiv_id}")
mcp__Claude_in_Chrome__get_page_text()
```
- Vérifier que le titre de la page contient le titre attendu
- Si la page renvoie une erreur 404 ou un titre différent → quarantaine
- ⚠️ Cette étape nécessite l'extension Claude in Chrome installée

### C. Vérification des hors_champ (bioRxiv/medRxiv)
Pour les preprints biomédicaux, utiliser **bioRxiv MCP** :
```
mcp__fb142a47-e47a-44bf-b310-4c67450f4358__get_preprint(doi="10.1101/...")
```

### D. Mise à jour des fichiers
Après vérification, pour chaque entrée :
- Validée → ajouter `verified_at: "YYYY-MM-DD"` et `verified_source: "<URL>"`
- Échec → déplacer dans `output/hors_champ_quarantine.json` ou
  `output/articles_quarantine.json` selon le cas, avec `quarantine_reason`

### E. Régénérer le dashboard
```bash
python3 $VEILLE_DIR/outils/generate_dashboard.py $VEILLE_DIR
```

La déduplication se fait par DOI ET par titre normalisé — relancer l'import plusieurs fois est sans risque.
Les transitions preprint→publié sont détectées automatiquement (mise à jour de la ligne existante).

## Articles liés (optionnel)

Si Alexis demande **"articles liés"** ou **"related articles"** pour un article du dashboard :
1. Récupérer le PMID de l'article
2. Appeler `mcp__c1938703-7f1d-4b20-a7f7-c940a37a18fc__find_related_articles` avec ce PMID
3. Filtrer les résultats par IF ≥ 5
4. Présenter les 5 meilleurs à Alexis avec titre, journal, IF, lien DOI
Le script `update_db.py` accepte les clés courtes (digest) ET les clés longues (format canonique) — pas de transformation nécessaire.

## Boucle de feedback

Le système apprend des préférences d'Alexis :
1. Alexis note les articles dans le dashboard (Utile / Bof / Ignoré)
2. Il exporte le feedback (bouton "Exporter feedback" → fichier `feedback_SEMAINE.json` à sauver dans `output/`)
3. À chaque import, `analyze_feedback.py` analyse les patterns et génère des ajustements de scoring
4. Ces ajustements sont injectés dans le prompt du digest sous forme de bonus/malus (+1/-1)
5. Le digest suivant tiendra compte des préférences

Le feedback est persisté via localStorage dans le navigateur ET rechargé depuis les fichiers `feedback_*.json` à chaque régénération du dashboard.
Les fichiers `feedback_*.json` dans `output/` sont cumulatifs et servent à l'analyse.
Le fichier `output/preferences.json` contient les préférences apprises.

## Fichiers

- `output/articles_db.json` — Base d'articles JSON (stockage central, remplace l'Excel)
- `output/index.html` — Dashboard interactif (feedback pré-chargé + localStorage)
- `output/conferences.json` — Conférences hémato (affiché dans le dashboard, mis à jour par hemato-clinical-trials)
- `output/clinical_trials.json` — Essais cliniques lymphomes B en cours (affiché dans le dashboard, mis à jour par hemato-clinical-trials)
- `output/hors_champ.json` — Articles hors champ avec ponts méthodologiques
- `output/directions.json` — Pistes de recherche suggérées
- `output/preferences.json` — Préférences apprises + calibration scoring (régression OLS)
- `outils/categories.json` — **Source unique des catégories** (label, rang, description). Modifier UNIQUEMENT ici.
- `outils/update_db.py` — Import JSON → base articles (dédup DOI+PMID+titre, transitions preprint→publié, normalise date_pub)
- `outils/generate_dashboard.py` — Charge les JSON, lit le template, remplace les placeholders, écrit le dashboard
- `outils/dashboard_template.html` — Template HTML/CSS/JS du dashboard (placeholders %%DATA%% etc.)
- `outils/analyze_feedback.py` — Feedback → Préférences → Calibration scoring par régression OLS
- `outils/consolidate_feedback.py` — Consolidation mensuelle des feedback_*.json (garde n-1, supprime les fusionnés)
- `outils/prepare_citations_update.py` — Phase 1 : lit articles_db.json, génère `/tmp/citations_fetch.js` (batches OpenAlex de 50 DOIs) et `/tmp/citations_input.json`
- `outils/apply_citations_update.py` — Phase 3 : lit `/tmp/citations_results.json` et merge `citation_count` + `citation_count_updated` + `citation_source` + `openalex_id` dans articles_db.json
- `outils/verify_hors_champ.py` — Vérification format hors_champ (sandbox, sans réseau)
- `outils/verify_articles.py` — Vérification format articles (sandbox, sans réseau)
- `outils/audit_db.py` — Audit hebdomadaire (doublons, champs manquants, regex-traps anti-hallucination)
- `outils/validate_schema.py` — Validation automatique des schémas et références croisées
- `outils/merge_pmid_duplicates.py` — Script one-shot : fusionne les articles partageant le même PMID
- `outils/auteurs_cles.txt` — Liste des auteurs à surveiller (highlight dans le dashboard)
- `outils/SCHEMA.md` — **Contrat de schéma** : noms de variables JS, clés JSON, contraintes de cohérence
- `outils/prompts/` — Prompts versionnés des tâches planifiées (source de vérité, propagés via sync_prompts.py)
- `output/audit_report.json` — Dernier rapport d'audit

## ⚠️ RÈGLE ANTI-CASSE DASHBOARD

Quand tu modifies `generate_dashboard.py` ou que tu écris des fichiers JSON :
1. **LIRE `outils/SCHEMA.md` d'abord** — il contient les noms exacts des variables JS et des clés JSON
2. **Les articles sont dans `DATA`** (pas `ARTICLES`)
3. **Les essais sont dans `CLINICAL_TRIALS`** (pas `TRIALS`)
4. **Le pont méthodologique est `pont_methodologique`** (pas `pont`)
5. **Exécuter `python3 outils/validate_schema.py .`** après toute modification
6. **Les `id` HTML doivent être sanitizés** (pas d'espaces, pas de `:`)

## Format JSON des articles

Format canonique (clés longues) :
```json
{"semaine":"2026-S13", "titre":"...", "premier_auteur":"...", "senior_auteur":"...",
 "journal":"...", "doi":"10.xxx", "categorie":"ctDNA — Lymphomes",
 "tag":"ctDNA, MRD", "resume":"...", "critique":"...", "metadata":"OK",
 "preprint":"Publié", "affiliations_fr":"Non", "if_value":45.3, "score":9,
 "date_pub":"2026-03-25", "pmid":"39012345", "pays":"US"}
```

Format court (accepté aussi par update_db.py) :
```json
{"semaine":"2026-S13", "titre":"...", "auteur":"...", "senior":"...",
 "journal":"...", "doi":"10.xxx", "categorie":"ctDNA — Lymphomes",
 "tags":"ctDNA, MRD", "resume":"...", "critique":"...", "preprint":"Publié", "affFR":"Non",
 "if_val":45.3, "score":9, "date_pub":"2026-03-25", "pmid":"39012345", "pays":"US"}
```

Catégories : définies dans `outils/categories.json` (source unique). Actuellement : `Hémato générale`, `Lymphomes`, `ctDNA — Lymphomes`, `ctDNA — Méthodo`, `Immuno + ctDNA/Lymphome`, `IA + Hémato`, `Preprint`. Pour ajouter/modifier une catégorie : éditer `categories.json`, puis vérifier que `update_db.py`, `audit_db.py` et `validate_schema.py` la prennent en compte automatiquement.

## Filtrage par Impact Factor

Le filtrage n'utilise PAS une liste SIGAPS fixe mais des seuils d'IF :
- **IF ≥ 10** → Rang A (inclus pour toutes catégories)
- **5 ≤ IF < 10** → Rang B (inclus pour C1-C3, exclu pour C4)
- **IF < 5** → Exclu

## Tâches planifiées

### Actives
- **hemato-weekly-search** (lundi 8h) — Recherche PubMed/bioRxiv/web, collecte métadonnées, vérification PMID. Produit `<CANDIDATES_JSON>` compact (pas de résumés). **Déclenche automatiquement hemato-weekly-summary 5 min après sa fin.**
- **hemato-weekly-summary** (déclenché par search) — Lit le transcript de hemato-weekly-search, écrit résumés/critiques/scores, produit `<ARTICLES_JSON>`, `<HORS_CHAMP_JSON>`, `<DIRECTIONS_JSON>`. Pas de cron propre — réarmé par hemato-weekly-search via `fireAt`.
- **hemato-clinical-trials** (1er du mois 10h) — Recherche essais cliniques lymphomes B + conférences hémato + abstracts conférences récentes + citations Semantic Scholar. Produit `<CLINICAL_TRIALS_JSON>`, `<CONFERENCES_JSON>`, et éventuellement `<ARTICLES_JSON>`.

### Désactivées
- **hemato-weekly-digest** — DÉSACTIVÉ (remplacé par hemato-weekly-search + hemato-weekly-summary)
- **hemato-monthly-report** — DÉSACTIVÉ (tendances intégrées directement dans le dashboard)
- **ctdna-daily-alert** — DÉSACTIVÉ (redondant avec le weekly search)
- **hemato-conference-alert** — DÉSACTIVÉ (fusionné dans hemato-clinical-trials)
- **hemato-retro-*** — ARCHIVÉ (14 tâches one-shot rétro, exécutées 28-29/03/2026, base constituée)

## TODO — Mises à jour de prompts en attente

Les prompts des tâches planifiées ne sont pas lisibles via l'API list_scheduled_tasks (seules les métadonnées sont retournées).
Pour les modifier, il faut utiliser `update_scheduled_task` avec le champ `prompt` complet.

### hemato-weekly-search — Ajouter recherche cross-disciplinaire
Le search actuel ne cherche que sur PubMed/bioRxiv (articles médicaux). Il faut ajouter une étape :
- Chercher sur arXiv, SSRN, IEEE les articles récents en **statistique, IA/ML, physique, ingénierie**
  avec des mots-clés méthodologiques transférables : "changepoint detection", "Bayesian adaptive design",
  "graph neural network", "optimal transport", "causal inference", "time series anomaly"
- Croiser avec les thématiques biopsie liquide / ctDNA / MRD / lymphome
- Ajouter les candidats dans un bloc `<HORS_CHAMP_CANDIDATES_JSON>` pour que hemato-weekly-summary les évalue

### hemato-clinical-trials — Améliorer les deadlines conférences
Le prompt doit inclure une base de connaissances des patterns de deadlines :
- ASH : abstracts ~début août (4 mois avant le meeting en décembre)
- ESMO : abstracts ~mi-mai (5 mois avant)
- ICML (lymphoma) : abstracts ~4 mois avant
- EHA : abstracts ~mars (3 mois avant)
- ASCO : abstracts ~fin janvier (4 mois avant)
- SFH : abstracts ~début janvier
- Instruction : "Pour chaque conférence, chercher activement la deadline sur le site officiel.
  Si introuvable, utiliser le pattern habituel (deadline = date_debut - 4 mois). Ne JAMAIS laisser null
  pour ASH, ESMO, EHA, ASCO, ICML."

## Robustesse des tâches planifiées

- Étape 0 obligatoire : ToolSearch pour découvrir les MCP tools (les IDs changent entre sessions)
- Metadata PubMed : batches de 5 PMIDs max
- Ne PAS utiliser WebFetch sur les sites éditeurs (ascopubs.org, ashpublications.org, nature.com → bloqués)
- Ignorer les timeouts bioRxiv/Semantic Scholar et continuer
- notifyOnCompletion: true sur chaque tâche
- **APIs de citations** : bloquées depuis le sandbox Python (toutes, testées 2026-04), mais accessibles via Chrome MCP (réseau du navigateur d'Alexis). Workflow mensuel via `outils/prepare_citations_update.py` + javascript_tool OpenAlex + `outils/apply_citations_update.py`. Domaine `api.openalex.org` doit être dans l'allowlist de l'extension Claude in Chrome.

## Commandes utiles

- **"importe la veille"** → import des articles récents dans la base JSON + dashboard
- **"génère le dashboard"** → `python3 outils/generate_dashboard.py .`
- **"montre le dashboard"** → lien vers `output/index.html`
- **"articles liés"** pour un article → find_related_articles via PMID
