#!/usr/bin/env python3
"""
analyze_feedback.py — Analyse les feedbacks cumulés et génère des préférences utilisateur.

Usage:
    python3 analyze_feedback.py <veille_dir>

Lit tous les fichiers feedback_*.json dans output/,
puis génère :
1. Un fichier output/preferences.json avec les patterns détectés
2. Un paragraphe texte à injecter dans le prompt du digest
3. Des poids de scoring calibrés par régression OLS (si ≥ 10 feedbacks)

Le fichier preferences.json est cumulatif et s'enrichit au fil du temps.
"""

import json
import sys
import os
import glob
import math
from collections import Counter, defaultdict


def load_feedback_files(output_dir):
    """Charge feedback_consolidated.json + les feedback_*.json restants."""
    all_feedback = []
    seen_dois = set()

    # 1. Charger le consolidé en premier
    consolidated = os.path.join(output_dir, 'feedback_consolidated.json')
    if os.path.exists(consolidated):
        with open(consolidated, 'r', encoding='utf-8') as f:
            for entry in json.load(f):
                if entry.get('feedback') and entry['feedback'] != 'non noté':
                    all_feedback.append(entry)
                    doi = entry.get('doi', '')
                    if doi:
                        seen_dois.add(doi)

    # 2. Charger les feedback_*.json restants (semaine en cours, etc.)
    pattern = os.path.join(output_dir, 'feedback_*.json')
    for fp in sorted(glob.glob(pattern)):
        if 'consolidated' in os.path.basename(fp):
            continue
        with open(fp, 'r', encoding='utf-8') as f:
            for entry in json.load(f):
                if entry.get('feedback') and entry['feedback'] != 'non noté':
                    doi = entry.get('doi', '')
                    if doi and doi in seen_dois:
                        # Plus récent gagne
                        for i, ex in enumerate(all_feedback):
                            if ex.get('doi') == doi:
                                all_feedback[i] = entry
                                break
                    else:
                        all_feedback.append(entry)
                        if doi:
                            seen_dois.add(doi)
    return all_feedback


def analyze(feedbacks):
    """Analyse les patterns de feedback."""
    if not feedbacks:
        return None

    stats = {
        'total': len(feedbacks),
        'utile': 0, 'bof': 0, 'ignore': 0,
        'by_category': defaultdict(lambda: {'utile': 0, 'bof': 0, 'ignore': 0, 'total': 0}),
        'by_journal': defaultdict(lambda: {'utile': 0, 'bof': 0, 'ignore': 0, 'total': 0}),
        'by_score': defaultdict(lambda: {'utile': 0, 'bof': 0, 'ignore': 0, 'total': 0}),
        'by_tag': defaultdict(lambda: {'utile': 0, 'bof': 0, 'ignore': 0, 'total': 0}),
        'utile_keywords': [],
        'ignore_keywords': [],
    }

    for fb in feedbacks:
        val = fb['feedback']
        stats[val] = stats.get(val, 0) + 1

        cat = fb.get('categorie', 'Inconnu')
        stats['by_category'][cat][val] += 1
        stats['by_category'][cat]['total'] += 1

        journal = fb.get('journal', '')
        if journal:
            stats['by_journal'][journal][val] += 1
            stats['by_journal'][journal]['total'] += 1

        score = fb.get('score', 0)
        bucket = f"{(score // 3) * 3}-{(score // 3) * 3 + 2}"
        stats['by_score'][bucket][val] += 1
        stats['by_score'][bucket]['total'] += 1

        # Tags
        tags_str = fb.get('tags', fb.get('tag', ''))
        if tags_str:
            for tag in tags_str.split(','):
                tag = tag.strip()
                if tag:
                    stats['by_tag'][tag][val] += 1
                    stats['by_tag'][tag]['total'] += 1

        # Collect keywords from titles
        titre = fb.get('titre', '')
        if val == 'utile':
            stats['utile_keywords'].append(titre)
        elif val == 'ignore':
            stats['ignore_keywords'].append(titre)

    return stats


