#!/usr/bin/env python3
"""
consolidate_feedback.py — Consolide les fichiers feedback_*.json mensuellement.

Usage:
    python3 consolidate_feedback.py <veille_dir>

Fusionne tous les fichiers feedback_*.json (hors semaine en cours)
dans feedback_consolidated.json, puis supprime les originaux fusionnés.
Garde une copie n-1 (feedback_consolidated_prev.json) comme filet de sécurité.
"""

import json
import sys
import os
import glob
import re
from datetime import date


def get_current_iso_week():
    """Retourne la semaine ISO courante sous forme 'YYYY-SWW'."""
    d = date.today()
    iso = d.isocalendar()
    return f"{iso[0]}-S{iso[1]:02d}"


def extract_week_from_filename(filename):
    """Extrait la semaine du nom de fichier feedback_YYYY-SWW.json."""
    basename = os.path.basename(filename)
    m = re.search(r'feedback_(\d{4}-[SW]\d{2})', basename)
    if m:
        return m.group(1)
    return None


def consolidate(veille_dir):
    output_dir = os.path.join(veille_dir, 'output')
    consolidated_path = os.path.join(output_dir, 'feedback_consolidated.json')
    prev_path = os.path.join(output_dir, 'feedback_consolidated_prev.json')

    # Charger le fichier consolidé existant
    existing = []
    existing_dois = set()
    if os.path.exists(consolidated_path):
        with open(consolidated_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
            for entry in existing:
                doi = entry.get('doi', '')
                if doi:
                    existing_dois.add(doi)

    # Trouver tous les feedback_*.json (sauf consolidated/prev)
    pattern = os.path.join(output_dir, 'feedback_*.json')
    files = sorted(glob.glob(pattern))
    files = [f for f in files if 'consolidated' not in os.path.basename(f)]

    if not files:
        return {
            'status': 'OK',
            'message': 'Aucun fichier feedback à consolider',
            'consolidated_count': len(existing),
            'deleted': 0,
        }

    current_week = get_current_iso_week()
    to_consolidate = []
    to_keep = []

    for fp in files:
        week = extract_week_from_filename(fp)
        if week and week == current_week:
            to_keep.append(fp)
        else:
            to_consolidate.append(fp)

    if not to_consolidate:
        return {
            'status': 'OK',
            'message': 'Seuls des fichiers de la semaine en cours — rien à consolider',
            'consolidated_count': len(existing),
            'deleted': 0,
        }

    # Fusionner les feedbacks
    new_entries = []
    for fp in to_consolidate:
        with open(fp, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for entry in data:
                doi = entry.get('doi', '')
                if doi and doi in existing_dois:
                    # Le plus récent gagne
                    for i, ex in enumerate(existing):
                        if ex.get('doi') == doi:
                            existing[i] = entry
                            break
                else:
                    new_entries.append(entry)
                    if doi:
                        existing_dois.add(doi)

    consolidated = existing + new_entries

    # Sauvegarder version n-1 (écraser l'éventuel prev existant)
    if os.path.exists(consolidated_path):
        if os.path.exists(prev_path):
            os.remove(prev_path)
        os.rename(consolidated_path, prev_path)

    # Écrire le nouveau consolidé
    with open(consolidated_path, 'w', encoding='utf-8') as f:
        json.dump(consolidated, f, ensure_ascii=False, indent=2)

    # Supprimer les fichiers fusionnés
    deleted = 0
    for fp in to_consolidate:
        os.remove(fp)
        deleted += 1

    return {
        'status': 'OK',
        'consolidated_count': len(consolidated),
        'new_entries': len(new_entries),
        'deleted': deleted,
        'kept_current_week': len(to_keep),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 consolidate_feedback.py <veille_dir>")
        sys.exit(1)

    veille_dir = sys.argv[1]
    result = consolidate(veille_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
