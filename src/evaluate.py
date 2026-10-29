"""Alert quality measures.

Precision is the share of alerts that turn out to be suspicious, which
drives investigator workload. Recall is the share of suspicious customers
that get an alert at all, which drives regulatory risk. Tuning a rule is
mostly about trading one against the other.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

RULE_TARGET = {
    "structuring": "structuring",
    "pass_through": "mule",
    "dormant_reactivation": "dormant",
}


def rule_quality(alerts, customers):
    """Per rule: alerts raised, true positives, precision and recall
    against the typology the rule is designed to catch."""
    lab = customers.set_index("customer_id")
    rows = []
    for rule, target in RULE_TARGET.items():
        hit = alerts.loc[alerts["rule"] == rule, "customer_id"].unique()
        typ = lab.loc[hit, "typology"]
        tp = int((typ != "none").sum())
        n_target = int((lab["typology"] == target).sum())
        caught = int((typ == target).sum())
        rows.append({
            "rule": rule,
            "alerts": len(hit),
            "true_positives": tp,
            "false_positives": len(hit) - tp,
            "precision": tp / len(hit) if len(hit) else np.nan,
            "recall_on_target": caught / n_target if n_target else np.nan,
        })
    return pd.DataFrame(rows)


def overall_quality(alerted_ids, customers):
    lab = customers.set_index("customer_id")["is_suspicious"]
    alerted = lab.index.isin(list(alerted_ids))
    tp = int((alerted & (lab == 1)).sum())
    return {
        "customers_alerted": int(alerted.sum()),
        "true_positives": tp,
        "precision": tp / alerted.sum() if alerted.sum() else np.nan,
        "recall": tp / lab.sum(),
        "alerts_per_1000_customers": 1000 * alerted.sum() / len(lab),
    }


def precision_at_k(y, score, k):
    order = np.argsort(-np.asarray(score))[:k]
    return float(np.asarray(y)[order].mean())


def recall_at_k(y, score, k):
    y = np.asarray(y)
    order = np.argsort(-np.asarray(score))[:k]
    return float(y[order].sum() / y.sum())


def average_precision(y, score):
    """Area under the precision recall curve. The baseline is the bad rate."""
    return float(average_precision_score(y, score))


def capacity_curve(y, score, ks):
    """Precision and recall if investigators can only work the top k cases."""
    return pd.DataFrame({
        "k": ks,
        "precision": [precision_at_k(y, score, k) for k in ks],
        "recall": [recall_at_k(y, score, k) for k in ks],
    })
