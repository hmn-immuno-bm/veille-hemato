#!/usr/bin/env python3
"""
generate_dashboard.py — Génère le dashboard HTML de veille hémato.

Usage:
    python3 generate_dashboard.py <veille_dir> [semaine_filter]

Lit articles_db.json et génère index.html dans output/.
Inclut : filtres par catégorie, tri par score/IF, titres cliquables (DOI),
résumés complets, boutons feedback (utile/bof/ignoré) avec export JSON.
"""

import json
import sys
import os
from datetime import date


def get_week_label(d=None):
    if d is None:
        d = date.today()
    iso = d.isocalendar()
    return f"{iso[0]}-S{iso[1]:02d}"


def load_articles(veille_dir, semaine_filter=None):
    """Charge les articles depuis articles_db.json."""
    db_path = os.path.join(veille_dir, 'output', 'articles_db.json')
    if not os.path.exists(db_path):
        return []
    with open(db_path, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    if semaine_filter:
        articles = [a for a in articles if str(a.get('semaine', '')) == semaine_filter]
    return articles


JOURNAL_NORMALIZE = {
    'j clin oncol': 'Journal of Clinical Oncology',
    'jco': 'Journal of Clinical Oncology',
    'journal of clinical oncology': 'Journal of Clinical Oncology',
    'n engl j med': 'New England Journal of Medicine',
    'nejm': 'New England Journal of Medicine',
    'new england journal of medicine': 'New England Journal of Medicine',
    'the new england journal of medicine': 'New England Journal of Medicine',
    'nat med': 'Nature Medicine',
    'nature medicine': 'Nature Medicine',
    'nat rev cancer': 'Nature Reviews Cancer',
    'nature reviews cancer': 'Nature Reviews Cancer',
    'nat rev clin oncol': 'Nature Reviews Clinical Oncology',
    'nature reviews clinical oncology': 'Nature Reviews Clinical Oncology',
    'nat genet': 'Nature Genetics',
    'nature genetics': 'Nature Genetics',
    'lancet oncol': 'Lancet Oncology',
    'the lancet oncology': 'Lancet Oncology',
    'lancet oncology': 'Lancet Oncology',
    'lancet haematol': 'Lancet Haematology',
    'the lancet haematology': 'Lancet Haematology',
    'lancet haematology': 'Lancet Haematology',
    'the lancet': 'The Lancet',
    'lancet': 'The Lancet',
    'j clin invest': 'Journal of Clinical Investigation',
    'jci': 'Journal of Clinical Investigation',
    'journal of clinical investigation': 'Journal of Clinical Investigation',
    'blood': 'Blood',
    'blood advances': 'Blood Advances',
    'blood adv': 'Blood Advances',
    'cancer discov': 'Cancer Discovery',
    'cancer discovery': 'Cancer Discovery',
    'cancer cell': 'Cancer Cell',
    'sci transl med': 'Science Translational Medicine',
    'science translational medicine': 'Science Translational Medicine',
    'ann oncol': 'Annals of Oncology',
    'annals of oncology': 'Annals of Oncology',
    'j hematol oncol': 'Journal of Hematology & Oncology',
    'journal of hematology & oncology': 'Journal of Hematology & Oncology',
    'journal of hematology and oncology': 'Journal of Hematology & Oncology',
    'leukemia': 'Leukemia',
    'haematologica': 'Haematologica',
    'clin cancer res': 'Clinical Cancer Research',
    'clinical cancer research': 'Clinical Cancer Research',
    'brit j haematol': 'British Journal of Haematology',
    'british journal of haematology': 'British Journal of Haematology',
    'br j haematol': 'British Journal of Haematology',
    'eur j cancer': 'European Journal of Cancer',
    'european journal of cancer': 'European Journal of Cancer',
    'biorxiv': 'bioRxiv',
    'medrxiv': 'medRxiv',
    'sci adv': 'Science Advances',
    'science advances': 'Science Advances',
    'nat biotechnol': 'Nature Biotechnology',
    'nature biotechnology': 'Nature Biotechnology',
    'cell': 'Cell',
    'nature': 'Nature',
    'science': 'Science',
    'jama oncol': 'JAMA Oncology',
    'jama oncology': 'JAMA Oncology',
}

TAG_NORMALIZE = {
    'ctdna': 'ctDNA', 'ctDNA': 'ctDNA', 'circulating tumor dna': 'ctDNA',
    'circulating tumor DNA': 'ctDNA', 'cfdna': 'cfDNA', 'cfDNA': 'cfDNA',
    'cell-free dna': 'cfDNA', 'cell-free DNA': 'cfDNA',
    'mrd': 'MRD', 'MRD': 'MRD', 'minimal residual disease': 'MRD',
    'maladie résiduelle': 'MRD', 'measurable residual disease': 'MRD',
    'dlbcl': 'DLBCL', 'DLBCL': 'DLBCL', 'diffuse large b-cell lymphoma': 'DLBCL',
    'diffuse large B-cell lymphoma': 'DLBCL', 'large b-cell lymphoma': 'LBCL',
    'lbcl': 'LBCL', 'LBCL': 'LBCL',
    'car-t': 'CAR-T', 'car t': 'CAR-T', 'CAR-T': 'CAR-T', 'cart': 'CAR-T',
    'CAR T': 'CAR-T', 'car-t cells': 'CAR-T', 'CAR-T cells': 'CAR-T',
    'bispecific': 'Bispecifiques', 'bispecifiques': 'Bispecifiques',
    'bispecific antibody': 'Bispecifiques', 'bispecific antibodies': 'Bispecifiques',
    'anticorps bispecifiques': 'Bispecifiques', 'anticorps bispecifique': 'Bispecifiques',
    't-cell engaging': 'Bispecifiques',
    'ngs': 'NGS', 'NGS': 'NGS', 'next-generation sequencing': 'NGS',
    'next generation sequencing': 'NGS',
    'liquid biopsy': 'Biopsie liquide', 'biopsie liquide': 'Biopsie liquide',
    'fragmentomics': 'Fragmentomique', 'fragmentomique': 'Fragmentomique',
    'fragmentomic': 'Fragmentomique',
    'pronostic': 'Pronostic', 'prognosis': 'Pronostic', 'pronostique': 'Pronostic',
    'prognostic': 'Pronostic',
    'machine learning': 'Machine Learning', 'deep learning': 'Deep Learning',
    'artificial intelligence': 'IA', 'intelligence artificielle': 'IA',
    'immunotherapy': 'Immunothérapie', 'immunothérapie': 'Immunothérapie',
    'immune checkpoint': 'Checkpoints immunitaires', 'checkpoint inhibitor': 'Checkpoints immunitaires',
    'pd-1': 'PD-1', 'pd-l1': 'PD-L1', 'PD-1': 'PD-1', 'PD-L1': 'PD-L1',
    'hodgkin': 'Hodgkin', 'hodgkin lymphoma': 'Hodgkin',
    'lymphome hodgkin': 'Hodgkin', "hodgkin's lymphoma": 'Hodgkin',
    'follicular lymphoma': 'Lymphome folliculaire', 'lymphome folliculaire': 'Lymphome folliculaire',
    'mantle cell lymphoma': 'Lymphome du manteau', 'mcl': 'Lymphome du manteau',
    'aml': 'LAM', 'lam': 'LAM', 'acute myeloid leukemia': 'LAM',
    'classification': 'Classification', 'classification moléculaire': 'Classification',
    'molecular classification': 'Classification',
    'venetoclax': 'Venetoclax', 'ibrutinib': 'Ibrutinib',
    'phasedseq': 'PhasED-Seq', 'phased-seq': 'PhasED-Seq', 'PhasED-Seq': 'PhasED-Seq',
    'capp-seq': 'CAPP-Seq', 'capp seq': 'CAPP-Seq', 'CAPP-Seq': 'CAPP-Seq',
    'glofitamab': 'Glofitamab', 'epcoritamab': 'Epcoritamab',
    'mosunetuzumab': 'Mosunetuzumab', 'polatuzumab': 'Polatuzumab',
    'clinical trial': 'Essai clinique', 'essai clinique': 'Essai clinique',
    'phase 3': 'Phase 3', 'phase iii': 'Phase 3', 'phase 2': 'Phase 2', 'phase ii': 'Phase 2',
    'survival': 'Survie', 'survie': 'Survie', 'overall survival': 'Survie',
    'response': 'Réponse', 'réponse': 'Réponse', 'treatment response': 'Réponse',
    'lymphome t': 'Lymphomes T', 'lymphomes t': 'Lymphomes T',
    't-cell lymphoma': 'Lymphomes T', 'ptcl': 'Lymphomes T',
    'swgs': 'sWGS', 'shallow whole genome sequencing': 'sWGS',
    'whole exome sequencing': 'WES', 'wes': 'WES',
    'dpcr': 'dPCR', 'digital pcr': 'dPCR', 'ddpcr': 'dPCR',
    'methylation': 'Méthylation', 'méthylation': 'Méthylation',
    'microenvironment': 'Microenvironnement', 'microenvironnement': 'Microenvironnement',
    'tumor microenvironment': 'Microenvironnement', 'tme': 'Microenvironnement',
}


COUNTRY_NORMALIZE = {
    'usa': 'US', 'us': 'US', 'united states': 'US', 'états-unis': 'US',
    'uk': 'GB', 'united kingdom': 'GB', 'england': 'GB', 'royaume-uni': 'GB',
    'china': 'CN', 'chine': 'CN',
    'germany': 'DE', 'allemagne': 'DE',
    'france': 'FR',
    'italy': 'IT', 'italie': 'IT',
    'spain': 'ES', 'espagne': 'ES',
    'japan': 'JP', 'japon': 'JP',
    'south korea': 'KR', 'korea': 'KR', 'corée': 'KR',
    'canada': 'CA',
    'australia': 'AU', 'australie': 'AU',
    'netherlands': 'NL', 'pays-bas': 'NL',
    'belgium': 'BE', 'belgique': 'BE',
    'switzerland': 'CH', 'suisse': 'CH',
    'sweden': 'SE', 'suède': 'SE',
    'denmark': 'DK', 'danemark': 'DK',
    'norway': 'NO', 'norvège': 'NO',
    'austria': 'AT', 'autriche': 'AT',
    'finland': 'FI', 'finlande': 'FI',
    'israel': 'IL', 'israël': 'IL',
    'brazil': 'BR', 'brésil': 'BR',
    'india': 'IN', 'inde': 'IN',
    'taiwan': 'TW', 'taïwan': 'TW',
    'international': '', 'intl': '', 'multicenter': '', 'multicentrique': '',
}


def normalize_country(code):
    """Normalise un code pays vers ISO 2 lettres."""
    if not code:
        return ''
    key = code.strip().lower()
    if key in COUNTRY_NORMALIZE:
        return COUNTRY_NORMALIZE[key]
    # Already a 2-letter code?
    if len(code.strip()) == 2:
        return code.strip().upper()
    return code.strip()


def normalize_journal(name):
    """Normalise un nom de journal vers sa forme canonique."""
    key = name.strip().lower().rstrip('.')
    return JOURNAL_NORMALIZE.get(key, name.strip())


def normalize_tags(tags_str):
    """Normalise et consolide les tags."""
    if not tags_str:
        return ""
    tags = [t.strip() for t in tags_str.split(',') if t.strip()]
    normalized = []
    seen = set()
    for t in tags:
        key = t.strip().lower()
        canonical = TAG_NORMALIZE.get(key, TAG_NORMALIZE.get(t.strip(), t.strip()))
        if canonical.lower() not in seen:
            normalized.append(canonical)
            seen.add(canonical.lower())
    return ', '.join(normalized)


def articles_to_js(articles):
    """Convertit les articles en données JS pour le dashboard."""
    js_articles = []
    for a in articles:
        doi = str(a.get("doi", "") or "").strip()
        # Flag suspect DOIs (placeholders, missing)
        if doi and ('XXX' in doi or 'xxx' in doi or not doi.startswith('10.')):
            import sys
            print(f"⚠️  DOI suspect: {doi} — {a.get('titre', '')[:60]}", file=sys.stderr)
            doi = ""  # Don't generate a broken link
        doi_url = f"https://doi.org/{doi}" if doi and not doi.startswith("http") else doi
        if_val = a.get("if_value", 0) or 0
        score = a.get("score", 0) or 0
        js_articles.append({
            "semaine": str(a.get("semaine", "")),
            "titre": str(a.get("titre", "")),
            "auteur": str(a.get("premier_auteur", "")),
            "senior": str(a.get("senior_auteur", "")),
            "journal": normalize_journal(str(a.get("journal", ""))),
            "doi": doi,
            "doi_url": doi_url,
            "categorie": str(a.get("categorie", "")),
            "tags": normalize_tags(str(a.get("tag", ""))),
            "resume": str(a.get("resume", "") or ""),
            "metadata": str(a.get("metadata", "OK")),
            "preprint": str(a.get("preprint", "Publié")),
            "affFR": str(a.get("affiliations_fr", "Non")),
            "if_val": float(if_val) if if_val else 0,
            "score": int(score) if score else 0,
            "date_pub": str(a.get("date_pub", "") or ""),
            "pmid": str(a.get("pmid", "") or ""),
            "critique": str(a.get("critique", "") or ""),
            "pays": normalize_country(str(a.get("pays", "") or "")),
            "citations": int(a.get("citation_count", 0) or 0),
        })
    return js_articles



def load_dashboard_template():
    """Charge le template HTML du dashboard et inline le CSS + JS depuis
    leurs fichiers séparés (dashboard.css et dashboard.js).

    Cette séparation permet d'éditer le CSS et le JS sans toucher au HTML
    et bénéficie de la coloration syntaxique de l'éditeur. Les placeholders
    %%DATA%%, %%CONFERENCES%%, etc. restent dans le JS et sont remplacés
    par generate() comme avant.
    """
    here = os.path.dirname(__file__)
    template_path = os.path.join(here, 'dashboard_template.html')
    css_path = os.path.join(here, 'dashboard.css')
    js_path = os.path.join(here, 'dashboard.js')

    if not os.path.exists(template_path):
        print(f"Erreur: fichier template non trouvé à {template_path}", file=sys.stderr)
        sys.exit(1)
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Inline CSS si le placeholder est présent
    if '%%CSS%%' in html and os.path.exists(css_path):
        with open(css_path, 'r', encoding='utf-8') as f:
            html = html.replace('%%CSS%%', f.read())
    # Inline JS si le placeholder est présent
    if '%%JS%%' in html and os.path.exists(js_path):
        with open(js_path, 'r', encoding='utf-8') as f:
            html = html.replace('%%JS%%', f.read())

    return html



def generate(veille_dir, semaine_filter=None):
    # Validation automatique du schéma avant génération
    try:
        from validate_schema import validate
        result = validate(veille_dir)
        if result['errors']:
            print(json.dumps({"status": "SCHEMA_ERROR", "errors": result['errors']}, ensure_ascii=False, indent=2))
            print(f"\n❌ {len(result['errors'])} erreur(s) de schéma — dashboard NON généré")
            sys.exit(1)
        if result['warnings']:
            for w in result['warnings']:
                print(f"⚠ {w}", file=sys.stderr)
    except ImportError:
        pass  # validate_schema.py absent — on continue

    articles = load_articles(veille_dir, semaine_filter)
    if not articles:
        print("Aucun article trouvé dans articles_db.json")
        sys.exit(0)

    if semaine_filter:
        semaine = semaine_filter
    else:
        # Take the most recent ISO-format semaine (YYYY-SNN)
        iso_sems = [a.get("semaine", "") for a in articles if a.get("semaine", "").startswith("20") and "-S" in a.get("semaine", "") and "retro" not in a.get("semaine", "")]
        semaine = max(iso_sems) if iso_sems else articles[0].get("semaine", get_week_label())
    semaine_safe = str(semaine).replace(" ", "_").replace("/", "-")
    js_data = articles_to_js(articles)

    date_gen = date.today().strftime("%d/%m/%Y")

    # Load key authors — JSON en priorité (riche), TXT en fallback (legacy)
    key_authors = []
    ka_json = os.path.join(veille_dir, 'outils', 'auteurs_cles.json')
    ka_txt = os.path.join(veille_dir, 'outils', 'auteurs_cles.txt')
    if os.path.exists(ka_json):
        try:
            with open(ka_json, 'r', encoding='utf-8') as f:
                ka_data = json.load(f)
            key_authors = [a['nom'] for a in ka_data.get('auteurs', []) if a.get('nom')]
        except Exception:
            pass
    if not key_authors and os.path.exists(ka_txt):
        with open(ka_txt, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key_authors.append(line)

    # Conferences placeholder (empty for now — populated by conference-alert task)
    conferences = []
    conf_path = os.path.join(veille_dir, 'output', 'conferences.json')
    if os.path.exists(conf_path):
        try:
            with open(conf_path, 'r', encoding='utf-8') as f:
                conferences = json.load(f)
        except Exception:
            pass

    # Load existing feedback files into a {doi: rating} map
    saved_feedback = {}
    output_dir = os.path.join(veille_dir, 'output')
    for fname in sorted(os.listdir(output_dir)):
        if fname.startswith('feedback_') and fname.endswith('.json'):
            try:
                with open(os.path.join(output_dir, fname), 'r', encoding='utf-8') as f:
                    fb_data = json.load(f)
                for entry in fb_data:
                    if entry.get('doi') and entry.get('feedback') and entry['feedback'] != 'non noté':
                        saved_feedback[entry['doi']] = entry['feedback']
            except Exception:
                pass

    # Hors champ articles
    hors_champ = []
    hc_path = os.path.join(veille_dir, 'output', 'hors_champ.json')
    if os.path.exists(hc_path):
        try:
            with open(hc_path, 'r', encoding='utf-8') as f:
                hors_champ = json.load(f)
        except Exception:
            pass

    # Research directions
    directions = []
    dir_path = os.path.join(veille_dir, 'output', 'directions.json')
    if os.path.exists(dir_path):
        try:
            with open(dir_path, 'r', encoding='utf-8') as f:
                directions = json.load(f)
        except Exception:
            pass

    # Clinical trials
    clinical_trials = []
    ct_path = os.path.join(veille_dir, 'output', 'clinical_trials.json')
    if os.path.exists(ct_path):
        try:
            with open(ct_path, 'r', encoding='utf-8') as f:
                clinical_trials = json.load(f)
        except Exception:
            pass

    # Load world map base64
    world_map_b64 = ''
    map_path = os.path.join(veille_dir, 'outils', 'world_map.b64')
    if os.path.exists(map_path):
        with open(map_path, 'r') as f:
            world_map_b64 = f.read().strip()

    html = load_dashboard_template()
    html = html.replace("%%WORLD_MAP_B64%%", world_map_b64)
    html = html.replace("%%SEMAINE%%", str(semaine))
    html = html.replace("%%SEMAINE_SAFE%%", semaine_safe)
    html = html.replace("%%DATE_GEN%%", date_gen)
    html = html.replace("%%DATA%%", json.dumps(js_data, ensure_ascii=False, indent=2))
    html = html.replace("%%HORS_CHAMP%%", json.dumps(hors_champ, ensure_ascii=False))
    html = html.replace("%%DIRECTIONS%%", json.dumps(directions, ensure_ascii=False))
    html = html.replace("%%KEY_AUTHORS%%", json.dumps(key_authors, ensure_ascii=False))
    html = html.replace("%%CONFERENCES%%", json.dumps(conferences, ensure_ascii=False))
    html = html.replace("%%CLINICAL_TRIALS%%", json.dumps(clinical_trials, ensure_ascii=False))
    html = html.replace("%%FEEDBACK%%", json.dumps(saved_feedback, ensure_ascii=False))

    output_path = os.path.join(veille_dir, 'output', 'index.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(json.dumps({
        "status": "OK",
        "semaine": str(semaine),
        "nb_articles": len(articles),
        "dashboard_path": output_path
    }, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_dashboard.py <veille_dir> [semaine_filter]")
        sys.exit(1)

    veille_dir = sys.argv[1]
    semaine_filter = sys.argv[2] if len(sys.argv) > 2 else None
    generate(veille_dir, semaine_filter)


if __name__ == '__main__':
    main()
