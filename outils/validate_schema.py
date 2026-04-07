#!/usr/bin/env python3
"""
Validation STRICTE du schéma et de la cohérence des fichiers JSON de veille.
Attrape les erreurs AVANT la génération du dashboard.

Toute clé manquante ou mal formatée → ERREUR (pas warning).
Référence SCHEMA.md pour les contrats.

Usage: python3 outils/validate_schema.py [veille_dir]
"""
import json, sys, os, re
from datetime import datetime

# ──────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
YEARMONTH_RE = re.compile(r'^\d{4}-\d{2}$')
SEMAINE_RE = re.compile(r'^\d{4}-(S\d{2}|H[12]|T[1-4])$')
DOI_RE = re.compile(r'^10\.\d{4,}/')
NCT_RE = re.compile(r'^NCT\d{7,}$')
ARXIV_RE = re.compile(r'^(\d{4})\.(\d{4,5})(v\d+)?$')  # YYMM.NNNNN

# ──────────────────────────────────────────────────────────────────
#  Regex-traps anti-hallucination DOI/arXiv
#  Patterns observés sur des hallucinations passées :
#   - Springer ABC : 10.1007/s00216-026-... (devrait être -2026-)
#   - Elsevier S-codes : doivent contenir l'année
#   - arXiv ID avec mois >12 ou année future
# ──────────────────────────────────────────────────────────────────
def doi_hallucination_check(doi):
    """Retourne un message si le DOI matche un pattern d'hallucination connu.
    NB : on évite les regex 'éditeur' (trop de faux positifs sur des DOIs réels).
    On se contente de patterns universels (formats invalides évidents)."""
    if not doi:
        return None
    d = doi.strip()
    # arXiv format dans le champ DOI
    m = re.match(r'^(?:arxiv:)?(\d{4})\.(\d{4,5})', d, re.I)
    if m:
        yymm = m.group(1)
        yy = int(yymm[:2])
        mm = int(yymm[2:])
        if mm < 1 or mm > 12:
            return f"arXiv ID mois invalide ({mm:02d}): {d}"
        if yy > 30:
            return f"arXiv ID année improbable (20{yy:02d}): {d}"
    # Caractères suspects (espaces, slashes multiples)
    if re.search(r'\s', d):
        return f"DOI contient des espaces: {d}"
    return None


def arxiv_id_hallucination_check(arxiv_id):
    """Vérifie qu'un arXiv ID a un format valide YYMM.NNNNN avec mois 01-12."""
    if not arxiv_id:
        return None
    a = arxiv_id.strip().replace('arXiv:', '').replace('arxiv:', '')
    m = ARXIV_RE.match(a)
    if not m:
        return f"arXiv ID format invalide '{arxiv_id}' (attendu YYMM.NNNNN)"
    yymm = m.group(1)
    mm = int(yymm[2:])
    if mm < 1 or mm > 12:
        return f"arXiv ID mois invalide {mm:02d} dans '{arxiv_id}'"
    yy = int(yymm[:2])
    if yy > 30:
        return f"arXiv ID année improbable 20{yy:02d} dans '{arxiv_id}'"
    return None


def load(veille_dir, path):
    full = os.path.join(veille_dir, path)
    if not os.path.exists(full):
        return None
    with open(full) as f:
        return json.load(f)


def check_type(obj, key, expected_type, label):
    """Vérifie qu'une clé existe et a le bon type. Retourne une erreur ou None."""
    if key not in obj:
        return f"{label}: clé '{key}' manquante"
    val = obj[key]
    if val is None and expected_type not in ('nullable', 'date_or_null'):
        return f"{label}: clé '{key}' est null (attendu: {expected_type})"
    if expected_type == 'str' and not isinstance(val, str):
        return f"{label}: clé '{key}' = {type(val).__name__} (attendu: str)"
    if expected_type == 'str_required' and (not isinstance(val, str) or not val.strip()):
        return f"{label}: clé '{key}' vide ou manquante (requis)"
    if expected_type == 'number' and not isinstance(val, (int, float)):
        return f"{label}: clé '{key}' = {type(val).__name__} (attendu: number)"
    if expected_type == 'bool' and not isinstance(val, bool):
        return f"{label}: clé '{key}' = {type(val).__name__} (attendu: bool)"
    if expected_type == 'list' and not isinstance(val, list):
        return f"{label}: clé '{key}' = {type(val).__name__} (attendu: list)"
    if expected_type == 'date_or_null':
        if val is not None and val != '' and not DATE_RE.match(str(val)):
            return f"{label}: clé '{key}' = '{val}' (attendu: YYYY-MM-DD ou null)"
    if expected_type == 'date_required':
        if not isinstance(val, str) or not DATE_RE.match(val):
            return f"{label}: clé '{key}' = '{val}' (attendu: YYYY-MM-DD)"
    return None


