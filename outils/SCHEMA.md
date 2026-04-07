# Contrat de schéma — Veille hémato-oncologie

Ce fichier documente les schémas exacts des fichiers JSON et les noms de variables JS du dashboard.
**Toute modification doit mettre à jour ce fichier.**

## Variables JS dans generate_dashboard.py

| Placeholder         | Variable JS       | Source fichier               |
|---------------------|-------------------|------------------------------|
| `%%DATA%%`          | `DATA`            | `output/articles_db.json`    |
| `%%HORS_CHAMP%%`    | `HORS_CHAMP`      | `output/hors_champ.json`     |
| `%%DIRECTIONS%%`    | `DIRECTIONS`      | `output/directions.json`     |
| `%%CONFERENCES%%`   | `CONFERENCES`     | `output/conferences.json`    |
| `%%CLINICAL_TRIALS%%`| `CLINICAL_TRIALS` | `output/clinical_trials.json`|
| `%%KEY_AUTHORS%%`   | `KEY_AUTHORS`     | `outils/auteurs_cles.txt`    |
| `%%FEEDBACK%%`      | `SAVED_FEEDBACK`  | `output/feedback_*.json`     |

⚠️ **NE PAS utiliser** `ARTICLES` (c'est `DATA`) ni `TRIALS` (c'est `CLINICAL_TRIALS`).

## Schéma : articles_db.json (clés longues / canoniques)

```json
{
  "semaine": "2026-S13",          // Format YYYY-SNN ou YYYY-HN ou YYYY-TN
  "titre": "string (requis)",
  "premier_auteur": "string",
  "senior_auteur": "string",
  "journal": "string",
  "doi": "10.xxxx/xxxx",
  "categorie": "enum (voir ci-dessous)",
  "tag": "tag1, tag2, tag3",
  "resume": "string (français, 300-600 chars)",
  "critique": "string (français, 200-400 chars)",
  "metadata": "OK",
  "preprint": "Publié | Preprint",
  "affiliations_fr": "Oui | Non",
  "if_value": 45.3,
  "score": 9,
  "date_pub": "YYYY-MM-DD",
  "pmid": "string",
  "pays": "XX (code ISO 2 lettres)"
}
```

Catégories valides : `Hémato générale`, `Lymphomes`, `ctDNA — Lymphomes`, `ctDNA — Méthodo`, `Immuno + ctDNA/Lymphome`, `IA + Hémato`, `Preprint`

## Schéma : hors_champ.json

```json
{
  "semaine": "2026-S13",
  "domaine": "string (discipline NON médicale)",
  "titre": "string (requis, sert d'identifiant pour les liens)",
  "journal": "string",
  "doi": "string (souvent vide pour preprints)",
  "if_value": 0,
  "pont_methodologique": "string (3-5 phrases, requis)",
  "pertinence": 5,
  "reference_henri_mondor": "string (piste concrète)"
}
```

⚠️ Le champ s'appelle `pont_methodologique` (PAS `pont`).

## Schéma : directions.json

```json
{
  "titre": "string (requis)",
  "description": "string (3-5 phrases)",
  "articles_support": ["10.xxxx/xxxx"],
  "hors_champ_refs": ["Titre exact d'un article hors_champ.json"],
  "trials_refs": ["NCTxxxxxxxx"],
  "priorite": "haute | moyenne | basse"
}
```

Contrainte : chaque titre dans `hors_champ_refs` DOIT correspondre à un `titre` dans `hors_champ.json`.
Contrainte : chaque NCT dans `trials_refs` DOIT correspondre à un `nct_id` dans `clinical_trials.json`.
Contrainte : chaque DOI dans `articles_support` DOIT correspondre à un `doi` dans `articles_db.json`.

## Schéma : clinical_trials.json

```json
{
  "nct_id": "NCTxxxxxxxx (requis)",
  "titre": "string",
  "phase": "Phase 1 | Phase 1/2 | Phase 2 | Phase 2/3 | Phase 3",
  "statut": "Recruiting | Active | Active, not recruiting",
  "sous_type": "DLBCL | FL | MCL | Hodgkin | MW | PCNSL | DLBCL/FL",
  "sponsor": "string",
  "centres_fr": "Oui | Non | À confirmer",
  "n_patients": "string",
  "date_debut": "YYYY-MM",
  "date_fin_est": "YYYY-MM",
  "endpoints": "string",
  "resume": "string",
  "has_ctdna": true,
  "last_updated": "YYYY-MM-DD"
}
```

## Schéma : conferences.json

```json
{
  "nom": "string (requis)",
  "lieu": "string",
  "date_debut": "YYYY-MM-DD",
  "date_fin": "YYYY-MM-DD",
  "deadline_abstract": "YYYY-MM-DD | null",
  "url": "string"
}
```

## Validation

Le script `validate_schema.py` vérifie toutes ces contraintes. À exécuter après chaque import :
```bash
python3 outils/validate_schema.py .
```