def generate_preferences(stats):
    """Génère les préférences structurées."""
    if not stats or stats['total'] < 3:
        return None

    prefs = {
        'total_feedbacks': stats['total'],
        'taux_utile': round(stats['utile'] / stats['total'] * 100, 1),
        'categories_preferees': [],
        'categories_ignorees': [],
        'tags_preferes': [],
        'tags_ignores': [],
        'score_adjustments': [],
    }

    # Catégories préférées/ignorées
    for cat, vals in stats['by_category'].items():
        if vals['total'] < 2:
            continue
        taux_utile = vals['utile'] / vals['total']
        taux_ignore = vals['ignore'] / vals['total']
        if taux_utile >= 0.6:
            prefs['categories_preferees'].append(cat)
        elif taux_ignore >= 0.5:
            prefs['categories_ignorees'].append(cat)

    # Tags préférés/ignorés
    for tag, vals in stats['by_tag'].items():
        if vals['total'] < 2:
            continue
        taux_utile = vals['utile'] / vals['total']
        taux_ignore = vals['ignore'] / vals['total']
        if taux_utile >= 0.6:
            prefs['tags_preferes'].append(tag)
        elif taux_ignore >= 0.5:
            prefs['tags_ignores'].append(tag)

    # Détection de patterns dans les scores
    for bucket, vals in stats['by_score'].items():
        if vals['total'] < 2:
            continue
        taux_ignore = vals['ignore'] / vals['total']
        if taux_ignore >= 0.6:
            prefs['score_adjustments'].append(
                f"Articles score {bucket} souvent ignorés ({taux_ignore*100:.0f}%)"
            )

    return prefs


# ---------------------------------------------------------------------------
# Calibration par régression OLS
# ---------------------------------------------------------------------------

# Mapping catégorie → score thème (grille de base)
THEME_MAP = {
    'ctDNA — Lymphomes': 4, 'Immuno + ctDNA/Lymphome': 4,
    'ctDNA — Méthodo': 3, 'Lymphomes': 3,
    'IA + Hémato': 2, 'Hémato générale': 2, 'Preprint': 2,
}

# Feedback → cible numérique
FEEDBACK_TARGET = {'utile': 1.0, 'bof': 0.4, 'ignore': 0.0}


def _extract_features(fb):
    """Extrait un vecteur de features depuis un feedback.

    Features (5 dims):
      0: theme_score     (0-4, d'après la catégorie)
      1: if_norm         (0-3, IF normalisé)
      2: is_ctdna        (0/1)
      3: is_lymphome     (0/1)
      4: is_fr           (0/1, affiliation française)
    """
    cat = fb.get('categorie', '')
    theme = THEME_MAP.get(cat, 2)

    if_val = fb.get('if_value', fb.get('if_val', 0)) or 0
    try:
        if_val = float(if_val)
    except (ValueError, TypeError):
        if_val = 0
    if if_val >= 50:
        if_norm = 3
    elif if_val >= 20:
        if_norm = 2.5
    elif if_val >= 10:
        if_norm = 2
    elif if_val >= 5:
        if_norm = 1
    else:
        if_norm = 0

    tags_str = str(fb.get('tags', fb.get('tag', ''))).lower()
    is_ctdna = 1 if 'ctdna' in tags_str or 'ctdna' in cat.lower() else 0
    is_lymphome = 1 if 'lymphom' in tags_str or 'lymphom' in cat.lower() else 0

    aff_fr = str(fb.get('affiliations_fr', fb.get('affFR', ''))).lower()
    is_fr = 1 if aff_fr == 'oui' else 0

    return [theme, if_norm, is_ctdna, is_lymphome, is_fr]


FEATURE_NAMES = ['theme', 'impact_factor', 'ctdna', 'lymphome', 'affiliation_fr']
DEFAULT_WEIGHTS = [0.40, 0.25, 0.15, 0.10, 0.10]


