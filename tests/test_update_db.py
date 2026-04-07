"""Tests pour outils/update_db.py — déduplication et normalisation."""
import os, sys, json
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'outils'))

import update_db as u


# ─── normalize_date_pub ──────────────────────────────────────────

def test_date_pub_full_format():
    assert u.normalize_date_pub("2026-03-25") == "2026-03-25"

def test_date_pub_year_month():
    assert u.normalize_date_pub("2026-03") == "2026-03-01"

def test_date_pub_year_only():
    assert u.normalize_date_pub("2026") == "2026-01-01"

def test_date_pub_empty():
    assert u.normalize_date_pub("") == ""
    assert u.normalize_date_pub(None) == ""

def test_date_pub_unknown_format_passthrough():
    # Format inconnu : on retourne tel quel et l'audit signalera
    assert u.normalize_date_pub("25/03/2026") == "25/03/2026"


# ─── fix_semaine ─────────────────────────────────────────────────

def test_fix_semaine_W_to_S():
    assert u.fix_semaine("2026-W14") == "2026-S14"

def test_fix_semaine_already_S():
    assert u.fix_semaine("2026-S14") == "2026-S14"

def test_fix_semaine_empty_returns_current():
    s = u.fix_semaine("")
    assert s.startswith("20") and "-S" in s


# ─── normalize_keys (alias court → long) ────────────────────────

def test_normalize_keys_aliases():
    art = {"auteur": "Doe", "senior": "Smith", "tags": "ctDNA", "if_val": 10, "affFR": "Oui"}
    out = u.normalize_keys(art)
    assert out["premier_auteur"] == "Doe"
    assert out["senior_auteur"] == "Smith"
    assert out["tag"] == "ctDNA"
    assert out["if_value"] == 10
    assert out["affiliations_fr"] == "Oui"

def test_normalize_keys_preserves_unknown():
    art = {"foo": "bar", "titre": "T"}
    out = u.normalize_keys(art)
    assert out["foo"] == "bar"
    assert out["titre"] == "T"


# ─── normalize_title ─────────────────────────────────────────────

def test_normalize_title_strips_punctuation():
    assert u.normalize_title("Hello, World!") == "hello world"

def test_normalize_title_collapses_spaces():
    assert u.normalize_title("Foo   bar    baz") == "foo bar baz"

def test_normalize_title_none():
    assert u.normalize_title(None) == ""


# ─── normalize_article (defaults + types) ───────────────────────

def test_normalize_article_fills_defaults():
    art = u.normalize_article({"titre": "T", "doi": "10.1/x"})
    assert art["preprint"] == "Publié"
    assert art["if_value"] == 0
    assert art["score"] == 0
    assert art["pmid"] == ""

def test_normalize_article_normalizes_date():
    art = u.normalize_article({"titre": "T", "date_pub": "2026-03"})
    assert art["date_pub"] == "2026-03-01"


# ─── Déduplication : DOI / PMID / titre / preprint→pub ──────────

def make_db():
    return [
        u.normalize_article({
            "titre": "ctDNA monitoring in DLBCL",
            "doi": "10.1056/nejmoa1234567",
            "pmid": "12345678",
            "preprint": "Publié",
        }),
    ]


def test_dedup_by_doi():
    db = make_db()
    new = [{"titre": "Tout autre titre", "doi": "10.1056/nejmoa1234567", "pmid": "99999999"}]
    written, dups, trans = u.import_articles(db, new)
    assert written == 0
    assert len(dups) == 1
    assert dups[0]["reason"] == "dup_doi"


def test_dedup_by_pmid():
    db = make_db()
    new = [{"titre": "Titre différent", "doi": "10.999/other", "pmid": "12345678"}]
    written, dups, trans = u.import_articles(db, new)
    assert written == 0
    assert len(dups) == 1
    assert dups[0]["reason"] == "dup_pmid"


def test_dedup_by_title():
    db = make_db()
    new = [{"titre": "ctDNA monitoring in DLBCL", "doi": "10.999/other", "pmid": "99999999"}]
    written, dups, trans = u.import_articles(db, new)
    assert written == 0
    assert len(dups) == 1
    assert dups[0]["reason"] == "dup_title"


def test_preprint_to_published_transition():
    db = [u.normalize_article({
        "titre": "MRD-guided CAR-T therapy in B-cell lymphoma",
        "doi": "10.1101/2025.01.01.000001",
        "preprint": "Preprint",
    })]
    new = [{
        "titre": "MRD-guided CAR-T therapy in B-cell lymphoma",
        "doi": "10.1056/nejmoa9999999",
        "pmid": "44444444",
        "journal": "NEJM",
        "preprint": "Publié",
        "if_value": 100,
    }]
    written, dups, trans = u.import_articles(db, new)
    assert written == 0  # pas un nouvel article : transition in-place
    assert len(trans) == 1
    assert db[0]["preprint"] == "Publié"
    assert db[0]["doi"] == "10.1056/nejmoa9999999"
    assert db[0]["journal"] == "NEJM"


def test_new_article_added():
    db = make_db()
    new = [{"titre": "Phased variants improve ctDNA detection sensitivity in DLBCL",
            "doi": "10.1038/s41591-025-12345",
            "pmid": "55555555"}]
    written, dups, trans = u.import_articles(db, new)
    assert written == 1
    assert len(db) == 2


def test_idempotent_import():
    """Importer 2 fois le même article ne crée pas de doublon."""
    db = make_db()
    new = [{"titre": "Phased variants improve ctDNA detection sensitivity",
            "doi": "10.1038/s41591-025-99999",
            "pmid": "77777777"}]
    u.import_articles(db, new)
    written2, _, _ = u.import_articles(db, new)
    assert written2 == 0
    assert len(db) == 2
