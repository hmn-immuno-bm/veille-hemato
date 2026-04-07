#!/usr/bin/env python3
"""
update_db.py — Import d'articles dans la base JSON (remplace update_excel.py).

Usage:
    python3 update_db.py <veille_dir> <articles_json_file>

Le fichier JSON d'import contient une liste d'articles (format court ou long).
La base est stockée dans output/articles_db.json.

Fonctionnalités :
- Déduplication par DOI + titre normalisé
- Détection preprint→publié (mise à jour in-place)
- Accepte clés courtes (digest) et longues (canonique)
"""

import json
import sys
import os
import re
from datetime import datetime, date


def get_week_label(d=None):
    if d is None:
        d = date.today()
    iso = d.isocalendar()
    return f"{iso[0]}-S{iso[1]:02d}"


# --- Normalisation ---

def normalize_keys(art):
    """Accepte les clés courtes (digest) et les convertit au format canonique."""
    aliases = {
        'auteur': 'premier_auteur',
        'senior': 'senior_auteur',
        'tags': 'tag',
        'affFR': 'affiliations_fr',
        'if_val': 'if_value',
    }
    return {aliases.get(k, k): v for k, v in art.items()}


def fix_semaine(s):
    """Corrige le format semaine : W→S, et valide le format."""
    if not s or not isinstance(s, str):
        return get_week_label()
    # Correction W→S (erreur fréquente des tâches planifiées)
    s = re.sub(r'^(\d{4})-W(\d{2})$', r'\1-S\2', s)
    return s


def normalize_date_pub(d):
    """Normalise une date de publication. Tolère YYYY, YYYY-MM, YYYY-MM-DD."""
    if not d or not isinstance(d, str):
        return ''
    d = d.strip()
    # YYYY-MM-DD : OK
    if re.match(r'^\d{4}-\d{2}-\d{2}$', d):
        return d
    # YYYY-MM → YYYY-MM-01
    if re.match(r'^\d{4}-\d{2}$', d):
        return f"{d}-01"
    # YYYY → YYYY-01-01
    if re.match(r'^\d{4}$', d):
        return f"{d}-01-01"
    # Format inconnu : on retourne tel quel et l'audit signalera
    return d


def load_categories(veille_dir):
    """Charge les labels de catégories depuis outils/categories.json."""
    path = os.path.join(veille_dir, 'outils', 'categories.json')
    try:
        with open(path) as f:
            data = json.load(f)
        return {c['label'] for c in data['categories']}
    except Exception:
        return set()


def normalize_article(art):
    """Assure que chaque article a tous les champs avec les bons types."""
    art = normalize_keys(art)
    defaults = {
        'semaine': get_week_label(), 'titre': '', 'premier_auteur': '', 'senior_auteur': '',
        'journal': '', 'doi': '', 'categorie': '', 'tag': '', 'resume': '',
        'metadata': 'OK', 'preprint': 'Publié', 'affiliations_fr': 'Non',
        'if_value': 0, 'score': 0, 'date_pub': '', 'pmid': '', 'critique': '', 'pays': '',
    }
    for k, v in defaults.items():
        if k not in art or art[k] is None or art[k] == '':
            art[k] = v
    # Correction semaine W→S
    art['semaine'] = fix_semaine(art['semaine'])
    # Normalisation date_pub : YYYY-MM → YYYY-MM-01
    if art.get('date_pub'):
        art['date_pub'] = normalize_date_pub(art['date_pub'])
    # Types
    art['if_value'] = float(art['if_value']) if art['if_value'] else 0
    art['score'] = int(art['score']) if art['score'] else 0
    for k in art:
        if art[k] is None:
            art[k] = ''
    return art


