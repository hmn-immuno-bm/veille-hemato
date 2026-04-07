#!/usr/bin/env python3
"""
Audit hebdomadaire de articles_db.json.
Vérifie l'intégrité, détecte les anomalies, produit un rapport.

Usage : python3 outils/audit_db.py <veille_dir>
Sortie : output/audit_report.json + résumé stdout
"""

import json, os, sys, re
from collections import Counter
from datetime import datetime

# ──────────────────────────────────────────────────────────────────
#  Regex-traps anti-hallucination DOI/PMID
# ──────────────────────────────────────────────────────────────────
def doi_hallucination_trap(doi):
    """Retourne un message si le DOI matche un pattern d'hallucination connu.
    Ne contient que des règles universelles pour éviter les faux positifs."""
    if not doi:
        return None
    d = doi.strip()
    # Espaces interdits
    if re.search(r'\s', d):
        return f"DOI contient des espaces: {d}"
    # arXiv ID dans le champ DOI : mois > 12 = invalide
    m = re.match(r'^(?:arxiv:)?(\d{2})(\d{2})\.\d{4,5}', d, re.I)
    if m:
        yy, mm = int(m.group(1)), int(m.group(2))
        if mm < 1 or mm > 12:
            return f"arXiv ID mois invalide ({mm:02d}): {d}"
        if yy > 30:
            return f"arXiv ID année improbable (20{yy:02d}): {d}"
    return None

def load_categories(veille_dir):
    """Charge les labels depuis outils/categories.json (source unique)."""
    path = os.path.join(veille_dir, 'outils', 'categories.json')
    try:
        with open(path) as f:
            data = json.load(f)
        return {c['label'] for c in data['categories']}
    except Exception:
        return {'Hémato générale', 'Lymphomes', 'ctDNA — Lymphomes',
                'ctDNA — Méthodo', 'Immuno + ctDNA/Lymphome', 'IA + Hémato', 'Preprint'}


