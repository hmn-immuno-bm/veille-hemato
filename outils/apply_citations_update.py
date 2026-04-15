#!/usr/bin/env python3
"""
apply_citations_update.py — Phase 3 du workflow de mise à jour des citations.

Lit /tmp/citations_results.json (produit par l'exécution via Chrome MCP
du snippet généré par prepare_citations_update.py) et merge les compteurs
dans output/articles_db.json.

Format attendu de citations_results.json :
{
  "backend": "openalex",
  "fetched_at": "YYYY-MM-DD",
  "citations": {
    "<doi_normalized>": {
      "cited_by_count": 42,
      "openalex_id": "https://openalex.org/W...",
      "title": "..."
    },
    ...
  },
  "errors": [...]
}

Pour chaque article de la base ayant un DOI :
- Si le DOI est présent dans citations[] → met à jour :
    citation_count, citation_count_updated, citation_source, openalex_id
- Sinon → on ne touche pas (on ne supprime jamais une valeur existante).
"""

import argparse
import json
import os
import sys
from datetime import date


def normalize_doi(doi: str) -> str:
    if not doi:
        return ""
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("veille_dir")
    parser.add_argument("--results", default="/tmp/citations_results.json",
                        help="Fichier JSON produit par Chrome MCP (défaut: /tmp/citations_results.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="N'écrit pas la base, affiche juste le plan.")
    args = parser.parse_args()

    db_path = os.path.join(args.veille_dir, "output", "articles_db.json")
    if not os.path.exists(db_path):
        print(f"ERREUR : {db_path} introuvable", file=sys.stderr)
        return 1

    if not os.path.exists(args.results):
        print(f"ERREUR : {args.results} introuvable.", file=sys.stderr)
        print("       Générer d'abord le snippet via prepare_citations_update.py", file=sys.stderr)
        print("       puis exécuter le snippet via Chrome MCP (javascript_tool)", file=sys.stderr)
        print("       et sauvegarder la sortie dans ce fichier.", file=sys.stderr)
        return 1

    with open(args.results) as f:
        results = json.load(f)

    citations_map = results.get("citations") or {}
    backend = results.get("backend", "unknown")
    fetched_at = results.get("fetched_at") or date.today().isoformat()
    errors = results.get("errors") or []

    if errors:
        print(f"⚠️  {len(errors)} batch(es) en erreur lors du fetch — voir {args.results}")

    with open(db_path) as f:
        articles = json.load(f)

    updated, unchanged, no_doi, not_found = 0, 0, 0, 0

    for a in articles:
        doi = normalize_doi(a.get("doi") or "")
        if not doi:
            no_doi += 1
            continue
        hit = citations_map.get(doi)
        if hit is None:
            not_found += 1
            continue
        new_count = hit.get("cited_by_count")
        if new_count is None:
            not_found += 1
            continue
        old_count = a.get("citation_count")
        if old_count == new_count and a.get("citation_source") == backend:
            # Rafraîchit juste la date
            a["citation_count_updated"] = fetched_at
            unchanged += 1
            continue
        a["citation_count"] = new_count
        a["citation_count_updated"] = fetched_at
        a["citation_source"] = backend
        if hit.get("openalex_id"):
            a["openalex_id"] = hit["openalex_id"]
        updated += 1

    print(f"Backend         : {backend}")
    print(f"Fetched_at      : {fetched_at}")
    print(f"Articles dans DB: {len(articles)}")
    print(f"  mis à jour    : {updated}")
    print(f"  inchangés     : {unchanged}")
    print(f"  sans DOI      : {no_doi}")
    print(f"  non trouvés   : {not_found}")

    if args.dry_run:
        print("\n(dry-run — aucune écriture)")
        return 0

    with open(db_path, "w") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {db_path} mis à jour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
