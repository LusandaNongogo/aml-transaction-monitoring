"""Daily and customer level aggregates used by the rules and the model."""

import numpy as np
import pandas as pd

from src.simulate import CASH_THRESHOLD

NEAR_THRESHOLD_FLOOR = 0.8


def near_threshold(tx, threshold=CASH_THRESHOLD, floor=NEAR_THRESHOLD_FLOOR):
    """Cash deposits between floor x threshold and the threshold itself."""
    return ((tx["channel"] == "cash") & (tx["direction"] == "in")
            & (tx["amount"] >= floor * threshold) & (tx["amount"] < threshold))


def daily(tx):
    """One row per customer per calendar day with flows and distinct senders."""
    t = tx.assign(date=tx["timestamp"].dt.normalize())
    inflow = t[t["direction"] == "in"]
    outflow = t[t["direction"] == "out"]

    d_in = inflow.groupby(["customer_id", "date"]).agg(
        amount_in=("amount", "sum"), n_in=("amount", "size"))
    d_out = outflow.groupby(["customer_id", "date"]).agg(
        amount_out=("amount", "sum"), n_out=("amount", "size"))
    # senders are counted on transfers only; cash and salary do not count
    p2p = inflow[inflow["channel"].isin(["instant", "eft"])]
    d_send = p2p.groupby(["customer_id", "date"])["counterparty"].agg(list).rename("senders")

    d = d_in.join(d_out, how="outer").join(d_send, how="left").reset_index()
    d[["amount_in", "n_in", "amount_out", "n_out"]] = (
        d[["amount_in", "n_in", "amount_out", "n_out"]].fillna(0))
    d["senders"] = d["senders"].apply(lambda v: v if isinstance(v, list) else [])
    return d.sort_values(["customer_id", "date"]).reset_index(drop=True)


def rolling_window(d, days=7):
    """Rolling sums over the previous `days` calendar days, per customer,
    plus the count of distinct senders in that window."""
    out = []
    for cid, g in d.groupby("customer_id", sort=False):
        g = g.set_index("date").asfreq("D")
        g["customer_id"] = cid
        for c in ["amount_in", "amount_out", "n_in", "n_out"]:
            g[c] = g[c].fillna(0)
        g["senders"] = g["senders"].apply(lambda v: v if isinstance(v, list) else [])
        r = g[["amount_in", "amount_out", "n_in", "n_out"]].rolling(f"{days}D").sum()
        sender_sets = g["senders"].tolist()
        distinct = [len(set().union(*[set(s) for s in sender_sets[max(0, i - days + 1): i + 1]]))
                    for i in range(len(sender_sets))]
        r["distinct_senders"] = distinct
        r["customer_id"] = cid
        out.append(r.reset_index())
    return pd.concat(out, ignore_index=True)


def customer_features(tx, customers):
    """One row per customer, used by the anomaly model."""
    t = tx.copy()
    t["near"] = near_threshold(t)
    inflow = t[t["direction"] == "in"]
    outflow = t[t["direction"] == "out"]

    f = pd.DataFrame(index=customers["customer_id"])
    f["total_in"] = inflow.groupby("customer_id")["amount"].sum()
    f["total_out"] = outflow.groupby("customer_id")["amount"].sum()
    f["n_in"] = inflow.groupby("customer_id").size()
    f["n_out"] = outflow.groupby("customer_id").size()
    f["cash_in"] = inflow[inflow["channel"] == "cash"].groupby("customer_id")["amount"].sum()
    f["n_near_threshold"] = t.groupby("customer_id")["near"].sum()
    f["n_distinct_senders"] = (inflow[inflow["channel"].isin(["instant", "eft"])]
                               .groupby("customer_id")["counterparty"].nunique())
    f["atm_out"] = outflow[outflow["channel"] == "atm"].groupby("customer_id")["amount"].sum()

    # stokvel members pay every month, scam victims sending to a mule do not
    p2p = inflow[inflow["channel"].isin(["instant", "eft"])]
    per_sender = p2p.groupby(["customer_id", "counterparty"]).size()
    f["repeat_sender_share"] = (per_sender > 1).groupby("customer_id").mean()
    # contributions and legitimate payments tend to be round numbers
    f["round_in_share"] = (inflow["amount"] % 100 == 0).groupby(inflow["customer_id"]).mean()
    f = f.fillna(0)

    gaps = (t.sort_values("timestamp").groupby("customer_id")["timestamp"]
            .diff().dt.days.groupby(t["customer_id"]).max())
    f["max_gap_days"] = gaps.reindex(f.index).fillna(0)

    f["cash_in_share"] = np.where(f["total_in"] > 0, f["cash_in"] / f["total_in"], 0)
    f["out_in_ratio"] = np.where(f["total_in"] > 0, f["total_out"] / f["total_in"], 0)
    f["avg_in_amount"] = np.where(f["n_in"] > 0, f["total_in"] / f["n_in"], 0)
    f["account_age_days"] = customers.set_index("customer_id")["account_age_days"]
    return f
