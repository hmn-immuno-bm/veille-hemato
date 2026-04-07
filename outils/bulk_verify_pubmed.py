#!/usr/bin/env python3
"""
bulk_verify_pubmed.py — Préparation d'une vérification PubMed massive.

Génère des batches de PMIDs (taille configurable) à fournir à Cowork qui
appellera mcp__c1938703...__get_article_metadata pour chaque batch.

Une fois la vérification effectuée, le script peut aussi appliquer les
résultats : marquage `verified_at` ou déplacement en quarantaine.

Usage :
    # Phase 1 : préparer la liste des batches à vérifier
    python3 outils/bulk_verify_pubmed.py <veille_dir> --plan [--batch 10] [--only-unverified]

    # Phase 2 : appliquer les résultats Cowork
    #   (results.json = {"verified": ["pmid1",...], "failed": [{"pmid": "...", "reason": "..."}]})
    python3 outils/bulk_verify_pubmed.py <veille_dir> --apply results.json
"""

import json
import os
import sys
import argparse
import shutil
from datetime import date, datetime


def cmd_plan(args):
    db_path = os.path.join(args.veille_dir, 'output', 'articles_db.json')
    with open(db_path, encoding='utf-8') as f:
        db = json.load(f)

    eligible = []
    for a in db:
        pmid = (a.get('pmid', '') or '').strip()
        if not pmid or not pmid.isdigit():
            continue
        if args.only_unverified and a.get('verified_at'):
            continue
        eligible.append({
            'pmid': pmid,
            'titre': (a.get('titre', '') or '')[:120],
            'doi': a.get('doi', ''),
            'semaine': a.get('semaine', ''),
        })

    # Découpe en batches
    batches = [eligible[i:i + args.batch] for i in range(0, len(eligible), args.batch)]

    plan = {
        'date': date.today().isoformat(),
        'total_in_db': len(db),
        'eligible': len(eligible),
        'only_unverified': args.only_unverified,
        'batch_size': args.batch,
        'n_batches': len(batches),
        'instructions': (
            "Pour chaque batch, appeler mcp__c1938703...__get_article_metadata "
            "avec la liste des PMIDs. Comparer chaque titre retourné avec "
            "le titre attendu (matching souple : tokens en commun ≥ 60%%). "
            "Construire results.json = {\"verified\": [pmid,...], "
            "\"failed\": [{\"pmid\": \"...\", \"reason\": \"...\"}]}, puis "
            "lancer ce script avec --apply results.json."
        ),
        'batches': [
            {'batch_id': i, 'pmids': [e['pmid'] for e in b], 'entries': b}
            for i, b in enumerate(batches)
        ],
    }

    out_path = os.path.join(args.veille_dir, 'output', 'bulk_verify_plan.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        'status': 'OK',
        'eligible': len(eligible),
        'batches': len(batches),
        'plan_path': out_path,
    }, indent=2))


def cmd_apply(args):
    db_path = os.path.join(args.veille_dir, 'output', 'articles_db.json')
    quar_path = os.path.join(args.veille_dir, 'output', 'articles_quarantine.json')

    with open(db_path, encoding='utf-8') as f:
        db = json.load(f)
    with open(args.results, encoding='utf-8') as f:
        results = json.load(f)

    verified_set = set(str(p) for p in results.get('verified', []))
    failed_map = {str(f['pmid']): f.get('reason', 'unknown')
                  for f in results.get('failed', [])}

    # Backup
    backup = os.path.join(args.veille_dir, 'output', 'archive',
                          f"articles_db_pre_bulk_verify_{datetime.now():%Y%m%d_%H%M%S}.json")
    os.makedirs(os.path.dirname(backup), exist_ok=True)
    shutil.copy(db_path, backup)

    today = date.today().isoformat()
    new_db = []
    quarantine = []
    n_verified = 0
    n_quarantine = 0
    if os.path.exists(quar_path):
        with open(quar_path, encoding='utf-8') as f:
            quarantine = json.load(f)

    for a in db:
        pmid = (a.get('pmid', '') or '').strip()
        if pmid in verified_set:
            a['verified_at'] = today
            a['verified_source'] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            n_verified += 1
            new_db.append(a)
        elif pmid in failed_map:
            a['quarantine_reason'] = failed_map[pmid]
            a['quarantined_at'] = today
            quarantine.append(a)
            n_quarantine += 1
        else:
            new_db.append(a)

    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump(new_db, f, ensure_ascii=False, indent=2)
    with open(quar_path, 'w', encoding='utf-8') as f:
        json.dump(quarantine, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        'status': 'OK',
        'backup': backup,
        'verified_marked': n_verified,
        'quarantined': n_quarantine,
        'remaining_in_db': len(new_db),
    }, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('veille_dir')
    p.add_argument('--plan', action='store_true', help='Phase 1 : générer le plan')
    p.add_argument('--apply', metavar='RESULTS_JSON', help='Phase 2 : appliquer les résultats')
    p.add_argument('--batch', type=int, default=10, help='Taille des batches PMIDs (défaut 10)')
    p.add_argument('--only-unverified', action='store_true',
                   help='Ne planifier que les articles sans verified_at')
    args = p.parse_args()

    if not args.plan and not args.apply:
        p.error('Spécifier --plan ou --apply')
    if args.apply:
        args.results = args.apply
        cmd_apply(args)
    else:
        cmd_plan(args)


if __name__ == '__main__':
    main()
