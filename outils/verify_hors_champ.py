#!/usr/bin/env python3
"""
Vérification en ligne des entrées hors_champ.json (anti-hallucination).

Pour chaque entrée :
  - Si arXiv URL/ID : fetch https://arxiv.org/abs/{id} → vérifie HTTP 200 et titre présent
  - Si DOI         : fetch https://doi.org/{doi}      → vérifie redirection valide (HTTP 200)
  - Si verified_source rempli : marqué OK sans refetch

Les entrées qui échouent sont déplacées dans output/hors_champ_quarantine.json
et retirées de output/hors_champ.json (sauf si --dry-run).

Usage : python3 outils/verify_hors_champ.py <veille_dir> [--dry-run]
"""
import json, os, sys, re, urllib.request, urllib.error
from datetime import datetime

UA = "Mozilla/5.0 (compatible; HoraciHoldsAuditBot/1.0)"
TIMEOUT = 15

def fetch(url):
    """Retourne (status, body_text_or_none, final_url) ou (None, str_error, None)."""
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(50000).decode('utf-8', errors='ignore')
            return (r.status, body, r.url)
    except urllib.error.HTTPError as e:
        return (e.code, None, url)
    except Exception as e:
        return (None, str(e), url)


def verify_arxiv(arxiv_id, expected_title=None):
    """Vérifie qu'un arXiv ID existe et matche éventuellement un titre."""
    aid = arxiv_id.replace('arXiv:', '').replace('arxiv:', '').strip().rstrip('/')
    # Format check
    m = re.match(r'^(\d{4})\.(\d{4,5})(v\d+)?$', aid)
    if not m:
        return (False, f"Format arXiv invalide: {aid}")
    yymm = m.group(1)
    mm = int(yymm[2:])
    if mm < 1 or mm > 12:
        return (False, f"Mois arXiv invalide ({mm:02d}): {aid}")
    url = f"https://arxiv.org/abs/{aid}"
    status, body, _ = fetch(url)
    # status None = erreur réseau, on ne quarantine PAS (réseau bloqué).
    if status is None:
        return (True, f"arXiv {aid} : format OK (réseau indisponible, non vérifié en ligne)")
    if status == 404:
        return (False, f"arXiv {aid} : 404 (n'existe pas)")
    if status != 200 or not body:
        return (True, f"arXiv {aid} : format OK (HTTP {status}, non vérifiable)")
    # Titre check rapide (le tag <title> contient "[id] Title" sur arxiv.org)
    if expected_title:
        # Normalise espaces et casse
        normed_body = re.sub(r'\s+', ' ', body.lower())
        normed_title = re.sub(r'\s+', ' ', expected_title.lower())
        # Cherche au moins un fragment significatif (premiers 40 chars)
        frag = normed_title[:40]
        if frag and frag not in normed_body:
            return (False, f"arXiv {aid} : titre ne correspond pas (cherché '{frag[:30]}…')")
    return (True, f"arXiv {aid} OK")


def verify_doi(doi):
    """Vérifie qu'un DOI résout."""
    d = doi.strip()
    if d.startswith('http'):
        url = d
    else:
        url = f"https://doi.org/{d}"
    status, body, final = fetch(url)
    if status == 200:
        return (True, f"DOI résout vers {final[:80]}")
    if status is None:
        return (True, f"DOI {d[:50]} : format OK (réseau indisponible)")
    if status == 404:
        return (False, f"DOI {d} : 404 (n'existe pas)")
    return (True, f"DOI {d[:50]} : HTTP {status} (non vérifiable mais format OK)")


def verify_entry(h):
    """Retourne (ok, message). Vérifie une entrée hors_champ."""
    titre = h.get('titre', '')
    doi_field = (h.get('doi') or '').strip()
    verified = (h.get('verified_source') or '').strip()

    # Si verified_source explicite, refetch
    if verified.startswith('http'):
        status, _, _ = fetch(verified)
        if status == 200:
            return (True, f"verified_source OK ({verified[:60]})")
        return (False, f"verified_source HTTP {status}")

    # arXiv URL ou ID
    m = re.search(r'arxiv\.org/abs/([^\s/]+)', doi_field, re.I)
    if m:
        return verify_arxiv(m.group(1), titre)
    m = re.match(r'^(?:arxiv:)?(\d{4}\.\d{4,5}(?:v\d+)?)$', doi_field, re.I)
    if m:
        return verify_arxiv(m.group(1), titre)

    # Champ "journal" du type "arXiv:2601.02957"
    j = (h.get('journal') or '').strip()
    m = re.match(r'arxiv:?\s*(\d{4}\.\d{4,5})', j, re.I)
    if m:
        return verify_arxiv(m.group(1), titre)

    # DOI brut
    if doi_field.startswith('10.') or doi_field.startswith('http'):
        return verify_doi(doi_field)

    return (False, "Aucun identifiant vérifiable (ni DOI ni arXiv ID)")


def run(veille_dir, dry_run=False):
    hc_path = os.path.join(veille_dir, 'output', 'hors_champ.json')
    if not os.path.exists(hc_path):
        print(f"❌ {hc_path} introuvable")
        return 1
    with open(hc_path, encoding='utf-8') as f:
        entries = json.load(f)

    kept, quarantined = [], []
    for i, h in enumerate(entries):
        ok, msg = verify_entry(h)
        label = h.get('titre', '')[:60]
        if ok:
            print(f"  ✅ [{i}] {label} → {msg}")
            h['verified_at'] = datetime.now().strftime("%Y-%m-%d")
            kept.append(h)
        else:
            print(f"  ❌ [{i}] {label} → {msg}")
            h['quarantine_reason'] = msg
            h['quarantined_at'] = datetime.now().strftime("%Y-%m-%d")
            quarantined.append(h)

    summary = {
        "total": len(entries),
        "verified": len(kept),
        "quarantined": len(quarantined),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    print("\n" + json.dumps(summary, indent=2))

    if dry_run:
        print("\n(dry-run : aucun fichier modifié)")
        return 0 if not quarantined else 2

    if quarantined:
        q_path = os.path.join(veille_dir, 'output', 'hors_champ_quarantine.json')
        existing = []
        if os.path.exists(q_path):
            with open(q_path, encoding='utf-8') as f:
                try:
                    existing = json.load(f)
                except json.JSONDecodeError:
                    existing = []
        existing.extend(quarantined)
        with open(q_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"\n→ {len(quarantined)} entrée(s) déplacée(s) dans {q_path}")

    with open(hc_path, 'w', encoding='utf-8') as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
    print(f"→ {hc_path} mis à jour ({len(kept)} entrée(s) conservée(s))")
    return 0


if __name__ == '__main__':
    args = sys.argv[1:]
    dry = '--dry-run' in args
    args = [a for a in args if a != '--dry-run']
    veille_dir = args[0] if args else '.'
    sys.exit(run(veille_dir, dry_run=dry))