def normalize_title(title):
    """Normalise un titre pour comparaison (minuscules, sans ponctuation)."""
    t = str(title or '').lower().strip()
    t = re.sub(r'[^a-z0-9\s]', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t


# --- Base de données ---

def load_db(db_path):
    """Charge la base d'articles existante."""
    if os.path.exists(db_path):
        with open(db_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_db(db_path, articles):
    """Sauvegarde la base d'articles."""
    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


def build_index(db):
    """Construit les index pour déduplication rapide (DOI + PMID + titre)."""
    doi_index = {}
    pmid_index = {}
    title_index = []
    for i, art in enumerate(db):
        doi = str(art.get('doi', '')).strip().lower()
        if doi:
            doi_index[doi] = i
        pmid = str(art.get('pmid', '')).strip()
        if pmid and pmid.isdigit():
            pmid_index[pmid] = i
        title_index.append({
            'idx': i,
            'titre_norm': normalize_title(art.get('titre', '')),
            'preprint': str(art.get('preprint', 'Publié')),
        })
    return doi_index, pmid_index, title_index


def detect_duplicate_or_transition(art, doi_index, pmid_index, title_index):
    """Détecte si un article est un doublon ou une transition preprint→publié.
    Retourne: ('new', None) | ('dup_doi', idx) | ('dup_pmid', idx) | ('dup_title', idx) | ('preprint_to_pub', idx)
    """
    doi = str(art.get('doi', '')).strip().lower()
    pmid = str(art.get('pmid', '')).strip()
    new_preprint = art.get('preprint', 'Publié')

    # 1. Doublon par DOI exact
    if doi and doi in doi_index:
        return ('dup_doi', doi_index[doi])

    # 2. Doublon par PMID exact
    if pmid and pmid.isdigit() and pmid in pmid_index:
        return ('dup_pmid', pmid_index[pmid])

    # 3. Doublon / transition par titre
    new_titre = normalize_title(art.get('titre', ''))
    if not new_titre or len(new_titre) < 15:
        return ('new', None)

    for entry in title_index:
        matched = False
        if entry['titre_norm'] == new_titre:
            matched = True
        elif len(new_titre) > 20 and len(entry['titre_norm']) > 20:
            if new_titre in entry['titre_norm'] or entry['titre_norm'] in new_titre:
                matched = True

        if matched:
            if entry['preprint'].startswith('Preprint') and new_preprint == 'Publié':
                return ('preprint_to_pub', entry['idx'])
            return ('dup_title', entry['idx'])

    return ('new', None)


# --- Import ---

def import_articles(db, new_articles):
    """Importe de nouveaux articles dans la base avec déduplication."""
    doi_index, pmid_index, title_index = build_index(db)
    written = 0
    duplicates = []
    transitions = []

    for art in new_articles:
        art = normalize_article(art)
        status, ref_idx = detect_duplicate_or_transition(art, doi_index, pmid_index, title_index)

        if status in ('dup_doi', 'dup_pmid', 'dup_title'):
            duplicates.append({'titre': art['titre'][:80], 'doi': art['doi'], 'reason': status})
            continue

        if status == 'preprint_to_pub':
            # Mise à jour in-place
            existing = db[ref_idx]
            existing['preprint'] = 'Publié'
            if art['doi']:
                existing['doi'] = art['doi']
            if art['journal']:
                existing['journal'] = art['journal']
            if art['if_value']:
                existing['if_value'] = art['if_value']
            if art['pmid']:
                existing['pmid'] = art['pmid']
            if art['critique'] and not existing.get('critique'):
                existing['critique'] = art['critique']
            transitions.append({'titre': art['titre'][:80], 'new_doi': art['doi']})
            # Mettre à jour les index
            doi = str(art['doi']).strip().lower()
            if doi:
                doi_index[doi] = ref_idx
            pmid = str(art['pmid']).strip()
            if pmid and pmid.isdigit():
                pmid_index[pmid] = ref_idx
            continue

        # Nouvel article
        db.append(art)
        new_idx = len(db) - 1
        doi = str(art['doi']).strip().lower()
        if doi:
            doi_index[doi] = new_idx
        pmid = str(art['pmid']).strip()
        if pmid and pmid.isdigit():
            pmid_index[pmid] = new_idx
        title_index.append({
            'idx': new_idx,
            'titre_norm': normalize_title(art['titre']),
            'preprint': art['preprint'],
        })
        written += 1

    return written, duplicates, transitions


# --- Sentinelle et log ---

def write_sentinel(veille_dir, semaine, nb_articles):
    path = os.path.join(veille_dir, 'outils', 'weekly_search_done.txt')
    with open(path, 'w') as f:
        f.write(f"date: {datetime.now().isoformat()}\n")
        f.write(f"semaine: {semaine}\n")
        f.write(f"nb_articles: {nb_articles}\n")
        f.write("status: OK\n")


def log(veille_dir, message):
    path = os.path.join(veille_dir, 'outils', 'veille_log.txt')
    with open(path, 'a') as f:
        f.write(f"[{date.today()}] {message}\n")


# --- Main ---

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 update_db.py <veille_dir> <articles_json_file>")
        sys.exit(1)

    veille_dir = sys.argv[1]
    json_path = sys.argv[2]

    db_path = os.path.join(veille_dir, 'output', 'articles_db.json')

    # Charger les nouveaux articles
    with open(json_path, 'r', encoding='utf-8') as f:
        new_articles = json.load(f)

    if not new_articles:
        print("Aucun article dans le JSON")
        sys.exit(0)

    semaine = new_articles[0].get('semaine', get_week_label())

    # Charger et mettre à jour la base
    db = load_db(db_path)
    written, duplicates, transitions = import_articles(db, new_articles)

    # Sauvegarder
    save_db(db_path, db)
    write_sentinel(veille_dir, semaine, written)
    log(veille_dir, f"update_db.py — {written} articles écrits, {len(duplicates)} doublons, {len(transitions)} preprint→publié (semaine {semaine})")

    result = {
        "status": "OK",
        "semaine": semaine,
        "articles_written": written,
        "duplicates_detected": len(duplicates),
        "preprint_to_published": len(transitions),
        "total_in_db": len(db),
        "db_path": db_path,
    }
    if duplicates:
        result["duplicate_titles"] = [d['titre'] for d in duplicates]
    if transitions:
        result["transition_titles"] = [t['titre'] for t in transitions]

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
