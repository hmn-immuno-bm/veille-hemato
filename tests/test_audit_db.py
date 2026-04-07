"""Tests pour outils/audit_db.py — regex-traps et chargement catégories."""
import os, sys, json, tempfile, shutil
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'outils'))

import audit_db as a


# ─── doi_hallucination_trap ─────────────────────────────────────

def test_trap_none_for_valid_doi():
    assert a.doi_hallucination_trap("10.1056/nejmoa1234567") is None

def test_trap_none_for_empty():
    assert a.doi_hallucination_trap("") is None
    assert a.doi_hallucination_trap(None) is None

def test_trap_doi_with_spaces():
    msg = a.doi_hallucination_trap("10.1056/nejm oa1234567")
    assert msg is not None and "espace" in msg.lower()

def test_trap_arxiv_invalid_month():
    msg = a.doi_hallucination_trap("2613.01234")  # mois 13 invalide
    assert msg is not None and "mois invalide" in msg

def test_trap_arxiv_valid_month():
    assert a.doi_hallucination_trap("2603.01234") is None

def test_trap_arxiv_with_prefix():
    msg = a.doi_hallucination_trap("arxiv:2613.01234")
    assert msg is not None

def test_trap_arxiv_year_far_future():
    msg = a.doi_hallucination_trap("3501.00001")
    assert msg is not None and "année improbable" in msg


# ─── load_categories (avec fallback) ────────────────────────────

def test_load_categories_from_json():
    """Charge depuis le vrai categories.json du repo."""
    cats = a.load_categories(ROOT)
    assert "ctDNA — Lymphomes" in cats
    assert "Lymphomes" in cats
    assert len(cats) >= 5

def test_load_categories_fallback_on_missing_dir():
    """Si le dossier n'existe pas, fallback hardcodé."""
    cats = a.load_categories("/nonexistent/path")
    assert "ctDNA — Lymphomes" in cats  # présent dans le fallback


# ─── run_audit (intégration sur mini-base) ──────────────────────

def test_run_audit_clean_db(tmp_path):
    """Audit sur une mini-base propre : 0 erreur."""
    # Setup veille_dir minimal
    veille = tmp_path / "veille"
    (veille / "outils").mkdir(parents=True)
    (veille / "output").mkdir()
    # Copier categories.json
    shutil.copy(os.path.join(ROOT, "outils", "categories.json"),
                veille / "outils" / "categories.json")
    # Mini-base
    db = [{
        "semaine": "2026-S14",
        "titre": "Test article on ctDNA in DLBCL",
        "doi": "10.1056/nejmoa1234567",
        "pmid": "12345678",
        "journal": "NEJM",
        "categorie": "ctDNA — Lymphomes",
        "resume": "A test resume",
        "critique": "A test critique",
        "score": 8,
        "date_pub": "2026-03-25",
    }]
    (veille / "output" / "articles_db.json").write_text(json.dumps(db), encoding="utf-8")
    report = a.run_audit(str(veille))
    assert report["total_articles"] == 1
    assert len(report["errors"]) == 0


def test_run_audit_detects_invalid_date_format(tmp_path):
    """date_pub mal formée → ERROR (pas warning)."""
    veille = tmp_path / "veille"
    (veille / "outils").mkdir(parents=True)
    (veille / "output").mkdir()
    shutil.copy(os.path.join(ROOT, "outils", "categories.json"),
                veille / "outils" / "categories.json")
    db = [{
        "semaine": "2026-S14",
        "titre": "Bad date article",
        "doi": "10.1/x",
        "pmid": "1",
        "journal": "J",
        "categorie": "Lymphomes",
        "resume": "r",
        "critique": "c",
        "score": 5,
        "date_pub": "2026-03",  # YYYY-MM : invalide après normalisation
    }]
    (veille / "output" / "articles_db.json").write_text(json.dumps(db), encoding="utf-8")
    report = a.run_audit(str(veille))
    assert any("date_pub" in e for e in report["errors"])


def test_run_audit_detects_doi_hallucination(tmp_path):
    veille = tmp_path / "veille"
    (veille / "outils").mkdir(parents=True)
    (veille / "output").mkdir()
    shutil.copy(os.path.join(ROOT, "outils", "categories.json"),
                veille / "outils" / "categories.json")
    db = [{
        "semaine": "2026-S14",
        "titre": "Article with bad arxiv id",
        "doi": "2613.01234",  # mois 13 → trap
        "journal": "arXiv",
        "categorie": "Preprint",
        "resume": "r",
        "score": 5,
        "date_pub": "2026-03-25",
    }]
    (veille / "output" / "articles_db.json").write_text(json.dumps(db), encoding="utf-8")
    report = a.run_audit(str(veille))
    assert any("hallucination" in e.lower() or "mois invalide" in e for e in report["errors"])


def test_run_audit_detects_invalid_category(tmp_path):
    veille = tmp_path / "veille"
    (veille / "outils").mkdir(parents=True)
    (veille / "output").mkdir()
    shutil.copy(os.path.join(ROOT, "outils", "categories.json"),
                veille / "outils" / "categories.json")
    db = [{
        "semaine": "2026-S14",
        "titre": "Misclassified article",
        "doi": "10.1/x",
        "pmid": "1",
        "journal": "J",
        "categorie": "Catégorie Inventée",
        "resume": "r",
        "critique": "c",
        "score": 5,
        "date_pub": "2026-03-25",
    }]
    (veille / "output" / "articles_db.json").write_text(json.dumps(db), encoding="utf-8")
    report = a.run_audit(str(veille))
    assert any("Catégorie Inventée" in w or "categorie" in w.lower() for w in report["warnings"])
