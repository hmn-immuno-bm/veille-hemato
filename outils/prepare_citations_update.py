#!/usr/bin/env python3
"""
prepare_citations_update.py — Phase 1 du workflow de mise à jour des citations.

Le proxy Anthropic bloque toutes les APIs de citations depuis le sandbox.
Le seul canal réseau accessible est Chrome MCP (qui passe par le navigateur
de l'utilisateur). Ce script prépare un snippet JavaScript prêt-à-exécuter
via mcp__Claude_in_Chrome__javascript_tool.

Backends supportés :
  - openalex (défaut) : batch de 50 DOIs via filter=doi:A|B|C
  - crossref (fallback) : 1 DOI par requête, champ is-referenced-by-count

Usage :
  # Tous les articles stales (défaut OpenAlex)
  python3 outils/prepare_citations_update.py .

  # Seulement les articles sans citation_count (fallback CrossRef)
  python3 outils/prepare_citations_update.py . --backend crossref --only-missing

  # Forcer tout re-fetch OpenAlex
  python3 outils/prepare_citations_update.py . --max-age-days 0
"""

import argparse
import json
import os
import sys
from datetime import date

OPENALEX_MAILTO = "alexis.claudel@gmail.com"
CROSSREF_MAILTO = "alexis.claudel@gmail.com"
OPENALEX_BATCH_SIZE = 50
CROSSREF_DELAY_MS = 120  # ~8 req/s — bien sous la limite polite
OPENALEX_DELAY_MS = 150


def normalize_doi(doi: str) -> str:
    """Normalise un DOI pour matching (lowercase, pas de préfixe URL)."""
    if not doi:
        return ""
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def _build_openalex_js(batches: list[list[str]]) -> str:
    """Snippet JS pour fetch OpenAlex par batches de 50 DOIs."""
    js_batches = json.dumps(batches, ensure_ascii=False)
    return f"""(async () => {{
  const batches = {js_batches};
  const mailto = {json.dumps(OPENALEX_MAILTO)};
  const out = {{}};
  const errors = [];
  let fetched = 0;
  for (let i = 0; i < batches.length; i++) {{
    const batch = batches[i];
    const filter = 'doi:' + batch.join('|');
    const url = `https://api.openalex.org/works?filter=${{filter}}&per-page={OPENALEX_BATCH_SIZE}&mailto=${{mailto}}`;
    try {{
      const r = await fetch(url);
      if (!r.ok) {{
        errors.push({{batch: i, status: r.status}});
        continue;
      }}
      const j = await r.json();
      for (const w of (j.results || [])) {{
        const d = (w.doi || '').replace(/^https?:\\/\\/doi\\.org\\//i, '').toLowerCase();
        if (d) {{
          out[d] = {{
            cited_by_count: w.cited_by_count,
            openalex_id: w.id,
            title: w.title
          }};
          fetched++;
        }}
      }}
    }} catch (e) {{
      errors.push({{batch: i, error: String(e).slice(0, 200)}});
    }}
    if (i < batches.length - 1) {{
      await new Promise(res => setTimeout(res, {OPENALEX_DELAY_MS}));
    }}
  }}
  return {{
    backend: 'openalex',
    fetched_at: new Date().toISOString().slice(0, 10),
    total_batches: batches.length,
    total_requested: batches.reduce((a, b) => a + b.length, 0),
    total_fetched: fetched,
    errors: errors,
    citations: out
  }};
}})()"""


