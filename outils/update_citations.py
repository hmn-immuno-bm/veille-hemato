#!/usr/bin/env python3
"""
update_citations.py — DEPRECATED (2026-04-07)

Mise à jour des compteurs de citations.

⚠️  STATUT : DÉSACTIVÉ — toutes les API publiques de citations sont bloquées
par le proxy egress de Cowork.

APIs testées et bloquées (2026-04-07) :
- icite.od.nih.gov              (NIH iCite)
- api.semanticscholar.org       (Semantic Scholar Graph)
- api.crossref.org              (CrossRef)
- api.openalex.org              (OpenAlex)
- www.ebi.ac.uk/europepmc       (Europe PMC REST)
- eutils.ncbi.nlm.nih.gov       (NCBI Entrez)
- pubmed.ncbi.nlm.nih.gov       (PubMed HTML)

Le PubMed MCP ne retourne pas de citation_count dans get_article_metadata.

──────────────────────────────────────────────────────────────────────────────
SEULES VOIES POSSIBLES :

1) Via Chrome MCP (extension Claude in Chrome installée côté utilisateur).
   La page PubMed `https://pubmed.ncbi.nlm.nih.gov/{PMID}/` affiche un panneau
   "Cited by" dans la sidebar — récupérable via :
       mcp__Claude_in_Chrome__navigate(url=...)
       mcp__Claude_in_Chrome__get_page_text()
   À implémenter dans une nouvelle tâche planifiée si besoin.

2) Manuel : un export CSV depuis Web of Science / Scopus à importer
   périodiquement. Plus fiable mais nécessite un accès institutionnel.

3) Si Anthropic ouvre l'egress vers iCite (NIH gov) un jour, ré-implémenter
   ce script avec le code ci-dessous (commenté).
──────────────────────────────────────────────────────────────────────────────
"""

import sys

print("⚠️  update_citations.py est DÉSACTIVÉ (toutes les API bloquées).")
print("    Voir l'en-tête du fichier pour les alternatives.")
sys.exit(2)


# ─────────────────────────────────────────────────────────────────────────────
# CODE LEGACY — gardé pour réactivation rapide si l'egress iCite est ouvert.
# ─────────────────────────────────────────────────────────────────────────────
#
# import json, os, time, urllib.request, urllib.error
#
# ICITE_URL = "https://icite.od.nih.gov/api/pubs?pmids={pmids}"
#
# def fetch_icite_batch(pmids):
#     """iCite accepte jusqu'à 1000 PMIDs par requête, comma-separated."""
#     url = ICITE_URL.format(pmids=",".join(pmids))
#     req = urllib.request.Request(url, headers={'User-Agent': 'VeilleHemato/1.0'})
#     with urllib.request.urlopen(req, timeout=20) as resp:
#         data = json.loads(resp.read().decode('utf-8'))
#         return {str(p['pmid']): p.get('citation_count', 0) for p in data.get('data', [])}
#
# def main():
#     veille_dir = sys.argv[1]
#     db_path = os.path.join(veille_dir, 'output', 'articles_db.json')
#     with open(db_path) as f:
#         articles = json.load(f)
#     pmids = [str(a['pmid']) for a in articles if a.get('pmid')]
#     # Batches de 200 PMIDs
#     counts = {}
#     for i in range(0, len(pmids), 200):
#         counts.update(fetch_icite_batch(pmids[i:i+200]))
#         time.sleep(1)
#     for a in articles:
#         pmid = str(a.get('pmid', ''))
#         if pmid in counts:
#             a['citation_count'] = counts[pmid]
#             a['citation_count_updated'] = '2026-04-07'
#     with open(db_path, 'w') as f:
#         json.dump(articles, f, ensure_ascii=False, indent=2)
