#!/usr/bin/env python3
"""
Vérification en ligne des articles récents de articles_db.json (anti-hallucination).

Pour chaque article ajouté dans la dernière semaine ISO :
  - Si DOI présent : fetch https://doi.org/{doi} → HTTP 200 attendu
  - Si PMID présent et pas de DOI : fetch https://pubmed.ncbi.nlm.nih.gov/{pmid}/

Les articles qui échouent sont marqués `unverified=true` (ou déplacés en
quarantaine si --remove). Par défaut, vérifie seulement la dernière semaine.

Usage : python3 outils/verify_articles.py <veille_dir> [--all] [--remove] [--week 2026-S14]
"""
import json, os, sys, re, urllib.request, urllib.error, time
from datetime import datetime

UA = "Mozilla/5.0 (compatible; HoraciHoldsAuditBot/1.0)"
TIMEOUT = 15
DELAY = 0.5  # politesse


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def verify_one(a):
    doi = (a.get('doi') or '').strip()
    pmid = (a.get('pmid') or '').strip()
    if doi:
        url = doi if doi.startswith('http') else f"https://doi.org/{doi}"
        s = fetch(url)
        if s == 200:
            return (True, f"DOI {doi[:50]} OK")
        if s is None:
            return (True, f"DOI {doi[:50]} : réseau indisponible (non vérifié)")
        if s == 404 and pmid:
            s2 = fetch(f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
            if s2 == 200:
                return (True, f"DOI 404 mais PMID {pmid} OK")
        if s == 404:
            return (False, f"DOI {doi[:50]} : 404 (n'existe pas)")
        return (True, f"DOI {doi[:50]} : HTTP {s} (non bloquant)")
    if pmid:
        s = fetch(f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
        if s == 200:
            return (True, f"PMID {pmid} OK")
        if s is None:
            return (True, f"PMID {pmid} : réseau indisponible")
        if s == 404:
            return (False, f"PMID {pmid} : 404")
        return (True, f"PMID {pmid} : HTTP {s} (non bloquant)")
    return (False, "Ni DOI ni PMID")


def latest_week(articles):
    sems = [a.get('semaine', '') for a in articles
            if re.match(r'^\d{4}-S\d{2}$', a.get('semaine', ''))]
    return max(sems) if sems else None


def run(veille_dir, all_=False, remove=False, week=None):
    db_path = os.path.join(veille_dir, 'output', 'articles_db.json')
    with open(db_path, encoding='utf-8') as f:
        articles = json.load(f)

    if not all_:
        target = week or latest_week(articles)
        if not target:
            print("❌ Aucune semaine ISO détectée")
            return 1
        targets = [(i, a) for i, a in enumerate(articles) if a.get('semaine') == target]
        print(f"→ Vérification semaine {target} ({len(targets)} articles)")
    else:
        targets = list(enumerate(articles))
        print(f"→ Vérification de TOUS les articles ({len(targets)})")

    failed = []
    for idx, (i, a) in enumerate(targets):
        ok, msg = verify_one(a)
        label = a.get('titre', '')[:55]
        marker = "✅" if ok else "❌"
        print(f"  {marker} [{i}] {label} → {msg}")
        if not ok:
            failed.append((i, a, msg))
        time.sleep(DELAY)

    print(f"\n{len(targets) - len(failed)}/{len(targets)} vérifiés. {len(failed)} échec(s).")

    if not failed:
        return 0

    if remove:
        bad_idx = {i for i, _, _ in failed}
        kept = [a for i, a in enumerate(articles) if i not in bad_idx]
        q_path = os.path.join(veille_dir, 'output', 'articles_quarantine.json')
        existing = []
        if os.path.exists(q_path):
            with open(q_path, encoding='utf-8') as f:
                try:
                    existing = json.load(f)
                except json.JSONDecodeError:
                    existing = []
        for i, a, msg in failed:
            a['quarantine_reason'] = msg
            a['quarantined_at'] = datetime.now().strftime("%Y-%m-%d")
            existing.append(a)
        with open(q_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(kept, f, ensure_ascii=False, indent=2)
        print(f"→ {len(failed)} article(s) déplacé(s) dans {q_path}")
    else:
        # Marquage non destructif
        for i, _, msg in failed:
            articles[i]['unverified'] = True
            articles[i]['unverified_reason'] = msg
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        print(f"→ {len(failed)} article(s) marqués `unverified=true` (utilise --remove pour quarantaine)")
    return 0 if not failed else 2


if __name__ == '__main__':
    args = sys.argv[1:]
    all_ = '--all' in args
    remove = '--remove' in args
    week = None
    if '--week' in args:
        idx = args.index('--week')
        week = args[idx + 1]
        args = args[:idx] + args[idx + 2:]
    args = [a for a in args if a not in ('--all', '--remove')]
    veille_dir = args[0] if args else '.'
    sys.exit(run(veille_dir, all_=all_, remove=remove, week=week))
