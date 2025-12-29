import pytest

from app.evaluation.prior_art_ground_truth_dataset import (
    evaluate_retrieval,
    normalize_citation,
)


def test_normalize_citation_patent_basic():
    c = normalize_citation("US20140072209 A1")
    assert c.citation_type == "patent"
    assert c.country == "US"
    assert c.number == "20140072209"
    assert c.kind == "A1"
    assert c.normalized_id == "US20140072209A1"


def test_normalize_citation_patent_with_slashes():
    c = normalize_citation("US 2014/0072209 A1")
    assert c.citation_type == "patent"
    assert c.normalized_id == "US20140072209A1"


def test_normalize_citation_npl_heuristic():
    c = normalize_citation("Smith et al., Journal of Testing, 2019")
    assert c.citation_type == "npl"
    assert c.normalized_id is None


def test_evaluate_retrieval_matches_after_normalization():
    gt = ["US 2014/0072209 A1", "JP2000123456 A"]
    pred = ["US20140072209A1", "JP 2000123456 A", "CN1234567 A"]
    m = evaluate_retrieval(predicted=pred, ground_truth=gt)
    assert m.tp == 2
    assert m.fp == 1
    assert m.fn == 0
    assert pytest.approx(m.precision, rel=1e-6) == 2 / 3
    assert pytest.approx(m.recall, rel=1e-6) == 1.0