def _ols_regression(X, y):
    """Régression OLS en pur Python (X @ beta = y, moindres carrés).

    Résout beta = (X^T X)^{-1} X^T y via élimination de Gauss.
    Retourne (beta, r_squared).
    """
    n = len(y)
    p = len(X[0])

    # X^T X
    XtX = [[0.0] * p for _ in range(p)]
    for i in range(p):
        for j in range(p):
            s = 0.0
            for k in range(n):
                s += X[k][i] * X[k][j]
            XtX[i][j] = s

    # X^T y
    Xty = [0.0] * p
    for i in range(p):
        s = 0.0
        for k in range(n):
            s += X[k][i] * y[k]
        Xty[i] = s

    # Résolution (X^T X) beta = X^T y par élimination de Gauss avec pivot partiel
    # Matrice augmentée
    aug = [XtX[i][:] + [Xty[i]] for i in range(p)]

    for col in range(p):
        # Pivot partiel
        max_row = col
        max_val = abs(aug[col][col])
        for row in range(col + 1, p):
            if abs(aug[row][col]) > max_val:
                max_val = abs(aug[row][col])
                max_row = row
        if max_val < 1e-12:
            return None, 0.0  # Matrice singulière
        aug[col], aug[max_row] = aug[max_row], aug[col]

        pivot = aug[col][col]
        for j in range(col, p + 1):
            aug[col][j] /= pivot
        for row in range(p):
            if row == col:
                continue
            factor = aug[row][col]
            for j in range(col, p + 1):
                aug[row][j] -= factor * aug[col][j]

    beta = [aug[i][p] for i in range(p)]

    # R² = 1 - SS_res / SS_tot
    y_mean = sum(y) / n
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    ss_res = 0.0
    for k in range(n):
        pred = sum(X[k][j] * beta[j] for j in range(p))
        ss_res += (y[k] - pred) ** 2
    r2 = 1 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0

    return beta, r2


def calibrate_scoring(feedbacks, articles_db=None):
    """Calibre les poids du scoring par régression sur les feedbacks.

    Retourne un dict avec :
      - weights: {feature: poids_normalisé} (somme = 1)
      - r_squared: qualité du fit
      - n_samples: nombre de feedbacks utilisés
      - formula: formule textuelle pour le prompt
      - raw_beta: coefficients bruts de la régression
    Retourne None si < 10 feedbacks exploitables.
    """
    # Enrichir les feedbacks avec les données d'articles si disponible
    if articles_db:
        db_index = {}
        for a in articles_db:
            doi = a.get('doi', '')
            if doi:
                db_index[doi.lower()] = a
            titre_norm = a.get('titre', '').strip().lower()
            if titre_norm:
                db_index[titre_norm] = a
        for fb in feedbacks:
            doi = fb.get('doi', '').lower()
            titre = fb.get('titre', '').strip().lower()
            ref = db_index.get(doi) or db_index.get(titre)
            if ref:
                for key in ['categorie', 'if_value', 'tag', 'affiliations_fr']:
                    if key not in fb or not fb[key]:
                        fb[key] = ref.get(key, '')

    # Construction matrice
    X = []
    y = []
    for fb in feedbacks:
        target = FEEDBACK_TARGET.get(fb.get('feedback', ''))
        if target is None:
            continue
        features = _extract_features(fb)
        # Vérifier qu'on a au moins des features non-nulles
        if all(f == 0 for f in features):
            continue
        X.append(features)
        y.append(target)

    if len(X) < 10:
        return None

    # Filtrer les features sans variance (constante → matrice singulière)
    p = len(FEATURE_NAMES)
    active_idx = []
    for j in range(p):
        vals = set(row[j] for row in X)
        if len(vals) > 1:
            active_idx.append(j)

    if len(active_idx) < 2:
        return None  # Pas assez de features variables

    X_active = [[row[j] for j in active_idx] for row in X]
    active_names = [FEATURE_NAMES[j] for j in active_idx]

    # Régression OLS sur les features actives
    beta_active, r2 = _ols_regression(X_active, y)
    if beta_active is None:
        return None

    # Reconstruire beta complet (0 pour features inactives)
    beta = [0.0] * p
    for k, j in enumerate(active_idx):
        beta[j] = beta_active[k]

    # Normaliser les poids (ramener à somme = 1, en gardant le signe)
    abs_sum = sum(abs(b) for b in beta)
    if abs_sum < 1e-12:
        return None

    weights = {}
    for i, name in enumerate(FEATURE_NAMES):
        weights[name] = round(beta[i] / abs_sum, 3)

    # Formule lisible pour le prompt
    formula_parts = []
    for name, w in weights.items():
        sign = "+" if w >= 0 else ""
        formula_parts.append(f"{name}: {sign}{w:.2f}")

    # Score max estimé (somme des contributions positives aux features max)
    max_features = [4, 3, 1, 1, 1]  # max de chaque feature
    score_max_raw = sum(beta[i] * max_features[i] for i in range(len(beta)))

    return {
        'weights': weights,
        'r_squared': round(r2, 3),
        'n_samples': len(X),
        'raw_beta': [round(b, 4) for b in beta],
        'score_max_raw': round(score_max_raw, 2),
        'formula': ", ".join(formula_parts),
    }


