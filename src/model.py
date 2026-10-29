"""Two models.

anomaly_scores: an unsupervised isolation forest. Rules only catch
patterns someone thought of in advance; this scores every customer on how
unusual they are with no labels needed.

triage_scores: a supervised model trained on the outcome of past alerts
(suspicious or closed as a false positive). It does not raise alerts, it
ranks the ones the rules raised so investigators work the likely cases
first. This is where most of the false positive reduction in practice
comes from.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, IsolationForest
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import StandardScaler

FEATURES = [
    "total_in", "total_out", "n_in", "n_out", "cash_in_share",
    "n_near_threshold", "n_distinct_senders", "atm_out", "max_gap_days",
    "out_in_ratio", "avg_in_amount", "account_age_days",
    "repeat_sender_share", "round_in_share",
]
# heavy tailed money and count columns are logged before scaling
LOG_COLS = ["total_in", "total_out", "n_in", "n_out", "n_near_threshold",
            "n_distinct_senders", "atm_out", "avg_in_amount", "account_age_days"]


def prepare(features):
    X = features[FEATURES].copy()
    X[LOG_COLS] = np.log1p(X[LOG_COLS])
    return StandardScaler().fit_transform(X)


def anomaly_scores(features, seed=7, n_estimators=300):
    """Higher score means more unusual."""
    model = IsolationForest(n_estimators=n_estimators, contamination="auto",
                            random_state=seed)
    model.fit(prepare(features))
    return pd.Series(-model.score_samples(prepare(features)),
                     index=features.index, name="anomaly_score")


def triage_scores(features, labels, seed=7, folds=5):
    """Out of fold probability that an alerted customer is suspicious.

    features and labels should cover alerted customers only. Every score
    comes from a model that never saw that customer, so the ranking can be
    evaluated honestly.
    """
    model = GradientBoostingClassifier(n_estimators=200, max_depth=2,
                                       learning_rate=0.05, random_state=seed)
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    p = cross_val_predict(model, features[FEATURES], labels, cv=cv,
                          method="predict_proba")[:, 1]
    return pd.Series(p, index=features.index, name="triage_score")


def feature_importance(features, labels, seed=7):
    model = GradientBoostingClassifier(n_estimators=200, max_depth=2,
                                       learning_rate=0.05, random_state=seed)
    model.fit(features[FEATURES], labels)
    return (pd.Series(model.feature_importances_, index=FEATURES)
            .sort_values(ascending=False))
