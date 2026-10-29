"""Transaction monitoring rules.

Each rule returns one row per customer it fires on, with the date of the
first hit and a short reason an investigator can read. Thresholds are
arguments so they can be tuned (see the tuning section in the notebook).
"""

import pandas as pd

from src.features import near_threshold
from src.simulate import CASH_THRESHOLD


def _alerts(df, rule, reason):
    if df.empty:
        return pd.DataFrame(columns=["customer_id", "rule", "alert_date", "reason"])
    first = df.sort_values("date").groupby("customer_id").first().reset_index()
    return pd.DataFrame({
        "customer_id": first["customer_id"],
        "rule": rule,
        "alert_date": first["date"],
        "reason": first.apply(reason, axis=1),
    })


def structuring(tx, min_count=3, window_days=7, floor=0.8, threshold=CASH_THRESHOLD):
    """Several cash deposits just under the reporting threshold in a short window."""
    hits = tx[near_threshold(tx, threshold, floor)].copy()
    hits["date"] = hits["timestamp"].dt.normalize()
    rows = []
    for cid, g in hits.groupby("customer_id"):
        s = g.set_index("timestamp")["amount"].sort_index()
        counts = s.rolling(f"{window_days}D").count()
        sums = s.rolling(f"{window_days}D").sum()
        mask = (counts >= min_count).to_numpy()
        if mask.any():
            i = mask.argmax()
            rows.append({"customer_id": cid, "date": counts.index[i].normalize(),
                         "count": int(counts.iloc[i]), "total": sums.iloc[i]})
    return _alerts(pd.DataFrame(rows), "structuring",
                   lambda r: f"{r['count']} cash deposits under the threshold in "
                             f"{window_days} days, R{r['total']:,.0f} in total")


def pass_through(window, min_senders=8, min_ratio=0.8, min_amount=20_000):
    """Mule pattern: many distinct senders and most of the money already gone."""
    w = window.assign(ratio=window["amount_out"] / window["amount_in"].where(window["amount_in"] > 0))
    hit = w[(w["distinct_senders"] >= min_senders) & (w["ratio"] >= min_ratio)
            & (w["amount_in"] >= min_amount)]
    return _alerts(hit, "pass_through",
                   lambda r: f"{int(r['distinct_senders'])} senders in 7 days, "
                             f"R{r['amount_in']:,.0f} in and {r['ratio']:.0%} sent out")


def dormant_reactivation(tx, min_gap_days=60, min_inflow=50_000, window_days=7):
    """No activity for a long time, then a large amount of money arrives."""
    t = tx.sort_values(["customer_id", "timestamp"]).copy()
    t["gap"] = t.groupby("customer_id")["timestamp"].diff().dt.days
    rows = []
    for _, r in t[t["gap"] >= min_gap_days].iterrows():
        g = t[(t["customer_id"] == r["customer_id"]) & (t["direction"] == "in")
              & (t["timestamp"] >= r["timestamp"])
              & (t["timestamp"] < r["timestamp"] + pd.Timedelta(days=window_days))]
        if g["amount"].sum() >= min_inflow:
            rows.append({"customer_id": r["customer_id"], "date": r["timestamp"].normalize(),
                         "gap": int(r["gap"]), "inflow": g["amount"].sum()})
    return _alerts(pd.DataFrame(rows), "dormant_reactivation",
                   lambda r: f"inactive {r['gap']} days, then R{r['inflow']:,.0f} "
                             f"in within {window_days} days")


def run_all(tx, window, **overrides):
    """Run every rule and stack the alerts."""
    return pd.concat([
        structuring(tx, **overrides.get("structuring", {})),
        pass_through(window, **overrides.get("pass_through", {})),
        dormant_reactivation(tx, **overrides.get("dormant_reactivation", {})),
    ], ignore_index=True)
