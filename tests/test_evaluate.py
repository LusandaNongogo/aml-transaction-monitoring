import pandas as pd
import pytest

from src.evaluate import (capacity_curve, overall_quality, precision_at_k,
                          recall_at_k, rule_quality)


def customers():
    return pd.DataFrame({
        "customer_id": ["a", "b", "c", "d", "e"],
        "typology": ["structuring", "mule", "none", "none", "mule"],
        "is_suspicious": [1, 1, 0, 0, 1],
    })


def test_rule_quality_counts():
    alerts = pd.DataFrame({"customer_id": ["a", "c", "b", "d"],
                           "rule": ["structuring", "structuring",
                                    "pass_through", "pass_through"]})
    q = rule_quality(alerts, customers()).set_index("rule")
    assert q.loc["structuring", "precision"] == pytest.approx(0.5)
    assert q.loc["structuring", "recall_on_target"] == pytest.approx(1.0)
    assert q.loc["pass_through", "recall_on_target"] == pytest.approx(0.5)
    assert q.loc["dormant_reactivation", "alerts"] == 0


def test_overall_quality():
    q = overall_quality(["a", "b", "c"], customers())
    assert q["precision"] == pytest.approx(2 / 3)
    assert q["recall"] == pytest.approx(2 / 3)
    assert q["alerts_per_1000_customers"] == pytest.approx(600)


def test_precision_and_recall_at_k():
    y = [1, 0, 1, 0, 0]
    s = [0.9, 0.8, 0.7, 0.2, 0.1]
    assert precision_at_k(y, s, 2) == pytest.approx(0.5)
    assert recall_at_k(y, s, 3) == pytest.approx(1.0)
    c = capacity_curve(y, s, [1, 3])
    assert list(c["precision"]) == pytest.approx([1.0, 2 / 3])