# ──────────────────────────────────────────────────────────────────
#  Validation principale
# ──────────────────────────────────────────────────────────────────
def load_categories(veille_dir):
    """Charge les labels de catégories depuis outils/categories.json (source unique)."""
    path = os.path.join(veille_dir, 'outils', 'categories.json')
    try:
        with open(path) as f:
            data = json.load(f)
        return {c['label'] for c in data['categories']}
    except Exception:
        # Fallback hardcodé si le fichier est cassé
        return {'Hémato générale', 'Lymphomes', 'ctDNA — Lymphomes',
                'ctDNA — Méthodo', 'Immuno + ctDNA/Lymphome', 'IA + Hémato', 'Preprint'}


def validate(veille_dir):
    errors = []
    warnings = []
    CATEGORIES = load_categories(veille_dir)

    # ═══════ 1. articles_db.json ═══════
    articles = load(veille_dir, 'output/articles_db.json')
    all_dois = set()
    if articles is None:
        errors.append("articles_db.json: fichier manquant")
    elif not isinstance(articles, list):
        errors.append("articles_db.json: n'est pas un tableau JSON")
    else:
        W_RE = re.compile(r'^\d{4}-W\d{2}$')
        for i, a in enumerate(articles):
            label = f"articles_db[{i}]"
            for key, typ in [('titre', 'str_required'), ('semaine', 'str_required'),
                             ('journal', 'str'), ('doi', 'str'),
                             ('if_value', 'number'), ('score', 'number')]:
                err = check_type(a, key, typ, label)
                if err:
                    errors.append(err)
            # Vérification format semaine : W interdit
            sem = a.get('semaine', '')
            if W_RE.match(sem):
                errors.append(f"{label}: semaine '{sem}' utilise W au lieu de S (ex: 2026-S13)")
            elif sem and not SEMAINE_RE.match(sem) and sem not in ('2014-2022', 'retro'):
                warnings.append(f"{label}: semaine '{sem}' format non standard")
            cat = a.get('categorie', '')
            if cat and cat not in CATEGORIES:
                warnings.append(f"{label}: catégorie inconnue '{cat}'")
            doi = a.get('doi', '')
            if doi:
                all_dois.add(doi)
                trap = doi_hallucination_check(doi)
                if trap:
                    errors.append(f"{label}: {trap}")

    # ═══════ 2. conferences.json — VALIDATION STRICTE ═══════
    conferences = load(veille_dir, 'output/conferences.json')
    if conferences is None:
        warnings.append("conferences.json: fichier manquant (optionnel)")
    elif not isinstance(conferences, list):
        errors.append("conferences.json: n'est pas un tableau JSON")
    else:
        CONF_REQUIRED = {
            'nom': 'str_required',
            'lieu': 'str',
            'date_debut': 'date_required',
            'date_fin': 'date_required',
            'deadline_abstract': 'date_or_null',
            'url': 'str',
        }
        for i, c in enumerate(conferences):
            label = f"conferences[{i}]"
            for key, typ in CONF_REQUIRED.items():
                err = check_type(c, key, typ, label)
                if err:
                    errors.append(err)
            # Vérifier cohérence date_debut <= date_fin
            d0, d1 = c.get('date_debut', ''), c.get('date_fin', '')
            if d0 and d1 and DATE_RE.match(d0) and DATE_RE.match(d1) and d0 > d1:
                errors.append(f"{label}: date_debut ({d0}) > date_fin ({d1})")
            # Clés interdites (erreur de format fréquente)
            for bad_key in ('dates', 'site_officiel', 'acronyme'):
                if bad_key in c:
                    errors.append(f"{label}: clé '{bad_key}' interdite (voir SCHEMA.md). "
                                  f"Utiliser date_debut/date_fin/url à la place.")

    # ═══════ 3. hors_champ.json ═══════
    hors_champ = load(veille_dir, 'output/hors_champ.json')
    hc_titres = set()
    if hors_champ is None:
        warnings.append("hors_champ.json: fichier manquant (optionnel)")
    elif not isinstance(hors_champ, list):
        errors.append("hors_champ.json: n'est pas un tableau JSON")
    else:
        HC_REQUIRED = {
            'titre': 'str_required',
            'pont_methodologique': 'str_required',
            'pertinence': 'number',
        }
        for i, h in enumerate(hors_champ):
            label = f"hors_champ[{i}]"
            for key, typ in HC_REQUIRED.items():
                err = check_type(h, key, typ, label)
                if err:
                    errors.append(err)
            if h.get('titre'):
                hc_titres.add(h['titre'])
            # Vérification format semaine : W interdit
            sem = h.get('semaine', '')
            if sem and re.match(r'^\d{4}-W\d{2}$', sem):
                errors.append(f"{label}: semaine '{sem}' utilise W au lieu de S")
            # Dépréciation
            if h.get('pont') and not h.get('pont_methodologique'):
                errors.append(f"{label}: utilise 'pont' au lieu de 'pont_methodologique'")
            # ── Anti-hallucination : exiger un identifiant vérifiable ──
            doi = (h.get('doi') or '').strip()
            verified = (h.get('verified_source') or '').strip()
            has_arxiv_url = doi.startswith('http') and 'arxiv.org/abs/' in doi
            has_doi_url = doi.startswith('https://doi.org/') or doi.startswith('http://doi.org/')
            has_raw_doi = doi.startswith('10.')
            if not (has_arxiv_url or has_doi_url or has_raw_doi or verified):
                errors.append(f"{label}: aucun identifiant vérifiable (doi/arxiv URL ou verified_source)")
            # Regex-trap DOI
            if has_raw_doi:
                trap = doi_hallucination_check(doi)
                if trap:
                    errors.append(f"{label}: {trap}")
            # Regex-trap arXiv URL
            if has_arxiv_url:
                m = re.search(r'arxiv\.org/abs/([^\s]+)', doi)
                if m:
                    trap = arxiv_id_hallucination_check(m.group(1).rstrip('/'))
                    if trap:
                        errors.append(f"{label}: {trap}")

    # ═══════ 4. clinical_trials.json — VALIDATION STRICTE ═══════
    trials = load(veille_dir, 'output/clinical_trials.json')
    trial_ncts = set()
    if trials is None:
        warnings.append("clinical_trials.json: fichier manquant (optionnel)")
    elif not isinstance(trials, list):
        errors.append("clinical_trials.json: n'est pas un tableau JSON")
    else:
        CT_REQUIRED = {
            'nct_id': 'str_required',
            'titre': 'str_required',
            'phase': 'str',
            'statut': 'str',
            'sous_type': 'str',
            'resume': 'str',
            'has_ctdna': 'bool',
            'last_updated': 'str',
        }
        VALID_SOUS_TYPES = {'DLBCL', 'FL', 'MCL', 'Hodgkin', 'MW', 'PCNSL', 'DLBCL/FL', 'CLL'}
        for i, t in enumerate(trials):
            label = f"clinical_trials[{i}]"
            for key, typ in CT_REQUIRED.items():
                err = check_type(t, key, typ, label)
                if err:
                    errors.append(err)
            nct = t.get('nct_id', '')
            if nct and not NCT_RE.match(nct):
                errors.append(f"{label}: nct_id '{nct}' format invalide (attendu: NCTxxxxxxxx)")
            if nct:
                if nct in trial_ncts:
                    errors.append(f"{label}: nct_id '{nct}' dupliqué")
                trial_ncts.add(nct)
            st = t.get('sous_type', '')
            if st and st not in VALID_SOUS_TYPES:
                warnings.append(f"{label}: sous_type '{st}' inconnu")

    # ═══════ 5. directions.json ═══════
    directions = load(veille_dir, 'output/directions.json')
    if directions is None:
        warnings.append("directions.json: fichier manquant (optionnel)")
    elif not isinstance(directions, list):
        errors.append("directions.json: n'est pas un tableau JSON")
    else:
        VALID_PRIO = {'haute', 'moyenne', 'basse'}
        for i, d in enumerate(directions):
            label = f"directions[{i}]"
            for key, typ in [('titre', 'str_required'), ('description', 'str_required'),
                             ('priorite', 'str_required'),
                             ('articles_support', 'list'), ('hors_champ_refs', 'list'),
                             ('trials_refs', 'list')]:
                err = check_type(d, key, typ, label)
                if err:
                    errors.append(err)
            prio = d.get('priorite', '')
            if prio and prio not in VALID_PRIO:
                errors.append(f"{label}: priorité '{prio}' invalide (attendu: haute|moyenne|basse)")

            # Références croisées
            for ref_titre in d.get('hors_champ_refs', []):
                if hors_champ is not None and ref_titre not in hc_titres:
                    errors.append(f"{label}: hors_champ_ref '{ref_titre[:50]}...' introuvable dans hors_champ.json")
            for nct in d.get('trials_refs', []):
                if trials is not None and nct not in trial_ncts:
                    errors.append(f"{label}: trials_ref '{nct}' introuvable dans clinical_trials.json")
            for doi in d.get('articles_support', []):
                if articles is not None and doi not in all_dois:
                    warnings.append(f"{label}: article DOI '{doi}' introuvable dans articles_db.json")

        # Hors champ orphelins
        if hors_champ and directions:
            refd = set()
            for d in directions:
                for r in d.get('hors_champ_refs', []):
                    refd.add(r)
            for o in (hc_titres - refd):
                warnings.append(f"hors_champ orphelin (non référencé par une piste): '{o[:60]}...'")

    # ═══════ 6. Vérifier generate_dashboard.py : noms de variables JS ═══════
    dashboard_py = os.path.join(veille_dir, 'outils', 'generate_dashboard.py')
    if os.path.exists(dashboard_py):
        with open(dashboard_py) as f:
            code = f.read()
        FORBIDDEN = {
            'ARTICLES': 'Utiliser DATA (voir SCHEMA.md)',
            'TRIALS': 'Utiliser CLINICAL_TRIALS (voir SCHEMA.md)',
        }
        js_parts = re.findall(r'`[^`]*`', code)
        all_js = ' '.join(js_parts) + ' '
        for forbidden, hint in FORBIDDEN.items():
            pattern = rf'\b{forbidden}\b'
            matches = re.findall(pattern, all_js)
            js_funcs = re.findall(r'function\s+\w+\s*\([^)]*\)\s*\{.*?\n\}', code, re.DOTALL)
            for func in js_funcs:
                matches += re.findall(pattern, func)
            if matches:
                errors.append(f"generate_dashboard.py: variable JS '{forbidden}' utilisée ({len(matches)}x). {hint}")

    # ═══════ 7. Vérifier le HTML généré (si existant) ═══════
    html_path = os.path.join(veille_dir, 'output', 'index.html')
    if os.path.exists(html_path):
        with open(html_path) as f:
            html = f.read()
        if not html.strip().endswith('</html>'):
            errors.append("index.html: ne se termine pas par </html>")
        for section in ['hcSection', 'dirSection', 'trialsSection', 'confSection']:
            if html.count(f'id="{section}"') < 1:
                errors.append(f"index.html: section '{section}' manquante")

    # ═══════ Résultat ═══════
    result = {
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "articles": len(articles) if isinstance(articles, list) else 0,
            "hors_champ": len(hors_champ) if isinstance(hors_champ, list) else 0,
            "directions": len(directions) if isinstance(directions, list) else 0,
            "trials": len(trials) if isinstance(trials, list) else 0,
            "conferences": len(conferences) if isinstance(conferences, list) else 0,
        }
    }
    return result


if __name__ == '__main__':
    veille_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    result = validate(veille_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['errors']:
        print(f"\n❌ {len(result['errors'])} ERREUR(S)")
        for e in result['errors']:
            print(f"  ✗ {e}")
    if result['warnings']:
        print(f"\n⚠️  {len(result['warnings'])} avertissement(s)")
        for w in result['warnings']:
            print(f"  ⚠ {w}")
    if not result['errors'] and not result['warnings']:
        print("\n✅ Tout est conforme au schéma")
    sys.exit(1 if result['errors'] else 0)
