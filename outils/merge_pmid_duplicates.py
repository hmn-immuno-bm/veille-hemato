#!/usr/bin/env python3
"""
merge_pmid_duplicates.py — Fusionne les articles partageant le même PMID.

Usage:
    python3 outils/merge_pmid_duplicates.py <veille_dir> [--dry-run]

Stratégie de fusion : pour chaque groupe de doublons :
  1. On garde l'article avec le résumé/critique le plus long (le plus enrichi)
  2. On absorbe les champs manquants depuis les autres copies
  3. On supprime les autres
  4. Backup automatique avant modification
"""

import json
import os
import sys
import shutil
from collections import defaultdict
from datetime import datetime


def quality_score(art):
    """Score de qualité d'un article pour choisir le 'meilleur' lors d'une fusion."""
    s = 0
    s += len(art.get('resume', '') or '')
    s += len(art.get('critique', '') or '')
    s += 50 if art.get('verified_at') else 0
    s += 30 if art.get('senior_auteur') else 0
    s += 20 if art.get('if_value', 0) else 0
    s += 10 if art.get('pays') else 0
    return s


def merge_into(target, source):
    """Complète target avec les champs vides remplis par source. In-place."""
    for k, v in source.items():
        if v in (None, '', 0):
            continue
        if not target.get(k):
            target[k] = v


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 outils/merge_pmid_duplicates.py <veille_dir> [--dry-run]")
        sys.exit(1)

    veille_dir = sys.argv[1]
    dry_run = '--dry-run' in sys.argv

    db_path = os.path.join(veille_dir, 'output', 'articles_db.json')
    with open(db_path, encoding='utf-8') as f:
        db = json.load(f)

    initial_count = len(db)

    # Grouper par PMID
    by_pmid = defaultdict(list)
    for i, a in enumerate(db):
        pmid = str(a.get('pmid', '') or '').strip()
        if pmid and pmid.isdigit():
            by_pmid[pmid].append(i)

    duplicates = {p: idxs for p, idxs in by_pmid.items() if len(idxs) > 1}

    if not duplicates:
        print("✅ Aucun PMID en doublon")
        sys.exit(0)

    print(f"🔍 {len(duplicates)} PMID(s) en doublon, "
          f"{sum(len(v) for v in duplicates.values())} entrées concernées")

    to_delete = set()
    actions = []

    for pmid, idxs in duplicates.items():
        # Trier par qualité décroissante
        idxs_sorted = sorted(idxs, key=lambda i: quality_score(db[i]), reverse=True)
        keeper_idx = idxs_sorted[0]
        keeper = db[keeper_idx]
        kept_title = (keeper.get('titre') or '')[:60]
        actions.append(f"PMID {pmid} : garde [{keeper_idx}] '{kept_title}...' (q={quality_score(keeper)})")
        for other_idx in idxs_sorted[1:]:
            other = db[other_idx]
            merge_into(keeper, other)
            to_delete.add(other_idx)
            actions.append(f"   └─ supprime [{other_idx}] (q={quality_score(other)})")

    for line in actions:
        print(line)

    if dry_run:
        print(f"\n[DRY-RUN] Supprimerait {len(to_delete)} entrées, "
              f"de {initial_count} à {initial_count - len(to_delete)}")
        sys.exit(0)

    # Backup
    backup_name = f"articles_db_pre_pmid_merge_{datetime.now():%Y%m%d_%H%M%S}.json"
    backup_path = os.path.join(veille_dir, 'output', 'archive', backup_name)
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    shutil.copy(db_path, backup_path)
    print(f"\n💾 Backup : {backup_path}")

    # Filtrer
    new_db = [a for i, a in enumerate(db) if i not in to_delete]
    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump(new_db, f, ensure_ascii=False, indent=2)

    print(f"✅ {initial_count} → {len(new_db)} articles ({len(to_delete)} fusionnés)")


if __name__ == '__main__':
    main()