def _build_crossref_js(dois: list[str]) -> str:
    """Snippet JS pour fetch CrossRef DOI par DOI (fallback)."""
    js_dois = json.dumps(dois, ensure_ascii=False)
    return f"""(async () => {{
  const dois = {js_dois};
  const mailto = {json.dumps(CROSSREF_MAILTO)};
  const out = {{}};
  const errors = [];
  let fetched = 0;
  for (let i = 0; i < dois.length; i++) {{
    const doi = dois[i];
    const url = `https://api.crossref.org/works/${{encodeURIComponent(doi)}}?mailto=${{mailto}}`;
    try {{
      const r = await fetch(url);
      if (!r.ok) {{
        errors.push({{doi: doi, status: r.status}});
        continue;
      }}
      const j = await r.json();
      const w = j.message || {{}};
      const count = w['is-referenced-by-count'];
      if (count !== undefined) {{
        out[doi.toLowerCase()] = {{
          cited_by_count: count,
          title: Array.isArray(w.title) ? w.title[0] : (w.title || null)
        }};
        fetched++;
      }}
    }} catch (e) {{
      errors.push({{doi: doi, error: String(e).slice(0, 200)}});
    }}
    if (i < dois.length - 1) {{
      await new Promise(res => setTimeout(res, {CROSSREF_DELAY_MS}));
    }}
  }}
  return {{
    backend: 'crossref',
    fetched_at: new Date().toISOString().slice(0, 10),
    total_requested: dois.length,
    total_fetched: fetched,
    errors: errors,
    citations: out
  }};
}})()"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("veille_dir", help="Chemin vers le dossier Veille")
    parser.add_argument("--backend", choices=["openalex", "crossref"], default="openalex",
                        help="Backend à utiliser (défaut: openalex)")
    parser.add_argument("--only-missing", action="store_true",
                        help="Seulement les articles SANS citation_count (fallback)")
    parser.add_argument("--output-js", default=None,
                        help="Chemin du snippet JS (défaut: /tmp/citations_fetch_{backend}.js)")
    parser.add_argument("--output-input", default=None,
                        help="Chemin du dump JSON des inputs")
    parser.add_argument("--max-age-days", type=int, default=30,
                        help="Re-fetch si citation_count_updated > N jours (défaut: 30). 0=tout.")
    args = parser.parse_args()

    backend = args.backend
    if args.output_js is None:
        args.output_js = f"/tmp/citations_fetch_{backend}.js"
    if args.output_input is None:
        args.output_input = f"/tmp/citations_input_{backend}.json"

    db_path = os.path.join(args.veille_dir, "output", "articles_db.json")
    if not os.path.exists(db_path):
        print(f"ERREUR : {db_path} introuvable", file=sys.stderr)
        return 1

    with open(db_path) as f:
        articles = json.load(f)

    today = date.today().isoformat()

    # Sélection des DOIs à interroger
    to_fetch = []
    for a in articles:
        doi = normalize_doi(a.get("doi") or "")
        if not doi:
            continue

        if args.only_missing:
            # Mode fallback : seulement ceux sans citation_count
            if a.get("citation_count") is not None:
                continue
        elif args.max_age_days > 0:
            last = a.get("citation_count_updated")
            if last:
                try:
                    last_d = date.fromisoformat(last)
                    delta = (date.fromisoformat(today) - last_d).days
                    if delta < args.max_age_days:
                        continue
                except ValueError:
                    pass

        to_fetch.append(doi)

    # Dedup en préservant l'ordre
    seen = set()
    unique_dois = []
    for d in to_fetch:
        if d not in seen:
            seen.add(d)
            unique_dois.append(d)

    if not unique_dois:
        print("Rien à mettre à jour.")
        return 0

    # Génération du snippet JS selon le backend
    if backend == "openalex":
        batches = [unique_dois[i:i + OPENALEX_BATCH_SIZE]
                   for i in range(0, len(unique_dois), OPENALEX_BATCH_SIZE)]
        js = _build_openalex_js(batches)
        batch_info = f"{len(batches)} batch(es) de {OPENALEX_BATCH_SIZE}"
    else:  # crossref
        js = _build_crossref_js(unique_dois)
        batches = [unique_dois]  # pour le dump
        batch_info = f"1 DOI/requête, {CROSSREF_DELAY_MS}ms entre chaque"

    # Dump pour référence / reprise
    with open(args.output_input, "w") as f:
        json.dump({
            "generated_at": today,
            "total_dois": len(unique_dois),
            "dois": unique_dois,
            "backend": backend,
        }, f, ensure_ascii=False, indent=2)

    with open(args.output_js, "w") as f:
        f.write(js)

    print(f"✅ Snippet JS généré : {args.output_js}")
    print(f"   Backend : {backend}")
    print(f"   {len(unique_dois)} DOIs — {batch_info}")
    print(f"   Backup des inputs : {args.output_input}")
    if backend == "crossref":
        est = len(unique_dois) * CROSSREF_DELAY_MS / 1000
        print(f"   Durée estimée : ~{est:.0f}s")
    print()
    print("─" * 70)
    print("ÉTAPE SUIVANTE (à exécuter par Cowork) :")
    print("─" * 70)
    print(f"  1. Lire {args.output_js}")
    print("  2. L'exécuter via mcp__Claude_in_Chrome__javascript_tool")
    print("     (action='javascript_exec', tabId=<id>)")
    print("  3. Sauvegarder le résultat JSON dans /tmp/citations_results.json")
    print(f"  4. python3 outils/apply_citations_update.py <veille_dir>")
    print("─" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