def generate_prompt_paragraph(prefs, calibration=None):
    """Génère un paragraphe à injecter dans le prompt du digest."""
    if not prefs:
        return ""

    lines = ["### Préférences utilisateur (apprises du feedback)"]
    lines.append(f"Basé sur {prefs['total_feedbacks']} articles notés ({prefs['taux_utile']}% jugés utiles).")

    if prefs['categories_preferees']:
        lines.append(f"**Catégories préférées** (bonus +1 au score) : {', '.join(prefs['categories_preferees'])}")

    if prefs['categories_ignorees']:
        lines.append(f"**Catégories peu utiles** (malus -1 au score) : {', '.join(prefs['categories_ignorees'])}")

    if prefs['tags_preferes']:
        lines.append(f"**Tags préférés** (prioriser) : {', '.join(prefs['tags_preferes'])}")

    if prefs['tags_ignores']:
        lines.append(f"**Tags ignorés** (dé-prioriser) : {', '.join(prefs['tags_ignores'])}")

    if prefs['score_adjustments']:
        for adj in prefs['score_adjustments']:
            lines.append(f"- {adj}")

    # Intégrer les poids calibrés si disponibles
    if calibration and calibration.get('r_squared', 0) >= 0.15:
        lines.append("")
        lines.append(f"### Scoring calibré (régression OLS, R²={calibration['r_squared']:.2f}, n={calibration['n_samples']})")
        lines.append("Pondération optimale des composantes du score :")
        w = calibration['weights']
        lines.append(f"  - Thème (pertinence catégorie) : **{w.get('theme', 0.40):.0%}**")
        lines.append(f"  - Impact Factor normalisé : **{w.get('impact_factor', 0.25):.0%}**")
        lines.append(f"  - Pertinence ctDNA : **{w.get('ctdna', 0.15):.0%}**")
        lines.append(f"  - Pertinence lymphome : **{w.get('lymphome', 0.10):.0%}**")
        lines.append(f"  - Affiliation française : **{w.get('affiliation_fr', 0.10):.0%}**")
        lines.append("")
        lines.append("Utiliser ces poids pour pondérer le score final (sur 10) plutôt que la grille fixe.")
    else:
        lines.append("")
        lines.append("Appliquer ces ajustements au scoring final (+1/-1) sans modifier la grille de base.")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_feedback.py <veille_dir>")
        sys.exit(1)

    veille_dir = sys.argv[1]
    output_dir = os.path.join(veille_dir, 'output')

    feedbacks = load_feedback_files(output_dir)

    if not feedbacks:
        print(json.dumps({
            "status": "NO_DATA",
            "message": "Aucun feedback trouvé. Utilise le dashboard pour noter les articles.",
            "prompt_paragraph": "",
            "calibration": None,
        }, ensure_ascii=False, indent=2))
        return

    # Charger la base articles pour enrichir les feedbacks
    db_path = os.path.join(output_dir, 'articles_db.json')
    articles_db = []
    if os.path.exists(db_path):
        with open(db_path, 'r', encoding='utf-8') as f:
            articles_db = json.load(f)

    stats = analyze(feedbacks)
    prefs = generate_preferences(stats)

    # Calibration par régression
    calibration = calibrate_scoring(feedbacks, articles_db)

    prompt_para = generate_prompt_paragraph(prefs, calibration)

    # Sauvegarder preferences.json (avec calibration)
    prefs_path = os.path.join(output_dir, 'preferences.json')
    if prefs:
        prefs_to_save = dict(prefs)
        if calibration:
            prefs_to_save['calibration'] = calibration
        with open(prefs_path, 'w', encoding='utf-8') as f:
            json.dump(prefs_to_save, f, ensure_ascii=False, indent=2)

    result = {
        "status": "OK",
        "total_feedbacks": len(feedbacks),
        "preferences": prefs,
        "calibration": calibration,
        "prompt_paragraph": prompt_para,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
