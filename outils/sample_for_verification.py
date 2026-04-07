#!/usr/bin/env python3
"""
sample_for_verification.py — Tirage stochastique anti-drift.

Sélectionne un échantillon aléatoire d'articles (5% par défaut, plafonné à 30)
pour vérification manuelle/MCP des PMID + titres + DOI auprès de PubMed.

Critères de stratification :
- 50% sur les articles AVEC verified_at (re-vérification)
- 50% sur les articles SANS verified_at (vérification primaire)
- On évite les articles déjà passés en quarantaine

Usage :
    python3 outils/sample_for_verification.py <veille_dir> [--rate 0.05] [--seed 42]

Sortie : JSON sur stdout avec la liste des articles à vérifier.
À donner ensuite à Cowork qui appellera mcp__c1938703...__get_article_metadata
en lots de 5-10 PMIDs.
"""

import json
import os
import sys
import random
import argparse
from datetime import date


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('veille_dir')
    p.add_argument('--rate', type=float, default=0.05,
                   help='Fraction de la base à échantillonner (défaut 0.05 = 5%%)')
    p.add_argument('--max', type=int, default=30,
                   help='Plafond absolu du nombre d\'articles tirés (défaut 30)')
    p.add_argument('--seed', type=int, default=None,
                   help='Seed PRNG pour reproductibilité (défaut: date du jour)')
    args = p.parse_args()

    db_path = os.path.join(args.veille_dir, 'output', 'articles_db.json')
    with open(db_path, encoding='utf-8') as f:
        db = json.load(f)

    # Seed déterministe par jour si non précisé → 1 tirage par jour reproductible
    if args.seed is None:
        args.seed = int(date.today().strftime('%Y%m%d'))
    random.seed(args.seed)

    # Filtrer : articles avec PMID OU DOI (sinon non vérifiable)
    eligible = [a for a in db if (a.get('pmid', '') or '').strip()
                or (a.get('doi', '') or '').strip()]

    n_target = min(args.max, max(1, int(len(eligible) * args.rate)))

    # Stratification verified / non-verified
    verified = [a for a in eligible if a.get('verified_at')]
    unverified = [a for a in eligible if not a.get('verified_at')]

    n_unverified = min(len(unverified), n_target // 2 + n_target % 2)
    n_verified = min(len(verified), n_target - n_unverified)

    sample = random.sample(unverified, n_unverified) + \
             random.sample(verified, n_verified)
    random.shuffle(sample)

    output = {
        'date': date.today().isoformat(),
        'seed': args.seed,
        'total_in_db': len(db),
        'eligible': len(eligible),
        'sample_size': len(sample),
        'split': {'unverified': n_unverified, 'verified': n_verified},
        'instructions': (
            "Pour chaque entrée, appeler PubMed MCP "
            "(mcp__c1938703...__get_article_metadata) avec le PMID, ou "
            "convert_article_ids depuis le DOI si pas de PMID. Comparer "
            "le titre retourné avec le titre attendu (matching souple). "
            "Marquer verified_at=YYYY-MM-DD si OK, sinon déplacer en quarantaine."
        ),
        'articles': [
            {
                'pmid': a.get('pmid', ''),
                'doi': a.get('doi', ''),
                'titre': a.get('titre', ''),
                'journal': a.get('journal', ''),
                'semaine': a.get('semaine', ''),
                'verified_at': a.get('verified_at', None),
            }
            for a in sample
        ],
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
