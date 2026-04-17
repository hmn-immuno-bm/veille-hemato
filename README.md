# Veille Hémato-Immuno-Oncologie

Système automatisé de veille bibliographique en hématologie, immuno-oncologie et biopsie liquide.

## Architecture

- **Base de données** : `output/articles_db.json` — stockage centralisé des articles (JSON pur)
- **Dashboard** : `output/index.html` — interface interactive avec feedback et filtrage
- **Tâches planifiées** : recherche automatique PubMed/bioRxiv/arXiv hebdomadaire
- **Import** : extraction des digests depuis les transcripts de sessions Cowork

## Outils

| Script | Rôle |
|--------|------|
| `update_db.py` | Import JSON → base articles (dédup DOI+PMID+titre) |
| `generate_dashboard.py` | Génération du dashboard HTML interactif |
| `validate_schema.py` | Validation du schéma et cohérence inter-fichiers |
| `audit_db.py` | Audit hebdomadaire (doublons, champs manquants, regex-traps) |
| `prepare_citations_update.py` | Phase 1 citations : génère un snippet JS (OpenAlex/CrossRef) |
| `apply_citations_update.py` | Phase 3 citations : merge les résultats dans la base |
| `analyze_feedback.py` | Analyse les feedbacks utilisateur → ajustement scoring |
| `verify_articles.py` | Vérification format articles (offline) |
| `verify_hors_champ.py` | Vérification format hors-champ (offline) |
| `sample_for_verification.py` | Tirage aléatoire anti-drift pour vérification PubMed |

## Workflow de citations

Le proxy sandbox bloque les APIs de citations. Le workflow passe par Chrome MCP :

1. **Phase 1** (Python) : `prepare_citations_update.py` génère un snippet JS
2. **Phase 2** (Chrome MCP) : exécution du JS via `javascript_tool` → OpenAlex/CrossRef
3. **Phase 3** (Python) : `apply_citations_update.py` merge les résultats

Backends : OpenAlex (batch de 50 DOIs, défaut) et CrossRef (fallback, 1 DOI/requête).

## Stack

- Python 3 (scripts d'import, validation, audit)
- HTML/CSS/JS (dashboard interactif)
- Cowork + Claude in Chrome MCP (automatisation)
- PubMed MCP (vérification PMID, articles liés)

## Auteur

Alexis Claudel — AHU, Service d'hématologie, Hôpital Henri Mondor (Créteil)