def run_audit(veille_dir):
    db_path = os.path.join(veille_dir, 'output', 'articles_db.json')
    with open(db_path, encoding='utf-8') as f:
        articles = json.load(f)

    report = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_articles": len(articles),
        "errors": [],
        "warnings": [],
        "stats": {}
    }

    dois = Counter()
    titres_norm = Counter()
    pmids = Counter()

    CATEGORIES = load_categories(veille_dir)

    REQUIRED_FIELDS = ['titre', 'doi', 'journal', 'categorie', 'resume', 'score', 'semaine']

    missing_doi = []
    missing_pmid = []
    missing_fields = []
    invalid_doi_format = []
    invalid_score = []
    invalid_date = []
    invalid_category = []
    duplicate_dois = []
    duplicate_titles = []
    duplicate_pmids = []
    no_resume = []
    no_critique = []
    suspicious_if = []
    hallucination_traps = []

    for i, a in enumerate(articles):
        label = f"[{i}] {a.get('titre', '???')[:60]}"

        # --- Champs obligatoires ---
        for field in REQUIRED_FIELDS:
            val = a.get(field)
            if val is None or (isinstance(val, str) and val.strip() == ''):
                missing_fields.append(f"{label}: champ '{field}' manquant")

        # --- DOI ---
        doi = a.get('doi', '').strip()
        if not doi:
            missing_doi.append(label)
        else:
            if not doi.startswith('10.'):
                invalid_doi_format.append(f"{label}: doi={doi}")
            dois[doi] += 1
            trap = doi_hallucination_trap(doi)
            if trap:
                hallucination_traps.append(f"{label}: {trap}")

        # --- PMID ---
        pmid = a.get('pmid', '').strip()
        if not pmid:
            missing_pmid.append(label)
        else:
            if not pmid.isdigit():
                report["errors"].append(f"{label}: pmid non numérique '{pmid}'")
            pmids[pmid] += 1

        # --- Titre normalisé (détection doublons) ---
        titre_n = re.sub(r'\W+', '', a.get('titre', '')).lower()
        if titre_n:
            titres_norm[titre_n] += 1

        # --- Score ---
        score = a.get('score')
        if score is not None:
            try:
                s = float(score)
                if s < 0 or s > 10:
                    invalid_score.append(f"{label}: score={s}")
            except (ValueError, TypeError):
                invalid_score.append(f"{label}: score non numérique '{score}'")

        # --- IF ---
        if_val = a.get('if_value') or a.get('if_val')
        if if_val is not None:
            try:
                iv = float(if_val)
                if iv > 300:
                    suspicious_if.append(f"{label}: IF={iv}")
            except (ValueError, TypeError):
                pass

        # --- Date ---
        date_pub = a.get('date_pub', '')
        if date_pub:
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_pub):
                # Erreur (pas warning) : update_db.py normalise depuis 2026-04-07
                report["errors"].append(f"{label}: date_pub='{date_pub}' format invalide (attendu YYYY-MM-DD)")

        # --- Catégorie ---
        cat = a.get('categorie', '')
        if cat and cat not in CATEGORIES:
            invalid_category.append(f"{label}: catégorie='{cat}'")

        # --- Résumé / Critique ---
        if not a.get('resume', '').strip():
            no_resume.append(label)
        if not a.get('critique', '').strip():
            no_critique.append(label)

    # --- Doublons ---
    for doi, count in dois.items():
        if count > 1:
            duplicate_dois.append(f"{doi} ({count}x)")
    for titre, count in titres_norm.items():
        if count > 1:
            # Retrouver le vrai titre
            real = next((a['titre'][:60] for a in articles if re.sub(r'\W+', '', a.get('titre', '')).lower() == titre), titre[:60])
            duplicate_titles.append(f"{real}... ({count}x)")
    for pmid, count in pmids.items():
        if count > 1:
            duplicate_pmids.append(f"PMID {pmid} ({count}x)")

    # --- Compilation ---
    if missing_doi:
        report["errors"].append(f"{len(missing_doi)} article(s) sans DOI")
        report["errors"].extend(missing_doi[:5])
    if duplicate_dois:
        report["errors"].append(f"{len(duplicate_dois)} DOI(s) en doublon")
        report["errors"].extend(duplicate_dois)
    if duplicate_pmids:
        report["warnings"].append(f"{len(duplicate_pmids)} PMID(s) en doublon")
        report["warnings"].extend(duplicate_pmids)
    if duplicate_titles:
        report["warnings"].append(f"{len(duplicate_titles)} titre(s) en doublon")
        report["warnings"].extend(duplicate_titles[:10])
    if invalid_doi_format:
        report["errors"].extend(invalid_doi_format)
    if invalid_score:
        report["warnings"].extend(invalid_score)
    if invalid_date:
        report["warnings"].extend(invalid_date)
    if invalid_category:
        report["warnings"].extend(invalid_category)
    if suspicious_if:
        report["warnings"].extend(suspicious_if)
    if missing_fields:
        report["warnings"].append(f"{len(missing_fields)} champ(s) obligatoire(s) manquant(s)")
        report["warnings"].extend(missing_fields[:10])
    if hallucination_traps:
        report["errors"].append(f"{len(hallucination_traps)} DOI matchant un pattern d'hallucination connu")
        report["errors"].extend(hallucination_traps)

    # --- Stats ---
    cats = Counter(a.get('categorie', '?') for a in articles)
    semaines = Counter(a.get('semaine', '?') for a in articles)
    with_pmid = sum(1 for a in articles if a.get('pmid', '').strip())
    with_doi = sum(1 for a in articles if a.get('doi', '').strip())

    report["stats"] = {
        "total": len(articles),
        "avec_doi": with_doi,
        "avec_pmid": with_pmid,
        "sans_resume": len(no_resume),
        "sans_critique": len(no_critique),
        "categories": dict(cats.most_common()),
        "semaines": dict(semaines.most_common()),
        "doublons_doi": len(duplicate_dois),
        "doublons_titre": len(duplicate_titles),
    }

    # --- Écriture rapport ---
    report_path = os.path.join(veille_dir, 'output', 'audit_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # --- Stdout ---
    print(json.dumps({
        "date": report["date"],
        "total": report["total_articles"],
        "errors": len(report["errors"]),
        "warnings": len(report["warnings"]),
        "doublons_doi": len(duplicate_dois),
        "doublons_titre": len(duplicate_titles),
        "sans_doi": len(missing_doi),
        "sans_pmid": len(missing_pmid),
    }, indent=2))

    if report["errors"]:
        print(f"\n❌ {len(report['errors'])} erreur(s):")
        for e in report["errors"]:
            print(f"  • {e}")

    if report["warnings"]:
        print(f"\n⚠️  {len(report['warnings'])} avertissement(s):")
        for w in report["warnings"][:15]:
            print(f"  • {w}")
        if len(report["warnings"]) > 15:
            print(f"  ... et {len(report['warnings']) - 15} de plus (voir audit_report.json)")

    if not report["errors"]:
        print("\n✅ Aucune erreur détectée")

    return report


if __name__ == '__main__':
    veille_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    run_audit(veille_dir)
