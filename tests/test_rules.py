import pandas as pd

from src.features import daily, rolling_window
from src.rules import dormant_reactivation, pass_through, structuring
from src.simulate import CASH_THRESHOLD

T0 = pd.Timestamp("2026-03-01 10:00")


def tx(rows):
    df = pd.DataFrame(rows, columns=["customer_id", "timestamp", "amount",
                                     "direction", "channel", "counterparty"])
    df.insert(0, "txn_id", range(len(df)))
    return df


def day(n, hour=10):
    return T0 + pd.Timedelta(days=n, hours=hour - 10)


def test_structuring_fires_on_three_near_threshold_deposits():
    near = 0.9 * CASH_THRESHOLD
    t = tx([("A", day(0), near, "in", "cash", "branch"),
            ("A", day(2), near, "in", "cash", "branch"),
            ("A", day(5), near, "in", "cash", "branch")])
    assert list(structuring(t)["customer_id"]) == ["A"]


def test_structuring_ignores_deposits_spread_out_or_over_threshold():
    near = 0.9 * CASH_THRESHOLD
    spread = tx([("A", day(0), near, "in", "cash", "branch"),
                 ("A", day(10), near, "in", "cash", "branch"),
                 ("A", day(20), near, "in", "cash", "branch")])
    over = tx([("B", day(i), CASH_THRESHOLD + 1, "in", "cash", "branch") for i in range(3)])
    small = tx([("C", day(i), 5_000, "in", "cash", "branch") for i in range(5)])
    assert structuring(spread).empty
    assert structuring(over).empty
    assert structuring(small).empty


def test_pass_through_fires_for_mule_but_not_for_saver():
    rows = [("M", day(i % 5), 4_000, "in", "instant", f"s{i}") for i in range(10)]
    rows += [("M", day(i % 5, 15), 3_800, "out", "atm", "x") for i in range(10)]
    rows += [("S", day(i % 5), 4_000, "in", "instant", f"s{i}") for i in range(10)]
    w = rolling_window(daily(tx(rows)))
    assert list(pass_through(w)["customer_id"]) == ["M"]


def test_pass_through_needs_enough_senders():
    rows = [("M", day(i), 10_000, "in", "instant", f"s{i % 3}") for i in range(5)]
    rows += [("M", day(i, 15), 9_500, "out", "atm", "x") for i in range(5)]
    w = rolling_window(daily(tx(rows)))
    assert pass_through(w).empty


def test_dormant_reactivation():
    t = tx([("D", day(0), 300, "out", "card", "shop"),
            ("D", day(90), 40_000, "in", "eft", "p1"),
            ("D", day(91), 30_000, "in", "eft", "p2"),
            ("A", day(0), 300, "out", "card", "shop"),
            ("A", day(5), 80_000, "in", "eft", "p1")])
    out = dormant_reactivation(t)
    assert list(out["customer_id"]) == ["D"]
    assert "inactive 90 days" in out["reason"].iloc[0]
