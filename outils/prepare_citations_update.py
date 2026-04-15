#!/usr/bin/env python3
"""
prepare_citations_update.py — Phase 1 du workflow de mise à jour des citations.

Le proxy Anthropic bloque toutes les APIs de citations depuis le sandbox.
Le seul canal réseau accessible est Chrome MCP (qui passe par le navigateur
de l'utilisateur). Ce script prépare un snippet JavaScript prêt-à-exécuter
via mcp__Claude_in_Chrome__javascript_tool.

Workflow complet (pilotable depuis une session Cowork) :

  1. python3 outils/prepare_citations_update.py .
     → génère /tmp/citations_fetch.js
     → affiche la commande à donner au javascript_tool

  2. Cowork exécute /tmp/citations_fetch.js via javascript_tool
     → résultat : {doi_normalized: {cited_by_count, title, openalex_id}, ...}
     → Cowork sauvegarde dans /tmp/citations_results.json

  3. python3 outils/apply_citations_update.py .
     → merge dans output/articles_db.json
     → ajoute citation_count + citation_count_updated + citation_source

Backend : OpenAlex (meilleure couverture, accepte DOI, rate-limit 10 req/s,
pas de clé, polite pool avec mailto).
"""

import argparse
import json
import os
import sys
from datetime import date

OPENALEX_MAILTO = "alexis.claudel@gmail.com"
BATCH_SIZE = 50  # OpenAlex accepte jusqu'à 50 DOIs dans filter=doi:A|B|C
POLITE_DELAY_MS = 150  # ~6.6 req/s — large sous la limite 10 req/s


def normalize_doi(doi: str) -> str:
    """Normalise un DOI pour matching (lowercase, pas de préfixe URL)."""
    if not doi:
        return ""
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("veille_dir", help="Chemin vers le dossier Veille (contient output/articles_db.json)")
    parser.add_argument("--output-js", default="/tmp/citations_fetch.js",
                        help="Chemin du snippet JS à générer (défaut: /tmp/citations_fetch.js)")
    parser.add_argument("--output-input", default="/tmp/citations_input.json",
                        help="Chemin du dump JSON des inputs (défaut: /tmp/citations_input.json)")
    parser.add_argument("--max-age-days", type=int, default=30,
                        help="Re-fetch seulement si citation_count_updated > N jours (défaut: 30). Mettre 0 pour tout re-fetch.")
    args = parser.parse_args()

    db_path = os.path.join(args.veille_dir, "output", "articles_db.json")
    if not os.path.exists(db_path):
        print(f"ERREUR : {db_path} introuvable", file=sys.stderr)
        return 1

    with open(db_path) as f:
        articles = json.load(f)

    today = date.today().isoformat()

    # Sélection : tout article avec DOI, filtré par fraîcheur si demandé
    to_fetch = []
    for a in articles:
        doi = normalize_doi(a.get("doi") or "")
        if not doi:
            continue
        if args.max_age_days > 0:
            last = a.get("citation_count_updated")
            if last:
                # Si la date est récente, on skip
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
        print("Rien à mettre à jour (tous les articles ont des citations fraîches).")
        return 0

    # Batches de BATCH_SIZE
    batches = [unique_dois[i:i + BATCH_SIZE] for i in range(0, len(unique_dois), BATCH_SIZE)]

    # Dump pour référence / reprise
    with open(args.output_input, "w") as f:
        json.dump({
            "generated_at": today,
            "total_dois": len(unique_dois),
            "batches": batches,
            "backend": "openalex",
            "mailto": OPENALEX_MAILTO,
        }, f, ensure_ascii=False, indent=2)

    # Génère le snippet JS
    # On inline les batches directement — pas de réseau sandbox, donc pas
    # d'autre choix que de transporter les données dans le texte JS.
    js_batches = json.dumps(batches, ensure_ascii=False)
    js = f"""(async () => {{
  const batches = {js_batches};
  const mailto = {json.dumps(OPENALEX_MAILTO)};
  const out = {{}};
  const errors = [];
  let fetched = 0;
  for (let i = 0; i < batches.length; i++) {{
    const batch = batches[i];
    const filter = 'doi:' + batch.join('|');
    const url = `https://api.openalex.org/works?filter=${{filter}}&per-page={BATCH_SIZE}&mailto=${{mailto}}`;
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
      await new Promise(res => setTimeout(res, {POLITE_DELAY_MS}));
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

    with open(args.output_js, "w") as f:
        f.write(js)

    print(f"✅ Snippet JS généré : {args.output_js}")
    print(f"   {len(unique_dois)} DOIs à interroger en {len(batches)} batch(es) de {BATCH_SIZE}")
    print(f"   Backup des inputs : {args.output_input}")
    print()
    print("─" * 70)
    print("ÉTAPE SUIVANTE (à exécuter par Cowork) :")
    print("─" * 70)
    print(f"  1. Lire {args.output_js}")
    print("  2. L'exécuter via mcp__Claude_in_Chrome__javascript_tool")
    print("     (action='javascript_exec', tabId=<id>)")
    print("  3. Sauvegarder le résultat JSON dans /tmp/citations_results.json")
    print("  4. python3 outils/apply_citations_update.py <veille_dir>")
    print("─" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
